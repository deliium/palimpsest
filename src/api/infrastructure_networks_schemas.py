"""Pydantic response models for infrastructure-networks GET routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

MAX_PAGE_LIMIT = 500


class InfrastructureNetworksSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    asset_count: int
    node_count: int
    edge_count: int
    operational_count: int
    damaged_count: int
    destroyed_count: int
    effects_active_count: int
    coverage: str
    route_count: int = 0
    route_open_count: int = 0
    route_restricted_count: int = 0
    route_closed_count: int = 0
    route_weather_count: int = 0
    route_seasonal_count: int = 0
    route_hazard_count: int = 0


class InfrastructureAssetOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    kind: str
    topology: str
    status: str
    integrity: float
    location_id: str
    endpoint_location_id: str | None = None
    effects_active: bool
    created_tick: int
    last_maintained_tick: int
    ticks_since_maintained: int
    linked_project_id: str
    linked_structure_id: str | None = None


class InfrastructureAssetPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[InfrastructureAssetOut, ...]
    next_cursor: str | None = None


class TravelRouteOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_location_id: str
    destination_location_id: str
    status: str
    seasonal_availability: str
    blockage_cause: str
    duration_ticks: int
    fatigue_cost: float
    capacity: int
    risk: float
    infrastructure_quality: float
    as_of_tick: int


class TravelRoutePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[TravelRouteOut, ...]
    next_cursor: str | None = None
    fingerprint: str
    publication: str
