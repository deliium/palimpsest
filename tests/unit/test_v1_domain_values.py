"""Canonical scalar domain values."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

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
