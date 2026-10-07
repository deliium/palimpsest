"""Frozen read-only observer contracts. No live engine and no presentation verbs."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn

from observer.presentation import EntityPresentation
from observer.version import (
    OBSERVER_LAYOUT_SCHEMA_VERSION,
    OBSERVER_PROTOCOL_VERSION,
    RELATIONSHIP_DIMENSION_CODES,
    SEMANTIC_EVENT_TYPES,
)

_LOGGER = logging.getLogger("observer.contracts")

_FORBIDDEN_INSTRUCTION_FIELDS = frozenset({"pixels", "sprite", "animation", "dx", "dy"})
_INVERSE_TYPE_PREFIX = "AGENT_" + "UN"
_ORDERING: Literal["tick_sequence"] = "tick_sequence"
_OBJECTIVE_LEAK_FIELDS: frozenset[str] = frozenset(
    {
        "relationship",
        "relationships",
        "territorial_claims",
        "group_formation",
        "spatial_control",
        "territory_owner",
        "controller",
        "semantic_naming",
        "cultural_narratives",
        "subjective_labels",
        "labels",
    }
)


def _reject_objective_leak(names: set[str]) -> None:
    leaked = _OBJECTIVE_LEAK_FIELDS.intersection(names)
    if not leaked:
        return
    name = sorted(leaked)[0]
    _LOGGER.error("objective_leak field=%s", name)
    _reject(name, "objective_leak")


class ObserverContractError(ValueError):
    """Closed validation failure for an observer contract."""

    def __init__(self, *, field: str, reason_code: str) -> None:
        self.field = field
        self.reason_code = reason_code
        super().__init__(f"{field}: {reason_code}")


def _reject(field: str, reason_code: str) -> NoReturn:
    _LOGGER.error(
        "observer_contract_rejected field=%s reason_code=%s",
        field,
        reason_code,
    )
    raise ObserverContractError(field=field, reason_code=reason_code)


def _reject_extra(extra: dict[str, object]) -> None:
    if not extra:
        return
    name = sorted(extra)[0]
    if name in _FORBIDDEN_INSTRUCTION_FIELDS:
        _reject(name, "presentation_instruction_forbidden")
    _reject(name, "unknown_field")


def _require_protocol(value: object, *, field: str = "protocol_version") -> str:
    if type(value) is not str or value != OBSERVER_PROTOCOL_VERSION:
        _reject(field, "unsupported_observer_protocol")
    return value


def _require_text(field: str, value: object) -> str:
    if type(value) is not str or not value:
        _reject(field, "invalid_id")
    return value


def _require_tick(field: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _reject(field, "invalid_tick")
    return value


def _optional_text(field: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_text(field, value)


def _finite(field: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _reject(field, "invalid_number")
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        _reject(field, "invalid_number")
    return number


def _id_tuple(field: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (set, frozenset)):
        _reject(field, "unordered_inventory")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _reject(field, "invalid_sequence")
    frozen: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _require_text(field, item)
        if text in seen:
            _reject(field, "duplicate_id")
        seen.add(text)
        frozen.append(text)
    return tuple(frozen)


def _log_built(kind: str, *, id_count: int, protocol_version: str) -> None:
    _LOGGER.debug(
        "observer_contract_built protocol_version=%s kind=%s id_count=%s",
        protocol_version,
        kind,
        id_count,
    )


@dataclass(frozen=True, slots=True)
class ScreenPoint:
    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite("x", self.x))
        object.__setattr__(self, "y", _finite("y", self.y))


@dataclass(frozen=True, slots=True)
class VisualBounds:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite("x", self.x))
        object.__setattr__(self, "y", _finite("y", self.y))
        width = _finite("width", self.width)
        height = _finite("height", self.height)
        if width < 0.0 or height < 0.0:
            _reject("visual_bounds", "invalid_bounds")
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)


@dataclass(frozen=True, slots=True)
class PresentationSlot:
    slot_index: int
    local_x: float | None = None
    local_y: float | None = None

    def __post_init__(self) -> None:
        if (
            isinstance(self.slot_index, bool)
            or type(self.slot_index) is not int
            or self.slot_index < 0
        ):
            _reject("slot_index", "invalid_slot_index")
        local_x = None if self.local_x is None else _finite("local_x", self.local_x)
        local_y = None if self.local_y is None else _finite("local_y", self.local_y)
        if (local_x is None) != (local_y is None):
            _reject("local_x", "incomplete_slot_coordinate")
        object.__setattr__(self, "local_x", local_x)
        object.__setattr__(self, "local_y", local_y)


@dataclass(frozen=True, slots=True)
class ObserverPresentation:
    screen_position: ScreenPoint | None
    visual_bounds: VisualBounds | None
    theme: str | None
    icon_ref: str | None
    background_ref: str | None
    connection_anchors: tuple[tuple[str, ScreenPoint], ...] = ()
    slot_anchors: tuple[ScreenPoint, ...] = ()

    def __post_init__(self) -> None:
        if (
            self.screen_position is not None
            and type(self.screen_position) is not ScreenPoint
        ):
            _reject("screen_position", "invalid_type")
        if (
            self.visual_bounds is not None
            and type(self.visual_bounds) is not VisualBounds
        ):
            _reject("visual_bounds", "invalid_type")
        anchors: list[tuple[str, ScreenPoint]] = []
        seen: set[str] = set()
        for key, point in self.connection_anchors:
            neighbor = _require_text("connection_anchors", key)
            if type(point) is not ScreenPoint:
                _reject("connection_anchors", "invalid_type")
            if neighbor in seen:
                _reject("connection_anchors", "duplicate_id")
            seen.add(neighbor)
            anchors.append((neighbor, point))
        slots: list[ScreenPoint] = []
        for point in self.slot_anchors:
            if type(point) is not ScreenPoint:
                _reject("slot_anchors", "invalid_type")
            slots.append(point)
        object.__setattr__(self, "connection_anchors", tuple(anchors))
        object.__setattr__(self, "slot_anchors", tuple(slots))


@dataclass(frozen=True, slots=True)
class ObserverLocation:
    location_id: str
    name: str
    display_name: str
    neighbor_ids: tuple[str, ...]
    presentation: ObserverPresentation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(self, "name", _require_text("name", self.name))
        object.__setattr__(
            self, "display_name", _require_text("display_name", self.display_name)
        )
        object.__setattr__(
            self, "neighbor_ids", _id_tuple("neighbor_ids", self.neighbor_ids)
        )
        if self.presentation is not None and type(self.presentation) is not (
            ObserverPresentation
        ):
            _reject("presentation", "invalid_type")


@dataclass(frozen=True, slots=True)
class ObserverBodyMeasures:
    health: float
    hunger: float
    thirst: float
    fatigue: float
    temperature: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "health", _finite("health", self.health))
        object.__setattr__(self, "hunger", _finite("hunger", self.hunger))
        object.__setattr__(self, "thirst", _finite("thirst", self.thirst))
        object.__setattr__(self, "fatigue", _finite("fatigue", self.fatigue))
        object.__setattr__(
            self, "temperature", _finite("temperature", self.temperature)
        )


@dataclass(frozen=True, slots=True)
class ObserverAgent:
    entity_id: str
    location_id: str
    life_status: str
    inventory_ids: tuple[str, ...]
    measures: ObserverBodyMeasures
    agent_id: str | None = None
    presentation_slot: PresentationSlot | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "entity_id", _require_text("entity_id", self.entity_id)
        )
        object.__setattr__(self, "agent_id", _optional_text("agent_id", self.agent_id))
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(
            self, "life_status", _require_text("life_status", self.life_status)
        )
        object.__setattr__(
            self, "inventory_ids", _id_tuple("inventory_ids", self.inventory_ids)
        )
        if type(self.measures) is not ObserverBodyMeasures:
            _reject("measures", "invalid_type")
        if (
            self.presentation_slot is not None
            and type(self.presentation_slot) is not PresentationSlot
        ):
            _reject("presentation_slot", "invalid_type")


@dataclass(frozen=True, slots=True)
class ObserverItem:
    item_id: str
    name: str
    kind: str
    location_id: str | None = None
    holder_id: str | None = None
    presentation: EntityPresentation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _require_text("item_id", self.item_id))
        object.__setattr__(self, "name", _require_text("name", self.name))
        object.__setattr__(self, "kind", _require_text("kind", self.kind))
        location_id = _optional_text("location_id", self.location_id)
        holder_id = _optional_text("holder_id", self.holder_id)
        if (location_id is None) == (holder_id is None):
            _reject("location_id", "invalid_placement")
        object.__setattr__(self, "location_id", location_id)
        object.__setattr__(self, "holder_id", holder_id)
        if self.presentation is not None and type(self.presentation) is not (
            EntityPresentation
        ):
            _reject("presentation", "invalid_type")


@dataclass(frozen=True, slots=True)
class ObserverResource:
    resource_id: str
    name: str
    kind: str
    location_id: str
    quantity: float
    unit: str
    presentation: EntityPresentation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resource_id", _require_text("resource_id", self.resource_id)
        )
        object.__setattr__(self, "name", _require_text("name", self.name))
        object.__setattr__(self, "kind", _require_text("kind", self.kind))
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(self, "quantity", _finite("quantity", self.quantity))
        object.__setattr__(self, "unit", _require_text("unit", self.unit))
        if self.presentation is not None and type(self.presentation) is not (
            EntityPresentation
        ):
            _reject("presentation", "invalid_type")


@dataclass(frozen=True, slots=True)
class ObserverStructure:
    structure_id: str
    location_id: str
    kind: str
    integrity: float
    stored_quantity: int
    presentation: EntityPresentation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "structure_id", _require_text("structure_id", self.structure_id)
        )
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(self, "kind", _require_text("kind", self.kind))
        object.__setattr__(self, "integrity", _finite("integrity", self.integrity))
        quantity = self.stored_quantity
        if isinstance(quantity, bool) or type(quantity) is not int:
            _reject("stored_quantity", "invalid_type")
        if self.stored_quantity < 0:
            _reject("stored_quantity", "invalid_quantity")
        if self.presentation is not None and type(self.presentation) is not (
            EntityPresentation
        ):
            _reject("presentation", "invalid_type")


@dataclass(frozen=True, slots=True)
class ObserverArtifact:
    artifact_id: str
    kind: str
    author_id: str
    created_tick: int
    content_revision: int
    location_id: str | None = None
    holder_id: str | None = None
    marks: tuple[str, ...] = ()
    presentation: EntityPresentation | None = None
    record_genre: str | None = None
    parent_artifact_id: str | None = None
    source_artifact_id: str | None = None
    copy_generation: int | None = None
    integrity: str | None = None
    annotation_revisions: int | None = None
    lost_mark_count: int | None = None
    custodian_repository_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_id", _require_text("artifact_id", self.artifact_id)
        )
        object.__setattr__(self, "kind", _require_text("kind", self.kind))
        object.__setattr__(
            self, "author_id", _require_text("author_id", self.author_id)
        )
        object.__setattr__(
            self, "created_tick", _require_tick("created_tick", self.created_tick)
        )
        object.__setattr__(
            self,
            "content_revision",
            _require_tick("content_revision", self.content_revision),
        )
        location_id = _optional_text("location_id", self.location_id)
        holder_id = _optional_text("holder_id", self.holder_id)
        if (location_id is None) == (holder_id is None):
            _reject("location_id", "invalid_placement")
        object.__setattr__(self, "location_id", location_id)
        object.__setattr__(self, "holder_id", holder_id)
        if isinstance(self.marks, (set, frozenset)):
            _reject("marks", "unordered_inventory")
        if isinstance(self.marks, (str, bytes)) or not isinstance(self.marks, Sequence):
            _reject("marks", "invalid_sequence")
        object.__setattr__(
            self,
            "marks",
            tuple(_require_text("marks", mark) for mark in self.marks),
        )
        if self.presentation is not None and type(self.presentation) is not (
            EntityPresentation
        ):
            _reject("presentation", "invalid_type")
        object.__setattr__(
            self, "record_genre", _optional_text("record_genre", self.record_genre)
        )
        object.__setattr__(
            self,
            "parent_artifact_id",
            _optional_text("parent_artifact_id", self.parent_artifact_id),
        )
        object.__setattr__(
            self,
            "source_artifact_id",
            _optional_text("source_artifact_id", self.source_artifact_id),
        )
        if self.copy_generation is not None:
            object.__setattr__(
                self,
                "copy_generation",
                _require_tick("copy_generation", self.copy_generation),
            )
        object.__setattr__(
            self, "integrity", _optional_text("integrity", self.integrity)
        )
        if self.annotation_revisions is not None:
            object.__setattr__(
                self,
                "annotation_revisions",
                _require_tick("annotation_revisions", self.annotation_revisions),
            )
        if self.lost_mark_count is not None:
            object.__setattr__(
                self,
                "lost_mark_count",
                _require_tick("lost_mark_count", self.lost_mark_count),
            )
        object.__setattr__(
            self,
            "custodian_repository_id",
            _optional_text(
                "custodian_repository_id", self.custodian_repository_id
            ),
        )


@dataclass(frozen=True, slots=True)
class ObserverRepository:
    """Objective repository container for presentation (no cultural labels)."""

    repository_id: str
    location_id: str
    status: str
    member_count: int
    access_mode: str | None = None
    structure_id: str | None = None
    founder_ids: tuple[str, ...] | None = None
    index_entry_count: int | None = None
    last_maintained_tick: int | None = None
    neglect_streak: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "repository_id",
            _require_text("repository_id", self.repository_id),
        )
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(self, "status", _require_text("status", self.status))
        object.__setattr__(
            self, "member_count", _require_tick("member_count", self.member_count)
        )
        object.__setattr__(
            self, "access_mode", _optional_text("access_mode", self.access_mode)
        )
        object.__setattr__(
            self, "structure_id", _optional_text("structure_id", self.structure_id)
        )
        if self.founder_ids is not None:
            if isinstance(self.founder_ids, (str, bytes)) or not isinstance(
                self.founder_ids, Sequence
            ):
                _reject("founder_ids", "invalid_sequence")
            object.__setattr__(
                self,
                "founder_ids",
                tuple(
                    _require_text("founder_ids", item) for item in self.founder_ids
                ),
            )
        if self.index_entry_count is not None:
            object.__setattr__(
                self,
                "index_entry_count",
                _require_tick("index_entry_count", self.index_entry_count),
            )
        if self.last_maintained_tick is not None:
            object.__setattr__(
                self,
                "last_maintained_tick",
                _require_tick("last_maintained_tick", self.last_maintained_tick),
            )
        if self.neglect_streak is not None:
            object.__setattr__(
                self,
                "neglect_streak",
                _require_tick("neglect_streak", self.neglect_streak),
            )


@dataclass(frozen=True, slots=True)
class ObserverWeather:
    location_id: str
    condition: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(
            self, "condition", _require_text("condition", self.condition)
        )


@dataclass(frozen=True, slots=True)
class ObserverTemperatureBand:
    location_id: str
    band: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(self, "band", _require_text("band", self.band))


@dataclass(frozen=True, slots=True)
class ObserverHazard:
    location_id: str
    hazard_kind: str
    remaining_ticks: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "location_id", _require_text("location_id", self.location_id)
        )
        object.__setattr__(
            self, "hazard_kind", _require_text("hazard_kind", self.hazard_kind)
        )
        object.__setattr__(
            self,
            "remaining_ticks",
            _require_tick("remaining_ticks", self.remaining_ticks),
        )


@dataclass(frozen=True, slots=True)
class ObserverWorldState:
    tick: int
    revision: int
    locations: tuple[ObserverLocation, ...] = ()
    agents: tuple[ObserverAgent, ...] = ()
    items: tuple[ObserverItem, ...] = ()
    resources: tuple[ObserverResource, ...] = ()
    weather: tuple[ObserverWeather, ...] = ()
    structures: tuple[ObserverStructure, ...] = ()
    artifacts: tuple[ObserverArtifact, ...] = ()
    repositories: tuple[ObserverRepository, ...] = ()
    season: str | None = None
    temperature_bands: tuple[ObserverTemperatureBand, ...] = ()
    hazards: tuple[ObserverHazard, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        object.__setattr__(self, "revision", _require_tick("revision", self.revision))
        locations = _typed_tuple("locations", self.locations, ObserverLocation)
        agents = _typed_tuple("agents", self.agents, ObserverAgent)
        items = _typed_tuple("items", self.items, ObserverItem)
        resources = _typed_tuple("resources", self.resources, ObserverResource)
        weather = _typed_tuple("weather", self.weather, ObserverWeather)
        structures = _typed_tuple("structures", self.structures, ObserverStructure)
        artifacts = _typed_tuple("artifacts", self.artifacts, ObserverArtifact)
        repositories = _typed_tuple(
            "repositories", self.repositories, ObserverRepository
        )
        bands = _typed_tuple(
            "temperature_bands", self.temperature_bands, ObserverTemperatureBand
        )
        hazards = _typed_tuple("hazards", self.hazards, ObserverHazard)
        season = _optional_text("season", self.season)
        _unique("locations", tuple(item.location_id for item in locations))
        _unique("agents", tuple(item.entity_id for item in agents))
        _unique("items", tuple(item.item_id for item in items))
        _unique("resources", tuple(item.resource_id for item in resources))
        _unique("weather", tuple(item.location_id for item in weather))
        _unique("structures", tuple(item.structure_id for item in structures))
        _unique("artifacts", tuple(item.artifact_id for item in artifacts))
        _unique(
            "repositories", tuple(item.repository_id for item in repositories)
        )
        _unique("temperature_bands", tuple(item.location_id for item in bands))
        _unique(
            "hazards",
            tuple(f"{item.location_id}:{item.hazard_kind}" for item in hazards),
        )
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "agents", agents)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "weather", weather)
        object.__setattr__(self, "structures", structures)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "repositories", repositories)
        object.__setattr__(self, "season", season)
        object.__setattr__(self, "temperature_bands", bands)
        object.__setattr__(self, "hazards", hazards)
        _reject_objective_leak(
            set(_OBJECTIVE_LEAK_FIELDS.intersection(self.__dataclass_fields__))
        )
        _log_built(
            "ObserverWorldState",
            id_count=len(locations) + len(agents) + len(items) + len(resources),
            protocol_version=OBSERVER_PROTOCOL_VERSION,
        )


_WORLD_FIELDS: frozenset[str] = frozenset(ObserverWorldState.__dataclass_fields__)
_generated_world_init = ObserverWorldState.__init__


def _guarded_world_init(
    self: ObserverWorldState, *args: object, **kwargs: object
) -> None:
    _reject_objective_leak(set(kwargs))
    _generated_world_init(self, *args, **kwargs)


ObserverWorldState.__init__ = _guarded_world_init  # type: ignore[method-assign]


def observer_world_state_from_mapping(
    payload: Mapping[str, object],
) -> ObserverWorldState:
    """Parse a detached world mapping and reject subjective or analytic keys."""
    if not isinstance(payload, Mapping):
        _reject("world", "invalid_type")
    names = {key for key in payload if isinstance(key, str)}
    _reject_objective_leak(names)
    extra = {key: payload[key] for key in names if key not in _WORLD_FIELDS}
    _reject_extra(extra)
    known = {key: payload[key] for key in names if key in _WORLD_FIELDS}
    return ObserverWorldState(**known)


def _typed_tuple[T](field: str, values: object, model: type[T]) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset)):
        _reject(field, "unordered_inventory")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _reject(field, "invalid_sequence")
    frozen: list[T] = []
    for item in values:
        if type(item) is not model:
            _reject(field, "invalid_type")
        frozen.append(item)
    return tuple(frozen)


def _unique(field: str, values: tuple[str, ...]) -> None:
    if len(values) != len(set(values)):
        _reject(field, "duplicate_id")


@dataclass(frozen=True, slots=True)
class ObserverEvent:
    protocol_version: str
    type: str
    domain_kind: str
    event_id: str
    tick: int
    sequence: int
    actor_id: str | None = None
    target_id: str | None = None
    item_id: str | None = None
    resource_id: str | None = None
    origin_location_id: str | None = None
    destination_location_id: str | None = None
    recipe_id: str | None = None
    structure_id: str | None = None
    artifact_id: str | None = None
    repository_id: str | None = None
    season: str | None = None
    temperature_band: str | None = None
    hazard_kind: str | None = None
    declared_confidence_band: str | None = None

    def __init__(
        self,
        protocol_version: str,
        type: str,
        domain_kind: str,
        event_id: str,
        tick: int,
        sequence: int,
        actor_id: str | None = None,
        target_id: str | None = None,
        item_id: str | None = None,
        resource_id: str | None = None,
        origin_location_id: str | None = None,
        destination_location_id: str | None = None,
        recipe_id: str | None = None,
        structure_id: str | None = None,
        artifact_id: str | None = None,
        repository_id: str | None = None,
        season: str | None = None,
        temperature_band: str | None = None,
        hazard_kind: str | None = None,
        declared_confidence_band: str | None = None,
        **extra: object,
    ) -> None:
        _reject_extra(extra)
        protocol = _require_protocol(protocol_version)
        semantic = type
        if not isinstance(semantic, str) or semantic not in SEMANTIC_EVENT_TYPES:
            if isinstance(semantic, str) and semantic.startswith(_INVERSE_TYPE_PREFIX):
                _reject("type", "presentation_instruction_forbidden")
            _reject("type", "unknown_event_kind")
        if semantic.startswith(_INVERSE_TYPE_PREFIX):
            _reject("type", "presentation_instruction_forbidden")
        kind = _require_text("domain_kind", domain_kind)
        object.__setattr__(self, "protocol_version", protocol)
        object.__setattr__(self, "type", semantic)
        object.__setattr__(self, "domain_kind", kind)
        object.__setattr__(self, "event_id", _require_text("event_id", event_id))
        object.__setattr__(self, "tick", _require_tick("tick", tick))
        object.__setattr__(self, "sequence", _require_tick("sequence", sequence))
        object.__setattr__(self, "actor_id", _optional_text("actor_id", actor_id))
        object.__setattr__(self, "target_id", _optional_text("target_id", target_id))
        object.__setattr__(self, "item_id", _optional_text("item_id", item_id))
        object.__setattr__(
            self, "resource_id", _optional_text("resource_id", resource_id)
        )
        object.__setattr__(
            self,
            "origin_location_id",
            _optional_text("origin_location_id", origin_location_id),
        )
        object.__setattr__(
            self,
            "destination_location_id",
            _optional_text("destination_location_id", destination_location_id),
        )
        object.__setattr__(self, "recipe_id", _optional_text("recipe_id", recipe_id))
        object.__setattr__(
            self, "structure_id", _optional_text("structure_id", structure_id)
        )
        object.__setattr__(
            self, "artifact_id", _optional_text("artifact_id", artifact_id)
        )
        object.__setattr__(
            self, "repository_id", _optional_text("repository_id", repository_id)
        )
        object.__setattr__(self, "season", _optional_text("season", season))
        object.__setattr__(
            self,
            "temperature_band",
            _optional_text("temperature_band", temperature_band),
        )
        object.__setattr__(
            self, "hazard_kind", _optional_text("hazard_kind", hazard_kind)
        )
        object.__setattr__(
            self,
            "declared_confidence_band",
            _optional_text("declared_confidence_band", declared_confidence_band),
        )
        _log_built("ObserverEvent", id_count=1, protocol_version=protocol)

    def public_mapping(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "protocol_version": self.protocol_version,
            "type": self.type,
            "domain_kind": self.domain_kind,
            "event_id": self.event_id,
            "tick": self.tick,
            "sequence": self.sequence,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "item_id": self.item_id,
            "resource_id": self.resource_id,
            "origin_location_id": self.origin_location_id,
            "destination_location_id": self.destination_location_id,
        }
        if self.recipe_id is not None:
            payload["recipe_id"] = self.recipe_id
        if self.structure_id is not None:
            payload["structure_id"] = self.structure_id
        if self.artifact_id is not None:
            payload["artifact_id"] = self.artifact_id
        if self.repository_id is not None:
            payload["repository_id"] = self.repository_id
        if self.season is not None:
            payload["season"] = self.season
        if self.temperature_band is not None:
            payload["temperature_band"] = self.temperature_band
        if self.hazard_kind is not None:
            payload["hazard_kind"] = self.hazard_kind
        if self.declared_confidence_band is not None:
            payload["declared_confidence_band"] = self.declared_confidence_band
        return payload


@dataclass(frozen=True, slots=True)
class ObserverPlaybackCursor:
    run_id: str
    mode: Literal["live", "replay"]
    tick: int
    protocol_version: str
    sequence: int | None = None
    after_tick: int | None = None
    after_sequence: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        if self.mode not in ("live", "replay"):
            _reject("mode", "invalid_mode")
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        object.__setattr__(
            self, "protocol_version", _require_protocol(self.protocol_version)
        )
        if self.sequence is not None:
            object.__setattr__(
                self, "sequence", _require_tick("sequence", self.sequence)
            )
        if (self.after_tick is None) != (self.after_sequence is None):
            _reject("after_tick", "incomplete_event_cursor")
        if self.after_tick is not None:
            object.__setattr__(
                self, "after_tick", _require_tick("after_tick", self.after_tick)
            )
            object.__setattr__(
                self,
                "after_sequence",
                _require_tick("after_sequence", self.after_sequence),
            )
        _log_built(
            "ObserverPlaybackCursor", id_count=1, protocol_version=self.protocol_version
        )


@dataclass(frozen=True, slots=True)
class ObserverFrame:
    protocol_version: str
    cursor: ObserverPlaybackCursor
    world: ObserverWorldState
    events: tuple[ObserverEvent, ...] | None = None

    def __post_init__(self) -> None:
        protocol = _require_protocol(self.protocol_version)
        if type(self.cursor) is not ObserverPlaybackCursor:
            _reject("cursor", "invalid_type")
        if type(self.world) is not ObserverWorldState:
            _reject("world", "invalid_type")
        if self.cursor.protocol_version != protocol:
            _reject("protocol_version", "unsupported_observer_protocol")
        events: tuple[ObserverEvent, ...] | None
        if self.events is None:
            events = None
        else:
            events = _typed_tuple("events", self.events, ObserverEvent)
        object.__setattr__(self, "protocol_version", protocol)
        object.__setattr__(self, "events", events)
        _log_built("ObserverFrame", id_count=1, protocol_version=protocol)


@dataclass(frozen=True, slots=True)
class ObserverManifest:
    protocol_version: str
    layout_schema_version: str
    layout_id: str
    layout_hash: str
    event_schema_version: int
    projector_version: str
    run_id: str
    ordering: Literal["tick_sequence"] = _ORDERING
    read_only: bool = True
    event_types: tuple[str, ...] = SEMANTIC_EVENT_TYPES
    parent_run_id: str | None = None
    fork_tick: int | None = None
    intervention_summary: str | None = None
    branch_id: str | None = None

    def __post_init__(self) -> None:
        protocol = _require_protocol(self.protocol_version)
        if self.layout_schema_version != OBSERVER_LAYOUT_SCHEMA_VERSION:
            _reject("layout_schema_version", "unsupported_observer_protocol")
        object.__setattr__(
            self, "layout_id", _require_text("layout_id", self.layout_id)
        )
        object.__setattr__(
            self, "layout_hash", _require_text("layout_hash", self.layout_hash)
        )
        object.__setattr__(self, "run_id", _require_text("run_id", self.run_id))
        if self.ordering != "tick_sequence":
            _reject("ordering", "invalid_ordering")
        if type(self.read_only) is not bool:
            _reject("read_only", "invalid_type")
        if self.read_only is not True:
            _reject("read_only", "read_only_required")
        if self.event_types != SEMANTIC_EVENT_TYPES:
            _reject("event_types", "unknown_event_kind")
        if (
            isinstance(self.event_schema_version, bool)
            or type(self.event_schema_version) is not int
            or self.event_schema_version < 1
        ):
            _reject("event_schema_version", "invalid_schema_version")
        object.__setattr__(
            self,
            "projector_version",
            _require_text("projector_version", self.projector_version),
        )
        object.__setattr__(self, "protocol_version", protocol)
        if self.parent_run_id is not None:
            object.__setattr__(
                self,
                "parent_run_id",
                _require_text("parent_run_id", self.parent_run_id),
            )
            if self.fork_tick is None:
                _reject("fork_tick", "fork_tick_required")
            if (
                isinstance(self.fork_tick, bool)
                or type(self.fork_tick) is not int
                or self.fork_tick < 0
            ):
                _reject("fork_tick", "invalid_fork_tick")
            if self.branch_id is None:
                _reject("branch_id", "branch_id_required")
            object.__setattr__(
                self, "branch_id", _require_text("branch_id", self.branch_id)
            )
            if self.intervention_summary is not None:
                object.__setattr__(
                    self,
                    "intervention_summary",
                    _require_text("intervention_summary", self.intervention_summary),
                )
        else:
            if self.fork_tick is not None or self.branch_id is not None:
                _reject("parent_run_id", "parent_required_for_fork_fields")
            if self.intervention_summary is not None:
                _reject("parent_run_id", "parent_required_for_fork_fields")
        _log_built(
            "ObserverManifest",
            id_count=len(self.event_types),
            protocol_version=protocol,
        )
        _LOGGER.debug(
            "observer_manifest_branch run_id=%s branch_id=%s parent_run_id=%s "
            "fork_tick=%s",
            self.run_id,
            self.branch_id,
            self.parent_run_id,
            self.fork_tick,
        )


@dataclass(frozen=True, slots=True)
class ObserverDimensionScore:
    dimension: str
    value: float

    def __post_init__(self) -> None:
        if self.dimension not in RELATIONSHIP_DIMENSION_CODES:
            _reject("dimension", "unknown_dimension")
        object.__setattr__(self, "value", _finite("value", self.value))


@dataclass(frozen=True, slots=True)
class ObserverRelationshipSummary:
    owner_id: str
    target_id: str
    dimensions: tuple[ObserverDimensionScore, ...]
    protocol_version: str = OBSERVER_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        protocol = _require_protocol(self.protocol_version)
        object.__setattr__(self, "owner_id", _require_text("owner_id", self.owner_id))
        object.__setattr__(
            self, "target_id", _require_text("target_id", self.target_id)
        )
        if self.owner_id == self.target_id:
            _reject("target_id", "duplicate_id")
        dimensions = _typed_tuple("dimensions", self.dimensions, ObserverDimensionScore)
        codes = tuple(item.dimension for item in dimensions)
        if len(codes) != len(set(codes)):
            _reject("dimensions", "duplicate_id")
        ordered = tuple(
            sorted(
                dimensions,
                key=lambda item: RELATIONSHIP_DIMENSION_CODES.index(item.dimension),
            )
        )
        object.__setattr__(self, "dimensions", ordered)
        object.__setattr__(self, "protocol_version", protocol)
        _log_built("ObserverRelationshipSummary", id_count=1, protocol_version=protocol)


__all__ = [
    "ObserverAgent",
    "ObserverArtifact",
    "ObserverBodyMeasures",
    "ObserverContractError",
    "ObserverDimensionScore",
    "ObserverEvent",
    "ObserverFrame",
    "ObserverItem",
    "ObserverLocation",
    "ObserverManifest",
    "ObserverPlaybackCursor",
    "ObserverPresentation",
    "ObserverRelationshipSummary",
    "ObserverRepository",
    "ObserverResource",
    "ObserverWeather",
    "ObserverWorldState",
    "PresentationSlot",
    "ScreenPoint",
    "VisualBounds",
]
