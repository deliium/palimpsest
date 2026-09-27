"""Pydantic copies of observer contracts. No fields the domain types lack."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from api.schemas import StrictModel
from observer.version import OBSERVER_PROTOCOL_VERSION


class ScreenPointOut(StrictModel):
    x: float
    y: float


class VisualBoundsOut(StrictModel):
    x: float
    y: float
    width: float
    height: float


class PresentationSlotOut(StrictModel):
    slot_index: int
    local_x: float | None = None
    local_y: float | None = None


class ObserverPresentationOut(StrictModel):
    screen_position: ScreenPointOut | None = None
    visual_bounds: VisualBoundsOut | None = None
    theme: str | None = None
    icon_ref: str | None = None
    background_ref: str | None = None
    connection_anchors: tuple[tuple[str, ScreenPointOut], ...] = ()
    slot_anchors: tuple[ScreenPointOut, ...] = ()


class ObserverLocationOut(StrictModel):
    location_id: str
    name: str
    display_name: str
    neighbor_ids: tuple[str, ...]
    presentation: ObserverPresentationOut | None = None


class ObserverBodyMeasuresOut(StrictModel):
    health: float
    hunger: float
    thirst: float
    fatigue: float
    temperature: float


class ObserverAgentOut(StrictModel):
    entity_id: str
    location_id: str
    life_status: str
    inventory_ids: tuple[str, ...]
    measures: ObserverBodyMeasuresOut
    agent_id: str | None = None
    presentation_slot: PresentationSlotOut | None = None


class ObserverItemOut(StrictModel):
    item_id: str
    name: str
    kind: str
    location_id: str | None = None
    holder_id: str | None = None


class ObserverResourceOut(StrictModel):
    resource_id: str
    name: str
    kind: str
    location_id: str
    quantity: float
    unit: str


class ObserverWeatherOut(StrictModel):
    location_id: str
    condition: str


class ObserverWorldStateOut(StrictModel):
    tick: int
    revision: int
    locations: tuple[ObserverLocationOut, ...] = ()
    agents: tuple[ObserverAgentOut, ...] = ()
    items: tuple[ObserverItemOut, ...] = ()
    resources: tuple[ObserverResourceOut, ...] = ()
    weather: tuple[ObserverWeatherOut, ...] = ()


class ObserverEventOut(StrictModel):
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


class ObserverPlaybackCursorOut(StrictModel):
    run_id: str
    mode: Literal["live", "replay"]
    tick: int
    protocol_version: str
    sequence: int | None = None
    after_tick: int | None = None
    after_sequence: int | None = None


class ObserverFrameOut(StrictModel):
    protocol_version: str
    cursor: ObserverPlaybackCursorOut
    world: ObserverWorldStateOut
    events: tuple[ObserverEventOut, ...] | None = None


class ObserverManifestOut(StrictModel):
    protocol_version: str = OBSERVER_PROTOCOL_VERSION
    layout_schema_version: str
    layout_id: str
    layout_hash: str
    ordering: Literal["tick_sequence"]
    read_only: Literal[True]
    event_types: tuple[str, ...]
    event_schema_version: int
    projector_version: str


class ObserverEventPageOut(StrictModel):
    run_id: str
    count: int
    events: tuple[ObserverEventOut, ...]
    limit: int = Field(ge=1)


class ObserverTickSummaryOut(StrictModel):
    tick: int
    event_count: int
    first_sequence: int | None = None
    last_sequence: int | None = None


class ObserverTickPageOut(StrictModel):
    run_id: str
    count: int
    ticks: tuple[ObserverTickSummaryOut, ...]


class ObserverRunOut(StrictModel):
    run_id: str
    world_id: str
    availability: Literal["available"]
    protocol_version: str
    event_schema_version: int
    projector_version: str
    tick: int
    latest_tick: int | None = None
    latest_sequence: int | None = None


class ObserverDimensionScoreOut(StrictModel):
    dimension: str
    value: float


class ObserverRelationshipSummaryOut(StrictModel):
    owner_id: str
    target_id: str
    dimensions: tuple[ObserverDimensionScoreOut, ...]
    protocol_version: str


class ObserverRelationshipPageOut(StrictModel):
    run_id: str
    owner_id: str
    count: int
    items: tuple[ObserverRelationshipSummaryOut, ...]


__all__ = [
    "ObserverAgentOut",
    "ObserverEventOut",
    "ObserverEventPageOut",
    "ObserverFrameOut",
    "ObserverManifestOut",
    "ObserverRelationshipPageOut",
    "ObserverRunOut",
    "ObserverTickPageOut",
]
