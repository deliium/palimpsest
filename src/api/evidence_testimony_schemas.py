"""Strict read-only response schemas for evidence-testimony routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MAX_PAGE_LIMIT",
    "EvidenceCandidateDetailOut",
    "EvidenceCandidateOut",
    "EvidenceCandidatePageOut",
    "EvidenceContradictionOut",
    "EvidenceContradictionPageOut",
    "EvidenceLineageEdgeOut",
    "EvidenceLineagePageOut",
    "EvidenceSourceOut",
    "EvidenceSourcePageOut",
    "EvidenceSummaryOut",
]

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceSummaryOut(_Strict):
    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    candidate_count: int
    source_count: int
    testimony_count: int
    item_count: int
    custody_link_count: int
    contradiction_count: int
    evaluation_count: int
    edge_count: int
    coverage: str
    schema_version: str
    window_count: int
    provenance_code: str


class EvidenceCandidateOut(_Strict):
    candidate_id: str
    subject_token: str
    source_kind_family: str
    owner_count: int
    item_count: int
    source_count: int
    testimony_count: int
    contradiction_count: int
    status: str
    coverage: str
    first_tick: int
    last_tick: int


class EvidenceSourceOut(_Strict):
    owner_token: str
    local_id: str
    source_kind: str
    reference_kind: str
    provenance: str
    confidence_band: str
    tick: int
    subject_token: str
    custody_status: str
    root_ref: str | None = None
    correlation_token: str | None = None


class EvidenceContradictionOut(_Strict):
    owner_token: str
    local_id: str
    candidate_id: str
    first_ref: str
    second_ref: str
    kind: str
    status: str
    tick: int


class EvidenceLineageEdgeOut(_Strict):
    edge_id: str
    kind: str
    source_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    window_index: int


class EvidenceCandidatePageOut(_Strict):
    items: list[EvidenceCandidateOut]
    next_cursor: str | None = None
    truncated: bool = False


class EvidenceSourcePageOut(_Strict):
    items: list[EvidenceSourceOut]
    next_cursor: str | None = None
    truncated: bool = False


class EvidenceContradictionPageOut(_Strict):
    items: list[EvidenceContradictionOut]
    next_cursor: str | None = None
    truncated: bool = False


class EvidenceLineagePageOut(_Strict):
    items: list[EvidenceLineageEdgeOut]
    next_cursor: str | None = None
    truncated: bool = False


class EvidenceCandidateDetailOut(_Strict):
    candidate: EvidenceCandidateOut
    sources: list[EvidenceSourceOut]
    contradictions: list[EvidenceContradictionOut]
    custody_complete_count: int = 0
    custody_incomplete_count: int = 0
    custody_conflicting_count: int = 0
    sources_truncated: bool = False
    contradictions_truncated: bool = False
    alignment_label: str = Field(default="researcher-only")
