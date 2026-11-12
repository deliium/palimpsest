"""Locked emergent-price analysis policy boundaries."""

from __future__ import annotations

import pytest

from analysis.emergent_prices_contract import EmergentPriceAnalysisError
from analysis.emergent_prices_policy import (
    EMERGENT_PRICE_ANALYSIS_LOCKED_POLICY,
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
    window_bounds,
    window_index_for_tick,
)

pytestmark = pytest.mark.unit


def test_locked_policy_equality() -> None:
    policy = default_emergent_prices_analysis_policy()
    assert type(policy) is EmergentPricesAnalysisPolicy
    for name, expected in EMERGENT_PRICE_ANALYSIS_LOCKED_POLICY.items():
        assert getattr(policy, name) == expected


def test_threshold_boundaries() -> None:
    policy = EmergentPricesAnalysisPolicy(
        convergence_low_milli=0,
        convergence_high_milli=1_000,
        alignment_low_milli=0,
        alignment_high_milli=1_000,
        min_distribution_samples=1,
        window_ticks=1,
        max_windows=1,
    )
    assert window_index_for_tick(0, policy) == 0
    assert window_bounds(0, policy) == (0, 1)
    with pytest.raises(EmergentPriceAnalysisError):
        window_index_for_tick(1, policy)


def test_out_of_range_fields_fail_closed() -> None:
    for field, value in (
        ("window_ticks", 0),
        ("max_windows", 0),
        ("min_distribution_samples", 0),
        ("convergence_high_milli", 0),
        ("convergence_low_milli", 1_000),
        ("max_ratio_milli", 0),
    ):
        with pytest.raises(EmergentPriceAnalysisError):
            EmergentPricesAnalysisPolicy(**{field: value})
