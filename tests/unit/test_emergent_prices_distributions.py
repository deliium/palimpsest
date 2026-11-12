"""Analytical price distributions keep quantiles, samples, and five bins."""

# mypy: ignore-errors


from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.emergent_prices_contract import (
    PriceDistributionStatus,
    PriceSampleSource,
)
from analysis.emergent_prices_detection import (
    detect_venue_distributions,
    distribution_summary,
)
from analysis.emergent_prices_events import price_evidence_rows_from_events
from tests.unit.emergent_prices_analysis_helpers import (
    completed,
    proposed,
)

pytestmark = pytest.mark.unit


def _events(*, ratios: tuple[tuple[str, int, int], ...], origin: str = "loc-a"):
    events = []
    for index, (kind, count, tick) in enumerate(ratios):
        take = (kind,) * count
        events.append(
            completed(f"event-{index}", take_kinds=take, tick=tick, origin=origin)
        )
    return events


def test_nearest_rank_quantiles_and_five_bins() -> None:
    summary = distribution_summary([1_000, 1_000, 1_000, 1_000, 2_000])
    assert summary.status is PriceDistributionStatus.AVAILABLE
    assert summary.sample_count == 5
    assert summary.minimum == 1_000
    assert summary.median == 1_000
    assert summary.maximum == 2_000
    assert sum(summary.bins) == 1_000
    assert len(summary.bins) == 5


def test_fewer_than_four_samples_is_explicit() -> None:
    summary = distribution_summary([1_000, 2_000, 3_000])
    assert summary.status is PriceDistributionStatus.INSUFFICIENT_SAMPLES
    assert summary.sample_count == 3
    assert summary.bins == (0, 0, 0, 0, 0)


def test_venue_distributions_separate_completed_and_quoted() -> None:
    events = [
        completed(f"event-{index}", tick=index)
        for index in range(4)
    ]
    events.append(
        proposed(
            "quote-1",
            give_ids=("give-event-0-0",),
            take_ids=("take-event-0-0",),
            tick=5,
        )
    )
    evidence = price_evidence_rows_from_events(events)
    distributions = detect_venue_distributions(evidence)
    assert {row.sample_source for row in distributions} == {
        PriceSampleSource.COMPLETED,
        PriceSampleSource.QUOTED,
    }
    completed_rows = [
        row for row in distributions if row.sample_source is PriceSampleSource.COMPLETED
    ]
    quoted_rows = [
        row for row in distributions if row.sample_source is PriceSampleSource.QUOTED
    ]
    assert completed_rows[0].sample_count == 4
    assert completed_rows[0].status is PriceDistributionStatus.AVAILABLE
    assert quoted_rows[0].sample_count == 1
    assert quoted_rows[0].status is PriceDistributionStatus.INSUFFICIENT_SAMPLES
    for row in distributions:
        assert row.market_token == "none"
        assert row.distribution_id.startswith("prcd-")


def test_heterogeneous_evidence_is_never_a_distribution_sample() -> None:
    events = [
        completed(
            f"event-{index}",
            give_kinds=("food", "tool"),
            take_kinds=("water",),
            tick=index,
        )
        for index in range(4)
    ]
    evidence = price_evidence_rows_from_events(events)
    assert detect_venue_distributions(evidence) == ()


def test_unit_source_is_recorded_and_not_pooled() -> None:
    evidence = price_evidence_rows_from_events(_events(ratios=(("water", 1, 0),)))
    rows = detect_venue_distributions(evidence)
    assert rows[0].unit_source.value == "exchange_counterpart"


@given(
    st.lists(st.integers(min_value=0, max_value=64_000), min_size=4, max_size=64)
)
@settings(max_examples=50)
def test_bin_shares_always_sum_to_one_thousand(ratios: list[int]) -> None:
    summary = distribution_summary(ratios)
    if summary.status is PriceDistributionStatus.AVAILABLE:
        assert sum(summary.bins) == 1_000
        assert all(0 <= share <= 1_000 for share in summary.bins)
        assert summary.minimum <= summary.p25 <= summary.median <= summary.p75
        assert summary.p75 <= summary.maximum
