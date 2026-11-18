# mypy: ignore-errors

"""Measurement contracts: closed dimensions, hidden reliability and legacy shape."""

from __future__ import annotations

import dataclasses
import math

import pytest

from world.identifiers import EntityId
from world.measurement import (
    MEASUREMENT_MAX_STEP_MILLI,
    CalibrationState,
    InstrumentAppearance,
    InstrumentState,
    InstrumentWearBand,
    MeasurementQuantity,
    MeasurementReading,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
    ReferenceAppearance,
    instrument_wear_band,
    measurement_unit_matches_quantity,
)
from world.models import Item

pytestmark = pytest.mark.unit

_CELSIUS = MeasurementUnit(MeasurementUnitKind.CELSIUS)
_TICKS = MeasurementUnit(MeasurementUnitKind.SIMULATED_TICK)
_LOAD = MeasurementUnit(MeasurementUnitKind.SIMULATED_LOAD)
_RESOURCE = MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, "grain")

_CASES = (
    (MeasurementQuantity.AMBIENT_TEMPERATURE, _CELSIUS),
    (MeasurementQuantity.RESOURCE_AMOUNT, _RESOURCE),
    (MeasurementQuantity.ELAPSED_DURATION, _TICKS),
    (MeasurementQuantity.TRAVEL_TIME_ESTIMATE, _TICKS),
    (MeasurementQuantity.LOAD_CATEGORY, _LOAD),
)


def _instrument(
    quantity: MeasurementQuantity = MeasurementQuantity.AMBIENT_TEMPERATURE,
    unit: MeasurementUnit = _CELSIUS,
    **overrides: object,
) -> InstrumentState:
    values: dict[str, object] = {
        "item_id": EntityId("item:thermometer"),
        "quantity": quantity,
        "unit": unit,
        "nominal_step_milli": 1000,
        "intrinsic_bias_milli": 0,
        "base_error_bound_milli": 0,
        "damage_milli": 0,
        "correction_milli": 0,
        "calibration_state": CalibrationState.NEVER_ADJUSTED,
        "calibration_revision": 0,
        "last_adjustment_tick": None,
        "damage_at_adjustment_milli": None,
        "timer_epoch_tick": 0
        if quantity is MeasurementQuantity.ELAPSED_DURATION
        else None,
    }
    values.update(overrides)
    return InstrumentState(**values)


@pytest.mark.parametrize(("quantity", "unit"), _CASES)
def test_each_quantity_accepts_its_closed_unit(
    quantity: MeasurementQuantity, unit: MeasurementUnit
) -> None:
    state = _instrument(quantity, unit)
    assert state.quantity is quantity
    assert measurement_unit_matches_quantity(quantity, unit)


@pytest.mark.parametrize(("quantity", "unit"), _CASES)
def test_each_quantity_rejects_another_unit(
    quantity: MeasurementQuantity, unit: MeasurementUnit
) -> None:
    other = _CELSIUS if unit is not _CELSIUS else _TICKS
    with pytest.raises(ValueError, match="measurement_invalid_unit"):
        _instrument(quantity, other)


def test_resource_unit_requires_exact_label_and_other_kinds_forbid_it() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_unit"):
        MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT)
    with pytest.raises(ValueError, match="measurement_invalid_unit"):
        MeasurementUnit(MeasurementUnitKind.CELSIUS, "grain")
    with pytest.raises(ValueError, match="measurement_invalid_unit"):
        MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, "")
    with pytest.raises(ValueError, match="measurement_invalid_unit"):
        MeasurementUnit(MeasurementUnitKind.RESOURCE_UNIT, " grain")


def test_negative_temperature_and_zero_amount_readings_are_legal() -> None:
    cold = MeasurementReading(
        reading_id="msr:request-1",
        instrument_id=EntityId("item:thermometer"),
        target_id=EntityId("loc:cave"),
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        sample_tick=3,
        nominal_division_milli=1000,
        displayed_scalar_milli=-4500,
    )
    assert cold.displayed_scalar_milli == -4500
    empty = MeasurementReading(
        reading_id="msr:request-2",
        instrument_id=EntityId("item:scale"),
        target_id=EntityId("res:grain"),
        quantity=MeasurementQuantity.RESOURCE_AMOUNT,
        unit=_RESOURCE,
        sample_tick=3,
        nominal_division_milli=500,
        displayed_scalar_milli=0,
    )
    assert empty.displayed_scalar_milli == 0


def _reading(**overrides: object) -> MeasurementReading:
    values: dict[str, object] = {
        "reading_id": "msr:request-1",
        "instrument_id": EntityId("item:thermometer"),
        "target_id": EntityId("loc:cave"),
        "quantity": MeasurementQuantity.AMBIENT_TEMPERATURE,
        "unit": _CELSIUS,
        "sample_tick": 3,
        "nominal_division_milli": 1000,
        "displayed_scalar_milli": 5000,
    }
    values.update(overrides)
    return MeasurementReading(**values)


def test_reading_rejects_ambiguous_or_missing_display() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_scalar"):
        _reading(displayed_category="light")
    with pytest.raises(ValueError, match="measurement_invalid_scalar"):
        _reading(displayed_scalar_milli=None)


def test_category_reading_is_closed_and_excludes_scalar() -> None:
    category = _reading(
        quantity=MeasurementQuantity.LOAD_CATEGORY,
        unit=_LOAD,
        target_id=EntityId("item:crate"),
        displayed_scalar_milli=None,
        displayed_category="heavy",
    )
    assert category.displayed_category == "heavy"
    with pytest.raises(ValueError, match="measurement_invalid_category"):
        _reading(
            quantity=MeasurementQuantity.LOAD_CATEGORY,
            unit=_LOAD,
            displayed_scalar_milli=None,
            displayed_category="enormous",
        )
    with pytest.raises(ValueError, match="measurement_invalid_scalar"):
        _reading(
            quantity=MeasurementQuantity.AMBIENT_TEMPERATURE, displayed_category="light"
        )


def test_non_temperature_readings_cannot_be_negative() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_scalar"):
        _reading(
            quantity=MeasurementQuantity.RESOURCE_AMOUNT,
            unit=_RESOURCE,
            target_id=EntityId("res:grain"),
            displayed_scalar_milli=-1,
        )


@pytest.mark.parametrize("bad", [True, 1.5, "5", None])
def test_integer_slots_reject_bool_float_text_and_none(bad: object) -> None:
    with pytest.raises(ValueError):
        _instrument(nominal_step_milli=bad)
    with pytest.raises(ValueError):
        _reading(displayed_scalar_milli=bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_nan_and_infinity_are_rejected(bad: float) -> None:
    with pytest.raises(ValueError):
        _reading(displayed_scalar_milli=bad)
    with pytest.raises(ValueError):
        MeasurementReference(
            item_id=EntityId("item:ref"),
            unit=_CELSIUS,
            nominal_value_milli=bad,
            physical_value_milli=0,
        )


def test_int64_overflow_is_rejected() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_bias"):
        _instrument(intrinsic_bias_milli=2**63)
    with pytest.raises(ValueError, match="measurement_invalid_scalar"):
        _reading(displayed_scalar_milli=2**63)
    with pytest.raises(ValueError, match="measurement_invalid_step"):
        _instrument(nominal_step_milli=MEASUREMENT_MAX_STEP_MILLI + 1)


def test_never_adjusted_requires_clean_anchors() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_calibration"):
        _instrument(calibration_revision=1)
    with pytest.raises(ValueError, match="measurement_invalid_calibration"):
        _instrument(correction_milli=5)
    with pytest.raises(ValueError, match="measurement_invalid_calibration"):
        _instrument(last_adjustment_tick=2)
    adjusted = _instrument(
        calibration_state=CalibrationState.ADJUSTED,
        calibration_revision=1,
        correction_milli=7,
        last_adjustment_tick=2,
        damage_at_adjustment_milli=0,
    )
    assert adjusted.calibration_state is CalibrationState.ADJUSTED
    with pytest.raises(ValueError, match="measurement_invalid_calibration"):
        _instrument(calibration_state=CalibrationState.ADJUSTED, calibration_revision=0)


def test_timer_epoch_belongs_only_to_duration_tools() -> None:
    timer = _instrument(
        MeasurementQuantity.ELAPSED_DURATION, _TICKS, timer_epoch_tick=4
    )
    assert timer.timer_epoch_tick == 4
    with pytest.raises(ValueError, match="measurement_invalid_tick"):
        _instrument(MeasurementQuantity.ELAPSED_DURATION, _TICKS, timer_epoch_tick=None)
    with pytest.raises(ValueError, match="measurement_invalid_tick"):
        _instrument(timer_epoch_tick=4)


def test_wear_bands_are_coarse() -> None:
    assert instrument_wear_band(0) is InstrumentWearBand.INTACT
    assert instrument_wear_band(249) is InstrumentWearBand.INTACT
    assert instrument_wear_band(250) is InstrumentWearBand.WORN
    assert instrument_wear_band(749) is InstrumentWearBand.WORN
    assert instrument_wear_band(750) is InstrumentWearBand.DAMAGED
    assert instrument_wear_band(999) is InstrumentWearBand.DAMAGED
    assert instrument_wear_band(1000) is InstrumentWearBand.BROKEN
    with pytest.raises(ValueError, match="measurement_invalid_damage"):
        instrument_wear_band(1001)


def test_agent_contracts_do_not_leak_hidden_reliability() -> None:
    appearance = InstrumentAppearance(
        quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
        unit=_CELSIUS,
        nominal_step_milli=1000,
        wear=InstrumentWearBand.WORN,
        adjustment_mark_present=True,
    )
    reference = ReferenceAppearance(unit=_CELSIUS, nominal_value_milli=20000)
    reading = _reading()
    for rendered in (repr(appearance), repr(reference), repr(reading)):
        lowered = rendered.lower()
        for hidden in (
            "bias",
            "correction",
            "base_error",
            "physical_value",
            "damage_milli",
            "calibration_revision",
            "timer_epoch",
        ):
            assert hidden not in lowered
    assert set(dataclasses.asdict(appearance)) == {
        "quantity",
        "unit",
        "nominal_step_milli",
        "wear",
        "adjustment_mark_present",
    }
    assert set(dataclasses.asdict(reference)) == {"unit", "nominal_value_milli"}


def test_appearance_rejects_boolean_marker_ambiguity() -> None:
    with pytest.raises(ValueError, match="measurement_invalid_appearance"):
        InstrumentAppearance(
            quantity=MeasurementQuantity.AMBIENT_TEMPERATURE,
            unit=_CELSIUS,
            nominal_step_milli=1000,
            wear=InstrumentWearBand.INTACT,
            adjustment_mark_present=1,
        )


def test_legacy_item_keys_and_tool_category_are_unchanged() -> None:
    assert [field.name for field in dataclasses.fields(Item)] == [
        "entity_id",
        "name",
        "kind",
        "load",
        "location_id",
        "holder_id",
    ]
