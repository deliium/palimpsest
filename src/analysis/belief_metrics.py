"""Belief accuracy and false-belief persistence metrics (Task 13).

Evaluates only claims covered by analysis-only ``ClaimTruthSpec``. Objective
truth never enters cognition. Missing/unevaluable claims stay ``unknown``.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Final

import numpy as np

from analysis.evidence import EvidenceStage
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    BeliefClaimRow,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from analysis.truth import (
    ClaimExpectedValue,
    ClaimTruthSpec,
    ClaimValueKind,
    TruthEvaluatorPolicy,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ClaimEvaluationOutcome",
    "compute_belief_accuracy",
    "compute_false_belief_persistence",
    "evaluate_claim_against_truth",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.belief_metrics")


class ClaimEvaluationOutcome(StrEnum):
    """Closed evaluation result for one claim revision vs a truth spec."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"
    OUT_OF_INTERVAL = "out_of_interval"


def evaluate_claim_against_truth(
    row: BeliefClaimRow,
    spec: ClaimTruthSpec,
) -> ClaimEvaluationOutcome:
    """Evaluate one belief claim against a typed truth specification."""
    if type(row) is not BeliefClaimRow:
        raise TypeError("evaluate_claim_against_truth: invalid_row")
    if type(spec) is not ClaimTruthSpec:
        raise TypeError("evaluate_claim_against_truth: invalid_spec")
    if row.claim_id != spec.claim_id:
        return ClaimEvaluationOutcome.UNKNOWN
    if row.logical_tick < spec.valid_from_tick:
        return ClaimEvaluationOutcome.OUT_OF_INTERVAL
    if spec.valid_to_tick is not None and row.logical_tick > spec.valid_to_tick:
        return ClaimEvaluationOutcome.OUT_OF_INTERVAL

    expected = spec.expected
    policy = spec.evaluator_policy
    if policy is TruthEvaluatorPolicy.EXACT_MATCH:
        return _exact_match(row, expected)
    if policy is TruthEvaluatorPolicy.CATEGORICAL_MEMBERSHIP:
        if expected.kind is not ClaimValueKind.CATEGORICAL:
            return ClaimEvaluationOutcome.UNKNOWN
        if row.categorical_value is None:
            return ClaimEvaluationOutcome.UNKNOWN
        if row.categorical_value == expected.categorical_value:
            return ClaimEvaluationOutcome.CORRECT
        return ClaimEvaluationOutcome.INCORRECT
    if policy is TruthEvaluatorPolicy.NUMERIC_TOLERANCE:
        if expected.kind is not ClaimValueKind.NUMERIC or row.numeric_value is None:
            return ClaimEvaluationOutcome.UNKNOWN
        assert expected.numeric_value is not None
        tolerance = 0.0 if spec.tolerance is None else spec.tolerance
        if abs(row.numeric_value - expected.numeric_value) <= tolerance:
            return ClaimEvaluationOutcome.CORRECT
        return ClaimEvaluationOutcome.INCORRECT
    return ClaimEvaluationOutcome.UNKNOWN


def _exact_match(
    row: BeliefClaimRow, expected: ClaimExpectedValue
) -> ClaimEvaluationOutcome:
    if expected.kind is ClaimValueKind.BOOLEAN:
        if row.bool_value is None:
            return ClaimEvaluationOutcome.UNKNOWN
        return (
            ClaimEvaluationOutcome.CORRECT
            if row.bool_value is expected.boolean_value
            else ClaimEvaluationOutcome.INCORRECT
        )
    if expected.kind is ClaimValueKind.CATEGORICAL:
        if row.categorical_value is None:
            return ClaimEvaluationOutcome.UNKNOWN
        return (
            ClaimEvaluationOutcome.CORRECT
            if row.categorical_value == expected.categorical_value
            else ClaimEvaluationOutcome.INCORRECT
        )
    if expected.kind is ClaimValueKind.NUMERIC:
        if row.numeric_value is None or expected.numeric_value is None:
            return ClaimEvaluationOutcome.UNKNOWN
        return (
            ClaimEvaluationOutcome.CORRECT
            if row.numeric_value == expected.numeric_value
            else ClaimEvaluationOutcome.INCORRECT
        )
    return ClaimEvaluationOutcome.UNKNOWN


def _document(
    *,
    family: str,
    algorithm_version: str,
    run_id: str,
    input_revision: str,
    evidence_stages: frozenset[EvidenceStage],
    population: str,
    denominator: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    coverage: MetricCoverage | None,
    notes_code: str,
) -> MetricDocument:
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=evidence_stages,
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="belief_metrics",
            source_ids=(),
            notes_code=notes_code,
        ),
    )


def compute_belief_accuracy(
    claims: Sequence[BeliefClaimRow],
    truth_specs: Sequence[ClaimTruthSpec],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Confidence-weighted and unweighted accuracy over evaluable claims."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.BELIEF_ACCURACY)

    specs_by_id = {item.claim_id: item for item in truth_specs}
    if not specs_by_id:
        _LOG.warning(
            "belief_accuracy_no_truth_specs",
            extra={
                "operation": "compute_belief_accuracy",
                "run_id": run_id,
                "reason_code": "no_truth_specs",
            },
        )
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=None,
            notes_code="no_truth_specs",
        )

    ordered = sorted(
        claims,
        key=lambda row: (row.logical_tick, row.owner_id, row.belief_id, row.claim_id),
    )
    evaluable = 0
    correct = 0
    unknown_excluded = 0
    weighted_sum = 0.0
    weight_total = 0.0
    missing_confidence = 0

    for row in ordered:
        truth = specs_by_id.get(row.claim_id)
        if truth is None:
            unknown_excluded += 1
            continue
        outcome = evaluate_claim_against_truth(row, truth)
        if outcome in (
            ClaimEvaluationOutcome.UNKNOWN,
            ClaimEvaluationOutcome.OUT_OF_INTERVAL,
        ):
            unknown_excluded += 1
            continue
        evaluable += 1
        is_correct = outcome is ClaimEvaluationOutcome.CORRECT
        if is_correct:
            correct += 1
        if row.confidence is None:
            missing_confidence += 1
        else:
            weighted_sum += float(row.confidence) * (1.0 if is_correct else 0.0)
            weight_total += float(row.confidence)

    if evaluable == 0:
        availability = MetricAvailability.UNKNOWN
        values: dict[str, object] = {
            "accuracy": None,
            "confidence_weighted_accuracy": None,
            "evaluable_count": 0,
            "unknown_excluded_count": unknown_excluded,
        }
        notes = "no_evaluable_claims"
    else:
        accuracy = quantize_float(require_finite(float(correct) / float(evaluable)))
        if weight_total > 0.0:
            cw = quantize_float(require_finite(weighted_sum / weight_total))
        elif missing_confidence == evaluable:
            cw = None
        else:
            cw = accuracy
        availability = MetricAvailability.PRESENT
        values = {
            "accuracy": accuracy,
            "confidence_weighted_accuracy": cw,
            "evaluable_count": evaluable,
            "unknown_excluded_count": unknown_excluded,
        }
        notes = "ok"

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "belief_accuracy_complete",
        extra={
            "operation": "compute_belief_accuracy",
            "run_id": run_id,
            "metric_family": spec.family_id.value,
            "algorithm_version": spec.algorithm_version,
            "evaluable_count": evaluable,
            "unknown_excluded_count": unknown_excluded,
            "availability": availability.value,
            "duration_ms": duration_ms,
        },
    )
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=availability,
        values=values,
        coverage=MetricCoverage(
            observed=evaluable,
            expected=evaluable + unknown_excluded,
            ratio=(
                None
                if evaluable + unknown_excluded == 0
                else float(evaluable) / float(evaluable + unknown_excluded)
            ),
        ),
        notes_code=notes,
    )


def _kaplan_meier_median(
    durations: Sequence[float], censored: Sequence[bool]
) -> float | None:
    """Kaplan–Meier median survival time; None if unidentified."""
    if not durations:
        return None
    pairs = sorted(zip(durations, censored, strict=True), key=lambda item: item[0])
    n = len(pairs)
    survival = 1.0
    at_risk = n
    for index, (duration, is_censored) in enumerate(pairs):
        if at_risk <= 0:
            break
        # Events at this time: uncensored with this duration.
        events = 0
        censored_here = 0
        j = index
        while j < len(pairs) and pairs[j][0] == duration:
            if pairs[j][1]:
                censored_here += 1
            else:
                events += 1
            j += 1
        if events > 0:
            survival *= 1.0 - (float(events) / float(at_risk))
            if survival <= 0.5:
                return quantize_float(require_finite(float(duration)))
        # Skip ahead past ties.
        if j > index + 1:
            # Will re-process via loop increment; adjust at_risk after tie group.
            pass
        at_risk -= events + censored_here
        # Advance index past tied group by mutating — use unique durations.
        # Simpler approach below.
    # Recompute with unique event times for clarity.
    unique_times = sorted({d for d, _ in pairs})
    survival = 1.0
    remaining = list(pairs)
    for t in unique_times:
        at_risk = sum(1 for d, _ in remaining if d >= t)
        if at_risk <= 0:
            break
        deaths = sum(1 for d, c in remaining if d == t and not c)
        if deaths > 0:
            survival *= 1.0 - float(deaths) / float(at_risk)
            if survival <= 0.5:
                return quantize_float(require_finite(float(t)))
        remaining = [(d, c) for d, c in remaining if d > t]
    return None


def compute_false_belief_persistence(
    claims: Sequence[BeliefClaimRow],
    truth_specs: Sequence[ClaimTruthSpec],
    *,
    run_id: str,
    input_revision: str,
    run_end_tick: int,
    death_ticks: Mapping[str, int] | None = None,
) -> MetricDocument:
    """Onset / correction / right-censored persistence for false evaluable beliefs."""
    started = time.perf_counter()
    run_id = require_stable_id("run_id", run_id)
    input_revision = require_stable_id("input_revision", input_revision)
    run_end_tick = require_exact_nonneg_int("run_end_tick", run_end_tick)
    deaths = dict(death_ticks or {})
    spec = metric_specification(MetricFamilyId.FALSE_BELIEF_PERSISTENCE)
    specs_by_id = {item.claim_id: item for item in truth_specs}

    if not specs_by_id:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.UNKNOWN,
            values={},
            coverage=None,
            notes_code="missing_truth_specs",
        )

    # Group by (owner, belief_id) ordered by tick.
    by_belief: dict[tuple[str, str], list[BeliefClaimRow]] = {}
    for row in claims:
        by_belief.setdefault((row.owner_id, row.belief_id), []).append(row)
    for key in by_belief:
        by_belief[key].sort(key=lambda item: (item.logical_tick, item.claim_id))

    durations: list[float] = []
    censored_flags: list[bool] = []
    onset_count = 0
    corrected = 0

    for (owner_id, _belief_id), revisions in sorted(by_belief.items()):
        onset_tick: int | None = None
        onset_claim: str | None = None
        for row in revisions:
            truth = specs_by_id.get(row.claim_id)
            if truth is None:
                continue
            outcome = evaluate_claim_against_truth(row, truth)
            if outcome is ClaimEvaluationOutcome.INCORRECT:
                if onset_tick is None:
                    onset_tick = row.logical_tick
                    onset_claim = row.claim_id
                    onset_count += 1
            elif (
                outcome is ClaimEvaluationOutcome.CORRECT
                and onset_tick is not None
                and onset_claim is not None
            ):
                duration = float(row.logical_tick - onset_tick)
                durations.append(duration)
                censored_flags.append(False)
                corrected += 1
                onset_tick = None
                onset_claim = None
            elif row.activation_state == "retired" and onset_tick is not None:
                duration = float(row.logical_tick - onset_tick)
                durations.append(duration)
                censored_flags.append(False)
                corrected += 1
                onset_tick = None
                onset_claim = None
        if onset_tick is not None:
            death = deaths.get(owner_id)
            end = run_end_tick if death is None else min(run_end_tick, death)
            durations.append(float(end - onset_tick))
            censored_flags.append(True)

    if onset_count == 0:
        return _document(
            family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            run_id=run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            availability=MetricAvailability.ABSENT,
            values={},
            coverage=None,
            notes_code="no_false_onsets",
        )

    median = _kaplan_meier_median(durations, censored_flags)
    censored_n = sum(1 for flag in censored_flags if flag)
    correction_rate = quantize_float(
        require_finite(float(corrected) / float(onset_count))
    )
    censored_fraction = quantize_float(
        require_finite(float(censored_n) / float(onset_count))
    )
    # Observed-length mean for labeled censored_mean policy (secondary).
    mean_duration = None
    if durations:
        arr = np.asarray(durations, dtype=np.float64)
        mean_duration = quantize_float(require_finite(float(np.mean(arr))))

    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "false_belief_persistence_complete",
        extra={
            "operation": "compute_false_belief_persistence",
            "run_id": run_id,
            "metric_family": spec.family_id.value,
            "onset_count": onset_count,
            "censored_count": censored_n,
            "duration_ms": duration_ms,
        },
    )
    values: dict[str, object] = {
        "median_false_duration_ticks": median,
        "correction_rate": correction_rate,
        "censored_fraction": censored_fraction,
        "onset_count": onset_count,
    }
    if mean_duration is not None and not math.isnan(mean_duration):
        values["mean_false_duration_ticks"] = mean_duration
    return _document(
        family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        availability=MetricAvailability.PRESENT,
        values=values,
        coverage=MetricCoverage(
            observed=onset_count,
            expected=onset_count,
            ratio=1.0,
        ),
        notes_code="ok",
    )
