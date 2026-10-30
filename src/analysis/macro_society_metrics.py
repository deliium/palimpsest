"""Four detached metric families over macro-society analysis."""

from __future__ import annotations

import logging
from typing import Final

from analysis.macro_society_contract import (
    MacroSocietyError,
    MacroSocietyLane,
    MacroSocietyLineageKind,
    MacroSocietyMembershipStatus,
    MacroSocietyStatus,
)
from analysis.macro_society_lineage import MacroSocietyAnalysis
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "compute_macro_society_identity_alignment_metric",
    "compute_macro_society_lineage_metric",
    "compute_macro_society_membership_dispute_metric",
    "compute_macro_society_structure_metric",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.macro_society_metrics")


def _availability(analysis: MacroSocietyAnalysis) -> MetricAvailability:
    if not analysis.windows:
        return MetricAvailability.ABSENT
    final = analysis.windows[-1]
    if not final.candidates:
        return MetricAvailability.ABSENT
    if any(not present for _, present in final.lane_presence):
        return MetricAvailability.PARTIAL
    if final.coverage.ratio is not None and final.coverage.ratio < 1.0:
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _document(
    analysis: MacroSocietyAnalysis,
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
            source_kind="macro_society_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )


def _validate(
    analysis: object, run_id: str, input_revision: str
) -> MacroSocietyAnalysis:
    if type(analysis) is not MacroSocietyAnalysis:
        raise MacroSocietyError("macro_society_invalid_analysis")
    require_stable_id("run_id", run_id)
    require_stable_id("input_revision", input_revision)
    return analysis


def compute_macro_society_structure_metric(
    analysis: MacroSocietyAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Candidate counts, coverage, overlap, and fragmentation."""
    analysis = _validate(analysis, run_id, input_revision)
    final = analysis.windows[-1]
    known = len(final.known_person_ids)
    members = {
        person for candidate in final.candidates for person in candidate.member_ids
    }
    largest = max(
        (len(candidate.member_ids) for candidate in final.candidates), default=0
    )
    availability = _availability(analysis)
    values = {
        "candidate_count": len(final.candidates),
        "largest_candidate_share": quantize_float(largest / known) if known else None,
        "covered_person_count": len(members),
        "overlap_person_count": len(final.overlap_person_ids),
        "fragment_person_count": len(final.fragment_person_ids),
        "mean_candidate_members": (
            quantize_float(len(members) / len(final.candidates))
            if final.candidates
            else None
        ),
        "lane_presence_count": sum(1 for _, present in final.lane_presence if present),
    }
    _LOG.debug(
        "macro_society_metric family=%s availability=%s candidates=%s",
        MetricFamilyId.MACRO_SOCIETY_STRUCTURE.value,
        availability.value,
        len(final.candidates),
    )
    return _document(
        analysis,
        MetricFamilyId.MACRO_SOCIETY_STRUCTURE,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="ok" if availability is not MetricAvailability.ABSENT else "empty",
    )


def compute_macro_society_identity_alignment_metric(
    analysis: MacroSocietyAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Self-identification and territory support versus analytical grouping."""
    analysis = _validate(analysis, run_id, input_revision)
    final = analysis.windows[-1]
    candidates = final.candidates
    with_self_id = [
        candidate
        for candidate in candidates
        if MacroSocietyLane.SELF_IDENTIFICATION in candidate.lanes
    ]
    self_id_members = {
        person for candidate in with_self_id for person in candidate.member_ids
    }
    members = {person for candidate in candidates for person in candidate.member_ids}
    unrecognized = sum(
        1
        for candidate in candidates
        if candidate.lanes == (MacroSocietyLane.SELF_IDENTIFICATION,)
    )
    territory_candidates = [
        candidate
        for candidate in candidates
        if MacroSocietyLane.TERRITORY in candidate.lanes
    ]
    territory_aligned = 0
    for candidate in territory_candidates:
        support = next(
            (
                item
                for item in candidate.lane_support
                if item.lane is MacroSocietyLane.TERRITORY
            ),
            None,
        )
        if support is not None and support.member_count == len(candidate.member_ids):
            territory_aligned += 1
    availability = _availability(analysis)
    values = {
        "candidates_with_self_identification": len(with_self_id),
        "self_identified_member_share": (
            quantize_float(len(self_id_members) / len(members)) if members else None
        ),
        "unrecognized_self_identified_group_count": unrecognized,
        "territory_alignment_share": (
            quantize_float(territory_aligned / len(territory_candidates))
            if territory_candidates
            else None
        ),
        "layer_disagreement_count": sum(
            1
            for candidate in candidates
            if candidate.status is MacroSocietyStatus.CONTESTED
        ),
        "territory_supported_candidate_count": len(territory_candidates),
    }
    return _document(
        analysis,
        MetricFamilyId.MACRO_SOCIETY_IDENTITY_ALIGNMENT,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="ok" if availability is not MetricAvailability.ABSENT else "empty",
    )


def compute_macro_society_lineage_metric(
    analysis: MacroSocietyAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Continuation, split, merge, dissolution, and emergence counts."""
    analysis = _validate(analysis, run_id, input_revision)
    kinds = [edge.kind for edge in analysis.edges]
    continuation_scores = [
        edge.jaccard
        for edge in analysis.edges
        if edge.kind in {
            MacroSocietyLineageKind.CONTINUED,
            MacroSocietyLineageKind.TRANSFORMED,
        }
        and edge.jaccard is not None
        and edge.from_id != edge.to_id
    ]
    availability = _availability(analysis)
    values = {
        "continuation_count": kinds.count(MacroSocietyLineageKind.CONTINUED),
        "transform_count": kinds.count(MacroSocietyLineageKind.TRANSFORMED),
        "split_count": kinds.count(MacroSocietyLineageKind.SPLIT),
        "merge_count": kinds.count(MacroSocietyLineageKind.MERGE),
        "dissolution_count": kinds.count(MacroSocietyLineageKind.DISSOLVED),
        "emergence_count": kinds.count(MacroSocietyLineageKind.EMERGED),
        "mean_continuation_jaccard": (
            quantize_float(sum(continuation_scores) / len(continuation_scores))
            if continuation_scores
            else None
        ),
        "lineage_window_count": len(analysis.windows),
    }
    return _document(
        analysis,
        MetricFamilyId.MACRO_SOCIETY_LINEAGE,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="ok" if availability is not MetricAvailability.ABSENT else "empty",
    )


def compute_macro_society_membership_dispute_metric(
    analysis: MacroSocietyAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Contested memberships, overlap, and unresolved fragments."""
    analysis = _validate(analysis, run_id, input_revision)
    final = analysis.windows[-1]
    disputed: set[str] = set()
    disputed_candidates = 0
    for candidate in final.candidates:
        membership = dict(candidate.membership)
        contested = {
            person
            for person, state in membership.items()
            if state is MacroSocietyMembershipStatus.CONTESTED
        }
        if contested:
            disputed_candidates += 1
            disputed.update(contested)
    known = len(final.known_person_ids)
    availability = _availability(analysis)
    values = {
        "disputed_member_count": len(disputed),
        "disputed_candidate_count": disputed_candidates,
        "overlap_member_count": len(final.overlap_person_ids),
        "contested_candidate_count": sum(
            1
            for candidate in final.candidates
            if candidate.status is MacroSocietyStatus.CONTESTED
        ),
        "unresolved_fragment_count": len(final.fragment_person_ids),
        "contested_share": (
            quantize_float(len(disputed) / known) if known else None
        ),
    }
    return _document(
        analysis,
        MetricFamilyId.MACRO_SOCIETY_MEMBERSHIP_DISPUTE,
        run_id=run_id,
        input_revision=input_revision,
        availability=availability,
        values=values,
        notes_code="ok" if availability is not MetricAvailability.ABSENT else "empty",
    )
