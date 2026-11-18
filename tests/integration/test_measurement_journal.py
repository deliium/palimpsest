"""Durable V4-29 measurement event and snapshot round-trip (PostgreSQL)."""

from __future__ import annotations

import uuid
from dataclasses import replace

import pytest
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import make_item

from agents.models import AgentId
from infrastructure.database import DatabaseResources
from persistence import (
    create_run_repository,
    create_tick_journal_repository,
)
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import hash_snapshot
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId
from simulation.persistence import (
    PROJECTOR_VERSION,
    PayloadHash,
    RunCreateRequest,
    SnapshotId,
    WorldSnapshot,
)
from simulation.service import PersistentSimulationService
from simulation.versioning import MEASUREMENT_WRITE_PAIR_CODEC
from world.actions import Measure
from world.events import EVENT_SCHEMA_REPLAY_V28, MeasurementTaken
from world.identifiers import EntityId, WorldRevision
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.values import ItemKind

pytestmark = pytest.mark.integration

_TOOL = EntityId("item-durable-thermometer")


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _instrument() -> InstrumentState:
    return InstrumentState(
        item_id=_TOOL,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=MeasurementUnit(MeasurementUnitKind.CELSIUS),
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=0,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _snapshot(engine: WorldEngine, *, snapshot_id: str) -> WorldSnapshot:
    state = engine._snapshot.world.state
    draft = WorldSnapshot(
        snapshot_id=SnapshotId(snapshot_id),
        run_id=engine.run_id,
        world_id=engine.world_id,
        seed=engine._config.seed,
        config=engine._config,
        registrations=engine._registrations,
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        items=tuple(state.items.values()),
        resources=tuple(state.resources.values()),
        weather=tuple(state.weather.values()),
        next_tick=Tick(0),
        revision=engine.revision,
        event_schema_version=EVENT_SCHEMA_REPLAY_V28,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version=MEASUREMENT_WRITE_PAIR_CODEC,
        derivation_version=engine._config.derivation_version or "v2",
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        instrument_states=tuple(state.instrument_states.values()),
        measurement_references=tuple(state.measurement_references.values()),
    )
    return replace(draft, integrity_hash=hash_snapshot(draft))


@pytest.mark.asyncio
async def test_measurement_event_and_v26_snapshot_are_durable(
    database_resources: DatabaseResources,
) -> None:
    fixture = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-1",
    )
    body = replace(fixture.bodies[0], inventory=(_TOOL,))
    world = replace(
        fixture,
        items=(tool,),
        bodies=(body, fixture.bodies[1]),
        revision=WorldRevision(0),
    )
    bootstrap = replace(world.as_bootstrap(), instrument_states=(_instrument(),))
    run_id = RunId(_unique("run-measurement-journal"))
    engine = WorldEngine(
        config=physical_config(41), bootstrap=bootstrap, run_id=run_id
    )
    await create_run_repository(database_resources.session_factory).create_run(
        RunCreateRequest(
            run_id=run_id,
            world_id=engine.world_id,
            seed=41,
            config=engine._config,
            bootstrap=_snapshot(engine, snapshot_id=_unique("snap")),
            derivation_version=engine._config.derivation_version or "v2",
        )
    )
    journal = create_tick_journal_repository(database_resources.session_factory)
    service = PersistentSimulationService(engine, journal)
    batch = engine.observe()
    await service.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId(fixture.registrations[0].agent_id.value),
                Measure(
                    _TOOL,
                    EntityId("loc-1"),
                    MeasurementQuantity.AMBIENT_TEMPERATURE,
                ),
            ),
        )
    )
    events = await journal.list_events(
        run_id,
        from_tick=Tick(0),
        to_tick=Tick(0),
        limit=100,
        offset=0,
    )
    assert any(type(event.details) is MeasurementTaken for event in events)
    assert all(
        event.schema_version == EVENT_SCHEMA_REPLAY_V28 for event in events
    )
