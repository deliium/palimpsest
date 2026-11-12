"""Cap-bound properties: deterministic prefixes and explicit partial coverage."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
)
from analysis.emergent_prices_detection import (
    detect_price_relations,
    detect_venue_distributions,
)
from analysis.emergent_prices_events import price_evidence_rows_from_events
from analysis.emergent_prices_expectations import (
    join_price_expectations,
    join_price_quotes,
)
from analysis.emergent_prices_policy import EmergentPricesAnalysisPolicy
from analysis.emergent_prices_rows import (
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
)
from tests.unit.emergent_prices_analysis_helpers import completed, proposed

pytestmark = pytest.mark.unit

VENUE = "mkt-ven-0123456789abcdef"


@given(st.integers(min_value=1, max_value=5))
@settings(max_examples=20)
def test_exchange_cap_is_a_deterministic_prefix(count: int) -> None:
    events = [
        completed(f"event-{index}", tick=index) for index in range(count)
    ]
    policy = EmergentPricesAnalysisPolicy(max_exchange_events=2)
    harvest = price_evidence_rows_from_events(events, policy=policy)
    assert harvest.exchange_count == min(2, count)
    assert tuple(row.event_token for row in harvest.exchanges) == tuple(
        sorted(row.event_token for row in harvest.exchanges)
    )
    if count > 2:
        assert harvest.coverage is PriceCoverage.PARTIAL
        assert harvest.notices.count("price_evidence_truncated") == 1


@given(st.integers(min_value=1, max_value=4))
@settings(max_examples=15)
def test_quote_cap_is_a_deterministic_prefix(count: int) -> None:
    events = [
        completed("event-0"),
        *(
            proposed(
                f"quote-{index}",
                give_ids=("give-event-0-0",),
                take_ids=("take-event-0-0",),
                tick=index + 1,
            )
            for index in range(count)
        ),
    ]
    policy = EmergentPricesAnalysisPolicy(max_quote_events=1)
    harvest = price_evidence_rows_from_events(events, policy=policy)
    assert harvest.quote_count == min(1, count)


def test_expectation_and_quote_caps() -> None:
    distributions = detect_venue_distributions(
        price_evidence_rows_from_events(
            [completed(f"event-{index}", tick=index) for index in range(4)]
        )
    )
    expectations = [
        PriceOwnerExpectationInput(
            owner_token=f"owner-{index}",
            window_index=0,
            item_kind="food",
            unit_kind="water",
            unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
            expected_ratio_milli=1_000,
            confidence_milli=600,
            level="expected",
            valuation_reservation=1,
            observation_count=4,
            quote_count=0,
            first_tick=0,
            last_tick=3,
            coverage=PriceCoverage.COMPLETE,
        )
        for index in range(4)
    ]
    join = join_price_expectations(
        expectations,
        distributions,
        policy=EmergentPricesAnalysisPolicy(max_expectation_rows=2),
    )
    assert len(join.rows) == 2
    assert join.notices.count("price_expectation_truncated") == 1
    quotes = [
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
        for index in range(4)
    ]
    quote_join = join_price_quotes(
        quotes, policy=EmergentPricesAnalysisPolicy(max_owner_quote_rows=2)
    )
    assert len(quote_join.rows) == 2
    assert quote_join.notices.count("price_quote_truncated") == 1


def test_relation_cap() -> None:
    events = []
    for index in range(4):
        events.append(
            completed(f"event-a-{index}", tick=index, origin="loc-a")
        )
        events.append(
            completed(f"event-b-{index}", tick=10 + index, origin="loc-b")
        )
        events.append(
            completed(f"event-c-{index}", tick=20 + index, origin="loc-c")
        )
    distributions = detect_venue_distributions(
        price_evidence_rows_from_events(events)
    )
    relations = detect_price_relations(
        distributions,
        policy=EmergentPricesAnalysisPolicy(max_relation_rows=1),
    )
    assert len(relations) == 1
    assert relations[0].coverage is PriceCoverage.PARTIAL
