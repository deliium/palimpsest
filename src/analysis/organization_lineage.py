"""Forward-only organization lineage over analytical identity records."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organization_contract import (
    ABSORPTION_CONTAINMENT,
    CONTINUATION_JACCARD,
    ORGANIZATION_ANALYSIS_POLICY_VERSION,
    SPLIT_CONTAINMENT,
    OrganizationAnalysisError,
    OrganizationCoverage,
    OrganizationLineageKind,
)
from analysis.organization_identity import (
    OrganizationIdentityAssignment,
    OrganizationRecord,
    OrganizationTransition,
    OrganizationWindowSnapshot,
)
from analysis.organization_layers import (
    OrganizationLayerView,
    project_organization_layers,
)
from analysis.organization_operations import OrganizationOperationSummary
from analysis.organizations import OrganizationHarvestRows
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "OrganizationAnalysis",
    "OrganizationLineageEdge",
    "build_organization_analysis",
    "derive_organization_lineage",
    "validate_organization_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_lineage")


@dataclass(frozen=True, slots=True)
class OrganizationLineageEdge:
    kind: OrganizationLineageKind
    from_id: str | None
    to_id: str | None
    tick: int
    jaccard: float | None = None
    containment: float | None = None
    policy_note: str = ""

    def __post_init__(self) -> None:
        if type(self.kind) is not OrganizationLineageKind:
            raise OrganizationAnalysisError("organization_lineage_tick")
        require_exact_nonneg_int("tick", self.tick)
        if self.kind is OrganizationLineageKind.EMERGED and self.from_id is not None:
            raise OrganizationAnalysisError("organization_lineage_unknown_endpoint")
        if self.kind is OrganizationLineageKind.DISSOLVED and self.to_id is not None:
            raise OrganizationAnalysisError("organization_lineage_unknown_endpoint")
        if self.kind not in (
            OrganizationLineageKind.EMERGED,
            OrganizationLineageKind.DISSOLVED,
        ):
            if self.from_id is None or self.to_id is None:
                raise OrganizationAnalysisError("organization_lineage_unknown_endpoint")


@dataclass(frozen=True, slots=True)
class OrganizationAnalysis:
    policy_version: str
    windows: tuple[OrganizationWindowSnapshot, ...]
    records: tuple[OrganizationRecord, ...]
    edges: tuple[OrganizationLineageEdge, ...]
    coverage: OrganizationCoverage
    layer_view: OrganizationLayerView | None = None
    operation_summary: OrganizationOperationSummary | None = None
    history_truncated: bool = False
    determinism_digest: str = ""

    def __post_init__(self) -> None:
        digest = _analysis_digest(self)
        object.__setattr__(self, "determinism_digest", digest)


def _content(analysis: OrganizationAnalysis) -> dict[str, object]:
    return {
        "policy_version": analysis.policy_version,
        "windows": [
            {
                "window_index": window.window_index,
                "start_tick": window.start_tick,
                "end_tick": window.end_tick,
                "candidates": [
                    {
                        "key": candidate.candidate_key,
                        "members": list(candidate.member_ids),
                        "anchors": list(candidate.anchor_signature),
                        "status": candidate.status.value,
                        "scope": candidate.temporal_scope.value,
                    }
                    for candidate in window.candidates
                ],
            }
            for window in analysis.windows
        ],
        "records": [
            {
                "organization_id": record.organization_id,
                "creation_tick": record.creation_tick,
                "first_tick": record.first_tick,
                "last_tick": record.last_tick,
                "member_ids": list(record.member_ids),
                "anchor_signature": list(record.anchor_signature),
                "window_indexes": list(record.window_indexes),
            }
            for record in analysis.records
        ],
        "edges": [
            {
                "kind": edge.kind.value,
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "tick": edge.tick,
                "jaccard": edge.jaccard,
                "containment": edge.containment,
            }
            for edge in analysis.edges
        ],
    }


def _analysis_digest(analysis: OrganizationAnalysis) -> str:
    payload = json.dumps(_content(analysis), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _window_tick(assignment: OrganizationIdentityAssignment, index: int) -> int:
    for window in assignment.windows:
        if window.window_index == index:
            return window.start_tick
    return 0


def derive_organization_lineage(
    assignment: OrganizationIdentityAssignment,
    *,
    layer_view: OrganizationLayerView | None = None,
    operation_summary: OrganizationOperationSummary | None = None,
    history_truncated: bool = False,
) -> OrganizationAnalysis:
    """Derive continued/transformed/split/merge/dissolved/emerged edges."""

    if type(assignment) is not OrganizationIdentityAssignment:
        raise OrganizationAnalysisError("organization_lineage_tick")
    records = assignment.records
    known = {record.organization_id for record in records}
    by_window: dict[int, list[OrganizationTransition]] = {}
    for transition in assignment.transitions:
        by_window.setdefault(transition.window_index, []).append(transition)
    edges: list[OrganizationLineageEdge] = []
    for window_index in sorted(by_window):
        transitions = by_window[window_index]
        tick = _window_tick(assignment, window_index)
        for transition in transitions:
            if transition.from_id is None:
                edges.append(
                    OrganizationLineageEdge(
                        kind=OrganizationLineageKind.EMERGED,
                        from_id=None,
                        to_id=transition.to_id,
                        tick=tick,
                    )
                )
        predecessors: dict[str, set[str]] = {}
        successors: dict[str, set[str]] = {}
        for transition in transitions:
            if transition.from_id is None:
                continue
            predecessors.setdefault(transition.to_id, set()).add(transition.from_id)
            successors.setdefault(transition.from_id, set()).add(transition.to_id)
        for transition in transitions:
            if transition.from_id is None:
                continue
            prior = predecessors.get(transition.to_id, set())
            later = successors.get(transition.from_id, set())
            if len(prior) > 1:
                kind = OrganizationLineageKind.MERGE
                containment = ABSORPTION_CONTAINMENT
            elif len(later) > 1:
                kind = OrganizationLineageKind.SPLIT
                containment = SPLIT_CONTAINMENT
            elif (
                transition.anchor_shared
                and transition.jaccard >= CONTINUATION_JACCARD
            ):
                kind = OrganizationLineageKind.CONTINUED
                containment = None
            else:
                kind = OrganizationLineageKind.TRANSFORMED
                containment = None
            edges.append(
                OrganizationLineageEdge(
                    kind=kind,
                    from_id=transition.from_id,
                    to_id=transition.to_id,
                    tick=tick,
                    jaccard=transition.jaccard,
                    containment=containment,
                    policy_note="observed",
                )
            )
    max_window = max((window.window_index for window in assignment.windows), default=-1)
    last_window: dict[str, int] = {}
    for record in records:
        last_window[record.organization_id] = record.window_indexes[-1]
    succeeded = {
        edge.from_id
        for edge in edges
        if edge.from_id is not None
        and edge.kind
        in (
            OrganizationLineageKind.CONTINUED,
            OrganizationLineageKind.TRANSFORMED,
            OrganizationLineageKind.SPLIT,
            OrganizationLineageKind.MERGE,
        )
    }
    for record in records:
        if record.organization_id in succeeded:
            continue
        if last_window[record.organization_id] >= max_window:
            continue
        edges.append(
            OrganizationLineageEdge(
                kind=OrganizationLineageKind.DISSOLVED,
                from_id=record.organization_id,
                to_id=None,
                tick=_window_tick(assignment, last_window[record.organization_id] + 1),
            )
        )
    ordered = tuple(
        sorted(
            edges,
            key=lambda edge: (
                edge.tick,
                edge.kind.value,
                edge.from_id or "",
                edge.to_id or "",
            ),
        )
    )
    validate_organization_lineage(ordered, known_ids=tuple(sorted(known)))
    _LOG.info(
        "organization_analysis records=%s edges=%s windows=%s",
        len(records),
        len(ordered),
        len(assignment.windows),
    )
    return OrganizationAnalysis(
        policy_version=ORGANIZATION_ANALYSIS_POLICY_VERSION,
        windows=assignment.windows,
        records=records,
        edges=ordered,
        coverage=assignment.coverage,
        layer_view=layer_view,
        operation_summary=operation_summary,
        history_truncated=bool(history_truncated),
    )


def validate_organization_lineage(
    edges: Sequence[OrganizationLineageEdge],
    *,
    known_ids: Sequence[str] | None = None,
) -> None:
    """Validate monotone ticks, known endpoints, endpoint rules, and acyclicity."""

    known = set(known_ids) if known_ids is not None else None
    previous_tick = -1
    graph: dict[str, set[str]] = {}
    for edge in edges:
        if type(edge) is not OrganizationLineageEdge:
            raise OrganizationAnalysisError("organization_lineage_tick")
        if edge.tick < previous_tick:
            raise OrganizationAnalysisError("organization_lineage_tick")
        previous_tick = edge.tick
        if known is not None:
            for endpoint in (edge.from_id, edge.to_id):
                if endpoint is not None and endpoint not in known:
                    raise OrganizationAnalysisError(
                        "organization_lineage_unknown_endpoint"
                    )
        if edge.from_id is not None and edge.to_id is not None:
            if edge.from_id != edge.to_id:
                graph.setdefault(edge.from_id, set()).add(edge.to_id)
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            raise OrganizationAnalysisError("organization_lineage_cycle")
        visiting.add(node)
        for target in sorted(graph.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(graph):
        visit(node)


def build_organization_analysis(
    assignment: OrganizationIdentityAssignment,
    *,
    owner_rows: Sequence[OrganizationHarvestRows] = (),
    layer_view: OrganizationLayerView | None = None,
    operation_summary: OrganizationOperationSummary | None = None,
    history_truncated: bool = False,
) -> OrganizationAnalysis:
    """Build the digest-bearing analysis, projecting layers when possible."""

    if layer_view is None and owner_rows:
        layer_view = project_organization_layers(assignment, owner_rows)
    return derive_organization_lineage(
        assignment,
        layer_view=layer_view,
        operation_summary=operation_summary,
        history_truncated=history_truncated,
    )
