"""Four detached metric families over organization analysis."""

from __future__ import annotations

import logging
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.organization_contract import (
    OrganizationAnalysisError,
    OrganizationCandidateStatus,
    OrganizationLineageKind,
    OrganizationMembershipStatus,
)
from analysis.organization_detection import OrganizationCandidate
from analysis.organization_identity import OrganizationWindowSnapshot
from analysis.organization_lineage import OrganizationAnalysis
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "compute_organization_formation_metric",
    "compute_organization_lineage_metric",
    "compute_organization_membership_metric",
    "compute_organization_structure_metric",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_metrics")


def _validate(
    analysis: object, run_id: str, input_revision: str
) -> OrganizationAnalysis:
    if type(analysis) is not OrganizationAnalysis:
        raise OrganizationAnalysisError("organization_metric_invalid")
    require_stable_id("run_id", run_id)
    require_stable_id("input_revision", input_revision)
    return analysis


def _final_window(analysis: OrganizationAnalysis) -> OrganizationWindowSnapshot | None:
    return analysis.windows[-1] if analysis.windows else None


def _availability(
    analysis: OrganizationAnalysis, *, require_edges: bool = False
) -> MetricAvailability:
    window = _final_window(analysis)
    if window is None:
        return MetricAvailability.ABSENT
    if require_edges and not analysis.edges:
        return MetricAvailability.ABSENT
    if not require_edges and not window.candidates:
        return MetricAvailability.ABSENT
    if any(not present for _, present in window.lane_presence):
        return MetricAvailability.PARTIAL
    if window.coverage.ratio is not None and window.coverage.ratio < 1.0:
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _document(
    analysis: OrganizationAnalysis,
    family: MetricFamilyId,
    *,
    run_id: str,
    input_revision: str,
    availability: MetricAvailability,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=MetricCoverage(
            observed=analysis.coverage.observed,
            expected=analysis.coverage.expected,
            ratio=analysis.coverage.ratio,
        ),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="organization_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )


def _anchor_family_count(candidate: OrganizationCandidate) -> int:
    return sum(
        1
        for family in (
            candidate.role_anchor_ids,
            candidate.goal_anchor_ids,
            candidate.resource_anchor_ids,
            candidate.procedure_anchor_ids,
            candidate.record_anchor_ids,
            candidate.commitment_ids,
            candidate.identity_tokens,
        )
        if family
    )


def compute_organization_formation_metric(
    analysis: OrganizationAnalysis,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Candidate formation counts under stated coverage."""
    analysis = _validate(analysis, run_id, input_revision)
    window = _final_window(analysis)
    candidates = window.candidates if window is not None else ()
    channels = [_anchor_family_count(candidate) for candidate in candidates]
    availability = _availability(analysis)
    values: dict[str, object] = {
        "candidate_count": len(candidates),
        "recognized_count": sum(
            1
            for candidate in candidates
            if candidate.status is OrganizationCandidateStatus.RECOGNIZED
        ),
        "temporary_count": sum(
            1
            for candidate in candidates
            if candidate.status is OrganizationCandidateStatus.TEMPORARY
        ),
        "multi_channel_candidate_count": sum(1 for count in channels if count >= 2),
        "mean_structural_channels": (
            quantize_float(sum(channels) / len(channels)) if channels else None
        ),
        "window_count": len(analysis.windows),
        "coverage_ratio": analysis.coverage.ratio,
        "as_of_tick": window.end_tick if window is not None else tick,
    }
    return _document(
        analysis,
        MetricFamilyId.ORGANIZATION_FORMATION,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="organization_formation_detached_candidates",
    )


def compute_organization_membership_metric(
    analysis: OrganizationAnalysis,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Perceived membership counts by closed status."""
    analysis = _validate(analysis, run_id, input_revision)
    window = _final_window(analysis)
    candidates = window.candidates if window is not None else ()
    claims = [claim for candidate in candidates for claim in candidate.member_claims]
    counts = {
        status: sum(1 for claim in claims if claim.status is status)
        for status in OrganizationMembershipStatus
    }
    availability = _availability(analysis)
    values: dict[str, object] = {
        "member_belief_count": len(claims),
        "explicit_count": counts[OrganizationMembershipStatus.EXPLICIT],
        "perceived_count": counts[OrganizationMembershipStatus.PERCEIVED],
        "disputed_count": counts[OrganizationMembershipStatus.DISPUTED],
        "unknown_count": counts[OrganizationMembershipStatus.UNKNOWN],
        "former_count": counts[OrganizationMembershipStatus.FORMER],
        "overlap_member_count": len(window.overlap_person_ids) if window else 0,
        "temporary_member_count": sum(
            1 for claim in claims if claim.temporal_scope.value == "temporary"
        ),
        "unresolved_member_count": counts[OrganizationMembershipStatus.UNKNOWN],
        "as_of_tick": window.end_tick if window is not None else tick,
    }
    return _document(
        analysis,
        MetricFamilyId.ORGANIZATION_MEMBERSHIP,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="organization_membership_detached_claims",
    )


def compute_organization_structure_metric(
    analysis: OrganizationAnalysis,
    *,
    run_id: str,
    input_revision: str,
    tick: int = 0,
) -> MetricDocument:
    """Believed structural families across final-window candidates."""
    analysis = _validate(analysis, run_id, input_revision)
    window = _final_window(analysis)
    candidates = window.candidates if window is not None else ()
    channels = [_anchor_family_count(candidate) for candidate in candidates]
    availability = _availability(analysis)
    values: dict[str, object] = {
        "role_count": sum(len(candidate.role_anchor_ids) for candidate in candidates),
        "goal_count": sum(len(candidate.goal_anchor_ids) for candidate in candidates),
        "resource_count": sum(
            len(candidate.resource_anchor_ids) for candidate in candidates
        ),
        "procedure_count": sum(
            len(candidate.procedure_anchor_ids) for candidate in candidates
        ),
        "record_count": sum(
            len(candidate.record_anchor_ids) for candidate in candidates
        ),
        "commitment_count": sum(
            len(candidate.commitment_ids) for candidate in candidates
        ),
        "identity_count": sum(
            len(candidate.identity_tokens) for candidate in candidates
        ),
        "candidates_with_roles": sum(
            1 for candidate in candidates if candidate.role_anchor_ids
        ),
        "candidates_with_goals": sum(
            1 for candidate in candidates if candidate.goal_anchor_ids
        ),
        "candidates_with_records": sum(
            1 for candidate in candidates if candidate.record_anchor_ids
        ),
        "mean_structural_channels": (
            quantize_float(sum(channels) / len(channels)) if channels else None
        ),
        "as_of_tick": window.end_tick if window is not None else tick,
    }
    return _document(
        analysis,
        MetricFamilyId.ORGANIZATION_STRUCTURE,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="organization_structure_detached_beliefs",
    )


def compute_organization_lineage_metric(
    analysis: OrganizationAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Forward-only lineage transition counts."""
    analysis = _validate(analysis, run_id, input_revision)
    edges = analysis.edges
    by_kind = {
        kind: sum(1 for edge in edges if edge.kind is kind)
        for kind in OrganizationLineageKind
    }
    jaccards = [
        edge.jaccard
        for edge in edges
        if edge.kind is OrganizationLineageKind.CONTINUED and edge.jaccard is not None
    ]
    availability = _availability(analysis, require_edges=True)
    values: dict[str, object] = {
        "continuation_count": by_kind[OrganizationLineageKind.CONTINUED],
        "transform_count": by_kind[OrganizationLineageKind.TRANSFORMED],
        "split_count": by_kind[OrganizationLineageKind.SPLIT],
        "merge_count": by_kind[OrganizationLineageKind.MERGE],
        "dissolution_count": by_kind[OrganizationLineageKind.DISSOLVED],
        "emergence_count": by_kind[OrganizationLineageKind.EMERGED],
        "mean_continuation_jaccard": (
            quantize_float(sum(jaccards) / len(jaccards)) if jaccards else None
        ),
        "lineage_window_count": len(analysis.windows),
        "as_of_tick": (analysis.windows[-1].end_tick if analysis.windows else 0),
    }
    return _document(
        analysis,
        MetricFamilyId.ORGANIZATION_LINEAGE,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="organization_lineage_forward_only",
    )
