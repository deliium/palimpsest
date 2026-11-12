"""Four detached credit relationship metric families (catalog 212 -> 216)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from analysis.credit_relationships_analysis import CreditRelationshipsAnalysis
from analysis.credit_relationships_contract import (
    CREDIT_ANALYSIS_FORBIDDEN_KEYS,
    CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
    CreditAlignment,
    CreditCoverage,
    CreditDistributionStatus,
    CreditOwnerStatus,
    CreditPerformanceOutcome,
    CreditRelationshipAnalysisError,
)
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
    "assemble_credit_relationship_metrics",
    "compute_credit_distribution_structure",
    "compute_credit_relationship_formation",
    "compute_credit_repayment_performance",
    "compute_credit_term_alignment",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "credit-relationships"


def _require(analysis: object) -> CreditRelationshipsAnalysis:
    if type(analysis) is not CreditRelationshipsAnalysis:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _state(coverage: CreditCoverage) -> str:
    if coverage is CreditCoverage.MISSING:
        return "unknown"
    if coverage is CreditCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden_fields(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in CREDIT_ANALYSIS_FORBIDDEN_KEYS:
            raise CreditRelationshipAnalysisError("credit_analysis_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
) -> MetricDocument:
    spec = metric_specification(family)
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
            observed=observed, expected=expected, ratio=_ratio(observed, expected)
        )
        _reject_forbidden_fields(values)
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
            source_kind="credit_relationships_analysis",
            source_ids=(
                run_id,
                input_revision,
                CREDIT_RELATIONSHIPS_ANALYSIS_POLICY_VERSION,
                _POLICY_TOKEN,
            ),
            notes_code="detached_credit_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def compute_credit_relationship_formation(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe owner credit relationship counts and confidence."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.relationship_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    relationships = rows.relationships
    pairs = {
        tuple(sorted((row.owner_token, row.counterparty_token)))
        for row in relationships
    }
    confidences = [row.confidence_milli for row in relationships]
    values = {
        "window_tick": rows.window_tick,
        "relationship_count": len(relationships),
        "proposed_count": sum(
            1
            for row in relationships
            if row.status is CreditOwnerStatus.PROPOSED
        ),
        "accepted_count": sum(
            1
            for row in relationships
            if row.status is CreditOwnerStatus.ACCEPTED
        ),
        "declined_count": sum(
            1
            for row in relationships
            if row.status is CreditOwnerStatus.DECLINED
        ),
        "withdrawn_count": sum(
            1
            for row in relationships
            if row.status is CreditOwnerStatus.WITHDRAWN
        ),
        "renegotiated_count": sum(
            row.renegotiate_count for row in relationships
        ),
        "distinct_counterparty_pairs": len(pairs),
        "collateral_claim_count": sum(
            1
            for row in relationships
            if row.collateral_kind not in {"none", "unspecified"}
        ),
        "conditional_count": sum(
            1
            for row in relationships
            if row.condition != "unspecified"
        ),
        "mean_confidence_milli": (
            0 if not confidences else sum(confidences) // len(confidences)
        ),
        "relationship_coverage": rows.relationship_coverage.value,
    }
    return _document(
        MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION,
        state=state,
        observed=sum(
            1
            for row in relationships
            if row.coverage is CreditCoverage.COMPLETE
        ),
        expected=len(relationships),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_credit_repayment_performance(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe descriptive performance outcomes and repayment ratios."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.performance_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    performances = rows.performances
    ratios = [
        row.repayment_quantity * 1_000 // row.principal_quantity
        for row in performances
        if row.principal_quantity > 0
    ]
    values = {
        "window_tick": rows.window_tick,
        "performance_count": len(performances),
        "repaid_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.REPAID
        ),
        "partially_repaid_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.PARTIALLY_REPAID
        ),
        "defaulted_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.DEFAULTED
        ),
        "forgiven_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.FORGIVEN
        ),
        "disputed_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.DISPUTED
        ),
        "expired_count": sum(
            1
            for row in performances
            if row.outcome is CreditPerformanceOutcome.EXPIRED
        ),
        "declared_repayment_count": sum(
            row.repay_count for row in performances
        ),
        "observed_transfer_count": sum(
            row.observed_transfer_count for row in performances
        ),
        "mean_repayment_ratio_milli": (
            0 if not ratios else sum(ratios) // len(ratios)
        ),
        "performance_coverage": rows.performance_coverage.value,
    }
    return _document(
        MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE,
        state=state,
        observed=sum(
            1
            for row in performances
            if row.coverage is CreditCoverage.COMPLETE
        ),
        expected=len(performances),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_credit_term_alignment(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe researcher-only alignment counts and gaps."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.alignment_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.CREDIT_TERM_ALIGNMENT,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    alignments = rows.alignments
    gaps = [
        row.gap_milli
        for row in alignments
        if row.alignment is not CreditAlignment.NOT_APPLICABLE
    ]
    values = {
        "window_tick": rows.window_tick,
        "alignment_row_count": len(alignments),
        "consistent_count": sum(
            1
            for row in alignments
            if row.alignment is CreditAlignment.CONSISTENT
        ),
        "unresolved_count": sum(
            1
            for row in alignments
            if row.alignment is CreditAlignment.UNRESOLVED
        ),
        "inconsistent_count": sum(
            1
            for row in alignments
            if row.alignment is CreditAlignment.INCONSISTENT
        ),
        "not_applicable_count": sum(
            1
            for row in alignments
            if row.alignment is CreditAlignment.NOT_APPLICABLE
        ),
        "mean_gap_milli": 0 if not gaps else sum(gaps) // len(gaps),
        "alignment_coverage": rows.alignment_coverage.value,
    }
    return _document(
        MetricFamilyId.CREDIT_TERM_ALIGNMENT,
        state=state,
        observed=sum(
            1
            for row in alignments
            if row.coverage is CreditCoverage.COMPLETE
        ),
        expected=len(alignments),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_credit_distribution_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Describe repayment-ratio distribution availability and shape."""

    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.distribution_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    distributions = rows.distributions
    available = [
        row
        for row in distributions
        if row.status is CreditDistributionStatus.AVAILABLE
    ]
    medians = sorted(row.median_ratio_milli for row in available)
    iqrs = [row.iqr_milli for row in available]
    dispersions = [row.dispersion_milli for row in available]
    median = (
        0 if not medians else medians[(len(medians) - 1) // 2]
    )
    values = {
        "window_tick": rows.window_tick,
        "distribution_count": len(distributions),
        "available_distribution_count": len(available),
        "insufficient_sample_count": sum(
            1
            for row in distributions
            if row.status is CreditDistributionStatus.INSUFFICIENT_SAMPLES
        ),
        "sample_count": sum(row.sample_count for row in distributions),
        "median_repayment_ratio_milli": median,
        "mean_iqr_milli": 0 if not iqrs else sum(iqrs) // len(iqrs),
        "mean_dispersion_milli": (
            0 if not dispersions else sum(dispersions) // len(dispersions)
        ),
        "distribution_coverage": rows.distribution_coverage.value,
    }
    return _document(
        MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE,
        state=state,
        observed=sum(row.sample_count for row in available),
        expected=sum(row.sample_count for row in distributions),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def assemble_credit_relationship_metrics(
    analysis: CreditRelationshipsAnalysis, *, run_id: str, input_revision: str
) -> tuple[MetricDocument, ...]:
    """Return the four credit families in catalog order."""

    return (
        compute_credit_relationship_formation(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_credit_repayment_performance(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_credit_term_alignment(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_credit_distribution_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
    )
