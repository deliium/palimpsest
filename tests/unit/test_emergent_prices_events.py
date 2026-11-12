"""Committed-event reconstruction of exchange-implied ratio evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.emergent_prices_contract import PriceCoverage, PricePairing
from analysis.emergent_prices_events import (
    price_evidence_digest,
    price_evidence_rows_from_events,
)
from analysis.emergent_prices_policy import EmergentPricesAnalysisPolicy
from tests.unit.emergent_prices_analysis_helpers import (
    completed,
    proposed,
)

pytestmark = pytest.mark.unit


def test_paired_exchange_produces_one_canonical_ratio() -> None:
    harvest = price_evidence_rows_from_events(
        [completed("event-1", give_kinds=("food",), take_kinds=("water",))]
    )
    assert harvest.coverage is PriceCoverage.COMPLETE
    row = harvest.exchanges[0]
    assert row.pairing is PricePairing.PAIRED
    assert (row.item_kind, row.unit_kind) == ("food", "water")
    assert row.ratio_milli == 1_000


def test_counts_set_the_ratio() -> None:
    harvest = price_evidence_rows_from_events(
        [
            completed(
                "event-1",
                give_kinds=("food",),
                take_kinds=("water", "water", "water"),
            )
        ]
    )
    assert harvest.exchanges[0].ratio_milli == 3_000
    assert harvest.exchanges[0].unit_count == 3


def test_heterogeneous_side_never_produces_a_ratio() -> None:
    harvest = price_evidence_rows_from_events(
        [
            completed(
                "event-1",
                give_kinds=("food", "tool"),
                take_kinds=("water",),
            )
        ]
    )
    assert harvest.exchanges[0].pairing is PricePairing.HETEROGENEOUS
    assert harvest.exchanges[0].ratio_milli is None


def test_same_kind_swap_never_produces_a_ratio() -> None:
    harvest = price_evidence_rows_from_events(
        [completed("event-1", give_kinds=("food",), take_kinds=("food",))]
    )
    assert harvest.exchanges[0].pairing is PricePairing.SAME_KIND
    assert harvest.exchanges[0].ratio_milli is None


def test_out_of_range_ratio_is_excluded() -> None:
    harvest = price_evidence_rows_from_events(
        [
            completed(
                "event-1",
                give_kinds=("food",),
                take_kinds=("water",) * 70,
            )
        ]
    )
    assert harvest.exchanges[0].pairing is PricePairing.OUT_OF_RANGE
    assert harvest.exchanges[0].ratio_milli is None


def test_missing_venue_is_partial_not_fabricated() -> None:
    harvest = price_evidence_rows_from_events(
        [completed("event-1", origin=None)]
    )
    assert harvest.coverage is PriceCoverage.PARTIAL
    assert harvest.exchanges[0].venue_token == "none"
    assert "price_venue_unresolved" in harvest.notices


def test_proposal_quotes_follow_the_same_pairing_rule() -> None:
    events = [
        completed(
            "event-1",
            give_kinds=("food", "tool"),
            take_kinds=("water",),
        ),
        proposed(
            "event-2",
            give_ids=("give-event-1-0", "give-event-1-1"),
            take_ids=("take-event-1-0",),
            tick=1,
        ),
        proposed(
            "event-3",
            give_ids=("give-event-1-0",),
            take_ids=("take-event-1-0",),
            tick=2,
        ),
    ]
    harvest = price_evidence_rows_from_events(events)
    assert len(harvest.quotes) == 2
    paired = [row for row in harvest.quotes if row.pairing is PricePairing.PAIRED]
    assert len(paired) == 1
    assert paired[0].ratio_milli == 1_000


def test_duplicate_quote_rows_are_deduplicated() -> None:
    events = [
        completed("event-1", give_kinds=("food",), take_kinds=("water",)),
        proposed(
            "event-2",
            give_ids=("give-event-1-0",),
            take_ids=("take-event-1-0",),
            tick=1,
        ),
    ]
    harvest = price_evidence_rows_from_events(events)
    assert len(harvest.quotes) == 1


def test_cap_truncation_is_deterministic_and_partial() -> None:
    policy = EmergentPricesAnalysisPolicy(max_exchange_events=1)
    harvest = price_evidence_rows_from_events(
        [completed("event-1"), completed("event-2", tick=1)],
        policy=policy,
    )
    assert harvest.exchange_count == 1
    assert harvest.exchanges[0].event_token == "event-1"
    assert harvest.coverage is PriceCoverage.PARTIAL
    assert "price_evidence_truncated" in harvest.notices


def test_digest_is_order_independent_for_canonical_rows() -> None:
    first = price_evidence_rows_from_events(
        [completed("event-1"), completed("event-2", tick=1)]
    )
    second = price_evidence_rows_from_events(
        [completed("event-2", tick=1), completed("event-1")]
    )
    assert price_evidence_digest(first) == price_evidence_digest(second)


def test_unknown_details_are_ignored() -> None:
    harvest = price_evidence_rows_from_events(
        [
            SimpleNamespace(
                event_id=SimpleNamespace(value="event-1"),
                tick=0,
                sequence=0,
                details=object(),
            )
        ]
    )
    assert harvest.coverage is PriceCoverage.MISSING
    assert harvest.exchanges == ()
