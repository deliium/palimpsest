"""Historical observer frames come from a fresh fold, then drop the engine."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
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
    PayloadHash,
    ReplayRequest,
    ReplayStatus,
    RunManifest,
    SnapshotId,
    TickAppendRequest,
    TickCommit,
    WorldSnapshot,
)
from simulation.replay import ReplayService, scene_at_tick
from tests.simulation_helpers import alive_body, weather_for_locations
from world.effects import ActionCause
from world.events import (
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
    def __init__(self, commit: TickCommit, events: tuple[WorldEvent, ...]) -> None:
        self.commit = commit
        self.events = events

    async def append_tick(self, request: TickAppendRequest) -> TickCommit:
        raise NotImplementedError

    async def get_tick_commit(self, run_id: RunId, tick: Tick) -> TickCommit | None:
        if self.commit.run_id == run_id and self.commit.tick == tick:
            return self.commit
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
        if self.commit.run_id != run_id:
            return ()
        if self.commit.tick.value < from_tick.value:
            return ()
        if to_tick is not None and self.commit.tick.value > to_tick.value:
            return ()
        return (self.commit,)


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


def test_scene_from_facts_drops_seed() -> None:
    history_scene = scene_from_facts
    assert "seed" not in history_scene.__code__.co_varnames
