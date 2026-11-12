"""Cross-market convergence from market-level distributions only."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceRelation,
)
from analysis.emergent_prices_detection import detect_venue_distributions
from analysis.emergent_prices_events import price_evidence_rows_from_events
from analysis.emergent_prices_markets import join_market_memberships
from analysis.emergent_prices_rows import PriceMarketMembershipInput
from analysis.market_institutions_contract import market_venue_token
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit

A = "mktc-aaaaaaaaaaaaaaaa"
B = "mktc-bbbbbbbbbbbbbbbb"


def _membership(market: str, origin: str) -> PriceMarketMembershipInput:
    return PriceMarketMembershipInput(
        market_token=market,
        venue_id=market_venue_token(origin),
        window_index=0,
        coverage=PriceCoverage.COMPLETE,
    )


def _join(left: int, right: int, *, samples: int = 4):
    events = []
    for index in range(samples):
        events.append(
            completed(
                f"event-a-{index}",
                take_kinds=("water",) * left,
                tick=index,
                origin="loc-a",
            )
        )
        events.append(
            completed(
                f"event-b-{index}",
                take_kinds=("water",) * right,
                tick=10 + index,
                origin="loc-b",
            )
        )
    evidence = price_evidence_rows_from_events(events)
    venue_rows = detect_venue_distributions(evidence)
    return join_market_memberships(
        [_membership(A, "loc-a"), _membership(B, "loc-b")],
        evidence,
        venue_rows,
    )


def test_converged_markets() -> None:
    join = _join(1, 1)
    assert join.relations[0].relation is PriceRelation.CONVERGED
    assert join.relations[0].group_kind == "market"


def test_partial_markets() -> None:
    join = _join(1, 2)
    assert join.relations[0].relation in {
        PriceRelation.PARTIALLY_CONVERGED,
        PriceRelation.DIVERGENT,
    }


def test_divergent_markets() -> None:
    join = _join(1, 9)
    assert join.relations[0].relation is PriceRelation.DIVERGENT


def test_insufficient_market_evidence() -> None:
    join = _join(1, 1, samples=3)
    assert join.relations
    assert join.relations[0].relation is PriceRelation.INSUFFICIENT_EVIDENCE


def test_relations_are_deterministic_and_ordered() -> None:
    first = _join(1, 1)
    second = _join(1, 1)
    assert [row.relation_id for row in first.relations] == [
        row.relation_id for row in second.relations
    ]
