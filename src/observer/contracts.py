"""Frozen read-only observer contracts. No live engine and no presentation verbs."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, NoReturn

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


@dataclass(frozen=True, slots=True)
class ObserverResource:
    resource_id: str
    name: str
    kind: str
    location_id: str
    quantity: float
    unit: str

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
class ObserverWorldState:
    tick: int
    revision: int
    locations: tuple[ObserverLocation, ...] = ()
    agents: tuple[ObserverAgent, ...] = ()
    items: tuple[ObserverItem, ...] = ()
    resources: tuple[ObserverResource, ...] = ()
    weather: tuple[ObserverWeather, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "tick", _require_tick("tick", self.tick))
        object.__setattr__(self, "revision", _require_tick("revision", self.revision))
        locations = _typed_tuple("locations", self.locations, ObserverLocation)
        agents = _typed_tuple("agents", self.agents, ObserverAgent)
        items = _typed_tuple("items", self.items, ObserverItem)
        resources = _typed_tuple("resources", self.resources, ObserverResource)
        weather = _typed_tuple("weather", self.weather, ObserverWeather)
        _unique("locations", tuple(item.location_id for item in locations))
        _unique("agents", tuple(item.entity_id for item in agents))
        _unique("items", tuple(item.item_id for item in items))
        _unique("resources", tuple(item.resource_id for item in resources))
        _unique("weather", tuple(item.location_id for item in weather))
        object.__setattr__(self, "locations", locations)
        object.__setattr__(self, "agents", agents)
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "weather", weather)
        if hasattr(self, "relationship") or hasattr(self, "relationships"):
            _reject("relationship", "objective_leak")
        _log_built(
            "ObserverWorldState",
            id_count=len(locations) + len(agents) + len(items) + len(resources),
            protocol_version=OBSERVER_PROTOCOL_VERSION,
        )


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
        _log_built("ObserverEvent", id_count=1, protocol_version=protocol)

    def public_mapping(self) -> dict[str, object]:
        return {
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
    ordering: Literal["tick_sequence"] = _ORDERING
    read_only: bool = True
    event_types: tuple[str, ...] = SEMANTIC_EVENT_TYPES

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
        _log_built(
            "ObserverManifest",
            id_count=len(self.event_types),
            protocol_version=protocol,
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
    "ObserverResource",
    "ObserverWeather",
    "ObserverWorldState",
    "PresentationSlot",
    "ScreenPoint",
    "VisualBounds",
]
