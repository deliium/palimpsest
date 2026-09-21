"""Immutable objective world events with a closed, versioned detail union.

Compatibility matrix:
- ``EVENT_SCHEMA_AUDIT_V1`` (1): decode/export-only; never authoritative replay.
- ``EVENT_SCHEMA_REPLAY_V2`` (2): legacy replay projector; alias
  ``EVENT_SCHEMA_REPLAY_V1`` retained for call-site compatibility.
- ``EVENT_SCHEMA_REPLAY_V3`` (3): physical-rules replay with effect-complete
  payloads and explicit action/system causes; no occurrence context.
- ``EVENT_SCHEMA_REPLAY_V4`` (4): physical replay plus explicit occurrence
  context for perception audience decisions.
- ``EVENT_SCHEMA_REPLAY_V5`` (5): physical replay plus structured communication
  payloads (Talked/Asked/Told). New physical runs emit v5. Replay-v2/v3/v4
  text-only communication records decode into unreferenced structured
  utterances; new writes use only this schema.

Runs never mix replay schema versions. ``WorldEvent.target_id`` retains detail
counterparty semantics and is never treated as an occurrence location.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal

from world.communications import StructuredUtterance, confidence_band
from world.effects import (
    ActionCause,
    DeathCause,
    EventCause,
    SystemCause,
    require_event_cause,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
    require_exact_nonneg_int,
    require_ordered_unique,
    require_stable_id,
)
from world.models import LifeStatus
from world.values import WeatherCondition

EVENT_SCHEMA_AUDIT_V1: Final[int] = 1
EVENT_SCHEMA_REPLAY_V2: Final[int] = 2
EVENT_SCHEMA_REPLAY_V1: Final[int] = EVENT_SCHEMA_REPLAY_V2
EVENT_SCHEMA_REPLAY_V3: Final[int] = 3
EVENT_SCHEMA_REPLAY_V4: Final[int] = 4
EVENT_SCHEMA_REPLAY_V5: Final[int] = 5
SUPPORTED_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {
        EVENT_SCHEMA_AUDIT_V1,
        EVENT_SCHEMA_REPLAY_V2,
        EVENT_SCHEMA_REPLAY_V3,
        EVENT_SCHEMA_REPLAY_V4,
        EVENT_SCHEMA_REPLAY_V5,
    }
)
REPLAYABLE_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {
        EVENT_SCHEMA_REPLAY_V2,
        EVENT_SCHEMA_REPLAY_V3,
        EVENT_SCHEMA_REPLAY_V4,
        EVENT_SCHEMA_REPLAY_V5,
    }
)
PHYSICAL_REPLAY_EVENT_SCHEMA_VERSIONS: Final[frozenset[int]] = frozenset(
    {
        EVENT_SCHEMA_REPLAY_V3,
        EVENT_SCHEMA_REPLAY_V4,
        EVENT_SCHEMA_REPLAY_V5,
    }
)
CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION: Final[int] = EVENT_SCHEMA_REPLAY_V5


class EventValidationCode(StrEnum):
    """Stable validation codes for orchestration ERROR logs (no payloads)."""

    INVALID_SCHEMA_VERSION = "invalid_event_schema_version"
    NON_REPLAYABLE = "non_replayable_event"
    UNKNOWN_EVENT_TYPE = "unknown_event_type"
    INVALID_ORDERING = "invalid_event_ordering"
    MISSING_EFFECT_FACTS = "missing_effect_facts"
    INVALID_IDENTITY = "invalid_event_identity"
    INVALID_CAUSE = "invalid_event_cause"
    MIXED_REPLAY_SCHEMA = "mixed_replay_schema_version"
    INVALID_OCCURRENCE_CONTEXT = "invalid_occurrence_context"


@dataclass(frozen=True, slots=True)
class OccurrenceContext:
    """Event-time perception audience facts.

    Captured at emission time so live and restored engines can decide
    origin/destination witnesses, participants, affected entities, and private
    recipients without consulting a later world state. Text remains in detail
    payloads; this context only records privacy routing metadata.
    """

    origin_location_id: EntityId | None = None
    destination_location_id: EntityId | None = None
    affected_entity_ids: Sequence[EntityId] = ()
    private_recipient_ids: Sequence[EntityId] = ()

    def __post_init__(self) -> None:
        if (
            self.origin_location_id is not None
            and type(self.origin_location_id) is not EntityId
        ):
            raise TypeError(
                "OccurrenceContext.origin_location_id must be EntityId or None"
            )
        if (
            self.destination_location_id is not None
            and type(self.destination_location_id) is not EntityId
        ):
            raise TypeError(
                "OccurrenceContext.destination_location_id must be EntityId or None"
            )
        object.__setattr__(
            self,
            "affected_entity_ids",
            require_ordered_unique(
                "OccurrenceContext.affected_entity_ids",
                self.affected_entity_ids,
                item_type=EntityId,
            ),
        )
        object.__setattr__(
            self,
            "private_recipient_ids",
            require_ordered_unique(
                "OccurrenceContext.private_recipient_ids",
                self.private_recipient_ids,
                item_type=EntityId,
            ),
        )


@dataclass(frozen=True, slots=True)
class Moved:
    destination_id: EntityId
    resulting_location_id: EntityId | None = None
    fatigue_delta: float | None = None
    resulting_fatigue: float | None = None
    kind: Literal["move"] = field(default="move", init=False)

    def __post_init__(self) -> None:
        if type(self.destination_id) is not EntityId:
            raise TypeError("Moved.destination_id must be EntityId")
        if (
            self.resulting_location_id is not None
            and type(self.resulting_location_id) is not EntityId
        ):
            raise TypeError("Moved.resulting_location_id must be EntityId or None")
        _optional_finite_float("Moved.fatigue_delta", self.fatigue_delta)
        _optional_finite_float("Moved.resulting_fatigue", self.resulting_fatigue)


@dataclass(frozen=True, slots=True)
class Searched:
    target_id: EntityId | None = None
    success: bool | None = None
    created_item_id: EntityId | None = None
    extracted_quantity: float | None = None
    resulting_resource_quantity: float | None = None
    kind: Literal["search"] = field(default="search", init=False)

    def __post_init__(self) -> None:
        if self.target_id is not None and type(self.target_id) is not EntityId:
            raise TypeError("Searched.target_id must be EntityId or None")
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("Searched.success must be bool or None")
        if (
            self.created_item_id is not None
            and type(self.created_item_id) is not EntityId
        ):
            raise TypeError("Searched.created_item_id must be EntityId or None")
        _optional_finite_float("Searched.extracted_quantity", self.extracted_quantity)
        _optional_finite_float(
            "Searched.resulting_resource_quantity", self.resulting_resource_quantity
        )
        if self.success is False and self.created_item_id is not None:
            raise ValueError("failed Searched must not carry created_item_id")


@dataclass(frozen=True, slots=True)
class Taken:
    """Committed take outcome. Replay requires ``resulting_holder_id``."""

    item_id: EntityId
    resulting_holder_id: EntityId | None = None
    kind: Literal["take"] = field(default="take", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Taken.item_id must be EntityId")
        if (
            self.resulting_holder_id is not None
            and type(self.resulting_holder_id) is not EntityId
        ):
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
        if (
            self.resulting_location_id is not None
            and type(self.resulting_location_id) is not EntityId
        ):
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
        if (
            self.resulting_holder_id is not None
            and type(self.resulting_holder_id) is not EntityId
        ):
            raise TypeError("Given.resulting_holder_id must be EntityId or None")


@dataclass(frozen=True, slots=True)
class Eaten:
    item_id: EntityId
    hunger_delta: float | None = None
    resulting_hunger: float | None = None
    kind: Literal["eat"] = field(default="eat", init=False)

    def __post_init__(self) -> None:
        if type(self.item_id) is not EntityId:
            raise TypeError("Eaten.item_id must be EntityId")
        _optional_finite_float("Eaten.hunger_delta", self.hunger_delta)
        _optional_finite_float("Eaten.resulting_hunger", self.resulting_hunger)


@dataclass(frozen=True, slots=True)
class Drunk:
    source_id: EntityId
    consumed_item: bool | None = None
    quantity_delta: float | None = None
    resulting_resource_quantity: float | None = None
    thirst_delta: float | None = None
    resulting_thirst: float | None = None
    kind: Literal["drink"] = field(default="drink", init=False)

    def __post_init__(self) -> None:
        if type(self.source_id) is not EntityId:
            raise TypeError("Drunk.source_id must be EntityId")
        if self.consumed_item is not None and type(self.consumed_item) is not bool:
            raise TypeError("Drunk.consumed_item must be bool or None")
        _optional_finite_float("Drunk.quantity_delta", self.quantity_delta)
        _optional_finite_float(
            "Drunk.resulting_resource_quantity", self.resulting_resource_quantity
        )
        _optional_finite_float("Drunk.thirst_delta", self.thirst_delta)
        _optional_finite_float("Drunk.resulting_thirst", self.resulting_thirst)


@dataclass(frozen=True, slots=True)
class Slept:
    fatigue_delta: float | None = None
    resulting_fatigue: float | None = None
    kind: Literal["sleep"] = field(default="sleep", init=False)

    def __post_init__(self) -> None:
        _optional_finite_float("Slept.fatigue_delta", self.fatigue_delta)
        _optional_finite_float("Slept.resulting_fatigue", self.resulting_fatigue)


@dataclass(frozen=True, slots=True)
class Talked:
    recipient_id: EntityId
    utterance: StructuredUtterance
    kind: Literal["talk"] = field(default="talk", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Talked.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Talked.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Talked(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count}, "
            f"confidence_band="
            f"{confidence_band(self.utterance.declared.sender_confidence)!r})"
        )


@dataclass(frozen=True, slots=True)
class Asked:
    recipient_id: EntityId
    utterance: StructuredUtterance
    kind: Literal["ask"] = field(default="ask", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Asked.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Asked.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Asked(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count})"
        )


@dataclass(frozen=True, slots=True)
class Told:
    recipient_id: EntityId
    utterance: StructuredUtterance
    kind: Literal["tell"] = field(default="tell", init=False)

    def __post_init__(self) -> None:
        if type(self.recipient_id) is not EntityId:
            raise TypeError("Told.recipient_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError("Told.utterance must be StructuredUtterance")

    def __repr__(self) -> str:
        return (
            f"Told(recipient_id={self.recipient_id.value!r}, "
            f"hop_count={self.utterance.declared.hop_count})"
        )


@dataclass(frozen=True, slots=True)
class Helped:
    target_id: EntityId
    health_delta: float | None = None
    resulting_target_health: float | None = None
    helper_fatigue_delta: float | None = None
    resulting_helper_fatigue: float | None = None
    kind: Literal["help"] = field(default="help", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Helped.target_id must be EntityId")
        _optional_finite_float("Helped.health_delta", self.health_delta)
        _optional_finite_float(
            "Helped.resulting_target_health", self.resulting_target_health
        )
        _optional_finite_float("Helped.helper_fatigue_delta", self.helper_fatigue_delta)
        _optional_finite_float(
            "Helped.resulting_helper_fatigue", self.resulting_helper_fatigue
        )


@dataclass(frozen=True, slots=True)
class Attacked:
    target_id: EntityId
    hit: bool | None = None
    damage: int | None = None
    resulting_target_health: float | None = None
    kind: Literal["attack"] = field(default="attack", init=False)

    def __post_init__(self) -> None:
        if type(self.target_id) is not EntityId:
            raise TypeError("Attacked.target_id must be EntityId")
        if self.hit is not None and type(self.hit) is not bool:
            raise TypeError("Attacked.hit must be bool or None")
        if self.damage is not None and (
            isinstance(self.damage, bool) or type(self.damage) is not int
        ):
            raise TypeError("Attacked.damage must be int or None")
        _optional_finite_float(
            "Attacked.resulting_target_health", self.resulting_target_health
        )
        if self.hit is False and self.damage is not None:
            raise ValueError("missed Attacked must not carry damage")


@dataclass(frozen=True, slots=True)
class Fled:
    threat_id: EntityId | None = None
    success: bool | None = None
    destination_id: EntityId | None = None
    fatigue_delta: float | None = None
    resulting_fatigue: float | None = None
    kind: Literal["flee"] = field(default="flee", init=False)

    def __post_init__(self) -> None:
        if self.threat_id is not None and type(self.threat_id) is not EntityId:
            raise TypeError("Fled.threat_id must be EntityId or None")
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("Fled.success must be bool or None")
        if (
            self.destination_id is not None
            and type(self.destination_id) is not EntityId
        ):
            raise TypeError("Fled.destination_id must be EntityId or None")
        _optional_finite_float("Fled.fatigue_delta", self.fatigue_delta)
        _optional_finite_float("Fled.resulting_fatigue", self.resulting_fatigue)
        if self.success is False and self.destination_id is not None:
            raise ValueError("failed Fled must not carry destination_id")


@dataclass(frozen=True, slots=True)
class Waited:
    kind: Literal["wait"] = field(default="wait", init=False)


@dataclass(frozen=True, slots=True)
class WeatherChanged:
    location_id: EntityId
    condition: WeatherCondition
    kind: Literal["weather_changed"] = field(default="weather_changed", init=False)

    def __post_init__(self) -> None:
        if type(self.location_id) is not EntityId:
            raise TypeError("WeatherChanged.location_id must be EntityId")
        if type(self.condition) is not WeatherCondition:
            raise TypeError("WeatherChanged.condition must be WeatherCondition")


@dataclass(frozen=True, slots=True)
class ResourceRegenerated:
    resource_id: EntityId
    quantity_delta: float
    resulting_quantity: float
    kind: Literal["resource_regenerated"] = field(
        default="resource_regenerated", init=False
    )

    def __post_init__(self) -> None:
        if type(self.resource_id) is not EntityId:
            raise TypeError("ResourceRegenerated.resource_id must be EntityId")
        object.__setattr__(
            self,
            "quantity_delta",
            _require_finite_float(
                "ResourceRegenerated.quantity_delta", self.quantity_delta
            ),
        )
        object.__setattr__(
            self,
            "resulting_quantity",
            _require_finite_float(
                "ResourceRegenerated.resulting_quantity", self.resulting_quantity
            ),
        )


@dataclass(frozen=True, slots=True)
class NeedsApplied:
    body_id: EntityId
    resulting_hunger: float
    resulting_thirst: float
    resulting_fatigue: float
    health_delta: float
    resulting_health: float
    kind: Literal["needs_applied"] = field(default="needs_applied", init=False)

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("NeedsApplied.body_id must be EntityId")
        for name in (
            "resulting_hunger",
            "resulting_thirst",
            "resulting_fatigue",
            "health_delta",
            "resulting_health",
        ):
            object.__setattr__(
                self,
                name,
                _require_finite_float(f"NeedsApplied.{name}", getattr(self, name)),
            )


@dataclass(frozen=True, slots=True)
class ExposureApplied:
    body_id: EntityId
    ambient_celsius: float
    resulting_temperature: float
    health_delta: float
    resulting_health: float
    kind: Literal["exposure_applied"] = field(default="exposure_applied", init=False)

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("ExposureApplied.body_id must be EntityId")
        for name in (
            "ambient_celsius",
            "resulting_temperature",
            "health_delta",
            "resulting_health",
        ):
            object.__setattr__(
                self,
                name,
                _require_finite_float(f"ExposureApplied.{name}", getattr(self, name)),
            )


@dataclass(frozen=True, slots=True)
class Died:
    body_id: EntityId
    death_cause: DeathCause
    resulting_life_status: LifeStatus = LifeStatus.DEAD
    kind: Literal["died"] = field(default="died", init=False)

    def __post_init__(self) -> None:
        if type(self.body_id) is not EntityId:
            raise TypeError("Died.body_id must be EntityId")
        if type(self.death_cause) is not DeathCause:
            raise TypeError("Died.death_cause must be DeathCause")
        if type(self.resulting_life_status) is not LifeStatus:
            raise TypeError("Died.resulting_life_status must be LifeStatus")
        if self.resulting_life_status is not LifeStatus.DEAD:
            raise ValueError("Died.resulting_life_status must be DEAD")


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
    | WeatherChanged
    | ResourceRegenerated
    | NeedsApplied
    | ExposureApplied
    | Died
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
        WeatherChanged,
        ResourceRegenerated,
        NeedsApplied,
        ExposureApplied,
        Died,
    }
)


def _optional_finite_float(name: str, value: float | None) -> None:
    if value is None:
        return
    _require_finite_float(name, value)


def _require_finite_float(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite float")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite float")
    if number == 0.0:
        return 0.0
    return number


def require_event_details(value: object) -> EventDetails:
    if type(value) not in _DETAIL_TYPES:
        raise TypeError(f"unsupported event details type {type(value).__name__}")
    return value  # type: ignore[return-value]


def _payload_effect_complete(details: EventDetails, *, schema_version: int) -> bool:
    match details:
        case Taken(resulting_holder_id=None):
            return False
        case Dropped(resulting_location_id=None):
            return False
        case Given(resulting_holder_id=None):
            return False
        case Given(recipient_id=recipient_id, resulting_holder_id=holder_id):
            if holder_id != recipient_id:
                return False
        case _:
            pass
    if schema_version < EVENT_SCHEMA_REPLAY_V3:
        return True
    match details:
        case Moved() as moved:
            return (
                moved.resulting_location_id is not None
                and moved.fatigue_delta is not None
                and moved.resulting_fatigue is not None
            )
        case Searched() as searched:
            if searched.success is None:
                return False
            if searched.success:
                return (
                    searched.created_item_id is not None
                    and searched.extracted_quantity is not None
                    and searched.resulting_resource_quantity is not None
                )
            return True
        case Eaten() as eaten:
            return eaten.hunger_delta is not None and eaten.resulting_hunger is not None
        case Drunk() as drunk:
            return (
                drunk.consumed_item is not None
                and drunk.thirst_delta is not None
                and drunk.resulting_thirst is not None
            )
        case Slept() as slept:
            return (
                slept.fatigue_delta is not None and slept.resulting_fatigue is not None
            )
        case Helped() as helped:
            return (
                helped.health_delta is not None
                and helped.resulting_target_health is not None
                and helped.helper_fatigue_delta is not None
                and helped.resulting_helper_fatigue is not None
            )
        case Attacked() as attacked:
            if attacked.hit is None:
                return False
            if attacked.hit:
                return (
                    attacked.damage is not None
                    and attacked.resulting_target_health is not None
                )
            return True
        case Fled() as fled:
            if fled.success is None:
                return False
            if fled.success:
                return (
                    fled.destination_id is not None
                    and fled.fatigue_delta is not None
                    and fled.resulting_fatigue is not None
                )
            return True
        case (
            WeatherChanged()
            | ResourceRegenerated()
            | NeedsApplied()
            | ExposureApplied()
            | Died()
            | Talked()
            | Asked()
            | Told()
            | Waited()
            | Taken()
            | Dropped()
            | Given()
        ):
            return True
        case _:
            return True


def event_is_replayable(event: WorldEvent) -> bool:
    """True only for replay-schema events with effect-complete payloads."""
    if event.schema_version not in REPLAYABLE_EVENT_SCHEMA_VERSIONS:
        return False
    return _payload_effect_complete(event.details, schema_version=event.schema_version)


def require_replayable_event(event: WorldEvent) -> WorldEvent:
    """Reject legacy or under-specified events as authoritative replay input."""
    if type(event) is not WorldEvent:
        raise TypeError("require_replayable_event requires WorldEvent")
    if event.schema_version not in REPLAYABLE_EVENT_SCHEMA_VERSIONS:
        raise ValueError(EventValidationCode.NON_REPLAYABLE.value)
    if not _payload_effect_complete(event.details, schema_version=event.schema_version):
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
        case (
            Talked(recipient_id=recipient_id)
            | Asked(recipient_id=recipient_id)
            | Told(recipient_id=recipient_id)
        ):
            return recipient_id
        case Helped(target_id=target_id) | Attacked(target_id=target_id):
            return target_id
        case Fled(threat_id=threat_id):
            return threat_id
        case WeatherChanged(location_id=location_id):
            return location_id
        case ResourceRegenerated(resource_id=resource_id):
            return resource_id
        case (
            NeedsApplied(body_id=body_id)
            | ExposureApplied(body_id=body_id)
            | Died(body_id=body_id)
        ):
            return body_id
        case Slept() | Waited():
            return None
        case _:
            raise TypeError(
                f"{EventValidationCode.UNKNOWN_EVENT_TYPE.value}: "
                f"{type(details).__name__}"
            )


def request_id_for_cause(cause: EventCause) -> RequestId:
    match cause:
        case ActionCause(request_id=request_id):
            return request_id
        case SystemCause(cause_id=cause_id):
            return cause_id
        case _:
            raise TypeError(EventValidationCode.INVALID_CAUSE.value)


def actor_id_for_cause(cause: EventCause) -> EntityId | None:
    match cause:
        case ActionCause(actor_id=actor_id):
            return actor_id
        case SystemCause():
            return None
        case _:
            raise TypeError(EventValidationCode.INVALID_CAUSE.value)


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
    cause: EventCause | None = None
    occurrence: OccurrenceContext | None = None

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
        if self.cause is not None:
            cause = require_event_cause(self.cause)
            object.__setattr__(self, "cause", cause)
            if request_id_for_cause(cause) != self.request_id:
                raise ValueError(EventValidationCode.INVALID_CAUSE.value)
            expected_actor = actor_id_for_cause(cause)
            if self.actor_id != expected_actor:
                raise ValueError(EventValidationCode.INVALID_CAUSE.value)
        elif self.schema_version >= EVENT_SCHEMA_REPLAY_V3:
            raise ValueError(EventValidationCode.INVALID_CAUSE.value)
        if (
            self.occurrence is not None
            and type(self.occurrence) is not OccurrenceContext
        ):
            raise TypeError("WorldEvent.occurrence must be OccurrenceContext or None")
        if self.schema_version >= EVENT_SCHEMA_REPLAY_V4:
            if self.occurrence is None:
                raise ValueError(EventValidationCode.INVALID_OCCURRENCE_CONTEXT.value)
        elif self.occurrence is not None:
            raise ValueError(EventValidationCode.INVALID_OCCURRENCE_CONTEXT.value)
        expected_target = target_id_for_details(self.details)
        if self.target_id != expected_target:
            raise ValueError(EventValidationCode.INVALID_IDENTITY.value)
        if (
            self.schema_version in REPLAYABLE_EVENT_SCHEMA_VERSIONS
            and not _payload_effect_complete(
                self.details, schema_version=self.schema_version
            )
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
    """Construct a legacy replay-v2 objective event."""
    return WorldEvent(
        event_id=event_id,
        run_id=run_id,
        world_id=world_id,
        tick=tick,
        sequence=sequence,
        request_id=request_id,
        resulting_revision=resulting_revision,
        schema_version=EVENT_SCHEMA_REPLAY_V2,
        details=details,
        actor_id=actor_id,
        target_id=target_id_for_details(require_event_details(details)),
        cause=None,
    )


def make_physical_replayable_event(
    *,
    event_id: EventId,
    run_id: str,
    world_id: WorldId,
    tick: int,
    sequence: int,
    cause: EventCause,
    resulting_revision: WorldRevision,
    details: EventDetails,
    occurrence: OccurrenceContext,
) -> WorldEvent:
    """Construct an authoritative physical replay-v5 objective event."""
    typed_cause = require_event_cause(cause)
    if type(occurrence) is not OccurrenceContext:
        raise TypeError("occurrence must be OccurrenceContext")
    return WorldEvent(
        event_id=event_id,
        run_id=run_id,
        world_id=world_id,
        tick=tick,
        sequence=sequence,
        request_id=request_id_for_cause(typed_cause),
        resulting_revision=resulting_revision,
        schema_version=CURRENT_PHYSICAL_EVENT_SCHEMA_VERSION,
        details=details,
        actor_id=actor_id_for_cause(typed_cause),
        target_id=target_id_for_details(require_event_details(details)),
        cause=typed_cause,
        occurrence=occurrence,
    )


def build_occurrence_context(
    details: EventDetails,
    *,
    origin_location_id: EntityId | None,
    destination_location_id: EntityId | None = None,
) -> OccurrenceContext:
    """Derive event-time occurrence context from details and known locations.

    ``origin_location_id`` is the actor/body location at emission (or the
    system location for weather/regeneration). Destination is supplied for
    movement/flee success; otherwise taken from movement details when present.
    """
    typed = require_event_details(details)
    if origin_location_id is not None and type(origin_location_id) is not EntityId:
        raise TypeError("origin_location_id must be EntityId or None")
    if (
        destination_location_id is not None
        and type(destination_location_id) is not EntityId
    ):
        raise TypeError("destination_location_id must be EntityId or None")
    match typed:
        case Moved(destination_id=destination_id, resulting_location_id=resulting):
            moved_dest = destination_location_id or resulting or destination_id
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=moved_dest,
                affected_entity_ids=(),
                private_recipient_ids=(),
            )
        case Fled(destination_id=destination_id) as fled:
            fled_dest = destination_location_id
            if fled.success and destination_id is not None:
                fled_dest = destination_location_id or destination_id
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=fled_dest,
                affected_entity_ids=(),
                private_recipient_ids=(),
            )
        case (
            Talked(recipient_id=recipient_id)
            | Asked(recipient_id=recipient_id)
            | Told(recipient_id=recipient_id)
        ):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(),
                private_recipient_ids=(recipient_id,),
            )
        case Helped(target_id=target_id) | Attacked(target_id=target_id):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(target_id,),
                private_recipient_ids=(),
            )
        case (
            Died(body_id=body_id)
            | NeedsApplied(body_id=body_id)
            | ExposureApplied(body_id=body_id)
        ):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(body_id,),
                private_recipient_ids=(),
            )
        case WeatherChanged(location_id=location_id):
            return OccurrenceContext(
                origin_location_id=location_id,
                destination_location_id=None,
                affected_entity_ids=(location_id,),
                private_recipient_ids=(),
            )
        case ResourceRegenerated(resource_id=resource_id):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(resource_id,),
                private_recipient_ids=(),
            )
        case Searched(created_item_id=created_item_id, target_id=target_id):
            affected: list[EntityId] = []
            if target_id is not None:
                affected.append(target_id)
            if created_item_id is not None:
                affected.append(created_item_id)
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=tuple(affected),
                private_recipient_ids=(),
            )
        case Taken(item_id=item_id) | Dropped(item_id=item_id) | Eaten(item_id=item_id):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(item_id,),
                private_recipient_ids=(),
            )
        case Given(recipient_id=recipient_id, item_id=item_id):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(item_id, recipient_id),
                private_recipient_ids=(),
            )
        case Drunk(source_id=source_id):
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(source_id,),
                private_recipient_ids=(),
            )
        case Slept() | Waited():
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=None,
                affected_entity_ids=(),
                private_recipient_ids=(),
            )
        case _:
            return OccurrenceContext(
                origin_location_id=origin_location_id,
                destination_location_id=destination_location_id,
                affected_entity_ids=(),
                private_recipient_ids=(),
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
    schema_version = normalized[0].schema_version
    for index, event in enumerate(normalized):
        if event.run_id != run_id or event.tick != tick:
            raise ValueError(EventValidationCode.INVALID_ORDERING.value)
        if event.sequence != index:
            raise ValueError(EventValidationCode.INVALID_ORDERING.value)
        if (
            event.schema_version in REPLAYABLE_EVENT_SCHEMA_VERSIONS
            and schema_version in REPLAYABLE_EVENT_SCHEMA_VERSIONS
            and event.schema_version != schema_version
        ):
            raise ValueError(EventValidationCode.MIXED_REPLAY_SCHEMA.value)
    return normalized
