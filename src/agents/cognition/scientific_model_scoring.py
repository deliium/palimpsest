"""Observation-relative predictive scoring, calibration, and comparison.

Performance is descriptive over the retained owner cohort. It is never a
scientific quality score, a universal ranking, or feedback into cognition.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import replace
from typing import Final

from agents.cognition.scientific_models import (
    MAX_PAIR_COMPARISONS,
    MAX_PERFORMANCE_SUMMARIES,
    CalibrationBin,
    ForecastCase,
    ForecastCaseState,
    ModelComparison,
    ModelComparisonStatus,
    ModelCoverageNotice,
    ModelObservedOutcome,
    ModelPerformanceSummary,
    ModelPrediction,
    ModelTargetKind,
    PredictiveModel,
    ScientificModelLedger,
    bump_notice,
    target_alphabet,
)

__all__ = [
    "MIN_PAIRED_SAMPLES",
    "compare_model_predictions",
    "recompute_model_accounting",
    "score_forecast_case",
    "score_model_prediction",
    "summarize_model_performance",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.scientific_model_scoring"
)

MIN_PAIRED_SAMPLES: Final[int] = 3


def _digest(*parts: str) -> str:
    material = "|".join(parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _fail(field_name: str, reason: str) -> ValueError:
    return ValueError(f"{field_name}: {reason}")


def _div_round_half_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise _fail("denominator", "invalid_range")
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def score_model_prediction(prediction: ModelPrediction, observed_class: str) -> int:
    """Return the exact per-case Brier numerator using the frozen distribution."""

    if type(prediction) is not ModelPrediction:
        raise _fail("prediction", "invalid_type")
    if observed_class not in prediction.alphabet:
        raise _fail("observed_class", "invalid_class")
    target = prediction.alphabet.index(observed_class)
    numerator = 0
    for index, probability in enumerate(prediction.probabilities_milli):
        expected = 1000 if index == target else 0
        numerator += (probability - expected) ** 2
    return numerator


def _condition_text(case: ForecastCase) -> str:
    return "|".join(f"{row.slot}={row.value_token}" for row in case.conditions)


def _cohort_key(case: ForecastCase) -> tuple[str, str, str, int, str]:
    return (
        case.target_kind.value,
        case.target_ref,
        case.unit_token,
        case.horizon_ticks,
        "ctx:"
        + _digest(
            case.target_kind.value,
            case.target_ref,
            case.unit_token,
            str(case.horizon_ticks),
            _condition_text(case),
        ),
    )


def score_forecast_case(
    case: ForecastCase, observed: ModelObservedOutcome
) -> ForecastCase:
    """Attach an actual owner observation and mark a pending case scored."""

    if type(case) is not ForecastCase:
        raise _fail("case", "invalid_type")
    if type(observed) is not ModelObservedOutcome:
        raise _fail("observed", "invalid_type")
    if case.state is not ForecastCaseState.PENDING:
        raise _fail("case", "already_terminal")
    if observed.observed_tick != case.target_observation_tick:
        raise _fail("observed", "invalid_tick")
    if observed.observed_class not in case.alphabet:
        raise _fail("observed", "invalid_class")
    return replace(
        case,
        state=ForecastCaseState.SCORED,
        observed=observed,
        outcome_refs=(
            *case.outcome_refs[:1],
            observed.outcome_ref,
        )[:2],
    )


def _summary_id(
    owner_id: str, model_id: str, cohort_key: tuple[str, str, str, int, str]
) -> str:
    kind, target_ref, unit_token, horizon, context = cohort_key
    return "sms:" + _digest(
        owner_id, model_id, kind, target_ref, unit_token, str(horizon), context
    )


def summarize_model_performance(
    cases: tuple[ForecastCase, ...],
    model_id: str,
    *,
    owner_id: str,
    evaluated_tick: int,
) -> ModelPerformanceSummary | None:
    """Summarize one model/cohort over retained cases only."""

    if not isinstance(cases, tuple):
        raise _fail("cases", "invalid_type")
    if type(model_id) is not str or not model_id:
        raise _fail("model_id", "invalid_type")
    cohort: list[ForecastCase] = []
    for case in cases:
        if not any(prediction.model_id == model_id for prediction in case.predictions):
            continue
        cohort.append(case)
    if not cohort:
        return None
    key = _cohort_key(cohort[0])
    if any(_cohort_key(case) != key for case in cohort):
        raise _fail("cases", "mixed_cohort")
    target_kind = cohort[0].target_kind
    alphabet = target_alphabet(target_kind)
    scored = [case for case in cohort if case.observed is not None]
    if not scored:
        return None
    if any(case.observed is None for case in scored):
        raise _fail("cases", "missing_outcome")
    counts = {
        ForecastCaseState.PENDING: 0,
        ForecastCaseState.NOT_ATTEMPTED: 0,
        ForecastCaseState.NOT_COMPARABLE: 0,
        ForecastCaseState.UNAVAILABLE: 0,
    }
    missing = 0
    for case in cohort:
        if case.observed is not None:
            continue
        counts[case.state] = counts.get(case.state, 0) + 1
        if case.target_observation_tick < evaluated_tick:
            missing += 1
    numerator_sum = 0
    hit_count = 0
    bins = [{"count": 0, "confidence": 0, "hits": 0} for _ in range(10)]
    for case in scored:
        assert case.observed is not None
        prediction = next(row for row in case.predictions if row.model_id == model_id)
        numerator_sum += score_model_prediction(
            prediction, case.observed.observed_class
        )
        hit = prediction.predicted_class == case.observed.observed_class
        hit_count += int(hit)
        index = min(prediction.confidence_milli // 100, 9)
        bins[index]["count"] += 1
        bins[index]["confidence"] += prediction.confidence_milli
        bins[index]["hits"] += int(hit)
    total = len(scored)
    gap_numerator = sum(
        abs(1000 * row["hits"] - row["confidence"]) for row in bins if row["count"] > 0
    )
    calibration_bins = tuple(
        CalibrationBin(
            bin_index=index,
            count=row["count"],
            confidence_sum_milli=row["confidence"],
            hit_count=row["hits"],
        )
        for index, row in enumerate(bins)
        if row["count"] > 0
    )
    return ModelPerformanceSummary(
        summary_id=_summary_id(owner_id, model_id, key),
        owner_id=cohort[0].owner_id,
        model_id=model_id,
        target_kind=target_kind,
        target_ref=cohort[0].target_ref,
        unit_token=cohort[0].unit_token,
        horizon_ticks=cohort[0].horizon_ticks,
        context_digest=key[4],
        alphabet=alphabet,
        scored_count=total,
        hit_count=hit_count,
        hit_share_milli=_div_round_half_even(1000 * hit_count, total),
        brier_numerator_sum=numerator_sum,
        mean_brier_millionths=_div_round_half_even(numerator_sum, total),
        calibration_gap_milli=_div_round_half_even(gap_numerator, total),
        calibration_bins=calibration_bins,
        evicted_count=0,
        missing_count=missing,
        pending_count=counts[ForecastCaseState.PENDING],
        unavailable_count=counts[ForecastCaseState.UNAVAILABLE],
        not_attempted_count=counts[ForecastCaseState.NOT_ATTEMPTED],
        not_comparable_count=counts[ForecastCaseState.NOT_COMPARABLE],
        retained_floor_tick=min(case.issued_observation_tick for case in cohort),
    )


def compare_model_predictions(
    cases: tuple[ForecastCase, ...],
    model_a_id: str,
    model_b_id: str,
) -> ModelComparison:
    """Paired descriptive comparison over identical retained cases."""

    if model_a_id == model_b_id:
        raise _fail("model_b_id", "same_model")
    paired: list[ForecastCase] = []
    excluded = 0
    for case in cases:
        model_ids = {row.model_id for row in case.predictions}
        if model_a_id not in model_ids or model_b_id not in model_ids:
            continue
        if case.observed is None:
            excluded += 1
            continue
        paired.append(case)
    if not paired:
        raise _fail("cases", "no_comparable_outcome")
    key = _cohort_key(paired[0])
    if any(_cohort_key(case) != key for case in paired):
        raise _fail("cases", "mixed_cohort")
    owners = {case.owner_id for case in paired}
    if len(owners) != 1:
        raise _fail("cases", "owner_mismatch")
    loss_a = 0
    loss_b = 0
    for case in paired:
        assert case.observed is not None
        prediction_a = next(
            row for row in case.predictions if row.model_id == model_a_id
        )
        prediction_b = next(
            row for row in case.predictions if row.model_id == model_b_id
        )
        loss_a += score_model_prediction(prediction_a, case.observed.observed_class)
        loss_b += score_model_prediction(prediction_b, case.observed.observed_class)
    count = len(paired)
    mean_a = _div_round_half_even(loss_a, count)
    mean_b = _div_round_half_even(loss_b, count)
    if count < MIN_PAIRED_SAMPLES:
        status = ModelComparisonStatus.INSUFFICIENT_SAMPLES
    elif mean_a < mean_b:
        status = ModelComparisonStatus.LOWER_LOSS_A
    elif mean_b < mean_a:
        status = ModelComparisonStatus.LOWER_LOSS_B
    else:
        status = ModelComparisonStatus.TIED
    owner = paired[0].owner_id
    comparison_id = "smcomp:" + _digest(
        owner.value,
        model_a_id,
        model_b_id,
        *sorted(case.case_id for case in paired),
    )
    return ModelComparison(
        comparison_id=comparison_id,
        owner_id=owner,
        target_kind=paired[0].target_kind,
        target_ref=paired[0].target_ref,
        unit_token=paired[0].unit_token,
        horizon_ticks=paired[0].horizon_ticks,
        context_digest=key[4],
        model_a_id=model_a_id,
        model_b_id=model_b_id,
        paired_count=count,
        excluded_count=excluded,
        mean_brier_millionths_a=mean_a,
        mean_brier_millionths_b=mean_b,
        a_minus_b_millionths=mean_a - mean_b,
        status=status,
    )


def _summary_notice(
    notices: tuple[ModelCoverageNotice, ...],
    *,
    tick: int,
    target_kind: ModelTargetKind,
) -> tuple[ModelCoverageNotice, ...]:
    return bump_notice(
        notices,
        reason_code="summary_cap",
        target_kind=target_kind,
        tick=tick,
    )


def recompute_model_accounting(
    ledger: ScientificModelLedger, *, evaluated_tick: int | None = None
) -> ScientificModelLedger:
    """Recompute summaries and pair comparisons from retained terminal cases."""

    if type(ledger) is not ScientificModelLedger:
        raise _fail("ledger", "invalid_type")
    tick = ledger.last_observation_tick if evaluated_tick is None else evaluated_tick
    summaries: list[ModelPerformanceSummary] = []
    notices = ledger.notices
    for model in ledger.models:
        summary = summarize_model_performance(
            ledger.cases,
            model.model_id,
            owner_id=ledger.owner_id.value,
            evaluated_tick=tick,
        )
        if summary is None:
            continue
        if len(summaries) >= MAX_PERFORMANCE_SUMMARIES:
            notices = _summary_notice(notices, tick=tick, target_kind=model.target_kind)
            break
        summaries.append(replace(summary, evicted_count=ledger.evicted_cases))
    comparisons: list[ModelComparison] = []
    paired_models: dict[tuple[str, str], list[PredictiveModel]] = {}
    for model in ledger.models:
        if model.predictor_variant.value == "hypothesis_baseline_v1":
            other = next(
                (
                    row
                    for row in ledger.models
                    if row.hypothesis_id == model.hypothesis_id
                    and row.model_id != model.model_id
                ),
                None,
            )
            if other is None:
                continue
            pair_key = tuple(sorted((model.model_id, other.model_id)))
            paired_models[(pair_key[0], pair_key[1])] = [model, other]
    for _, (first, second) in sorted(paired_models.items()):
        try:
            comparison = compare_model_predictions(
                ledger.cases, first.model_id, second.model_id
            )
        except ValueError:
            continue
        if len(comparisons) >= MAX_PAIR_COMPARISONS:
            break
        comparisons.append(comparison)
    updated = replace(
        ledger,
        summaries=tuple(summaries),
        comparisons=tuple(comparisons),
        notices=notices,
    )
    _LOG.debug(
        "scientific_model_accounting owner_id=%s summary_count=%s "
        "comparison_count=%s evaluated_tick=%s",
        ledger.owner_id.value,
        len(summaries),
        len(comparisons),
        tick,
    )
    return updated
