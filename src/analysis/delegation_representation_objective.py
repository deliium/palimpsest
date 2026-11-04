"""Detached objective speech and action anchors for representation alignment.

Events are consumed as duck-typed committed values. This module never imports
``world``, ``agents``, an event store, an engine, cognition, or persistence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, NoReturn

from analysis.delegation_representation_contract import RepresentationAnalysisError

__all__ = [
    "REPRESENTATION_MAX_WINDOWS",
    "RepresentationObjectiveAnchorKind",
    "RepresentationObjectiveAnchorRow",
    "RepresentationWindowEvidence",
    "build_representation_windows",
    "representation_objective_anchor_rows_from_events",
]

REPRESENTATION_MAX_WINDOWS: Final[int] = 1024
_SEPARATOR: Final[str] = "\x1f"


class RepresentationObjectiveAnchorKind(StrEnum):
    """Closed objective anchor kind projected from committed history."""

    COMMUNICATION = "communication"
    TRANSFER = "transfer"
    HARM = "harm"
    COMMITMENT_DECLARED = "commitment_declared"


def _fail(code: str) -> NoReturn:
    raise RepresentationAnalysisError(code)


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
class RepresentationObjectiveAnchorRow:
    """One detached objective anchor. No event body, request id, or owner id."""

    anchor_id: str
    kind: RepresentationObjectiveAnchorKind
    tick: int
    actor_token: str | None
    target_token: str | None
    subject_token: str | None
    quantity: int
    correlation_token: str | None

    def __post_init__(self) -> None:
        if type(self.kind) is not RepresentationObjectiveAnchorKind:
            _fail("representation_invalid_row")
        if type(self.tick) is not int or self.tick < 0:
            _fail("representation_invalid_row")
        if type(self.quantity) is not int or self.quantity < 0:
            _fail("representation_invalid_row")
        if self.anchor_id != _anchor_id(
            self.kind,
            self.tick,
            self.actor_token,
            self.target_token,
            self.subject_token,
            self.quantity,
            self.correlation_token,
        ):
            _fail("representation_invalid_row")


def _anchor_id(
    kind: RepresentationObjectiveAnchorKind,
    tick: int,
    actor: str | None,
    target: str | None,
    subject: str | None,
    quantity: int,
    correlation: str | None,
) -> str:
    return (
        "rep-"
        + _digest(
            "representation-anchor",
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
    kind: RepresentationObjectiveAnchorKind,
    tick: int,
    *,
    actor: str | None = None,
    target: str | None = None,
    subject: str | None = None,
    quantity: int = 0,
    correlation: str | None = None,
) -> RepresentationObjectiveAnchorRow:
    return RepresentationObjectiveAnchorRow(
        anchor_id=_anchor_id(kind, tick, actor, target, subject, quantity, correlation),
        kind=kind,
        tick=tick,
        actor_token=actor,
        target_token=target,
        subject_token=subject,
        quantity=quantity,
        correlation_token=correlation,
    )


_EVENT_KINDS: Final[Mapping[str, RepresentationObjectiveAnchorKind]] = {
    "Talked": RepresentationObjectiveAnchorKind.COMMUNICATION,
    "Asked": RepresentationObjectiveAnchorKind.COMMUNICATION,
    "Told": RepresentationObjectiveAnchorKind.COMMUNICATION,
    "Given": RepresentationObjectiveAnchorKind.TRANSFER,
    "Taken": RepresentationObjectiveAnchorKind.TRANSFER,
    "Attacked": RepresentationObjectiveAnchorKind.HARM,
    "CommitmentDeclared": RepresentationObjectiveAnchorKind.COMMITMENT_DECLARED,
}


def _communication_subject(details: object) -> str | None:
    utterance = _field(details, "utterance")
    declared = getattr(utterance, "declared", None)
    return _value(getattr(declared, "communication_id", None))


def representation_objective_anchor_rows_from_events(
    events: Iterable[object],
    entity_to_agent: Mapping[str, str],
) -> tuple[RepresentationObjectiveAnchorRow, ...]:
    """Project whitelisted committed events into detached anchors."""

    rows: list[RepresentationObjectiveAnchorRow] = []
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
                "giver_id",
                "taker_id",
                "attacker_id",
                "speaker_id",
            )
        )
        target = _value(
            _field(
                details, "target_id", "recipient_id", "listener_id", "counterparty_id"
            )
        )
        subject = _value(_field(details, "item_id", "commitment_id", "subject_token"))
        if kind is RepresentationObjectiveAnchorKind.COMMUNICATION:
            subject = _communication_subject(details)
        actor_token = None if actor is None else entity_to_agent.get(actor, actor)
        target_token = None if target is None else entity_to_agent.get(target, target)
        if subject is None and kind is not RepresentationObjectiveAnchorKind.HARM:
            continue
        rows.append(
            _anchor(
                kind,
                tick,
                actor=actor_token,
                target=target_token,
                subject=subject,
                quantity=_int_field(details, "quantity", "amount"),
                correlation=correlation,
            )
        )
    unique = {row.anchor_id: row for row in rows}
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class RepresentationWindowEvidence:
    """One detached tick window. Empty windows are explicitly partial."""

    window_index: int
    start_tick: int
    end_tick: int
    mandate_count: int
    position_count: int
    revocation_count: int
    conflict_count: int
    objective_anchor_count: int
    partial: bool


def build_representation_windows(
    rows: object,
    *,
    window_ticks: int = 100,
    objective_rows: Sequence[RepresentationObjectiveAnchorRow] = (),
) -> tuple[RepresentationWindowEvidence, ...]:
    """Aggregate row and anchor counts per tick window, capped at 1024."""

    if type(window_ticks) is not int or window_ticks <= 0:
        _fail("representation_analysis_invalid_input")
    mandates = tuple(getattr(rows, "mandates", ()))
    positions = tuple(getattr(rows, "positions", ()))
    revocations = tuple(getattr(rows, "revocations", ()))
    conflicts = tuple(getattr(rows, "conflicts", ()))
    ticks: list[int] = [row.start_tick for row in mandates]
    ticks.extend(row.tick for row in positions)
    ticks.extend(row.tick for row in revocations)
    ticks.extend(row.tick for row in conflicts)
    ticks.extend(row.tick for row in objective_rows)
    if not ticks:
        return ()
    start = (min(ticks) // window_ticks) * window_ticks
    end = max(ticks)
    windows: list[RepresentationWindowEvidence] = []
    index = 0
    cursor = start
    while cursor <= end and index < REPRESENTATION_MAX_WINDOWS:
        stop = cursor + window_ticks - 1
        mandate_count = sum(1 for row in mandates if cursor <= row.start_tick <= stop)
        position_count = sum(1 for row in positions if cursor <= row.tick <= stop)
        revocation_count = sum(1 for row in revocations if cursor <= row.tick <= stop)
        conflict_count = sum(1 for row in conflicts if cursor <= row.tick <= stop)
        anchor_count = sum(1 for row in objective_rows if cursor <= row.tick <= stop)
        windows.append(
            RepresentationWindowEvidence(
                window_index=index,
                start_tick=cursor,
                end_tick=stop,
                mandate_count=mandate_count,
                position_count=position_count,
                revocation_count=revocation_count,
                conflict_count=conflict_count,
                objective_anchor_count=anchor_count,
                partial=(
                    mandate_count
                    + position_count
                    + revocation_count
                    + conflict_count
                    + anchor_count
                    == 0
                ),
            )
        )
        index += 1
        cursor += window_ticks
    return tuple(windows)
