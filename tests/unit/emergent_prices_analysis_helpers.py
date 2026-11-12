"""Shared builders for detached emergent-price analysis tests."""

from __future__ import annotations

from types import SimpleNamespace

from world.events import (
    ExchangeCompleted,
    ExchangeProposed,
    ExchangeWithdrawn,
)
from world.identifiers import EntityId, EventId


def event(
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


def _ids(prefix: str, kinds: tuple[str, ...], tick: int) -> tuple[EntityId, ...]:
    return tuple(
        EntityId(f"{prefix}-{index}") for index, _kind in enumerate(kinds)
    )


def completed(
    token: str,
    *,
    give_kinds: tuple[str, ...] = ("food",),
    take_kinds: tuple[str, ...] = ("water",),
    tick: int = 0,
    origin: str | None = "loc-a",
) -> SimpleNamespace:
    index = int(token.rsplit("-", 1)[-1]) if token.rsplit("-", 1)[-1].isdigit() else 0
    return event(
        token,
        ExchangeCompleted(
            actor_id=EntityId("body-a"),
            counterparty_id=EntityId("body-b"),
            act="accept",
            give_item_ids=_ids(f"give-{token}", give_kinds, tick),
            take_item_ids=_ids(f"take-{token}", take_kinds, tick),
            give_item_kinds=give_kinds,
            take_item_kinds=take_kinds,
        ),
        tick=tick,
        sequence=index,
        origin=origin,
    )


def proposed(
    token: str,
    *,
    give_ids: tuple[str, ...],
    take_ids: tuple[str, ...],
    tick: int = 0,
    origin: str | None = "loc-a",
    withdrawn: bool = False,
) -> SimpleNamespace:
    index = int(token.rsplit("-", 1)[-1]) if token.rsplit("-", 1)[-1].isdigit() else 0
    details_type = ExchangeWithdrawn if withdrawn else ExchangeProposed
    return event(
        token,
        details_type(
            actor_id=EntityId("body-a"),
            counterparty_id=EntityId("body-b"),
            act="withdraw" if withdrawn else "offer",
            give_item_ids=tuple(EntityId(value) for value in give_ids),
            take_item_ids=tuple(EntityId(value) for value in take_ids),
        ),
        tick=tick,
        sequence=index,
        origin=origin,
    )
