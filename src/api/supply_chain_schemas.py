"""Strict response schemas for read-only supply-chain routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "SupplyBottleneckOut",
    "SupplyBottlenecksPageOut",
    "SupplyChainOut",
    "SupplyChainSummaryOut",
    "SupplyChainsPageOut",
    "SupplyDependenciesPageOut",
    "SupplyDependencyOut",
    "SupplyLineageOut",
    "SupplyLocationOut",
    "SupplyLocationsPageOut",
    "SupplyOrganizationOut",
    "SupplyOrganizationsPageOut",
    "SupplyStageOut",
    "SupplyStagesPageOut",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SupplyStageOut(_Strict):
    stage_token: str
    window_index: int
    recipe_id: str
    action: str
    location_token: str
    actor_token: str
    item_names: list[str]
    completed: bool
    attempt: bool
    duration_ticks: int
    created_item_token: str
    cause: str
    coverage: str


class SupplyDependencyOut(_Strict):
    edge_token: str
    window_index: int
    from_kind: str
    from_token: str
    to_kind: str
    to_token: str
    edge_kind: str
    recipe_id: str
    observed_count: int
    completed_count: int
    share_milli: int
    created_elsewhere_count: int
    coverage: str


class SupplyChainOut(_Strict):
    chain_token: str
    window_index: int
    stage_tokens: list[str]
    edge_tokens: list[str]
    depth: int
    completed_count: int
    coverage: str


class SupplyLineageOut(_Strict):
    chain_token: str
    window_index: int
    status: str
    predecessor_tokens: list[str]
    successor_tokens: list[str]
    shared_edge_count: int
    overlap_milli: int
    coverage: str


class SupplyBottleneckOut(_Strict):
    bottleneck_token: str
    window_index: int
    kind: str
    stage_token: str
    edge_token: str
    observed_count: int
    demand_count: int
    supply_count: int
    ratio_milli: int
    location_token: str
    organization_token: str
    skill_domain: str
    coverage: str


class SupplyLocationOut(_Strict):
    location_token: str
    window_index: int
    observed_count: int
    completed_count: int
    coverage: str


class SupplyOrganizationOut(_Strict):
    organization_token: str
    window_index: int
    actor_count: int
    claim_count: int
    completed_count: int
    coverage: str


class SupplyStagesPageOut(_Strict):
    items: list[SupplyStageOut]
    next_cursor: str | None = None


class SupplyDependenciesPageOut(_Strict):
    items: list[SupplyDependencyOut]
    next_cursor: str | None = None


class SupplyChainsPageOut(_Strict):
    items: list[SupplyChainOut]
    next_cursor: str | None = None


class SupplyBottlenecksPageOut(_Strict):
    items: list[SupplyBottleneckOut]
    next_cursor: str | None = None


class SupplyLocationsPageOut(_Strict):
    items: list[SupplyLocationOut]
    next_cursor: str | None = None


class SupplyOrganizationsPageOut(_Strict):
    items: list[SupplyOrganizationOut]
    next_cursor: str | None = None


class SupplyChainSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    window_tick: int
    stage_count: int
    edge_count: int
    chain_count: int
    lineage_count: int
    bottleneck_count: int
    location_count: int
    organization_count: int
    sustained_chain_count: int
    max_depth: int
    coverage: str
    truncated: bool
