"""Public physical measurement contracts.

These records describe objective instrument condition and the *displayed*
result of an instrument interaction. A display is not a sampled truth value:
agents receive only the reading/appearance contracts, while intrinsic bias,
noise bounds, corrections and reference physical values stay engine-private.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world.identifiers import EntityId

__all__ = [
    "LOAD_CATEGORY_HEAVY_MILLI",
    "LOAD_CATEGORY_MEDIUM_MILLI",
    "MEASUREMENT_BROKEN_DAMAGE_MILLI",
    "MEASUREMENT_CATEGORY_VALUES",
    "MEASUREMENT_DAMAGED_DAMAGE_MILLI",
    "MEASUREMENT_MAX_ERROR_BOUND_MILLI",
    "MEASUREMENT_MAX_RECORDS",
    "MEASUREMENT_MAX_STEP_MILLI",
    "MEASUREMENT_POLICY_VERSION",
    "MEASUREMENT_STALE_DAMAGE_DELTA_MILLI",
    "MEASUREMENT_WEAR_BAND_INTACT_MAX",
    "MEASUREMENT_WEAR_PER_USE_MILLI",
    "MEASUREMENT_WORN_DAMAGE_MILLI",
    "CalibrationState",
    "InstrumentAppearance",
    "InstrumentState",
    "InstrumentWearBand",
    "MeasurementQuantity",
    "MeasurementReading",
    "MeasurementReference",
    "MeasurementUnit",
    "MeasurementUnitKind",
    "ReferenceAppearance",
    "instrument_wear_band",
    "measurement_unit_matches_quantity",
]

_MEASUREMENT_LOG: Final[logging.Logger] = logging.getLogger("world.measurement")

MEASUREMENT_POLICY_VERSION: Final[str] = "measurement-instruments.v1"
MEASUREMENT_MAX_RECORDS: Final[int] = 64
MEASUREMENT_MAX_STEP_MILLI: Final[int] = 1_000_000_000
MEASUREMENT_MAX_ERROR_BOUND_MILLI: Final[int] = 1_000_000_000
MEASUREMENT_BROKEN_DAMAGE_MILLI: Final[int] = 1000
MEASUREMENT_WEAR_BAND_INTACT_MAX: Final[int] = 250
MEASUREMENT_WORN_DAMAGE_MILLI: Final[int] = 250
MEASUREMENT_DAMAGED_DAMAGE_MILLI: Final[int] = 750
MEASUREMENT_WEAR_PER_USE_MILLI: Final[int] = 10
MEASUREMENT_STALE_DAMAGE_DELTA_MILLI: Final[int] = 100
LOAD_CATEGORY_MEDIUM_MILLI: Final[int] = 1000
LOAD_CATEGORY_HEAVY_MILLI: Final[int] = 5000
MEASUREMENT_CATEGORY_VALUES: Final[frozenset[str]] = frozenset(
    {"light", "medium", "heavy"}
)

_INT64_MIN: Final[int] = -(2**63)
_INT64_MAX: Final[int] = 2**63 - 1


def _fail(field_name: str, code: str) -> ValueError:
    _MEASUREMENT_LOG.error(
        "measurement_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_entity(field_name: str, value: object) -> EntityId:
    if type(value) is not EntityId:
        raise _fail(field_name, "measurement_invalid_item")
    return value


def _require_enum(field_name: str, value: object, enum_type: type, code: str) -> object:
    if type(value) is not enum_type:
        raise _fail(field_name, code)
    return value


def _require_int(
    field_name: str,
    value: object,
    *,
    code: str,
    minimum: int = _INT64_MIN,
    maximum: int = _INT64_MAX,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field_name, code)
    if value < minimum or value > maximum:
        raise _fail(field_name, code)
    return value


def _require_optional_int(
    field_name: str,
    value: object,
    *,
    code: str,
    minimum: int = _INT64_MIN,
    maximum: int = _INT64_MAX,
) -> int | None:
    if value is None:
        return None
    return _require_int(
        field_name, value, code=code, minimum=minimum, maximum=maximum
    )


def _require_bool(field_name: str, value: object, *, code: str) -> bool:
    if type(value) is not bool:
        raise _fail(field_name, code)
    return value


def _require_stable_reading_id(field_name: str, value: object) -> str:
    if not isinstance(value, str):
        raise _fail(field_name, "measurement_invalid_reading_id")
    if not 1 <= len(value) <= 128:
        raise _fail(field_name, "measurement_invalid_reading_id")
    if value != value.strip():
        raise _fail(field_name, "measurement_invalid_reading_id")
    if any(char.isspace() or ord(char) < 32 for char in value):
        raise _fail(field_name, "measurement_invalid_reading_id")
    return value


def _require_unit_label(field_name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(field_name, "measurement_invalid_unit")
    if value != value.strip():
        raise _fail(field_name, "measurement_invalid_unit")
    if any(ord(char) < 32 for char in value):
        raise _fail(field_name, "measurement_invalid_unit")
    return value


class MeasurementQuantity(StrEnum):
    """Closed set of quantities this instrument generation can observe."""

    AMBIENT_TEMPERATURE = "ambient_temperature"
    RESOURCE_AMOUNT = "resource_amount"
    ELAPSED_DURATION = "elapsed_duration"
    TRAVEL_TIME_ESTIMATE = "travel_time_estimate"
    LOAD_CATEGORY = "load_category"


class MeasurementUnitKind(StrEnum):
    """Closed unit families. Resource units keep their exact original label."""

    CELSIUS = "celsius"
    RESOURCE_UNIT = "resource_unit"
    SIMULATED_TICK = "simulated_tick"
    SIMULATED_LOAD = "simulated_load"


@dataclass(frozen=True, slots=True)
class MeasurementUnit:
    """A quantity unit, not a standards institution or conversion service."""

    kind: MeasurementUnitKind
    resource_unit: str | None = None

    def __post_init__(self) -> None:
        _require_enum(
            "MeasurementUnit.kind",
            self.kind,
            MeasurementUnitKind,
            "measurement_invalid_unit",
        )
        if self.kind is MeasurementUnitKind.RESOURCE_UNIT:
            if self.resource_unit is None:
                raise _fail("MeasurementUnit.resource_unit", "measurement_invalid_unit")
            _require_unit_label(
                "MeasurementUnit.resource_unit", self.resource_unit
            )
        elif self.resource_unit is not None:
            raise _fail("MeasurementUnit.resource_unit", "measurement_invalid_unit")


def measurement_unit_matches_quantity(
    quantity: MeasurementQuantity, unit: MeasurementUnit
) -> bool:
    """Return whether ``unit`` is the closed unit family for ``quantity``."""
    if type(quantity) is not MeasurementQuantity:
        raise _fail("quantity", "measurement_invalid_quantity")
    if type(unit) is not MeasurementUnit:
        raise _fail("unit", "measurement_invalid_unit")
    expected = {
        MeasurementQuantity.AMBIENT_TEMPERATURE: MeasurementUnitKind.CELSIUS,
        MeasurementQuantity.RESOURCE_AMOUNT: MeasurementUnitKind.RESOURCE_UNIT,
        MeasurementQuantity.ELAPSED_DURATION: MeasurementUnitKind.SIMULATED_TICK,
        MeasurementQuantity.TRAVEL_TIME_ESTIMATE: MeasurementUnitKind.SIMULATED_TICK,
        MeasurementQuantity.LOAD_CATEGORY: MeasurementUnitKind.SIMULATED_LOAD,
    }[quantity]
    return unit.kind is expected


class CalibrationState(StrEnum):
    """Physical adjustment history, not an accuracy or certification verdict."""

    NEVER_ADJUSTED = "never_adjusted"
    ADJUSTED = "adjusted"
    STALE = "stale"


class InstrumentWearBand(StrEnum):
    """Coarse objective wear visible to owners."""

    INTACT = "intact"
    WORN = "worn"
    DAMAGED = "damaged"
    BROKEN = "broken"


def instrument_wear_band(damage_milli: int) -> InstrumentWearBand:
    """Map exact damage to the coarse owner-visible wear band."""
    damage = _require_int(
        "damage_milli",
        damage_milli,
        code="measurement_invalid_damage",
        minimum=0,
        maximum=MEASUREMENT_BROKEN_DAMAGE_MILLI,
    )
    if damage >= MEASUREMENT_BROKEN_DAMAGE_MILLI:
        return InstrumentWearBand.BROKEN
    if damage >= MEASUREMENT_DAMAGED_DAMAGE_MILLI:
        return InstrumentWearBand.DAMAGED
    if damage >= MEASUREMENT_WORN_DAMAGE_MILLI:
        return InstrumentWearBand.WORN
    return InstrumentWearBand.INTACT


@dataclass(frozen=True, slots=True)
class InstrumentState:
    """Objective condition of one portable TOOL item. Engine-private inputs."""

    item_id: EntityId
    quantity: MeasurementQuantity
    unit: MeasurementUnit
    nominal_step_milli: int
    intrinsic_bias_milli: int
    base_error_bound_milli: int
    damage_milli: int
    correction_milli: int
    calibration_state: CalibrationState
    calibration_revision: int
    last_adjustment_tick: int | None = None
    damage_at_adjustment_milli: int | None = None
    timer_epoch_tick: int | None = None

    def __post_init__(self) -> None:
        _require_entity("InstrumentState.item_id", self.item_id)
        _require_enum(
            "InstrumentState.quantity",
            self.quantity,
            MeasurementQuantity,
            "measurement_invalid_quantity",
        )
        if type(self.unit) is not MeasurementUnit:
            raise _fail("InstrumentState.unit", "measurement_invalid_unit")
        if not measurement_unit_matches_quantity(self.quantity, self.unit):
            raise _fail("InstrumentState.unit", "measurement_invalid_unit")
        object.__setattr__(
            self,
            "nominal_step_milli",
            _require_int(
                "InstrumentState.nominal_step_milli",
                self.nominal_step_milli,
                code="measurement_invalid_step",
                minimum=1,
                maximum=MEASUREMENT_MAX_STEP_MILLI,
            ),
        )
        object.__setattr__(
            self,
            "intrinsic_bias_milli",
            _require_int(
                "InstrumentState.intrinsic_bias_milli",
                self.intrinsic_bias_milli,
                code="measurement_invalid_bias",
            ),
        )
        object.__setattr__(
            self,
            "base_error_bound_milli",
            _require_int(
                "InstrumentState.base_error_bound_milli",
                self.base_error_bound_milli,
                code="measurement_invalid_error_bound",
                minimum=0,
                maximum=MEASUREMENT_MAX_ERROR_BOUND_MILLI,
            ),
        )
        object.__setattr__(
            self,
            "damage_milli",
            _require_int(
                "InstrumentState.damage_milli",
                self.damage_milli,
                code="measurement_invalid_damage",
                minimum=0,
                maximum=MEASUREMENT_BROKEN_DAMAGE_MILLI,
            ),
        )
        object.__setattr__(
            self,
            "correction_milli",
            _require_int(
                "InstrumentState.correction_milli",
                self.correction_milli,
                code="measurement_invalid_correction",
            ),
        )
        _require_enum(
            "InstrumentState.calibration_state",
            self.calibration_state,
            CalibrationState,
            "measurement_invalid_calibration",
        )
        revision = _require_int(
            "InstrumentState.calibration_revision",
            self.calibration_revision,
            code="measurement_invalid_calibration",
            minimum=0,
        )
        object.__setattr__(self, "calibration_revision", revision)
        last_adjustment = _require_optional_int(
            "InstrumentState.last_adjustment_tick",
            self.last_adjustment_tick,
            code="measurement_invalid_tick",
            minimum=0,
        )
        damage_at_adjustment = _require_optional_int(
            "InstrumentState.damage_at_adjustment_milli",
            self.damage_at_adjustment_milli,
            code="measurement_invalid_calibration",
            minimum=0,
            maximum=MEASUREMENT_BROKEN_DAMAGE_MILLI,
        )
        object.__setattr__(self, "last_adjustment_tick", last_adjustment)
        object.__setattr__(
            self, "damage_at_adjustment_milli", damage_at_adjustment
        )
        if self.calibration_state is CalibrationState.NEVER_ADJUSTED:
            if revision != 0:
                raise _fail(
                    "InstrumentState.calibration_revision",
                    "measurement_invalid_calibration",
                )
            if self.correction_milli != 0:
                raise _fail(
                    "InstrumentState.correction_milli",
                    "measurement_invalid_calibration",
                )
            if last_adjustment is not None or damage_at_adjustment is not None:
                raise _fail(
                    "InstrumentState.calibration_state",
                    "measurement_invalid_calibration",
                )
        else:
            if revision < 1:
                raise _fail(
                    "InstrumentState.calibration_revision",
                    "measurement_invalid_calibration",
                )
            if last_adjustment is None or damage_at_adjustment is None:
                raise _fail(
                    "InstrumentState.calibration_state",
                    "measurement_invalid_calibration",
                )
        timer_epoch = _require_optional_int(
            "InstrumentState.timer_epoch_tick",
            self.timer_epoch_tick,
            code="measurement_invalid_tick",
            minimum=0,
        )
        if self.quantity is MeasurementQuantity.ELAPSED_DURATION:
            if timer_epoch is None:
                raise _fail(
                    "InstrumentState.timer_epoch_tick",
                    "measurement_invalid_tick",
                )
        elif timer_epoch is not None:
            raise _fail(
                "InstrumentState.timer_epoch_tick", "measurement_invalid_tick"
            )
        object.__setattr__(self, "timer_epoch_tick", timer_epoch)
        _MEASUREMENT_LOG.debug(
            "measurement_instrument_constructed item_id=%s quantity=%s",
            self.item_id.value,
            self.quantity.value,
        )


@dataclass(frozen=True, slots=True)
class MeasurementReference:
    """Physical reference object. Its physical value is never owner-visible."""

    item_id: EntityId
    unit: MeasurementUnit
    nominal_value_milli: int
    physical_value_milli: int

    def __post_init__(self) -> None:
        _require_entity("MeasurementReference.item_id", self.item_id)
        if type(self.unit) is not MeasurementUnit:
            raise _fail("MeasurementReference.unit", "measurement_invalid_unit")
        object.__setattr__(
            self,
            "nominal_value_milli",
            _require_int(
                "MeasurementReference.nominal_value_milli",
                self.nominal_value_milli,
                code="measurement_invalid_reference",
            ),
        )
        object.__setattr__(
            self,
            "physical_value_milli",
            _require_int(
                "MeasurementReference.physical_value_milli",
                self.physical_value_milli,
                code="measurement_invalid_reference",
            ),
        )
        _MEASUREMENT_LOG.debug(
            "measurement_reference_constructed item_id=%s unit_kind=%s",
            self.item_id.value,
            self.unit.kind.value,
        )


@dataclass(frozen=True, slots=True)
class MeasurementReading:
    """What the instrument displayed. Never the sampled target value."""

    reading_id: str
    instrument_id: EntityId
    target_id: EntityId
    quantity: MeasurementQuantity
    unit: MeasurementUnit
    sample_tick: int
    nominal_division_milli: int
    displayed_scalar_milli: int | None = None
    displayed_category: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reading_id",
            _require_stable_reading_id(
                "MeasurementReading.reading_id", self.reading_id
            ),
        )
        _require_entity("MeasurementReading.instrument_id", self.instrument_id)
        _require_entity("MeasurementReading.target_id", self.target_id)
        _require_enum(
            "MeasurementReading.quantity",
            self.quantity,
            MeasurementQuantity,
            "measurement_invalid_quantity",
        )
        if type(self.unit) is not MeasurementUnit:
            raise _fail("MeasurementReading.unit", "measurement_invalid_unit")
        if not measurement_unit_matches_quantity(self.quantity, self.unit):
            raise _fail("MeasurementReading.unit", "measurement_invalid_unit")
        object.__setattr__(
            self,
            "sample_tick",
            _require_int(
                "MeasurementReading.sample_tick",
                self.sample_tick,
                code="measurement_invalid_tick",
                minimum=0,
            ),
        )
        object.__setattr__(
            self,
            "nominal_division_milli",
            _require_int(
                "MeasurementReading.nominal_division_milli",
                self.nominal_division_milli,
                code="measurement_invalid_step",
                minimum=1,
                maximum=MEASUREMENT_MAX_STEP_MILLI,
            ),
        )
        has_scalar = self.displayed_scalar_milli is not None
        has_category = self.displayed_category is not None
        if has_scalar == has_category:
            raise _fail(
                "MeasurementReading.displayed_scalar_milli",
                "measurement_invalid_scalar",
            )
        if self.quantity is MeasurementQuantity.LOAD_CATEGORY:
            if has_scalar or self.displayed_category not in MEASUREMENT_CATEGORY_VALUES:
                raise _fail(
                    "MeasurementReading.displayed_category",
                    "measurement_invalid_category",
                )
        else:
            if has_category:
                raise _fail(
                    "MeasurementReading.displayed_scalar_milli",
                    "measurement_invalid_scalar",
                )
            scalar = _require_int(
                "MeasurementReading.displayed_scalar_milli",
                self.displayed_scalar_milli,
                code="measurement_invalid_scalar",
            )
            if (
                self.quantity is not MeasurementQuantity.AMBIENT_TEMPERATURE
                and scalar < 0
            ):
                raise _fail(
                    "MeasurementReading.displayed_scalar_milli",
                    "measurement_invalid_scalar",
                )
        _MEASUREMENT_LOG.debug(
            "measurement_reading_constructed reading_id=%s quantity=%s target_id=%s",
            self.reading_id,
            self.quantity.value,
            self.target_id.value,
        )


@dataclass(frozen=True, slots=True)
class InstrumentAppearance:
    """Owner-visible instrument cues. No bias, error, correction or exact damage."""

    quantity: MeasurementQuantity
    unit: MeasurementUnit
    nominal_step_milli: int
    wear: InstrumentWearBand
    adjustment_mark_present: bool

    def __post_init__(self) -> None:
        _require_enum(
            "InstrumentAppearance.quantity",
            self.quantity,
            MeasurementQuantity,
            "measurement_invalid_quantity",
        )
        if type(self.unit) is not MeasurementUnit:
            raise _fail("InstrumentAppearance.unit", "measurement_invalid_unit")
        if not measurement_unit_matches_quantity(self.quantity, self.unit):
            raise _fail("InstrumentAppearance.unit", "measurement_invalid_unit")
        object.__setattr__(
            self,
            "nominal_step_milli",
            _require_int(
                "InstrumentAppearance.nominal_step_milli",
                self.nominal_step_milli,
                code="measurement_invalid_step",
                minimum=1,
                maximum=MEASUREMENT_MAX_STEP_MILLI,
            ),
        )
        _require_enum(
            "InstrumentAppearance.wear",
            self.wear,
            InstrumentWearBand,
            "measurement_invalid_appearance",
        )
        _require_bool(
            "InstrumentAppearance.adjustment_mark_present",
            self.adjustment_mark_present,
            code="measurement_invalid_appearance",
        )


@dataclass(frozen=True, slots=True)
class ReferenceAppearance:
    """Only the visible reference mark; the physical value stays hidden."""

    unit: MeasurementUnit
    nominal_value_milli: int

    def __post_init__(self) -> None:
        if type(self.unit) is not MeasurementUnit:
            raise _fail("ReferenceAppearance.unit", "measurement_invalid_unit")
        object.__setattr__(
            self,
            "nominal_value_milli",
            _require_int(
                "ReferenceAppearance.nominal_value_milli",
                self.nominal_value_milli,
                code="measurement_invalid_reference",
            ),
        )
