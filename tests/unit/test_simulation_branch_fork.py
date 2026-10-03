"""Unit proofs for objective research-fork rematerialization."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration
from simulation.branch_service import BranchService
from simulation.branching import BranchError
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
    verify_commit_chain,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from tests.simulation_helpers import make_location, make_weather
from world.events import Waited, WorldEvent, make_replayable_event
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

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
        carry_capacity=CarryCapacity(10),
    )


def _snapshot(
    *,
    run_id: str = "parent-run",
    snapshot_id: str = "snap-0",
    next_tick: int = 0,
    revision: int = 0,
    predecessor: object | None = None,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(snapshot_id),
        run_id=RunId(run_id),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(make_location("loc-1", name="Camp"),),
        bodies=(_alive(),),
        items=(),
        resources=(),
        weather=(make_weather(),),
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


def _manifest(run_id: str = "parent-run") -> RunManifest:
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
        snapshot_id=None if request.snapshot is None else request.snapshot.snapshot_id,
    )


class _FakeRuns:
    def __init__(self, manifests: dict[str, RunManifest] | None = None) -> None:
        self.manifests = manifests or {}
        self.create_calls: list[RunCreateRequest] = []

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        return self.manifests.get(run_id.value)

    async def create_run(self, request: RunCreateRequest) -> RunManifest:
        self.create_calls.append(request)
        if request.run_id.value in self.manifests:
            raise RuntimeError("run_exists")
        manifest = RunManifest(
            run_id=request.run_id,
            world_id=request.world_id,
            seed=request.seed,
            config=request.config,
            derivation_version=request.derivation_version,
            event_schema_version=request.event_schema_version,
            projector_version=request.projector_version,
            persistence_codec_version=request.persistence_codec_version,
        )
        self.manifests[request.run_id.value] = manifest
        return manifest


class _FakeSnapshots:
    def __init__(self, snapshots: list[WorldSnapshot]) -> None:
        self.snapshots = list(snapshots)

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
        self.commits = list(commits or [])
        self.events = list(events or [])
        self.append_calls: list[TickAppendRequest] = []

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        self.append_calls.append(request)
        commit = _commit_for(
            request, resulting_revision=WorldRevision(request.tick.value)
        )
        self.commits.append(commit)
        self.events.extend(request.events)
        if request.snapshot is not None:
            # Snapshot storage is owned by the snapshot fake in the service test.
            pass
        return commit

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
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
async def test_fork_tick_ahead_of_head_rejected() -> None:
    bootstrap = _snapshot()
    runs = _FakeRuns({bootstrap.run_id.value: _manifest()})
    journal = _FakeJournal()
    service = BranchService(
        runs=runs,
        journal=journal,
        snapshots=_FakeSnapshots([bootstrap]),
    )
    with pytest.raises(BranchError) as exc:
        await service.materialize_objective_fork(
            parent_run_id=RunId("parent-run"),
            child_run_id=RunId("child-run"),
            fork_tick=1,
        )
    assert exc.value.reason_code == "fork_tick_ahead_of_head"
    assert runs.create_calls == []


@pytest.mark.asyncio
async def test_objective_prefix_rematerialized_without_parent_mutation() -> None:
    bootstrap = _snapshot()
    event = make_replayable_event(
        event_id=EventId("evt-1"),
        run_id="parent-run",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    parent_request = TickAppendRequest(
        run_id=RunId("parent-run"),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="parent-idem-0",
        events=(event,),
    )
    parent_commit = _commit_for(parent_request, resulting_revision=WorldRevision(0))
    fork_point = _snapshot(
        snapshot_id="snap-fork",
        next_tick=1,
        revision=0,
        predecessor=parent_commit.commit_hash,
    )
    parent_hash = parent_commit.commit_hash.value

    runs = _FakeRuns({"parent-run": _manifest()})
    journal = _FakeJournal(commits=[parent_commit], events=[event])
    snapshots = _FakeSnapshots([bootstrap, fork_point])
    service = BranchService(runs=runs, journal=journal, snapshots=snapshots)

    result = await service.materialize_objective_fork(
        parent_run_id=RunId("parent-run"),
        child_run_id=RunId("child-run"),
        fork_tick=1,
    )

    assert result.child_run_id == RunId("child-run")
    assert result.fork_tick == 1
    assert result.event_count == 1
    assert len(result.child_commits) == 1
    child_commit = result.child_commits[0]
    assert child_commit.run_id == RunId("child-run")
    assert child_commit.commit_hash.value != parent_hash
    verify_commit_chain(result.child_commits)

    # Parent commit hash untouched.
    parent_after = await journal.list_tick_commits(
        RunId("parent-run"), from_tick=Tick(0), to_tick=None
    )
    assert parent_after[0].commit_hash.value == parent_hash
    assert parent_after[0].run_id == RunId("parent-run")

    child_events = await journal.list_events(
        RunId("child-run"),
        from_tick=Tick(0),
        to_tick=Tick(0),
        limit=10,
        offset=0,
    )
    assert len(child_events) == 1
    assert child_events[0].run_id == "child-run"
    assert child_events[0].event_id == event.event_id
