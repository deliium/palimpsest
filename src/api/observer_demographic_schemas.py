"""Strict, independently versioned demographic observer response schemas."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from api.schemas import StrictModel

DEMOGRAPHICS_SCHEMA_VERSION: Final[Literal["observer-demographics-v1"]] = (
    "observer-demographics-v1"
)
GENERATION_MARKERS_SCHEMA_VERSION: Final[Literal["observer-generation-markers-v1"]] = (
    "observer-generation-markers-v1"
)


class DemographicPopulationOut(StrictModel):
    living: int = Field(ge=0)
    admitted: int = Field(ge=0)
    dead: int = Field(ge=0)
    max_generation_index: int = Field(ge=0)


class DemographicStageRowOut(StrictModel):
    stage: str
    life_status: Literal["alive", "dead"]
    count: int = Field(ge=0)


class DemographicAgentRowOut(StrictModel):
    agent_id: str
    entity_id: str
    entry_tick: int = Field(ge=0)
    generation_index: int = Field(ge=0)
    cohort_id: str
    stage: str
    dependency_status: Literal["dependent", "independent"]
    life_status: Literal["alive", "dead"]
    age_ticks: int | None = Field(default=None, ge=0)
    age_reason_code: Literal["dead_age_not_projected"] | None = None


class DemographicCohortRowOut(StrictModel):
    generation_index: int = Field(ge=0)
    entry_tick: int = Field(ge=0)
    cohort_id: str
    admitted: int = Field(ge=0)
    living: int = Field(ge=0)
    dead: int = Field(ge=0)


class DemographicGenerationRowOut(StrictModel):
    generation_index: int = Field(ge=0)
    admitted: int = Field(ge=0)
    living: int = Field(ge=0)
    dead: int = Field(ge=0)


class ObserverDemographicsOut(StrictModel):
    schema_version: Literal["observer-demographics-v1"] = DEMOGRAPHICS_SCHEMA_VERSION
    run_id: str
    requested_tick: int = Field(ge=0)
    requested_through_sequence: int | None = Field(default=None, ge=0)
    resolved_tick: int = Field(ge=0)
    revision: int = Field(ge=0)
    evidence_class: Literal["objective"] = "objective"
    availability: Literal["available", "unavailable"]
    reason_code: Literal["lifecycle_disabled"] | None = None
    section: Literal["agents", "cohorts", "generations"]
    selection_state: Literal["all", "selected", "not_present_at_cursor", "unavailable"]
    population: DemographicPopulationOut | None = None
    stage_rows: tuple[DemographicStageRowOut, ...] = ()
    stage_counts_truncated: bool = False
    agents: tuple[DemographicAgentRowOut, ...] = ()
    cohorts: tuple[DemographicCohortRowOut, ...] = ()
    generations: tuple[DemographicGenerationRowOut, ...] = ()
    next_after_agent_id: str | None = None
    next_after_group_key: str | None = None
    limit: int = Field(ge=1, le=200)


class GenerationMarkerRowOut(StrictModel):
    generation_index: int = Field(ge=0)
    first_entry_tick: int = Field(ge=0)
    seek_tick: int = Field(ge=0)
    admitted_count: int = Field(ge=1)
    label_code: Literal["founders", "generation_first_admission"]


class ObserverGenerationMarkersOut(StrictModel):
    schema_version: Literal["observer-generation-markers-v1"] = (
        GENERATION_MARKERS_SCHEMA_VERSION
    )
    run_id: str
    requested_tick: int = Field(ge=0)
    resolved_tick: int = Field(ge=0)
    revision: int = Field(ge=0)
    evidence_class: Literal["objective"] = "objective"
    availability: Literal["available", "unavailable"]
    reason_code: Literal["lifecycle_disabled"] | None = None
    markers: tuple[GenerationMarkerRowOut, ...] = ()
    next_after_generation_index: int | None = Field(default=None, ge=0)
    limit: int = Field(ge=1, le=200)
