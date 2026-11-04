"""Strict read-only response schemas for representation routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "MAX_PAGE_LIMIT",
    "RepresentationLineageOut",
    "RepresentationLineagePageOut",
    "RepresentationMandateOut",
    "RepresentationMandatePageOut",
    "RepresentationPositionOut",
    "RepresentationPositionPageOut",
    "RepresentationRevocationOut",
    "RepresentationRevocationPageOut",
    "RepresentationSummaryOut",
]

MAX_PAGE_LIMIT = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RepresentationSummaryOut(_Strict):
    run_id: str
    publication_id: str
    snapshot_digest: str
    generated_tick: int
    mandate_count: int
    position_count: int
    revocation_count: int
    conflict_count: int
    candidate_count: int
    lineage_edge_count: int
    owner_count: int
    coverage: str
    schema_version: str


class RepresentationMandateOut(_Strict):
    mandate_id: str
    owner_token: str
    principal_kind: str
    principal_token: str | None = None
    representative_token: str
    scope_kind: str
    scope_subject_token: str | None = None
    duration_kind: str
    start_tick: int
    end_tick: int | None = None
    provenance: str
    status: str
    recognition_basis: str
    support_roots: int
    opposition_roots: int
    confidence_band: str
    coverage: str


class RepresentationPositionOut(_Strict):
    position_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    stance: str
    provenance: str
    tick: int
    active: bool


class RepresentationRevocationOut(_Strict):
    revocation_id: str
    mandate_id: str
    owner_token: str
    actor_token: str
    kind: str
    provenance: str
    tick: int
    contested: bool


class RepresentationLineageOut(_Strict):
    edge_id: str
    from_candidate_id: str
    to_candidate_id: str
    kind: str
    tick: int


class RepresentationMandatePageOut(_Strict):
    items: list[RepresentationMandateOut]
    next_cursor: str | None = None
    truncated: bool = False


class RepresentationPositionPageOut(_Strict):
    items: list[RepresentationPositionOut]
    next_cursor: str | None = None
    truncated: bool = False


class RepresentationRevocationPageOut(_Strict):
    items: list[RepresentationRevocationOut]
    next_cursor: str | None = None
    truncated: bool = False


class RepresentationLineagePageOut(_Strict):
    items: list[RepresentationLineageOut]
    next_cursor: str | None = None
    truncated: bool = False
