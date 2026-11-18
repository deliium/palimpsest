"""Frozen prior forecasts and deterministic predictive distributions."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.experimentation import ExperimentLedger
from agents.cognition.scientific_model_derivation import (
    derive_model_hypotheses,
)
from agents.cognition.scientific_model_prediction import (
    baseline_distribution,
    empirical_distribution,
    issue_model_forecasts,
    largest_remainder,
)
from agents.cognition.scientific_models import (
    MAX_PENDING_CASES,
    SEASON_CLASSES,
    ForecastCaseState,
    ModelCondition,
    ModelHypothesis,
    ModelHypothesisRevision,
    ModelPrediction,
    ModelPredictorVariant,
    ModelRevisionReason,
    ModelSourceKind,
    ModelTargetKind,
    ScientificModelLedger,
    empty_scientific_model_ledger,
    scientific_hypothesis_id,
)
from world.environment import Season
from world.identifiers import AgentId, EntityId, WorldId, WorldRevision
from world.observations import Observation

pytestmark = pytest.mark.unit

_OWNER = AgentId("agent-1")
_OTHER = AgentId("agent-2")
_WORLD = WorldId("world-1")


def _experiment_ledger() -> ExperimentLedger:
    return ExperimentLedger(
        owner_id=_OWNER,
        max_hypotheses=4,
        max_trials_per_tick=1,
        repeat_threshold=1,
        learn_into_genealogy=False,
    )


def _observation(
    tick: int, *, season: Season | None = Season.SPRING, owner_id: AgentId = _OWNER
) -> Observation:
    return Observation(
        world_id=_WORLD,
        observer_id=EntityId(owner_id.value),
        revision=WorldRevision(tick),
        tick=tick,
        season=season,
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
            _observation(tick, season=season),
            experiment_ledger=_experiment_ledger(),
        )
    return ledger


def _two_hypotheses() -> ScientificModelLedger:
    ledger = empty_scientific_model_ledger(_OWNER)
    rows = []
    for index, predicted in enumerate(("summer", "autumn")):
        target_ref = f"season:variant-{index}"
        rows.append(
            ModelHypothesis(
                owner_id=_OWNER,
                hypothesis_id=scientific_hypothesis_id(
                    _OWNER,
                    ModelTargetKind.SEASON,
                    target_ref,
                    "season",
                    2,
                    ModelSourceKind.OBSERVED_REGULARITY,
                ),
                target_kind=ModelTargetKind.SEASON,
                target_ref=target_ref,
                unit_token="season",
                horizon_ticks=2,
                source_kind=ModelSourceKind.OBSERVED_REGULARITY,
                revisions=(
                    ModelHypothesisRevision(
                        revision_index=0,
                        tick=0,
                        reason=ModelRevisionReason.FORMULATED,
                        conditions=(_spring(),),
                        predicted_class=predicted,
                        source_revision_ref="sample:0",
                    ),
                ),
                created_tick=0,
            )
        )
    return dataclasses.replace(ledger, hypotheses=tuple(rows))


def _spring() -> ModelCondition:
    return ModelCondition("season", "spring")


def test_largest_remainder_allocates_exactly_one_thousand() -> None:
    assert largest_remainder((2, 1, 1, 1)) == (400, 200, 200, 200)
    assert largest_remainder((1, 1, 1, 1)) == (250, 250, 250, 250)
    assert largest_remainder((1, 1, 1)) == (334, 333, 333)
    assert sum(largest_remainder((5, 3, 2))) == 1000
    assert largest_remainder((0, 0)) == (500, 500)


def test_baseline_weights_the_claim_twice() -> None:
    probabilities = baseline_distribution(SEASON_CLASSES, "summer")
    assert probabilities == (200, 400, 200, 200)
    with pytest.raises(ValueError, match="invalid_class"):
        baseline_distribution(SEASON_CLASSES, "monsoon")


def test_empirical_distribution_is_laplace_smoothed() -> None:
    assert empirical_distribution(SEASON_CLASSES, (0, 0, 0, 0)) == (
        250,
        250,
        250,
        250,
    )
    assert empirical_distribution(SEASON_CLASSES, (3, 0, 1, 0)) == (
        500,
        125,
        250,
        125,
    )
    with pytest.raises(ValueError, match="invalid_alphabet"):
        empirical_distribution(SEASON_CLASSES, (1, 2))


def test_issued_case_freezes_both_candidates_before_the_target() -> None:
    ledger = _season_ledger()
    issued = issue_model_forecasts(ledger, _observation(4))
    cases = issued.pending_cases
    assert len(cases) == 1
    case = cases[0]
    assert case.issued_observation_tick == 4
    assert case.committed_after_tick == 4
    assert case.target_observation_tick == 6
    assert case.training_high_water_tick == 3
    assert {row.predictor_variant for row in case.predictions} == {
        ModelPredictorVariant.HYPOTHESIS_BASELINE_V1,
        ModelPredictorVariant.EMPIRICAL_CONTEXT_V1,
    }
    assert len(issued.models) == 2


def test_source_confidence_never_changes_probabilities() -> None:
    ledger = _season_ledger()
    hypothesis = ledger.hypotheses[0]
    low = hypothesis.revisions[0]
    high = dataclasses.replace(
        hypothesis,
        revisions=(dataclasses.replace(low, support_refs=("a", "b", "c")),),
    )
    first = issue_model_forecasts(
        dataclasses.replace(ledger, hypotheses=(hypothesis,)), _observation(4)
    )
    second = issue_model_forecasts(
        dataclasses.replace(ledger, hypotheses=(high,)), _observation(4)
    )
    assert first.cases[0].predictions == second.cases[0].predictions


def test_predictions_are_identical_for_the_same_state() -> None:
    ledger = _season_ledger()
    first = issue_model_forecasts(ledger, _observation(4))
    second = issue_model_forecasts(ledger, _observation(4))
    assert first == second


def test_a_second_issuance_on_the_same_tick_is_suppressed() -> None:
    ledger = _season_ledger()
    first = issue_model_forecasts(ledger, _observation(4))
    second = issue_model_forecasts(first, _observation(4))
    assert second == first
    assert first.cursor == 0


def test_an_existing_case_is_never_rewritten_by_a_new_revision() -> None:
    ledger = _season_ledger()
    first = issue_model_forecasts(ledger, _observation(4))
    frozen = first.pending_cases[0]
    hypothesis = first.hypotheses[0]
    changed = dataclasses.replace(
        hypothesis,
        revisions=(
            *hypothesis.revisions,
            dataclasses.replace(
                hypothesis.current_revision,
                revision_index=len(hypothesis.revisions),
                reason=ModelRevisionReason.PARAMETER_UPDATED,
                predicted_class="winter",
            ),
        ),
    )
    updated = dataclasses.replace(first, hypotheses=(changed,))
    again = issue_model_forecasts(updated, _observation(4))
    assert again.pending_cases == (frozen,)


def test_round_robin_selection_is_deterministic() -> None:
    ledger = _two_hypotheses()
    first = issue_model_forecasts(ledger, _observation(4))
    second = issue_model_forecasts(first, _observation(5))
    selected = {
        first.pending_cases[0].target_ref,
        second.pending_cases[-1].target_ref,
    }
    assert selected == {"season:variant-0", "season:variant-1"}
    assert second.cursor == 0


def test_conditions_that_do_not_hold_suppress_issuance() -> None:
    ledger = _two_hypotheses()
    issued = issue_model_forecasts(ledger, _observation(4, season=Season.WINTER))
    assert issued.pending_cases == ()
    assert issued.last_issued_tick == 4


def test_pending_cap_refuses_new_cases_without_dropping_old_ones() -> None:
    ledger = _season_ledger()
    issued = issue_model_forecasts(ledger, _observation(4))
    case = issued.pending_cases[0]
    filled = dataclasses.replace(
        issued,
        cases=tuple(
            dataclasses.replace(case, case_id=f"smc:fill-{index}")
            for index in range(MAX_PENDING_CASES)
        ),
    )
    blocked = issue_model_forecasts(
        dataclasses.replace(filled, last_issued_tick=3, issued_observation_keys=()),
        _observation(5),
    )
    assert len(blocked.pending_cases) == MAX_PENDING_CASES
    assert any(row.reason_code == "pending_cap" for row in blocked.notices)


def test_forecast_rejects_invalid_ledger_types() -> None:
    with pytest.raises(ValueError, match="invalid_type"):
        issue_model_forecasts(object(), _observation(4))  # type: ignore[arg-type]


def test_terminal_case_state_is_untouched_by_issuance() -> None:
    ledger = _season_ledger()
    issued = issue_model_forecasts(ledger, _observation(4))
    case = issued.pending_cases[0]
    assert case.state is ForecastCaseState.PENDING
    terminal = dataclasses.replace(case, state=ForecastCaseState.NOT_ATTEMPTED)
    updated = dataclasses.replace(issued, cases=(terminal,))
    assert issue_model_forecasts(updated, _observation(5)).terminal_cases[0].state is (
        ForecastCaseState.NOT_ATTEMPTED
    )


def test_predictions_use_the_locked_alphabet() -> None:
    ledger = _season_ledger()
    issued = issue_model_forecasts(ledger, _observation(4))
    prediction: ModelPrediction = issued.pending_cases[0].predictions[0]
    assert prediction.alphabet == SEASON_CLASSES
    assert sum(prediction.probabilities_milli) == 1000
    assert prediction.confidence_milli == max(prediction.probabilities_milli)
