"""Strict frozen response models for emergent-price read routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EmergentPricesMarketsPageOut",
    "EmergentPricesSummaryOut",
    "PriceDistributionOut",
    "PriceDistributionsPageOut",
    "PriceExpectationOut",
    "PriceExpectationsPageOut",
    "PriceMarketOut",
    "PriceQuoteOut",
    "PriceQuotesPageOut",
    "PriceRelationOut",
    "PriceRelationsPageOut",
    "PriceUnitOut",
    "PriceUnitsPageOut",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PriceUnitOut(_Strict):
    unit_token: str
    unit_source: str
    owner_count: int
    expectation_count: int
    distribution_count: int
    median_confidence_milli: int
    unit_alignment: str
    coverage: str


class PriceExpectationOut(_Strict):
    expectation_id: str
    window_index: int
    owner_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    expected_ratio_milli: int
    confidence_milli: int
    level: str
    valuation_reservation: int
    observation_count: int
    quote_count: int
    distribution_source: str
    alignment: str
    coverage: str


class PriceQuoteOut(_Strict):
    quote_id: str
    window_index: int
    venue_id: str
    actor_token: str
    counterparty_token: str
    item_kind: str
    unit_kind: str
    direction: str
    ratio_milli: int
    confidence_milli: int
    source: str
    source_tick: int
    coverage: str


class PriceDistributionOut(_Strict):
    distribution_id: str
    window_index: int
    venue_id: str
    market_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    sample_source: str
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: str
    coverage: str


class PriceMarketOut(_Strict):
    market_token: str
    window_index: int
    venue_count: int
    distribution_count: int
    sample_count: int
    item_kind_count: int
    unit_count: int
    coverage: str


class PriceRelationOut(_Strict):
    relation_id: str
    window_index: int
    group_kind: str
    group_a_token: str
    group_b_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    sample_source: str
    overlap_milli: int
    median_gap_milli: int
    relation: str
    sample_a: int
    sample_b: int
    coverage: str


class EmergentPricesSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    window_tick: int
    window_count: int
    unit_count: int
    expectation_count: int
    quote_count: int
    distribution_count: int
    market_count: int
    relation_count: int
    exchange_count: int
    quote_event_count: int
    evidence_coverage: str
    expectation_coverage: str
    quote_coverage: str
    distribution_coverage: str
    market_coverage: str
    relation_coverage: str
    coverage: str
    truncated: bool


class _PageOut(_Strict):
    run_id: str
    publication_id: str
    window_index: int | None
    next_cursor: str | None
    coverage: str


class PriceUnitsPageOut(_PageOut):
    rows: tuple[PriceUnitOut, ...] = Field(default_factory=tuple)


class PriceExpectationsPageOut(_PageOut):
    rows: tuple[PriceExpectationOut, ...] = Field(default_factory=tuple)


class PriceQuotesPageOut(_PageOut):
    rows: tuple[PriceQuoteOut, ...] = Field(default_factory=tuple)


class PriceDistributionsPageOut(_PageOut):
    rows: tuple[PriceDistributionOut, ...] = Field(default_factory=tuple)


class EmergentPricesMarketsPageOut(_PageOut):
    rows: tuple[PriceMarketOut, ...] = Field(default_factory=tuple)


class PriceRelationsPageOut(_PageOut):
    rows: tuple[PriceRelationOut, ...] = Field(default_factory=tuple)
