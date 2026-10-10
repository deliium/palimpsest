"""Owner-scoped interpretations of public commitment speech.

The ledger is not a contract and is not on Observation. Two owners may
store different terms for the same event. Nothing here moves items.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from agents.models import AgentId
from world.identifiers import require_exact_nonneg_int
from world.structured_commitments import (
    COMMITMENT_DUE_KINDS,
    COMMITMENT_KINDS,
    COMMITMENT_OWED_BY,
    COMMITMENT_SERVICES,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.structured_commitments"
)

MAX_OPEN_INTERPRETATIONS_LIMIT: Final[int] = 16
COMMITMENT_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "proposed",
        "accepted",
        "open",
        "partial",
        "fulfilled",
        "violated",
        "disputed",
        "forgotten",
    }
)
COMMITMENT_SANCTION_TOKENS: Final[frozenset[str]] = frozenset(
    {"none", "criticism", "shun", "retaliation_considered"}
)
_SCORE_QUANTUM: Final[float] = 1e-6


def _quantize_unit(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    quantized = round(number / _SCORE_QUANTUM) * _SCORE_QUANTUM
    return 0.0 if quantized == 0.0 else quantized


@dataclass(frozen=True, slots=True)
class CommitmentRevision:
    """Earlier terms kept when a dispute does not overwrite them."""

    tick: int
    debtor_id: str
    creditor_id: str
    kind: str
    owed_by: str
    item_kind: str
    service: str
    quantity: int
    now_item_kind: str
    due_kind: str
    due_tick: int | None
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("CommitmentRevision.tick", self.tick)
        )
        if self.status not in COMMITMENT_STATUSES:
            raise ValueError("CommitmentRevision.status")
        if type(self.quantity) is not int or self.quantity not in {1, 2, 3}:
            raise ValueError("CommitmentRevision.quantity")


@dataclass(frozen=True, slots=True)
class CommitmentInterpretation:
    """One owner's reading of a public commitment."""

    local_id: int
    source_event_ids: tuple[str, ...]
    parties: tuple[str, str]
    debtor_id: str
    creditor_id: str
    kind: str
    owed_by: str
    item_kind: str
    service: str
    quantity: int
    now_item_kind: str
    due_kind: str
    due_tick: int | None
    created_tick: int
    status: str
    now_matched: bool
    matched_quantity: int
    confidence: float
    memory_trace_ids: tuple[str, ...] = ()
    revisions: tuple[CommitmentRevision, ...] = ()
    sanction: str = "none"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "local_id",
            require_exact_nonneg_int(
                "CommitmentInterpretation.local_id", self.local_id
            ),
        )
        object.__setattr__(
            self,
            "created_tick",
            require_exact_nonneg_int(
                "CommitmentInterpretation.created_tick", self.created_tick
            ),
        )
        if (
            isinstance(self.source_event_ids, (str, bytes))
            or not isinstance(self.source_event_ids, tuple)
            or any(type(item) is not str for item in self.source_event_ids)
        ):
            raise TypeError("source_event_ids must be a tuple of str")
        if (
            not isinstance(self.parties, tuple)
            or len(self.parties) != 2
            or any(type(item) is not str for item in self.parties)
        ):
            raise TypeError("parties must be a pair of str")
        for name in (
            "debtor_id",
            "creditor_id",
            "kind",
            "owed_by",
            "item_kind",
            "service",
            "now_item_kind",
            "due_kind",
            "status",
        ):
            if type(getattr(self, name)) is not str:
                raise TypeError(f"CommitmentInterpretation.{name} must be str")
        if self.kind not in COMMITMENT_KINDS and self.kind != "unspecified":
            raise ValueError("CommitmentInterpretation.kind")
        if self.owed_by not in COMMITMENT_OWED_BY and self.owed_by != "unspecified":
            raise ValueError("CommitmentInterpretation.owed_by")
        if self.service not in COMMITMENT_SERVICES and self.service != "unspecified":
            raise ValueError("CommitmentInterpretation.service")
        if self.due_kind not in COMMITMENT_DUE_KINDS and self.due_kind != "unspecified":
            raise ValueError("CommitmentInterpretation.due_kind")
        if self.status not in COMMITMENT_STATUSES:
            raise ValueError("CommitmentInterpretation.status")
        if type(self.quantity) is not int or self.quantity not in {1, 2, 3}:
            raise ValueError("CommitmentInterpretation.quantity")
        if self.due_tick is not None:
            object.__setattr__(
                self,
                "due_tick",
                require_exact_nonneg_int(
                    "CommitmentInterpretation.due_tick", self.due_tick
                ),
            )
        if type(self.now_matched) is not bool:
            raise TypeError("now_matched must be bool")
        if (
            type(self.matched_quantity) is not int
            or isinstance(self.matched_quantity, bool)
            or self.matched_quantity < 0
            or self.matched_quantity > self.quantity
        ):
            raise ValueError("CommitmentInterpretation.matched_quantity")
        object.__setattr__(
            self,
            "confidence",
            _quantize_unit("CommitmentInterpretation.confidence", self.confidence),
        )
        if isinstance(self.memory_trace_ids, (str, bytes)) or not isinstance(
            self.memory_trace_ids, tuple
        ):
            raise TypeError("memory_trace_ids must be a tuple")
        if any(type(item) is not str for item in self.memory_trace_ids):
            raise TypeError("memory_trace_ids entries must be str")
        if isinstance(self.revisions, (str, bytes)) or not isinstance(
            self.revisions, tuple
        ):
            raise TypeError("revisions must be a tuple")
        for revision in self.revisions:
            if type(revision) is not CommitmentRevision:
                raise TypeError("revisions entries must be CommitmentRevision")
        if self.sanction not in COMMITMENT_SANCTION_TOKENS:
            raise ValueError("CommitmentInterpretation.sanction")


@dataclass(frozen=True, slots=True)
class StructuredCommitmentLedger:
    """One owner's interpretations. The cap is the spec value, not a world id."""

    owner_id: AgentId
    max_open_interpretations: int
    interpretations: tuple[CommitmentInterpretation, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise TypeError("StructuredCommitmentLedger.owner_id must be AgentId")
        if (
            type(self.max_open_interpretations) is not int
            or isinstance(self.max_open_interpretations, bool)
            or not 1 <= self.max_open_interpretations <= MAX_OPEN_INTERPRETATIONS_LIMIT
        ):
            raise ValueError("max_open_interpretations must be in [1, 16]")
        if isinstance(self.interpretations, (str, bytes)) or not isinstance(
            self.interpretations, tuple
        ):
            raise TypeError("interpretations must be a tuple")
        seen: set[int] = set()
        for row in self.interpretations:
            if type(row) is not CommitmentInterpretation:
                raise TypeError(
                    "interpretations entries must be CommitmentInterpretation"
                )
            if row.local_id in seen:
                raise ValueError("duplicate local_id")
            seen.add(row.local_id)


def empty_structured_commitments(
    owner_id: AgentId, *, max_open_interpretations: int = 8
) -> StructuredCommitmentLedger:
    """Blank owner ledger. Does not copy another owner's terms."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    ledger = StructuredCommitmentLedger(owner_id, max_open_interpretations)
    _LOG.debug(
        "commitment_ledger_updated owner_id=%s local_id=%s status=%s",
        owner_id.value,
        "-",
        "empty",
    )
    return ledger


def require_owner_structured_commitments(
    value: object | None,
    owner_id: AgentId,
    *,
    field_name: str,
) -> None:
    if value is None:
        return
    if type(value) is not StructuredCommitmentLedger:
        raise TypeError(f"{field_name} must be StructuredCommitmentLedger or None")
    if value.owner_id != owner_id:
        raise ValueError(f"{field_name} owner_id mismatch")


def replace_interpretation(
    ledger: StructuredCommitmentLedger, row: CommitmentInterpretation
) -> StructuredCommitmentLedger:
    """Replace the row with the same local id, or append it."""
    if type(ledger) is not StructuredCommitmentLedger:
        raise TypeError("ledger must be StructuredCommitmentLedger")
    if type(row) is not CommitmentInterpretation:
        raise TypeError("row must be CommitmentInterpretation")
    kept = tuple(
        item for item in ledger.interpretations if item.local_id != row.local_id
    )
    updated = replace(ledger, interpretations=(*kept, row))
    _LOG.debug(
        "commitment_ledger_updated owner_id=%s local_id=%s status=%s",
        ledger.owner_id.value,
        row.local_id,
        row.status,
    )
    return updated


def ledgers_by_owner(
    ledgers: Mapping[AgentId, StructuredCommitmentLedger],
) -> dict[str, StructuredCommitmentLedger]:
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Mapping):
        raise TypeError("ledgers must be a mapping")
    copied: dict[str, StructuredCommitmentLedger] = {}
    for owner_id, ledger in ledgers.items():
        if (
            type(owner_id) is not AgentId
            or type(ledger) is not StructuredCommitmentLedger
        ):
            raise TypeError("ledgers must map AgentId to StructuredCommitmentLedger")
        if ledger.owner_id != owner_id:
            raise ValueError("structured_commitments owner_id mismatch")
        copied[owner_id.value] = ledger
    return copied


def _fact(facts: Mapping[str, object], key: str, default: str = "unspecified") -> str:
    value = facts.get(key, default)
    if value is None:
        return default
    if type(value) is not str:
        return default
    return value


def _same_terms(row: CommitmentInterpretation, incoming: Mapping[str, object]) -> bool:
    due = incoming.get("due_tick")
    return (
        row.kind == incoming["kind"]
        and row.owed_by == incoming["owed_by"]
        and row.item_kind == incoming["item_kind"]
        and row.service == incoming["service"]
        and row.quantity == incoming["quantity"]
        and row.now_item_kind == incoming["now_item_kind"]
        and row.due_kind == incoming["due_kind"]
        and row.due_tick == due
        and row.parties == incoming["parties"]
    )


def _status_log(owner: str, local_id: int, status: str) -> None:
    _LOG.debug("commitment_status local_id=%s status=%s", local_id, status)
    if status in {"violated", "disputed", "fulfilled"}:
        _LOG.info(
            "commitment_status owner_id=%s local_id=%s status=%s",
            owner,
            local_id,
            status,
        )


def _with_status(
    ledger: StructuredCommitmentLedger,
    row: CommitmentInterpretation,
    status: str,
) -> StructuredCommitmentLedger:
    if row.status == status:
        return replace_interpretation(ledger, row)
    updated = replace(row, status=status)
    _status_log(ledger.owner_id.value, updated.local_id, status)
    return replace_interpretation(ledger, updated)


def apply_structured_commitment_update(
    ledger: StructuredCommitmentLedger,
    observation: object,
    *,
    tick: int,
) -> StructuredCommitmentLedger:
    """Fold this owner's occurrences into their ledger. No peer copy."""
    if type(ledger) is not StructuredCommitmentLedger:
        raise TypeError("ledger must be StructuredCommitmentLedger")
    occurrences = getattr(observation, "occurrences", ())
    if isinstance(occurrences, (str, bytes)) or not isinstance(occurrences, tuple):
        raise TypeError("observation.occurrences must be a tuple")
    current = ledger
    for occurrence in occurrences:
        kind = getattr(occurrence, "kind", None)
        if kind == "commitment_declared":
            current = _fold_speech(current, occurrence, tick=tick)
        elif kind == "give":
            current = _fold_give(current, occurrence)
        elif kind in {"help", "feed", "transport"}:
            current = _fold_service(current, occurrence)
    return _apply_due(current, observation, tick=tick)


def _incoming_terms(occurrence: object) -> Mapping[str, object] | None:
    facts = getattr(occurrence, "public_facts", None)
    actor = getattr(occurrence, "actor_id", None)
    other = getattr(occurrence, "other_entity_id", None)
    if not isinstance(facts, Mapping) or actor is None or other is None:
        return None
    quantity = facts.get("quantity", 1)
    if type(quantity) is not int or quantity not in {1, 2, 3}:
        quantity = 1
    due_tick = facts.get("due_tick")
    if type(due_tick) is not int:
        due_tick = None
    return {
        "kind": _fact(facts, "kind"),
        "act": _fact(facts, "act"),
        "owed_by": _fact(facts, "owed_by"),
        "item_kind": _fact(facts, "item_kind"),
        "service": _fact(facts, "service", "none"),
        "quantity": quantity,
        "now_item_kind": _fact(facts, "now_item_kind"),
        "due_kind": _fact(facts, "due_kind", "none"),
        "due_tick": due_tick,
        "parties": (actor.value, other.value),
        "actor": actor.value,
        "counterparty": other.value,
        "event_id": getattr(
            getattr(occurrence, "provenance", None), "source_event_id", None
        ),
    }


def _roles(terms: Mapping[str, object]) -> tuple[str, str]:
    if terms["owed_by"] == "self":
        return str(terms["actor"]), str(terms["counterparty"])
    return str(terms["counterparty"]), str(terms["actor"])


def _fold_speech(
    ledger: StructuredCommitmentLedger, occurrence: object, *, tick: int
) -> StructuredCommitmentLedger:
    terms = _incoming_terms(occurrence)
    if terms is None or terms["kind"] == "unspecified":
        return ledger
    act = str(terms["act"])
    if act == "propose":
        return _open_row(ledger, terms, tick=tick)
    match = _matching_row(ledger, terms)
    if act == "accept":
        if match is None:
            disputed = _party_mismatch(ledger, terms)
            if disputed is not None:
                return _dispute(ledger, disputed, terms, tick=tick)
            return _open_row(ledger, terms, tick=tick, status="accepted")
        return _with_status(ledger, match, "accepted")
    reports = {
        "report_fulfilled",
        "report_partial",
        "report_violated",
        "report_dispute",
    }
    if act in reports:
        if match is None:
            disputed = _party_mismatch(ledger, terms)
            if disputed is None:
                return ledger
            return _dispute(ledger, disputed, terms, tick=tick)
        if act == "report_fulfilled" and match.matched_quantity >= match.quantity:
            return _with_status(ledger, match, "fulfilled")
        if act == "report_partial" and 0 < match.matched_quantity < match.quantity:
            return _with_status(ledger, match, "partial")
        if act in {"report_violated", "report_dispute"}:
            return _dispute(ledger, match, terms, tick=tick)
    return ledger


def _matching_row(
    ledger: StructuredCommitmentLedger, terms: Mapping[str, object]
) -> CommitmentInterpretation | None:
    for row in ledger.interpretations:
        if row.status == "forgotten":
            continue
        if _same_terms(row, terms):
            return row
    return None


def _party_mismatch(
    ledger: StructuredCommitmentLedger, terms: Mapping[str, object]
) -> CommitmentInterpretation | None:
    for row in ledger.interpretations:
        if row.status == "forgotten" or row.parties != terms["parties"]:
            continue
        if row.kind == terms["kind"] and not _same_terms(row, terms):
            return row
    return None


def _open_row(
    ledger: StructuredCommitmentLedger,
    terms: Mapping[str, object],
    *,
    tick: int,
    status: str | None = None,
) -> StructuredCommitmentLedger:
    if len(ledger.interpretations) >= ledger.max_open_interpretations:
        _LOG.debug(
            "commitment_dropped_over_cap owner_id=%s cap=%s",
            ledger.owner_id.value,
            ledger.max_open_interpretations,
        )
        return ledger
    if status is None:
        status = (
            "open"
            if terms["kind"] == "promise" and terms["owed_by"] == "self"
            else "proposed"
        )
        if terms["due_kind"] == "if_counterpart_gives":
            status = "proposed"
    debtor, creditor = _roles(terms)
    event_id = terms["event_id"]
    source = () if event_id is None else (event_id.value,)
    local_id = 1 + max((row.local_id for row in ledger.interpretations), default=0)
    row = CommitmentInterpretation(
        local_id,
        source,
        terms["parties"],  # type: ignore[arg-type]
        debtor,
        creditor,
        str(terms["kind"]),
        str(terms["owed_by"]),
        str(terms["item_kind"]),
        str(terms["service"]),
        int(terms["quantity"]),  # type: ignore[arg-type]
        str(terms["now_item_kind"]),
        str(terms["due_kind"]),
        terms["due_tick"] if type(terms["due_tick"]) is int else None,
        tick,
        status,
        False,
        0,
        0.5,
    )
    _status_log(ledger.owner_id.value, local_id, status)
    return replace_interpretation(ledger, row)


def _dispute(
    ledger: StructuredCommitmentLedger,
    row: CommitmentInterpretation,
    terms: Mapping[str, object],
    *,
    tick: int,
) -> StructuredCommitmentLedger:
    debtor_id, creditor_id = _roles(terms)
    revision = CommitmentRevision(
        tick,
        debtor_id,
        creditor_id,
        str(terms["kind"]),
        str(terms["owed_by"]),
        str(terms["item_kind"]),
        str(terms["service"]),
        int(terms["quantity"]),  # type: ignore[arg-type]
        str(terms["now_item_kind"]),
        str(terms["due_kind"]),
        terms["due_tick"] if type(terms["due_tick"]) is int else None,
        "disputed",
    )
    updated = replace(row, revisions=(*row.revisions, revision), status="disputed")
    _status_log(ledger.owner_id.value, updated.local_id, "disputed")
    return replace_interpretation(ledger, updated)


def _fold_give(
    ledger: StructuredCommitmentLedger, occurrence: object
) -> StructuredCommitmentLedger:
    facts = getattr(occurrence, "public_facts", {})
    if not isinstance(facts, Mapping) or "item_kind" not in facts:
        return ledger
    actor = getattr(occurrence, "actor_id", None)
    other = getattr(occurrence, "other_entity_id", None)
    if actor is None or other is None:
        return ledger
    item_kind = facts.get("item_kind")
    if type(item_kind) is not str:
        return ledger
    current = ledger
    for row in ledger.interpretations:
        if row.status in {"forgotten", "fulfilled", "violated", "disputed"}:
            continue
        if actor.value != row.debtor_id or other.value != row.creditor_id:
            continue
        now_matched = row.now_matched
        matched = row.matched_quantity
        if item_kind == row.now_item_kind and row.now_item_kind != "unspecified":
            now_matched = True
        elif item_kind == row.item_kind and row.item_kind != "unspecified":
            matched = min(row.quantity, matched + 1)
        else:
            continue
        status = row.status
        if now_matched and status == "proposed":
            status = "open"
        if 0 < matched < row.quantity:
            status = "partial"
        elif matched >= row.quantity and row.item_kind != "unspecified":
            status = "fulfilled"
        updated = replace(
            row,
            now_matched=now_matched,
            matched_quantity=matched,
            status=status,
        )
        if status != row.status:
            _status_log(ledger.owner_id.value, row.local_id, status)
        current = replace_interpretation(current, updated)
    return current


def _fold_service(
    ledger: StructuredCommitmentLedger, occurrence: object
) -> StructuredCommitmentLedger:
    actor = getattr(occurrence, "actor_id", None)
    other = getattr(occurrence, "other_entity_id", None)
    kind = getattr(occurrence, "kind", None)
    if actor is None or other is None or type(kind) is not str:
        return ledger
    current = ledger
    for row in ledger.interpretations:
        if row.kind != "service_obligation" or row.service != kind:
            continue
        if row.status in {"forgotten", "fulfilled", "violated", "disputed"}:
            continue
        if actor.value != row.debtor_id or other.value != row.creditor_id:
            continue
        updated = replace(row, matched_quantity=1, status="fulfilled")
        _status_log(ledger.owner_id.value, row.local_id, "fulfilled")
        current = replace_interpretation(current, updated)
    return current


def _apply_due(
    ledger: StructuredCommitmentLedger, observation: object, *, tick: int
) -> StructuredCommitmentLedger:
    together = _colocated_ids(observation)
    current = ledger
    for row in ledger.interpretations:
        if row.status in {"forgotten", "fulfilled", "violated", "disputed"}:
            continue
        if row.due_kind == "none" or row.due_kind == "if_counterpart_gives":
            continue
        short = row.matched_quantity < row.quantity
        if (
            row.due_kind == "by_tick"
            and row.due_tick is not None
            and tick > row.due_tick
            and short
        ):
            current = _with_status(current, row, "violated")
        elif (
            row.due_kind == "when_next_colocated"
            and tick > row.created_tick
            and row.debtor_id in together
            and row.creditor_id in together
            and short
        ):
            current = _with_status(current, row, "violated")
    return current


def _colocated_ids(observation: object) -> set[str]:
    ids: set[str] = set()
    observer = getattr(observation, "observer_id", None)
    if observer is not None:
        ids.add(observer.value)
    for body in getattr(observation, "visible_bodies", ()) or ():
        entity_id = getattr(body, "entity_id", None)
        if entity_id is not None:
            ids.add(entity_id.value)
    return ids
