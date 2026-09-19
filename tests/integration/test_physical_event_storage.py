"""Physical event storage round-trip against disposable PostgreSQL."""

from __future__ import annotations

import uuid

import pytest
from tests.physical_helpers import physical_config, two_location_fixture

from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.models import RunId
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.service import PersistentSimulationService
from world.events import Died, NeedsApplied
from world.identifiers import EntityId
from world.models import LifeStatus, copy_body
from world.values import Fatigue, Health, Hunger, Thirst

pytestmark = pytest.mark.integration


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _snapshot(
    engine: WorldEngine,
    *,
    snapshot_id: str,
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
async def test_autonomous_physiology_events_persist(
    database_resources: DatabaseResources,
) -> None:
    factory = database_resources.session_factory
    runs = create_run_repository(factory)
    journal = create_tick_journal_repository(factory)
    run_id = _unique("phys-evt")
    fixture = two_location_fixture(item_on_ground=False)
    stressed = copy_body(
        fixture.bodies[0],
        health=Health(10),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
    )
    world = type(fixture)(
        world_id=fixture.world_id,
        locations=fixture.locations,
        bodies=(stressed, fixture.bodies[1]),
        items=(),
        resources=fixture.resources,
        weather=fixture.weather,
        registrations=fixture.registrations,
        revision=fixture.revision,
    )
    config = physical_config(44)
    engine = WorldEngine(
        config=config,
        bootstrap=world.as_bootstrap(),
        run_id=RunId(run_id),
    )
    bootstrap = _snapshot(engine, snapshot_id=_unique("snap"))
    await runs.create_run(
        RunCreateRequest(
            run_id=RunId(run_id),
            world_id=world.world_id,
            seed=44,
            config=config,
            bootstrap=bootstrap,
            derivation_version=config.derivation_version or "v2",
        )
    )
    service = PersistentSimulationService(engine, journal)
    engine.observe()
    await service.resolve_tick(())

    events = await journal.list_events(
        RunId(run_id),
        from_tick=Tick(0),
        to_tick=Tick(0),
        limit=1000,
        offset=0,
    )
    kinds = {type(event.details) for event in events}
    assert NeedsApplied in kinds
    # Stressed body may die; assert death is stored when present.
    if Died in kinds:
        died = [event for event in events if type(event.details) is Died]
        assert len(died) == 1
        assert (
            engine._snapshot.world.state.bodies[EntityId("body-1")].life_status
            is LifeStatus.DEAD
        )
    assert events
    for event in events:
        assert event.resulting_revision == engine.revision
