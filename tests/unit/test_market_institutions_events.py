"""Committed-event extraction of bounded exchange evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.market_institutions_contract import MarketCoverage
from analysis.market_institutions_events import (
    market_evidence_digest,
    market_evidence_rows_from_events,
)
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
)
from world.events import (
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
)
from world.identifiers import EntityId, EventId

pytestmark = pytest.mark.unit


def _event(
    token: str,
    details: object,
    *,
    tick: int = 0,
    sequence: int = 0,
    origin: str | None = "loc-a",
) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=sequence,
        details=details,
        occurrence=SimpleNamespace(
            origin_location_id=None if origin is None else EntityId(origin)
        ),
    )


def _completed(
    token: str,
    *,
    tick: int = 0,
    actor: str = "body-a",
    other: str = "body-b",
    origin: str | None = "loc-a",
) -> SimpleNamespace:
    return _event(
        token,
        ExchangeCompleted(
            actor_id=EntityId(actor),
            counterparty_id=EntityId(other),
            act="accept",
            give_item_ids=(EntityId("item-give"),),
            take_item_ids=(EntityId("item-take"),),
            give_item_kinds=("food",),
            take_item_kinds=("material",),
        ),
        tick=tick,
        sequence=int(token.rsplit("-", 1)[-1])
        if token.rsplit("-", 1)[-1].isdigit()
        else 0,
        origin=origin,
    )


def _proposed(
    token: str, *, act: str = "offer", tick: int = 0, origin: str | None = "loc-a"
) -> SimpleNamespace:
    return _event(
        token,
        ExchangeProposed(
            actor_id=EntityId("body-a"),
            counterparty_id=EntityId("body-b"),
            act=act,
            give_item_ids=(EntityId("item-give"),),
            take_item_ids=(EntityId("item-take"),),
        ),
        tick=tick,
        origin=origin,
    )


def _withdrawn(token: str, *, tick: int = 0) -> SimpleNamespace:
    return _event(
        token,
        ExchangeWithdrawn(
            actor_id=EntityId("body-a"),
            counterparty_id=EntityId("body-b"),
            act="withdraw",
            give_item_ids=(EntityId("item-give"),),
            take_item_ids=(EntityId("item-take"),),
        ),
        tick=tick,
    )


def test_one_row_per_completion_with_canonical_parties() -> None:
    harvest = market_evidence_rows_from_events(
        (_completed("evt-1", tick=2), _completed("evt-2", tick=3))
    )
    assert harvest.exchange_count == 2
    assert harvest.coverage is MarketCoverage.COMPLETE
    assert harvest.exchanges[0].party_tokens == ("body-a", "body-b")
    assert harvest.exchanges[0].location_token == "loc-a"
    assert harvest.exchanges[0].source_kind == "exchange"


def test_attempt_kinds_and_missing_location() -> None:
    harvest = market_evidence_rows_from_events(
        (
            _proposed("evt-1", act="offer"),
            _proposed("evt-2", act="counteroffer", tick=1),
            _withdrawn("evt-3", tick=2),
            _proposed("evt-4", origin=None, tick=3),
        )
    )
    assert [row.attempt_kind.value for row in harvest.attempts] == [
        "offer",
        "counteroffer",
        "withdraw",
    ]
    assert "market_institutions_attempt_location_unresolved" in harvest.notices
    assert harvest.coverage is MarketCoverage.PARTIAL


def test_missing_exchange_location_fails_closed() -> None:
    from analysis.market_institutions_contract import MarketInstitutionsError

    with pytest.raises(MarketInstitutionsError):
        market_evidence_rows_from_events((_completed("evt-1", origin=None),))


def test_duplicate_event_fails_closed() -> None:
    from analysis.market_institutions_contract import MarketInstitutionsError

    duplicate = _completed("evt-1")
    with pytest.raises(MarketInstitutionsError):
        market_evidence_rows_from_events((duplicate, duplicate))


def test_unrelated_events_are_ignored() -> None:
    harvest = market_evidence_rows_from_events(
        (
            SimpleNamespace(
                event_id=EventId("evt-1"),
                tick=0,
                sequence=0,
                details=object(),
                occurrence=None,
            ),
        )
    )
    assert harvest.exchanges == ()
    assert harvest.attempts == ()
    assert harvest.coverage is MarketCoverage.MISSING


def test_independent_exchange_and_attempt_truncation() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_exchange_events=1, max_attempt_rows=1)
    harvest = market_evidence_rows_from_events(
        (
            _completed("evt-1", tick=1),
            _completed("evt-2", tick=2),
            _proposed("evt-3", tick=3),
            _proposed("evt-4", tick=4),
        ),
        policy=policy,
    )
    assert harvest.exchange_count == 1
    assert harvest.attempt_count == 1
    assert "market_institutions_exchange_truncated" in harvest.notices
    assert "market_institutions_attempt_truncated" in harvest.notices
    assert harvest.coverage is MarketCoverage.PARTIAL


def test_reordering_input_produces_identical_rows_and_digest() -> None:
    first = _completed("evt-2", tick=2)
    second = _completed("evt-1", tick=1)
    left = market_evidence_rows_from_events((first, second))
    right = market_evidence_rows_from_events((second, first))
    assert left.exchanges == right.exchanges
    assert market_evidence_digest(left) == market_evidence_digest(right)
