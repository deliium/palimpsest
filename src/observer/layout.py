"""Presentation layout catalogs and deterministic slot placement."""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import files
from typing import NoReturn, cast

from observer.contracts import ObserverPresentation, ScreenPoint, VisualBounds
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION
from world.models import Location

_LOGGER = logging.getLogger("observer.layout")
_GOLDEN_ANGLE = 2.399963


class ObserverLayoutError(ValueError):
    """Closed layout validation failure."""

    def __init__(self, *, reason_code: str, location_id: str | None = None) -> None:
        self.reason_code = reason_code
        self.location_id = location_id
        super().__init__(reason_code)


def _fail(reason_code: str, *, location_id: str | None = None) -> NoReturn:
    _LOGGER.error(
        "observer_layout_rejected reason_code=%s location_id=%s",
        reason_code,
        location_id if location_id is not None else "-",
    )
    raise ObserverLayoutError(reason_code=reason_code, location_id=location_id)


def _record(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail("invalid_layout")
    return cast(dict[str, object], value)


def _number(record: dict[str, object], key: str) -> float:
    raw = record[key]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        _fail("invalid_layout")
    return float(raw)


def _point(value: object, *, field: str) -> ScreenPoint:
    record = _record(value)
    try:
        return ScreenPoint(x=_number(record, "x"), y=_number(record, "y"))
    except (KeyError, TypeError) as exc:
        _LOGGER.error(
            "observer_layout_rejected reason_code=%s location_id=%s",
            "invalid_layout",
            field,
        )
        raise ObserverLayoutError(reason_code="invalid_layout") from exc


def _bounds(value: object) -> VisualBounds:
    record = _record(value)
    try:
        return VisualBounds(
            x=_number(record, "x"),
            y=_number(record, "y"),
            width=_number(record, "width"),
            height=_number(record, "height"),
        )
    except (KeyError, TypeError) as exc:
        raise ObserverLayoutError(reason_code="invalid_layout") from exc


@dataclass(frozen=True, slots=True)
class LocationVisualSpec:
    location_id: str
    display_name: str
    screen_position: ScreenPoint | None
    visual_bounds: VisualBounds | None
    theme: str | None
    icon_ref: str | None
    background_ref: str | None
    connection_anchors: tuple[tuple[str, ScreenPoint], ...]
    slot_anchors: tuple[ScreenPoint, ...]

    def __post_init__(self) -> None:
        if type(self.location_id) is not str or not self.location_id:
            _fail("invalid_layout")
        if type(self.display_name) is not str or not self.display_name:
            _fail("invalid_layout")
        if self.screen_position is not None and type(self.screen_position) is not (
            ScreenPoint
        ):
            _fail("invalid_layout")
        if (
            self.visual_bounds is not None
            and type(self.visual_bounds) is not VisualBounds
        ):
            _fail("invalid_layout")


@dataclass(frozen=True, slots=True)
class SlotAssignment:
    entity_id: str
    slot_index: int
    local_x: float | None
    local_y: float | None


@dataclass(frozen=True, slots=True)
class ObserverLayoutCatalog:
    layout_id: str
    schema_version: str
    specs: tuple[LocationVisualSpec, ...]

    def __post_init__(self) -> None:
        if self.schema_version != OBSERVER_LAYOUT_SCHEMA_VERSION:
            _fail("unsupported_observer_protocol")
        if type(self.layout_id) is not str or not self.layout_id:
            _fail("invalid_layout")
        seen: set[str] = set()
        for spec in self.specs:
            if type(spec) is not LocationVisualSpec:
                _fail("invalid_layout")
            if spec.location_id in seen:
                _fail("duplicate_id", location_id=spec.location_id)
            seen.add(spec.location_id)
        object.__setattr__(self, "specs", tuple(self.specs))

    def spec_for(self, location_id: str) -> LocationVisualSpec | None:
        for spec in self.specs:
            if spec.location_id == location_id:
                return spec
        return None

    def content_hash(self) -> str:
        payload = json.dumps(
            _canonical_catalog(self), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_catalog(catalog: ObserverLayoutCatalog) -> dict[str, object]:
    locations: list[dict[str, object]] = []
    for spec in catalog.specs:
        anchors = {
            neighbor: {"x": point.x, "y": point.y}
            for neighbor, point in spec.connection_anchors
        }
        locations.append(
            {
                "background_ref": spec.background_ref,
                "connection_anchors": anchors,
                "display_name": spec.display_name,
                "icon_ref": spec.icon_ref,
                "location_id": spec.location_id,
                "screen_position": (
                    None
                    if spec.screen_position is None
                    else {"x": spec.screen_position.x, "y": spec.screen_position.y}
                ),
                "slot_anchors": [
                    {"x": point.x, "y": point.y} for point in spec.slot_anchors
                ],
                "theme": spec.theme,
                "visual_bounds": (
                    None
                    if spec.visual_bounds is None
                    else {
                        "height": spec.visual_bounds.height,
                        "width": spec.visual_bounds.width,
                        "x": spec.visual_bounds.x,
                        "y": spec.visual_bounds.y,
                    }
                ),
            }
        )
    return {
        "layout_id": catalog.layout_id,
        "locations": locations,
        "schema_version": catalog.schema_version,
    }


def load_layout(catalog_id: str) -> ObserverLayoutCatalog:
    if type(catalog_id) is not str or not catalog_id or "/" in catalog_id:
        _fail("invalid_layout")
    path = files("observer").joinpath("layouts", f"{catalog_id}.json")
    if not path.is_file():
        _fail("unknown_layout")
    raw = json.loads(path.read_text(encoding="utf-8"))
    catalog = catalog_from_mapping(raw)
    if catalog.layout_id != catalog_id:
        _fail("invalid_layout")
    _LOGGER.debug(
        "layout_loaded catalog_id=%s location_count=%s schema=%s",
        catalog.layout_id,
        len(catalog.specs),
        catalog.schema_version,
    )
    return catalog


def catalog_from_mapping(raw: object) -> ObserverLayoutCatalog:
    document = _record(raw)
    schema = document.get("schema_version")
    layout_id = document.get("layout_id")
    entries = document.get("locations")
    if type(layout_id) is not str or not isinstance(entries, list):
        _fail("invalid_layout")
    specs: list[LocationVisualSpec] = []
    for item in entries:
        entry = _record(item)
        location_id = entry.get("location_id")
        display_name = entry.get("display_name")
        if type(location_id) is not str or type(display_name) is not str:
            _fail("invalid_layout")
        position = entry.get("screen_position")
        bounds = entry.get("visual_bounds")
        anchors_raw = entry.get("connection_anchors") or {}
        slots_raw = entry.get("slot_anchors") or []
        if not isinstance(anchors_raw, dict) or not isinstance(slots_raw, list):
            _fail("invalid_layout", location_id=location_id)
        anchors = tuple(
            (str(neighbor), _point(point, field=str(neighbor)))
            for neighbor, point in anchors_raw.items()
        )
        slots = tuple(_point(point, field="slot") for point in slots_raw)
        specs.append(
            LocationVisualSpec(
                location_id=location_id,
                display_name=display_name,
                screen_position=None
                if position is None
                else _point(position, field="screen"),
                visual_bounds=None if bounds is None else _bounds(bounds),
                theme=_optional_str(entry.get("theme")),
                icon_ref=_optional_str(entry.get("icon_ref")),
                background_ref=_optional_str(entry.get("background_ref")),
                connection_anchors=anchors,
                slot_anchors=slots,
            )
        )
    return ObserverLayoutCatalog(
        layout_id=layout_id,
        schema_version=str(schema),
        specs=tuple(specs),
    )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value:
        _fail("invalid_layout")
    return value


def validate_layout(
    catalog: ObserverLayoutCatalog, locations: Sequence[Location]
) -> None:
    if type(catalog) is not ObserverLayoutCatalog:
        _fail("invalid_layout")
    index: dict[str, Location] = {}
    for location in locations:
        if type(location) is not Location:
            _fail("invalid_layout")
        index[location.entity_id.value] = location
    for spec in catalog.specs:
        if spec.location_id not in index:
            _fail("unknown_location_id", location_id=spec.location_id)
    for spec in catalog.specs:
        location = index[spec.location_id]
        adjacent = {item.value for item in location.adjacent}
        for neighbor, _point_value in spec.connection_anchors:
            if neighbor not in adjacent:
                _fail("visual_edge_not_in_graph", location_id=spec.location_id)


def warn_missing_specs(
    catalog: ObserverLayoutCatalog, location_ids: Sequence[str]
) -> None:
    known = {spec.location_id for spec in catalog.specs}
    for location_id in location_ids:
        if location_id not in known:
            _LOGGER.warning(
                "layout_spec_missing reason_code=%s location_id=%s",
                "layout_spec_missing",
                location_id,
            )


def assign_slots(
    location_id: str,
    occupant_entity_ids: Sequence[str],
    spec: LocationVisualSpec | None,
) -> tuple[SlotAssignment, ...]:
    del location_id
    if isinstance(occupant_entity_ids, (set, frozenset, str, bytes)):
        _fail("unordered_inventory")
    ordered = tuple(sorted(occupant_entity_ids))
    anchors = () if spec is None else spec.slot_anchors
    bounds = None if spec is None else spec.visual_bounds
    assigned: list[SlotAssignment] = []
    for index, entity_id in enumerate(ordered):
        local_x: float | None = None
        local_y: float | None = None
        if index < len(anchors):
            local_x = anchors[index].x
            local_y = anchors[index].y
        elif bounds is not None:
            radius = min(bounds.width, bounds.height) * 0.25
            angle = index * _GOLDEN_ANGLE
            local_x = (bounds.x + bounds.width / 2.0) + radius * math.cos(angle)
            local_y = (bounds.y + bounds.height / 2.0) + radius * math.sin(angle)
        assigned.append(
            SlotAssignment(
                entity_id=entity_id,
                slot_index=index,
                local_x=local_x,
                local_y=local_y,
            )
        )
    return tuple(assigned)


def presentation_for(spec: LocationVisualSpec) -> ObserverPresentation:
    return ObserverPresentation(
        screen_position=spec.screen_position,
        visual_bounds=spec.visual_bounds,
        theme=spec.theme,
        icon_ref=spec.icon_ref,
        background_ref=spec.background_ref,
        connection_anchors=spec.connection_anchors,
        slot_anchors=spec.slot_anchors,
    )


__all__ = [
    "LocationVisualSpec",
    "ObserverLayoutCatalog",
    "ObserverLayoutError",
    "SlotAssignment",
    "assign_slots",
    "catalog_from_mapping",
    "load_layout",
    "presentation_for",
    "validate_layout",
    "warn_missing_specs",
]
