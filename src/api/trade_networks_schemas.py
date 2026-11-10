"""Strict response schemas for read-only trade-network routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "CrossSocietyPageOut",
    "CrossSocietyTradeOut",
    "DependencePageOut",
    "TradeCorridorOut",
    "TradeCorridorsPageOut",
    "TradeDependenceOut",
    "TradeFlowOut",
    "TradeFlowsPageOut",
    "TradeLocationOut",
    "TradeLocationsPageOut",
    "TradeNetworkOut",
    "TradeNetworksPageOut",
    "TradeNetworksSummaryOut",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TradeCorridorOut(_Strict):
    corridor_id: str
    window_index: int
    from_location_id: str
    to_location_id: str
    flow_counts: dict[str, int]
    transfer_count: int
    coverage: str


class TradeFlowOut(_Strict):
    window_index: int
    flow_class: str
    transfer_count: int
    cross_location_count: int
    imported_count: int
    exported_count: int
    local_count: int
    coverage: str


class TradeLocationOut(_Strict):
    location_id: str
    window_index: int
    inflow_count: int
    outflow_count: int
    local_count: int
    corridor_degree: int
    is_major: bool
    trade_post_present: bool
    flow_counts: dict[str, int]
    coverage: str


class TradeDependenceOut(_Strict):
    location_id: str
    window_index: int
    flow_class: str
    imported_count: int
    locally_originated_count: int
    dependence_milli: int | None
    high_dependence: bool
    coverage: str


class CrossSocietyTradeOut(_Strict):
    pair_id: str
    window_index: int
    society_a: str
    society_b: str
    society_a_location_id: str
    society_b_location_id: str
    overlap_member_count: int
    flow_counts: dict[str, int]
    transfer_count: int
    society_a_to_b_count: int
    society_b_to_a_count: int
    coverage: str


class TradeNetworkOut(_Strict):
    network_id: str
    window_index: int
    corridor_ids: list[str]
    location_ids: list[str]
    flow_counts: dict[str, int]
    transfer_count: int
    status: str
    previous_network_ids: list[str]
    next_network_ids: list[str]
    rerouted: bool
    sustained: bool
    coverage: str


class TradeCorridorsPageOut(_Strict):
    items: list[TradeCorridorOut]
    next_cursor: str | None = None


class TradeFlowsPageOut(_Strict):
    items: list[TradeFlowOut]
    next_cursor: str | None = None


class TradeLocationsPageOut(_Strict):
    items: list[TradeLocationOut]
    next_cursor: str | None = None


class DependencePageOut(_Strict):
    items: list[TradeDependenceOut]
    next_cursor: str | None = None


class CrossSocietyPageOut(_Strict):
    items: list[CrossSocietyTradeOut]
    next_cursor: str | None = None


class TradeNetworksPageOut(_Strict):
    items: list[TradeNetworkOut]
    next_cursor: str | None = None


class TradeNetworksSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    window_tick: int
    corridor_count: int
    flow_count: int
    location_count: int
    major_location_count: int
    trade_post_location_count: int
    network_count: int
    cross_society_pair_count: int
    transfer_count: int
    emerged_count: int
    continued_count: int
    transformed_count: int
    split_count: int
    merge_count: int
    dissolved_count: int
    rerouted_count: int
    sustained_network_count: int
    lineage_edge_count: int
    coverage: str
    truncated: bool

