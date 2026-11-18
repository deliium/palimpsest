"""Six descriptive scientific-model metric families. Counts only."""

from __future__ import annotations

import logging
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
from analysis.scientific_models_contract import (
    FORBIDDEN_PREDICTIVE_KEYS,
    SCIENTIFIC_MODELS_ANALYSIS_POLICY,
    ScientificModelsAnalysisError,
)
from analysis.scientific_models_rows import ScientificModelsAnalysis
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_scientific_model_calibration",
    "compute_scientific_model_comparison",
    "compute_scientific_model_observed_outcomes",
    "compute_scientific_model_predictions",
    "compute_scientific_model_revisions",
    "compute_scientific_model_structure",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_models.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _require(analysis: object) -> ScientificModelsAnalysis:
    if type(analysis) is not ScientificModelsAnalysis:
        raise ScientificModelsAnalysisError("scientific_models_analysis_invalid_type")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _state(
    analysis: ScientificModelsAnalysis,
) -> tuple[str, int, int]:
    if analysis.export_status == "absent":
        return "unknown", 0, 0
    return (
        "present" if analysis.export_status == "complete" else "partial",
        analysis.owner_count,
        analysis.expected_owner_count,
    )


def _document(
    family: MetricFamilyId,
    analysis: ScientificModelsAnalysis,
    *,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    state, observed, expected = _state(analysis)
    for key in values:
        if str(key).lower() in FORBIDDEN_PREDICTIVE_KEYS:
            raise ScientificModelsAnalysisError(
                "scientific_models_analysis_forbidden_key"
            )
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
            source_kind="scientific_models_analysis",
            source_ids=(
                run_id,
                input_revision,
                SCIENTIFIC_MODELS_ANALYSIS_POLICY,
                "scientific-models",
                notes_code,
            ),
        ),
    )


def compute_scientific_model_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    values = {
        "model_count": len(data.models),
        "hypothesis_count": len(data.hypotheses),
        "target_kind_count": len({row.target_kind for row in data.hypotheses}),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_STRUCTURE,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="structure",
    )


def compute_scientific_model_predictions(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    pending = sum(1 for row in data.outcomes if row.state == "pending")
    values = {
        "prediction_count": len(data.predictions),
        "case_count": len(data.outcomes),
        "pending_case_count": pending,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_PREDICTIONS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="predictions",
    )


def compute_scientific_model_observed_outcomes(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    states = [row.state for row in data.outcomes]
    evicted = sum(
        row.count for row in data.coverage if row.reason_code == "retention_cap"
    )
    values = {
        "observed_case_count": states.count("scored"),
        "unavailable_case_count": states.count("unavailable"),
        "not_attempted_case_count": states.count("not_attempted"),
        "not_comparable_case_count": states.count("not_comparable"),
        "evicted_case_count": evicted,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_OBSERVED_OUTCOMES,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="outcomes",
    )


def compute_scientific_model_calibration(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    values = {
        "scored_prediction_count": sum(
            row.scored_count for row in data.calibration
        ),
        "calibration_group_count": len(data.calibration),
        "insufficient_group_count": sum(
            1 for row in data.calibration if row.insufficient
        ),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_CALIBRATION,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="calibration",
    )


def compute_scientific_model_revisions(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    values = {
        "revision_count": len(data.revisions),
        "source_revision_count": sum(
            1 for row in data.revisions if row.reason == "source_changed"
        ),
        "parameter_revision_count": sum(
            1 for row in data.revisions if row.reason == "parameter_updated"
        ),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_REVISIONS,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="revisions",
    )


def compute_scientific_model_comparison(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    data = _require(analysis)
    statuses = [row.status for row in data.comparisons]
    values = {
        "comparison_count": len(data.comparisons),
        "paired_case_count": sum(row.paired_count for row in data.comparisons),
        "lower_loss_a_count": statuses.count("lower_loss_a"),
        "lower_loss_b_count": statuses.count("lower_loss_b"),
        "tie_count": statuses.count("tied"),
        "insufficient_comparison_count": statuses.count("insufficient_samples"),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_MODEL_COMPARISON,
        data,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="comparison",
    )
