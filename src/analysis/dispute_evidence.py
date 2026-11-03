"""Bounded detached dispute objective anchors and tick windows.

Objective anchors are researcher-only projections of committed events. They are
never imported by cognition, prompts, memory, world state, or observer
semantics, and they carry no raw payload, prompt, or hidden actor identity.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, cast

from analysis.dispute_contract import (
    DISPUTE_MAX_WINDOWS,
    DisputeAnalysisError,
    DisputeCoverage,
)
from analysis.disputes import DisputeHarvestRows

__all__ = [
    "DisputeObjectiveAnchorKind",
    "DisputeObjectiveAnchorRow",
    "DisputeWindowEvidence",
    "build_dispute_windows",
    "dispute_objective_anchor_rows_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_evidence")

_ANCHOR_NAMESPACE: Final[str] = "dispute-objective-anchor"


class DisputeObjectiveAnchorKind(StrEnum):
    """Closed researcher-only objective anchor vocabulary."""

    ITEM_TRANSFER = "item_transfer"
    RESOURCE_TAKEN = "resource_taken"
    HARM = "harm"
    COMMITMENT_DECLARATION = "commitment_declaration"
    EXCHANGE_COMPLETION = "exchange_completion"
    RECORD_CREATION = "record_creation"
    REPOSITORY_ENTRY = "repository_entry"
    OTHER = "other"


_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    member.value for member in DisputeObjectiveAnchorKind
)


def _fail(code: str = "dispute_invalid_row") -> None:
    raise DisputeAnalysisError(code)


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail()
    return cast(str, value)


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail()
    return cast(int, value)


def _entity_token(value: object) -> str | None:
    if value is None:
        return None
    token = getattr(value, "value", value)
    if token is None:
        return None
    if not isinstance(token, str) or not token:
        _fail()
    return cast(str, token)


def _first(values: object) -> str | None:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        _fail()
    items = sorted(
        token
        for token in (_entity_token(item) for item in cast("Sequence[object]", values))
        if token
    )
    return items[0] if items else None


def _anchor_digest(
    kind: str,
    tick: int,
    actor_id: str,
    target_id: str | None,
    item_token: str | None,
    quantity: int,
) -> str:
    material = "\x1f".join(
        (
            _ANCHOR_NAMESPACE,
            kind,
            str(tick),
            actor_id,
            target_id or "-",
            item_token or "-",
            str(quantity),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DisputeObjectiveAnchorRow:
    """One aggregate-ready researcher-only objective anchor."""

    reference_id: str
    kind: DisputeObjectiveAnchorKind
    tick: int
    actor_id: str
    target_id: str | None
    item_token: str | None
    quantity: int
    event_kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference_id", _text(self.reference_id))
        if type(self.kind) is not DisputeObjectiveAnchorKind:
            _fail()
        object.__setattr__(self, "tick", _count(self.tick))
        object.__setattr__(self, "actor_id", _text(self.actor_id))
        if self.target_id is not None:
            object.__setattr__(self, "target_id", _text(self.target_id))
        if self.item_token is not None:
            object.__setattr__(self, "item_token", _text(self.item_token))
        object.__setattr__(self, "quantity", _count(self.quantity))
        object.__setattr__(self, "event_kind", _text(self.event_kind))
        if self.reference_id != _anchor_digest(
            self.kind.value,
            self.tick,
            self.actor_id,
            self.target_id,
            self.item_token,
            self.quantity,
        ):
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeWindowEvidence:
    """One complete deterministic tick bucket of detached dispute evidence."""

    start_tick: int
    end_tick: int
    owner_count: int
    case_count: int
    claim_count: int
    testimony_count: int
    evidence_count: int
    objective_anchor_count: int
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        start, end = _count(self.start_tick), _count(self.end_tick)
        if end < start:
            _fail()
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick", end)
        for name in (
            "owner_count",
            "case_count",
            "claim_count",
            "testimony_count",
            "evidence_count",
            "objective_anchor_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if type(self.coverage) is not DisputeCoverage:
            _fail()


def _mapped_anchor(
    *,
    kind: DisputeObjectiveAnchorKind,
    event_kind: str,
    tick: int,
    actor_entity: object,
    target_entity: object,
    item_entity: object,
    quantity: object,
    entity_to_agent: Mapping[str, str],
    target_is_agent: bool = True,
) -> DisputeObjectiveAnchorRow | None:
    actor_token = _entity_token(actor_entity)
    if actor_token is None:
        return None
    actor_id = entity_to_agent.get(actor_token)
    if actor_id is None:
        return None
    target_token = _entity_token(target_entity)
    target_id: str | None = None
    if target_token is not None:
        if target_is_agent:
            target_id = entity_to_agent.get(target_token)
            if target_id is None:
                return None
        else:
            target_id = target_token.lower()
    item_token = _entity_token(item_entity)
    if item_token is not None:
        item_token = item_token.lower()
    if isinstance(quantity, bool):
        count = 0
    elif type(quantity) is int and quantity >= 0:
        count = quantity
    else:
        count = 0
    return DisputeObjectiveAnchorRow(
        reference_id=_anchor_digest(
            kind.value, tick, actor_id, target_id, item_token, count
        ),
        kind=kind,
        tick=tick,
        actor_id=actor_id,
        target_id=target_id,
        item_token=item_token,
        quantity=count,
        event_kind=event_kind,
    )


def dispute_objective_anchor_rows_from_events(
    events: Sequence[object],
    *,
    entity_to_agent: Mapping[str, str],
) -> tuple[DisputeObjectiveAnchorRow, ...]:
    """Project committed events into closed, content-addressed anchor rows."""

    if not isinstance(entity_to_agent, Mapping):
        raise TypeError("entity_to_agent must be a Mapping")
    rows: list[DisputeObjectiveAnchorRow] = []
    for event in events:
        details = getattr(event, "details", event)
        event_kind = getattr(details, "kind", None) or getattr(event, "kind", None)
        if not isinstance(event_kind, str) or not event_kind:
            continue
        tick = getattr(event, "tick", None)
        if isinstance(tick, bool) or type(tick) is not int or tick < 0:
            continue
        anchor: DisputeObjectiveAnchorRow | None = None
        if event_kind == "give":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.ITEM_TRANSFER,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(event, "actor_id", None),
                target_entity=getattr(details, "recipient_id", None),
                item_entity=getattr(details, "item_id", None),
                quantity=getattr(details, "quantity", 1),
                entity_to_agent=entity_to_agent,
            )
        elif event_kind == "take":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.RESOURCE_TAKEN,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(event, "actor_id", None),
                target_entity=getattr(details, "resulting_holder_id", None),
                item_entity=getattr(details, "item_id", None),
                quantity=getattr(details, "quantity", 1),
                entity_to_agent=entity_to_agent,
            )
        elif event_kind == "attack":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.HARM,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(event, "actor_id", None),
                target_entity=getattr(details, "target_id", None)
                or getattr(event, "target_id", None),
                item_entity=None,
                quantity=getattr(details, "damage", 0),
                entity_to_agent=entity_to_agent,
            )
        elif event_kind == "commitment_declared":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.COMMITMENT_DECLARATION,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(details, "actor_id", None)
                or getattr(event, "actor_id", None),
                target_entity=getattr(details, "counterparty_id", None),
                item_entity=getattr(details, "item_kind", None),
                quantity=getattr(details, "quantity", 0),
                entity_to_agent=entity_to_agent,
            )
        elif event_kind == "exchange_completed":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.EXCHANGE_COMPLETION,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(details, "actor_id", None)
                or getattr(event, "actor_id", None),
                target_entity=getattr(details, "counterparty_id", None),
                item_entity=_first(getattr(details, "give_item_kinds", ())),
                quantity=len(tuple(getattr(details, "give_item_ids", ()) or ())),
                entity_to_agent=entity_to_agent,
            )
        elif event_kind in ("artifact_created", "artifact_modified"):
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.RECORD_CREATION,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(details, "author_id", None)
                or getattr(event, "actor_id", None),
                target_entity=getattr(details, "artifact_id", None),
                item_entity=None,
                quantity=1,
                entity_to_agent=entity_to_agent,
                target_is_agent=False,
            )
        elif event_kind == "item_stored":
            anchor = _mapped_anchor(
                kind=DisputeObjectiveAnchorKind.REPOSITORY_ENTRY,
                event_kind=event_kind,
                tick=tick,
                actor_entity=getattr(event, "actor_id", None),
                target_entity=getattr(details, "structure_id", None),
                item_entity=getattr(details, "consumed_item_id", None),
                quantity=getattr(details, "resulting_stored_quantity", 0),
                entity_to_agent=entity_to_agent,
                target_is_agent=False,
            )
        if anchor is None:
            continue
        rows.append(anchor)
    deduped: dict[str, DisputeObjectiveAnchorRow] = {}
    for row in rows:
        deduped.setdefault(row.reference_id, row)
    ordered = tuple(
        deduped[key]
        for key in sorted(
            deduped,
            key=lambda key: (
                deduped[key].tick,
                deduped[key].kind.value,
                deduped[key].actor_id,
                deduped[key].target_id or "",
                deduped[key].item_token or "",
                key,
            ),
        )
    )
    _LOG.debug("dispute_objective_anchors count=%s", len(ordered))
    return ordered


def _case_overlaps(row: object, start: int, end: int) -> bool:
    return (
        getattr(row, "first_tick", 0) <= end and getattr(row, "last_tick", 0) >= start
    )


def _claim_overlaps(row: object, start: int, end: int) -> bool:
    return (
        getattr(row, "first_tick", 0) <= end and getattr(row, "last_tick", 0) >= start
    )


def build_dispute_windows(
    rows: DisputeHarvestRows,
    *,
    window_ticks: int = 100,
    objective_rows: Sequence[DisputeObjectiveAnchorRow] = (),
) -> tuple[DisputeWindowEvidence, ...]:
    """Group rows into complete, deterministic tick windows.

    A window without dispute evidence or an objective anchor remains explicit
    and is marked ``partial``; the builder never invents a missing tick, case,
    or claim.
    """

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    if isinstance(window_ticks, bool) or type(window_ticks) is not int:
        _fail()
    if window_ticks < 1:
        _fail()
    if isinstance(objective_rows, (str, bytes)) or not isinstance(
        objective_rows, Sequence
    ):
        raise TypeError("objective_rows must be a Sequence")
    anchors = tuple(objective_rows)
    ticks: list[int] = []
    for case in rows.cases:
        ticks.extend((case.first_tick, case.last_tick))
    for claim in rows.claims:
        ticks.extend((claim.first_tick, claim.last_tick))
    for testimony_row in rows.testimony:
        ticks.append(testimony_row.tick)
    for evidence_row in rows.evidence:
        ticks.append(evidence_row.tick)
    for resolution in rows.resolutions:
        ticks.extend((resolution.first_tick, resolution.last_tick))
    for anchor in anchors:
        ticks.append(anchor.tick)
    if not ticks:
        return ()
    starts = list(range(0, max(ticks) + 1, window_ticks))
    if len(starts) > DISPUTE_MAX_WINDOWS:
        starts = starts[-DISPUTE_MAX_WINDOWS:]
        _LOG.warning("dispute_window_trimmed window_count=%s", len(starts))
    windows: list[DisputeWindowEvidence] = []
    for start in starts:
        end = start + window_ticks - 1
        cases = tuple(row for row in rows.cases if _case_overlaps(row, start, end))
        claims = tuple(row for row in rows.claims if _claim_overlaps(row, start, end))
        testimony = tuple(row for row in rows.testimony if start <= row.tick <= end)
        evidence = tuple(row for row in rows.evidence if start <= row.tick <= end)
        resolutions = tuple(
            row for row in rows.resolutions if _case_overlaps(row, start, end)
        )
        window_anchors = tuple(
            anchor for anchor in anchors if start <= anchor.tick <= end
        )
        present = bool(
            cases or claims or testimony or evidence or resolutions or window_anchors
        )
        owners = (
            {row.owner_id for row in cases}
            | {row.owner_id for row in claims}
            | {row.owner_id for row in testimony}
            | {row.owner_id for row in evidence}
            | {row.owner_id for row in resolutions}
        )
        coverage = DisputeCoverage(
            observed=1 if present else 0,
            expected=1,
            partial=not present,
        )
        windows.append(
            DisputeWindowEvidence(
                start_tick=start,
                end_tick=end,
                owner_count=len(owners),
                case_count=len(cases),
                claim_count=len(claims),
                testimony_count=len(testimony),
                evidence_count=len(evidence),
                objective_anchor_count=len(window_anchors),
                coverage=coverage,
            )
        )
    if any(window.coverage.partial for window in windows):
        _LOG.warning(
            "dispute_window_partial window_count=%s partial_count=%s",
            len(windows),
            sum(1 for window in windows if window.coverage.partial),
        )
    return tuple(windows)
