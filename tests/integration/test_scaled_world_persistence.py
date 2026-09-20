"""Scaled physical world persistence against disposable PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from tests.physical_helpers import (
    objective_fingerprint,
    physical_config,
    scaled_fixture,
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


def _snapshot(engine: WorldEngine, *, snapshot_id: str) -> WorldSnapshot:
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
        next_tick=Tick(0),
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
@pytest.mark.parametrize(("agents", "locations"), [(5, 10), (10, 20)])
async def test_scaled_world_postgres_round_trip(
    database_resources: DatabaseResources,
    agents: int,
    locations: int,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    snapshots = create_snapshot_repository(factory)
    run_id = _unique(f"scale-{agents}x{locations}")
    fixture = scaled_fixture(agents=agents, locations=locations, seed_tag=run_id)
    config = physical_config(2026)
    engine = WorldEngine(
        config=config,
        bootstrap=fixture.as_bootstrap(),
        run_id=RunId(run_id),
    )
    bootstrap = _snapshot(engine, snapshot_id=_unique("snap"))
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=fixture.world_id,
            seed=2026,
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
                batch.token, AgentId("agent-00"), Take(EntityId("item-00"))
            ),
            ActionSubmission(batch.token, AgentId("agent-01"), Wait()),
        )
    )
    batch2 = engine.observe()
    await service.resolve_tick(
        (ActionSubmission(batch2.token, AgentId("agent-00"), Wait()),)
    )
    live_fp = objective_fingerprint(engine)

    replay = ReplayService(runs, journal, snapshots)
    outcome = await replay.replay(ReplayRequest(run_id=RunId(run_id), target_tick=None))
    assert outcome.result.status is ReplayStatus.OK
    assert outcome.engine is not None
    assert objective_fingerprint(outcome.engine) == live_fp
