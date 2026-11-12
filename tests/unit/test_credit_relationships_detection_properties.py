"""Hypothesis properties for credit repayment distributions."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.credit_relationships_contract import CreditDistributionStatus
from analysis.credit_relationships_detection import credit_distribution_summary

pytestmark = pytest.mark.unit

RATIOS = st.lists(
    st.integers(min_value=1, max_value=64_000), max_size=40
)


@given(RATIOS)
@settings(max_examples=120)
def test_bins_always_sum_to_one_thousand(ratios: list[int]) -> None:
    summary = credit_distribution_summary(ratios)
    if summary.status is CreditDistributionStatus.AVAILABLE:
        assert sum(summary.bins) == 1_000
        assert all(share >= 0 for share in summary.bins)


@given(RATIOS)
@settings(max_examples=120)
def test_quantiles_are_ordered_when_available(ratios: list[int]) -> None:
    summary = credit_distribution_summary(ratios)
    if summary.status is CreditDistributionStatus.AVAILABLE:
        assert (
            summary.minimum
            <= summary.p25
            <= summary.median
            <= summary.p75
            <= summary.maximum
        )
        assert summary.iqr == summary.p75 - summary.p25
        assert summary.iqr >= 0


@given(RATIOS, st.integers(min_value=1, max_value=64_000))
@settings(max_examples=120)
def test_sample_count_is_monotone(ratios: list[int], extra: int) -> None:
    before = credit_distribution_summary(ratios)
    after = credit_distribution_summary([*ratios, extra])
    assert after.sample_count >= before.sample_count
