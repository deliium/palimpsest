"""End-to-end persistence and replay against disposable PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from tests.unit.determinism_helpers import project_world_state

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    CommitHash,
    PayloadHash,
    ReplayMode,
    ReplayRequest,
    ReplayStatus,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.replay import ReplayService
from simulation.service import PersistentSimulationService
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


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


def _objective_fingerprint(engine: WorldEngine) -> tuple[object, ...]:
    return (
        engine.tick.value,
        engine.revision.value,
        project_world_state(engine._snapshot.world.state),
    )


def _event_fingerprint(
    engine: WorldEngine,
) -> tuple[tuple[str, ...], tuple[tuple[int, int, str], ...]]:
    export = engine.export_events()
    return (
        tuple(event.event_id.value for event in export.events),
        tuple(
            (event.tick, event.sequence, event.event_type)
            for event in export.events
        ),
    )


def _fingerprint(engine: WorldEngine) -> tuple[object, ...]:
    return _objective_fingerprint(engine) + _event_fingerprint(engine)


def _snapshot_from_engine(
    *,
    engine: WorldEngine,
    snapshot_id: str,
    next_tick: Tick,
    predecessor_commit_hash: CommitHash | None,
) -> WorldSnapshot:
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(snapshot_id),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(engine._snapshot.world.state.locations.values()),
        bodies=tuple(engine._snapshot.world.state.bodies.values()),
        items=tuple(engine._snapshot.world.state.items.values()),
        resources=tuple(engine._snapshot.world.state.resources.values()),
        weather=tuple(engine._snapshot.world.state.weather.values()),
        next_tick=next_tick,
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_VERSION,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=predecessor_commit_hash,
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


async def _wait_tick(
    service: PersistentSimulationService,
    *,
    snapshot: WorldSnapshot | None = None,
) -> None:
    engine = service.engine
    batch = engine.observe()
    submission = ActionSubmission(
        agent_id=AgentId("agent-1"),
        token=batch.token,
        command=Wait(),
    )
    await service.resolve_tick((submission,), snapshot=snapshot)


async def test_live_bootstrap_and_checkpoint_replay_agree(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    run_id = _unique("run")
    engine = WorldEngine(
        config=SimulationRunConfig(seed=19),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=(Location(entity_id=EntityId("loc-1"), name="Camp"),),
            bodies=(_alive(),),
            registrations=(
                AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            ),
        ),
        run_id=RunId(run_id),
    )
    bootstrap = _snapshot_from_engine(
        engine=engine,
        snapshot_id=_unique("snap"),
        next_tick=Tick(0),
        predecessor_commit_hash=None,
    )
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=WorldId("world-1"),
            seed=19,
            config=SimulationRunConfig(seed=19),
            bootstrap=bootstrap,
        )
    )
    service = PersistentSimulationService(engine, journal)

    await _wait_tick(service)
    await _wait_tick(service)
    # Mid-run checkpoint attached to tick 2 (Wait leaves objective state unchanged).
    # Predecessor is rebound to this tick's commit hash by PersistentSimulationService.
    mid_id = _unique("snap")
    mid_draft = _snapshot_from_engine(
        engine=engine,
        snapshot_id=mid_id,
        next_tick=Tick(engine.tick.value + 1),
        predecessor_commit_hash=CommitHash("b" * 64),
    )
    await _wait_tick(service, snapshot=mid_draft)
    mid = await snapshots.get_snapshot(SnapshotId(mid_id))
    assert mid is not None
    await _wait_tick(service)
    await _wait_tick(service)

    live = _fingerprint(engine)
    assert engine.tick == Tick(5)

    replay = ReplayService(runs, journal, snapshots)
    head = await replay.replay(
        ReplayRequest(run_id=RunId(run_id), target_tick=None)
    )
    assert head.result.status is ReplayStatus.OK
    assert head.result.mode is ReplayMode.CONTINUATION
    assert head.engine is not None
    assert head.result.snapshot_id == mid.snapshot_id
    # Checkpoint restore folds only subsequent events; objective cursor must match.
    assert _objective_fingerprint(head.engine) == _objective_fingerprint(engine)
    assert head.result.events_applied == 2
    live_events = _event_fingerprint(engine)
    assert _event_fingerprint(head.engine) == (
        live_events[0][-2:],
        live_events[1][-2:],
    )

    loaded_bootstrap = await snapshots.get_snapshot(bootstrap.snapshot_id)
    assert loaded_bootstrap is not None
    all_events = await journal.list_events(
        RunId(run_id),
        from_tick=Tick(0),
        to_tick=Tick(4),
        limit=10_000,
        offset=0,
    )
    bootstrap_engine = WorldEngine.restore_from_snapshot(
        loaded_bootstrap,
        events=all_events,
        committed_through_tick=Tick(4),
    )
    assert _fingerprint(bootstrap_engine) == live

    historical = await replay.replay(
        ReplayRequest(run_id=RunId(run_id), target_tick=Tick(3))
    )
    assert historical.result.status is ReplayStatus.OK
    assert historical.result.mode is ReplayMode.READONLY
    assert historical.engine is not None
    assert historical.engine.tick == Tick(3)
    assert _objective_fingerprint(historical.engine) == (
        3,
        engine.revision.value,
        project_world_state(engine._snapshot.world.state),
    )
    with pytest.raises(RuntimeError, match="read-only"):
        replay.open_durable(historical, journal)
