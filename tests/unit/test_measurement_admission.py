# mypy: ignore-errors

"""Real WorldEngine admission for Measure/CalibrateInstrument commands."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import make_item
from world.actions import CalibrateInstrument, Measure, Wait
from world.events import (
    EVENT_SCHEMA_REPLAY_V28,
    InstrumentCalibrated,
    MeasurementTaken,
)
from world.identifiers import EntityId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TOOL = EntityId("item-thermometer")
_REF = EntityId("item-reference")
_ACTOR = EntityId("body-1")
_AGENT = AgentId("agent-1")


def _fixture(*, damage: int = 0):
    base = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    reference_item = make_item(
        _REF.value,
        name="Reference",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    body = replace(base.bodies[0], inventory=(_TOOL, _REF))
    return replace(
        base,
        items=(tool, reference_item),
        bodies=(body, base.bodies[1]),
    )


def _instrument(damage: int = 0) -> InstrumentState:
    return InstrumentState(
        item_id=_TOOL,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=damage,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _reference() -> MeasurementReference:
    return MeasurementReference(
        item_id=_REF,
        unit=_CELSIUS,
        nominal_value_milli=20000,
        physical_value_milli=20000,
    )


def _engine(*, instrument: bool = True, damage: int = 0) -> WorldEngine:
    fixture = _fixture(damage=damage)
    bootstrap = replace(
        fixture.as_bootstrap(),
        instrument_states=(_instrument(damage),) if instrument else (),
        measurement_references=(_reference(),) if instrument else (),
    )
    return WorldEngine(config=physical_config(7), bootstrap=bootstrap)


def _submit(engine: WorldEngine, command: object):
    batch = engine.observe()
    return engine.resolve_tick((ActionSubmission(batch.token, _AGENT, command),))


def test_measure_is_admitted_and_emits_effect_complete_event() -> None:
    engine = _engine()
    result = _submit(
        engine,
        Measure(_TOOL, EntityId("loc-1"), MeasurementQuantity.AMBIENT_TEMPERATURE),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    events = [record.event for record in result.events]
    taken = [event for event in events if type(event.details) is MeasurementTaken]
    assert len(taken) == 1
    event = taken[0]
    assert event.schema_version == EVENT_SCHEMA_REPLAY_V28
    assert event.details.reading.reading_id == (
        f"msr:{result.resolutions[0].request_id.value}"
    )
    assert event.details.instrument_after.damage_milli == 10
    state = engine._snapshot.world.state
    assert state.instrument_states[_TOOL].damage_milli == 10
    assert state.resources[EntityId("res-water")].quantity == 3.0


def test_calibration_is_admitted_and_adjusts_once() -> None:
    engine = _engine()
    result = _submit(engine, CalibrateInstrument(_TOOL, _REF))
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    events = [record.event for record in result.events]
    calibrated = [
        event for event in events if type(event.details) is InstrumentCalibrated
    ]
    assert len(calibrated) == 1
    after = engine._snapshot.world.state.instrument_states[_TOOL]
    assert after.calibration_revision == 1
    assert after.calibration_state is CalibrationState.ADJUSTED
    assert after.damage_milli == 10


def test_channel_off_rejects_both_commands_without_events() -> None:
    engine = _engine(instrument=False)
    for command in (
        Measure(_TOOL, EntityId("loc-1"), MeasurementQuantity.AMBIENT_TEMPERATURE),
        CalibrateInstrument(_TOOL, _REF),
    ):
        result = _submit(engine, command)
        assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
        assert all(
            type(record.event.details)
            not in {MeasurementTaken, InstrumentCalibrated}
            for record in result.events
        )


def test_broken_instrument_is_rejected_without_wear() -> None:
    engine = _engine(damage=1000)
    result = _submit(
        engine,
        Measure(_TOOL, EntityId("loc-1"), MeasurementQuantity.AMBIENT_TEMPERATURE),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert engine._snapshot.world.state.instrument_states[_TOOL].damage_milli == 1000


def test_quantity_mismatch_and_ineligible_target_are_rejected() -> None:
    engine = _engine()
    for command in (
        Measure(
            _TOOL,
            EntityId("loc-1"),
            MeasurementQuantity.RESOURCE_AMOUNT,
        ),
        Measure(
            _TOOL,
            EntityId("loc-2"),
            MeasurementQuantity.AMBIENT_TEMPERATURE,
        ),
    ):
        result = _submit(engine, command)
        assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
        assert engine._snapshot.world.state.instrument_states[_TOOL].damage_milli == 0


def test_unheld_instrument_is_rejected() -> None:
    fixture = _fixture()
    tool = next(item for item in fixture.items if item.entity_id == _TOOL)
    moved_tool = replace(tool, holder_id=None, location_id=EntityId("loc-2"))
    body = replace(fixture.bodies[0], inventory=(_REF,))
    bootstrap = replace(
        replace(
            fixture.as_bootstrap(),
            items=tuple(
                moved_tool if item.entity_id == _TOOL else item
                for item in fixture.items
            ),
            bodies=(body, fixture.bodies[1]),
        ),
        instrument_states=(_instrument(),),
        measurement_references=(_reference(),),
    )
    engine = WorldEngine(config=physical_config(7), bootstrap=bootstrap)
    result = _submit(
        engine,
        Measure(_TOOL, EntityId("loc-1"), MeasurementQuantity.AMBIENT_TEMPERATURE),
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED


def test_existing_wait_remains_legal_in_a_measurement_world() -> None:
    engine = _engine()
    result = _submit(engine, Wait())
    assert result.resolutions[0].status is ActionResolutionStatus.APPLIED
    assert all(
        type(record.event.details) is not MeasurementTaken
        for record in result.events
    )
