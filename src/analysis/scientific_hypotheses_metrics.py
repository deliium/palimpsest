"""Six detached scientific-hypothesis metric families (catalog 244 -> 250)."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.scientific_hypotheses_analysis import ScientificHypothesesAnalysis
from analysis.scientific_hypotheses_contract import (
    SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS,
    SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
    ScientificHypothesesError,
    ScientificHypothesisAvailability,
    ScientificHypothesisCoverage,
    ScientificHypothesisRevisionReason,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import (
    ScientificHypothesisRow,
    ScientificTrialRow,
)
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_scientific_hypothesis_evidence",
    "compute_scientific_hypothesis_prediction_outcomes",
    "compute_scientific_hypothesis_provenance",
    "compute_scientific_hypothesis_revisions",
    "compute_scientific_hypothesis_structure",
    "compute_scientific_hypothesis_test_activity",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.scientific_hypotheses.metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _require(analysis: object) -> ScientificHypothesesAnalysis:
    if type(analysis) is not ScientificHypothesesAnalysis:
        raise ScientificHypothesesError("scientific_hypotheses_invalid_hypothesis")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _reject_forbidden(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in SCIENTIFIC_HYPOTHESES_FORBIDDEN_KEYS:
            raise ScientificHypothesesError("scientific_hypotheses_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
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
            observed=observed,
            expected=expected,
            ratio=_ratio(observed, expected),
        )
        _reject_forbidden(values)
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
            source_kind="scientific_hypotheses_analysis",
            source_ids=(
                run_id,
                input_revision,
                SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
                "scientific-hypotheses",
                notes_code,
            ),
        ),
    )


def _latest_window(analysis: ScientificHypothesesAnalysis) -> int:
    if not analysis.coverage_rows:
        return 0
    return max(row.window_index for row in analysis.coverage_rows)


def _is_missing(analysis: ScientificHypothesesAnalysis) -> bool:
    if not analysis.hypothesis_rows:
        return True
    return all(
        row.coverage is ScientificHypothesisCoverage.MISSING
        for row in analysis.coverage_rows
    )


def _state(analysis: ScientificHypothesesAnalysis) -> str:
    if _is_missing(analysis):
        return "unknown"
    if any(
        row.availability is ScientificHypothesisAvailability.AVAILABLE
        for row in analysis.coverage_rows
    ):
        return "present"
    return "partial"


def _hypotheses(
    analysis: ScientificHypothesesAnalysis,
) -> tuple[ScientificHypothesisRow, ...]:
    window = _latest_window(analysis)
    return tuple(
        row for row in analysis.hypothesis_rows if row.window_index == window
    )


def _trials(
    analysis: ScientificHypothesesAnalysis,
) -> tuple[ScientificTrialRow, ...]:
    window = _latest_window(analysis)
    return tuple(row for row in analysis.trial_rows if row.window_index == window)


def _milli(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return (numerator * 1_000) // denominator


def _confidence_stats(rows: Sequence[ScientificHypothesisRow]) -> tuple[int, int, int]:
    if not rows:
        return 0, 0, 0
    values = [row.confidence_milli for row in rows]
    return sum(values) // len(values), min(values), max(values)


def compute_scientific_hypothesis_structure(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    hypotheses = _hypotheses(value)
    total = len(hypotheses)
    condition_count = sum(row.condition_count for row in hypotheses)
    status_counts = {
        status: sum(1 for row in hypotheses if row.status is status)
        for status in ScientificHypothesisStatus
    }
    values: dict[str, object] = {
        "hypothesis_count": total,
        "active_count": sum(1 for row in hypotheses if row.active),
        "provisional_count": status_counts[ScientificHypothesisStatus.PROVISIONAL],
        "supported_count": status_counts[ScientificHypothesisStatus.SUPPORTED],
        "contradicted_count": status_counts[ScientificHypothesisStatus.CONTRADICTED],
        "inconclusive_count": status_counts[ScientificHypothesisStatus.INCONCLUSIVE],
        "superseded_count": status_counts[ScientificHypothesisStatus.SUPERSEDED],
        "retired_count": status_counts[ScientificHypothesisStatus.RETIRED],
        "condition_count": condition_count,
        "claim_count": len({row.claim_token for row in hypotheses}),
        "mean_conditions_milli": _milli(condition_count, total),
        "coverage_ratio_milli": (
            1_000
            if all(
                row.coverage is ScientificHypothesisCoverage.COMPLETE
                for row in hypotheses
            )
            else 500
        ),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_STRUCTURE,
        state=_state(value),
        observed=total,
        expected=max(total, 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="structure",
    )


def compute_scientific_hypothesis_evidence(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    hypotheses = _hypotheses(value)
    support = sum(row.support_count for row in hypotheses)
    contradiction = sum(row.contradiction_count for row in hypotheses)
    with_support = sum(1 for row in hypotheses if row.support_count > 0)
    with_contradiction = sum(
        1 for row in hypotheses if row.contradiction_count > 0
    )
    confidence_mean, confidence_min, confidence_max = _confidence_stats(hypotheses)
    values: dict[str, object] = {
        "support_observation_count": support,
        "contradiction_count": contradiction,
        "hypotheses_with_support": with_support,
        "hypotheses_with_contradiction": with_contradiction,
        "evidence_event_count": len(value.objective_rows),
        "unresolved_evidence_count": sum(
            1 for row in hypotheses if row.support_count + row.contradiction_count == 0
        ),
        "support_share_milli": _milli(support, support + contradiction),
        "contradiction_share_milli": _milli(contradiction, support + contradiction),
        "confidence_mean_milli": confidence_mean,
        "confidence_min_milli": confidence_min,
        "confidence_max_milli": confidence_max,
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_EVIDENCE,
        state=_state(value),
        observed=support + contradiction,
        expected=max(support + contradiction, 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="evidence",
    )


def compute_scientific_hypothesis_test_activity(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    hypotheses = _hypotheses(value)
    trials = _trials(value)
    trial_count = sum(row.trial_count for row in trials)
    tested = sum(
        1
        for hypothesis in hypotheses
        if hypothesis.hypothesis_token
        in {trial.hypothesis_token for trial in trials}
    )
    formulated = sum(
        1
        for row in value.revision_rows
        if row.reason is ScientificHypothesisRevisionReason.TEST_FORMULATED
    )
    values: dict[str, object] = {
        "test_formulated_count": formulated,
        "trial_count": trial_count,
        "deliberate_trial_count": sum(row.deliberate_count for row in trials),
        "accidental_trial_count": sum(row.accidental_count for row in trials),
        "tested_hypothesis_count": tested,
        "untested_hypothesis_count": max(0, len(hypotheses) - tested),
        "mean_trials_milli": _milli(trial_count, len(hypotheses)),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_TEST_ACTIVITY,
        state=_state(value),
        observed=trial_count,
        expected=max(trial_count, 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="test_activity",
    )


def compute_scientific_hypothesis_revisions(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    hypotheses = _hypotheses(value)
    rows = value.revision_rows
    reasons = {
        reason: sum(1 for row in rows if row.reason is reason)
        for reason in ScientificHypothesisRevisionReason
    }
    depths = [row.revision_count for row in hypotheses]
    values: dict[str, object] = {
        "revision_count": len(rows),
        "revised_hypothesis_count": sum(1 for depth in depths if depth > 0),
        "formulated_revision_count": reasons[
            ScientificHypothesisRevisionReason.FORMULATED
        ],
        "prediction_revision_count": reasons[
            ScientificHypothesisRevisionReason.PREDICTION_REVISED
        ],
        "condition_revision_count": reasons[
            ScientificHypothesisRevisionReason.CONDITION_REVISED
        ],
        "evidence_revision_count": (
            reasons[ScientificHypothesisRevisionReason.SUPPORT_ADDED]
            + reasons[ScientificHypothesisRevisionReason.CONTRADICTION_ADDED]
        ),
        "source_revision_count": reasons[
            ScientificHypothesisRevisionReason.SOURCE_ADOPTED
        ],
        "superseded_revision_count": reasons[
            ScientificHypothesisRevisionReason.SUPERSEDED
        ],
        "mean_revision_depth_milli": _milli(sum(depths), len(hypotheses)),
        "max_revision_depth": max(depths, default=0),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_REVISIONS,
        state=_state(value),
        observed=len(rows),
        expected=max(len(rows), 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="revisions",
    )


def compute_scientific_hypothesis_provenance(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    hypotheses = _hypotheses(value)
    counts = {
        kind: sum(1 for row in hypotheses if row.source_kind is kind)
        for kind in ScientificHypothesisSourceKind
    }
    communicated = counts[ScientificHypothesisSourceKind.COMMUNICATED]
    values: dict[str, object] = {
        "self_formulated_count": counts[
            ScientificHypothesisSourceKind.SELF_FORMULATED
        ],
        "observed_count": counts[ScientificHypothesisSourceKind.OBSERVED],
        "remembered_count": counts[ScientificHypothesisSourceKind.REMEMBERED],
        "communicated_count": communicated,
        "recorded_count": counts[ScientificHypothesisSourceKind.RECORDED],
        "unknown_count": counts[ScientificHypothesisSourceKind.UNKNOWN],
        "adopted_count": communicated,
        "communicated_share_milli": _milli(communicated, len(hypotheses)),
        "independent_evidence_count": sum(
            1
            for row in hypotheses
            if row.source_kind is not ScientificHypothesisSourceKind.COMMUNICATED
            and row.support_count + row.contradiction_count > 0
        ),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_PROVENANCE,
        state=_state(value),
        observed=len(hypotheses),
        expected=max(len(hypotheses), 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="provenance",
    )


def compute_scientific_hypothesis_prediction_outcomes(
    analysis: ScientificHypothesesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    window = _latest_window(value)
    rows = tuple(
        row for row in value.outcome_rows if row.window_index == window
    )
    matched = sum(row.matched_count for row in rows)
    mismatched = sum(row.mismatched_count for row in rows)
    inconclusive = sum(row.trial_count - row.matched_count - row.mismatched_count for row in rows)  # noqa: E501
    by_class = {row.outcome_class.value: row.trial_count for row in rows}
    values: dict[str, object] = {
        "matched_count": matched,
        "mismatched_count": mismatched,
        "inconclusive_count": inconclusive,
        "unexpected_count": by_class.get("unexpected", 0),
        "success_count": by_class.get("success", 0),
        "partial_success_count": by_class.get("partial_success", 0),
        "failure_count": by_class.get("failure", 0),
        "harm_count": by_class.get("harm", 0),
        "matched_share_milli": _milli(matched, matched + mismatched),
        "mismatched_share_milli": _milli(mismatched, matched + mismatched),
    }
    return _document(
        MetricFamilyId.SCIENTIFIC_HYPOTHESIS_PREDICTION_OUTCOMES,
        state=_state(value),
        observed=matched + mismatched,
        expected=max(matched + mismatched + inconclusive, 1),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="prediction_outcomes",
    )
