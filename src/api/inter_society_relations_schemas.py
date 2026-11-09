"""Pydantic response models for inter-society-relations GET routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_LIMIT = 500


class InterSocietyRelationsSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    pair_count: int
    window_count: int
    series_point_count: int
    comparison_count: int
    coverage: str


class InterSocietyDomainPanelOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    event_count: int
    availability: str
    coverage_observed: int
    coverage_expected: int
    values: dict[str, object] = Field(default_factory=dict)


class InterSocietyPairOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    society_a: str
    society_b: str
    window_tick: int
    status: str
    overlap_member_count: int
    panels: tuple[InterSocietyDomainPanelOut, ...]


class InterSocietyPairPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[InterSocietyPairOut, ...]
    next_cursor: str | None = None


class InterSocietySeriesPointOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    window_index: int
    window_start_tick: int
    window_end_tick: int
    panels: tuple[InterSocietyDomainPanelOut, ...]


class InterSocietySeriesPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[InterSocietySeriesPointOut, ...]
    next_cursor: str | None = None


class InterSocietyDomainDeltaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: str
    count_delta: int
    left_availability: str
    right_availability: str


class InterSocietyComparisonOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_pair_id: str
    right_pair_id: str
    left_window_tick: int
    right_window_tick: int
    domain_deltas: tuple[InterSocietyDomainDeltaOut, ...]
