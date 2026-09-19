"""Canonical scalar value objects for objective world state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

PHYSICAL_DECIMAL_PLACES: Final[int] = 1


def _canonical_finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite float")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite float")
    if number == 0.0:
        return 0.0
    return number


def _bounded_need(name: str, value: object) -> float:
    number = _canonical_finite_float(name, value)
    if number < 0.0 or number > 100.0:
        raise ValueError(f"{name} must be in [0.0, 100.0]")
    return number


def _unit_interval(name: str, value: object) -> float:
    number = _canonical_finite_float(name, value)
    if number < 0.0 or number > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0]")
    return number


def _exact_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError(f"{name} must be a positive integer")
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _exact_nonneg_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int:
        raise ValueError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def round_physical(value: object) -> float:
    """Round once to one decimal place using ties-to-even, then normalize -0.0."""
    number = _canonical_finite_float("round_physical", value)
    rounded = round(number, PHYSICAL_DECIMAL_PLACES)
    return 0.0 if rounded == 0.0 else float(rounded)


def clamp_unit_interval(value: object) -> float:
    """Clamp a finite float into ``[0.0, 1.0]`` without rounding."""
    number = _canonical_finite_float("clamp_unit_interval", value)
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def clamp_need(value: object) -> float:
    """Clamp a finite float into ``[0.0, 100.0]`` without rounding."""
    number = _canonical_finite_float("clamp_need", value)
    if number < 0.0:
        return 0.0
    if number > 100.0:
        return 100.0
    return number


class ItemKind(StrEnum):
    FOOD = "food"
    WATER = "water"
    MATERIAL = "material"
    MEDICAL = "medical"
    GENERIC = "generic"


class ResourceKind(StrEnum):
    FOOD = "food"
    WATER = "water"
    MATERIAL = "material"


class WeatherCondition(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"


class DayPhase(StrEnum):
    DAY = "day"
    NIGHT = "night"


@dataclass(frozen=True, slots=True)
class Health:
    """Physical integrity. ``0.0`` is terminal; positive values are living."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _bounded_need("Health.value", self.value))


@dataclass(frozen=True, slots=True)
class Hunger:
    """Need intensity. ``0.0`` means no need; ``100.0`` is maximum need."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _bounded_need("Hunger.value", self.value))


@dataclass(frozen=True, slots=True)
class Thirst:
    """Need intensity. ``0.0`` means no need; ``100.0`` is maximum need."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _bounded_need("Thirst.value", self.value))


@dataclass(frozen=True, slots=True)
class Fatigue:
    """Need intensity. ``0.0`` means no need; ``100.0`` is maximum need."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _bounded_need("Fatigue.value", self.value))


@dataclass(frozen=True, slots=True)
class TemperatureCelsius:
    """Body or ambient temperature in Celsius. Any finite float is accepted."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "value",
            _canonical_finite_float("TemperatureCelsius.value", self.value),
        )


@dataclass(frozen=True, slots=True)
class BodyCapacity:
    """Maximum bodies (including dead) that may occupy a location."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _exact_positive_int("BodyCapacity.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class ItemCapacity:
    """Maximum ground items that may occupy a location."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _exact_nonneg_int("ItemCapacity.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class CarryCapacity:
    """Maximum total item load a body may carry."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _exact_positive_int("CarryCapacity.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class ItemLoad:
    """Positive integer load contributed by one portable item."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _exact_positive_int("ItemLoad.value", self.value)
        )


@dataclass(frozen=True, slots=True)
class UnitInterval:
    """Closed unit interval scalar used for shelter and visibility factors."""

    value: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "value", _unit_interval("UnitInterval.value", self.value)
        )
