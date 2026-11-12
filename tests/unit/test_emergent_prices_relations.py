"""Pairwise distributional convergence and divergence between venues."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_contract import PriceRelation, PriceSampleSource
from analysis.emergent_prices_detection import (
    detect_price_relations,
    detect_venue_distributions,
)
from analysis.emergent_prices_events import price_evidence_rows_from_events
from analysis.market_institutions_contract import market_venue_token
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit


def _venue_events(
    origin: str, *, take_count: int, samples: int = 4, start: int = 0
):
    return [
        completed(
            f"event-{origin}-{index}",
            take_kinds=("water",) * take_count,
            tick=start + index,
            origin=origin,
        )
        for index in range(samples)
    ]


def _relations_for(left: int, right: int, *, samples: int = 4):
    events = _venue_events("loc-a", take_count=left, samples=samples)
    events += _venue_events("loc-b", take_count=right, samples=samples, start=10)
    evidence = price_evidence_rows_from_events(events)
    distributions = detect_venue_distributions(evidence)
    return detect_price_relations(distributions)


def test_identical_distributions_are_converged() -> None:
    rows = _relations_for(1, 1)
    assert len(rows) == 1
    assert rows[0].relation is PriceRelation.CONVERGED
    assert rows[0].overlap_milli >= 750
    assert rows[0].group_kind == "venue"
    assert {
        rows[0].group_a_token,
        rows[0].group_b_token,
    } == {market_venue_token("loc-a"), market_venue_token("loc-b")}


def test_disjoint_distributions_are_divergent() -> None:
    rows = _relations_for(1, 9)
    assert rows[0].relation is PriceRelation.DIVERGENT
    assert rows[0].median_gap_milli >= 750


def test_partly_overlapping_distributions_are_partial() -> None:
    events = [
        completed("event-a-0", take_kinds=("water",), tick=0, origin="loc-a"),
        completed("event-a-1", take_kinds=("water",) * 2, tick=1, origin="loc-a"),
        completed("event-a-2", take_kinds=("water",), tick=2, origin="loc-a"),
        completed("event-a-3", take_kinds=("water",) * 2, tick=3, origin="loc-a"),
        completed("event-b-0", take_kinds=("water",) * 2, tick=10, origin="loc-b"),
        completed("event-b-1", take_kinds=("water",) * 3, tick=11, origin="loc-b"),
        completed("event-b-2", take_kinds=("water",) * 2, tick=12, origin="loc-b"),
        completed("event-b-3", take_kinds=("water",) * 3, tick=13, origin="loc-b"),
    ]
    evidence = price_evidence_rows_from_events(events)
    rows = detect_price_relations(detect_venue_distributions(evidence))
    assert rows
    assert all(
        row.relation
        in {
            PriceRelation.PARTIALLY_CONVERGED,
            PriceRelation.CONVERGED,
            PriceRelation.DIVERGENT,
        }
        for row in rows
    )


def test_below_threshold_is_insufficient_evidence() -> None:
    rows = _relations_for(1, 1, samples=3)
    assert rows
    assert rows[0].relation is PriceRelation.INSUFFICIENT_EVIDENCE


def test_completed_and_quoted_never_pair() -> None:
    from tests.unit.emergent_prices_analysis_helpers import proposed

    events = _venue_events("loc-a", take_count=1)
    events += _venue_events("loc-b", take_count=1, start=10)
    events.append(
        proposed(
            "quote-1",
            give_ids=("give-event-loc-a-0-0",),
            take_ids=("take-event-loc-a-0-0",),
            tick=20,
        )
    )
    evidence = price_evidence_rows_from_events(events)
    relations = detect_price_relations(detect_venue_distributions(evidence))
    assert relations
    assert all(
        row.sample_source is PriceSampleSource.COMPLETED for row in relations
    )


def test_pair_order_and_ids_are_deterministic() -> None:
    first = _relations_for(1, 2)
    second = _relations_for(2, 1)
    assert first[0].relation_id == second[0].relation_id
    assert first[0].group_a_token < first[0].group_b_token
