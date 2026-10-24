"""Strict `lineage-participants-v1` envelope and native participant cards."""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from api.lineage_schemas import (
    LineageCoverageOut,
    LineageEvidenceRefOut,
    LineageNodeRefOut,
    LineageSnapshotOut,
)
from api.schemas import StrictModel

PARTICIPANTS_SCHEMA_VERSION: Final[Literal["lineage-participants-v1"]] = (
    "lineage-participants-v1"
)


class LineageParticipantCardOut(StrictModel):
    ref: LineageNodeRefOut
    teacher_id: str = Field(max_length=128)
    learner_id: str = Field(max_length=128)
    owner_id: str = Field(max_length=128)
    lineage_id: str = Field(max_length=128)
    root_id: str = Field(max_length=128)
    parent_ids: list[str] = Field(default_factory=list, max_length=64)
    content_kind: str = Field(max_length=128)
    content_key: str = Field(max_length=256)
    hop: int = Field(ge=0)
    acquisition_tick: int = Field(ge=0)
    update_tick: int = Field(ge=0)
    attempt_count: int = Field(ge=0)
    learning_evidence_count: int = Field(ge=0)
    confidence_band: str | None = Field(default=None, max_length=128)
    mutated: bool
    native_status: str | None = Field(default=None, max_length=128)
    evidence_refs: list[LineageEvidenceRefOut] = Field(
        default_factory=list, max_length=64
    )
    policy_version: str = Field(max_length=128)
    observed_boundary: int = Field(ge=0)
    source_observed_boundary: int = Field(ge=0)
    learning_state: Literal["attempt_only", "learning_evidence"]


class LineageParticipantsOut(StrictModel):
    schema_version: Literal["lineage-participants-v1"] = (
        PARTICIPANTS_SCHEMA_VERSION
    )
    snapshot: LineageSnapshotOut
    requested_boundary_tick: int | None = Field(default=None, ge=0)
    captured_boundary_tick: int = Field(ge=0)
    family: Literal["mentorship"] = "mentorship"
    evidence_class: Literal["subjective", "analytical"]
    owner_id: str | None = Field(default=None, max_length=128)
    agent_id: str = Field(max_length=128)
    role: Literal["teacher", "learner", "both"]
    items: list[LineageParticipantCardOut] = Field(default_factory=list)
    scanned_count: int = Field(ge=0, le=200)
    unprojectable_count: int = Field(ge=0, le=200)
    scan_limited: bool = False
    coverage: LineageCoverageOut
    next_cursor: str | None = Field(default=None, max_length=4096)
    effective_page_size: int = Field(ge=1, le=200)
