"""Deeply immutable agent-facing observations.

Perception field access matrix (documented for tests and projectors):

===========================  =====================
Field / projection           Access
===========================  =====================
self physiology / inventory  ALWAYS_SELF
hour, day_phase, visibility  ALWAYS_SELF
weather_condition            ALWAYS_SELF
current location (id/name)   ALWAYS_SELF
adjacent exits               ALWAYS_SELF
held inventory item details  ALWAYS_SELF
ground items (local)         VISIBILITY_GATED (≥0.5)
resources (local quantity)   VISIBILITY_GATED (≥0.5)
other bodies (coarse)        VISIBILITY_GATED (≥0.5)
public occurrence facts      VISIBILITY_GATED or PARTICIPANT_ONLY
participant occurrence detail PARTICIPANT_ONLY
communication payload          RECIPIENT_ONLY (+ sender)
location capacities/shelter  OMITTED
resource max / regeneration  OMITTED
other-agent inventory/needs  OMITTED
remote weather / topology    OMITTED
request / system cause IDs   OMITTED
===========================  =====================

Observations never invent facts, treat communication as truth, or distort
memory. Provenance is narrow: source kind plus tick/event correlation only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from world._freeze import freeze_mapping, require_non_empty
from world.communications import StructuredUtterance
from world.identifiers import (
    EntityId,
    EventId,
    WorldId,
    WorldRevision,
    require_exact_nonneg_int,
)
from world.models import (
    AgentBody,
    LifeStatus,
    PhysicalRules,
    default_physical_rules,
)
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)

__all__ = [
    "CONTENT_VISIBILITY_THRESHOLD",
    "PERCEPTION_FIELD_ACCESS",
    "CoarseHealth",
    "Observation",
    "ObservationAudienceRole",
    "ObservationContext",
    "ObservationFieldAccess",
    "ObservationProvenance",
    "ObservationSourceKind",
    "ObservedCommunication",
    "ObservedItem",
    "ObservedItemPlacement",
    "ObservedLocation",
    "ObservedOccurrence",
    "ObservedResource",
    "ObservedSelf",
    "VisibleBody",
    "VisibleExit",
    "coarse_health_for",
    "detached_mapping",
    "observed_self_from_body",
]

CONTENT_VISIBILITY_THRESHOLD = 0.5


class ObservationFieldAccess(StrEnum):
    """Closed access classes for agent-facing observation fields."""

    ALWAYS_SELF = "always_self"
    VISIBILITY_GATED = "visibility_gated"
    PARTICIPANT_ONLY = "participant_only"
    RECIPIENT_ONLY = "recipient_only"
    OMITTED = "omitted"


PERCEPTION_FIELD_ACCESS: Mapping[str, ObservationFieldAccess] = {
    "self": ObservationFieldAccess.ALWAYS_SELF,
    "hour": ObservationFieldAccess.ALWAYS_SELF,
    "day_phase": ObservationFieldAccess.ALWAYS_SELF,
    "visibility": ObservationFieldAccess.ALWAYS_SELF,
    "weather_condition": ObservationFieldAccess.ALWAYS_SELF,
    "location": ObservationFieldAccess.ALWAYS_SELF,
    "exits": ObservationFieldAccess.ALWAYS_SELF,
    "held_items": ObservationFieldAccess.ALWAYS_SELF,
    "ground_items": ObservationFieldAccess.VISIBILITY_GATED,
    "resources": ObservationFieldAccess.VISIBILITY_GATED,
    "visible_bodies": ObservationFieldAccess.VISIBILITY_GATED,
    "occurrences_public": ObservationFieldAccess.VISIBILITY_GATED,
    "occurrences_participant": ObservationFieldAccess.PARTICIPANT_ONLY,
    "communications": ObservationFieldAccess.RECIPIENT_ONLY,
    "location_capacities": ObservationFieldAccess.OMITTED,
    "resource_regeneration": ObservationFieldAccess.OMITTED,
    "resource_maximum": ObservationFieldAccess.OMITTED,
    "other_inventory": ObservationFieldAccess.OMITTED,
    "other_physiology": ObservationFieldAccess.OMITTED,
    "remote_weather": ObservationFieldAccess.OMITTED,
    "remote_topology": ObservationFieldAccess.OMITTED,
    "request_ids": ObservationFieldAccess.OMITTED,
    "system_cause_ids": ObservationFieldAccess.OMITTED,
}


class ObservationSourceKind(StrEnum):
    """Closed provenance source kinds exposed to cognition."""

    WORLD_STATE = "world_state"
    OCCURRENCE = "occurrence"
    COMMUNICATION = "communication"


class ObservationAudienceRole(StrEnum):
    """Audience role used when redacting an occurrence for one observer."""

    ACTOR = "actor"
    TARGET = "target"
    WITNESS = "witness"
    BYSTANDER = "bystander"


class ObservedItemPlacement(StrEnum):
    """Placement visible to the observer without exposing foreign holder IDs."""

    HELD_BY_SELF = "held_by_self"
    GROUND_HERE = "ground_here"


class CoarseHealth(StrEnum):
    """Limited health band exposed for other visible bodies."""

    DEAD = "dead"
    CRITICAL = "critical"
    INJURED = "injured"
    STABLE = "stable"


def detached_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    """Return a deeply immutable copy detached from the caller's containers."""
    return freeze_mapping(value)


def _copy_models(
    name: str, values: Sequence[object], *, model_type: type
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for value in copied:
        if type(value) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


def coarse_health_for(body: AgentBody) -> CoarseHealth:
    """Map authoritative physiology to a coarse visible health band."""
    if type(body) is not AgentBody:
        raise TypeError("coarse_health_for requires AgentBody")
    if body.life_status is LifeStatus.DEAD or body.health.value <= 0.0:
        return CoarseHealth.DEAD
    if body.health.value <= 25.0:
        return CoarseHealth.CRITICAL
    if body.health.value <= 75.0:
        return CoarseHealth.INJURED
    return CoarseHealth.STABLE


@dataclass(frozen=True, slots=True)
class ObservationProvenance:
    """Narrow source correlation useful for cognition and deduplication.

    Must not carry request IDs, system cause IDs, hidden actor/target
    identities, global event counts, or raw replay payloads.
    """

    source_kind: ObservationSourceKind
    source_tick: int
    source_event_id: EventId | None = None

    def __post_init__(self) -> None:
        if type(self.source_kind) is not ObservationSourceKind:
            raise TypeError(
                "ObservationProvenance.source_kind must be ObservationSourceKind"
            )
        object.__setattr__(
            self,
            "source_tick",
            require_exact_nonneg_int(
                "ObservationProvenance.source_tick", self.source_tick
            ),
        )
        if (
            self.source_event_id is not None
            and type(self.source_event_id) is not EventId
        ):
            raise TypeError(
                "ObservationProvenance.source_event_id must be EventId or None"
            )
        if (
            self.source_kind is ObservationSourceKind.WORLD_STATE
            and self.source_event_id is not None
        ):
            raise ValueError(
                "ObservationProvenance.WORLD_STATE must not carry source_event_id"
            )
        if (
            self.source_kind
            in (
                ObservationSourceKind.OCCURRENCE,
                ObservationSourceKind.COMMUNICATION,
            )
            and self.source_event_id is None
        ):
            raise ValueError(
                "ObservationProvenance occurrence/communication requires "
                "source_event_id"
            )


@dataclass(frozen=True, slots=True)
class VisibleExit:
    """Adjacent destination identity and name only."""

    destination_id: EntityId
    name: str

    def __post_init__(self) -> None:
        if type(self.destination_id) is not EntityId:
            raise TypeError("VisibleExit.destination_id must be EntityId")
        require_non_empty("VisibleExit.name", self.name)


@dataclass(frozen=True, slots=True)
class VisibleBody:
    """Other-body projection without inventory or exact physiology."""

    entity_id: EntityId
    life_status: LifeStatus
    coarse_health: CoarseHealth

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("VisibleBody.entity_id must be EntityId")
        if type(self.life_status) is not LifeStatus:
            raise TypeError("VisibleBody.life_status must be LifeStatus")
        if type(self.coarse_health) is not CoarseHealth:
            raise TypeError("VisibleBody.coarse_health must be CoarseHealth")
        if (
            self.life_status is LifeStatus.DEAD
            and self.coarse_health is not CoarseHealth.DEAD
        ):
            raise ValueError("dead VisibleBody requires CoarseHealth.DEAD")
        if (
            self.life_status is LifeStatus.ALIVE
            and self.coarse_health is CoarseHealth.DEAD
        ):
            raise ValueError("living VisibleBody cannot be CoarseHealth.DEAD")


@dataclass(frozen=True, slots=True)
class ObservedLocation:
    """Current location without capacity, shelter, or environment policy fields."""

    entity_id: EntityId
    name: str

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedLocation.entity_id must be EntityId")
        require_non_empty("ObservedLocation.name", self.name)


@dataclass(frozen=True, slots=True)
class ObservedItem:
    """Portable item visible to the observer without foreign placement IDs."""

    entity_id: EntityId
    name: str
    kind: ItemKind
    load: ItemLoad
    placement: ObservedItemPlacement

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedItem.entity_id must be EntityId")
        require_non_empty("ObservedItem.name", self.name)
        if type(self.kind) is not ItemKind:
            raise TypeError("ObservedItem.kind must be ItemKind")
        if type(self.load) is not ItemLoad:
            raise TypeError("ObservedItem.load must be ItemLoad")
        if type(self.placement) is not ObservedItemPlacement:
            raise TypeError("ObservedItem.placement must be ObservedItemPlacement")


@dataclass(frozen=True, slots=True)
class ObservedResource:
    """Local resource quantity without maximum or regeneration policy."""

    entity_id: EntityId
    name: str
    kind: ResourceKind
    quantity: float
    unit: str

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedResource.entity_id must be EntityId")
        require_non_empty("ObservedResource.name", self.name)
        if type(self.kind) is not ResourceKind:
            raise TypeError("ObservedResource.kind must be ResourceKind")
        require_non_empty("ObservedResource.unit", self.unit)
        if isinstance(self.quantity, bool) or not isinstance(
            self.quantity, (int, float)
        ):
            raise TypeError("ObservedResource.quantity must be a finite float")
        number = float(self.quantity)
        if number != number or number in (float("inf"), float("-inf")):
            raise ValueError("ObservedResource.quantity must be finite")
        if number < 0.0:
            raise ValueError("ObservedResource.quantity must be non-negative")
        object.__setattr__(self, "quantity", 0.0 if number == 0.0 else number)


@dataclass(frozen=True, slots=True)
class ObservedSelf:
    """Exact self physiology available to the owning observer only."""

    entity_id: EntityId
    location_id: EntityId
    health: Health
    hunger: Hunger
    thirst: Thirst
    fatigue: Fatigue
    temperature: TemperatureCelsius
    inventory: Sequence[EntityId]
    life_status: LifeStatus
    carry_capacity: CarryCapacity

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedSelf.entity_id must be EntityId")
        if type(self.location_id) is not EntityId:
            raise TypeError("ObservedSelf.location_id must be EntityId")
        for field_name, expected, value in (
            ("health", Health, self.health),
            ("hunger", Hunger, self.hunger),
            ("thirst", Thirst, self.thirst),
            ("fatigue", Fatigue, self.fatigue),
            ("temperature", TemperatureCelsius, self.temperature),
            ("carry_capacity", CarryCapacity, self.carry_capacity),
        ):
            if type(value) is not expected:
                raise TypeError(
                    f"ObservedSelf.{field_name} must be {expected.__name__}"
                )
        if type(self.life_status) is not LifeStatus:
            raise TypeError("ObservedSelf.life_status must be LifeStatus")
        if isinstance(self.inventory, (set, frozenset, Mapping)):
            raise TypeError("ObservedSelf.inventory must be an ordered sequence")
        if isinstance(self.inventory, (str, bytes, bytearray)) or not isinstance(
            self.inventory, Sequence
        ):
            raise TypeError("ObservedSelf.inventory must be an ordered sequence")
        inventory = tuple(self.inventory)
        seen: set[EntityId] = set()
        for item_id in inventory:
            if type(item_id) is not EntityId:
                raise TypeError("ObservedSelf.inventory entries must be EntityId")
            if item_id in seen:
                raise ValueError("ObservedSelf.inventory must not contain duplicates")
            seen.add(item_id)
        object.__setattr__(self, "inventory", inventory)
        if self.life_status is LifeStatus.ALIVE and self.health.value <= 0.0:
            raise ValueError("LifeStatus.ALIVE requires positive health")
        if self.life_status is LifeStatus.DEAD and self.health.value != 0.0:
            raise ValueError("LifeStatus.DEAD requires zero health")


def observed_self_from_body(body: AgentBody) -> ObservedSelf:
    """Project an authoritative body into the explicit self observation DTO."""
    if type(body) is not AgentBody:
        raise TypeError("observed_self_from_body requires AgentBody")
    return ObservedSelf(
        entity_id=body.entity_id,
        location_id=body.location_id,
        health=body.health,
        hunger=body.hunger,
        thirst=body.thirst,
        fatigue=body.fatigue,
        temperature=body.temperature,
        inventory=body.inventory,
        life_status=body.life_status,
        carry_capacity=body.carry_capacity,
    )


@dataclass(frozen=True, slots=True)
class ObservedOccurrence:
    """Redacted occurrence facts for one observer audience role.

    Partial fields are optional; absent means unknown to this audience, never
    a fabricated default. Does not assert communication truth.
    """

    provenance: ObservationProvenance
    kind: str
    audience_role: ObservationAudienceRole
    actor_id: EntityId | None = None
    other_entity_id: EntityId | None = None
    destination_id: EntityId | None = None
    success: bool | None = None
    public_facts: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.provenance) is not ObservationProvenance:
            raise TypeError(
                "ObservedOccurrence.provenance must be ObservationProvenance"
            )
        if self.provenance.source_kind is not ObservationSourceKind.OCCURRENCE:
            raise ValueError(
                "ObservedOccurrence.provenance.source_kind must be OCCURRENCE"
            )
        require_non_empty("ObservedOccurrence.kind", self.kind)
        if type(self.audience_role) is not ObservationAudienceRole:
            raise TypeError(
                "ObservedOccurrence.audience_role must be ObservationAudienceRole"
            )
        for field_name, value in (
            ("actor_id", self.actor_id),
            ("other_entity_id", self.other_entity_id),
            ("destination_id", self.destination_id),
        ):
            if value is not None and type(value) is not EntityId:
                raise TypeError(
                    f"ObservedOccurrence.{field_name} must be EntityId or None"
                )
        if self.success is not None and type(self.success) is not bool:
            raise TypeError("ObservedOccurrence.success must be bool or None")
        if not isinstance(self.public_facts, Mapping):
            raise TypeError("ObservedOccurrence.public_facts must be a mapping")
        object.__setattr__(self, "public_facts", freeze_mapping(self.public_facts))


@dataclass(frozen=True, slots=True)
class ObservedCommunication:
    """Delivered utterance claim with source provenance.

    Semantics: entity A communicated structured content to entity B. Perception
    does not assert that the content is true and does not create memories or
    beliefs. ``speaker_id``, ``listener_id``, and ``provenance`` are
    world-verified delivery fields; ``utterance.declared`` is speaker testimony.
    """

    provenance: ObservationProvenance
    speaker_id: EntityId
    listener_id: EntityId
    utterance: StructuredUtterance
    action_kind: Literal["talk", "ask", "tell"]

    def __post_init__(self) -> None:
        if type(self.provenance) is not ObservationProvenance:
            raise TypeError(
                "ObservedCommunication.provenance must be ObservationProvenance"
            )
        if self.provenance.source_kind is not ObservationSourceKind.COMMUNICATION:
            raise ValueError(
                "ObservedCommunication.provenance.source_kind must be COMMUNICATION"
            )
        if type(self.speaker_id) is not EntityId:
            raise TypeError("ObservedCommunication.speaker_id must be EntityId")
        if type(self.listener_id) is not EntityId:
            raise TypeError("ObservedCommunication.listener_id must be EntityId")
        if type(self.utterance) is not StructuredUtterance:
            raise TypeError(
                "ObservedCommunication.utterance must be StructuredUtterance"
            )
        if self.action_kind not in {"talk", "ask", "tell"}:
            raise ValueError("ObservedCommunication.action_kind: unsupported")

    def __repr__(self) -> str:
        event_id = (
            None
            if self.provenance.source_event_id is None
            else self.provenance.source_event_id.value
        )
        return (
            f"ObservedCommunication(speaker_id={self.speaker_id.value!r}, "
            f"listener_id={self.listener_id.value!r}, "
            f"action_kind={self.action_kind!r}, "
            f"hop_count={self.utterance.declared.hop_count}, "
            f"event_id={event_id!r})"
        )


@dataclass(frozen=True, slots=True)
class ObservationContext:
    """World-owned perception inputs derived from tick and physical rules."""

    tick: int
    physical_rules: PhysicalRules = field(default_factory=default_physical_rules)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ObservationContext.tick", self.tick),
        )
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("ObservationContext.physical_rules must be PhysicalRules")

    @property
    def hour(self) -> int:
        return self.physical_rules.hour_for_tick(self.tick)

    @property
    def day_phase(self) -> DayPhase:
        return self.physical_rules.day_phase_for_tick(self.tick)


@dataclass(frozen=True, slots=True)
class Observation:
    """Immutable tick-scoped agent observation with redacted projections only."""

    world_id: WorldId
    observer_id: EntityId
    revision: WorldRevision
    tick: int = 0
    self_body: ObservedSelf | None = None
    locations: Sequence[ObservedLocation] = field(default_factory=tuple)
    items: Sequence[ObservedItem] = field(default_factory=tuple)
    resources: Sequence[ObservedResource] = field(default_factory=tuple)
    exits: Sequence[VisibleExit] = field(default_factory=tuple)
    visible_bodies: Sequence[VisibleBody] = field(default_factory=tuple)
    occurrences: Sequence[ObservedOccurrence] = field(default_factory=tuple)
    communications: Sequence[ObservedCommunication] = field(default_factory=tuple)
    hour: int | None = None
    day_phase: DayPhase | None = None
    visibility: float | None = None
    weather_condition: WeatherCondition | None = None

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("Observation.world_id must be WorldId")
        if type(self.observer_id) is not EntityId:
            raise TypeError("Observation.observer_id must be EntityId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("Observation.revision must be WorldRevision")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("Observation.tick", self.tick),
        )
        if self.self_body is not None and type(self.self_body) is not ObservedSelf:
            raise TypeError("Observation.self_body must be ObservedSelf or None")
        object.__setattr__(
            self,
            "locations",
            _copy_models(
                "Observation.locations", self.locations, model_type=ObservedLocation
            ),
        )
        object.__setattr__(
            self,
            "items",
            _copy_models("Observation.items", self.items, model_type=ObservedItem),
        )
        object.__setattr__(
            self,
            "resources",
            _copy_models(
                "Observation.resources", self.resources, model_type=ObservedResource
            ),
        )
        object.__setattr__(
            self,
            "exits",
            _copy_models("Observation.exits", self.exits, model_type=VisibleExit),
        )
        object.__setattr__(
            self,
            "visible_bodies",
            _copy_models(
                "Observation.visible_bodies",
                self.visible_bodies,
                model_type=VisibleBody,
            ),
        )
        object.__setattr__(
            self,
            "occurrences",
            _copy_models(
                "Observation.occurrences",
                self.occurrences,
                model_type=ObservedOccurrence,
            ),
        )
        object.__setattr__(
            self,
            "communications",
            _copy_models(
                "Observation.communications",
                self.communications,
                model_type=ObservedCommunication,
            ),
        )
        if self.hour is not None:
            if isinstance(self.hour, bool) or type(self.hour) is not int:
                raise TypeError("Observation.hour must be int or None")
            if self.hour < 0:
                raise ValueError("Observation.hour must be non-negative")
        if self.day_phase is not None and type(self.day_phase) is not DayPhase:
            raise TypeError("Observation.day_phase must be DayPhase or None")
        if self.visibility is not None:
            if isinstance(self.visibility, bool) or not isinstance(
                self.visibility, (int, float)
            ):
                raise TypeError("Observation.visibility must be float or None")
            number = float(self.visibility)
            if number < 0.0 or number > 1.0:
                raise ValueError("Observation.visibility must be in [0.0, 1.0]")
            object.__setattr__(self, "visibility", 0.0 if number == 0.0 else number)
        if (
            self.weather_condition is not None
            and type(self.weather_condition) is not WeatherCondition
        ):
            raise TypeError(
                "Observation.weather_condition must be WeatherCondition or None"
            )
        if self.self_body is not None and self.self_body.entity_id != self.observer_id:
            raise ValueError("Observation.self_body must match observer_id")
        _validate_ordered_ids(
            "Observation.locations",
            tuple(location.entity_id for location in self.locations),
        )
        _validate_ordered_ids(
            "Observation.items",
            tuple(item.entity_id for item in self.items),
        )
        _validate_ordered_ids(
            "Observation.resources",
            tuple(resource.entity_id for resource in self.resources),
        )
        _validate_ordered_ids(
            "Observation.visible_bodies",
            tuple(body.entity_id for body in self.visible_bodies),
        )
        _validate_occurrence_sources(self.occurrences, self.communications, self.tick)
        for item in self.items:
            if item.placement is ObservedItemPlacement.HELD_BY_SELF:
                if self.self_body is None:
                    raise ValueError(
                        "Observation held item requires ObservedSelf inventory"
                    )
                if item.entity_id not in self.self_body.inventory:
                    raise ValueError(
                        "Observation held item must appear in ObservedSelf.inventory"
                    )


def _validate_ordered_ids(name: str, values: tuple[EntityId, ...]) -> None:
    if values != tuple(sorted(values, key=lambda entity: entity.value)):
        raise ValueError(f"{name} must be sorted by EntityId")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must not contain duplicate EntityId values")


def _validate_occurrence_sources(
    occurrences: Sequence[ObservedOccurrence],
    communications: Sequence[ObservedCommunication],
    observation_tick: int,
) -> None:
    seen_event_ids: set[EventId] = set()
    for occurrence in occurrences:
        event_id = occurrence.provenance.source_event_id
        if event_id is None:
            raise ValueError("Observation occurrence requires source_event_id")
        if event_id in seen_event_ids:
            raise ValueError("Observation occurrence source_event_id must be unique")
        seen_event_ids.add(event_id)
        if occurrence.provenance.source_tick >= observation_tick:
            raise ValueError(
                "Observation occurrences must come from a prior committed tick"
            )
    for communication in communications:
        event_id = communication.provenance.source_event_id
        if event_id is None:
            raise ValueError("Observation communication requires source_event_id")
        if event_id in seen_event_ids:
            raise ValueError(
                "Observation communication source_event_id must be unique across "
                "occurrences and communications"
            )
        seen_event_ids.add(event_id)
        if communication.provenance.source_tick >= observation_tick:
            raise ValueError(
                "Observation communications must come from a prior committed tick"
            )
