"""Pydantic copies of observer contracts. No fields the domain types lack."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_serializer, model_validator

from api.schemas import StrictModel
from observer.version import OBSERVER_PROTOCOL_VERSION

_OBJECTIVE_LEAK_KEYS = frozenset(
    {
        "relationship",
        "relationships",
        "territorial_claims",
        "spatial_control",
        "territory_owner",
        "controller",
        "semantic_naming",
        "subjective_labels",
        "labels",
    }
)


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


class EntityPresentationOut(StrictModel):
    visual_category: str
    icon_key: str
    size_category: str
    display_label: str | None = None


class ObserverItemOut(StrictModel):
    item_id: str
    name: str
    kind: str
    location_id: str | None = None
    holder_id: str | None = None
    presentation: EntityPresentationOut | None = None


class ObserverResourceOut(StrictModel):
    resource_id: str
    name: str
    kind: str
    location_id: str
    quantity: float
    unit: str
    presentation: EntityPresentationOut | None = None


class ObserverStructureOut(StrictModel):
    structure_id: str
    location_id: str
    kind: str
    integrity: float
    stored_quantity: int
    presentation: EntityPresentationOut | None = None


class ObserverArtifactOut(StrictModel):
    artifact_id: str
    kind: str
    author_id: str
    created_tick: int
    content_revision: int
    location_id: str | None = None
    holder_id: str | None = None
    marks: tuple[str, ...] = ()
    presentation: EntityPresentationOut | None = None


class ObserverWeatherOut(StrictModel):
    location_id: str
    condition: str


class ObserverTemperatureBandOut(StrictModel):
    location_id: str
    band: str


class ObserverHazardOut(StrictModel):
    location_id: str
    hazard_kind: str
    remaining_ticks: int


class ObserverWorldStateOut(StrictModel):
    tick: int
    revision: int
    locations: tuple[ObserverLocationOut, ...] = ()
    agents: tuple[ObserverAgentOut, ...] = ()
    items: tuple[ObserverItemOut, ...] = ()
    resources: tuple[ObserverResourceOut, ...] = ()
    weather: tuple[ObserverWeatherOut, ...] = ()
    structures: tuple[ObserverStructureOut, ...] = ()
    artifacts: tuple[ObserverArtifactOut, ...] = ()
    season: str | None = None
    temperature_bands: tuple[ObserverTemperatureBandOut, ...] = ()
    hazards: tuple[ObserverHazardOut, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def _reject_non_objective_keys(cls, data: object) -> object:
        if isinstance(data, dict):
            leaked = _OBJECTIVE_LEAK_KEYS.intersection(data)
            if leaked:
                name = sorted(leaked)[0]
                raise ValueError(f"objective_leak:{name}")
        return data

    @model_serializer(mode="wrap")
    def _omit_absent_environment(self, handler: object) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("observer world serializer requires a mapping")
        if payload.get("season") is None:
            payload.pop("season", None)
            payload.pop("temperature_bands", None)
            payload.pop("hazards", None)
        return payload


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
    recipe_id: str | None = None
    structure_id: str | None = None
    artifact_id: str | None = None
    season: str | None = None
    temperature_band: str | None = None
    hazard_kind: str | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_environment(self, handler: object) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("observer event serializer requires a mapping")
        for key in ("season", "temperature_band", "hazard_kind", "artifact_id"):
            if payload.get(key) is None:
                payload.pop(key, None)
        return payload


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


class ObserverLabelReadingOut(StrictModel):
    objective_id: str
    objective_display_name: str
    referent_kind: str
    label_token: str
    label_display: str
    sense_revision: int = Field(ge=0)
    strength_band: Literal["candidate", "low", "mid", "high"]
    label_source: Literal["agent_perspective"] = "agent_perspective"


class ObserverLabelOverlayOut(StrictModel):
    run_id: str
    agent_id: str
    layer: Literal["subjective_labels"] = "subjective_labels"
    protocol_version: str = OBSERVER_PROTOCOL_VERSION
    count: int
    readings: tuple[ObserverLabelReadingOut, ...]


__all__ = [
    "ObserverAgentOut",
    "ObserverEventOut",
    "ObserverEventPageOut",
    "ObserverFrameOut",
    "ObserverLabelOverlayOut",
    "ObserverManifestOut",
    "ObserverRelationshipPageOut",
    "ObserverRunOut",
    "ObserverTickPageOut",
]
