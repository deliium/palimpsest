"""Deeply immutable agent-facing observations.

Perception field access matrix (documented for tests and projectors):

===========================  =====================
Field / projection           Access
===========================  =====================
self physiology / inventory  ALWAYS_SELF
hour, day_phase, visibility  ALWAYS_SELF
weather_condition            ALWAYS_SELF
season / band / hazards      ALWAYS_SELF (present only when dynamics are on)
current location (id/name)   ALWAYS_SELF
adjacent exits               ALWAYS_SELF
held inventory item details  ALWAYS_SELF
ground items (local)         VISIBILITY_GATED (≥0.5)
resources (local quantity)   VISIBILITY_GATED (≥0.5)
structures (local)           VISIBILITY_GATED (≥0.5)
artifacts (ground local)       VISIBILITY_GATED (≥0.5)
artifacts (held by self)       ALWAYS_SELF
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
from types import MappingProxyType
from typing import Literal

from world._freeze import freeze_mapping, require_non_empty
from world.artifacts import ArtifactContent, ArtifactKind, require_artifact_content
from world.communications import StructuredUtterance
from world.environment import HazardKind, Season, TemperatureBand
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
from world.production import StructureKind
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
    "ObservedArtifact",
    "ObservedCommunication",
    "ObservedDependencyNeed",
    "ObservedDependencyNeeds",
    "ObservedItem",
    "ObservedItemPlacement",
    "ObservedKinshipVisible",
    "ObservedLifecycle",
    "ObservedLocation",
    "ObservedOccurrence",
    "ObservedResource",
    "ObservedSelf",
    "ObservedStructure",
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
    "season": ObservationFieldAccess.ALWAYS_SELF,
    "temperature_band": ObservationFieldAccess.ALWAYS_SELF,
    "hazard_kinds": ObservationFieldAccess.ALWAYS_SELF,
    "location": ObservationFieldAccess.ALWAYS_SELF,
    "exits": ObservationFieldAccess.ALWAYS_SELF,
    "held_items": ObservationFieldAccess.ALWAYS_SELF,
    "ground_items": ObservationFieldAccess.VISIBILITY_GATED,
    "resources": ObservationFieldAccess.VISIBILITY_GATED,
    "artifacts": ObservationFieldAccess.VISIBILITY_GATED,
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
    lifecycle: ObservedLifecycle | None = None
    kinship_visible: ObservedKinshipVisible | None = None
    dependency_needs: ObservedDependencyNeeds | None = None

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("VisibleBody.entity_id must be EntityId")
        if type(self.life_status) is not LifeStatus:
            raise TypeError("VisibleBody.life_status must be LifeStatus")
        if type(self.coarse_health) is not CoarseHealth:
            raise TypeError("VisibleBody.coarse_health must be CoarseHealth")
        if self.lifecycle is not None and type(self.lifecycle) is not ObservedLifecycle:
            raise TypeError("VisibleBody.lifecycle must be ObservedLifecycle or None")
        if (
            self.kinship_visible is not None
            and type(self.kinship_visible) is not ObservedKinshipVisible
        ):
            raise TypeError(
                "VisibleBody.kinship_visible must be ObservedKinshipVisible or None"
            )
        if (
            self.dependency_needs is not None
            and type(self.dependency_needs) is not ObservedDependencyNeeds
        ):
            raise TypeError(
                "VisibleBody.dependency_needs must be ObservedDependencyNeeds or None"
            )
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
class ObservedLifecycle:
    """Closed objective lifecycle facts visible when the channel is on.

    Exact fields only. Generation/cohort/provenance stay out of perception.
    """

    chronological_age: int
    stage: str
    dependency_status: str

    def __post_init__(self) -> None:
        from world.identifiers import require_exact_nonneg_int, require_stable_id
        from world.lifecycle import DependencyStatus

        object.__setattr__(
            self,
            "chronological_age",
            require_exact_nonneg_int(
                "ObservedLifecycle.chronological_age", self.chronological_age
            ),
        )
        object.__setattr__(
            self,
            "stage",
            require_stable_id("ObservedLifecycle.stage", self.stage),
        )
        object.__setattr__(
            self,
            "dependency_status",
            require_stable_id(
                "ObservedLifecycle.dependency_status", self.dependency_status
            ),
        )
        if self.dependency_status not in {item.value for item in DependencyStatus}:
            raise ValueError(
                "ObservedLifecycle.dependency_status must be a closed "
                "DependencyStatus"
            )


@dataclass(frozen=True, slots=True)
class ObservedKinshipVisible:
    """Closed self-incident kinship facts when perception_mode allows.

    Agent-id strings only. Never ancestors/descendants dumps. Relatedness
    never implies trust, affection, loyalty, obligation, or inheritance.
    """

    parents: tuple[str, ...] = ()
    children: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from world.identifiers import require_stable_id

        if isinstance(self.parents, (str, bytes)) or not isinstance(
            self.parents, tuple
        ):
            raise TypeError("ObservedKinshipVisible.parents must be a tuple")
        if isinstance(self.children, (str, bytes)) or not isinstance(
            self.children, tuple
        ):
            raise TypeError("ObservedKinshipVisible.children must be a tuple")
        parents = tuple(
            require_stable_id("ObservedKinshipVisible.parents", item)
            for item in self.parents
        )
        children = tuple(
            require_stable_id("ObservedKinshipVisible.children", item)
            for item in self.children
        )
        if parents != tuple(sorted(parents)):
            raise ValueError("ObservedKinshipVisible.parents must be sorted")
        if children != tuple(sorted(children)):
            raise ValueError("ObservedKinshipVisible.children must be sorted")
        if len(set(parents)) != len(parents):
            raise ValueError("ObservedKinshipVisible.parents must be unique")
        if len(set(children)) != len(children):
            raise ValueError("ObservedKinshipVisible.children must be unique")
        object.__setattr__(self, "parents", parents)
        object.__setattr__(self, "children", children)


@dataclass(frozen=True, slots=True)
class ObservedDependencyNeed:
    """Closed need-deficit summary for dependency-care perception."""

    need_id: str
    deficit: float
    critical: bool

    def __post_init__(self) -> None:
        from world.dependency_care import CARE_NEED_IDS

        if type(self.need_id) is not str:
            raise TypeError("ObservedDependencyNeed.need_id must be str")
        if self.need_id not in CARE_NEED_IDS:
            raise ValueError(
                f"ObservedDependencyNeed.need_id must be closed CareNeedId "
                f"(got {self.need_id!r})"
            )
        if isinstance(self.deficit, bool) or not isinstance(self.deficit, (int, float)):
            raise TypeError("ObservedDependencyNeed.deficit must be a number")
        deficit = float(self.deficit)
        if deficit < 0.0 or deficit > 1.0:
            raise ValueError("ObservedDependencyNeed.deficit must be in [0, 1]")
        object.__setattr__(self, "deficit", deficit)
        if type(self.critical) is not bool:
            raise TypeError("ObservedDependencyNeed.critical must be bool")


@dataclass(frozen=True, slots=True)
class ObservedDependencyNeeds:
    """Ordered need-deficit summaries (sibling of lifecycle — not inside it)."""

    needs: tuple[ObservedDependencyNeed, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.needs, (str, bytes)) or not isinstance(self.needs, tuple):
            raise TypeError("ObservedDependencyNeeds.needs must be a tuple")
        cleaned: list[ObservedDependencyNeed] = []
        seen: set[str] = set()
        for item in self.needs:
            if type(item) is not ObservedDependencyNeed:
                raise TypeError(
                    "ObservedDependencyNeeds.needs entries must be "
                    "ObservedDependencyNeed"
                )
            if item.need_id in seen:
                raise ValueError("ObservedDependencyNeeds.needs must be unique by need_id")
            seen.add(item.need_id)
            cleaned.append(item)
        ordered = tuple(sorted(cleaned, key=lambda row: row.need_id))
        object.__setattr__(self, "needs", ordered)


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
class ObservedStructure:
    """Location-attached structure visible under the content threshold."""

    entity_id: EntityId
    location_id: EntityId
    kind: StructureKind
    integrity: float
    stored_quantity: int

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedStructure.entity_id must be EntityId")
        if type(self.location_id) is not EntityId:
            raise TypeError("ObservedStructure.location_id must be EntityId")
        if type(self.kind) is not StructureKind:
            raise TypeError("ObservedStructure.kind must be StructureKind")
        if isinstance(self.integrity, bool) or not isinstance(
            self.integrity, (int, float)
        ):
            raise TypeError("ObservedStructure.integrity must be a finite float")
        number = float(self.integrity)
        if number != number or number < 0.0 or number > 1.0:
            raise ValueError("ObservedStructure.integrity must be in [0, 1]")
        object.__setattr__(self, "integrity", 0.0 if number == 0.0 else number)
        quantity = self.stored_quantity
        if isinstance(quantity, bool) or type(quantity) is not int:
            raise TypeError("ObservedStructure.stored_quantity must be int")
        if self.stored_quantity < 0:
            raise ValueError("ObservedStructure.stored_quantity must be non-negative")


@dataclass(frozen=True, slots=True)
class ObservedArtifact:
    """Objective artifact marks visible without interpretation or presentation."""

    entity_id: EntityId
    kind: ArtifactKind
    author_id: EntityId
    created_tick: int
    content: ArtifactContent
    content_revision: int
    placement: ObservedItemPlacement

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("ObservedArtifact.entity_id must be EntityId")
        if type(self.kind) is not ArtifactKind:
            raise TypeError("ObservedArtifact.kind must be ArtifactKind")
        if type(self.author_id) is not EntityId:
            raise TypeError("ObservedArtifact.author_id must be EntityId")
        if isinstance(self.created_tick, bool) or type(self.created_tick) is not int:
            raise TypeError("ObservedArtifact.created_tick must be int")
        if self.created_tick < 0:
            raise ValueError("ObservedArtifact.created_tick must be non-negative")
        require_artifact_content(self.content, field_name="ObservedArtifact.content")
        if (
            isinstance(self.content_revision, bool)
            or type(self.content_revision) is not int
        ):
            raise TypeError("ObservedArtifact.content_revision must be int")
        if self.content_revision < 0:
            raise ValueError("ObservedArtifact.content_revision must be non-negative")
        if type(self.placement) is not ObservedItemPlacement:
            raise TypeError("ObservedArtifact.placement must be ObservedItemPlacement")
        if self.placement not in {
            ObservedItemPlacement.GROUND_HERE,
            ObservedItemPlacement.HELD_BY_SELF,
        }:
            raise ValueError(
                "ObservedArtifact.placement must be ground or held-by-self"
            )


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
    lifecycle: ObservedLifecycle | None = None
    kinship_visible: ObservedKinshipVisible | None = None
    dependency_needs: ObservedDependencyNeeds | None = None

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
        if self.lifecycle is not None and type(self.lifecycle) is not ObservedLifecycle:
            raise TypeError("ObservedSelf.lifecycle must be ObservedLifecycle or None")
        if (
            self.kinship_visible is not None
            and type(self.kinship_visible) is not ObservedKinshipVisible
        ):
            raise TypeError(
                "ObservedSelf.kinship_visible must be ObservedKinshipVisible or None"
            )
        if (
            self.dependency_needs is not None
            and type(self.dependency_needs) is not ObservedDependencyNeeds
        ):
            raise TypeError(
                "ObservedSelf.dependency_needs must be ObservedDependencyNeeds or None"
            )
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


def observed_self_from_body(
    body: AgentBody,
    *,
    lifecycle: ObservedLifecycle | None = None,
    kinship_visible: ObservedKinshipVisible | None = None,
    dependency_needs: ObservedDependencyNeeds | None = None,
) -> ObservedSelf:
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
        lifecycle=lifecycle,
        kinship_visible=kinship_visible,
        dependency_needs=dependency_needs,
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
    lifecycle_by_body: Mapping[EntityId, ObservedLifecycle] | None = None
    kinship_self_by_body: Mapping[EntityId, ObservedKinshipVisible] | None = None
    kinship_agent_by_body: Mapping[EntityId, str] | None = None
    dependency_needs_by_body: Mapping[EntityId, ObservedDependencyNeeds] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ObservationContext.tick", self.tick),
        )
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("ObservationContext.physical_rules must be PhysicalRules")
        if self.lifecycle_by_body is not None:
            if isinstance(self.lifecycle_by_body, (str, bytes)) or not isinstance(
                self.lifecycle_by_body, Mapping
            ):
                raise TypeError(
                    "ObservationContext.lifecycle_by_body must be a mapping or None"
                )
            frozen: dict[EntityId, ObservedLifecycle] = {}
            for body_id, view in self.lifecycle_by_body.items():
                if type(body_id) is not EntityId:
                    raise TypeError(
                        "ObservationContext.lifecycle_by_body keys must be EntityId"
                    )
                if type(view) is not ObservedLifecycle:
                    raise TypeError(
                        "ObservationContext.lifecycle_by_body values must be "
                        "ObservedLifecycle"
                    )
                frozen[body_id] = view
            object.__setattr__(
                self, "lifecycle_by_body", MappingProxyType(frozen)
            )
        if self.kinship_self_by_body is not None:
            if isinstance(self.kinship_self_by_body, (str, bytes)) or not isinstance(
                self.kinship_self_by_body, Mapping
            ):
                raise TypeError(
                    "ObservationContext.kinship_self_by_body must be a mapping or None"
                )
            kin_frozen: dict[EntityId, ObservedKinshipVisible] = {}
            for body_id, view in self.kinship_self_by_body.items():
                if type(body_id) is not EntityId:
                    raise TypeError(
                        "ObservationContext.kinship_self_by_body keys must be EntityId"
                    )
                if type(view) is not ObservedKinshipVisible:
                    raise TypeError(
                        "ObservationContext.kinship_self_by_body values must be "
                        "ObservedKinshipVisible"
                    )
                kin_frozen[body_id] = view
            object.__setattr__(
                self, "kinship_self_by_body", MappingProxyType(kin_frozen)
            )
        if self.kinship_agent_by_body is not None:
            if isinstance(self.kinship_agent_by_body, (str, bytes)) or not isinstance(
                self.kinship_agent_by_body, Mapping
            ):
                raise TypeError(
                    "ObservationContext.kinship_agent_by_body must be a mapping or None"
                )
            agents: dict[EntityId, str] = {}
            for body_id, agent_id in self.kinship_agent_by_body.items():
                if type(body_id) is not EntityId:
                    raise TypeError(
                        "ObservationContext.kinship_agent_by_body keys must be EntityId"
                    )
                if not isinstance(agent_id, str):
                    raise TypeError(
                        "ObservationContext.kinship_agent_by_body values must be str"
                    )
                agents[body_id] = agent_id
            object.__setattr__(
                self, "kinship_agent_by_body", MappingProxyType(agents)
            )
        if self.dependency_needs_by_body is not None:
            if isinstance(self.dependency_needs_by_body, (str, bytes)) or not isinstance(
                self.dependency_needs_by_body, Mapping
            ):
                raise TypeError(
                    "ObservationContext.dependency_needs_by_body must be a mapping "
                    "or None"
                )
            need_frozen: dict[EntityId, ObservedDependencyNeeds] = {}
            for body_id, view in self.dependency_needs_by_body.items():
                if type(body_id) is not EntityId:
                    raise TypeError(
                        "ObservationContext.dependency_needs_by_body keys must be "
                        "EntityId"
                    )
                if type(view) is not ObservedDependencyNeeds:
                    raise TypeError(
                        "ObservationContext.dependency_needs_by_body values must be "
                        "ObservedDependencyNeeds"
                    )
                need_frozen[body_id] = view
            object.__setattr__(
                self, "dependency_needs_by_body", MappingProxyType(need_frozen)
            )

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
    structures: Sequence[ObservedStructure] = field(default_factory=tuple)
    artifacts: Sequence[ObservedArtifact] = field(default_factory=tuple)
    exits: Sequence[VisibleExit] = field(default_factory=tuple)
    visible_bodies: Sequence[VisibleBody] = field(default_factory=tuple)
    occurrences: Sequence[ObservedOccurrence] = field(default_factory=tuple)
    communications: Sequence[ObservedCommunication] = field(default_factory=tuple)
    hour: int | None = None
    day_phase: DayPhase | None = None
    visibility: float | None = None
    weather_condition: WeatherCondition | None = None
    season: Season | None = None
    temperature_band: TemperatureBand | None = None
    hazard_kinds: Sequence[HazardKind] | None = None

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
            "structures",
            _copy_models(
                "Observation.structures",
                self.structures,
                model_type=ObservedStructure,
            ),
        )
        object.__setattr__(
            self,
            "artifacts",
            _copy_models(
                "Observation.artifacts",
                self.artifacts,
                model_type=ObservedArtifact,
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
        if self.season is not None and type(self.season) is not Season:
            raise TypeError("Observation.season must be Season or None")
        if (
            self.temperature_band is not None
            and type(self.temperature_band) is not TemperatureBand
        ):
            raise TypeError(
                "Observation.temperature_band must be TemperatureBand or None"
            )
        object.__setattr__(
            self,
            "hazard_kinds",
            _copy_hazard_kinds(self.hazard_kinds),
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
            "Observation.structures",
            tuple(structure.entity_id for structure in self.structures),
        )
        _validate_ordered_ids(
            "Observation.artifacts",
            tuple(artifact.entity_id for artifact in self.artifacts),
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


def _copy_hazard_kinds(
    values: Sequence[HazardKind] | None,
) -> tuple[HazardKind, ...] | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError("Observation.hazard_kinds must be an ordered sequence or None")
    copied = tuple(values)
    for kind in copied:
        if type(kind) is not HazardKind:
            raise TypeError("Observation.hazard_kinds entries must be HazardKind")
    ordered = tuple(sorted(copied, key=lambda kind: kind.value))
    if len(ordered) != len(set(ordered)):
        raise ValueError("Observation.hazard_kinds must not contain duplicates")
    return ordered


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
