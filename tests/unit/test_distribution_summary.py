"""Distribution summary helper tests."""

from __future__ import annotations

from analysis.distribution_summary import (
    proportion_confidence_interval,
    summarize_distribution,
)


def test_summarize_drops_non_finite() -> None:
    summary = summarize_distribution([1.0, float("nan"), 3.0, None, 2.0])
    assert summary.n == 3
    assert summary.dropped_non_finite == 2
    assert summary.mean == 2.0
    assert summary.interval_method == "percentile"


def test_empty_sample() -> None:
    summary = summarize_distribution([])
    assert summary.n == 0
    assert summary.mean is None


def test_binomial_interval() -> None:
    low, high, method = proportion_confidence_interval(5, 10)
    assert method == "binomial_exact"
    assert 0.0 <= low <= high <= 1.0
