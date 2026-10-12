"""Counts of how goods move. These numbers do not name a currency.

Research inference only. ``WorldEngine`` does not import this module.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from world.events import (
    CraftStarted,
    Drunk,
    Eaten,
    ExchangeCompleted,
    ExchangeProposed,
    Fed,
    Given,
    ItemCrafted,
    ResourceHarvested,
    WorldEvent,
)
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("analysis.exchange_functions")
_LAYER: Final[str] = "research_inference"
FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "is_money",
        "medium_of_exchange",
        "store_of_value",
        "unit_of_account",
        "support_band",
        "threshold",
    }
)


@dataclass(frozen=True, slots=True)
class AcceptanceShareRow:
    item_kind: str
    completed_swap_count: int
    kind_present_count: int
    kind_received_count: int
    giver_breadth: int
    share_num: int
    share_den: int


@dataclass(frozen=True, slots=True)
class AcquisitionFateRow:
    item_kind: str
    acquired_count: int
    later_transferred_count: int
    consumed_count: int
    still_held_count: int
    median_hold_ticks: int | None


@dataclass(frozen=True, slots=True)
class QuoteHomogeneityRow:
    item_kind: str
    homogeneous_side_count: int
    nonquote_count: int
    paired_item_count_median: int | None
    reference_row_count: int
    quote_num: int
    quote_den: int


@dataclass(frozen=True, slots=True)
class ExchangeFunctionViews:
    acceptance_share: tuple[AcceptanceShareRow, ...]
    acquisition_fate: tuple[AcquisitionFateRow, ...]
    quote_homogeneity: tuple[QuoteHomogeneityRow, ...]


def classify_exchange_functions(
    events: Sequence[WorldEvent],
    *,
    spec: object | None,
    ledgers: Sequence[object] = (),
) -> ExchangeFunctionViews:
    """Three views. An absent spec yields an empty harvest."""
    if spec is None:
        _LOG.debug("exchange_functions_skipped reason=spec_absent")
        return ExchangeFunctionViews((), (), ())
    ordered = tuple(events)
    kind_of = _kind_index(ordered)
    completed = [
        event
        for event in ordered
        if type(event.details) is ExchangeCompleted
    ]
    quotes = [
        event
        for event in ordered
        if type(event.details) in {ExchangeProposed, ExchangeCompleted}
    ]
    share = tuple(_acceptance_share(kind, completed) for kind in ItemKind)
    fate = tuple(_acquisition_fate(kind, ordered, kind_of) for kind in ItemKind)
    homogeneity = tuple(
        _quote_row(kind, quotes, kind_of, ledgers) for kind in ItemKind
    )
    for row in (*share, *fate, *homogeneity):
        _reject_forbidden(row)
        _LOG.debug(
            "exchange_functions_assembled family=%s kind=%s num=%s den=%s",
            type(row).__name__,
            row.item_kind,
            getattr(row, "share_num", getattr(row, "quote_num", None)),
            getattr(row, "share_den", getattr(row, "quote_den", None)),
        )
    return ExchangeFunctionViews(share, fate, homogeneity)


def _acceptance_share(
    kind: ItemKind, completed: Sequence[WorldEvent]
) -> AcceptanceShareRow:
    present = 0
    received = 0
    givers: set[str] = set()
    token = kind.value
    for event in completed:
        details = event.details
        assert type(details) is ExchangeCompleted
        on_give = token in details.give_item_kinds
        on_take = token in details.take_item_kinds
        if on_give or on_take:
            present += 1
            received += 1
        if on_give:
            givers.add(details.actor_id.value)
        if on_take:
            givers.add(details.counterparty_id.value)
    total = len(completed)
    return AcceptanceShareRow(
        kind.value,
        total,
        present,
        received,
        len(givers),
        present,
        total,
    )


def _acquisition_fate(
    kind: ItemKind, events: Sequence[WorldEvent], kind_of: Mapping[str, str]
) -> AcquisitionFateRow:
    token = kind.value
    acquired: dict[str, int] = {}
    holder: dict[str, str] = {}
    fate: dict[str, str] = {}
    hold: list[int] = []
    for event in events:
        details = event.details
        tick = event.tick
        arrivals = _arrivals(details, kind_of)
        for item_id, item_kind, body_id in arrivals:
            if item_kind != token or item_id in acquired:
                continue
            acquired[item_id] = tick
            holder[item_id] = body_id
        if type(details) is Given and details.resulting_holder_id is not None:
            item_id = details.item_id.value
            if item_id in acquired and item_id not in fate and tick > acquired[item_id]:
                fate[item_id] = "transferred"
                hold.append(tick - acquired[item_id])
        for item_id, body_id in _departures(details):
            if item_id not in acquired or item_id in fate:
                continue
            if holder.get(item_id) != body_id:
                continue
            if tick <= acquired[item_id]:
                continue
            fate[item_id] = "transferred"
            hold.append(tick - acquired[item_id])
        for item_id in _consumes(details):
            if item_id not in acquired or item_id in fate:
                continue
            fate[item_id] = "consumed"
            hold.append(tick - acquired[item_id])
    transferred = sum(1 for value in fate.values() if value == "transferred")
    consumed = sum(1 for value in fate.values() if value == "consumed")
    still = len(acquired) - transferred - consumed
    return AcquisitionFateRow(
        token,
        len(acquired),
        transferred,
        consumed,
        still,
        _lower_median(hold),
    )


def _quote_row(
    kind: ItemKind,
    quotes: Sequence[WorldEvent],
    kind_of: Mapping[str, str],
    ledgers: Sequence[object],
) -> QuoteHomogeneityRow:
    token = kind.value
    homogeneous = 0
    nonquote = 0
    paired: list[int] = []
    for event in quotes:
        sides = _quote_sides(event.details, kind_of)
        if sides is None:
            nonquote += 1
            continue
        left, right = sides
        hits = _homogeneous_kinds(left, right)
        if not hits:
            nonquote += 1
            continue
        if token in hits:
            homogeneous += 1
            other = right if left and all(item == token for item in left) else left
            paired.append(len(other))
    references = sum(
        1
        for row in ledgers
        if str(getattr(row, "reference_kind", "")) == token
    )
    return QuoteHomogeneityRow(
        token,
        homogeneous,
        nonquote,
        _lower_median(paired) if paired else None,
        references,
        homogeneous,
        len(quotes),
    )


def _homogeneous_kinds(
    left: tuple[str, ...], right: tuple[str, ...]
) -> set[str]:
    found: set[str] = set()
    if left and right:
        if len(set(left)) == 1 and any(item != left[0] for item in right):
            found.add(left[0])
        if len(set(right)) == 1 and any(item != right[0] for item in left):
            found.add(right[0])
    return found


def _quote_sides(
    details: object, kind_of: Mapping[str, str]
) -> tuple[tuple[str, ...], tuple[str, ...]] | None:
    if type(details) is ExchangeCompleted:
        return details.give_item_kinds, details.take_item_kinds
    if type(details) is not ExchangeProposed:
        return None
    give = _resolve(details.give_item_ids, kind_of)
    take = _resolve(details.take_item_ids, kind_of)
    if give is None or take is None:
        return None
    return give, take


def _resolve(
    item_ids: tuple[object, ...], kind_of: Mapping[str, str]
) -> tuple[str, ...] | None:
    kinds: list[str] = []
    for item_id in item_ids:
        key = getattr(item_id, "value", str(item_id))
        kind = kind_of.get(key)
        if kind is None:
            return None
        kinds.append(kind)
    return tuple(kinds)


def _kind_index(events: Sequence[WorldEvent]) -> dict[str, str]:
    found: dict[str, str] = {}
    for event in events:
        details = event.details
        if type(details) is ExchangeCompleted:
            for item_id, kind in zip(
                details.give_item_ids, details.give_item_kinds, strict=True
            ):
                found[item_id.value] = kind
            for item_id, kind in zip(
                details.take_item_ids, details.take_item_kinds, strict=True
            ):
                found[item_id.value] = kind
        elif type(details) is Fed:
            found[details.item_id.value] = details.item_kind
    return found


def _arrivals(
    details: object, kind_of: Mapping[str, str]
) -> tuple[tuple[str, str, str], ...]:
    rows: list[tuple[str, str, str]] = []
    if type(details) is Given and details.resulting_holder_id is not None:
        kind = kind_of.get(details.item_id.value)
        if kind is not None:
            rows.append(
                (details.item_id.value, kind, details.resulting_holder_id.value)
            )
    elif type(details) is ExchangeCompleted:
        for item_id, kind in zip(
            details.give_item_ids, details.give_item_kinds, strict=True
        ):
            rows.append((item_id.value, kind, details.counterparty_id.value))
        for item_id, kind in zip(
            details.take_item_ids, details.take_item_kinds, strict=True
        ):
            rows.append((item_id.value, kind, details.actor_id.value))
    elif type(details) is ResourceHarvested and details.created_item_id is not None:
        kind = kind_of.get(details.created_item_id.value)
        if kind is not None:
            rows.append((details.created_item_id.value, kind, ""))
    elif type(details) is ItemCrafted:
        kind = kind_of.get(details.created_item_id.value)
        if kind is not None:
            rows.append(
                (
                    details.created_item_id.value,
                    kind,
                    details.resulting_holder_id.value,
                )
            )
    return tuple(rows)


def _departures(details: object) -> tuple[tuple[str, str], ...]:
    if type(details) is Given:
        return ()
    if type(details) is ExchangeCompleted:
        leaving = [
            (item_id.value, details.actor_id.value)
            for item_id in details.give_item_ids
        ]
        leaving.extend(
            (item_id.value, details.counterparty_id.value)
            for item_id in details.take_item_ids
        )
        return tuple(leaving)
    return ()


def _consumes(details: object) -> tuple[str, ...]:
    if type(details) is Eaten:
        return (details.item_id.value,)
    if type(details) is Fed:
        return (details.item_id.value,)
    if type(details) is Drunk and details.consumed_item is True:
        return (details.source_id.value,)
    if type(details) is CraftStarted:
        return tuple(item_id.value for item_id in details.consumed_item_ids)
    return ()


def _lower_median(values: Sequence[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def _reject_forbidden(row: object) -> None:
    names = set(getattr(row, "__dataclass_fields__", {}))
    blocked = names & FORBIDDEN_KEYS
    if blocked:
        _LOG.warning(
            "exchange_functions_forbidden_key keys=%s",
            ",".join(sorted(blocked)),
        )
        raise ValueError("exchange function row refused a forbidden key")
