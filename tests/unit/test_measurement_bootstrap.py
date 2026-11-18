# mypy: ignore-errors

"""Instrument sidecars follow physical TOOL items without resetting condition."""

from __future__ import annotations

from dataclasses import replace

import pytest

from simulation.engine import WorldEngine
from tests.physical_helpers import physical_config, two_location_fixture
from tests.simulation_helpers import make_item
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)
from world.production import ToolMark, ToolRole
from world.values import ItemKind

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TOOL_ID = EntityId("item-thermometer")
_REF_ID = EntityId("item-reference")


def _fixture():
    base = two_location_fixture(item_on_ground=False)
    tool = make_item(
        _TOOL_ID.value,
        name="Thermometer",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-1",
    )
    reference = make_item(
        _REF_ID.value,
        name="Reference",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-1",
    )
    holder = replace(base.bodies[0], inventory=(_TOOL_ID, _REF_ID))
    return replace(
        base,
        items=(tool, reference),
        bodies=(holder, base.bodies[1]),
    )


def _instrument() -> InstrumentState:
    return InstrumentState(
        item_id=_TOOL_ID,
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        intrinsic_bias_milli=250,
        base_error_bound_milli=100,
        damage_milli=300,
        correction_milli=0,
        calibration_state=CalibrationState.NEVER_ADJUSTED,
        calibration_revision=0,
    )


def _reference() -> MeasurementReference:
    return MeasurementReference(
        item_id=_REF_ID,
        unit=_CELSIUS,
        nominal_value_milli=20000,
        physical_value_milli=21000,
    )


def _bootstrap(fixture, *, instrument=True):
    return replace(
        fixture.as_bootstrap(),
        instrument_states=(_instrument(),) if instrument else (),
        measurement_references=(_reference(),) if instrument else (),
    )


def test_held_and_ground_instruments_are_bootstrapped() -> None:
    fixture = _fixture()
    bootstrap = _bootstrap(fixture)
    engine = WorldEngine(config=physical_config(7), bootstrap=bootstrap)
    state = engine._snapshot.world.state
    assert state.instrument_states[_TOOL_ID].intrinsic_bias_milli == 250
    assert state.measurement_references[_REF_ID].physical_value_milli == 21000


def test_transfer_and_storage_preserve_condition_and_epoch() -> None:
    fixture = _fixture()
    state = WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        instrument_states=(_instrument(),),
        measurement_references=(_reference(),),
    )
    items = dict(state.items)
    items[_TOOL_ID] = replace(
        items[_TOOL_ID], holder_id=None, location_id=fixture.locations[0].entity_id
    )
    bodies = dict(state.bodies)
    bodies[fixture.bodies[0].entity_id] = replace(
        fixture.bodies[0], inventory=(_REF_ID,)
    )
    moved = rebuild_world_state(state, items=items, bodies=bodies)
    assert moved.instrument_states[_TOOL_ID] == _instrument()
    assert moved.measurement_references[_REF_ID] == _reference()


def test_consumed_item_removes_its_sidecar_in_the_same_rebuild() -> None:
    fixture = _fixture()
    state = WorldState(
        fixture.revision,
        locations=fixture.locations,
        bodies=fixture.bodies,
        items=fixture.items,
        resources=fixture.resources,
        weather=fixture.weather,
        instrument_states=(_instrument(),),
        measurement_references=(_reference(),),
    )
    pruned = rebuild_world_state(state, items={}, bodies={})
    assert pruned.instrument_states == {}
    assert pruned.measurement_references == {}


def test_missing_or_non_tool_anchor_is_rejected() -> None:
    fixture = _fixture()
    with pytest.raises(ValueError, match="known item"):
        WorldState(
            fixture.revision,
            locations=fixture.locations,
            bodies=fixture.bodies,
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
            instrument_states=(replace(_instrument(), item_id=EntityId("nope")),),
        )
    food = make_item(
        "item-food",
        name="Food",
        kind=ItemKind.FOOD,
        location_id=None,
        holder_id="body-1",
    )
    with pytest.raises(ValueError, match="TOOL item"):
        WorldState(
            fixture.revision,
            locations=fixture.locations,
            bodies=(
                replace(fixture.bodies[0], inventory=(food.entity_id,)),
                fixture.bodies[1],
            ),
            items=(food,),
            resources=fixture.resources,
            weather=fixture.weather,
            instrument_states=(replace(_instrument(), item_id=food.entity_id),),
        )


def test_duplicate_and_cross_role_records_are_rejected() -> None:
    fixture = _fixture()
    with pytest.raises(ValueError, match="duplicate instrument"):
        WorldState(
            fixture.revision,
            locations=fixture.locations,
            bodies=fixture.bodies,
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
            instrument_states=(_instrument(), _instrument()),
        )
    with pytest.raises(ValueError, match="measurement_role_conflict"):
        WorldState(
            fixture.revision,
            locations=fixture.locations,
            bodies=fixture.bodies,
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
            tool_marks=(ToolMark(_TOOL_ID, ToolRole.STRIKE),),
            instrument_states=(_instrument(),),
        )
    with pytest.raises(ValueError, match="measurement_role_conflict"):
        WorldState(
            fixture.revision,
            locations=fixture.locations,
            bodies=fixture.bodies,
            items=fixture.items,
            resources=fixture.resources,
            weather=fixture.weather,
            instrument_states=(_instrument(),),
            measurement_references=(
                _reference(),
                replace(_reference(), item_id=_TOOL_ID),
            ),
        )


def test_bootstrap_constructor_defensively_copies_sequences() -> None:
    fixture = _fixture()
    source = [_instrument()]
    bootstrap = _bootstrap(fixture)
    bootstrap = replace(bootstrap, instrument_states=source)  # type: ignore[arg-type]
    source.clear()
    assert len(bootstrap.instrument_states) == 1
    assert isinstance(bootstrap.instrument_states, tuple)
