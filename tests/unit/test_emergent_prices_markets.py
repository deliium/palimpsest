"""Market-level distributions through detached V4-20 memberships."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceDistributionStatus,
    PriceSampleSource,
)
from analysis.emergent_prices_detection import detect_venue_distributions
from analysis.emergent_prices_events import price_evidence_rows_from_events
from analysis.emergent_prices_markets import join_market_memberships
from analysis.emergent_prices_policy import EmergentPricesAnalysisPolicy
from analysis.emergent_prices_rows import PriceMarketMembershipInput
from analysis.market_institutions_contract import market_venue_token
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

MARKET_A = "mktc-aaaaaaaaaaaaaaaa"
MARKET_B = "mktc-bbbbbbbbbbbbbbbb"


def _events(origin: str, *, take_count: int = 1, samples: int = 4, start: int = 0):
    return [
        completed(
            f"event-{origin}-{index}",
            take_kinds=("water",) * take_count,
            tick=start + index,
            origin=origin,
        )
        for index in range(samples)
    ]


def _membership(market: str, origin: str) -> PriceMarketMembershipInput:
    return PriceMarketMembershipInput(
        market_token=market,
        venue_id=market_venue_token(origin),
        window_index=0,
        coverage=PriceCoverage.COMPLETE,
    )


def _join(events, memberships, *, policy=None):
    evidence = price_evidence_rows_from_events(events)
    venue_rows = detect_venue_distributions(evidence)
    return join_market_memberships(
        memberships, evidence, venue_rows, policy=policy
    )


def test_two_venues_join_one_market_with_recomputed_distribution() -> None:
    events = _events("loc-a", take_count=1, start=0) + _events(
        "loc-b", take_count=2, start=10
    )
    join = _join(
        events,
        [_membership(MARKET_A, "loc-a"), _membership(MARKET_A, "loc-b")],
    )
    assert len(join.markets) == 1
    market = join.markets[0]
    assert market.market_token == MARKET_A
    assert market.venue_count == 2
    assert market.distribution_count == 1
    assert market.sample_count == 8
    distribution = join.distributions[0]
    assert distribution.market_token == MARKET_A
    assert distribution.venue_id == "none"
    assert distribution.sample_source is PriceSampleSource.COMPLETED
    assert sum(distribution.bin_shares_milli) == 1_000
    assert distribution.status is PriceDistributionStatus.AVAILABLE


def test_two_markets_are_compared_pairwise() -> None:
    events = _events("loc-a", take_count=1, start=0) + _events(
        "loc-b", take_count=2, start=10
    )
    join = _join(
        events,
        [_membership(MARKET_A, "loc-a"), _membership(MARKET_B, "loc-b")],
    )
    assert len(join.markets) == 2
    assert len(join.relations) == 1
    relation = join.relations[0]
    assert relation.group_kind == "market"
    assert {relation.group_a_token, relation.group_b_token} == {
        MARKET_A,
        MARKET_B,
    }


def test_absent_membership_keeps_venues_and_reports_missing() -> None:
    evidence = price_evidence_rows_from_events(_events("loc-a"))
    venue_rows = detect_venue_distributions(evidence)
    assert venue_rows
    join = join_market_memberships((), evidence, venue_rows)
    assert join.distributions == ()
    assert join.markets == ()
    assert join.market_coverage is PriceCoverage.MISSING
    assert "price_market_membership_missing" in join.notices


def test_conflicting_venue_membership_is_skipped_with_one_notice() -> None:
    events = _events("loc-a")
    join = _join(
        events,
        [_membership(MARKET_A, "loc-a"), _membership(MARKET_B, "loc-a")],
    )
    assert any(row.market_token == MARKET_A for row in join.markets)
    assert any(row.market_token == MARKET_B for row in join.markets) is False
    assert "price_market_membership_conflict" in join.notices


def test_duplicate_membership_fails_closed() -> None:
    from analysis.emergent_prices_contract import EmergentPriceAnalysisError

    membership = _membership(MARKET_A, "loc-a")
    with pytest.raises(EmergentPriceAnalysisError):
        _join(_events("loc-a"), [membership, membership])


def test_market_cap_truncates_deterministically() -> None:
    events = _events("loc-a") + _events("loc-b", start=10)
    join = _join(
        events,
        [_membership(MARKET_A, "loc-a"), _membership(MARKET_B, "loc-b")],
        policy=EmergentPricesAnalysisPolicy(max_market_rows=1),
    )
    assert len(join.markets) == 1
    assert join.markets[0].market_token == MARKET_A


def test_market_join_never_mints_market_ids() -> None:
    join = _join(_events("loc-a"), [_membership(MARKET_A, "loc-a")])
    assert {row.market_token for row in join.markets} == {MARKET_A}
    assert {row.market_token for row in join.distributions} == {MARKET_A}
