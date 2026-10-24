"""Strict client-neutral lineage HTTP schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LineageCoverageOut(_Strict):
    state: str
    reason_codes: list[str] = Field(default_factory=list, max_length=64)
    capture_start_tick: int | None = Field(default=None, ge=0)
    capture_end_tick: int | None = Field(default=None, ge=0)
    missing_prefix_tick: int | None = Field(default=None, ge=0)
    pruned_count: int = Field(default=0, ge=0)
    unresolved_count: int = Field(default=0, ge=0)
    policy_version: str | None = Field(default=None, max_length=128)


class LineageFamilyOut(_Strict):
    family: str
    available_classes: list[str]
    owner_required: bool
    directions: list[str]
    max_depth: int
    max_nodes: int
    max_edges: int
    max_page_size: int


class LineageSnapshotOut(_Strict):
    publication_id: str = Field(max_length=128)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    boundary_tick: int = Field(ge=0)
    schema_version: str


class LineageNodeRefOut(_Strict):
    run_id: str = Field(max_length=128)
    family: str
    evidence_class: str
    native_kind: str
    native_id: str = Field(max_length=128)
    identity_owner: str | None = Field(default=None, max_length=128)
    key: str = Field(pattern=r"^[0-9a-f]{64}$")


class LineageEvidenceRefOut(_Strict):
    evidence_class: str
    native_kind: str
    native_id: str = Field(max_length=128)
    owner_id: str | None = Field(default=None, max_length=128)
    observed_tick: int | None = Field(default=None, ge=0)


class LineageNodeOut(_Strict):
    ref: LineageNodeRefOut
    state: str
    living: bool | None = None
    observed_tick: int | None = Field(default=None, ge=0)
    status_code: str | None = Field(default=None, max_length=128)
    confidence_code: str | None = Field(default=None, max_length=128)
    confidence_value: float | None = None
    unresolved_reason: str | None = Field(default=None, max_length=128)
    native_revision: str | None = Field(default=None, max_length=128)
    evidence_refs: list[LineageEvidenceRefOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    source_observed_boundary: int | None = Field(default=None, ge=0)


class LineageEdgeOut(_Strict):
    edge_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    relation: str = Field(max_length=128)
    native_kind: str
    native_id: str = Field(max_length=128)
    claim_owner_id: str | None = Field(default=None, max_length=128)
    observed_tick: int | None = Field(default=None, ge=0)
    status_code: str | None = Field(default=None, max_length=128)
    confidence_code: str | None = Field(default=None, max_length=128)
    confidence_value: float | None = None
    source_presence: str
    evidence_refs: list[LineageEvidenceRefOut] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class LineageSnapshotListOut(_Strict):
    schema_version: str
    items: list[LineageSnapshotOut]
    declared_count: int = Field(ge=0)
    next_cursor: str | None = Field(default=None, max_length=4096)
    coverage: LineageCoverageOut | None = None


class LineageNodeListOut(_Strict):
    schema_version: str
    snapshot: LineageSnapshotOut
    items: list[LineageNodeOut]
    matched_node_keys: list[str]
    context_only_node_keys: list[str]
    declared_count: int = Field(ge=0)
    next_cursor: str | None = Field(default=None, max_length=4096)
    coverage: LineageCoverageOut | None = None
    requested_boundary_tick: int | None = Field(default=None, ge=0)
    captured_boundary_tick: int = Field(ge=0)
    effective_page_size: int = Field(ge=1)


class LineageAvailabilityOut(_Strict):
    schema_version: str
    availability: str
    reason_code: str = Field(max_length=128)
    family: str
    evidence_class: str
    requested_boundary_tick: int | None = Field(default=None, ge=0)
    captured_boundary_tick: int | None = Field(default=None, ge=0)


class LineageGraphOut(_Strict):
    schema_version: str
    root: LineageNodeRefOut
    snapshot: LineageSnapshotOut
    nodes: list[LineageNodeOut]
    edges: list[LineageEdgeOut]
    matched_node_keys: list[str]
    context_only_node_keys: list[str]
    visited_node_count: int = Field(ge=0)
    visited_edge_count: int = Field(ge=0)
    stop_reasons: list[str]
    coverage: LineageCoverageOut
    next_cursor: str | None = Field(default=None, max_length=4096)
    requested_boundary_tick: int | None = Field(default=None, ge=0)
    captured_boundary_tick: int = Field(ge=0)
    effective_max_depth: int = Field(ge=0)
    effective_max_nodes: int = Field(ge=1)
    effective_max_edges: int = Field(ge=1)
    effective_page_size: int = Field(ge=1)
