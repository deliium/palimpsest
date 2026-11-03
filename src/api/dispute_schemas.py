"""Read-only dispute API response models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DisputeCoverageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed: int
    expected: int
    ratio: float | None
    note: str


class DisputeSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    publication_id: str
    schema_version: str
    generated_tick: int
    candidate_count: int
    case_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    accepted_count: int
    rejected_count: int
    edge_count: int
    window_count: int
    coverage: DisputeCoverageOut
    provenance_code: str
    snapshot_digest: str


class DisputeCandidateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    kind: str
    subject_token: str
    party_count: int
    owner_count: int
    case_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    disagreement_count: int
    status: str
    first_tick: int
    last_tick: int
    coverage: DisputeCoverageOut


class DisputeClaimOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    case_ref: str
    claimant_id: str
    respondent_id: str
    role: str
    claim_kind: str
    polarity: str
    subject_token: str
    counters_claim_ref: str | None
    evidence_count: int
    first_tick: int
    last_tick: int
    candidate_id: str


class DisputeTestimonyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    testimony_id: str
    case_ref: str
    claim_id: str
    speaker_id: str
    channel: str
    root_token: str
    independently_evidenced: bool
    tick: int


class DisputeEvidenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    case_ref: str
    claim_id: str
    channel: str
    reference_kind: str
    reference_token: str
    tick: int
    independently_evidenced: bool


class DisputeRuleReferenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_reference_id: str
    case_ref: str
    claim_ref: str
    system_token: str
    rule_token: str
    version_number: int
    applicability: str
    interpretation: str
    status: str


class DisputeAuthorityReferenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_reference_id: str
    case_ref: str
    authority_kind: str
    reference_token: str
    strength: float
    uncertainty: float
    dissenting: bool


class DisputeMediationReferenceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mediation_reference_id: str
    case_ref: str
    mediation_case_token: str
    recommendation_token: str | None
    response_token: str | None
    outcome_token: str | None
    link_status: str


class DisputeResolutionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_id: str
    resolution_ref: str
    case_ref: str
    proposer_id: str
    source: str
    terms_digest: str
    status: str
    first_tick: int
    last_tick: int
    expires_tick: int | None
    accepted_party_count: int
    rejected_party_count: int
    candidate_id: str


class DisputeResolutionResponseOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: str
    resolution_ref: str
    party_id: str
    kind: str
    tick: int
    terms_digest: str
    active: bool


class DisputeCandidateDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: DisputeCandidateOut
    coverage: DisputeCoverageOut
    testimony: list[DisputeTestimonyOut] = Field(default_factory=list)
    evidence: list[DisputeEvidenceOut] = Field(default_factory=list)
    rule_references: list[DisputeRuleReferenceOut] = Field(default_factory=list)
    authority_references: list[DisputeAuthorityReferenceOut] = Field(
        default_factory=list
    )
    mediation_references: list[DisputeMediationReferenceOut] = Field(
        default_factory=list
    )
    responses: list[DisputeResolutionResponseOut] = Field(default_factory=list)
    truncated: bool = False


class DisputeLineageEdgeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source: str
    target: str
    kind: str
    tick: int


class DisputeCandidatePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DisputeCandidateOut]
    next_cursor: str | None = None
    truncated: bool = False


class DisputeClaimPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DisputeClaimOut]
    next_cursor: str | None = None
    truncated: bool = False


class DisputeResolutionPageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DisputeResolutionOut]
    next_cursor: str | None = None
    truncated: bool = False


class DisputeLineagePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DisputeLineageEdgeOut]
    next_cursor: str | None = None
    truncated: bool = False


MAX_PAGE_LIMIT = Field(default=100, ge=1, le=500)


__all__ = [
    "DisputeAuthorityReferenceOut",
    "DisputeCandidateDetailOut",
    "DisputeCandidateOut",
    "DisputeCandidatePageOut",
    "DisputeClaimOut",
    "DisputeClaimPageOut",
    "DisputeCoverageOut",
    "DisputeEvidenceOut",
    "DisputeLineageEdgeOut",
    "DisputeLineagePageOut",
    "DisputeMediationReferenceOut",
    "DisputeResolutionOut",
    "DisputeResolutionPageOut",
    "DisputeResolutionResponseOut",
    "DisputeRuleReferenceOut",
    "DisputeSummaryOut",
    "DisputeTestimonyOut",
]
