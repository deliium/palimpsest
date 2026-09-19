"""Physical simulation replay against disposable PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from tests.physical_helpers import (
    objective_fingerprint,
    physical_config,
    two_location_fixture,
)

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_snapshot_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    ReplayRequest,
    ReplayStatus,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.replay import ReplayService
from simulation.service import PersistentSimulationService
from world.actions import Take, Wait
from world.identifiers import EntityId

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _snapshot_from_engine(
    *,
    engine: WorldEngine,
    snapshot_id: str,
    next_tick: Tick,
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
        derivation_version=engine._config.derivation_version or "v2",
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
        predecessor_commit_hash=None,
    )


@pytest.mark.asyncio
async def test_physical_live_bootstrap_and_checkpoint_replay(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    run_id = _unique("phys-run")
    fixture = two_location_fixture()
    config = physical_config(91)
    engine = WorldEngine(
        config=config,
        bootstrap=fixture.as_bootstrap(),
        run_id=RunId(run_id),
    )
    bootstrap = _snapshot_from_engine(
        engine=engine,
        snapshot_id=_unique("snap"),
        next_tick=Tick(0),
    )
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=fixture.world_id,
            seed=91,
            config=config,
            bootstrap=bootstrap,
            derivation_version=config.derivation_version or "v2",
        )
    )
    service = PersistentSimulationService(engine, journal)

    batch = engine.observe()
    await service.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-1"))
            ),
            ActionSubmission(batch.token, AgentId("agent-2"), Wait()),
        )
    )
    mid_id = SnapshotId(_unique("snap"))
    batch2 = engine.observe()
    await service.resolve_tick(
        (ActionSubmission(batch2.token, AgentId("agent-1"), Wait()),),
        checkpoint_id=mid_id,
    )
    batch3 = engine.observe()
    await service.resolve_tick(
        (ActionSubmission(batch3.token, AgentId("agent-2"), Wait()),)
    )
    live_fp = objective_fingerprint(engine)

    replay = ReplayService(runs, journal, snapshots)
    head = await replay.replay(
        ReplayRequest(run_id=RunId(run_id), target_tick=None)
    )
    assert head.result.status is ReplayStatus.OK
    assert head.engine is not None
    assert objective_fingerprint(head.engine) == live_fp

    loaded_bootstrap = await snapshots.get_snapshot(bootstrap.snapshot_id)
    assert loaded_bootstrap is not None
    all_events = await journal.list_events(
        RunId(run_id),
        from_tick=Tick(0),
        to_tick=Tick(engine.tick.value - 1),
        limit=10_000,
        offset=0,
    )
    bootstrap_engine = WorldEngine.restore_from_snapshot(
        loaded_bootstrap,
        events=all_events,
        committed_through_tick=Tick(engine.tick.value - 1),
    )
    assert objective_fingerprint(bootstrap_engine) == live_fp
