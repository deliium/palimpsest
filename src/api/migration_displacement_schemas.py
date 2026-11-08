# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Strict read-only schemas for migration-displacement publication."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MigrationDisplacementSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    candidate_count: int = 0
    wave_count: int = 0
    cluster_count: int = 0
    outcome_count: int = 0
    movement_count: int = 0
    cause_count: int = 0
    displacement_like_count: int = 0
    mixed_count: int = 0
    not_displacement_like_count: int = 0
    unknown_count: int = 0
    coverage: str = "not_applicable"


class MigrationWaveOut(_Strict):
    wave_token: str
    origin_token: str
    destination_token: str
    participant_tokens: tuple[str, ...] = ()
    route_tokens: tuple[str, ...] = ()
    start_tick: int
    end_tick: int
    cause_support_counts: tuple[tuple[str, int], ...] = ()
    displacement_classification: str
    displacement_bases: tuple[str, ...] = ()
    independent_cause_count: int = 0
    cluster_tokens: tuple[str, ...] = ()
    coverage: str


class MigrationWaveDetailOut(MigrationWaveOut):
    lineage_tokens: tuple[str, ...] = ()
    alignment_tokens: tuple[str, ...] = ()


class MigrationRouteOut(_Strict):
    route_token: str
    owner_token: str
    origin_token: str
    destination_token: str
    route_tokens: tuple[str, ...] = ()
    observed_duration_ticks: int = 0
    fatigue_cost: float = 0.0
    basis: str
    status: str
    first_tick: int
    last_tick: int


class MigrationCauseOut(_Strict):
    cause_token: str
    owner_token: str
    cause_kind: str
    source_kind: str
    anchor_token: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    tick: int
    status: str


class MigrationOutcomeOut(_Strict):
    outcome_token: str
    participant_token: str
    destination_token: str
    residence_ticks: int = 0
    access_evidence_count: int = 0
    participation_evidence_count: int = 0
    relationship_evidence_count: int = 0
    conflict_evidence_count: int = 0
    classification: str
    coverage: str
    censored: bool = False


class MigrationWavePageOut(_Strict):
    items: tuple[MigrationWaveOut, ...] = ()
    next_cursor: str | None = None


class MigrationRoutePageOut(_Strict):
    items: tuple[MigrationRouteOut, ...] = ()
    next_cursor: str | None = None


class MigrationCausePageOut(_Strict):
    items: tuple[MigrationCauseOut, ...] = ()
    next_cursor: str | None = None


class MigrationOutcomePageOut(_Strict):
    items: tuple[MigrationOutcomeOut, ...] = ()
    next_cursor: str | None = None
