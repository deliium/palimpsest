"""Closed historical-lineage query DTOs.

Sibling research/query schemas only: these contracts are not runner, replay,
result or observer protocol versions and never feed simulation behavior.

Framework-free. No persistence, API, analysis, experiments or ORM imports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
    require_lineage_key,
    require_supported_scope_owner,
)
from simulation.models import RunId
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "DEFAULT_LINEAGE_MAX_DEPTH",
    "DEFAULT_LINEAGE_MAX_EDGES",
    "DEFAULT_LINEAGE_MAX_NODES",
    "DEFAULT_LINEAGE_PAGE_SIZE",
    "LINEAGE_GRAPH_PAGE_SCHEMA_VERSION",
    "LINEAGE_SNAPSHOT_SCHEMA_VERSION",
    "MAX_LINEAGE_MAX_DEPTH",
    "MAX_LINEAGE_MAX_EDGES",
    "MAX_LINEAGE_MAX_NODES",
    "MAX_LINEAGE_PAGE_SIZE",
    "LineageCoverage",
    "LineageCoverageState",
    "LineageDirection",
    "LineageEdge",
    "LineageError",
    "LineageNode",
    "LineageNodeState",
    "LineagePage",
    "LineageQuery",
    "LineageScope",
    "LineageSnapshotRef",
    "MentorshipLineageRecord",
    "require_lineage_cursor",
]

LINEAGE_SNAPSHOT_SCHEMA_VERSION: Final[str] = "lineage-snapshot-v1"
LINEAGE_GRAPH_PAGE_SCHEMA_VERSION: Final[str] = "lineage-graph-page-v1"

DEFAULT_LINEAGE_MAX_DEPTH: Final[int] = 4
MAX_LINEAGE_MAX_DEPTH: Final[int] = 32
DEFAULT_LINEAGE_MAX_NODES: Final[int] = 200
MAX_LINEAGE_MAX_NODES: Final[int] = 1_000
DEFAULT_LINEAGE_MAX_EDGES: Final[int] = 500
MAX_LINEAGE_MAX_EDGES: Final[int] = 4_000
DEFAULT_LINEAGE_PAGE_SIZE: Final[int] = 100
MAX_LINEAGE_PAGE_SIZE: Final[int] = 200

_MAX_CURSOR_LENGTH: Final[int] = 4_096


class LineageError(ValueError):
    """Stable lineage error carrying only a safe reason code."""

    def __init__(self, code: str) -> None:
        self.code = require_stable_id("LineageError.code", code)
        super().__init__(self.code)


class LineageDirection(StrEnum):
    """Traversal direction over native edges (orientation is always preserved)."""

    ANCESTORS = "ancestors"
    DESCENDANTS = "descendants"
    BOTH = "both"


class LineageNodeState(StrEnum):
    """Retention state of a node descriptor."""

    OBSERVED = "observed"
    ARCHIVED = "archived"
    UNRESOLVED = "unresolved"


class LineageCoverageState(StrEnum):
    """Availability of captured evidence for a scope."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


def require_lineage_cursor(value: object) -> str:
    """Validate an opaque continuation token (bounded, no control characters)."""
    if not isinstance(value, str):
        raise ValueError("lineage cursor must be a str")
    if not 1 <= len(value) <= _MAX_CURSOR_LENGTH:
        raise ValueError("lineage cursor length is invalid")
    if value != value.strip():
        raise ValueError("lineage cursor must not have surrounding whitespace")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("lineage cursor must not contain control characters")
    return value


def _require_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a bool")
    return value


def _require_optional_id(name: str, value: object) -> str | None:
    if value is None:
        return None
    return require_stable_id(name, value)


def _require_optional_tick(name: str, value: object) -> int | None:
    if value is None:
        return None
    return require_exact_nonneg_int(name, value)


def _require_optional_finite(name: str, value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


@dataclass(frozen=True, slots=True)
class LineageScope:
    """One family, one evidence class and the exact owner selection."""

    run_id: RunId
    family: LineageFamily
    evidence_class: LineageEvidenceClass
    owner_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise ValueError("LineageScope.run_id must be RunId")
        if type(self.family) is not LineageFamily:
            raise ValueError("LineageScope.family must be LineageFamily")
        if type(self.evidence_class) is not LineageEvidenceClass:
            raise ValueError("LineageScope.evidence_class must be LineageEvidenceClass")
        owner = _require_optional_id("LineageScope.owner_id", self.owner_id)
        try:
            require_supported_scope_owner(self.family, self.evidence_class, owner)
        except ValueError as exc:
            raise LineageError("invalid_lineage_scope") from exc
        object.__setattr__(self, "owner_id", owner)


@dataclass(frozen=True, slots=True)
class LineageSnapshotRef:
    """Immutable publication identity and captured boundary."""

    publication_id: str
    digest: str
    boundary_tick: int
    schema_version: str = LINEAGE_SNAPSHOT_SCHEMA_VERSION
    catalogue_generation: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "publication_id",
            require_stable_id("LineageSnapshotRef.publication_id", self.publication_id),
        )
        object.__setattr__(
            self,
            "digest",
            require_lineage_key("LineageSnapshotRef.digest", self.digest),
        )
        object.__setattr__(
            self,
            "boundary_tick",
            require_exact_nonneg_int(
                "LineageSnapshotRef.boundary_tick", self.boundary_tick
            ),
        )
        if self.schema_version != LINEAGE_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("unsupported lineage snapshot schema")
        object.__setattr__(
            self,
            "catalogue_generation",
            _require_optional_id(
                "LineageSnapshotRef.catalogue_generation",
                self.catalogue_generation,
            ),
        )


@dataclass(frozen=True, slots=True)
class LineageCoverage:
    """Honest bounded coverage for the declared captured evidence."""

    state: LineageCoverageState
    reason_codes: tuple[str, ...] = ()
    capture_start_tick: int | None = None
    capture_end_tick: int | None = None
    missing_prefix_tick: int | None = None
    pruned_count: int = 0
    unresolved_count: int = 0
    policy_version: str | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not LineageCoverageState:
            raise ValueError("LineageCoverage.state must be LineageCoverageState")
        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                require_stable_id("LineageCoverage.reason_code", item)
                for item in self.reason_codes
            ),
        )
        for name in (
            "capture_start_tick",
            "capture_end_tick",
            "missing_prefix_tick",
        ):
            object.__setattr__(
                self,
                name,
                _require_optional_tick(f"LineageCoverage.{name}", getattr(self, name)),
            )
        object.__setattr__(
            self,
            "pruned_count",
            require_exact_nonneg_int("LineageCoverage.pruned_count", self.pruned_count),
        )
        object.__setattr__(
            self,
            "unresolved_count",
            require_exact_nonneg_int(
                "LineageCoverage.unresolved_count", self.unresolved_count
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            _require_optional_id("LineageCoverage.policy_version", self.policy_version),
        )
        start = self.capture_start_tick
        end = self.capture_end_tick
        if start is not None and end is not None and start > end:
            raise ValueError("LineageCoverage start tick exceeds end tick")
        if (
            self.missing_prefix_tick is not None
            and start is not None
            and self.missing_prefix_tick > start
        ):
            raise ValueError("LineageCoverage missing prefix exceeds capture start")


@dataclass(frozen=True, slots=True)
class LineageNode:
    """Descriptor for one qualified lineage node."""

    ref: LineageNodeRef
    state: LineageNodeState
    living: bool | None = None
    observed_tick: int | None = None
    status_code: str | None = None
    confidence_code: str | None = None
    confidence_value: float | None = None
    unresolved_reason: str | None = None
    native_revision: str | None = None
    evidence_refs: tuple[LineageEvidenceRef, ...] = ()
    counts: tuple[tuple[str, int], ...] = ()
    source_observed_boundary: int | None = None
    mentorship_record: MentorshipLineageRecord | None = None
    custodian_repository_id: str | None = None
    source_loss_state: str | None = None
    source_loss_reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.ref) is not LineageNodeRef:
            raise ValueError("LineageNode.ref must be LineageNodeRef")
        if type(self.state) is not LineageNodeState:
            raise ValueError("LineageNode.state must be LineageNodeState")
        if self.living is not None:
            object.__setattr__(
                self, "living", _require_bool("LineageNode.living", self.living)
            )
            if self.ref.native_kind is not LineageNativeKind.AGENT:
                raise ValueError("LineageNode.living requires an agent node")
        object.__setattr__(
            self,
            "observed_tick",
            _require_optional_tick("LineageNode.observed_tick", self.observed_tick),
        )
        for name in ("status_code", "confidence_code", "native_revision"):
            object.__setattr__(
                self,
                name,
                _require_optional_id(f"LineageNode.{name}", getattr(self, name)),
            )
        object.__setattr__(
            self,
            "confidence_value",
            _require_optional_finite(
                "LineageNode.confidence_value", self.confidence_value
            ),
        )
        unresolved_reason = _require_optional_id(
            "LineageNode.unresolved_reason", self.unresolved_reason
        )
        if self.state is LineageNodeState.UNRESOLVED:
            if unresolved_reason is None:
                raise ValueError("unresolved lineage node requires a reason")
        elif unresolved_reason is not None:
            raise ValueError("only unresolved lineage nodes carry a reason")
        object.__setattr__(self, "unresolved_reason", unresolved_reason)
        refs = tuple(self.evidence_refs)
        for item in refs:
            if type(item) is not LineageEvidenceRef:
                raise ValueError("LineageNode.evidence_refs must be LineageEvidenceRef")
        object.__setattr__(self, "evidence_refs", refs)
        normalized_counts: list[tuple[str, int]] = []
        seen_count_keys: set[str] = set()
        for count_item in self.counts:
            if not isinstance(count_item, tuple) or len(count_item) != 2:
                raise ValueError("LineageNode.counts entries must be pairs")
            count_key = require_stable_id("LineageNode.counts.key", count_item[0])
            count_value = require_exact_nonneg_int(
                "LineageNode.counts.value", count_item[1]
            )
            if count_key in seen_count_keys:
                raise ValueError("duplicate LineageNode.counts key")
            seen_count_keys.add(count_key)
            normalized_counts.append((count_key, count_value))
        object.__setattr__(self, "counts", tuple(normalized_counts))
        object.__setattr__(
            self,
            "source_observed_boundary",
            _require_optional_tick(
                "LineageNode.source_observed_boundary",
                self.source_observed_boundary,
            ),
        )
        if self.mentorship_record is not None:
            if type(self.mentorship_record) is not MentorshipLineageRecord:
                raise ValueError(
                    "LineageNode.mentorship_record must be MentorshipLineageRecord"
                )
            if self.ref.native_kind is not LineageNativeKind.MENTORSHIP_ENTRY:
                raise ValueError("mentorship_record requires a mentorship entry node")
        for name in (
            "custodian_repository_id",
            "source_loss_state",
            "source_loss_reason",
        ):
            object.__setattr__(
                self,
                name,
                _require_optional_id(f"LineageNode.{name}", getattr(self, name)),
            )

    @property
    def key(self) -> str:
        return self.ref.key


@dataclass(frozen=True, slots=True)
class LineageEdge:
    """Directed native evidence edge; orientation never flips with query mode."""

    edge_key: str
    source_key: str
    target_key: str
    relation: str
    native_kind: LineageNativeKind
    native_id: str
    claim_owner_id: str | None = None
    evidence_refs: tuple[LineageEvidenceRef, ...] = ()
    observed_tick: int | None = None
    last_observed_boundary: int | None = None
    status_code: str | None = None
    confidence_code: str | None = None
    confidence_value: float | None = None
    source_presence: str = "present"
    counts: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        for name in ("edge_key", "source_key", "target_key"):
            object.__setattr__(
                self,
                name,
                require_lineage_key(f"LineageEdge.{name}", getattr(self, name)),
            )
        object.__setattr__(
            self, "relation", require_stable_id("LineageEdge.relation", self.relation)
        )
        if type(self.native_kind) is not LineageNativeKind:
            raise ValueError("LineageEdge.native_kind must be LineageNativeKind")
        object.__setattr__(
            self,
            "native_id",
            require_stable_id("LineageEdge.native_id", self.native_id),
        )
        object.__setattr__(
            self,
            "claim_owner_id",
            _require_optional_id("LineageEdge.claim_owner_id", self.claim_owner_id),
        )
        refs = tuple(self.evidence_refs)
        for item in refs:
            if type(item) is not LineageEvidenceRef:
                raise ValueError("LineageEdge.evidence_refs must be LineageEvidenceRef")
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(
            self,
            "observed_tick",
            _require_optional_tick("LineageEdge.observed_tick", self.observed_tick),
        )
        last_observed = self.last_observed_boundary
        if last_observed is None:
            last_observed = self.observed_tick
        object.__setattr__(
            self,
            "last_observed_boundary",
            _require_optional_tick("LineageEdge.last_observed_boundary", last_observed),
        )
        for name in ("status_code", "confidence_code"):
            object.__setattr__(
                self,
                name,
                _require_optional_id(f"LineageEdge.{name}", getattr(self, name)),
            )
        object.__setattr__(
            self,
            "confidence_value",
            _require_optional_finite(
                "LineageEdge.confidence_value", self.confidence_value
            ),
        )
        if self.source_presence not in {"present", "archived", "unresolved"}:
            raise ValueError("LineageEdge.source_presence is not supported")
        normalized_counts: list[tuple[str, int]] = []
        seen_count_keys: set[str] = set()
        for count_item in self.counts:
            if not isinstance(count_item, tuple) or len(count_item) != 2:
                raise ValueError("LineageEdge.counts entries must be pairs")
            count_key = require_stable_id("LineageEdge.counts.key", count_item[0])
            count_value = require_exact_nonneg_int(
                "LineageEdge.counts.value", count_item[1]
            )
            if count_key in seen_count_keys:
                raise ValueError("duplicate LineageEdge.counts key")
            seen_count_keys.add(count_key)
            normalized_counts.append((count_key, count_value))
        object.__setattr__(self, "counts", tuple(normalized_counts))


@dataclass(frozen=True, slots=True)
class MentorshipLineageRecord:
    """Safe native mentorship-entry metadata shared by both evidence classes.

    Deliberately excludes content fingerprints and all content text.
    """

    owner_id: str
    teacher_id: str
    learner_id: str
    lineage_id: str
    root_id: str
    parent_ids: tuple[str, ...]
    content_kind: str
    content_key: str
    hop: int
    acquisition_tick: int
    update_tick: int
    attempt_count: int
    learning_evidence_count: int
    confidence_band: str | None
    mutated: bool
    evidence_refs: tuple[LineageEvidenceRef, ...]
    policy_version: str
    observed_boundary: int
    source_observed_boundary: int
    native_status: str | None = None
    source_revision: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "teacher_id",
            "learner_id",
            "lineage_id",
            "root_id",
            "content_kind",
            "content_key",
            "policy_version",
        ):
            object.__setattr__(
                self,
                name,
                require_stable_id(
                    f"MentorshipLineageRecord.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "parent_ids",
            tuple(
                require_stable_id("MentorshipLineageRecord.parent_id", item)
                for item in self.parent_ids
            ),
        )
        for name in (
            "hop",
            "acquisition_tick",
            "update_tick",
            "attempt_count",
            "learning_evidence_count",
            "observed_boundary",
            "source_observed_boundary",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"MentorshipLineageRecord.{name}", getattr(self, name)
                ),
            )
        object.__setattr__(
            self,
            "confidence_band",
            _require_optional_id(
                "MentorshipLineageRecord.confidence_band", self.confidence_band
            ),
        )
        object.__setattr__(
            self,
            "mutated",
            _require_bool("MentorshipLineageRecord.mutated", self.mutated),
        )
        refs = tuple(self.evidence_refs)
        for item in refs:
            if type(item) is not LineageEvidenceRef:
                raise ValueError(
                    "MentorshipLineageRecord.evidence_refs must be LineageEvidenceRef"
                )
        object.__setattr__(self, "evidence_refs", refs)
        for name in ("native_status", "source_revision"):
            object.__setattr__(
                self,
                name,
                _require_optional_id(
                    f"MentorshipLineageRecord.{name}", getattr(self, name)
                ),
            )


@dataclass(frozen=True, slots=True)
class LineageQuery:
    """One bounded, snapshot-pinned lineage graph request."""

    scope: LineageScope
    snapshot: LineageSnapshotRef | None = None
    root: LineageNodeRef | None = None
    direction: LineageDirection = LineageDirection.BOTH
    max_depth: int = DEFAULT_LINEAGE_MAX_DEPTH
    max_nodes: int = DEFAULT_LINEAGE_MAX_NODES
    max_edges: int = DEFAULT_LINEAGE_MAX_EDGES
    living_only: bool = False
    page_size: int = DEFAULT_LINEAGE_PAGE_SIZE

    def __post_init__(self) -> None:
        if type(self.scope) is not LineageScope:
            raise ValueError("LineageQuery.scope must be LineageScope")
        if self.snapshot is not None and type(self.snapshot) is not LineageSnapshotRef:
            raise ValueError("LineageQuery.snapshot must be LineageSnapshotRef")
        if self.root is not None:
            if type(self.root) is not LineageNodeRef:
                raise ValueError("LineageQuery.root must be LineageNodeRef")
            self._validate_root(self.root)
        if type(self.direction) is not LineageDirection:
            raise ValueError("LineageQuery.direction must be LineageDirection")
        for name, maximum in (
            ("max_depth", MAX_LINEAGE_MAX_DEPTH),
            ("max_nodes", MAX_LINEAGE_MAX_NODES),
            ("max_edges", MAX_LINEAGE_MAX_EDGES),
            ("page_size", MAX_LINEAGE_PAGE_SIZE),
        ):
            value = require_exact_nonneg_int(
                f"LineageQuery.{name}", getattr(self, name)
            )
            minimum = 0 if name == "max_depth" else 1
            if value < minimum or value > maximum:
                raise LineageError("invalid_lineage_budget")
            object.__setattr__(self, name, value)
        object.__setattr__(
            self,
            "living_only",
            _require_bool("LineageQuery.living_only", self.living_only),
        )
        if self.living_only and self.scope.family is not LineageFamily.GENEALOGY:
            raise LineageError("invalid_lineage_scope")

    def _validate_root(self, root: LineageNodeRef) -> None:
        scope = self.scope
        if root.run_id != scope.run_id:
            raise LineageError("invalid_lineage_scope")
        if root.family is not scope.family:
            raise LineageError("invalid_lineage_scope")
        if root.evidence_class is not scope.evidence_class:
            raise LineageError("invalid_lineage_scope")
        if (
            scope.evidence_class is LineageEvidenceClass.SUBJECTIVE
            and root.identity_owner != scope.owner_id
        ):
            raise LineageError("invalid_lineage_scope")


@dataclass(frozen=True, slots=True)
class LineagePage:
    """One deterministic graph page with complete edge-endpoint context."""

    root: LineageNodeRef
    snapshot: LineageSnapshotRef
    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]
    coverage: LineageCoverage
    visited_node_count: int
    visited_edge_count: int
    matched_node_keys: tuple[str, ...] = ()
    context_only_node_keys: tuple[str, ...] = ()
    stop_reasons: tuple[str, ...] = ()
    continuation: str | None = None
    schema_version: str = LINEAGE_GRAPH_PAGE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.root) is not LineageNodeRef:
            raise ValueError("LineagePage.root must be LineageNodeRef")
        if type(self.snapshot) is not LineageSnapshotRef:
            raise ValueError("LineagePage.snapshot must be LineageSnapshotRef")
        if type(self.coverage) is not LineageCoverage:
            raise ValueError("LineagePage.coverage must be LineageCoverage")
        nodes = tuple(self.nodes)
        for node in nodes:
            if type(node) is not LineageNode:
                raise ValueError("LineagePage.nodes must be LineageNode")
        edges = tuple(self.edges)
        for edge in edges:
            if type(edge) is not LineageEdge:
                raise ValueError("LineagePage.edges must be LineageEdge")
        if self.schema_version != LINEAGE_GRAPH_PAGE_SCHEMA_VERSION:
            raise ValueError("unsupported lineage graph page schema")
        node_keys = {node.key for node in nodes}
        if self.root.key not in node_keys:
            raise ValueError("LineagePage requires its root descriptor")
        if len(node_keys) != len(nodes):
            raise ValueError("duplicate_lineage_identity")
        edge_keys = {edge.edge_key for edge in edges}
        if len(edge_keys) != len(edges):
            raise ValueError("duplicate_lineage_edge")
        for edge in edges:
            if edge.source_key not in node_keys or edge.target_key not in node_keys:
                raise ValueError("lineage edge endpoint descriptor is missing")
        matched = tuple(
            require_lineage_key("LineagePage.matched_node_key", key)
            for key in self.matched_node_keys
        )
        if any(key not in node_keys for key in matched):
            raise ValueError("matched lineage node is missing from the page")
        context = tuple(
            require_lineage_key("LineagePage.context_only_node_key", key)
            for key in self.context_only_node_keys
        )
        if any(key not in node_keys for key in context):
            raise ValueError("context lineage node is missing from the page")
        if set(matched) & set(context):
            raise ValueError("lineage node cannot be matched and context-only")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)
        object.__setattr__(self, "matched_node_keys", matched)
        object.__setattr__(self, "context_only_node_keys", context)
        object.__setattr__(
            self,
            "stop_reasons",
            tuple(
                require_stable_id("LineagePage.stop_reason", item)
                for item in self.stop_reasons
            ),
        )
        for name in ("visited_node_count", "visited_edge_count"):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(f"LineagePage.{name}", getattr(self, name)),
            )
        if self.continuation is not None:
            object.__setattr__(
                self, "continuation", require_lineage_cursor(self.continuation)
            )
