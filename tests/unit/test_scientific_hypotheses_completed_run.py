# mypy: ignore-errors
"""Completed-run fact mapping and no-objective-rule boundary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    HypothesisCondition,
    HypothesisConditionSlot,
    admit_hypothesis,
    apply_test_outcome,
    empty_experiment_ledger,
    formulate_hypothesis,
)
from agents.models import AgentId
from analysis.scientific_hypotheses_contract import NONE_TOKEN
from experiments.scientific_hypotheses_completed_run import (
    build_completed_run_scientific_hypotheses_analysis,
    scientific_hypothesis_facts,
)
from world.effects import ActionCause
from world.events import ExperimentResolved, OccurrenceContext, WorldEvent
from world.experimentation import (
    DiscoveryMode,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")


def _binding() -> ExperimentCognitionBinding:
    return ExperimentCognitionBinding(
        max_hypotheses=8,
        max_trials_per_tick=4,
        repeat_threshold=2,
        learn_into_genealogy=False,
        allow_provider=False,
    )


def _ledger():
    ledger = empty_experiment_ledger(OWNER, _binding())
    row = formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:run",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item-material",
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS,
        conditions=(
            HypothesisCondition(HypothesisConditionSlot.LOCATION, "loc-1"),
            HypothesisCondition(HypothesisConditionSlot.COUNTERPART, "agent-2"),
        ),
        created_tick=1,
    )
    ledger = admit_hypothesis(ledger, row)
    ledger = apply_test_outcome(
        ledger,
        "hyp:run",
        outcome_class=ExperimentOutcomeClass.SUCCESS,
        event_id="e1",
        tick=2,
        discovery_mode=DiscoveryMode.DELIBERATE,
    )
    from agents.cognition.experimentation import ExperimentTrial, record_trial

    ledger = record_trial(
        ledger,
        ExperimentTrial(
            tick=2,
            event_id="e1",
            outcome_class="success",
            discovery_mode="deliberate",
            hypothesis_id="hyp:run",
        ),
    )
    return ledger


def _event(tick: int = 2, event_id: str = "e1") -> WorldEvent:
    return WorldEvent(
        event_id=EventId(event_id),
        run_id="run-science",
        world_id=WorldId("world-science"),
        tick=tick,
        sequence=0,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(tick),
        schema_version=27,
        details=ExperimentResolved(
            operator="combine",
            operand_a_id=EntityId("item-material"),
            operand_b_id=EntityId("resource-material"),
            process_token="none",
            outcome_class="success",
            delta="none",
            discovery_mode="deliberate",
            product_id="",
        ),
        actor_id=EntityId("body-1"),
        target_id=EntityId("item-material"),
        cause=ActionCause(RequestId(f"req-{event_id}"), EntityId("body-1")),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
    )


def _runner_result(*, science: bool = True, ledgers=None):
    flags = SimpleNamespace(science=science)
    config = SimpleNamespace(
        v4_capability_flags=flags,
        bounded_experimentation=SimpleNamespace(laws=("objective-law",)),
    )
    return SimpleNamespace(
        runner_config=config,
        experiment_ledgers=tuple(ledgers or ()),
    )


def test_facts_tokenize_owner_and_counterpart() -> None:
    facts = scientific_hypothesis_facts(_runner_result(ledgers=[_ledger()]))
    assert len(facts) == 1
    fact = facts[0]
    assert fact.owner_token.startswith("owner-")
    assert "agent-1" not in fact.owner_token
    values = {pair.value_token for pair in fact.conditions}
    assert "agent-2" not in values
    assert fact.revisions
    assert fact.trials
    assert fact.trials[0].matched is True


def test_missing_science_flag_produces_no_facts() -> None:
    assert scientific_hypothesis_facts(
        _runner_result(science=False, ledgers=[_ledger()])
    ) == ()


def test_builder_requires_committed_events() -> None:
    with pytest.raises(ValueError, match="scientific_hypotheses_requires_events"):
        build_completed_run_scientific_hypotheses_analysis(
            _runner_result(ledgers=[_ledger()]),
            committed_events=(),
            run_id="run-science",
        )


def test_builder_maps_facts_without_law_access() -> None:
    analysis = build_completed_run_scientific_hypotheses_analysis(
        _runner_result(ledgers=[_ledger()]),
        committed_events=(_event(),),
        run_id="run-science",
    )
    assert analysis.hypothesis_rows
    assert analysis.objective_rows
    assert analysis.trial_rows
    dumped = str(analysis)
    assert "objective-law" not in dumped


def test_explicit_facts_override_derivation() -> None:
    analysis = build_completed_run_scientific_hypotheses_analysis(
        _runner_result(ledgers=[_ledger()]),
        committed_events=(_event(),),
        run_id="run-science",
        facts=(),
    )
    assert analysis.hypothesis_rows == ()


def test_missing_prediction_maps_to_none_token() -> None:
    ledger = empty_experiment_ledger(OWNER, _binding())
    row = formulate_hypothesis(
        owner_id=OWNER,
        hypothesis_id="hyp:none",
        operator=ExperimentOperator.COMBINE,
        operand_a_id="item-material",
        operand_b_id="resource-material",
        process_token=ExperimentProcessToken.NONE,
        predicted_outcome=None,
    )
    ledger = admit_hypothesis(ledger, row)
    facts = scientific_hypothesis_facts(_runner_result(ledgers=[ledger]))
    assert facts[0].predicted_outcome == NONE_TOKEN
