# mypy: ignore-errors

"""Adversarial chronology: no outcome before commitment, no retroactive edits."""

from __future__ import annotations

import dataclasses

import pytest

from agents.cognition.scientific_model_lifecycle import (
    advance_scientific_models,
)
from agents.cognition.scientific_model_observation import (
    resolve_due_model_cases,
)
from agents.cognition.scientific_models import (
    ForecastCaseState,
    ModelExecutionComparability,
    ModelObservedOutcome,
    ModelTargetKind,
    empty_scientific_model_ledger,
    scientific_model_content_count,
)
from tests.unit.test_scientific_models_lifecycle import (
    _bind,
    _experiment_ledger,
    _observation,
    _occurrence,
    _production_case,
    _season_ledger,
)
from world.environment import Season

pytestmark = pytest.mark.unit


def _season_case():
    ledger = _season_ledger()
    pending = [
        row for row in ledger.pending_cases if row.target_kind is ModelTargetKind.SEASON
    ]
    return ledger, max(pending, key=lambda row: row.target_observation_tick)


def test_three_boundary_order_is_exact() -> None:
    ledger, case = _season_case()
    assert case.issued_observation_tick == case.committed_after_tick
    assert case.target_observation_tick == case.issued_observation_tick + 2
    at_one = resolve_due_model_cases(
        ledger, _observation(case.issued_observation_tick + 1, season=Season.SUMMER)
    )
    still = next(row for row in at_one.cases if row.case_id == case.case_id)
    assert still.state is ForecastCaseState.PENDING
    at_two = resolve_due_model_cases(
        ledger, _observation(case.target_observation_tick, season=Season.SUMMER)
    )
    scored = next(row for row in at_two.cases if row.case_id == case.case_id)
    assert scored.state is ForecastCaseState.SCORED
    assert scored.observed is not None
    assert scored.observed.observed_tick == case.target_observation_tick


def test_outcome_at_or_before_commitment_is_rejected() -> None:
    _, case = _season_case()
    for tick in (case.committed_after_tick, case.issued_observation_tick):
        with pytest.raises(ValueError, match="invalid_tick"):
            dataclasses.replace(
                case,
                state=ForecastCaseState.SCORED,
                observed=ModelObservedOutcome("summer", tick, "event:early"),
                settlement_reason="observed",
            )


def test_scored_case_is_not_rewritten_by_a_later_observation() -> None:
    ledger, case = _season_case()
    scored = resolve_due_model_cases(
        ledger, _observation(case.target_observation_tick, season=Season.SUMMER)
    )
    frozen = next(row for row in scored.cases if row.case_id == case.case_id)
    again = resolve_due_model_cases(
        scored,
        _observation(case.target_observation_tick + 5, season=Season.WINTER),
    )
    same = next(row for row in again.cases if row.case_id == case.case_id)
    assert same.state is ForecastCaseState.SCORED
    assert same.observed == frozen.observed
    assert same.predictions == frozen.predictions


def test_duplicate_settlement_is_idempotent() -> None:
    ledger, case = _season_case()
    first = resolve_due_model_cases(
        ledger, _observation(case.target_observation_tick, season=Season.SUMMER)
    )
    second = resolve_due_model_cases(
        first, _observation(case.target_observation_tick, season=Season.SUMMER)
    )
    assert second == first
    assert scientific_model_content_count(second) == scientific_model_content_count(
        first
    )


def test_source_revision_after_issuance_cannot_rewrite_the_case() -> None:
    ledger, case = _season_case()
    hypothesis = next(
        row
        for row in ledger.hypotheses
        if row.hypothesis_id
        in {prediction.hypothesis_id for prediction in case.predictions}
    )
    changed = dataclasses.replace(
        hypothesis,
        revisions=(
            *hypothesis.revisions,
            dataclasses.replace(
                hypothesis.current_revision,
                revision_index=len(hypothesis.revisions),
                predicted_class="winter",
            ),
        ),
    )
    updated = dataclasses.replace(
        ledger,
        hypotheses=tuple(
            changed if row.hypothesis_id == changed.hypothesis_id else row
            for row in ledger.hypotheses
        ),
    )
    same = next(row for row in updated.cases if row.case_id == case.case_id)
    assert same.predictions == case.predictions
    assert same.source_claim == case.source_claim


def test_late_old_and_foreign_occurrences_never_become_outcomes() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    old = _occurrence(tick=case.issued_observation_tick, event_id="evt-old")
    foreign = _occurrence(
        tick=case.issued_observation_tick + 1,
        actor=__import__("world.identifiers", fromlist=["EntityId"]).EntityId("other"),
        event_id="evt-foreign",
    )
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(old, foreign),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_ATTEMPTED
    assert updated.observed is None


def test_operator_only_occurrence_does_not_invent_details() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(ledger, case.case_id)
    occurrence = _occurrence(
        tick=case.issued_observation_tick + 1,
        facts={"outcome_class": "success"},
    )
    # Remove the exposed operator; the binding claim still governs comparability.
    facts = dict(occurrence.public_facts)
    facts.pop("operator", None)
    stripped = dataclasses.replace(occurrence, public_facts=facts)
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(stripped,),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.SCORED
    assert updated.observed is not None
    assert updated.observed.observed_class == "success"


def test_changed_conditions_bind_but_do_not_score() -> None:
    ledger, _ = _production_case()
    case = next(
        row
        for row in ledger.pending_cases
        if row.target_kind is ModelTargetKind.PRODUCTION_OUTCOME
    )
    bound = _bind(
        ledger,
        case.case_id,
        comparability=ModelExecutionComparability.CHANGED_CONDITIONS,
    )
    occurrence = _occurrence(tick=case.issued_observation_tick + 1)
    resolved = resolve_due_model_cases(
        bound,
        _observation(
            case.target_observation_tick,
            include_self=True,
            occurrences=(occurrence,),
        ),
    )
    updated = next(row for row in resolved.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.NOT_COMPARABLE


def test_issuance_update_never_targets_its_own_evidence_tick() -> None:
    ledger = advance_scientific_models(
        empty_scientific_model_ledger(_season_ledger().owner_id),
        _observation(0, season=Season.SPRING),
        experiment_ledger=_experiment_ledger(),
    )
    for case in ledger.pending_cases:
        assert case.target_observation_tick > case.training_high_water_tick
        assert case.committed_after_tick == case.issued_observation_tick


def test_pending_recovery_before_acknowledgment_preserves_the_frozen_case() -> None:
    from simulation.runner_serialization import (
        decode_finalization_command,
        encode_finalization_command,
    )
    from tests.unit.test_scientific_models_checkpoint import _command

    command = _command()
    restored = decode_finalization_command(encode_finalization_command(command))
    ledger = restored.scientific_model_ledger
    assert ledger is not None
    pending = [
        row for row in ledger.pending_cases if row.target_kind is ModelTargetKind.SEASON
    ]
    case = max(pending, key=lambda row: row.target_observation_tick)
    again = decode_finalization_command(encode_finalization_command(restored))
    assert again.scientific_model_ledger.cases == ledger.cases
    settled = resolve_due_model_cases(
        ledger,
        _observation(case.target_observation_tick, season=Season.SUMMER),
    )
    updated = next(row for row in settled.cases if row.case_id == case.case_id)
    assert updated.state is ForecastCaseState.SCORED
    assert updated.predictions == case.predictions
