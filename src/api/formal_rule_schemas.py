"""Read-only formal-rule API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FormalRuleCoverageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed: int
    expected: int
    partial: bool


class FormalRuleSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    publication_id: str
    schema_version: str
    generated_tick: int
    candidate_count: int
    rule_count: int
    version_count: int
    window_count: int
    coverage: FormalRuleCoverageOut
    provenance_code: str
    snapshot_digest: str


class FormalRuleCandidateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    status: str
    scope_kind: str
    stage: str
    action_token: str
    constraint_kinds: tuple[str, ...]
    authority_kinds: tuple[str, ...]
    system_count: int
    rule_count: int
    version_count: int
    competing_candidate_ids: tuple[str, ...]
    first_tick: int
    last_tick: int


class FormalRuleCandidateDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: FormalRuleCandidateOut
    coverage: FormalRuleCoverageOut


class FormalRuleWrittenRepresentationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    artifact_present: bool
    artifact_revision: int | None
    repository_present: bool


class FormalRuleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    candidate_id: str
    stage: str
    constraint_kind: str
    scope_kind: str
    action_token: str
    authority_kind: str
    recognition: str
    written_representation: FormalRuleWrittenRepresentationOut
    sanction_kinds: tuple[str, ...]
    exception_count: int
    version_count: int
    latest_version: int
    proponent_count: int
    response_counts: tuple[tuple[str, int], ...]


class FormalRuleVersionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: str
    rule_id: str
    version_number: int
    stage: str
    constraint_kind: str
    scope_kind: str
    scope_digest: str
    action_token: str
    authority_kind: str
    recognition: str
    written_representation: FormalRuleWrittenRepresentationOut
    sanction_kinds: tuple[str, ...]
    exception_count: int
    tick: int
    revision_kind: str
    supersedes_version_id: str | None


class FormalRuleLineageEdgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_candidate_id: str
    target_candidate_id: str
    kind: str
    tick: int
    jaccard: float
    containment: float


class FormalRuleCandidatePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FormalRuleCandidateOut]
    next_cursor: str | None = None
    truncated: bool = False


class FormalRulePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FormalRuleOut]
    next_cursor: str | None = None
    truncated: bool = False


class FormalRuleVersionPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FormalRuleVersionOut]
    next_cursor: str | None = None
    truncated: bool = False


class FormalRuleLineagePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FormalRuleLineageEdgeOut]
    next_cursor: str | None = None
    truncated: bool = False


MAX_PAGE_LIMIT = Field(default=100, ge=1, le=500)


__all__ = [
    "FormalRuleCandidateDetailOut",
    "FormalRuleCandidateOut",
    "FormalRuleCandidatePageOut",
    "FormalRuleCoverageOut",
    "FormalRuleLineageEdgeOut",
    "FormalRuleLineagePageOut",
    "FormalRuleOut",
    "FormalRulePageOut",
    "FormalRuleSummaryOut",
    "FormalRuleVersionOut",
    "FormalRuleVersionPageOut",
    "FormalRuleWrittenRepresentationOut",
]
