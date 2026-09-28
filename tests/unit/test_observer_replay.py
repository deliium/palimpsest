"""Historical observer frames come from a fresh fold, then drop the engine."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from api.errors import ApiError
from api.observer_service import ObserverReadService
from experiments.reference_scenario import LOC_CAMP, LOC_SPRING, _build_locations
from observer.layout import load_layout
from observer.sources import LiveObserverSource, ReplayObserverSource
from simulation.bootstrap import AgentRegistration
from simulation.clock import Tick
from simulation.journal import (
    compute_commit_hash,
    hash_snapshot,
    hash_tick_events,
    hash_tick_payload,
)
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.observer_facts import scene_from_facts
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    PayloadHash,
    ReplayRequest,
    ReplayStatus,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.replay import ReplayService, scene_at_tick, scene_through_event
from tests.simulation_helpers import alive_body, weather_for_locations
from world.effects import ActionCause, DeathCause, SystemCause, SystemEffectFamily
from world.events import (
    Died,
    Moved,
    Waited,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

RUN_ID = "run-observer"
WORLD_ID = "world-observer"
BODY_ID = "body-mira"
AGENT = "agent-mira"


def _snapshot() -> WorldSnapshot:
    locations = _build_locations()
    draft = WorldSnapshot(
        snapshot_id=SnapshotId("snap-observer"),
        run_id=RunId(RUN_ID),
        world_id=WorldId(WORLD_ID),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId(AGENT), EntityId(BODY_ID)),),
        locations=locations,
        bodies=(alive_body(BODY_ID, location_id=LOC_CAMP),),
        items=(),
        resources=(),
        weather=weather_for_locations(locations),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
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


def _manifest() -> RunManifest:
    return RunManifest(
        run_id=RunId(RUN_ID),
        world_id=WorldId(WORLD_ID),
        seed=7,
        config=SimulationRunConfig(seed=7),
        derivation_version=DERIVATION_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
    )


def _move_and_wait() -> tuple[WorldEvent, WorldEvent]:
    move = Moved(
        destination_id=EntityId(LOC_SPRING),
        resulting_location_id=EntityId(LOC_SPRING),
        fatigue_delta=0.0,
        resulting_fatigue=0.0,
    )
    moved = make_physical_replayable_event(
        event_id=EventId("evt-move"),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId("req-move"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(1),
        details=move,
        occurrence=build_occurrence_context(
            move, origin_location_id=EntityId(LOC_CAMP)
        ),
    )
    waited_details = Waited()
    waited = make_physical_replayable_event(
        event_id=EventId("evt-wait"),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=0,
        sequence=1,
        cause=ActionCause(RequestId("req-wait"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(1),
        details=waited_details,
        occurrence=build_occurrence_context(
            waited_details, origin_location_id=EntityId(LOC_CAMP)
        ),
    )
    return moved, waited


def _commit(events: tuple[WorldEvent, ...]) -> TickCommit:
    request = TickAppendRequest(
        run_id=RunId(RUN_ID),
        tick=Tick(0),
        expected_base_revision=WorldRevision(0),
        expected_predecessor_commit_hash=None,
        idempotency_key="idem-observer-0",
        events=events,
    )
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    resulting = WorldRevision(1)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None,
    )


class FakeRuns:
    def __init__(self, manifest: RunManifest) -> None:
        self.manifest = manifest

    async def get_run(self, run_id: RunId) -> RunManifest | None:
        if self.manifest.run_id != run_id:
            return None
        return self.manifest

    async def create_run(self, request: object) -> RunManifest:
        raise NotImplementedError


class FakeSnapshots:
    def __init__(self, snapshot: WorldSnapshot) -> None:
        self.snapshot = snapshot

    async def get_latest_at_or_before(
        self, run_id: RunId, tick: Tick
    ) -> WorldSnapshot | None:
        if self.snapshot.run_id != run_id:
            return None
        if self.snapshot.next_tick.value <= tick.value:
            return self.snapshot
        return None

    async def get_snapshot(self, snapshot_id: SnapshotId) -> WorldSnapshot | None:
        if self.snapshot.snapshot_id == snapshot_id:
            return self.snapshot
        return None


class FakeJournal:
    def __init__(
        self,
        commit: TickCommit,
        events: tuple[WorldEvent, ...] = (),
        *,
        commits: tuple[TickCommit, ...] | None = None,
    ) -> None:
        self.commits = (commit,) if commits is None else commits
        self.commit = self.commits[0]
        self.events = events
        self.appended: list[TickAppendRequest] = []

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        self.appended.append(request)
        raise NotImplementedError

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        for commit in self.commits:
            if commit.run_id == run_id and commit.tick == tick:
                return commit
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
            commit
            for commit in self.commits
            if commit.run_id == run_id
            and commit.tick.value >= from_tick.value
            and (to_tick is None or commit.tick.value <= to_tick.value)
        ]
        return tuple(sorted(selected, key=lambda item: item.tick.value))


def observer_replay_service() -> tuple[ReplayService, tuple[WorldEvent, ...]]:
    events = _move_and_wait()
    service = ReplayService(
        FakeRuns(_manifest()),
        FakeJournal(_commit(events), events),
        FakeSnapshots(_snapshot()),
    )
    return service, events


def _body_locations(history: object) -> tuple[tuple[str, str], ...]:
    scene = history.scene  # type: ignore[attr-defined]
    return tuple(
        (body.entity_id.value, body.location_id.value) for body in scene.bodies
    )


@pytest.mark.asyncio
async def test_two_folds_of_the_same_tick_match(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, events = observer_replay_service()
    layout = load_layout("reference-v1")
    first = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    second = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    assert not hasattr(first, "engine")
    assert not hasattr(second, "engine")
    live = LiveObserverSource(
        scene=first.scene,
        events=first.events,
        layout=layout,
        event_schema_version=first.result.event_schema_version,
        projector_version=first.result.projector_version,
    )
    replay = ReplayObserverSource(
        scene=second.scene,
        events=second.events,
        layout=layout,
        event_schema_version=second.result.event_schema_version,
        projector_version=second.result.projector_version,
    )
    assert type(live.frame()) is type(replay.frame())
    assert type(live.manifest()) is type(replay.manifest())
    assert type(live.events_after(0, -1, 10)) is type(replay.events_after(0, -1, 10))
    assert live.frame().world == replay.frame().world
    assert tuple(item.event_id for item in replay.events_after(0, -1, 10)) == tuple(
        event.event_id.value for event in events
    )
    with caplog.at_level(logging.DEBUG):
        replay.frame()
    assert "observer_source_frame" in caplog.text


@pytest.mark.asyncio
async def test_fold_moves_bodies_past_the_raw_snapshot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, events = observer_replay_service()
    with caplog.at_level(logging.DEBUG, logger="api.observer"):
        history = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    assert history.result.status is ReplayStatus.OK
    assert _body_locations(history) != history.snapshot_body_locations
    assert _body_locations(history) == ((BODY_ID, LOC_SPRING),)
    assert history.snapshot_body_locations == ((BODY_ID, LOC_CAMP),)
    again = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    assert _body_locations(again) == _body_locations(history)
    assert tuple(event.event_id.value for event in history.events) == tuple(
        event.event_id.value for event in events
    )
    assert "seed" not in history.scene.__slots__


@pytest.mark.asyncio
async def test_target_past_head_does_not_advance_the_clock() -> None:
    service, _events = observer_replay_service()
    outcome = await service.replay(
        ReplayRequest(run_id=RunId(RUN_ID), target_tick=Tick(9))
    )
    assert outcome.result.status is ReplayStatus.TARGET_UNREACHABLE
    assert outcome.engine is None


def _commit_tick(
    events: tuple[WorldEvent, ...],
    *,
    tick: int,
    base_revision: int,
    resulting_revision: int,
    predecessor: CommitHash | None,
    idempotency_key: str,
) -> TickCommit:
    request = TickAppendRequest(
        run_id=RunId(RUN_ID),
        tick=Tick(tick),
        expected_base_revision=WorldRevision(base_revision),
        expected_predecessor_commit_hash=predecessor,
        idempotency_key=idempotency_key,
        events=events,
    )
    payload = hash_tick_payload(request.events)
    event_hashes = hash_tick_events(request.events)
    resulting = WorldRevision(resulting_revision)
    commit_hash = compute_commit_hash(
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        run_id=request.run_id,
        tick=request.tick,
        base_revision=request.expected_base_revision,
        resulting_revision=resulting,
        event_hashes=event_hashes,
        payload_hash=payload,
    )
    return TickCommit(
        run_id=request.run_id,
        tick=request.tick,
        resulting_tick=Tick(request.tick.value + 1),
        base_revision=request.expected_base_revision,
        resulting_revision=resulting,
        predecessor_commit_hash=request.expected_predecessor_commit_hash,
        commit_hash=commit_hash,
        idempotency_key=request.idempotency_key,
        event_count=len(request.events),
        payload_hash=payload,
        snapshot_id=None,
    )


def _wait(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    revision: int,
    location_id: str,
) -> WorldEvent:
    details = Waited()
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(revision),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId(location_id)
        ),
    )


def _died(*, event_id: str, tick: int, sequence: int, revision: int) -> WorldEvent:
    details = Died(EntityId(BODY_ID), DeathCause.COMBINED_NEEDS)
    cause = SystemCause(
        RequestId(f"sys-{event_id}"),
        SystemEffectFamily.COMBINED_NEEDS,
        EntityId(BODY_ID),
        0,
    )
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id=RUN_ID,
        world_id=WorldId(WORLD_ID),
        tick=tick,
        sequence=sequence,
        cause=cause,
        resulting_revision=WorldRevision(revision),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId(LOC_SPRING)
        ),
    )


def boundary_replay_service() -> tuple[ReplayService, FakeJournal]:
    """Three ticks whose snapshot cursor is still tick 0."""
    moved, waited = _move_and_wait()
    tick1 = _wait(
        event_id="evt-wait-1",
        tick=1,
        sequence=0,
        revision=1,
        location_id=LOC_SPRING,
    )
    before_death = _wait(
        event_id="evt-wait-2",
        tick=2,
        sequence=0,
        revision=2,
        location_id=LOC_SPRING,
    )
    died = _died(event_id="evt-died", tick=2, sequence=1, revision=2)
    events = (moved, waited, tick1, before_death, died)
    commit0 = _commit_tick(
        (moved, waited),
        tick=0,
        base_revision=0,
        resulting_revision=1,
        predecessor=None,
        idempotency_key="idem-0",
    )
    commit1 = _commit_tick(
        (tick1,),
        tick=1,
        base_revision=1,
        resulting_revision=1,
        predecessor=commit0.commit_hash,
        idempotency_key="idem-1",
    )
    commit2 = _commit_tick(
        (before_death, died),
        tick=2,
        base_revision=1,
        resulting_revision=2,
        predecessor=commit1.commit_hash,
        idempotency_key="idem-2",
    )
    journal = FakeJournal(commit0, events, commits=(commit0, commit1, commit2))
    service = ReplayService(FakeRuns(_manifest()), journal, FakeSnapshots(_snapshot()))
    return service, journal


def _agent(frame: object, entity_id: str) -> object:
    world = frame.world  # type: ignore[attr-defined]
    for agent in world.agents:
        if agent.entity_id == entity_id:
            return agent
    raise AssertionError(f"missing agent {entity_id}")


@pytest.mark.asyncio
async def test_event_cursor_steps_forward_and_backward_without_an_inverse(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, journal = boundary_replay_service()
    reader = ObserverReadService(service)
    with caplog.at_level(logging.DEBUG, logger="simulation.replay"):
        first = await reader.state(
            RUN_ID, tick=0, through_sequence=0, layout_id="reference-v1"
        )
    assert "observer_event_fold" in caplog.text
    assert "tick=" in caplog.text
    assert "through_sequence=" in caplog.text
    assert first.cursor.mode == "replay"
    assert first.cursor.after_tick == 0
    assert first.cursor.after_sequence == 0
    assert first.world.tick == 0
    assert first.world.revision == 0
    assert _agent(first, BODY_ID).location_id == LOC_SPRING  # type: ignore[attr-defined]
    second = await reader.state(
        RUN_ID, tick=0, through_sequence=1, layout_id="reference-v1"
    )
    finished = await reader.state(RUN_ID, tick=1, layout_id="reference-v1")
    assert second.world == finished.world
    assert second.cursor.after_tick == 0
    assert second.cursor.after_sequence == 1
    assert second.world.tick == 1
    backward = await reader.state(
        RUN_ID, tick=0, through_sequence=0, layout_id="reference-v1"
    )
    assert backward.world == first.world
    assert backward.cursor.after_sequence == 0
    assert all("UN" not in event.type for event in backward.events or ())
    assert journal.appended == []
    assert not hasattr(backward, "engine")


@pytest.mark.asyncio
async def test_event_cursor_tick_boundaries_jump_and_death() -> None:
    service, _journal = boundary_replay_service()
    reader = ObserverReadService(service)
    last_of_previous = await reader.state(
        RUN_ID, tick=0, through_sequence=1, layout_id="reference-v1"
    )
    next_tick = await reader.state(
        RUN_ID, tick=1, through_sequence=0, layout_id="reference-v1"
    )
    start_of_next = await reader.state(RUN_ID, tick=1, layout_id="reference-v1")
    assert last_of_previous.world == start_of_next.world
    assert next_tick.world.tick == 2
    assert next_tick.cursor.after_tick == 1
    assert next_tick.cursor.after_sequence == 0
    previous_tick = await reader.state(
        RUN_ID, tick=1, through_sequence=0, layout_id="reference-v1"
    )
    assert previous_tick.world == next_tick.world
    jumped = await scene_through_event(
        service, RunId(RUN_ID), tick=Tick(2), through_sequence=0
    )
    assert jumped.result.snapshot_next_tick == Tick(0)
    assert not hasattr(jumped, "engine")
    before_death = await reader.state(
        RUN_ID, tick=2, through_sequence=0, layout_id="reference-v1"
    )
    after_death = await reader.state(
        RUN_ID, tick=2, through_sequence=1, layout_id="reference-v1"
    )
    assert before_death.world.tick == 2
    assert _agent(before_death, BODY_ID).life_status == "alive"  # type: ignore[attr-defined]
    assert _agent(after_death, BODY_ID).life_status == "dead"  # type: ignore[attr-defined]
    assert _agent(after_death, BODY_ID).entity_id == BODY_ID  # type: ignore[attr-defined]
    finished_death = await reader.state(RUN_ID, tick=3, layout_id="reference-v1")
    assert after_death.world == finished_death.world
    assert after_death.cursor.after_tick == 2
    assert after_death.cursor.after_sequence == 1
    first = await reader.state(
        RUN_ID, tick=0, through_sequence=0, layout_id="reference-v1"
    )
    live = await reader.state(RUN_ID, tick=None, layout_id="reference-v1")
    assert first.cursor.after_sequence == 0
    assert live.cursor.mode == "live"
    assert live.world == after_death.world
    tick_only = await reader.state(RUN_ID, tick=0, layout_id="reference-v1")
    assert tick_only.cursor.mode == "replay"
    assert tick_only.world.tick == 0
    assert _agent(tick_only, BODY_ID).location_id == LOC_CAMP  # type: ignore[attr-defined]
    assert not hasattr(after_death, "engine")
    with pytest.raises(ApiError) as missing:
        await reader.state(RUN_ID, tick=0, through_sequence=9, layout_id="reference-v1")
    assert missing.value.code == "observer_event_not_found"
    with pytest.raises(ApiError) as ahead:
        await reader.state(RUN_ID, tick=3, through_sequence=0, layout_id="reference-v1")
    assert ahead.value.code == "cursor_ahead_of_high_water"
    with pytest.raises(ApiError) as incomplete:
        await reader.state(
            RUN_ID, tick=None, through_sequence=0, layout_id="reference-v1"
        )
    assert incomplete.value.code == "incomplete_event_cursor"


def test_scene_from_facts_drops_seed() -> None:
    history_scene = scene_from_facts
    assert "seed" not in history_scene.__code__.co_varnames
