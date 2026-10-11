"""Analysis-only labels for barter. Not a market price.

Path tokens stay separate from each owner's reservation. This module never
moves items and is not imported by ``WorldEngine``.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Final

from world.events import (
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
    WorldEvent,
)
from world.identifiers import require_exact_nonneg_int

_LOG: Final[logging.Logger] = logging.getLogger("analysis.subjective_value")
_PRICE_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "world_price",
        "market_price",
        "price_table",
        "exchange_rate",
        "currency",
        "posted_price",
        "clearing_price",
        "numeraire",
        "price",
    }
)


@dataclass(frozen=True, slots=True)
class ExchangeLedgerSnapshot:
    """One owner's reservation for one kind. Not a posted price."""

    owner_id: str
    item_kind: str
    reservation: int

    def __post_init__(self) -> None:
        if type(self.owner_id) is not str or self.owner_id == "":
            raise ValueError("ExchangeLedgerSnapshot.owner_id")
        if type(self.item_kind) is not str or self.item_kind == "":
            raise ValueError("ExchangeLedgerSnapshot.item_kind")
        if (
            type(self.reservation) is not int
            or isinstance(self.reservation, bool)
            or not 0 <= self.reservation <= 16
        ):
            raise ValueError("ExchangeLedgerSnapshot.reservation")


@dataclass(frozen=True, slots=True)
class ExchangeReservation:
    """A formed reservation, or ``unformed`` when that owner has no row."""

    owner_id: str
    item_kind: str
    reservation: int | None
    status: str

    def __post_init__(self) -> None:
        if self.status not in {"formed", "unformed"}:
            raise ValueError("ExchangeReservation.status")
        if self.status == "unformed" and self.reservation is not None:
            raise ValueError("unformed reservation")
        if self.status == "formed" and type(self.reservation) is not int:
            raise ValueError("formed reservation")


@dataclass(frozen=True, slots=True)
class ExchangeView:
    """What was said, what moved, and what each owner believed."""

    path: tuple[str, ...]
    reservations: tuple[ExchangeReservation, ...]
    divergent: bool
    realized_bundle: tuple[tuple[str, int], ...]
    institution: str

    def __post_init__(self) -> None:
        if self.institution != "none":
            raise ValueError("institution must be none")
        names = {item.name for item in fields(self)}
        if names & _PRICE_TOKENS:
            raise ValueError("price field")


def classify_exchange(
    events: Sequence[WorldEvent],
    *,
    as_of_tick: int,
    ledgers: Sequence[ExchangeLedgerSnapshot] = (),
    owner_ids: Sequence[str] = (),
) -> tuple[ExchangeView, ...]:
    """Label one negotiation path. Channel-off logs yield an empty tuple."""
    typed_tick = require_exact_nonneg_int("as_of_tick", as_of_tick)
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be a sequence of WorldEvent")
    ordered = tuple(
        event
        for event in events
        if type(event) is WorldEvent and event.tick <= typed_tick
    )
    path: list[str] = []
    kind_counts: Counter[str] = Counter()
    for event in ordered:
        token = _path_token(event.details)
        if token is None:
            continue
        path.append(token)
        if type(event.details) is ExchangeCompleted:
            kind_counts.update(event.details.give_item_kinds)
            kind_counts.update(event.details.take_item_kinds)
    if not path:
        return ()
    reservations = _reservations(ledgers, owner_ids)
    view = ExchangeView(
        tuple(path),
        reservations,
        _divergent(reservations),
        tuple(sorted(kind_counts.items())),
        "none",
    )
    _LOG.debug(
        "exchange_classified divergent=%s event_count=%s",
        view.divergent,
        len(view.path),
    )
    return (view,)


def _path_token(details: object) -> str | None:
    if type(details) is ExchangeProposed:
        return details.act
    if type(details) is ExchangeWithdrawn:
        return "withdraw"
    if type(details) is ExchangeCompleted:
        return "complete"
    return None


def _reservations(
    ledgers: Sequence[ExchangeLedgerSnapshot],
    owner_ids: Sequence[str],
) -> tuple[ExchangeReservation, ...]:
    formed = tuple(
        ExchangeReservation(row.owner_id, row.item_kind, row.reservation, "formed")
        for row in ledgers
    )
    known = {row.owner_id for row in ledgers}
    missing = tuple(
        ExchangeReservation(owner_id, "", None, "unformed")
        for owner_id in owner_ids
        if owner_id not in known
    )
    return formed + missing


def _divergent(rows: tuple[ExchangeReservation, ...]) -> bool:
    tools = [
        row.reservation
        for row in rows
        if row.item_kind == "tool" and row.status == "formed"
    ]
    return len(tools) >= 2 and len(set(tools)) > 1
