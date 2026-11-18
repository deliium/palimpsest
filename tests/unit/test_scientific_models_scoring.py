"""Observation-relative calibration, exact Brier arithmetic and comparison."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.experimentation import ExperimentLedger
from agents.cognition.scientific_model_derivation import derive_model_hypotheses
from agents.cognition.scientific_model_prediction import issue_model_forecasts
from agents.cognition.scientific_model_scoring import (
    compare_model_predictions,
    recompute_model_accounting,
    score_forecast_case,
    score_model_prediction,
    summarize_model_performance,
)
from agents.cognition.scientific_models import (
    SEASON_CLASSES,
    CalibrationBin,
    ForecastCase,
    ForecastCaseState,
    ModelComparisonStatus,
    ModelObservedOutcome,
    ModelPrediction,
    ModelPredictorVariant,
    ModelRevisionReason,
    ModelTargetKind,
    ScientificModelLedger,
    empty_scientific_model_ledger,
    scientific_prediction_id,
)
from world.environment import Season
from world.identifiers import AgentId, EntityId, WorldId, WorldRevision
from world.observations import Observation

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_WORLD = WorldId("world-1")


def _observation(tick: int) -> Observation:
    return Observation(
        world_id=_WORLD,
        observer_id=EntityId(_OWNER.value),
        revision=WorldRevision(tick),
        tick=tick,
        season=Season.SPRING,
    )


def _experiment_ledger() -> ExperimentLedger:
    return ExperimentLedger(
        owner_id=_OWNER,
        max_hypotheses=4,
        max_trials_per_tick=1,
        repeat_threshold=1,
        learn_into_genealogy=False,
    )


def _season_ledger() -> ScientificModelLedger:
    ledger = empty_scientific_model_ledger(_OWNER)
    for tick, season in (
        (0, Season.SPRING),
        (1, Season.SPRING),
        (2, Season.SUMMER),
        (3, Season.SUMMER),
    ):
        ledger = derive_model_hypotheses(
            ledger,
            Observation(
                world_id=_WORLD,
                observer_id=EntityId(_OWNER.value),
                revision=WorldRevision(tick),
                tick=tick,
                season=season,
            ),
            experiment_ledger=_experiment_ledger(),
        )
    return ledger


def _prediction(
    *,
    probabilities: tuple[int, ...],
    predicted: str,
    model_id: str = "smm:a",
    variant: ModelPredictorVariant = ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
    case_id: str = "smc:case",
) -> ModelPrediction:
    return ModelPrediction(
        prediction_id=scientific_prediction_id(case_id, variant),
        model_id=model_id,
        hypothesis_id="smh:a",
        predictor_variant=variant,
        alphabet=SEASON_CLASSES,
        probabilities_milli=probabilities,
        predicted_class=predicted,
        confidence_milli=probabilities[SEASON_CLASSES.index(predicted)],
        model_revision_ref=f"{model_id}#0",
        source_revision_ref="smh:a#0",
        parameter_digest="par:1",
    )


def _case(
    predictions: tuple[ModelPrediction, ...],
    *,
    case_id: str = "smc:case",
    tick: int = 4,
    observed: str | None = None,
) -> ForecastCase:
    return ForecastCase(
        case_id=case_id,
        owner_id=_OWNER,
        target_kind=ModelTargetKind.SEASON,
        target_ref="season:spring",
        unit_token="season",
        horizon_ticks=2,
        alphabet=SEASON_CLASSES,
        conditions=(),
        predictions=predictions,
        issued_observation_tick=tick,
        issued_observation_key=f"tick:{tick}",
        committed_after_tick=tick,
        target_observation_tick=tick + 2,
        training_high_water_tick=max(0, tick - 1),
        state=(ForecastCaseState.SCORED if observed else ForecastCaseState.PENDING),
        observed=(
            ModelObservedOutcome(observed, tick + 2, f"event:{tick}")
            if observed
            else None
        ),
    )


def test_perfect_and_wrong_forecasts_have_exact_brier_numerators() -> None:
    perfect = _prediction(probabilities=(0, 1000, 0, 0), predicted="summer")
    wrong = _prediction(probabilities=(1000, 0, 0, 0), predicted="spring")
    uniform = _prediction(probabilities=(250, 250, 250, 250), predicted="spring")
    assert score_model_prediction(perfect, "summer") == 0
    assert score_model_prediction(wrong, "summer") == 2_000_000
    assert score_model_prediction(uniform, "summer") == 750_000


def test_out_of_alphabet_outcomes_are_rejected() -> None:
    prediction = _prediction(probabilities=(250, 250, 250, 250), predicted="spring")
    with pytest.raises(ValueError, match="invalid_class"):
        score_model_prediction(prediction, "monsoon")


def test_summary_reports_retained_cohort_and_calibration() -> None:
    prediction = _prediction(probabilities=(0, 1000, 0, 0), predicted="summer")
    other = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    case = _case((prediction, other), observed="summer")
    summary = summarize_model_performance(
        (case,), "smm:a", owner_id=_OWNER.value, evaluated_tick=8
    )
    assert summary is not None
    assert summary.scored_count == 1
    assert summary.hit_count == 1
    assert summary.hit_share_milli == 1000
    assert summary.mean_brier_millionths == 0
    assert summary.calibration_gap_milli == 0
    assert summary.calibration_bins == (CalibrationBin(9, 1, 1000, 1),)


def test_missing_outcomes_are_not_zero_loss_samples() -> None:
    prediction = _prediction(probabilities=(0, 1000, 0, 0), predicted="summer")
    other = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    scored = _case((prediction, other), case_id="smc:1", observed="summer")
    missing = _case((prediction, other), case_id="smc:2", tick=6)
    summary = summarize_model_performance(
        (scored, missing), "smm:a", owner_id=_OWNER.value, evaluated_tick=9
    )
    assert summary is not None
    assert summary.scored_count == 1
    assert summary.pending_count == 1
    assert summary.missing_count == 1


def test_comparison_needs_three_identical_paired_cases() -> None:
    baseline = _prediction(probabilities=(0, 1000, 0, 0), predicted="summer")
    empirical = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    cases = tuple(
        _case(
            (baseline, empirical),
            case_id=f"smc:{index}",
            tick=4 + index,
            observed="summer",
        )
        for index in range(3)
    )
    comparison = compare_model_predictions(cases, "smm:a", "smm:b")
    assert comparison.paired_count == 3
    assert comparison.status is ModelComparisonStatus.LOWER_LOSS_A
    assert comparison.mean_brier_millionths_a == 0
    assert comparison.mean_brier_millionths_b == 750_000
    assert comparison.a_minus_b_millionths == -750_000

    two = compare_model_predictions(cases[:2], "smm:a", "smm:b")
    assert two.status is ModelComparisonStatus.INSUFFICIENT_SAMPLES


def test_ties_and_rounding_follow_half_even() -> None:
    first = _prediction(probabilities=(250, 250, 250, 250), predicted="spring")
    second = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    cases = tuple(
        _case(
            (first, second),
            case_id=f"smc:tie-{index}",
            tick=4 + index,
            observed="summer",
        )
        for index in range(3)
    )
    comparison = compare_model_predictions(cases, "smm:a", "smm:b")
    assert comparison.status is ModelComparisonStatus.TIED
    assert comparison.a_minus_b_millionths == 0


def test_mixed_cohorts_are_rejected() -> None:
    first = _prediction(probabilities=(0, 1000, 0, 0), predicted="summer")
    second = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    good = _case((first, second), observed="summer")
    other = dataclasses.replace(good, target_ref="season:auction", case_id="smc:other")
    with pytest.raises(ValueError, match="mixed_cohort"):
        compare_model_predictions((good, other), "smm:a", "smm:b")
    with pytest.raises(ValueError, match="mixed_cohort"):
        summarize_model_performance(
            (good, other), "smm:a", owner_id=_OWNER.value, evaluated_tick=8
        )


def test_scoring_requires_the_exact_target_tick() -> None:
    prediction = _prediction(probabilities=(250, 250, 250, 250), predicted="spring")
    other = _prediction(
        probabilities=(250, 250, 250, 250),
        predicted="spring",
        model_id="smm:b",
        variant=ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    )
    case = _case((prediction, other))
    with pytest.raises(ValueError, match="invalid_tick"):
        score_forecast_case(case, ModelObservedOutcome("summer", 9, "event:1"))
    scored = score_forecast_case(
        case, ModelObservedOutcome("summer", case.target_observation_tick, "event:1")
    )
    assert scored.state is ForecastCaseState.SCORED
    assert scored.outcome_refs == ("event:1",)
    with pytest.raises(ValueError, match="already_terminal"):
        score_forecast_case(
            scored,
            ModelObservedOutcome("summer", case.target_observation_tick, "event:2"),
        )


def test_calibration_uses_predictive_confidence_not_source_support() -> None:
    ledger = _season_ledger()
    issued = issue_model_forecasts(ledger, _observation(4))
    case = issued.pending_cases[0]
    hypothesis = issued.hypotheses[0]
    assert hypothesis.revisions[0].support_refs == (
        *hypothesis.revisions[0].support_refs,
    )
    baseline = next(
        row
        for row in case.predictions
        if row.predictor_variant is ModelPredictorVariant.HYPOTHESIS_BASELINE_V1
    )
    assert baseline.confidence_milli == max(baseline.probabilities_milli)
    assert baseline.confidence_milli == 400


def test_accounting_recomputes_summaries_and_comparisons() -> None:
    ledger = _season_ledger()
    updated = ledger
    for tick in (4, 5, 6):
        updated = issue_model_forecasts(updated, _observation(tick))
    scored_cases = []
    for case in updated.pending_cases:
        scored_cases.append(
            score_forecast_case(
                case,
                ModelObservedOutcome(
                    "summer", case.target_observation_tick, f"event:{case.case_id}"
                ),
            )
        )
    updated = dataclasses.replace(updated, cases=tuple(scored_cases))
    accounted = recompute_model_accounting(updated, evaluated_tick=9)
    assert accounted.summaries
    assert accounted.comparisons
    assert all(row.scored_count == 3 for row in accounted.summaries)
    assert accounted.comparisons[0].paired_count == 3


def test_empirical_candidate_uses_past_resolved_cases() -> None:
    ledger = _season_ledger()
    first = issue_model_forecasts(ledger, _observation(4))
    baseline_model = next(
        row
        for row in first.models
        if row.predictor_variant is ModelPredictorVariant.HYPOTHESIS_BASELINE_V1
    )
    empirical_model = next(
        row
        for row in first.models
        if row.predictor_variant is ModelPredictorVariant.EMPIRICAL_CONTEXT_V1
    )
    case = first.pending_cases[0]
    scored = score_forecast_case(
        case,
        ModelObservedOutcome("autumn", case.target_observation_tick, "event:1"),
    )
    updated = dataclasses.replace(first, cases=(scored,), cursor=0)
    updated = dataclasses.replace(updated, last_issued_tick=4)
    second = issue_model_forecasts(updated, _observation(5))
    empirical_prediction = next(
        row
        for row in second.pending_cases[-1].predictions
        if row.model_id == empirical_model.model_id
    )
    assert baseline_model.model_id != empirical_model.model_id
    assert empirical_prediction.probabilities_milli != (250, 250, 250, 250)
    assert sum(empirical_prediction.probabilities_milli) == 1000


def test_revision_reason_set_is_closed() -> None:
    assert ModelRevisionReason.PARAMETER_UPDATED.value == "parameter_updated"
    assert {row.value for row in ModelRevisionReason} == {
        "formulated",
        "source_changed",
        "parameter_updated",
        "retired",
        "suspended",
        "resumed",
    }
