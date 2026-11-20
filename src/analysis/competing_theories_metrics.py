"""Six descriptive competing-theory metric families. Counts only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from analysis.competing_theories_models import CompetingTheoryAnalysis
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_competing_theory_citations",
    "compute_competing_theory_failures",
    "compute_competing_theory_predictions",
    "compute_competing_theory_structure",
    "compute_competing_theory_support_network",
    "compute_competing_theory_transmission",
]

_ABSENT: Final[MetricCoverage] = MetricCoverage(observed=0, expected=0, ratio=None)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _document(
    family: MetricFamilyId,
    analysis: CompetingTheoryAnalysis,
    *,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    if analysis.coverage:
        last = analysis.coverage[-1]
        observed = last.observed_owners
        expected = last.expected_owners
    else:
        observed = 0
        expected = 0
    availability = (
        MetricAvailability.PRESENT
        if expected > 0 and observed > 0
        else MetricAvailability.PARTIAL
    )
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
        coverage=(
            MetricCoverage(
                observed=observed,
                expected=expected,
                ratio=_ratio(observed, expected),
            )
            if expected
            else _ABSENT
        ),
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="competing_theories_analysis",
            source_ids=(
                run_id,
                input_revision,
                "competing-theories-analysis.v1",
                "competing-theories",
                notes_code,
            ),
        ),
    )


def _require(analysis: object) -> CompetingTheoryAnalysis:
    if type(analysis) is not CompetingTheoryAnalysis:
        raise ValueError("competing_theories_analysis_invalid_type")
    return analysis


def compute_competing_theory_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_STRUCTURE,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "claim_count": data.claim_count,
            "rival_pair_count": data.rival_pair_count,
        },
        notes_code="structure",
    )


def compute_competing_theory_support_network(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_SUPPORT_NETWORK,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "support_edge_count": data.support_edge_count,
            "community_count": data.community_count,
        },
        notes_code="support",
    )


def compute_competing_theory_citations(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_CITATIONS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "citation_count": data.citation_count,
            "verified_root_count": data.verified_root_count,
        },
        notes_code="citations",
    )


def compute_competing_theory_predictions(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_PREDICTIONS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "prediction_count": data.prediction_count,
            "scored_count": data.scored_count,
        },
        notes_code="predictions",
    )


def compute_competing_theory_failures(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_FAILURES,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "failure_count": data.failure_count,
            "unscored_count": data.unscored_count,
        },
        notes_code="failures",
    )


def compute_competing_theory_transmission(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    return _document(
        MetricFamilyId.COMPETING_THEORY_TRANSMISSION,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values={
            "delivered_count": data.delivered_count,
            "teaching_count": data.teaching_count,
        },
        notes_code="transmission",
    )
