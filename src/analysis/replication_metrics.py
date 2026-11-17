"""Six descriptive scientific-replication metric families."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.replication_contract import (
    FORBIDDEN_REPLICATION_KEYS,
    REPLICATION_POLICY_VERSION,
    ReplicationAnalysis,
    ReplicationAnalysisError,
)
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_replication_conditions",
    "compute_replication_design_lineage",
    "compute_replication_relationships",
    "compute_replication_results",
    "compute_replication_social_interpretation",
    "compute_replication_uncertainty",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.replication.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _require(analysis: object) -> ReplicationAnalysis:
    if type(analysis) is not ReplicationAnalysis:
        raise ReplicationAnalysisError("replication_analysis_invalid_type")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _milli(numerator: int, denominator: int) -> int | None:
    if denominator <= 0:
        return None
    return (1000 * numerator) // denominator


def _state(analysis: ReplicationAnalysis) -> tuple[str, int, int]:
    if not analysis.coverage:
        return "unknown", 0, 0
    coverage = analysis.coverage[-1]
    if coverage.coverage == "missing":
        return "unknown", 0, 0
    return (
        "present"
        if coverage.availability == "available"
        else "partial",
        coverage.observed_count,
        coverage.submitted_count,
    )


def _document(
    family: MetricFamilyId,
    analysis: ReplicationAnalysis,
    *,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    state, observed, expected = _state(analysis)
    for key in values:
        if str(key).lower() in FORBIDDEN_REPLICATION_KEYS:
            raise ReplicationAnalysisError("replication_analysis_forbidden_key")
    if state == "unknown":
        availability = MetricAvailability.UNKNOWN
        coverage = _ABSENT_COVERAGE
        payload: dict[str, object] = {}
    else:
        availability = (
            MetricAvailability.PRESENT
            if state == "present"
            else MetricAvailability.PARTIAL
        )
        coverage = MetricCoverage(
            observed=observed,
            expected=expected,
            ratio=_ratio(observed, expected),
        )
        payload = dict(values)
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
        coverage=coverage,
        availability=availability,
        values=payload,
        provenance=MetricProvenance(
            source_kind="scientific_replication_analysis",
            source_ids=(
                run_id,
                input_revision,
                REPLICATION_POLICY_VERSION,
                "scientific-replication",
                notes_code,
            ),
        ),
    )


def compute_replication_design_lineage(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    roots = sum(1 for row in data.designs if row.fact.parent_design_token is None)
    children = len(data.designs) - roots
    known = {row.fact.design_token for row in data.designs}
    unresolved = sum(
        1
        for row in data.designs
        if row.fact.parent_design_token is not None
        and row.fact.parent_design_token not in known
    )
    values = {
        "design_count": len(data.designs),
        "root_count": roots,
        "child_count": children,
        "unresolved_parent_count": unresolved,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_DESIGN_LINEAGE,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="design_lineage",
    )


def compute_replication_conditions(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    matched = sum(
        1 for row in data.comparisons if row.condition_comparison == "matched"
    )
    different = sum(
        1 for row in data.comparisons if row.condition_comparison == "different"
    )
    unknown = sum(
        1 for row in data.comparisons if row.condition_comparison == "unknown"
    )
    total = len(data.comparisons)
    values = {
        "comparison_count": total,
        "matched_count": matched,
        "different_count": different,
        "unknown_count": unknown,
        "matched_share_milli": _milli(matched, total),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_CONDITIONS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="condition_comparison",
    )


def compute_replication_results(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    paired = [
        row
        for row in data.comparisons
        if row.excluded_reason is None
        and row.source_outcome is not None
        and row.child_outcome is not None
    ]
    compatible = sum(1 for row in paired if row.appraisal == "compatible")
    conflicting = sum(1 for row in paired if row.appraisal == "conflicting")
    inconclusive = sum(1 for row in data.comparisons if row.appraisal == "inconclusive")
    not_comparable = sum(
        1 for row in data.comparisons if row.appraisal == "not_comparable"
    )
    differences = sum(
        1 for row in data.comparisons if row.category_difference is True
    )
    values = {
        "paired_count": len(paired),
        "compatible_count": compatible,
        "conflicting_count": conflicting,
        "inconclusive_count": inconclusive,
        "not_comparable_count": not_comparable,
        "category_difference_count": differences,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_RESULTS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="qualified_categories",
    )


def compute_replication_uncertainty(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    measurements = [row.fact.measurement for row in data.reports]
    declared = sum(1 for row in measurements if row.uncertainty_kind == "declared_set")
    unreported = sum(1 for row in measurements if row.uncertainty_kind == "unreported")
    ambiguous = sum(
        1 for row in measurements if len(row.possible_outcomes) > 1
    )
    total = len(measurements)
    values = {
        "measurement_count": total,
        "declared_set_count": declared,
        "unreported_count": unreported,
        "ambiguous_set_count": ambiguous,
        "unreported_share_milli": _milli(unreported, total),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_UNCERTAINTY,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="measurement_uncertainty",
    )


def compute_replication_relationships(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    repeat = sum(1 for row in data.comparisons if row.relation_kind == "repeat")
    adapted = sum(1 for row in data.comparisons if row.relation_kind == "adapted")
    execution_backed = sum(
        1
        for row in data.comparisons
        if row.evidence_qualification == "execution_backed"
    )
    declared_only = sum(
        1 for row in data.comparisons if row.evidence_qualification == "declared_only"
    )
    unresolved = sum(
        1 for row in data.comparisons if row.evidence_qualification == "unresolved"
    )
    values = {
        "attempt_count": len(data.attempts),
        "repeat_count": repeat,
        "adapted_count": adapted,
        "execution_backed_count": execution_backed,
        "declared_only_count": declared_only,
        "duplicate_source_count": 0,
        "unresolved_count": unresolved,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_RELATIONSHIPS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="relation_and_evidence",
    )


def compute_replication_social_interpretation(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    appraisals: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in data.interpretations:
        appraisals[
            (
                row.fact.design_token,
                row.fact.origin_report_token,
                row.fact.participant_token,
            )
        ].add(row.fact.appraisal)
    disagreement = sum(1 for values in appraisals.values() if len(values) > 1)
    declarations = sum(
        len(row.fact.participant_declarations) for row in data.collaborations
    )
    values = {
        "interpretation_count": len(data.interpretations),
        "trusted_count": sum(
            1
            for row in data.interpretations
            if row.fact.source_appraisal == "trusted_testimony"
        ),
        "contested_count": sum(
            1
            for row in data.interpretations
            if row.fact.source_appraisal == "contested_testimony"
        ),
        "unknown_source_count": sum(
            1
            for row in data.interpretations
            if row.fact.source_appraisal == "unknown"
        ),
        "disagreement_count": disagreement,
        "collaboration_count": len(data.collaborations),
        "participant_declaration_count": declarations,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_REPLICATION_SOCIAL_INTERPRETATION,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="social_interpretation",
    )
