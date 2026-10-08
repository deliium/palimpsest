"""Accidental discovery stays on the trial until an explicit learn step."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    ExperimentHypothesis,
    ExperimentTrial,
    admit_hypothesis,
    commit_experiment_learning,
    empty_experiment_ledger,
    experiment_hypothesis_id,
    record_trial,
    score_remembered_experiment,
)
from agents.cognition.practical_knowledge import (
    PracticalKnowledgeLedger,
    empty_practical_knowledge_ledger,
)
from agents.models import AgentId
from world.experimentation import ExperimentOperator, ExperimentProcessToken
from world.identifiers import EntityId, EventId
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_OWNER = AgentId("owner-1")


def _ledger(*, learn: bool = False, threshold: int = 2):
    return empty_experiment_ledger(
        _OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=4,
            max_trials_per_tick=2,
            repeat_threshold=threshold,
            learn_into_genealogy=learn,
            allow_provider=False,
        ),
    )


def _hypothesis(*, predicted: str | None) -> ExperimentHypothesis:
    operator = ExperimentOperator.COMBINE
    token = ExperimentProcessToken.NONE
    return ExperimentHypothesis(
        owner_id=_OWNER,
        hypothesis_id=experiment_hypothesis_id(
            _OWNER, operator, "item-a", "item-b", token
        ),
        operator=operator,
        operand_a_id="item-a",
        operand_b_id="item-b",
        process_token=token,
        predicted_outcome=predicted,
    )


def _occurrence(
    *,
    outcome: str,
    mode: str,
    event_id: str = "evt-exp-1",
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId(event_id),
        ),
        kind="experiment_resolved",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId("item-a"),
        success=None,
        public_facts={
            "kind": "experiment_resolved",
            "outcome_class": outcome,
            "delta": "none",
            "operator": "combine",
            "discovery_mode": mode,
        },
    )


def test_empty_hypothesis_keeps_engine_accidental(
    caplog: pytest.LogCaptureFixture,
) -> None:
    occurrence = _occurrence(outcome="unexpected", mode="accidental")
    with caplog.at_level(logging.INFO, logger="agents.cognition.experimentation"):
        scored = score_remembered_experiment(_ledger(), occurrence, tick=2)
    assert scored.trials[0].hypothesis_id == ""
    assert scored.trials[0].discovery_mode == "accidental"
    assert occurrence.public_facts["discovery_mode"] == "accidental"
    assert "experiment_discovery_mode discovery_mode=accidental" in caplog.text


def test_mismatched_prediction_marks_the_trial_accidental() -> None:
    ledger = admit_hypothesis(
        _ledger(), _hypothesis(predicted="success")
    )
    occurrence = _occurrence(outcome="unexpected", mode="deliberate")
    scored = score_remembered_experiment(ledger, occurrence, tick=2)
    assert scored.trials[0].discovery_mode == "accidental"
    assert scored.trials[0].hypothesis_id != ""
    assert occurrence.public_facts["discovery_mode"] == "deliberate"


def test_matching_unexpected_prediction_stays_deliberate() -> None:
    ledger = admit_hypothesis(
        _ledger(), _hypothesis(predicted="unexpected")
    )
    scored = score_remembered_experiment(
        ledger,
        _occurrence(outcome="unexpected", mode="deliberate"),
        tick=2,
    )
    assert scored.trials[0].discovery_mode == "deliberate"


def test_accidental_success_does_not_mint_until_learn() -> None:
    hypothesis = _hypothesis(predicted="success")
    ledger = admit_hypothesis(_ledger(learn=True, threshold=2), hypothesis)
    ledger = record_trial(
        ledger,
        ExperimentTrial(
            tick=1,
            event_id="evt-0",
            outcome_class="unexpected",
            discovery_mode="accidental",
            hypothesis_id=hypothesis.hypothesis_id,
        ),
    )
    knowledge = empty_practical_knowledge_ledger(_OWNER)
    _kept, updated = commit_experiment_learning(
        ledger,
        knowledge,
        genealogy_active=True,
        enabled_kinds=("crafting_process",),
        tick=3,
    )
    assert isinstance(updated, PracticalKnowledgeLedger)
    assert updated.entries == ()
