"""Owner-scoped memory of kinds accepted in observed swaps.

A missing row is not received-count zero. The engine never reads this ledger.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from agents.models import AgentId
from world.values import ItemKind

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.acceptance_memory")

_MAX_RECEIVED: Final[int] = 64
_MAX_GIVERS: Final[int] = 8
_MAX_FINGERPRINTS: Final[int] = 32

Fingerprint = tuple[int, str, str, tuple[str, ...], tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class AcceptanceMemoryRow:
    """How often this owner has seen one kind arrive in a completed swap."""

    item_kind: ItemKind
    received_count: int
    giver_ids: tuple[str, ...]
    tick: int

    def __post_init__(self) -> None:
        if type(self.item_kind) is not ItemKind:
            raise TypeError("item_kind must be ItemKind")
        if (
            type(self.received_count) is not int
            or isinstance(self.received_count, bool)
            or not 0 <= self.received_count <= _MAX_RECEIVED
        ):
            raise ValueError("received_count must be in [0, 64]")
        if isinstance(self.giver_ids, (str, bytes)) or not isinstance(
            self.giver_ids, tuple
        ):
            raise TypeError("giver_ids must be a tuple")
        if len(self.giver_ids) > _MAX_GIVERS or len(set(self.giver_ids)) != len(
            self.giver_ids
        ):
            raise ValueError("giver_ids must be at most 8 distinct ids")
        if any(type(item) is not str or not item for item in self.giver_ids):
            raise TypeError("giver_ids entries must be non-empty str")
        if type(self.tick) is not int or isinstance(self.tick, bool) or self.tick < 0:
            raise ValueError("tick must be a non-negative int")


@dataclass(frozen=True, slots=True)
class AcceptanceMemoryLedger:
    """Rows for kinds this owner has seen accepted, plus recent fingerprints."""

    owner_id: AgentId
    rows: tuple[AcceptanceMemoryRow, ...] = ()
    fingerprints: tuple[Fingerprint, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("AcceptanceMemoryLedger.owner_id must be AgentId")
        if isinstance(self.rows, (str, bytes)) or not isinstance(self.rows, tuple):
            raise TypeError("rows must be a tuple")
        if isinstance(self.fingerprints, (str, bytes)) or not isinstance(
            self.fingerprints, tuple
        ):
            raise TypeError("fingerprints must be a tuple")
        seen: set[ItemKind] = set()
        copied: list[AcceptanceMemoryRow] = []
        for row in self.rows:
            if type(row) is not AcceptanceMemoryRow:
                raise TypeError("rows entries must be AcceptanceMemoryRow")
            if row.item_kind in seen:
                raise ValueError("duplicate acceptance row")
            seen.add(row.item_kind)
            copied.append(row)
        fingerprints: list[Fingerprint] = []
        for item in self.fingerprints:
            fingerprints.append(_require_fingerprint(item))
        if len(fingerprints) > _MAX_FINGERPRINTS:
            raise ValueError("fingerprint cap exceeded")
        object.__setattr__(self, "rows", tuple(copied))
        object.__setattr__(self, "fingerprints", tuple(fingerprints))


def empty_acceptance_memories(owner_id: AgentId) -> AcceptanceMemoryLedger:
    """Newborn ledger. Does not copy another owner's rows."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    _LOG.info(
        "acceptance_memory_blank owner_id=%s",
        owner_id.value,
    )
    return AcceptanceMemoryLedger(owner_id)


def require_owner_acceptance_memories(
    value: object | None, owner_id: AgentId, *, field_name: str
) -> None:
    if value is None:
        return
    if type(value) is not AcceptanceMemoryLedger:
        raise TypeError(f"{field_name} must be AcceptanceMemoryLedger or None")
    if value.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def received_count_for(
    ledger: AcceptanceMemoryLedger | None, item_kind: ItemKind
) -> int | None:
    """Return the stored count, or None when this owner has no row."""
    if ledger is None:
        return None
    if type(ledger) is not AcceptanceMemoryLedger:
        raise TypeError("ledger must be AcceptanceMemoryLedger or None")
    for row in ledger.rows:
        if row.item_kind is item_kind:
            return row.received_count
    return None


def note_exchange_completed(
    ledger: AcceptanceMemoryLedger,
    *,
    observation_tick: int,
    source_tick: int,
    window_ticks: int,
    actor_id: str,
    counterparty_id: str,
    give_item_ids: tuple[str, ...],
    take_item_ids: tuple[str, ...],
    give_item_kinds: tuple[ItemKind, ...],
    take_item_kinds: tuple[ItemKind, ...],
) -> tuple[AcceptanceMemoryLedger, str]:
    """Fold one observed completion. Returns the ledger and a status token.

    Status is ``ignored``, ``skipped``, or ``accepted``. A second completion
    in the same tick still applies when its item ids differ.
    """
    if type(ledger) is not AcceptanceMemoryLedger:
        raise TypeError("ledger must be AcceptanceMemoryLedger")
    if observation_tick - source_tick > window_ticks:
        _LOG.debug(
            "acceptance_event_ignored owner_id=%s source_tick=%s observation_tick=%s",
            ledger.owner_id.value,
            source_tick,
            observation_tick,
        )
        return ledger, "ignored"
    fingerprint = (
        source_tick,
        actor_id,
        counterparty_id,
        give_item_ids,
        take_item_ids,
    )
    _require_fingerprint(fingerprint)
    if fingerprint in ledger.fingerprints:
        _LOG.debug(
            "acceptance_fingerprint_skipped owner_id=%s source_tick=%s",
            ledger.owner_id.value,
            source_tick,
        )
        return ledger, "skipped"
    rows = {row.item_kind: row for row in ledger.rows}
    for kind in give_item_kinds:
        rows[kind] = _increment(
            rows.get(kind),
            kind,
            actor_id,
            observation_tick,
            owner_id=ledger.owner_id.value,
        )
    for kind in take_item_kinds:
        rows[kind] = _increment(
            rows.get(kind),
            kind,
            counterparty_id,
            observation_tick,
            owner_id=ledger.owner_id.value,
        )
    fingerprints = (*ledger.fingerprints, fingerprint)[-_MAX_FINGERPRINTS:]
    updated = AcceptanceMemoryLedger(
        ledger.owner_id,
        rows=tuple(rows[kind] for kind in sorted(rows, key=lambda item: item.value)),
        fingerprints=fingerprints,
    )
    return updated, "accepted"


def _increment(
    previous: AcceptanceMemoryRow | None,
    kind: ItemKind,
    giver_id: str,
    tick: int,
    *,
    owner_id: str,
) -> AcceptanceMemoryRow:
    givers = () if previous is None else previous.giver_ids
    count = 0 if previous is None else previous.received_count
    if giver_id not in givers:
        givers = (*givers, giver_id)
        if len(givers) > _MAX_GIVERS:
            givers = givers[-_MAX_GIVERS:]
    row = AcceptanceMemoryRow(
        kind,
        min(_MAX_RECEIVED, count + 1),
        givers,
        tick,
    )
    _LOG.debug(
        "acceptance_memory_updated owner_id=%s item_kind=%s received_count=%s "
        "giver_count=%s tick=%s",
        owner_id,
        kind.value,
        row.received_count,
        len(row.giver_ids),
        tick,
    )
    return row


def _require_fingerprint(item: object) -> Fingerprint:
    if not isinstance(item, tuple) or len(item) != 5:
        raise TypeError("fingerprint must be a 5-tuple")
    source_tick, actor_id, counterparty_id, give_ids, take_ids = item
    if type(source_tick) is not int or isinstance(source_tick, bool) or source_tick < 0:
        raise ValueError("fingerprint source_tick must be a non-negative int")
    if type(actor_id) is not str or type(counterparty_id) is not str:
        raise TypeError("fingerprint party ids must be str")
    return (
        source_tick,
        actor_id,
        counterparty_id,
        _id_tuple(give_ids),
        _id_tuple(take_ids),
    )


def _id_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise TypeError("fingerprint item ids must be a tuple")
    copied: list[str] = []
    for item in value:
        if type(item) is not str:
            raise TypeError("fingerprint item id must be str")
        copied.append(item)
    return tuple(copied)
