# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Deterministic physical-use extraction from committed events.

Rows are counts and closed classifications only. They never assert an owner, a
controller, a title, or a country. Missing location or actor data is skipped and
recorded as partial coverage, never guessed.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.borders_policy import BordersAnalysisPolicy

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.events")

BORDER_ACTOR_PREFIX: Final[str] = "bactor-"
BORDER_LOCATION_PREFIX: Final[str] = "bloc-"

_PRESENCE_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "moved",
        "journey_started",
        "journey_arrived",
        "journey_ended",
        "contact_recorded",
    }
)
_USE_EVENTS: Final[frozenset[str]] = frozenset(
    {
        "search",
        "take",
        "taken_from_corpse",
        "resource_harvested",
        "item_stored",
        "sleep",
        "structure_built",
        "structure_repaired",
        "project_contributed",
        "public_good_benefit",
        "exchange_completed",
    }
)
_HOSTILE_EVENTS: Final[frozenset[str]] = frozenset(
    {"attack", "flee", "died", "public_good_opposed"}
)
_ASSISTANCE_EVENTS: Final[frozenset[str]] = frozenset({"help", "feed", "transport"})
_STRUCTURE_EVENTS: Final[frozenset[str]] = frozenset(
    {"structure_built", "structure_repaired"}
)


def _token(prefix: str, value: object) -> str:
    text = value if type(value) is str else getattr(value, "value", None)
    if type(text) is not str or not text:
        raise ValueError("token: invalid_identifier")
    return f"{prefix}{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"


def border_agent_token(value: object) -> str:
    """Opaque actor token. Never returns a raw ``AgentId`` or ``EntityId``."""
    return _token(BORDER_ACTOR_PREFIX, value)


def border_location_token(value: object) -> str:
    """Opaque location token. Never returns a raw ``EntityId``."""
    return _token(BORDER_LOCATION_PREFIX, value)


@dataclass(frozen=True, slots=True)
class PhysicalUseEvent:
    tick: int
    location_token: str
    actor_token: str
    kind: str
    action_code: str
    source_event_token: str

    def __post_init__(self) -> None:
        if type(self.tick) is not int or self.tick < 0:
            raise ValueError("tick: invalid_tick")
        for name in ("location_token", "actor_token", "source_event_token"):
            if type(getattr(self, name)) is not str or not getattr(self, name):
                raise ValueError(f"{name}: invalid_identifier")
        if self.kind not in {"presence", "use", "hostile", "assistance", "structure"}:
            raise ValueError("kind: unknown_kind")


@dataclass(frozen=True, slots=True)
class BorderPhysicalRow:
    location_token: str
    window_start: int
    window_end: int
    actor_count: int
    action_count: int
    hostile_count: int
    assistance_count: int
    presence_ticks: int
    classification: str

    def __post_init__(self) -> None:
        for name in (
            "window_start",
            "window_end",
            "actor_count",
            "action_count",
            "hostile_count",
            "assistance_count",
            "presence_ticks",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name}: invalid_count")
        if self.window_end < self.window_start:
            raise ValueError("window_end: invalid_order")
        if self.classification not in {
            "unoccupied",
            "transient",
            "repeated_use",
            "shared_use",
            "contested_use",
        }:
            raise ValueError("classification: unknown_classification")


def _event_kind(action_code: str) -> str | None:
    if action_code in _PRESENCE_EVENTS:
        return "presence"
    if action_code in _STRUCTURE_EVENTS:
        return "structure"
    if action_code in _USE_EVENTS:
        return "use"
    if action_code in _HOSTILE_EVENTS:
        return "hostile"
    if action_code in _ASSISTANCE_EVENTS:
        return "assistance"
    return None


def _as_entity_id(value: object) -> object | None:
    if value is None:
        return None
    if type(value).__name__ != "EntityId":
        return None
    return value


def _location_for(event: object, action_code: str) -> object | None:
    details = getattr(event, "details", None)
    if action_code == "moved":
        value = _as_entity_id(getattr(details, "destination_id", None))
        if value is not None:
            return value
    if action_code == "journey_started":
        journey = getattr(details, "journey", None)
        value = _as_entity_id(getattr(journey, "origin_location_id", None))
        if value is not None:
            return value
    if action_code in {"journey_arrived", "journey_ended"}:
        value = _as_entity_id(getattr(details, "destination_location_id", None))
        if value is not None:
            return value
    if action_code == "contact_recorded":
        value = _as_entity_id(getattr(details, "location_id", None))
        if value is not None:
            return value
    occurrence = getattr(event, "occurrence", None)
    for name in (
        "destination_location_id",
        "origin_location_id",
    ):
        value = _as_entity_id(getattr(occurrence, name, None))
        if value is not None:
            return value
    return None


def _actor_for(event: object, action_code: str) -> object | None:
    value = _as_entity_id(getattr(event, "actor_id", None))
    if value is not None:
        return value
    details = getattr(event, "details", None)
    if action_code == "died":
        value = _as_entity_id(getattr(details, "body_id", None))
        if value is not None:
            return value
    for name in ("participant_body_ids",):
        items = getattr(details, name, None)
        if (
            isinstance(items, Sequence)
            and not isinstance(items, (str, bytes))
            and items
        ):
            first = _as_entity_id(items[0])
            if first is not None:
                return first
    return None


def extract_physical_events(
    committed_events: Sequence[object],
) -> tuple[tuple[PhysicalUseEvent, ...], bool]:
    """Extract rows and report whether any event was partially skipped."""
    events: list[PhysicalUseEvent] = []
    partial = False
    if isinstance(committed_events, (str, bytes)) or not isinstance(
        committed_events, Sequence
    ):
        raise TypeError("committed_events must be a sequence")
    for event in committed_events:
        details = getattr(event, "details", None)
        action_code = getattr(details, "kind", None)
        if type(action_code) is not str:
            partial = True
            continue
        kind = _event_kind(action_code)
        if kind is None:
            continue
        tick = getattr(event, "tick", None)
        if type(tick) is not int or tick < 0:
            partial = True
            continue
        location = _location_for(event, action_code)
        actor = _actor_for(event, action_code)
        if location is None or actor is None:
            partial = True
            continue
        source = getattr(event, "event_id", None)
        source_value = getattr(source, "value", None)
        if type(source_value) is not str or not source_value:
            source_value = f"{tick}:{action_code}"
        events.append(
            PhysicalUseEvent(
                tick=tick,
                location_token=border_location_token(location),
                actor_token=border_agent_token(actor),
                kind=kind,
                action_code=action_code,
                source_event_token=_token("bevent-", source_value),
            )
        )
    events.sort(
        key=lambda item: (
            item.tick,
            item.action_code,
            item.actor_token,
            item.source_event_token,
        )
    )
    return tuple(events), partial


def _classification(
    *,
    actor_count: int,
    action_count: int,
    hostile_count: int,
    policy: BordersAnalysisPolicy,
) -> str:
    if hostile_count > 0:
        return "contested_use"
    if actor_count >= policy.min_distinct_actors:
        return "shared_use"
    if action_count >= policy.min_use_actions:
        return "repeated_use"
    if action_count > 0:
        return "transient"
    return "unoccupied"


def harvest_physical_rows(
    committed_events: Sequence[object],
    *,
    policy: BordersAnalysisPolicy,
) -> tuple[BorderPhysicalRow, ...]:
    """One row per observed location and fixed six-tick window."""
    events, _partial = extract_physical_events(committed_events)
    window = policy.physical_window_ticks
    grouped: dict[tuple[str, int], dict[str, object]] = {}
    for event in events:
        window_start = event.tick - (event.tick % window)
        key = (event.location_token, window_start)
        bucket = grouped.setdefault(
            key,
            {
                "actors": set(),
                "actions": 0,
                "hostile": 0,
                "assistance": 0,
                "presence_ticks": set(),
            },
        )
        bucket["actors"].add(event.actor_token)  # type: ignore[union-attr]
        bucket["actions"] = int(bucket["actions"]) + 1  # type: ignore[arg-type]
        if event.kind == "hostile":
            bucket["hostile"] = int(bucket["hostile"]) + 1  # type: ignore[arg-type]
        if event.kind == "assistance":
            bucket["assistance"] = int(bucket["assistance"]) + 1  # type: ignore[arg-type]
        if event.kind == "presence":
            bucket["presence_ticks"].add(event.tick)  # type: ignore[union-attr]
    rows: list[BorderPhysicalRow] = []
    for (location_token, window_start), bucket in sorted(grouped.items()):
        actor_count = len(bucket["actors"])  # type: ignore[arg-type]
        action_count = int(bucket["actions"])  # type: ignore[arg-type]
        hostile_count = int(bucket["hostile"])  # type: ignore[arg-type]
        assistance_count = int(bucket["assistance"])  # type: ignore[arg-type]
        presence_ticks = len(bucket["presence_ticks"])  # type: ignore[arg-type]
        rows.append(
            BorderPhysicalRow(
                location_token=location_token,
                window_start=window_start,
                window_end=window_start + window - 1,
                actor_count=actor_count,
                action_count=action_count,
                hostile_count=hostile_count,
                assistance_count=assistance_count,
                presence_ticks=presence_ticks,
                classification=_classification(
                    actor_count=actor_count,
                    action_count=action_count,
                    hostile_count=hostile_count,
                    policy=policy,
                ),
            )
        )
    _LOG.debug(
        "borders_physical_rows rows=%s windows=%s coverage=%s",
        len(rows),
        len(grouped),
        "partial" if _partial else "observed",
    )
    return tuple(rows)


def physical_rows_summary(
    rows: Sequence[BorderPhysicalRow],
) -> Mapping[str, int]:
    counts: dict[str, int] = {
        "row_count": 0,
        "location_count": 0,
        "actor_count": 0,
        "action_count": 0,
        "hostile_count": 0,
    }
    locations: set[str] = set()
    for row in rows:
        if type(row) is not BorderPhysicalRow:
            raise TypeError("rows: invalid_item")
        counts["row_count"] += 1
        locations.add(row.location_token)
        counts["actor_count"] += row.actor_count
        counts["action_count"] += row.action_count
        counts["hostile_count"] += row.hostile_count
    counts["location_count"] = len(locations)
    return counts


__all__ = [
    "BORDER_ACTOR_PREFIX",
    "BORDER_LOCATION_PREFIX",
    "BorderPhysicalRow",
    "PhysicalUseEvent",
    "border_agent_token",
    "border_location_token",
    "extract_physical_events",
    "harvest_physical_rows",
    "physical_rows_summary",
]
