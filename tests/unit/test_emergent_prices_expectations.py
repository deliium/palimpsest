"""One-way owner joins to objective distributions, independent of cognition."""

from __future__ import annotations

import pytest

from analysis.emergent_prices_contract import (
    PriceAlignment,
    PriceCoverage,
    PriceDistributionStatus,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceSampleSource,
    PriceUnitSource,
    price_distribution_token,
)
from analysis.emergent_prices_expectations import (
    join_price_expectations,
    join_price_quotes,
    summarize_price_units,
)
from analysis.emergent_prices_policy import EmergentPricesAnalysisPolicy
from analysis.emergent_prices_rows import (
    PriceDistributionRow,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
)

pytestmark = pytest.mark.unit

VENUE = "mkt-ven-0123456789abcdef"


def _distribution(
    *,
    median: int = 1_000,
    source: PriceSampleSource = PriceSampleSource.COMPLETED,
    sample_count: int = 4,
    unit_source: PriceUnitSource = PriceUnitSource.EXCHANGE_COUNTERPART,
    window: int = 0,
) -> PriceDistributionRow:
    return PriceDistributionRow(
        distribution_id=price_distribution_token(
            VENUE,
            window,
            "food",
            "water",
            unit_source.value,
            source.value,
        ),
        window_index=window,
        venue_id=VENUE,
        market_token="none",
        item_kind="food",
        unit_kind="water",
        unit_source=unit_source,
        sample_source=source,
        sample_count=sample_count,
        min_ratio_milli=median,
        p25_ratio_milli=median,
        median_ratio_milli=median,
        p75_ratio_milli=median,
        max_ratio_milli=median,
        iqr_milli=0,
        dispersion_milli=0,
        bin_shares_milli=(0, 0, 0, 0, 1_000),
        status=PriceDistributionStatus.AVAILABLE,
        coverage=PriceCoverage.COMPLETE,
    )


def _expectation(
    *,
    expected: int = 1_000,
    unit_source: PriceUnitSource = PriceUnitSource.OWNER_REFERENCE,
    window: int = 0,
    owner: str = "owner-1",
) -> PriceOwnerExpectationInput:
    return PriceOwnerExpectationInput(
        owner_token=owner,
        window_index=window,
        item_kind="food",
        unit_kind="water",
        unit_source=unit_source,
        expected_ratio_milli=expected,
        confidence_milli=600,
        level="expected",
        valuation_reservation=2,
        observation_count=2,
        quote_count=1,
        first_tick=0,
        last_tick=window * 32,
        coverage=PriceCoverage.COMPLETE,
    )


@pytest.mark.parametrize(
    ("expected", "alignment"),
    (
        (1_000, PriceAlignment.CONSISTENT),
        (1_100, PriceAlignment.CONSISTENT),
        (1_500, PriceAlignment.UNRESOLVED),
        (5_000, PriceAlignment.INCONSISTENT),
    ),
)
def test_alignment_thresholds(expected: int, alignment: PriceAlignment) -> None:
    join = join_price_expectations(
        [_expectation(expected=expected)], [_distribution()]
    )
    assert join.rows[0].alignment is alignment


def test_completed_is_preferred_and_recorded() -> None:
    quoted = _distribution(
        median=5_000, source=PriceSampleSource.QUOTED, sample_count=9
    )
    completed = _distribution(median=1_000)
    join = join_price_expectations(
        [_expectation()], [quoted, completed]
    )
    row = join.rows[0]
    assert row.distribution_source == "completed"
    assert row.alignment is PriceAlignment.CONSISTENT
    assert row.coverage is PriceCoverage.PARTIAL


def test_no_distribution_is_not_applicable_and_missing_input_is_explicit() -> None:
    join = join_price_expectations([_expectation()], [])
    assert join.rows[0].alignment is PriceAlignment.NOT_APPLICABLE
    assert join.rows[0].distribution_source == "none"
    missing = join_price_expectations([], [])
    assert missing.rows == ()
    assert missing.coverage is PriceCoverage.MISSING
    assert "price_owner_rows_missing" in missing.notices


def test_unit_alignment_for_each_source() -> None:
    expectations = join_price_expectations(
        [
            _expectation(unit_source=PriceUnitSource.OBSERVED_MEDIUM),
            _expectation(unit_source=PriceUnitSource.UNKNOWN),
        ],
        [_distribution()],
    )
    units = summarize_price_units(
        expectations.rows, (), [_distribution()]
    )
    by_source = {row.unit_source: row for row in units.rows}
    assert (
        by_source[PriceUnitSource.OBSERVED_MEDIUM].unit_alignment
        is PriceAlignment.CONSISTENT
    )
    assert (
        by_source[PriceUnitSource.UNKNOWN].unit_alignment
        is PriceAlignment.NOT_APPLICABLE
    )
    inconsistent = summarize_price_units(
        expectations.rows, (), [_distribution(unit_source=PriceUnitSource.QUOTED)]
    )
    assert any(
        row.unit_alignment is PriceAlignment.INCONSISTENT
        for row in inconsistent.rows
    )


def test_owner_rows_never_change_distributions() -> None:
    distributions = [_distribution()]
    before = tuple(distributions)
    join_price_expectations([_expectation(expected=9_000)], distributions)
    assert tuple(distributions) == before


def test_quote_join_is_ordered_and_capped() -> None:
    inputs = [
        PriceOwnerQuoteInput(
            owner_token=f"owner-{index}",
            venue_id=VENUE,
            window_index=0,
            item_kind="food",
            unit_kind="water",
            direction=PriceQuoteDirection.GIVE_FOR_UNIT,
            ratio_milli=1_000,
            confidence_milli=500,
            source=PriceQuoteSource.OBSERVED_OFFER,
            source_tick=index,
            first_tick=index,
            last_tick=index,
            coverage=PriceCoverage.COMPLETE,
        )
        for index in range(3)
    ]
    join = join_price_quotes(inputs)
    assert len(join.rows) == 3
    assert [row.actor_token for row in join.rows] == [
        "owner-0",
        "owner-1",
        "owner-2",
    ]
    tiny = join_price_quotes(
        inputs, policy=EmergentPricesAnalysisPolicy(max_owner_quote_rows=2)
    )
    assert len(tiny.rows) == 2
    assert "price_quote_truncated" in tiny.notices


def test_expectation_cap_truncates_deterministically() -> None:
    inputs = [_expectation(owner=f"owner-{index}") for index in range(3)]
    join = join_price_expectations(
        inputs,
        [_distribution()],
        policy=EmergentPricesAnalysisPolicy(max_expectation_rows=2),
    )
    assert len(join.rows) == 2
    assert "price_expectation_truncated" in join.notices
