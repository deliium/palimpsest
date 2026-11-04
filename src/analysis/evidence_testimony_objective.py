"""Detached objective anchors and tick windows for evidence alignment.

Events are consumed as duck-typed committed values. This module never imports
``world``, an event store, an engine, cognition, or persistence, and it carries
no event body.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from analysis.evidence_testimony_contract import EvidenceAnalysisError

__all__ = [
    "EVIDENCE_MAX_WINDOWS",
    "EvidenceObjectiveAnchorKind",
    "EvidenceObjectiveAnchorRow",
    "EvidenceWindowEvidence",
    "build_evidence_windows",
    "evidence_objective_anchor_rows_from_events",
]

EVIDENCE_MAX_WINDOWS: Final[int] = 1024
_SEPARATOR: Final[str] = "\x1f"


class EvidenceObjectiveAnchorKind(StrEnum):
    """Closed objective anchor kind projected from committed history."""

    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_MODIFIED = "artifact_modified"
    ARTIFACT_MOVED = "artifact_moved"
    ARTIFACT_DESTROYED = "artifact_destroyed"
    ARTIFACT_DAMAGED = "artifact_damaged"
    ARTIFACT_COPIED = "artifact_copied"
    REPOSITORY_DEPOSITED = "repository_deposited"
    REPOSITORY_RETRIEVED = "repository_retrieved"
    REPOSITORY_MAINTAINED = "repository_maintained"
    TRANSFER = "transfer"
    HARM = "harm"
    COMMITMENT_DECLARED = "commitment_declared"
    COMMUNICATION = "communication"
    ITEM_STATE = "item_state"


def _fail(code: str) -> NoReturn:
    raise EvidenceAnalysisError(code)


def _digest(*parts: str) -> str:
    return hashlib.sha256(_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def _value(value: object) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    if type(raw) is not str or not raw:
        return None
    return raw


def _field(details: object, *names: str) -> object:
    for name in names:
        if hasattr(details, name):
            return getattr(details, name)
    return None


def _int_field(details: object, *names: str) -> int:
    value = _field(details, *names)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


@dataclass(frozen=True, slots=True)
class EvidenceObjectiveAnchorRow:
    """One detached objective anchor. No event body, request id, or owner id."""

    anchor_id: str
    kind: EvidenceObjectiveAnchorKind
    tick: int
    actor_token: str | None
    target_token: str | None
    subject_token: str | None
    quantity: int
    correlation_token: str | None

    def __post_init__(self) -> None:
        if type(self.kind) is not EvidenceObjectiveAnchorKind:
            _fail("evidence_testimony_invalid_row")
        if type(self.tick) is not int or self.tick < 0:
            _fail("evidence_testimony_invalid_row")
        if type(self.quantity) is not int or self.quantity < 0:
            _fail("evidence_testimony_invalid_row")
        expected = _anchor_id(
            self.kind,
            self.tick,
            self.actor_token,
            self.target_token,
            self.subject_token,
            self.quantity,
            self.correlation_token,
        )
        if self.anchor_id != expected:
            _fail("evidence_testimony_invalid_row")


def _anchor_id(
    kind: EvidenceObjectiveAnchorKind,
    tick: int,
    actor: str | None,
    target: str | None,
    subject: str | None,
    quantity: int,
    correlation: str | None,
) -> str:
    return (
        "evid-"
        + _digest(
            "evidence-anchor",
            kind.value,
            str(tick),
            actor or "",
            target or "",
            subject or "",
            str(quantity),
            correlation or "",
        )[:16]
    )


def _anchor(
    kind: EvidenceObjectiveAnchorKind,
    tick: int,
    *,
    actor: str | None = None,
    target: str | None = None,
    subject: str | None = None,
    quantity: int = 0,
    correlation: str | None = None,
) -> EvidenceObjectiveAnchorRow:
    return EvidenceObjectiveAnchorRow(
        anchor_id=_anchor_id(kind, tick, actor, target, subject, quantity, correlation),
        kind=kind,
        tick=tick,
        actor_token=actor,
        target_token=target,
        subject_token=subject,
        quantity=quantity,
        correlation_token=correlation,
    )


_EVENT_KINDS: Final[Mapping[str, EvidenceObjectiveAnchorKind]] = {
    "ArtifactCreated": EvidenceObjectiveAnchorKind.ARTIFACT_CREATED,
    "ArtifactModified": EvidenceObjectiveAnchorKind.ARTIFACT_MODIFIED,
    "ArtifactMoved": EvidenceObjectiveAnchorKind.ARTIFACT_MOVED,
    "ArtifactDestroyed": EvidenceObjectiveAnchorKind.ARTIFACT_DESTROYED,
    "ArtifactDamaged": EvidenceObjectiveAnchorKind.ARTIFACT_DAMAGED,
    "ArtifactCopied": EvidenceObjectiveAnchorKind.ARTIFACT_COPIED,
    "RepositoryMemberDeposited": EvidenceObjectiveAnchorKind.REPOSITORY_DEPOSITED,
    "RepositoryMemberRetrieved": EvidenceObjectiveAnchorKind.REPOSITORY_RETRIEVED,
    "RepositoryMaintained": EvidenceObjectiveAnchorKind.REPOSITORY_MAINTAINED,
    "Given": EvidenceObjectiveAnchorKind.TRANSFER,
    "Taken": EvidenceObjectiveAnchorKind.TRANSFER,
    "Attacked": EvidenceObjectiveAnchorKind.HARM,
    "CommitmentDeclared": EvidenceObjectiveAnchorKind.COMMITMENT_DECLARED,
    "Talked": EvidenceObjectiveAnchorKind.COMMUNICATION,
    "Asked": EvidenceObjectiveAnchorKind.COMMUNICATION,
    "Told": EvidenceObjectiveAnchorKind.COMMUNICATION,
    "ItemStored": EvidenceObjectiveAnchorKind.ITEM_STATE,
    "Dropped": EvidenceObjectiveAnchorKind.ITEM_STATE,
}


def _communication_subject(details: object) -> str | None:
    utterance = _field(details, "utterance")
    declared = getattr(utterance, "declared", None)
    return _value(getattr(declared, "communication_id", None))


def evidence_objective_anchor_rows_from_events(
    events: Iterable[object],
    entity_to_agent: Mapping[str, str],
) -> tuple[EvidenceObjectiveAnchorRow, ...]:
    """Project the whitelisted committed events into detached objective anchors."""

    rows: list[EvidenceObjectiveAnchorRow] = []
    for event in events:
        details = getattr(event, "details", None)
        kind = _EVENT_KINDS.get(type(details).__name__)
        if kind is None:
            continue
        tick = getattr(event, "tick", None)
        if type(tick) is not int or tick < 0:
            tick = _int_field(details, "tick")
        correlation = _value(getattr(event, "event_id", None))
        actor = _value(
            _field(
                details,
                "actor_id",
                "author_id",
                "creator_id",
                "giver_id",
                "taker_id",
                "attacker_id",
                "speaker_id",
                "owner_id",
            )
        )
        target = _value(
            _field(
                details,
                "target_id",
                "recipient_id",
                "listener_id",
                "location_id",
                "repository_id",
                "counterparty_id",
                "holder_id",
            )
        )
        subject = _value(
            _field(
                details,
                "artifact_id",
                "item_id",
                "member_id",
                "commitment_id",
                "subject_token",
            )
        )
        if kind is EvidenceObjectiveAnchorKind.COMMUNICATION:
            subject = _communication_subject(details)
        quantity = _int_field(details, "quantity", "amount")
        if kind is EvidenceObjectiveAnchorKind.ARTIFACT_DESTROYED:
            target = None
        actor_token = None if actor is None else entity_to_agent.get(actor, actor)
        target_token = None if target is None else entity_to_agent.get(target, target)
        if subject is None and kind is not EvidenceObjectiveAnchorKind.HARM:
            continue
        rows.append(
            _anchor(
                kind,
                tick,
                actor=actor_token,
                target=target_token,
                subject=subject,
                quantity=quantity,
                correlation=correlation,
            )
        )
    unique = {row.anchor_id: row for row in rows}
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class EvidenceWindowEvidence:
    """One detached tick window. Empty windows are explicitly partial."""

    window_index: int
    start_tick: int
    end_tick: int
    source_count: int
    testimony_count: int
    item_count: int
    contradiction_count: int
    evaluation_count: int
    objective_anchor_count: int
    partial: bool


def build_evidence_windows(
    rows: object,
    *,
    window_ticks: int = 100,
    objective_rows: Sequence[EvidenceObjectiveAnchorRow] = (),
) -> tuple[EvidenceWindowEvidence, ...]:
    """Aggregate row and anchor counts per tick window, capped at 1024 windows."""

    if type(window_ticks) is not int or window_ticks <= 0:
        _fail("evidence_testimony_invalid_input")
    ticks: list[int] = []
    collections = (
        getattr(rows, "sources", ()),
        getattr(rows, "testimony", ()),
        getattr(rows, "items", ()),
        getattr(rows, "contradictions", ()),
        getattr(rows, "evaluations", ()),
    )
    for collection in collections:
        ticks.extend(row.tick for row in collection)
    ticks.extend(row.tick for row in objective_rows)
    if not ticks:
        return ()
    start = (min(ticks) // window_ticks) * window_ticks
    end = max(ticks)
    windows: list[EvidenceWindowEvidence] = []
    index = 0
    cursor = start
    while cursor <= end and index < EVIDENCE_MAX_WINDOWS:
        stop = cursor + window_ticks - 1
        source_count = sum(1 for row in collections[0] if cursor <= row.tick <= stop)
        testimony_count = sum(1 for row in collections[1] if cursor <= row.tick <= stop)
        item_count = sum(1 for row in collections[2] if cursor <= row.tick <= stop)
        contradiction_count = sum(
            1 for row in collections[3] if cursor <= row.tick <= stop
        )
        evaluation_count = sum(
            1 for row in collections[4] if cursor <= row.tick <= stop
        )
        anchor_count = sum(1 for row in objective_rows if cursor <= row.tick <= stop)
        windows.append(
            EvidenceWindowEvidence(
                window_index=index,
                start_tick=cursor,
                end_tick=stop,
                source_count=source_count,
                testimony_count=testimony_count,
                item_count=item_count,
                contradiction_count=contradiction_count,
                evaluation_count=evaluation_count,
                objective_anchor_count=anchor_count,
                partial=(
                    source_count
                    + testimony_count
                    + item_count
                    + contradiction_count
                    + evaluation_count
                    + anchor_count
                    == 0
                ),
            )
        )
        index += 1
        cursor += window_ticks
    return tuple(windows)
