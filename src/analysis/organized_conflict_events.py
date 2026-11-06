# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Objective conflict rows from existing committed world events.

Rows are token-only. Detection never reads owner claims, world state, or a
ledger. No new event type or persistence surface is introduced.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organized_conflict_policy import (
    OrganizedConflictAnalysisPolicy,
    default_organized_conflict_analysis_policy,
)

__all__ = [
    "ConflictEventRow",
    "build_conflict_windows",
    "conflict_agent_token",
    "conflict_event_rows_from_events",
    "conflict_location_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.events")

_HOSTILE_EVENT_CLASSES: Final[frozenset[str]] = frozenset(
    {"attack", "structure_opposition", "death", "custody_capture"}
)
_CONFLICT_EVENT_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "attack",
        "retreat",
        "death",
        "assistance",
        "custody_capture",
        "custody_transfer",
        "structure_opposition",
        "movement",
        "co_movement",
        "contact",
        "route_denial",
    }
)


def _token(domain: str, value: object) -> str:
    raw = getattr(value, "value", value)
    payload = f"{domain}|{raw}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def conflict_agent_token(agent_id: object) -> str:
    """Hash one agent/body identity into a bounded objective token."""

    return _token("palimpsest.organized_conflict.agent.v1", agent_id)


def conflict_location_token(entity_id: object) -> str:
    """Hash one location identity into a bounded objective token."""

    return _token("palimpsest.organized_conflict.location.v1", entity_id)


@dataclass(frozen=True, slots=True)
class ConflictEventRow:
    """One token-only objective conflict row."""

    tick: int
    sequence: int
    event_class: str
    actor_token: str | None
    other_token: str | None
    success: bool | None = None
    magnitude: int = 0
    source_event_kind: str = ""
    location_token: str | None = None
    region_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.tick) is not int or self.tick < 0:
            raise TypeError("ConflictEventRow.tick must be a non-negative int")
        if type(self.sequence) is not int or self.sequence < 0:
            raise TypeError("ConflictEventRow.sequence must be a non-negative int")
        if self.event_class not in _CONFLICT_EVENT_CLASSES:
            raise ValueError("ConflictEventRow.event_class is not closed")
        for name in ("actor_token", "other_token", "location_token", "region_token"):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value):
                raise TypeError(f"ConflictEventRow.{name} must be an opaque token")
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("ConflictEventRow.success must be bool or None")
        if type(self.magnitude) is not int or self.magnitude < 0:
            raise TypeError("ConflictEventRow.magnitude must be a non-negative int")


def _details(event: object) -> object | None:
    return getattr(event, "details", None)


def _row(
    *,
    event: object,
    index: int,
    event_class: str,
    actor: object | None = None,
    other: object | None = None,
    success: bool | None = None,
    magnitude: int = 0,
    location: object | None = None,
    region: object | None = None,
    source_kind: str = "",
) -> ConflictEventRow:
    return ConflictEventRow(
        tick=getattr(event, "tick", 0),
        sequence=index,
        event_class=event_class,
        actor_token=None if actor is None else conflict_agent_token(actor),
        other_token=None if other is None else conflict_agent_token(other),
        success=success,
        magnitude=magnitude if type(magnitude) is int and magnitude >= 0 else 0,
        source_event_kind=source_kind,
        location_token=(
            None if location is None else conflict_location_token(location)
        ),
        region_token=(
            None if region is None else f"region-{conflict_location_token(region)}"
        ),
    )


def _magnitude(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 1
    return max(int(abs(value)), 1)


def conflict_event_rows_from_events(
    events: Sequence[object],
    *,
    policy: OrganizedConflictAnalysisPolicy | None = None,
) -> tuple[ConflictEventRow, ...]:
    """Map committed events to token-only conflict rows."""

    _ = policy or default_organized_conflict_analysis_policy()
    rows: list[ConflictEventRow] = []
    unknown = 0
    for index, event in enumerate(events):
        details = _details(event)
        kind = getattr(details, "kind", None)
        actor = getattr(event, "actor_id", None)
        if kind == "attack":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="attack",
                    actor=actor,
                    other=getattr(details, "target_id", None),
                    success=(
                        True
                        if getattr(details, "hit", None) is True
                        else (False if getattr(details, "hit", None) is False else None)
                    ),
                    magnitude=_magnitude(getattr(details, "damage", None)),
                    source_kind=kind,
                )
            )
        elif kind == "flee":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="retreat",
                    actor=actor,
                    other=getattr(details, "threat_id", None),
                    success=getattr(details, "success", None),
                    location=getattr(details, "destination_id", None),
                    source_kind=kind,
                )
            )
        elif kind == "died":
            death_cause = getattr(getattr(details, "death_cause", None), "value", None)
            if death_cause == "attack":
                rows.append(
                    _row(
                        event=event,
                        index=index,
                        event_class="death",
                        other=getattr(details, "body_id", None),
                        source_kind=kind,
                    )
                )
        elif kind == "help":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="assistance",
                    actor=actor,
                    other=getattr(details, "target_id", None),
                    success=True,
                    magnitude=_magnitude(getattr(details, "health_delta", None)),
                    source_kind=kind,
                )
            )
        elif kind in {"feed", "transport"}:
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="assistance",
                    actor=actor,
                    other=getattr(details, "target_id", None),
                    success=True,
                    location=getattr(details, "destination_id", None),
                    source_kind=kind,
                )
            )
        elif kind == "take":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="custody_capture",
                    actor=actor,
                    other=getattr(details, "item_id", None),
                    success=True,
                    magnitude=1,
                    source_kind=kind,
                )
            )
        elif kind == "taken_from_corpse":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="custody_capture",
                    actor=getattr(details, "resulting_holder_id", actor),
                    other=getattr(details, "item_id", None),
                    success=True,
                    magnitude=1,
                    location=getattr(details, "source_body_id", None),
                    source_kind=kind,
                )
            )
        elif kind == "give":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="custody_transfer",
                    actor=actor,
                    other=getattr(details, "recipient_id", None),
                    success=True,
                    magnitude=1,
                    source_kind=kind,
                )
            )
        elif kind == "public_good_opposed":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="structure_opposition",
                    actor=getattr(details, "actor_id", actor),
                    other=getattr(details, "project_id", None),
                    success=True,
                    magnitude=_magnitude(getattr(details, "integrity_millis", None)),
                    source_kind=kind,
                )
            )
        elif kind == "move":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="movement",
                    actor=actor,
                    location=getattr(details, "destination_id", None),
                    success=True,
                    source_kind=kind,
                )
            )
        elif kind in {"journey_started", "journey_arrived"}:
            participants = tuple(getattr(details, "participant_body_ids", ()) or ())
            for participant in participants:
                rows.append(
                    _row(
                        event=event,
                        index=index,
                        event_class="co_movement",
                        actor=participant,
                        location=getattr(details, "destination_location_id", None),
                        success=True,
                        magnitude=max(len(participants), 1),
                        source_kind=kind,
                    )
                )
        elif kind == "contact_recorded":
            rows.append(
                _row(
                    event=event,
                    index=index,
                    event_class="contact",
                    actor=actor,
                    location=getattr(details, "location_id", None),
                    success=True,
                    source_kind=kind,
                )
            )
        else:
            unknown += 1
    if unknown:
        _LOG.warning("organized_conflict_unknown_event count=%s", unknown)
    rows.sort(
        key=lambda row: (
            row.tick,
            row.sequence,
            row.event_class,
            row.actor_token or "",
            row.other_token or "",
        )
    )
    return tuple(rows)


def build_conflict_windows(
    rows: Sequence[ConflictEventRow],
    policy: OrganizedConflictAnalysisPolicy,
) -> tuple[tuple[ConflictEventRow, ...], ...]:
    """Return fixed, sorted, non-empty windows from minimum to maximum tick."""

    if not rows:
        return ()
    ordered = sorted(rows, key=lambda row: (row.tick, row.sequence, row.event_class))
    minimum = ordered[0].tick
    maximum = ordered[-1].tick
    windows: list[tuple[ConflictEventRow, ...]] = []
    start = minimum
    while start <= maximum:
        end = start + policy.window_ticks
        bucket = tuple(row for row in ordered if start <= row.tick < end)
        if bucket:
            windows.append(bucket)
        start = end
    _LOG.debug(
        "organized_conflict_objective_rows count=%s windows=%s",
        len(ordered),
        len(windows),
    )
    return tuple(windows)
