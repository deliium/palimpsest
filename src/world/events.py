"""Immutable objective world events with a closed, versioned detail union.

Replay-capable events (``EVENT_SCHEMA_REPLAY_V1``) carry effect-complete
payloads and full run/tick/sequence identity so a strict projector can rebuild
state without re-running current command rules. Legacy audit events
(``EVENT_SCHEMA_AUDIT_V1``) remain decodable for export compatibility but are
rejected as authoritative replay input when under-specified.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal

from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

EVENT_SCHEMA_AUDIT_V1: Final[int] = 1
EVENT_SCHEMA_REPLAY_V1: Final[int] = 2
SUPPORTED_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {EVENT_SCHEMA_AUDIT_V1, EVENT_SCHEMA_REPLAY_V1}
)
REPLAYABLE_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {EVENT_SCHEMA_REPLAY_V1}
)


class EventValidationCode(StrEnum):
    """Stable validation codes for orchestration ERROR logs (no payloads)."""

    INVALID_SCHEMA_VERSION = "invalid_event_schema_version"
    NON_REPLAYABLE = "non_replayable_event"
    UNKNOWN_EVENT_TYPE = "unknown_event_type"
    INVALID_ORDERING = "invalid_event_ordering"
    MISSING_EFFECT_FACTS = "missing_effect_facts"
    INVALID_IDENTITY = "invalid_event_identity"


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
    """Committed take outcome. Replay requires ``resulting_holder_id``."""

    item_id: EntityId
    resulting_holder_id: EntityId | None = None
    kind: Literal["take"] = field(default="take", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Taken.item_id must be EntityId")
        if self.resulting_holder_id is not None and type(
            self.resulting_holder_id
        ) is not EntityId:
            raise TypeError("Taken.resulting_holder_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Dropped:
    """Committed drop outcome. Replay requires ``resulting_location_id``."""

    item_id: EntityId
    resulting_location_id: EntityId | None = None
    kind: Literal["drop"] = field(default="drop", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Dropped.item_id must be EntityId")
        if self.resulting_location_id is not None and type(
            self.resulting_location_id
        ) is not EntityId:
            raise TypeError("Dropped.resulting_location_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Given:
    """Committed give outcome. Replay requires ``resulting_holder_id``."""

    recipient_id: EntityId
    item_id: EntityId
    resulting_holder_id: EntityId | None = None
    kind: Literal["give"] = field(default="give", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Given.recipient_id must be EntityId")
        if type(self.item_id) is not EntityId:
            raise TypeError("Given.item_id must be EntityId")
        if self.resulting_holder_id is not None and type(
            self.resulting_holder_id
        ) is not EntityId:
            raise TypeError("Given.resulting_holder_id must be EntityId or None")


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


def _payload_effect_complete(details: EventDetails) -> bool:
    match details:
        case Taken(resulting_holder_id=None):
            return False
        case Dropped(resulting_location_id=None):
            return False
        case Given(resulting_holder_id=None):
            return False
        case Given(recipient_id=recipient_id, resulting_holder_id=holder_id):
            return holder_id == recipient_id
        case _:
            return True


def event_is_replayable(event: WorldEvent) -> bool:
    """True only for replay-schema events with effect-complete payloads."""
    if event.schema_version not in REPLAYABLE_EVENT_SCHEMA_VERSIONS:
        return False
    return _payload_effect_complete(event.details)


def require_replayable_event(event: WorldEvent) -> WorldEvent:
    """Reject legacy or under-specified events as authoritative replay input."""
    if type(event) is not WorldEvent:
        raise TypeError("require_replayable_event requires WorldEvent")
    if event.schema_version not in REPLAYABLE_EVENT_SCHEMA_VERSIONS:
        raise ValueError(EventValidationCode.NON_REPLAYABLE.value)
    if not _payload_effect_complete(event.details):
        raise ValueError(EventValidationCode.MISSING_EFFECT_FACTS.value)
    return event


def target_id_for_details(details: EventDetails) -> EntityId | None:
    """Field applicability: optional counterparty/location/item target."""
    match details:
        case Moved(destination_id=destination_id):
            return destination_id
        case Searched(target_id=target_id):
            return target_id
        case Taken(item_id=item_id) | Dropped(item_id=item_id) | Eaten(item_id=item_id):
            return item_id
        case Given(recipient_id=recipient_id):
            return recipient_id
        case Drunk(source_id=source_id):
            return source_id
        case Talked(recipient_id=recipient_id) | Asked(
            recipient_id=recipient_id
        ) | Told(recipient_id=recipient_id):
            return recipient_id
        case Helped(target_id=target_id) | Attacked(target_id=target_id):
            return target_id
        case Fled(threat_id=threat_id):
            return threat_id
        case Slept() | Waited():
            return None
        case _:
            raise TypeError(
                f"{EventValidationCode.UNKNOWN_EVENT_TYPE.value}: "
                f"{type(details).__name__}"
            )


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """Objective event. Immutable and detached from the producing aggregate.

    ``run_id`` is an opaque validated stable string so ``world`` stays free of
    ``simulation.RunId``. ``tick`` and ``sequence`` are exact non-negative
    integers; typed ``Tick`` conversion is owned by ``simulation``.
    Canonical order is ``(run_id, tick, sequence)``.
    """

    event_id: EventId
    run_id: str
    world_id: WorldId
    tick: int
    sequence: int
    request_id: RequestId
    resulting_revision: WorldRevision
    schema_version: int
    details: EventDetails
    actor_id: EntityId | None = None
    target_id: EntityId | None = None

    def __post_init__(self) -> None:
        if type(self.event_id) is not EventId:
            raise TypeError("WorldEvent.event_id must be EventId")
        object.__setattr__(
            self, "run_id", require_stable_id("WorldEvent.run_id", self.run_id)
        )
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldEvent.world_id must be WorldId")
        object.__setattr__(
            self, "tick", require_exact_nonneg_int("WorldEvent.tick", self.tick)
        )
        object.__setattr__(
            self,
            "sequence",
            require_exact_nonneg_int("WorldEvent.sequence", self.sequence),
        )
        if type(self.request_id) is not RequestId:
            raise TypeError("WorldEvent.request_id must be RequestId")
        if type(self.resulting_revision) is not WorldRevision:
            raise TypeError("WorldEvent.resulting_revision must be WorldRevision")
        if isinstance(self.schema_version, bool) or not isinstance(
            self.schema_version, int
        ):
            raise ValueError(EventValidationCode.INVALID_SCHEMA_VERSION.value)
        if self.schema_version not in SUPPORTED_EVENT_SCHEMA_VERSIONS:
            raise ValueError(EventValidationCode.INVALID_SCHEMA_VERSION.value)
        object.__setattr__(self, "details", require_event_details(self.details))
        if self.actor_id is not None and type(self.actor_id) is not EntityId:
            raise TypeError("WorldEvent.actor_id must be EntityId or None")
        if self.target_id is not None and type(self.target_id) is not EntityId:
            raise TypeError("WorldEvent.target_id must be EntityId or None")
        expected_target = target_id_for_details(self.details)
        if self.target_id != expected_target:
            raise ValueError(EventValidationCode.INVALID_IDENTITY.value)
        if (
            self.schema_version in REPLAYABLE_EVENT_SCHEMA_VERSIONS
            and not _payload_effect_complete(self.details)
        ):
            raise ValueError(EventValidationCode.MISSING_EFFECT_FACTS.value)

    @property
    def event_type(self) -> str:
        return self.details.kind

    @property
    def revision(self) -> WorldRevision:
        """Alias for ``resulting_revision`` (legacy call-site compatibility)."""
        return self.resulting_revision


def make_replayable_event(
    *,
    event_id: EventId,
    run_id: str,
    world_id: WorldId,
    tick: int,
    sequence: int,
    request_id: RequestId,
    resulting_revision: WorldRevision,
    details: EventDetails,
    actor_id: EntityId | None,
) -> WorldEvent:
    """Construct an authoritative replay-capable objective event."""
    return WorldEvent(
        event_id=event_id,
        run_id=run_id,
        world_id=world_id,
        tick=tick,
        sequence=sequence,
        request_id=request_id,
        resulting_revision=resulting_revision,
        schema_version=EVENT_SCHEMA_REPLAY_V1,
        details=details,
        actor_id=actor_id,
        target_id=target_id_for_details(require_event_details(details)),
    )


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


def normalize_ordered_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    """Normalize and enforce contiguous ``(run_id, tick, sequence)`` order."""
    normalized = normalize_events(events)
    if not normalized:
        return normalized
    run_id = normalized[0].run_id
    tick = normalized[0].tick
    for index, event in enumerate(normalized):
        if event.run_id != run_id or event.tick != tick:
            raise ValueError(EventValidationCode.INVALID_ORDERING.value)
        if event.sequence != index:
            raise ValueError(EventValidationCode.INVALID_ORDERING.value)
    return normalized
