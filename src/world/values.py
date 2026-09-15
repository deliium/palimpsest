"""Canonical scalar value objects for objective world state."""

from __future__ import annotations

import math
from dataclasses import dataclass


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
