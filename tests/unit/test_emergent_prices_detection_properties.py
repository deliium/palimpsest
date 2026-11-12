"""Property bounds for price distribution summaries and relations."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.emergent_prices_contract import PriceDistributionStatus
from analysis.emergent_prices_detection import distribution_summary

pytestmark = pytest.mark.unit


@given(
    st.lists(st.integers(min_value=0, max_value=64_000), min_size=0, max_size=40)
)
@settings(max_examples=75)
def test_quantiles_are_non_decreasing_and_bins_sum(
    ratios: list[int],
) -> None:
    summary = distribution_summary(ratios)
    assert summary.sample_count == len(ratios)
    if summary.status is PriceDistributionStatus.INSUFFICIENT_SAMPLES:
        assert len(ratios) < 4
        return
    assert summary.minimum <= summary.p25 <= summary.median
    assert summary.median <= summary.p75 <= summary.maximum
    assert summary.iqr == summary.p75 - summary.p25
    assert sum(summary.bins) == 1_000
    assert all(0 <= share <= 1_000 for share in summary.bins)
