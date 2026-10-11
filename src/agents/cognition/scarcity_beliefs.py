"""Owner-scoped counts of items this agent can see and does not hold."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from agents.models import AgentId
from world.identifiers import EntityId
from world.values import ItemKind

_LOG = logging.getLogger("agents.cognition.scarcity_beliefs")

_COUNT_MAX = 64


@dataclass(frozen=True, slots=True)
class ScarcityBelief:
    """One kind at one location. A missing row is not count zero."""

    item_kind: ItemKind
    believed_local_count: int
    location_id: EntityId
    tick: int

    def __post_init__(self) -> None:
        if type(self.item_kind) is not ItemKind:
            raise TypeError("ScarcityBelief.item_kind must be ItemKind")
        if (
            type(self.believed_local_count) is not int
            or isinstance(self.believed_local_count, bool)
            or not 0 <= self.believed_local_count <= _COUNT_MAX
        ):
            raise ValueError("believed_local_count must be in [0, 64]")
        if type(self.location_id) is not EntityId:
            raise TypeError("ScarcityBelief.location_id must be EntityId")
        if type(self.tick) is not int or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("ScarcityBelief.tick must be a non-negative int")


@dataclass(frozen=True, slots=True)
class ScarcityBeliefLedger:
    """Latest row per item kind for one owner. Other owners are not copied."""

    owner_id: AgentId
    rows: tuple[ScarcityBelief, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("ScarcityBeliefLedger.owner_id must be AgentId")
        if isinstance(self.rows, (str, bytes)) or not isinstance(self.rows, tuple):
            raise TypeError("rows must be a tuple")
        seen: set[ItemKind] = set()
        for row in self.rows:
            if type(row) is not ScarcityBelief:
                raise TypeError("rows entries must be ScarcityBelief")
            if row.item_kind in seen:
                raise ValueError("duplicate scarcity item_kind")
            seen.add(row.item_kind)


def empty_scarcity_beliefs(owner_id: AgentId) -> ScarcityBeliefLedger:
    """Blank owner ledger. A newborn has no rows."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    return ScarcityBeliefLedger(owner_id)


def require_owner_scarcity_beliefs(
    value: object | None, owner_id: AgentId, *, field_name: str
) -> None:
    if value is None:
        return
    if type(value) is not ScarcityBeliefLedger:
        raise TypeError(f"{field_name} must be ScarcityBeliefLedger or None")
    if value.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def scarcity_row(
    ledger: ScarcityBeliefLedger, item_kind: ItemKind
) -> ScarcityBelief | None:
    """Return the stored row, or None when this owner has never recorded the kind."""
    if type(ledger) is not ScarcityBeliefLedger:
        raise TypeError("ledger must be ScarcityBeliefLedger")
    if type(item_kind) is not ItemKind:
        raise TypeError("item_kind must be ItemKind")
    for row in ledger.rows:
        if row.item_kind is item_kind:
            return row
    return None


def update_visible_scarcity(
    ledger: ScarcityBeliefLedger,
    *,
    location_id: EntityId,
    tick: int,
    ground_kinds: tuple[ItemKind, ...],
    other_held_kinds: tuple[ItemKind, ...],
) -> ScarcityBeliefLedger:
    """Rewrite counts for kinds visible here. Hidden locations stay untouched."""
    if type(location_id) is not EntityId:
        raise TypeError("location_id must be EntityId")
    counts: dict[ItemKind, int] = {}
    for kind in (*ground_kinds, *other_held_kinds):
        if type(kind) is not ItemKind:
            raise TypeError("visible kinds must be ItemKind")
        counts[kind] = min(64, counts.get(kind, 0) + 1)
    updated = ledger
    for kind, count in counts.items():
        updated = store_scarcity_belief(
            updated, ScarcityBelief(kind, count, location_id, tick)
        )
    _LOG.debug(
        "scarcity_belief_updated location_id=%s kind_count=%s",
        location_id.value,
        len(counts),
    )
    return updated


def store_scarcity_belief(
    ledger: ScarcityBeliefLedger, row: ScarcityBelief
) -> ScarcityBeliefLedger:
    """Overwrite the row for this kind. Leaving a location does not erase it."""
    if type(ledger) is not ScarcityBeliefLedger:
        raise TypeError("ledger must be ScarcityBeliefLedger")
    if type(row) is not ScarcityBelief:
        raise TypeError("row must be ScarcityBelief")
    kept = tuple(item for item in ledger.rows if item.item_kind is not row.item_kind)
    updated = replace(ledger, rows=(*kept, row))
    _LOG.debug(
        "scarcity_belief_stored item_kind=%s believed_local_count=%s",
        row.item_kind.value,
        row.believed_local_count,
    )
    return updated
