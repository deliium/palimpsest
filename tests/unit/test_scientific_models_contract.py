"""Scientific-model contracts: identities, caps, probabilities and retention."""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition.scientific_models import (
    MAX_PENDING_CASES,
    MAX_TERMINAL_CASES,
    SEASON_CLASSES,
    CalibrationBin,
    DerivationSample,
    ForecastCase,
    ForecastCaseState,
    ModelComparison,
    ModelComparisonStatus,
    ModelCondition,
    ModelCoverageNotice,
    ModelHypothesis,
    ModelHypothesisRevision,
    ModelLifecycle,
    ModelObservedOutcome,
    ModelPerformanceSummary,
    ModelPrediction,
    ModelPredictorVariant,
    ModelRevision,
    ModelRevisionReason,
    ModelSourceKind,
    ModelTargetKind,
    PredictiveModel,
    ScientificModelLedger,
    ScientificModelPolicy,
    bump_notice,
    empty_scientific_model_ledger,
    prune_terminal_cases,
    scientific_case_id,
    scientific_hypothesis_id,
    scientific_model_id,
    scientific_prediction_id,
    target_alphabet,
)
from world.identifiers import AgentId, EntityId, require_exact_nonneg_int

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")
_RESOURCE = EntityId("res-1")


def _condition() -> tuple[ModelCondition, ...]:
    return (ModelCondition("season", "spring"),)


def _hypothesis(
    owner_id: AgentId = _OWNER,
    *,
    target_kind: ModelTargetKind = ModelTargetKind.SEASON,
    target_ref: str = "season-forecast",
    unit_token: str = "season",
    horizon_ticks: int = 2,
) -> ModelHypothesis:
    hypothesis_id = scientific_hypothesis_id(
        owner_id,
        target_kind,
        target_ref,
        unit_token,
        horizon_ticks,
        ModelSourceKind.OBSERVED_REGULARITY,
    )
    return ModelHypothesis(
        owner_id=owner_id,
        hypothesis_id=hypothesis_id,
        target_kind=target_kind,
        target_ref=target_ref,
        unit_token=unit_token,
        horizon_ticks=horizon_ticks,
        source_kind=ModelSourceKind.OBSERVED_REGULARITY,
        source_refs=("observation:1",),
        revisions=(
            ModelHypothesisRevision(
                revision_index=0,
                tick=1,
                reason=ModelRevisionReason.FORMULATED,
                conditions=_condition(),
                predicted_class="summer",
                source_revision_ref="sample:1",
            ),
        ),
        created_tick=1,
        sequence=0,
    )


def _model(
    hypothesis: ModelHypothesis,
    variant: ModelPredictorVariant,
    *,
    owner_id: AgentId | None = None,
) -> PredictiveModel:
    owner = hypothesis.owner_id if owner_id is None else owner_id
    model_id = scientific_model_id(
        owner,
        hypothesis.hypothesis_id,
        variant,
        hypothesis.target_ref,
        hypothesis.unit_token,
        hypothesis.horizon_ticks,
    )
    return PredictiveModel(
        owner_id=owner,
        model_id=model_id,
        hypothesis_id=hypothesis.hypothesis_id,
        target_kind=hypothesis.target_kind,
        target_ref=hypothesis.target_ref,
        unit_token=hypothesis.unit_token,
        horizon_ticks=hypothesis.horizon_ticks,
        predictor_variant=variant,
        source_revision_ref=hypothesis.revision_ref,
        parameter_digest="params:1",
        lifecycle=ModelLifecycle.ACTIVE,
        revisions=(
            ModelRevision(
                revision_index=0,
                tick=1,
                reason=ModelRevisionReason.FORMULATED,
                source_revision_ref=hypothesis.revision_ref,
                parameter_digest="params:1",
                conditions=_condition(),
                predicted_class="summer",
            ),
        ),
        created_tick=1,
    )


def _prediction(
    model: PredictiveModel,
    *,
    probabilities: tuple[int, ...] = (700, 100, 100, 100),
    alphabet: tuple[str, ...] = SEASON_CLASSES,
    predicted_class: str = "spring",
) -> ModelPrediction:
    return ModelPrediction(
        prediction_id=scientific_prediction_id(model.model_id, model.predictor_variant),
        model_id=model.model_id,
        hypothesis_id=model.hypothesis_id,
        predictor_variant=model.predictor_variant,
        alphabet=alphabet,
        probabilities_milli=probabilities,
        predicted_class=predicted_class,
        confidence_milli=probabilities[alphabet.index(predicted_class)],
        model_revision_ref=f"{model.model_id}#0",
        source_revision_ref=model.source_revision_ref,
        parameter_digest=model.parameter_digest,
    )


def _case(
    hypothesis: ModelHypothesis,
    models: tuple[PredictiveModel, PredictiveModel],
    *,
    case_id: str = "smc:case-1",
    issued_tick: int = 4,
    state: ForecastCaseState = ForecastCaseState.PENDING,
    observed: ModelObservedOutcome | None = None,
) -> ForecastCase:
    predictions = (
        _prediction(models[0]),
        _prediction(
            models[1],
            probabilities=(250, 250, 250, 250),
            predicted_class="spring",
        ),
    )
    return ForecastCase(
        case_id=case_id,
        owner_id=hypothesis.owner_id,
        target_kind=hypothesis.target_kind,
        target_ref=hypothesis.target_ref,
        unit_token=hypothesis.unit_token,
        horizon_ticks=hypothesis.horizon_ticks,
        alphabet=SEASON_CLASSES,
        conditions=_condition(),
        predictions=predictions,
        issued_observation_tick=issued_tick,
        issued_observation_key=f"observation:{issued_tick}",
        committed_after_tick=issued_tick,
        target_observation_tick=issued_tick + 2,
        training_high_water_tick=max(0, issued_tick - 1),
        state=state,
        observed=observed,
    )


def test_empty_ledger_has_locked_policy() -> None:
    ledger = empty_scientific_model_ledger(_OWNER)
    assert ledger.owner_id == _OWNER
    assert ledger.policy_version == "scientific-models.v1"
    assert ledger.hypotheses == ()
    assert ledger.pending_cases == ()
    assert ScientificModelPolicy().max_pending_cases == MAX_PENDING_CASES


def test_policy_caps_cannot_be_widened() -> None:
    with pytest.raises(ValueError, match="max_pending_cases"):
        ScientificModelPolicy(max_pending_cases=MAX_PENDING_CASES + 1)
    with pytest.raises(ValueError, match="policy_version"):
        ScientificModelPolicy(policy_version="scientific-models.v2")


def test_identities_are_deterministic_and_owner_scoped() -> None:
    first = scientific_hypothesis_id(
        _OWNER,
        ModelTargetKind.SEASON,
        "season-forecast",
        "season",
        2,
        ModelSourceKind.OBSERVED_REGULARITY,
    )
    second = scientific_hypothesis_id(
        _OWNER,
        ModelTargetKind.SEASON,
        "season-forecast",
        "season",
        2,
        ModelSourceKind.OBSERVED_REGULARITY,
    )
    foreign = scientific_hypothesis_id(
        _OTHER,
        ModelTargetKind.SEASON,
        "season-forecast",
        "season",
        2,
        ModelSourceKind.OBSERVED_REGULARITY,
    )
    assert first == second
    assert first.startswith("smh:")
    assert first != foreign
    assert scientific_case_id(_OWNER, "observation:4") == scientific_case_id(
        _OWNER, "observation:4"
    )


def test_identities_reject_boolean_horizon() -> None:
    with pytest.raises(ValueError, match="horizon_ticks"):
        scientific_hypothesis_id(
            _OWNER,
            ModelTargetKind.SEASON,
            "season-forecast",
            "season",
            True,
            ModelSourceKind.OBSERVED_REGULARITY,
        )


def test_hypothesis_revisions_must_be_contiguous() -> None:
    hypothesis = _hypothesis()
    with pytest.raises(ValueError, match="invalid_index_sequence"):
        dataclasses.replace(
            hypothesis,
            revisions=(
                ModelHypothesisRevision(
                    revision_index=1,
                    tick=2,
                    reason=ModelRevisionReason.SOURCE_CHANGED,
                    predicted_class="autumn",
                    source_revision_ref="sample:2",
                ),
            ),
        )


def test_hypothesis_rejects_unknown_predicted_class_and_reason() -> None:
    hypothesis = _hypothesis()
    revision = hypothesis.current_revision
    with pytest.raises(ValueError, match="invalid_type"):
        dataclasses.replace(
            revision,
            reason="formulated",  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="invalid_class"):
        dataclasses.replace(
            hypothesis, target_kind=ModelTargetKind.RESOURCE_REGENERATION
        )


def test_disease_cannot_be_modelled_or_forecast() -> None:
    with pytest.raises(ValueError, match="disease_unavailable"):
        _hypothesis(
            target_kind=ModelTargetKind.DISEASE_RISK,
            target_ref="disease-risk",
            unit_token="risk",
        )
    assert target_alphabet(ModelTargetKind.DISEASE_RISK) == ()


def test_model_rejects_bad_conditions_and_bins() -> None:
    hypothesis = _hypothesis()
    model = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    with pytest.raises(ValueError, match="invalid_slot"):
        ModelCondition("humidity", "wet")
    with pytest.raises(ValueError, match="duplicate_slot"):
        dataclasses.replace(
            model.current_revision,
            conditions=(
                ModelCondition("season", "spring"),
                ModelCondition("season", "summer"),
            ),
        )


def test_prediction_probabilities_must_sum_and_match_argmax() -> None:
    hypothesis = _hypothesis()
    model = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    with pytest.raises(ValueError, match="invalid_sum"):
        _prediction(model, probabilities=(700, 100, 100, 99))
    with pytest.raises(ValueError, match="not_argmax"):
        _prediction(model, probabilities=(100, 700, 100, 100))
    with pytest.raises(ValueError, match="invalid_type"):
        _prediction(model, probabilities=(700, 100, 100, True))


def test_case_requires_two_distinct_candidates() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    case = _case(hypothesis, (baseline, empirical))
    assert len(case.predictions) == 2
    with pytest.raises(ValueError, match="invalid_count"):
        dataclasses.replace(case, predictions=(case.predictions[0],))
    with pytest.raises(ValueError, match="duplicate_variant"):
        dataclasses.replace(
            case, predictions=(case.predictions[0], case.predictions[0])
        )


def test_case_target_is_a_future_observation_boundary() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    case = _case(hypothesis, (baseline, empirical))
    with pytest.raises(ValueError, match="invalid_horizon"):
        dataclasses.replace(case, target_observation_tick=case.issued_observation_tick)
    with pytest.raises(ValueError, match="trained_on_target"):
        dataclasses.replace(
            case, training_high_water_tick=case.issued_observation_tick + 1
        )
    with pytest.raises(ValueError, match="pending_with_outcome"):
        dataclasses.replace(
            case,
            observed=ModelObservedOutcome(
                "summer", case.target_observation_tick, "event:1"
            ),
        )


def test_scored_case_requires_outcome_on_target_tick() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    case = _case(hypothesis, (baseline, empirical))
    scored = _case(
        hypothesis,
        (baseline, empirical),
        state=ForecastCaseState.SCORED,
        observed=ModelObservedOutcome(
            "summer", case.target_observation_tick, "event:1"
        ),
    )
    assert scored.observed is not None
    with pytest.raises(ValueError, match="scored_without_outcome"):
        _case(
            hypothesis,
            (baseline, empirical),
            state=ForecastCaseState.SCORED,
        )
    with pytest.raises(ValueError, match="invalid_tick"):
        _case(
            hypothesis,
            (baseline, empirical),
            state=ForecastCaseState.SCORED,
            observed=ModelObservedOutcome("summer", 99, "event:1"),
        )


def test_ledger_rejects_foreign_owner_and_unknown_models() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    case = _case(hypothesis, (baseline, empirical))
    with pytest.raises(ValueError, match="owner_mismatch"):
        ScientificModelLedger(
            owner_id=_OWNER,
            hypotheses=(hypothesis,),
            models=(baseline, empirical),
            cases=(dataclasses.replace(case, owner_id=_OTHER),),
        )
    with pytest.raises(ValueError, match="unknown_model"):
        ScientificModelLedger(owner_id=_OWNER, hypotheses=(hypothesis,), cases=(case,))
    with pytest.raises(ValueError, match="owner_mismatch"):
        ScientificModelLedger(owner_id=_OWNER, hypotheses=(_hypothesis(_OTHER),))


def test_ledger_rejects_duplicate_identities() -> None:
    hypothesis = _hypothesis()
    with pytest.raises(ValueError, match="duplicate_id"):
        ScientificModelLedger(
            owner_id=_OWNER,
            hypotheses=(hypothesis, hypothesis),
        )
    notice = ModelCoverageNotice("retention_cap", ModelTargetKind.SEASON, 1, 1, 1)
    with pytest.raises(ValueError, match="duplicate_key"):
        ScientificModelLedger(owner_id=_OWNER, notices=(notice, notice))


def test_nested_values_are_frozen() -> None:
    hypothesis = _hypothesis()
    with pytest.raises(dataclasses.FrozenInstanceError):
        hypothesis.revisions[0].tick = 5  # type: ignore[misc]
    with pytest.raises(AttributeError):
        hypothesis.target_ref = "x"  # type: ignore[misc]


def test_pending_and_terminal_caps_are_enforced() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    pending = tuple(
        _case(hypothesis, (baseline, empirical), case_id=f"smc:p{index}")
        for index in range(MAX_PENDING_CASES + 1)
    )
    with pytest.raises(ValueError, match="pending_cap_exceeded"):
        ScientificModelLedger(
            owner_id=_OWNER,
            hypotheses=(hypothesis,),
            models=(baseline, empirical),
            cases=pending,
        )
    terminal = tuple(
        _case(
            hypothesis,
            (baseline, empirical),
            case_id=f"smc:t{index}",
            state=ForecastCaseState.NOT_ATTEMPTED,
        )
        for index in range(MAX_TERMINAL_CASES + 1)
    )
    with pytest.raises(ValueError, match="terminal_cap_exceeded"):
        ScientificModelLedger(
            owner_id=_OWNER,
            hypotheses=(hypothesis,),
            models=(baseline, empirical),
            cases=terminal,
        )


def test_pruning_keeps_pending_and_pinned_cases() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    terminal = tuple(
        _case(
            hypothesis,
            (baseline, empirical),
            case_id=f"smc:t{index}",
            issued_tick=index,
            state=ForecastCaseState.NOT_ATTEMPTED,
        )
        for index in range(5)
    )
    pending = _case(
        hypothesis, (baseline, empirical), case_id="smc:pending", issued_tick=9
    )
    kept, evicted, floor = prune_terminal_cases(
        (*terminal, pending),
        pinned_case_ids=frozenset({"smc:t0"}),
        max_terminal=3,
    )
    kept_ids = {row.case_id for row in kept}
    assert evicted == 2
    assert "smc:t0" in kept_ids
    assert "smc:pending" in kept_ids
    assert floor == 0
    with pytest.raises(ValueError, match="retention_cap"):
        prune_terminal_cases(
            terminal,
            pinned_case_ids=frozenset({"smc:t0", "smc:t1", "smc:t2", "smc:t3"}),
            max_terminal=2,
        )


def test_pruning_never_drops_pending_only_state() -> None:
    hypothesis = _hypothesis()
    baseline = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    empirical = _model(hypothesis, ModelPredictorVariant.EMPIRICAL_CONTEXT_V1)
    pending = _case(hypothesis, (baseline, empirical), case_id="smc:pending")
    kept, evicted, _ = prune_terminal_cases((pending,), max_terminal=0)
    assert kept == (pending,)
    assert evicted == 0


def test_coverage_notices_aggregate_instead_of_appending() -> None:
    notices = bump_notice(
        (),
        reason_code="source_missing",
        target_kind=ModelTargetKind.SEASON,
        tick=4,
    )
    notices = bump_notice(
        notices,
        reason_code="source_missing",
        target_kind=ModelTargetKind.SEASON,
        tick=9,
    )
    assert len(notices) == 1
    assert notices[0].count == 2
    assert (notices[0].first_tick, notices[0].last_tick) == (4, 9)
    with pytest.raises(ValueError, match="unknown_reason"):
        bump_notice(
            (),
            reason_code="made_up",
            target_kind=ModelTargetKind.SEASON,
            tick=1,
        )


def test_summary_and_comparison_reject_empty_evidence() -> None:
    with pytest.raises(ValueError, match="empty_cohort"):
        _summary(scored_count=0)
    with pytest.raises(ValueError, match="same_model"):
        _comparison(model_b="smm:a")
    with pytest.raises(ValueError, match="insufficient_samples"):
        _comparison(paired_count=2, status=ModelComparisonStatus.LOWER_LOSS_A)


def _summary(*, scored_count: int = 3) -> ModelPerformanceSummary:
    return ModelPerformanceSummary(
        summary_id="sms:1",
        owner_id=_OWNER,
        model_id="smm:a",
        target_kind=ModelTargetKind.SEASON,
        target_ref="season-forecast",
        unit_token="season",
        horizon_ticks=2,
        context_digest="context:1",
        alphabet=SEASON_CLASSES,
        scored_count=scored_count,
        hit_count=1,
        hit_share_milli=333,
        brier_numerator_sum=100,
        mean_brier_millionths=33,
        calibration_bins=(CalibrationBin(5, 3, 2100, 1),),
    )


def _comparison(
    *,
    model_b: str = "smm:b",
    paired_count: int = 3,
    status: ModelComparisonStatus = ModelComparisonStatus.TIED,
) -> ModelComparison:
    return ModelComparison(
        comparison_id="smcomp:1",
        owner_id=_OWNER,
        target_kind=ModelTargetKind.SEASON,
        target_ref="season-forecast",
        unit_token="season",
        horizon_ticks=2,
        context_digest="context:1",
        model_a_id="smm:a",
        model_b_id=model_b,
        paired_count=paired_count,
        excluded_count=1,
        mean_brier_millionths_a=10,
        mean_brier_millionths_b=10,
        a_minus_b_millionths=0,
        status=status,
    )


def test_derivation_sample_requires_an_observed_value() -> None:
    with pytest.raises(ValueError, match="missing_value"):
        DerivationSample(
            sample_id="smd:1",
            target_kind=ModelTargetKind.RESOURCE_REGENERATION,
            target_ref=str(_RESOURCE),
            unit_token="grain",
            observed_tick=2,
            observation_key="observation:2",
            location_ref="loc-1",
        )
    sample = DerivationSample(
        sample_id="smd:2",
        target_kind=ModelTargetKind.RESOURCE_REGENERATION,
        target_ref=str(_RESOURCE),
        unit_token="grain",
        observed_tick=2,
        observation_key="observation:2",
        location_ref="loc-1",
        quantity_milli=1500,
    )
    assert sample.quantity_milli == 1500


def test_target_alphabets_are_locked() -> None:
    assert target_alphabet(ModelTargetKind.SEASON) == SEASON_CLASSES
    assert target_alphabet(ModelTargetKind.RESOURCE_REGENERATION) == (
        "decrease",
        "unchanged",
        "increase",
    )
    assert len(target_alphabet(ModelTargetKind.PRODUCTION_OUTCOME)) == 5
    assert target_alphabet(ModelTargetKind.DISEASE_RISK) == ()
    with pytest.raises(ValueError, match="invalid_type"):
        target_alphabet("season")  # type: ignore[arg-type]


def test_counters_must_be_exact_nonnegative_integers() -> None:
    with pytest.raises(ValueError):
        require_exact_nonneg_int("cursor", True)
    with pytest.raises(ValueError, match="cursor"):
        ScientificModelLedger(owner_id=_OWNER, cursor=-1)


@settings(max_examples=40, deadline=None)
@given(
    weights=st.lists(st.integers(min_value=0, max_value=1000), min_size=4, max_size=4)
)
def test_any_nonnegative_distribution_is_accepted(weights: list[int]) -> None:
    total = sum(weights)
    if total == 0:
        return
    scaled = [value * 1000 // total for value in weights]
    scaled[0] += 1000 - sum(scaled)
    hypothesis = _hypothesis()
    model = _model(hypothesis, ModelPredictorVariant.HYPOTHESIS_BASELINE_V1)
    best = max(range(len(scaled)), key=lambda index: (scaled[index], -index))
    prediction = _prediction(
        model,
        probabilities=tuple(scaled),
        predicted_class=SEASON_CLASSES[best],
    )
    assert sum(prediction.probabilities_milli) == 1000
    assert prediction.brier_numerator >= 0
