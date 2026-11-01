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
    operation_count: int = 0


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
