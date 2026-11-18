"""Strict canonical leaf codecs for physical measurement payloads."""

from __future__ import annotations

import logging
from typing import Final

from world.identifiers import EntityId
from world.measurement import (
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReading,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)

__all__ = [
    "MeasurementSerializationError",
    "decode_instrument_state",
    "decode_measurement_reading",
    "decode_measurement_reference",
    "decode_measurement_unit",
    "encode_instrument_state",
    "encode_measurement_reading",
    "encode_measurement_reference",
    "encode_measurement_unit",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.measurement_serialization"
)

_UNIT_KEYS: Final[frozenset[str]] = frozenset({"kind", "resource_unit"})
_INSTRUMENT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "item_id",
        "quantity",
        "unit",
        "nominal_step_milli",
        "intrinsic_bias_milli",
        "base_error_bound_milli",
        "damage_milli",
        "correction_milli",
        "calibration_state",
        "calibration_revision",
        "last_adjustment_tick",
        "damage_at_adjustment_milli",
        "timer_epoch_tick",
    }
)
_REFERENCE_KEYS: Final[frozenset[str]] = frozenset(
    {"item_id", "unit", "nominal_value_milli", "physical_value_milli"}
)
_READING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "reading_id",
        "instrument_id",
        "target_id",
        "quantity",
        "unit",
        "sample_tick",
        "nominal_division_milli",
        "displayed_scalar_milli",
        "displayed_category",
    }
)


class MeasurementSerializationError(ValueError):
    """Strict payload error with a stable code and path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> MeasurementSerializationError:
    _LOG.error(
        "measurement_serialization_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return MeasurementSerializationError(code, path)


def _mapping(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _fail("invalid_object", path)
    return value


def _exact_keys(value: dict[str, object], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("invalid_fields", path)


def encode_measurement_unit(unit: MeasurementUnit) -> dict[str, object]:
    return {"kind": unit.kind.value, "resource_unit": unit.resource_unit}


def decode_measurement_unit(value: object, *, path: str) -> MeasurementUnit:
    record = _mapping(value, path)
    _exact_keys(record, _UNIT_KEYS, path)
    try:
        return MeasurementUnit(
            MeasurementUnitKind(record["kind"]),  # type: ignore[arg-type]
            record["resource_unit"],  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        raise _fail("invalid_unit", path) from exc


def encode_instrument_state(state: InstrumentState) -> dict[str, object]:
    return {
        "item_id": state.item_id.value,
        "quantity": state.quantity.value,
        "unit": encode_measurement_unit(state.unit),
        "nominal_step_milli": state.nominal_step_milli,
        "intrinsic_bias_milli": state.intrinsic_bias_milli,
        "base_error_bound_milli": state.base_error_bound_milli,
        "damage_milli": state.damage_milli,
        "correction_milli": state.correction_milli,
        "calibration_state": state.calibration_state.value,
        "calibration_revision": state.calibration_revision,
        "last_adjustment_tick": state.last_adjustment_tick,
        "damage_at_adjustment_milli": state.damage_at_adjustment_milli,
        "timer_epoch_tick": state.timer_epoch_tick,
    }


def decode_instrument_state(value: object, *, path: str) -> InstrumentState:
    record = _mapping(value, path)
    _exact_keys(record, _INSTRUMENT_KEYS, path)
    try:
        return InstrumentState(
            item_id=EntityId(record["item_id"]),  # type: ignore[arg-type]
            quantity=MeasurementQuantity(record["quantity"]),  # type: ignore[arg-type]
            unit=decode_measurement_unit(record["unit"], path=f"{path}.unit"),
            nominal_step_milli=record["nominal_step_milli"],  # type: ignore[arg-type]
            intrinsic_bias_milli=record["intrinsic_bias_milli"],  # type: ignore[arg-type]
            base_error_bound_milli=record["base_error_bound_milli"],  # type: ignore[arg-type]
            damage_milli=record["damage_milli"],  # type: ignore[arg-type]
            correction_milli=record["correction_milli"],  # type: ignore[arg-type]
            calibration_state=CalibrationState(record["calibration_state"]),  # type: ignore[arg-type]
            calibration_revision=record["calibration_revision"],  # type: ignore[arg-type]
            last_adjustment_tick=record["last_adjustment_tick"],  # type: ignore[arg-type]
            damage_at_adjustment_milli=record["damage_at_adjustment_milli"],  # type: ignore[arg-type]
            timer_epoch_tick=record["timer_epoch_tick"],  # type: ignore[arg-type]
        )
    except MeasurementSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _fail("invalid_instrument", path) from exc


def encode_measurement_reference(
    reference: MeasurementReference,
) -> dict[str, object]:
    return {
        "item_id": reference.item_id.value,
        "unit": encode_measurement_unit(reference.unit),
        "nominal_value_milli": reference.nominal_value_milli,
        "physical_value_milli": reference.physical_value_milli,
    }


def decode_measurement_reference(
    value: object, *, path: str
) -> MeasurementReference:
    record = _mapping(value, path)
    _exact_keys(record, _REFERENCE_KEYS, path)
    try:
        return MeasurementReference(
            item_id=EntityId(record["item_id"]),  # type: ignore[arg-type]
            unit=decode_measurement_unit(record["unit"], path=f"{path}.unit"),
            nominal_value_milli=record["nominal_value_milli"],  # type: ignore[arg-type]
            physical_value_milli=record["physical_value_milli"],  # type: ignore[arg-type]
        )
    except MeasurementSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _fail("invalid_reference", path) from exc


def encode_measurement_reading(reading: MeasurementReading) -> dict[str, object]:
    return {
        "reading_id": reading.reading_id,
        "instrument_id": reading.instrument_id.value,
        "target_id": reading.target_id.value,
        "quantity": reading.quantity.value,
        "unit": encode_measurement_unit(reading.unit),
        "sample_tick": reading.sample_tick,
        "nominal_division_milli": reading.nominal_division_milli,
        "displayed_scalar_milli": reading.displayed_scalar_milli,
        "displayed_category": reading.displayed_category,
    }


def decode_measurement_reading(
    value: object, *, path: str
) -> MeasurementReading:
    record = _mapping(value, path)
    _exact_keys(record, _READING_KEYS, path)
    try:
        return MeasurementReading(
            reading_id=record["reading_id"],  # type: ignore[arg-type]
            instrument_id=EntityId(record["instrument_id"]),  # type: ignore[arg-type]
            target_id=EntityId(record["target_id"]),  # type: ignore[arg-type]
            quantity=MeasurementQuantity(record["quantity"]),  # type: ignore[arg-type]
            unit=decode_measurement_unit(record["unit"], path=f"{path}.unit"),
            sample_tick=record["sample_tick"],  # type: ignore[arg-type]
            nominal_division_milli=record["nominal_division_milli"],  # type: ignore[arg-type]
            displayed_scalar_milli=record["displayed_scalar_milli"],  # type: ignore[arg-type]
            displayed_category=record["displayed_category"],  # type: ignore[arg-type]
        )
    except MeasurementSerializationError:
        raise
    except (TypeError, ValueError) as exc:
        raise _fail("invalid_reading", path) from exc
