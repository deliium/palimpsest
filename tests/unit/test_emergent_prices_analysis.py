"""Bounded composition of evidence, distributions, markets, and owner joins."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import (
    emergent_prices_analysis_digest,
    empty_emergent_prices_analysis,
    harvest_emergent_prices_analysis,
)
from analysis.emergent_prices_contract import (
    EmergentPriceAnalysisError,
    PriceAlignment,
    PriceCoverage,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
)
from analysis.emergent_prices_layers import project_price_layers
from analysis.emergent_prices_rows import (
    PriceMarketMembershipInput,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
)
from analysis.market_institutions_contract import market_venue_token
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

MARKET = "mktc-aaaaaaaaaaaaaaaa"
MARKET_B = "mktc-bbbbbbbbbbbbbbbb"


def _events(*, samples: int = 4):
    events = [
        completed(f"event-{index}", tick=index, origin="loc-a")
        for index in range(samples)
    ]
    events.extend(
        completed(f"event-b-{index}", tick=10 + index, origin="loc-b")
        for index in range(samples)
    )
    return events


def _expectation() -> PriceOwnerExpectationInput:
    return PriceOwnerExpectationInput(
        owner_token="owner-1",
        window_index=0,
        item_kind="food",
        unit_kind="water",
        unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
        expected_ratio_milli=1_000,
        confidence_milli=800,
        level="strong",
        valuation_reservation=1,
        observation_count=4,
        quote_count=0,
        first_tick=0,
        last_tick=3,
        coverage=PriceCoverage.COMPLETE,
    )


def _quote() -> PriceOwnerQuoteInput:
    return PriceOwnerQuoteInput(
        owner_token="owner-1",
        venue_id=market_venue_token("loc-a"),
        window_index=0,
        item_kind="food",
        unit_kind="water",
        direction=PriceQuoteDirection.GIVE_FOR_UNIT,
        ratio_milli=1_000,
        confidence_milli=500,
        source=PriceQuoteSource.OBSERVED_OFFER,
        source_tick=1,
        first_tick=1,
        last_tick=1,
        coverage=PriceCoverage.COMPLETE,
    )


def _membership(
    market: str = MARKET, origin: str = "loc-a"
) -> PriceMarketMembershipInput:
    return PriceMarketMembershipInput(
        market_token=market,
        venue_id=market_venue_token(origin),
        window_index=0,
        coverage=PriceCoverage.COMPLETE,
    )


def test_empty_events_yield_missing_analysis() -> None:
    analysis = harvest_emergent_prices_analysis(committed_events=())
    assert analysis == empty_emergent_prices_analysis()
    assert analysis.coverage is PriceCoverage.MISSING


def test_venues_only_are_partial_without_owner_rows_or_memberships() -> None:
    analysis = harvest_emergent_prices_analysis(committed_events=_events())
    assert analysis.distributions
    assert analysis.expectations == ()
    assert analysis.market_coverage is PriceCoverage.MISSING
    assert analysis.coverage is PriceCoverage.PARTIAL


def test_complete_analysis_with_owner_rows_and_membership() -> None:
    analysis = harvest_emergent_prices_analysis(
        committed_events=_events(),
        expectation_inputs=(_expectation(),),
        quote_inputs=(_quote(),),
        membership_inputs=(
            _membership(),
            _membership(MARKET_B, "loc-b"),
        ),
    )
    assert analysis.expectation_coverage is PriceCoverage.COMPLETE
    assert analysis.quote_coverage is PriceCoverage.COMPLETE
    assert analysis.market_coverage is PriceCoverage.COMPLETE
    assert analysis.distribution_coverage is PriceCoverage.COMPLETE
    assert analysis.coverage is PriceCoverage.COMPLETE
    assert analysis.expectations[0].alignment is PriceAlignment.CONSISTENT
    assert analysis.exchange_count == 8


def test_digest_is_stable_and_layer_separation_holds() -> None:
    analysis = harvest_emergent_prices_analysis(committed_events=_events())
    assert emergent_prices_analysis_digest(analysis) == (
        emergent_prices_analysis_digest(analysis)
    )
    layers = project_price_layers(analysis)
    assert layers.objective_exchange
    assert layers.analytical_distribution
    assert layers.owner_expectation == ()


def test_window_bound_fails_closed() -> None:
    with pytest.raises(EmergentPriceAnalysisError):
        harvest_emergent_prices_analysis(
            committed_events=_events(), window_end=512 * 32
        )


def test_invalid_inputs_fail_closed() -> None:
    with pytest.raises(EmergentPriceAnalysisError):
        harvest_emergent_prices_analysis(committed_events="not-events")
    with pytest.raises(EmergentPriceAnalysisError):
        emergent_prices_analysis_digest(object())  # type: ignore[arg-type]
