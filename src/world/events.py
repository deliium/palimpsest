"""Immutable objective world events with a closed V1 detail union."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
    require_bounded_text,
)


@dataclass(frozen=True, slots=True)
class Moved:
    destination_id: EntityId
    kind: Literal["move"] = field(default="move", init=False)

    def __post_init__(self) -> None:
        if type(self.destination_id) is not EntityId:
            raise TypeError("Moved.destination_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Searched:
    target_id: EntityId | None = None
    kind: Literal["search"] = field(default="search", init=False)

    def __post_init__(self) -> None:
        if self.target_id is not None and type(self.target_id) is not EntityId:
            raise TypeError("Searched.target_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Taken:
    item_id: EntityId
    kind: Literal["take"] = field(default="take", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Taken.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Dropped:
    item_id: EntityId
    kind: Literal["drop"] = field(default="drop", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Dropped.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Given:
    recipient_id: EntityId
    item_id: EntityId
    kind: Literal["give"] = field(default="give", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Given.recipient_id must be EntityId")
        if type(self.item_id) is not EntityId:
            raise TypeError("Given.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Eaten:
    item_id: EntityId
    kind: Literal["eat"] = field(default="eat", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Eaten.item_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Drunk:
    source_id: EntityId
    kind: Literal["drink"] = field(default="drink", init=False)

    def __post_init__(self) -> None:
        if type(self.source_id) is not EntityId:
            raise TypeError("Drunk.source_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Slept:
    kind: Literal["sleep"] = field(default="sleep", init=False)


@dataclass(frozen=True, slots=True)
class Talked:
    recipient_id: EntityId
    text: str
    kind: Literal["talk"] = field(default="talk", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Talked.recipient_id must be EntityId")
        require_bounded_text("Talked.text", self.text)


@dataclass(frozen=True, slots=True)
class Asked:
    recipient_id: EntityId
    text: str
    kind: Literal["ask"] = field(default="ask", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Asked.recipient_id must be EntityId")
        require_bounded_text("Asked.text", self.text)


@dataclass(frozen=True, slots=True)
class Told:
    recipient_id: EntityId
    text: str
    kind: Literal["tell"] = field(default="tell", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Told.recipient_id must be EntityId")
        require_bounded_text("Told.text", self.text)


@dataclass(frozen=True, slots=True)
class Helped:
    target_id: EntityId
    kind: Literal["help"] = field(default="help", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Helped.target_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Attacked:
    target_id: EntityId
    kind: Literal["attack"] = field(default="attack", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Attacked.target_id must be EntityId")


@dataclass(frozen=True, slots=True)
class Fled:
    threat_id: EntityId | None = None
    kind: Literal["flee"] = field(default="flee", init=False)

    def __post_init__(self) -> None:
        if self.threat_id is not None and type(self.threat_id) is not EntityId:
            raise TypeError("Fled.threat_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Waited:
    kind: Literal["wait"] = field(default="wait", init=False)


EventDetails = (
    Moved
    | Searched
    | Taken
    | Dropped
    | Given
    | Eaten
    | Drunk
    | Slept
    | Talked
    | Asked
    | Told
    | Helped
    | Attacked
    | Fled
    | Waited
)

_DETAIL_TYPES: Final[frozenset[type]] = frozenset(
    {
        Moved,
        Searched,
        Taken,
        Dropped,
        Given,
        Eaten,
        Drunk,
        Slept,
        Talked,
        Asked,
        Told,
        Helped,
        Attacked,
        Fled,
        Waited,
    }
)


def require_event_details(value: object) -> EventDetails:
    if type(value) not in _DETAIL_TYPES:
        raise TypeError(f"unsupported event details type {type(value).__name__}")
    return value  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Objective event. Immutable and detached from the producing aggregate."""

    event_id: EventId
    request_id: RequestId
    world_id: WorldId
    revision: WorldRevision
    details: EventDetails

    def __post_init__(self) -> None:
        if type(self.event_id) is not EventId:
            raise TypeError("WorldEvent.event_id must be EventId")
        if type(self.request_id) is not RequestId:
            raise TypeError("WorldEvent.request_id must be RequestId")
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldEvent.world_id must be WorldId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldEvent.revision must be WorldRevision")
        object.__setattr__(self, "details", require_event_details(self.details))


def normalize_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    """Copy events to an immutable tuple; reject non-events and duplicates."""
    if isinstance(events, (set, frozenset)):
        raise TypeError("events must be an ordered sequence")
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise TypeError("events must be an ordered sequence")
    copied = tuple(events)
    seen: set[EventId] = set()
    for event in copied:
        if type(event) is not WorldEvent:
            raise TypeError("events entries must be WorldEvent")
        if event.event_id in seen:
            raise ValueError("events must not contain duplicate event_id values")
        seen.add(event.event_id)
    return copied
