"""Strict read-only schemas for market-institution API responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "MarketCandidateOut",
    "MarketExpectationOut",
    "MarketGatheringOut",
    "MarketInstitutionsSummaryOut",
    "MarketLineageOut",
    "MarketMarketsPageOut",
    "MarketRecordOut",
    "MarketRecordsPageOut",
    "MarketRoleOut",
    "MarketRolesPageOut",
    "MarketVenueOut",
    "MarketVenuesPageOut",
]

_STRICT = ConfigDict(extra="forbid", frozen=True)


class _Base(BaseModel):
    model_config = _STRICT


class MarketVenueOut(_Base):
    venue_id: str
    window_index: int
    location_id: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    distinct_actor_count: int
    active_window_count: int
    recurrence_milli: int
    status: str
    market_like: bool
    coverage: str


class MarketGatheringOut(_Base):
    venue_id: str
    window_index: int
    location_id: str
    exchange_count: int
    proposal_count: int
    withdrawn_count: int
    distinct_party_count: int
    status: str
    coverage: str


class MarketExpectationOut(_Base):
    venue_id: str
    window_index: int
    owner_token: str
    expectation: str
    cadence: str
    interval_ticks: int | None
    phase_tick: int | None
    schedule_window_index: int | None
    confidence_milli: int
    evidence_count: int
    alignment: str
    coverage: str


class MarketRoleOut(_Base):
    venue_id: str
    window_index: int
    actor_token: str
    role_kind: str
    role_basis: str
    recognized: bool
    exchange_count: int
    counterparty_count: int
    active_window_count: int
    coverage: str


class MarketRecordOut(_Base):
    venue_id: str
    window_index: int
    record_kind: str
    anchor_token: str
    owner_row_count: int
    coverage: str


class MarketCandidateOut(_Base):
    market_id: str
    window_index: int
    venue_ids: list[str]
    exchange_count: int
    distinct_party_count: int
    coverage: str


class MarketLineageOut(_Base):
    window_index: int
    market_id: str
    venue_ids: list[str]
    party_count: int
    status: str
    previous_market_ids: list[str]
    next_market_ids: list[str]
    rerouted: bool
    sustained: bool
    coverage: str


class MarketInstitutionsSummaryOut(_Base):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    window_tick: int
    venue_count: int
    gathering_count: int
    market_like_venue_count: int
    recurring_venue_count: int
    expected_venue_count: int
    market_count: int
    expectation_row_count: int
    role_row_count: int
    record_anchor_count: int
    emerged_count: int
    continued_count: int
    transformed_count: int
    split_count: int
    merge_count: int
    dissolved_count: int
    sustained_market_count: int
    lineage_edge_count: int
    coverage: str
    truncated: bool


class MarketVenuesPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["venues"] = "venues"
    window_index: int | None
    rows: list[MarketVenueOut]
    next_cursor: str | None
    coverage: str


class MarketGatheringsPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["gatherings"] = "gatherings"
    window_index: int | None
    rows: list[MarketGatheringOut]
    next_cursor: str | None
    coverage: str


class MarketExpectationsPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["expectations"] = "expectations"
    window_index: int | None
    rows: list[MarketExpectationOut]
    next_cursor: str | None
    coverage: str


class MarketRolesPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["roles"] = "roles"
    window_index: int | None
    rows: list[MarketRoleOut]
    next_cursor: str | None
    coverage: str


class MarketRecordsPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["records"] = "records"
    window_index: int | None
    rows: list[MarketRecordOut]
    next_cursor: str | None
    coverage: str


class MarketMarketsPageOut(_Base):
    run_id: str
    publication_id: str
    purpose: Literal["markets"] = "markets"
    window_index: int | None
    rows: list[MarketCandidateOut]
    lineage: list[MarketLineageOut]
    next_cursor: str | None
    coverage: str
