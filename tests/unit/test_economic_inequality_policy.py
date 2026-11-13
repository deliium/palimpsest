# mypy: ignore-errors
"""Locked policy and window-helper tests for economic-inequality analysis."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis.economic_inequality_contract import EconomicInequalityError
from analysis.economic_inequality_policy import (
    ECONOMIC_INEQUALITY_ANALYSIS_LOCKED_POLICY,
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
    validate_window_index,
    window_bounds,
    window_index_for_tick,
    with_window_end,
)


def test_defaults_are_locked() -> None:
    policy = default_economic_inequality_analysis_policy()
    assert policy.window_ticks == 32
    assert policy.max_windows == 512
    assert policy.min_distribution_samples == 4
    assert policy.max_event_rows == 200_000
    assert policy.max_owners == 4_096
    assert policy.max_dimension_rows == 4_096
    assert policy.max_comparison_rows == 4_096
    assert policy.max_cohorts == 32
    assert policy.max_societies == 2_048
    assert policy.max_notices == 8
    assert policy.trend_threshold_milli == 50
    assert ECONOMIC_INEQUALITY_ANALYSIS_LOCKED_POLICY["window_ticks"] == 32


@pytest.mark.parametrize(
    "field,value",
    [
        ("window_ticks", 0),
        ("max_windows", 0),
        ("min_distribution_samples", 0),
        ("trend_threshold_milli", 1_001),
        ("max_notices", 0),
        ("window_ticks", True),
        ("window_ticks", 32.0),
    ],
)
def test_invalid_policy_values_fail_closed(field: str, value: object) -> None:
    with pytest.raises(EconomicInequalityError, match="invalid_policy"):
        EconomicInequalityAnalysisPolicy(**{field: value})


def test_window_index_is_tick_floor_division() -> None:
    assert window_index_for_tick(0) == 0
    assert window_index_for_tick(31) == 0
    assert window_index_for_tick(32) == 1
    assert window_index_for_tick(64) == 2
    with pytest.raises(EconomicInequalityError, match="invalid_window"):
        window_index_for_tick(-1)
    with pytest.raises(EconomicInequalityError, match="invalid_window"):
        window_index_for_tick(32 * 512)


def test_window_bounds_and_validation() -> None:
    assert window_bounds(0) == (0, 32)
    assert window_bounds(3) == (96, 128)
    assert validate_window_index(511) == 511
    with pytest.raises(EconomicInequalityError, match="invalid_window"):
        validate_window_index(512)
    with pytest.raises(EconomicInequalityError, match="invalid_window"):
        validate_window_index(-1)


def test_with_window_end_shrinks_the_window_count() -> None:
    policy = with_window_end(95)
    assert policy.max_windows == 3
    assert policy.window_ticks == 32
    assert replace(policy, max_windows=4).max_windows == 4
    with pytest.raises(EconomicInequalityError, match="invalid_window"):
        with_window_end(-1)
    with pytest.raises(EconomicInequalityError, match="invalid_policy"):
        window_index_for_tick(0, policy=object())  # type: ignore[arg-type]
