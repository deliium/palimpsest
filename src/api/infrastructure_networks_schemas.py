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
