"""Canonical scalar domain values."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    clamp_need,
    clamp_unit_interval,
    round_physical,
)

_BOUNDED = st.floats(
    min_value=0.0,
    max_value=100.0,
    allow_nan=False,
    allow_infinity=False,
    width=64,
)
_FINITE = st.floats(allow_nan=False, allow_infinity=False, width=64)


@given(value=_BOUNDED)
@settings(max_examples=40, deadline=None)
def test_property_need_scalars_accept_closed_unit_interval(value: float) -> None:
    assert Health(value).value == (0.0 if value == 0.0 else value)
    assert Hunger(value).value == (0.0 if value == 0.0 else value)
    assert Thirst(value).value == (0.0 if value == 0.0 else value)
    assert Fatigue(value).value == (0.0 if value == 0.0 else value)


@given(value=_FINITE)
@settings(max_examples=40, deadline=None)
def test_property_temperature_accepts_any_finite_float(value: float) -> None:
    expected = 0.0 if value == 0.0 else value
    assert TemperatureCelsius(value).value == expected


@pytest.mark.parametrize("wrapper", [Health, Hunger, Thirst, Fatigue])
@pytest.mark.parametrize("invalid", [-0.1, 100.1, math.inf, math.nan, True, "1"])
def test_need_scalars_reject_invalid_values(
    wrapper: type, invalid: object
) -> None:
    with pytest.raises(ValueError):
        wrapper(invalid)


@pytest.mark.parametrize("invalid", [math.inf, math.nan, True, "20", None])
def test_temperature_rejects_non_finite_and_non_numeric(invalid: object) -> None:
    with pytest.raises(ValueError):
        TemperatureCelsius(invalid)  # type: ignore[arg-type]


def test_freeze_rejects_bytes_and_custom_objects() -> None:
    from world._freeze import freeze

    with pytest.raises(TypeError):
        freeze(b"raw")
    with pytest.raises(TypeError):
        freeze(object())


def test_negative_zero_is_normalized() -> None:
    assert Health(-0.0).value == 0.0
    assert Hunger(-0.0).value == 0.0
    assert Thirst(-0.0).value == 0.0
    assert Fatigue(-0.0).value == 0.0
    assert TemperatureCelsius(-0.0).value == 0.0
    assert math.copysign(1.0, Health(-0.0).value) == 1.0


def test_zero_health_is_terminal_and_zero_needs_mean_none() -> None:
    assert Health(0.0).value == 0.0
    assert Hunger(0.0).value == 0.0
    assert Thirst(100.0).value == 100.0
    assert Fatigue(100.0).value == 100.0


def test_capacity_and_load_value_objects() -> None:
    assert BodyCapacity(1).value == 1
    assert ItemCapacity(0).value == 0
    assert CarryCapacity(3).value == 3
    assert ItemLoad(2).value == 2
    assert UnitInterval(0.5).value == 0.5
    with pytest.raises(ValueError):
        BodyCapacity(0)
    with pytest.raises(ValueError):
        ItemCapacity(-1)
    with pytest.raises(ValueError):
        CarryCapacity(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ItemLoad(0)
    with pytest.raises(ValueError):
        UnitInterval(1.1)


def test_round_physical_uses_ties_to_even() -> None:
    assert round_physical(1.25) == 1.2
    assert round_physical(1.35) == 1.4
    assert round_physical(-0.0) == 0.0
    assert clamp_need(150) == 100.0
    assert clamp_need(-3) == 0.0
    assert clamp_unit_interval(1.5) == 1.0
    assert clamp_unit_interval(-0.2) == 0.0
