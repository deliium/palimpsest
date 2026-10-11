"""Negotiation labels stay separate from each owner's reservation."""

from __future__ import annotations

from dataclasses import fields

from analysis.subjective_value import ExchangeLedgerSnapshot, classify_exchange
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V18,
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision


def test_eight_and_three_diverge_without_a_completion() -> None:
    views = classify_exchange(
        (_event(_offer(), tick=1, sequence=1),),
        as_of_tick=2,
        ledgers=(
            ExchangeLedgerSnapshot("alice", "tool", 8),
            ExchangeLedgerSnapshot("bob", "tool", 3),
        ),
        owner_ids=("alice", "bob"),
    )
    view = views[0]
    assert view.path == ("offer",)
    assert view.divergent is True
    assert view.realized_bundle == ()
    assert view.institution == "none"
    assert {row.owner_id: row.reservation for row in view.reservations} == {
        "alice": 8,
        "bob": 3,
    }


def test_overlapping_completion_stores_kind_counts() -> None:
    views = classify_exchange(
        (
            _event(_offer(), tick=1, sequence=1),
            _event(_completed(), tick=2, sequence=1),
        ),
        as_of_tick=2,
        ledgers=(
            ExchangeLedgerSnapshot("alice", "tool", 3),
            ExchangeLedgerSnapshot("bob", "tool", 3),
        ),
    )
    view = views[0]
    assert view.path == ("offer", "complete")
    assert view.divergent is False
    assert view.realized_bundle == (("food", 3), ("tool", 1))


def test_withdrawn_path_moves_nothing() -> None:
    views = classify_exchange(
        (
            _event(_offer(), tick=1, sequence=1),
            _event(
                ExchangeWithdrawn(EntityId("body-a"), EntityId("body-b"), "withdraw"),
                tick=2,
                sequence=1,
            ),
        ),
        as_of_tick=2,
        ledgers=(
            ExchangeLedgerSnapshot("alice", "tool", 8),
            ExchangeLedgerSnapshot("bob", "tool", 3),
        ),
    )
    view = views[0]
    assert view.path == ("offer", "withdraw")
    assert view.divergent is True
    assert view.realized_bundle == ()


def test_channel_off_is_an_empty_list() -> None:
    assert classify_exchange((), as_of_tick=1) == ()


def test_missing_ledger_is_unformed() -> None:
    views = classify_exchange(
        (_event(_offer(), tick=1, sequence=1),),
        as_of_tick=1,
        ledgers=(ExchangeLedgerSnapshot("alice", "tool", 8),),
        owner_ids=("alice", "cara"),
    )
    missing = views[0].reservations[1]
    assert missing.owner_id == "cara"
    assert missing.status == "unformed"
    assert missing.reservation is None


def test_price_field_is_absent() -> None:
    views = classify_exchange(
        (_event(_offer(), tick=1, sequence=1),),
        as_of_tick=1,
        ledgers=(ExchangeLedgerSnapshot("alice", "tool", 8),),
    )
    names = {item.name for item in fields(views[0])}
    assert "world_price" not in names
    assert "price" not in names


def _offer() -> ExchangeProposed:
    return ExchangeProposed(
        EntityId("body-a"),
        EntityId("body-b"),
        "offer",
        (EntityId("tool-1"),),
        (EntityId("food-1"), EntityId("food-2"), EntityId("food-3")),
    )


def _completed() -> ExchangeCompleted:
    return ExchangeCompleted(
        EntityId("body-a"),
        EntityId("body-b"),
        "accept",
        (EntityId("tool-1"),),
        (EntityId("food-1"), EntityId("food-2"), EntityId("food-3")),
        ("tool",),
        ("food", "food", "food"),
    )


def _event(details: object, *, tick: int, sequence: int):
    return make_physical_replayable_event(
        event_id=EventId(f"evt-{tick}-{sequence}"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=tick,
        sequence=sequence,
        cause=ActionCause(
            request_id=RequestId(f"req-{tick}-{sequence}"),
            actor_id=EntityId("body-a"),
        ),
        resulting_revision=WorldRevision(tick),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V18,
    )
