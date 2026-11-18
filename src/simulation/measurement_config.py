"""Exact runner configuration seam for physical measurement instruments."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from world.measurement import (
    MEASUREMENT_MAX_RECORDS,
    MEASUREMENT_POLICY_VERSION,
    CalibrationState,
    InstrumentState,
    MeasurementQuantity,
    MeasurementReference,
    MeasurementUnit,
    MeasurementUnitKind,
)

__all__ = [
    "MEASUREMENT_INSTRUMENTS_KEY",
    "MeasurementConfigError",
    "MeasurementInstrumentsSpec",
    "decode_measurement_instruments",
    "encode_measurement_instruments",
]

_LOGGER: Final[logging.Logger] = logging.getLogger("simulation.measurement_config")

MEASUREMENT_INSTRUMENTS_KEY: Final[str] = "measurement_instruments"

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
_UNIT_KEYS: Final[frozenset[str]] = frozenset({"kind", "resource_unit"})
_SPEC_KEYS: Final[frozenset[str]] = frozenset(
    {"policy_version", "instruments", "references"}
)


class MeasurementConfigError(ValueError):
    """Strict configuration failure with a stable code and JSON-like path."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{path}: {code}")


def _fail(code: str, path: str) -> MeasurementConfigError:
    _LOGGER.error(
        "measurement_config_invalid path=%s reason_code=%s",
        path,
        code,
    )
    return MeasurementConfigError(code, path)


@dataclass(frozen=True, slots=True)
class MeasurementInstrumentsSpec:
    """Declared instruments and references anchored to existing TOOL items."""

    policy_version: str
    instruments: tuple[InstrumentState, ...]
    references: tuple[MeasurementReference, ...] = ()

    def __post_init__(self) -> None:
        if self.policy_version != MEASUREMENT_POLICY_VERSION:
            raise _fail(
                "measurement_policy_unsupported",
                "measurement_instruments.policy_version",
            )
        instruments = self._ordered_records(
            "instruments", self.instruments, InstrumentState
        )
        references = self._ordered_records(
            "references", self.references, MeasurementReference
        )
        if not instruments:
            raise _fail(
                "measurement_anchor_invalid", "measurement_instruments.instruments"
            )
        instrument_ids = {instrument.item_id for instrument in instruments}
        reference_ids = {reference.item_id for reference in references}
        if instrument_ids & reference_ids:
            raise _fail(
                "measurement_anchor_invalid", "measurement_instruments.references"
            )
        object.__setattr__(self, "instruments", instruments)
        object.__setattr__(self, "references", references)
        _LOGGER.info(
            "measurement_instruments_configured policy_version=%s "
            "instrument_count=%s reference_count=%s",
            self.policy_version,
            len(instruments),
            len(references),
        )

    @staticmethod
    def _ordered_records(
        name: str, values: object, model_type: type
    ) -> tuple[Any, ...]:
        if isinstance(values, (str, bytes, bytearray)) or not isinstance(
            values, (tuple, list)
        ):
            raise _fail("measurement_anchor_invalid", f"measurement_instruments.{name}")
        records = tuple(values)
        if len(records) > MEASUREMENT_MAX_RECORDS:
            raise _fail("measurement_anchor_invalid", f"measurement_instruments.{name}")
        for index, record in enumerate(records):
            if type(record) is not model_type:
                raise _fail(
                    "measurement_anchor_invalid",
                    f"measurement_instruments.{name}[{index}]",
                )
        identifiers = [record.item_id.value for record in records]
        if identifiers != sorted(identifiers):
            raise _fail("measurement_anchor_invalid", f"measurement_instruments.{name}")
        if len(set(identifiers)) != len(identifiers):
            raise _fail("measurement_anchor_invalid", f"measurement_instruments.{name}")
        return records


def _encode_unit(unit: MeasurementUnit) -> dict[str, object]:
    return {"kind": unit.kind.value, "resource_unit": unit.resource_unit}


def _encode_instrument(state: InstrumentState) -> dict[str, object]:
    return {
        "item_id": state.item_id.value,
        "quantity": state.quantity.value,
        "unit": _encode_unit(state.unit),
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


def _encode_reference(reference: MeasurementReference) -> dict[str, object]:
    return {
        "item_id": reference.item_id.value,
        "unit": _encode_unit(reference.unit),
        "nominal_value_milli": reference.nominal_value_milli,
        "physical_value_milli": reference.physical_value_milli,
    }


def encode_measurement_instruments(
    spec: MeasurementInstrumentsSpec,
) -> dict[str, object]:
    """Encode the exact ``measurement_instruments`` sibling object."""
    if type(spec) is not MeasurementInstrumentsSpec:
        raise TypeError("spec must be MeasurementInstrumentsSpec")
    return {
        "policy_version": spec.policy_version,
        "instruments": [_encode_instrument(item) for item in spec.instruments],
        "references": [_encode_reference(item) for item in spec.references],
    }


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail("measurement_anchor_invalid", path)
    return value


def _require_keys(value: dict[str, Any], keys: frozenset[str], path: str) -> None:
    if set(value) != keys:
        raise _fail("measurement_anchor_invalid", path)


def _decode_unit(value: object, path: str) -> MeasurementUnit:
    unit = _require_mapping(value, path)
    _require_keys(unit, _UNIT_KEYS, path)
    kind = unit["kind"]
    try:
        return MeasurementUnit(
            MeasurementUnitKind(kind),
            unit["resource_unit"],
        )
    except (TypeError, ValueError) as exc:
        raise _fail("measurement_anchor_invalid", path) from exc


def _decode_instrument(value: object, path: str) -> InstrumentState:
    record = _require_mapping(value, path)
    _require_keys(record, _INSTRUMENT_KEYS, path)
    try:
        from world.identifiers import EntityId

        return InstrumentState(
            item_id=EntityId(record["item_id"]),
            quantity=MeasurementQuantity(record["quantity"]),
            unit=_decode_unit(record["unit"], f"{path}.unit"),
            nominal_step_milli=record["nominal_step_milli"],
            intrinsic_bias_milli=record["intrinsic_bias_milli"],
            base_error_bound_milli=record["base_error_bound_milli"],
            damage_milli=record["damage_milli"],
            correction_milli=record["correction_milli"],
            calibration_state=CalibrationState(record["calibration_state"]),
            calibration_revision=record["calibration_revision"],
            last_adjustment_tick=record["last_adjustment_tick"],
            damage_at_adjustment_milli=record["damage_at_adjustment_milli"],
            timer_epoch_tick=record["timer_epoch_tick"],
        )
    except (TypeError, ValueError) as exc:
        raise _fail("measurement_anchor_invalid", path) from exc


def _decode_reference(value: object, path: str) -> MeasurementReference:
    record = _require_mapping(value, path)
    _require_keys(record, _REFERENCE_KEYS, path)
    try:
        from world.identifiers import EntityId

        return MeasurementReference(
            item_id=EntityId(record["item_id"]),
            unit=_decode_unit(record["unit"], f"{path}.unit"),
            nominal_value_milli=record["nominal_value_milli"],
            physical_value_milli=record["physical_value_milli"],
        )
    except (TypeError, ValueError) as exc:
        raise _fail("measurement_anchor_invalid", path) from exc


def decode_measurement_instruments(value: object) -> MeasurementInstrumentsSpec:
    """Decode the exact ``measurement_instruments`` sibling object."""
    path = "$.measurement_instruments"
    record = _require_mapping(value, path)
    _require_keys(record, _SPEC_KEYS, path)
    instruments_raw = record["instruments"]
    references_raw = record["references"]
    if not isinstance(instruments_raw, list) or not isinstance(references_raw, list):
        raise _fail("measurement_anchor_invalid", path)
    instruments = tuple(
        _decode_instrument(item, f"{path}.instruments[{index}]")
        for index, item in enumerate(instruments_raw)
    )
    references = tuple(
        _decode_reference(item, f"{path}.references[{index}]")
        for index, item in enumerate(references_raw)
    )
    policy_version = record["policy_version"]
    if type(policy_version) is not str:
        raise _fail("measurement_anchor_invalid", f"{path}.policy_version")
    try:
        return MeasurementInstrumentsSpec(
            policy_version=policy_version,
            instruments=instruments,
            references=references,
        )
    except MeasurementConfigError:
        raise
    except (TypeError, ValueError) as exc:
        raise _fail("measurement_anchor_invalid", path) from exc
