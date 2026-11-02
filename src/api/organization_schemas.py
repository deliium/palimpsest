"""Strict response models for the read-only organization routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OrganizationCoverageOut(_Strict):
    observed: int
    expected: int
    ratio: float | None


class OrganizationSummaryOut(_Strict):
    run_id: str
    publication_id: str
    schema_version: str
    generated_tick: int
    candidate_count: int
    edge_count: int
    window_count: int
    coverage: OrganizationCoverageOut
    provenance_code: str
    snapshot_digest: str
    operation_count: int = 0
    collective_proposal_count: int = 0
    collective_amendment_count: int = 0
    collective_support_count: int = 0
    collective_oppose_count: int = 0
    collective_abstain_count: int = 0
    collective_decision_count: int = 0
    collective_implementation_count: int = 0
    unimplemented_decision_count: int = 0


class OrganizationCollectiveImplementationOut(_Strict):
    implementation_id: str
    actor_ref: str
    status: str
    effect: str
    observed_tick: int
    provenance_code: str
    resolved: bool


class OrganizationCollectiveDecisionOut(_Strict):
    decision_id: str
    organization_id: str
    proposal_ref: str
    revision: int
    procedure_ref: str | None
    recognition: str
    authority_basis: str
    support_count: int
    oppose_count: int
    abstain_count: int
    contest_count: int
    implementation_mode: str
    effect: str
    target_kind: str
    target_ref: str | None
    decided_tick: int
    window_end_tick: int
    implementation_status: str
    provenance_code: str
    resolved: bool
    implementations: tuple[OrganizationCollectiveImplementationOut, ...] = ()


class OrganizationCollectiveAgencyListOut(_Strict):
    publication_id: str
    items: tuple[OrganizationCollectiveDecisionOut, ...]
    next_cursor: str | None
    truncated: bool


class OrganizationMemberOut(_Strict):
    member_id: str
    status: str
    basis: str
    temporal_scope: str
    first_tick: int
    last_tick: int
    expires_tick: int | None
    strength: float
    owner_support_count: int


class OrganizationStructuralOut(_Strict):
    kind: str
    anchor_id: str
    status: str
    first_tick: int
    last_tick: int
    resolved: bool


class OrganizationWindowOut(_Strict):
    window_index: int
    start_tick: int
    end_tick: int
    candidate_ids: tuple[str, ...]
    member_count: int
    overlap_member_count: int
    lane_presence: tuple[tuple[str, bool], ...]


class OrganizationCandidateOut(_Strict):
    organization_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: str
    temporal_scope: str
    self_identified: bool
    member_count: int
    role_count: int
    goal_count: int
    resource_count: int
    procedure_count: int
    record_count: int
    commitment_count: int
    identity_count: int
    structural_channel_count: int
    window_indexes: tuple[int, ...]
    operation_count: int = 0
    contested_operation_count: int = 0
    collective_proposal_count: int = 0
    collective_amendment_count: int = 0
    collective_support_count: int = 0
    collective_oppose_count: int = 0
    collective_abstain_count: int = 0
    collective_decision_count: int = 0
    collective_implementation_count: int = 0
    unimplemented_decision_count: int = 0
    contested_decision_count: int = 0


class OrganizationOperationOut(_Strict):
    operation_id: str
    domain: str
    act: str
    stance: str
    authority_basis: str
    provenance_code: str
    outcome: str
    command_kind: str
    target_kind: str
    anchor_kind: str
    anchor_id: str | None
    tick: int
    first_tick: int
    last_tick: int
    support_count: int
    contest_count: int
    resolved: bool


class OrganizationCandidateDetailOut(OrganizationCandidateOut):
    members: tuple[OrganizationMemberOut, ...]
    structure: tuple[OrganizationStructuralOut, ...]
    operations: tuple[OrganizationOperationOut, ...] = ()
    collective_decisions: tuple[OrganizationCollectiveDecisionOut, ...] = ()


class OrganizationLineageEdgeOut(_Strict):
    kind: str
    tick: int
    from_id: str | None
    to_id: str | None
    jaccard: float | None
    containment: float | None


class OrganizationCandidateListOut(_Strict):
    publication_id: str
    items: tuple[OrganizationCandidateOut, ...]
    next_cursor: str | None
    truncated: bool


class OrganizationLineageListOut(_Strict):
    publication_id: str
    items: tuple[OrganizationLineageEdgeOut, ...]
    next_cursor: str | None
    truncated: bool


class OrganizationOperationListOut(_Strict):
    publication_id: str
    items: tuple[OrganizationOperationOut, ...]
    next_cursor: str | None
    truncated: bool


class OrganizationWindowListOut(_Strict):
    publication_id: str
    items: tuple[OrganizationWindowOut, ...]
