# mypy: ignore-errors

"""Recorded measurement effects replay without resampling."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tests.physical_helpers import two_location_fixture
from tests.simulation_helpers import make_item
from world._replay import ProjectionError, project_events
from world._state import WorldState
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V28,
    InstrumentCalibrated,
    MeasurementTaken,
    OccurrenceContext,
    WorldEvent,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReading,
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
_LOC = EntityId("loc-1")
_WORLD = WorldId("world-1")
_RUN = "run-1"


def _fixture():
    base = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    reference = make_item(
        _REF.value,
        name="Reference",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id=_ACTOR.value,
    )
    body = replace(base.bodies[0], inventory=(_TOOL, _REF))
    return replace(base, items=(tool, reference), bodies=(body, base.bodies[1]))


def _instrument() -> InstrumentState:
    return InstrumentState(
        item_id=_TOOL,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=0,
        base_error_bound_milli=0,
        damage_milli=0,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _state() -> WorldState:
    fixture = _fixture()
    return WorldState(
        WorldRevision(0),
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        instrument_states=(_instrument(),),
        measurement_references=(
            MeasurementReference(
                item_id=_REF,
                unit=_CELSIUS,
                nominal_value_milli=20000,
                physical_value_milli=20500,
            ),
        ),
    )


def _event(details, tick: int = 0) -> WorldEvent:
    return WorldEvent(
        event_id=EventId("e" * 64),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=0,
        request_id=RequestId("req-1"),
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V28,
        details=details,
        actor_id=_ACTOR,
        target_id=(
            details.reading.target_id
            if type(details) is MeasurementTaken
            else details.reference_id
        ),
        cause=ActionCause(request_id=RequestId("req-1"), actor_id=_ACTOR),
        occurrence=OccurrenceContext(
            origin_location_id=_LOC,
            affected_entity_ids=(_TOOL,),
        ),
    )


def _taken() -> MeasurementTaken:
    before = _instrument()
    return MeasurementTaken(
        reading=MeasurementReading(
            reading_id="msr:req-1",
            instrument_id=_TOOL,
            target_id=_LOC,
            quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
            unit=_CELSIUS,
            sample_tick=0,
            nominal_division_milli=1000,
            displayed_scalar_milli=15000,
        ),
        instrument_before=before,
        instrument_after=replace(before, damage_milli=10),
    )


def test_measurement_replay_applies_recorded_after_state(monkeypatch) -> None:
    import world._measurement as measurement_module

    def _boom(*args, **kwargs):
        raise AssertionError("replay must not resample")

    monkeypatch.setattr(measurement_module, "resolve_measurement", _boom)
    projected = project_events(
        _state(), (_event(_taken()),), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert projected.instrument_states[_TOOL].damage_milli == 10
    assert projected.revision == WorldRevision(1)


def test_calibration_replay_applies_recorded_revision(monkeypatch) -> None:
    import world._measurement as measurement_module

    monkeypatch.setattr(
        measurement_module,
        "resolve_instrument_calibration",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resample")),
    )
    before = _instrument()
    after = replace(
        before,
        correction_milli=-500,
        calibration_revision=1,
        calibration_state=CalibrationState.ADJUSTED,
        last_adjustment_tick=0,
        damage_at_adjustment_milli=0,
        damage_milli=10,
    )
    details = InstrumentCalibrated(
        reference_id=_REF,
        reference_unit=_CELSIUS,
        nominal_value_milli=20000,
        reference_display_milli=20500,
        instrument_before=before,
        instrument_after=after,
    )
    projected = project_events(
        _state(), (_event(details),), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert projected.instrument_states[_TOOL] == after


def test_tampered_before_state_fails_closed() -> None:
    details = _taken()
    tampered = replace(
        details,
        instrument_before=replace(details.instrument_before, damage_milli=10),
        instrument_after=replace(details.instrument_after, damage_milli=20),
    )
    with pytest.raises(ProjectionError):
        project_events(
            _state(),
            (_event(tampered),),
            expected_run_id=_RUN,
            expected_world_id=_WORLD,
        )


def test_reading_quantity_and_unit_must_match_the_instrument() -> None:
    details = _taken()
    mismatched = replace(
        details.reading,
        quantity=MeasurementQuantity.RESOURCE_AMOUNT,
        unit=MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, "units"),
    )
    with pytest.raises(ValueError, match="measurement_taken_reading_mismatch"):
        replace(details, reading=mismatched)
