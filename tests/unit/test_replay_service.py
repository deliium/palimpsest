"""Unit tests for ReplayService reconstruction and continuation gating."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    ReplayFallbackPolicy,
    ReplayMode,
    ReplayRequest,
    ReplayStatus,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.replay import ReplayService
from world.events import Waited, WorldEvent, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

pytestmark = pytest.mark.unit


def _alive() -> AgentBody:
    return AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
    )


def _snapshot(
    *,
    run_id: str = "run-1",
    next_tick: int = 0,
    revision: int = 0,
    predecessor: object | None = None,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-1"),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
        ),
        locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
        bodies=(_alive(),),
        items=(),
        resources=(),
        weather=(),
        next_tick=Tick(next_tick),
        revision=WorldRevision(revision),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=predecessor,  # type: ignore[arg-type]
    )
    return WorldSnapshot(
        snapshot_id=draft.snapshot_id,
        run_id=draft.run_id,
        world_id=draft.world_id,
        seed=draft.seed,
        config=draft.config,
        registrations=draft.registrations,
        locations=draft.locations,
        bodies=draft.bodies,
        items=draft.items,
        resources=draft.resources,
        weather=draft.weather,
        next_tick=draft.next_tick,
        revision=draft.revision,
        event_schema_version=draft.event_schema_version,
        projector_version=draft.projector_version,
        persistence_codec_version=draft.persistence_codec_version,
        derivation_version=draft.derivation_version,
        integrity_hash=hash_snapshot(draft),
        predecessor_commit_hash=draft.predecessor_commit_hash,
    )


def _manifest(run_id: str = "run-1") -> RunManifest:
    return RunManifest(
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _commit_for(
    request: TickAppendRequest, *, resulting_revision: WorldRevision
) -> TickCommit:
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting_revision,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None,
    )


class _FakeRuns:
    def __init__(self, manifest: RunManifest | None) -> None:
        self.manifest = manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        if self.manifest is None or self.manifest.run_id != run_id:
            return None
        return self.manifest

    async def create_run(self, request: object) -> RunManifest:
        raise NotImplementedError


class _FakeSnapshots:
    def __init__(self, snapshots: list[WorldSnapshot]) -> None:
        self.snapshots = snapshots

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        candidates = [
            item
            for item in self.snapshots
            if item.run_id == run_id and item.next_tick.value <= tick.value
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.next_tick.value)

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        for item in self.snapshots:
            if item.snapshot_id == snapshot_id:
                return item
        return None


class _FakeJournal:
    def __init__(
        self,
        commits: list[TickCommit] | None = None,
        events: list[WorldEvent] | None = None,
    ) -> None:
        self.commits = commits or []
        self.events = events or []

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        raise NotImplementedError

    async def get_tick_commit(
        self, run_id: RunId, tick: Tick
    ) -> TickCommit | None:
        for item in self.commits:
            if item.run_id == run_id and item.tick == tick:
                return item
        return None

    async def list_events(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
        limit: int,
        offset: int,
    ) -> tuple[WorldEvent, ...]:
        selected = [
            event
            for event in self.events
            if event.run_id == run_id.value
            and event.tick >= from_tick.value
            and (to_tick is None or event.tick <= to_tick.value)
        ]
        return tuple(selected[offset : offset + limit])

    async def list_tick_commits(
        self,
        run_id: RunId,
        *,
        from_tick: Tick,
        to_tick: Tick | None,
    ) -> tuple[TickCommit, ...]:
        selected = [
            item
            for item in self.commits
            if item.run_id == run_id
            and item.tick.value >= from_tick.value
            and (to_tick is None or item.tick.value <= to_tick.value)
        ]
        return tuple(sorted(selected, key=lambda item: item.tick.value))


@pytest.mark.asyncio
async def test_bootstrap_only_replay_at_tick_zero() -> None:
    snapshot = _snapshot()
    service = ReplayService(
        _FakeRuns(_manifest()),
        _FakeJournal(),
        _FakeSnapshots([snapshot]),
    )
    outcome = await service.replay(
        ReplayRequest(run_id=RunId("run-1"), target_tick=Tick(0))
    )
    assert outcome.result.status is ReplayStatus.OK
    assert outcome.result.mode is ReplayMode.CONTINUATION
    assert outcome.engine is not None
    assert outcome.engine.tick == Tick(0)
    assert outcome.predecessor_commit_hash is None


@pytest.mark.asyncio
async def test_replay_with_events_at_head_is_continuation() -> None:
    snapshot = _snapshot()
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    request = TickAppendRequest(
        run_id=RunId("run-1"),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="idem-0",
        events=(event,),
    )
    commit = _commit_for(request, resulting_revision=WorldRevision(0))
    service = ReplayService(
        _FakeRuns(_manifest()),
        _FakeJournal(commits=[commit], events=[event]),
        _FakeSnapshots([snapshot]),
    )
    outcome = await service.replay(
        ReplayRequest(run_id=RunId("run-1"), target_tick=None)
    )
    assert outcome.result.status is ReplayStatus.OK
    assert outcome.result.mode is ReplayMode.CONTINUATION
    assert outcome.result.events_applied == 1
    assert outcome.engine is not None
    assert outcome.engine.tick == Tick(1)
    durable = service.open_durable(outcome, _FakeJournal(commits=[commit]))
    assert durable.engine.tick == Tick(1)


@pytest.mark.asyncio
async def test_historical_target_is_readonly_and_blocks_durable() -> None:
    snapshot = _snapshot()
    empty_req = TickAppendRequest(
        run_id=RunId("run-1"),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="idem-0",
        events=(),
    )
    commit0 = _commit_for(empty_req, resulting_revision=WorldRevision(0))
    empty_req1 = TickAppendRequest(
        run_id=RunId("run-1"),
        tick=Tick(1),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=commit0.commit_hash,
        idempotency_key="idem-1",
        events=(),
    )
    commit1 = _commit_for(empty_req1, resulting_revision=WorldRevision(0))
    service = ReplayService(
        _FakeRuns(_manifest()),
        _FakeJournal(commits=[commit0, commit1]),
        _FakeSnapshots([snapshot]),
    )
    outcome = await service.replay(
        ReplayRequest(run_id=RunId("run-1"), target_tick=Tick(1))
    )
    assert outcome.result.status is ReplayStatus.OK
    assert outcome.result.mode is ReplayMode.READONLY
    assert outcome.engine is not None
    assert outcome.engine.tick == Tick(1)
    with pytest.raises(RuntimeError, match="read-only"):
        service.open_durable(outcome, _FakeJournal())


@pytest.mark.asyncio
async def test_version_mismatch_and_missing_snapshot() -> None:
    bad = RunManifest(
        run_id=RunId("run-1"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        derivation_version="v-old",
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )
    service = ReplayService(
        _FakeRuns(bad),
        _FakeJournal(),
        _FakeSnapshots([_snapshot()]),
    )
    outcome = await service.replay(
        ReplayRequest(run_id=RunId("run-1"), target_tick=Tick(0))
    )
    assert outcome.result.status is ReplayStatus.VERSION_INCOMPATIBLE

    service2 = ReplayService(
        _FakeRuns(_manifest()),
        _FakeJournal(),
        _FakeSnapshots([]),
    )
    missing = await service2.replay(
        ReplayRequest(run_id=RunId("run-1"), target_tick=Tick(0))
    )
    assert missing.result.status is ReplayStatus.SNAPSHOT_MISSING


@pytest.mark.asyncio
async def test_commit_gap_is_stream_discontinuity() -> None:
    snapshot = _snapshot()
    empty_req = TickAppendRequest(
        run_id=RunId("run-1"),
        tick=Tick(1),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="idem-1",
        events=(),
    )
    # tick 1 without tick 0 → gap when replaying to tick 2 from bootstrap
    commit = _commit_for(empty_req, resulting_revision=WorldRevision(0))
    service = ReplayService(
        _FakeRuns(_manifest()),
        _FakeJournal(commits=[commit]),
        _FakeSnapshots([snapshot]),
    )
    outcome = await service.replay(
        ReplayRequest(
            run_id=RunId("run-1"),
            target_tick=Tick(2),
            fallback_policy=ReplayFallbackPolicy.LATEST_AT_OR_BEFORE,
        )
    )
    assert outcome.result.status is ReplayStatus.STREAM_DISCONTINUITY
