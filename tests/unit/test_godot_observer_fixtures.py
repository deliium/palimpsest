"""Golden observer payloads stay on observer-protocol-v1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from observer.contracts import (
    ObserverAgent,
    ObserverArtifact,
    ObserverBodyMeasures,
    ObserverContractError,
    ObserverEvent,
    ObserverFrame,
    ObserverItem,
    ObserverLocation,
    ObserverPlaybackCursor,
    ObserverPresentation,
    ObserverResource,
    ObserverWeather,
    ObserverWorldState,
    PresentationSlot,
    ScreenPoint,
    VisualBounds,
)
from observer.presentation import EntityPresentation
from observer.version import OBSERVER_PROTOCOL_VERSION, SEMANTIC_EVENT_TYPES

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "clients" / "godot-observer" / "fixtures" / "protocol"
EVENTS = FIXTURES / "events"
FRAME = FIXTURES / "reference_frame.json"
SMOKE = (
    ROOT
    / "clients"
    / "godot-observer"
    / "fixtures"
    / "smoke"
    / "reference_session.json"
)


_ENVIRONMENT_EVENT_NAMES = frozenset(
    {
        "SEASON_CHANGED",
        "TEMPERATURE_BAND_CHANGED",
        "RESOURCE_NODE_DEPLETED",
        "RESOURCE_NODE_RECOVERED",
        "ENVIRONMENTAL_HAZARD_STARTED",
        "ENVIRONMENTAL_HAZARD_ENDED",
    }
)
_PRODUCTION_EVENT_NAMES = frozenset(
    {
        "RESOURCE_HARVESTED",
        "CRAFT_STARTED",
        "ITEM_CRAFTED",
        "STRUCTURE_BUILT",
        "STRUCTURE_REPAIRED",
        "ITEM_STORED",
    }
)
_ARTIFACT_EVENT_NAMES = frozenset(
    {
        "ARTIFACT_CREATED",
        "ARTIFACT_MODIFIED",
        "ARTIFACT_MOVED",
        "ARTIFACT_DESTROYED",
        "ARTIFACT_COPIED",
        "ARTIFACT_ANNOTATED",
        "ARTIFACT_DAMAGED",
        "ARTIFACT_PARTIALLY_LOST",
    }
)
_LIFECYCLE_EVENT_NAMES = frozenset(
    {
        "AGENT_CREATED",
        "AGENT_ENTERED_WORLD",
        "AGENT_INITIALIZED",
        "LIFECYCLE_STAGE_CHANGED",
    }
)
_REPOSITORY_EVENT_NAMES = frozenset(
    {
        "REPOSITORY_ESTABLISHED",
        "REPOSITORY_MEMBER_DEPOSITED",
        "REPOSITORY_MEMBER_RETRIEVED",
        "REPOSITORY_MAINTAINED",
        "REPOSITORY_INDEXED",
        "REPOSITORY_NEGLECTED",
    }
)


def test_event_fixtures_cover_closed_semantic_types() -> None:
    names = tuple(sorted(path.stem for path in EVENTS.glob("*.json")))
    expected = tuple(
        name
        for name in sorted(SEMANTIC_EVENT_TYPES)
        if name
        not in (
            _ENVIRONMENT_EVENT_NAMES
            | _ARTIFACT_EVENT_NAMES
            | _LIFECYCLE_EVENT_NAMES
            | _REPOSITORY_EVENT_NAMES
        )
    )
    assert names == expected
    assert len(names) == 29
    assert _PRODUCTION_EVENT_NAMES < set(names)
    assert set(names) < set(SEMANTIC_EVENT_TYPES)
    assert _ARTIFACT_EVENT_NAMES < set(SEMANTIC_EVENT_TYPES)
    assert _LIFECYCLE_EVENT_NAMES < set(SEMANTIC_EVENT_TYPES)
    assert _REPOSITORY_EVENT_NAMES < set(SEMANTIC_EVENT_TYPES)
    assert set(names).isdisjoint(_ARTIFACT_EVENT_NAMES)
    assert set(names).isdisjoint(_ENVIRONMENT_EVENT_NAMES)
    assert set(names).isdisjoint(_LIFECYCLE_EVENT_NAMES)
    assert set(names).isdisjoint(_REPOSITORY_EVENT_NAMES)


def test_event_fixtures_construct_observer_events() -> None:
    for path in sorted(EVENTS.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        event = ObserverEvent(**payload)
        assert event.type == path.stem
        assert event.protocol_version == OBSERVER_PROTOCOL_VERSION
        assert event.type in SEMANTIC_EVENT_TYPES


def test_smoke_fixture_keeps_known_events_on_the_protocol() -> None:
    document = json.loads(SMOKE.read_text(encoding="utf-8"))
    unknown_seen = False
    for raw in document["events"]:
        event_type = str(raw["type"])
        if event_type not in SEMANTIC_EVENT_TYPES:
            unknown_seen = True
            with pytest.raises(ObserverContractError):
                ObserverEvent(**raw)
            continue
        event = ObserverEvent(**raw)
        assert event.type == event_type
    assert unknown_seen is True


def test_reference_frame_uses_wire_anchors_and_a_null_cursor() -> None:
    raw = json.loads(FRAME.read_text(encoding="utf-8"))
    camp_anchors = raw["world"]["locations"][0]["presentation"]["connection_anchors"]
    assert isinstance(camp_anchors, list)
    assert camp_anchors[0][0] == "loc-spring"
    assert not isinstance(camp_anchors, dict)
    frame = _frame(raw)
    assert frame.protocol_version == OBSERVER_PROTOCOL_VERSION
    assert frame.cursor.after_tick is None
    assert frame.cursor.after_sequence is None
    assert frame.cursor.sequence is None
    assert tuple(item.location_id for item in frame.world.locations) == (
        "loc-camp",
        "loc-spring",
        "loc-grove",
        "loc-ridge",
    )
    spring = frame.world.locations[1].presentation
    assert spring is not None
    assert spring.screen_position is not None
    assert spring.screen_position.y == -80.0
    assert frame.events is not None
    assert frame.events[0].destination_location_id == "loc-grove"
    assert frame.world.agents[0].location_id == "loc-grove"
    assert frame.events[0].tick <= frame.world.tick


def _frame(payload: dict[str, object]) -> ObserverFrame:
    cursor_raw = _mapping(payload["cursor"])
    world_raw = _mapping(payload["world"])
    events_raw = payload.get("events")
    events = None
    if events_raw is not None:
        events = tuple(ObserverEvent(**_mapping(item)) for item in _items(events_raw))
    return ObserverFrame(
        protocol_version=str(payload["protocol_version"]),
        cursor=ObserverPlaybackCursor(
            run_id=str(cursor_raw["run_id"]),
            mode=_mode(cursor_raw["mode"]),
            tick=int(str(cursor_raw["tick"])),
            protocol_version=str(cursor_raw["protocol_version"]),
            sequence=_optional_int(cursor_raw.get("sequence")),
            after_tick=_optional_int(cursor_raw.get("after_tick")),
            after_sequence=_optional_int(cursor_raw.get("after_sequence")),
        ),
        world=_world(world_raw),
        events=events,
    )


def _world(payload: dict[str, object]) -> ObserverWorldState:
    return ObserverWorldState(
        tick=int(str(payload["tick"])),
        revision=int(str(payload["revision"])),
        locations=tuple(_location(item) for item in _items(payload.get("locations"))),
        agents=tuple(_agent(item) for item in _items(payload.get("agents"))),
        items=tuple(_item(item) for item in _items(payload.get("items"))),
        resources=tuple(_resource(item) for item in _items(payload.get("resources"))),
        weather=tuple(_weather(item) for item in _items(payload.get("weather"))),
        artifacts=tuple(
            _artifact(item) for item in _items(payload.get("artifacts"))
        ),
    )


def _artifact(payload: dict[str, object]) -> ObserverArtifact:
    presentation = None
    presentation_raw = payload.get("presentation")
    if presentation_raw is not None:
        presented = _mapping(presentation_raw)
        presentation = EntityPresentation(
            visual_category=str(presented["visual_category"]),
            icon_key=str(presented["icon_key"]),
            size_category=str(presented["size_category"]),
            display_label=_optional_text(presented.get("display_label")),
        )
    return ObserverArtifact(
        artifact_id=str(payload["artifact_id"]),
        kind=str(payload["kind"]),
        author_id=str(payload["author_id"]),
        created_tick=int(str(payload["created_tick"])),
        content_revision=int(str(payload["content_revision"])),
        location_id=_optional_text(payload.get("location_id")),
        holder_id=_optional_text(payload.get("holder_id")),
        marks=tuple(str(item) for item in _items(payload.get("marks"))),
        presentation=presentation,
    )


def _location(payload: dict[str, object]) -> ObserverLocation:
    return ObserverLocation(
        location_id=str(payload["location_id"]),
        name=str(payload["name"]),
        display_name=str(payload["display_name"]),
        neighbor_ids=tuple(str(item) for item in _items(payload.get("neighbor_ids"))),
        presentation=_presentation(payload.get("presentation")),
    )


def _presentation(value: object) -> ObserverPresentation | None:
    if value is None:
        return None
    payload = _mapping(value)
    anchors: list[tuple[str, ScreenPoint]] = []
    for pair in _items(payload.get("connection_anchors")):
        if not isinstance(pair, list) or len(pair) < 2:
            raise AssertionError("connection_anchors must be wire pairs")
        point = _point(pair[1])
        if point is None:
            raise AssertionError("connection anchor is missing a point")
        anchors.append((str(pair[0]), point))
    slots: list[ScreenPoint] = []
    for item in _items(payload.get("slot_anchors")):
        point = _point(item)
        if point is not None:
            slots.append(point)
    return ObserverPresentation(
        screen_position=_point(payload.get("screen_position")),
        visual_bounds=_bounds(payload.get("visual_bounds")),
        theme=_optional_text(payload.get("theme")),
        icon_ref=_optional_text(payload.get("icon_ref")),
        background_ref=_optional_text(payload.get("background_ref")),
        connection_anchors=tuple(anchors),
        slot_anchors=tuple(slots),
    )


def _agent(payload: dict[str, object]) -> ObserverAgent:
    slot_raw = payload.get("presentation_slot")
    slot = None
    if slot_raw is not None:
        slot_payload = _mapping(slot_raw)
        slot = PresentationSlot(
            slot_index=int(str(slot_payload["slot_index"])),
            local_x=_optional_float(slot_payload.get("local_x")),
            local_y=_optional_float(slot_payload.get("local_y")),
        )
    return ObserverAgent(
        entity_id=str(payload["entity_id"]),
        location_id=str(payload["location_id"]),
        life_status=str(payload["life_status"]),
        inventory_ids=tuple(str(item) for item in _items(payload.get("inventory_ids"))),
        measures=_measures(_mapping(payload["measures"])),
        agent_id=_optional_text(payload.get("agent_id")),
        presentation_slot=slot,
    )


def _measures(payload: dict[str, object]) -> ObserverBodyMeasures:
    return ObserverBodyMeasures(
        health=float(str(payload["health"])),
        hunger=float(str(payload["hunger"])),
        thirst=float(str(payload["thirst"])),
        fatigue=float(str(payload["fatigue"])),
        temperature=float(str(payload["temperature"])),
    )


def _item(payload: dict[str, object]) -> ObserverItem:
    return ObserverItem(
        item_id=str(payload["item_id"]),
        name=str(payload["name"]),
        kind=str(payload["kind"]),
        location_id=_optional_text(payload.get("location_id")),
        holder_id=_optional_text(payload.get("holder_id")),
    )


def _resource(payload: dict[str, object]) -> ObserverResource:
    return ObserverResource(
        resource_id=str(payload["resource_id"]),
        name=str(payload["name"]),
        kind=str(payload["kind"]),
        location_id=str(payload["location_id"]),
        quantity=float(str(payload["quantity"])),
        unit=str(payload["unit"]),
    )


def _weather(payload: dict[str, object]) -> ObserverWeather:
    return ObserverWeather(
        location_id=str(payload["location_id"]),
        condition=str(payload["condition"]),
    )


def _point(value: object) -> ScreenPoint | None:
    if value is None:
        return None
    payload = _mapping(value)
    return ScreenPoint(x=float(str(payload["x"])), y=float(str(payload["y"])))


def _bounds(value: object) -> VisualBounds | None:
    if value is None:
        return None
    payload = _mapping(value)
    return VisualBounds(
        x=float(str(payload["x"])),
        y=float(str(payload["y"])),
        width=float(str(payload["width"])),
        height=float(str(payload["height"])),
    )


def _mode(value: object) -> str:
    mode = str(value)
    if mode not in {"live", "replay"}:
        raise AssertionError(mode)
    return mode


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise AssertionError(type(value).__name__)
    return value


def _items(value: object) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AssertionError(type(value).__name__)
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(str(value))


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(str(value))
