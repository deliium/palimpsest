"""Bounded detached predictive analysis. Independent of cognition scoring."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import replace
from typing import Final

from analysis.scientific_models_contract import (
    MAX_PREDICTIVE_WINDOWS,
    MINIMUM_PAIRED_SAMPLES,
    SCIENTIFIC_MODELS_WINDOW_TICKS,
    PriorPredictionFact,
    ScientificModelsAnalysisError,
)
from analysis.scientific_models_rows import (
    ModelCalibrationFact,
    ModelComparisonFact,
    ScientificModelsAnalysis,
)

__all__ = ["harvest_scientific_models_analysis"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.scientific_models.analysis")


def _fail(code: str) -> ScientificModelsAnalysisError:
    return ScientificModelsAnalysisError(code)


def _div_round_half_even(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise _fail("scientific_models_analysis_invalid_denominator")
    quotient, remainder = divmod(numerator, denominator)
    doubled = 2 * remainder
    if doubled > denominator or (doubled == denominator and quotient % 2 == 1):
        quotient += 1
    return quotient


def _group_token(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:32]


def _brier(prediction: PriorPredictionFact, observed_class: str) -> int:
    target = prediction.alphabet.index(observed_class)
    total = 0
    for index, probability in enumerate(prediction.probabilities_milli):
        expected = 1000 if index == target else 0
        total += (probability - expected) ** 2
    return total


def harvest_scientific_models_analysis(
    analysis: object,
) -> ScientificModelsAnalysis:
    """Verify closure and derive calibration/comparison rows over 32-tick windows."""

    if type(analysis) is not ScientificModelsAnalysis:
        raise _fail("scientific_models_analysis_invalid_type")
    outcomes = {row.case_token: row for row in analysis.outcomes}
    models = {row.model_token: row for row in analysis.models}
    windows = sorted(
        {
            row.issued_tick // SCIENTIFIC_MODELS_WINDOW_TICKS
            for row in analysis.predictions
        }
    )[-MAX_PREDICTIVE_WINDOWS:]
    kept_windows = set(windows)
    predictions = [
        row
        for row in analysis.predictions
        if row.issued_tick // SCIENTIFIC_MODELS_WINDOW_TICKS in kept_windows
    ]
    for prediction in predictions:
        if prediction.model_token not in models:
            raise _fail("scientific_models_revision_missing")
        outcome = outcomes.get(prediction.case_token)
        if outcome is None:
            raise _fail("scientific_models_outcome_missing")
        if (
            outcome.target_kind != prediction.target_kind
            or outcome.target_token != prediction.target_token
            or outcome.unit_token != prediction.unit_token
            or outcome.horizon_ticks != prediction.horizon_ticks
        ):
            raise _fail("scientific_models_comparable_mismatch")
        if outcome.observed_tick is not None and (
            outcome.observed_tick <= prediction.committed_after_tick
        ):
            raise _fail("scientific_models_precommit_outcome")

    scored: list[tuple[PriorPredictionFact, str]] = []
    for prediction in predictions:
        outcome = outcomes[prediction.case_token]
        if outcome.state != "scored" or outcome.observed_class is None:
            continue
        if outcome.observed_class not in prediction.alphabet:
            raise _fail("scientific_models_outcome_unknown_class")
        scored.append((prediction, outcome.observed_class))

    calibration_groups: dict[str, list[tuple[PriorPredictionFact, str]]] = defaultdict(
        list
    )
    for prediction, observed_class in scored:
        key = _group_token(
            "calibration",
            prediction.target_kind,
            prediction.target_token,
            prediction.unit_token,
            str(prediction.horizon_ticks),
            prediction.context_token,
            prediction.model_token,
        )
        calibration_groups[key].append((prediction, observed_class))
    calibration: list[ModelCalibrationFact] = []
    for group_token, group_rows in sorted(calibration_groups.items()):
        numerator = sum(
            _brier(prediction, observed) for prediction, observed in group_rows
        )
        hits = 0
        confidence_sum = 0
        bins: dict[int, tuple[int, int, int]] = {}
        for prediction, observed in group_rows:
            hit = int(prediction.predicted_class == observed)
            hits += hit
            confidence_sum += prediction.confidence_milli
            index = min(prediction.confidence_milli // 100, 9)
            count, sum_confidence, bin_hits = bins.get(index, (0, 0, 0))
            bins[index] = (
                count + 1,
                sum_confidence + prediction.confidence_milli,
                bin_hits + hit,
            )
        gap_numerator = sum(
            abs(1000 * bin_hits - sum_confidence)
            for _, sum_confidence, bin_hits in bins.values()
        )
        calibration.append(
            ModelCalibrationFact(
                group_token=group_token,
                target_kind=group_rows[0][0].target_kind,
                model_token=group_rows[0][0].model_token,
                scored_count=len(group_rows),
                brier_numerator_sum=numerator,
                mean_brier_millionths=_div_round_half_even(numerator, len(group_rows)),
                calibration_gap_milli=(
                    None
                    if not group_rows
                    else _div_round_half_even(gap_numerator, len(group_rows))
                ),
                insufficient=len(group_rows) < MINIMUM_PAIRED_SAMPLES,
            )
        )

    pair_groups: dict[str, list[PriorPredictionFact]] = defaultdict(list)
    for prediction in predictions:
        key = _group_token(
            "comparison",
            prediction.target_kind,
            prediction.target_token,
            prediction.unit_token,
            str(prediction.horizon_ticks),
            prediction.context_token,
        )
        pair_groups[key].append(prediction)
    comparisons: list[ModelComparisonFact] = []
    for group_token, pair_rows in sorted(pair_groups.items()):
        by_case: dict[str, dict[str, PriorPredictionFact]] = defaultdict(dict)
        for prediction in pair_rows:
            variant = models[prediction.model_token].predictor_variant
            by_case[prediction.case_token][variant] = prediction
        pairs: list[tuple[PriorPredictionFact, PriorPredictionFact, str]] = []
        for case_token, variants in by_case.items():
            baseline = variants.get("hypothesis_baseline_v1")
            empirical = variants.get("empirical_context_v1")
            outcome = outcomes.get(case_token)
            if baseline is None or empirical is None:
                continue
            if (
                outcome is None
                or outcome.state != "scored"
                or outcome.observed_class is None
            ):
                continue
            pairs.append((baseline, empirical, outcome.observed_class))
        if not pairs:
            continue
        losses_a = sum(_brier(a, observed) for a, _, observed in pairs)
        losses_b = sum(_brier(b, observed) for _, b, observed in pairs)
        count = len(pairs)
        mean_a = _div_round_half_even(losses_a, count)
        mean_b = _div_round_half_even(losses_b, count)
        if count < MINIMUM_PAIRED_SAMPLES:
            status = "insufficient_samples"
        elif mean_a < mean_b:
            status = "lower_loss_a"
        elif mean_b < mean_a:
            status = "lower_loss_b"
        else:
            status = "tied"
        comparisons.append(
            ModelComparisonFact(
                group_token=group_token,
                target_kind=pair_rows[0].target_kind,
                model_a_token=pairs[0][0].model_token,
                model_b_token=pairs[0][1].model_token,
                paired_count=count,
                mean_brier_millionths_a=mean_a,
                mean_brier_millionths_b=mean_b,
                a_minus_b_millionths=mean_a - mean_b,
                status=status,
            )
        )
    _LOG.debug(
        "scientific_models_harvested prediction_count=%s calibration_groups=%s "
        "comparisons=%s windows=%s",
        len(predictions),
        len(calibration),
        len(comparisons),
        len(windows),
    )
    return replace(
        analysis,
        predictions=tuple(predictions),
        calibration=tuple(calibration),
        comparisons=tuple(comparisons),
    )
