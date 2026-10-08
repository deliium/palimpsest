"""Remember an experiment outcome without minting knowledge."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.experimentation import (
    ExperimentCognitionBinding,
    compile_experiment_command,
    empty_experiment_ledger,
    score_remembered_experiment,
)
from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.practical_knowledge import empty_practical_knowledge_ledger
from agents.models import AgentId
from memory.beliefs import SemanticBeliefStore
from world.identifiers import EntityId, EventId, WorldRevision
from world.observations import (
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
)

_OWNER = AgentId("owner-1")


class _Seen:
    def __init__(self, entity_id: str) -> None:
        self.entity_id = type("Id", (), {"value": entity_id})()


class _Observation:
    def __init__(self, *ids: str, tick: int = 3) -> None:
        self.tick = tick
        self.items = tuple(_Seen(item) for item in ids)
        self.resources = ()
        self.structures = ()
        self.artifacts = ()


def _ledger():
    return empty_experiment_ledger(
        _OWNER,
        ExperimentCognitionBinding(
            max_hypotheses=4,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
    )


def _occurrence(
    *,
    outcome: str,
    event_id: str = "evt-exp-1",
    operand: str = "item-a",
) -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=2,
            source_event_id=EventId(event_id),
        ),
        kind="experiment_resolved",
        audience_role=ObservationAudienceRole.ACTOR,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId(operand),
        success=outcome in {"success", "partial_success"},
        public_facts={
            "kind": "experiment_resolved",
            "outcome_class": outcome,
            "delta": "none",
            "operator": "combine",
            "discovery_mode": "deliberate",
        },
    )


def test_success_scores_support_and_does_not_mint_knowledge(
    caplog: pytest.LogCaptureFixture,
) -> None:
    knowledge = empty_practical_knowledge_ledger(_OWNER)
    beliefs = SemanticBeliefStore(_OWNER)
    compiled = compile_experiment_command(
        _OWNER, _ledger(), _Observation("item-b", "item-a")
    )
    assert compiled.command is not None
    with caplog.at_level(logging.DEBUG):
        trace = build_direct_observation_memory_trace(
            owner_id=_OWNER,
            observation_tick=3,
            observation_revision=WorldRevision(1),
            occurrence=_occurrence(outcome="success"),
            location_id=EntityId("loc-1"),
        )
        scored = score_remembered_experiment(
            compiled.ledger, _occurrence(outcome="success"), tick=3
        )
    assert "outcome_class:success" in trace.context.tags
    assert "discovery_mode:deliberate" in trace.context.tags
    assert trace.provenance.observed_source_id == EventId("evt-exp-1")
    assert scored.hypotheses[0].support == 1
    assert scored.hypotheses[0].counter == 0
    assert knowledge.entries == ()
    assert beliefs.snapshot() == ()
    assert "experiment_remembered" in caplog.text
    assert "experiment_hypothesis_scored" in caplog.text


def test_mismatch_increments_counter() -> None:
    compiled = compile_experiment_command(
        _OWNER, _ledger(), _Observation("item-b", "item-a")
    )
    scored = score_remembered_experiment(
        compiled.ledger, _occurrence(outcome="failure"), tick=3
    )
    assert scored.hypotheses[0].support == 0
    assert scored.hypotheses[0].counter == 1


def test_same_hypothesis_can_repeat_on_a_later_tick() -> None:
    compiled = compile_experiment_command(
        _OWNER, _ledger(), _Observation("item-b", "item-a", tick=3)
    )
    assert compiled.command is not None
    scored = score_remembered_experiment(
        compiled.ledger, _occurrence(outcome="success"), tick=3
    )
    blocked = compile_experiment_command(
        _OWNER, scored, _Observation("item-b", "item-a", tick=3)
    )
    assert blocked.reason == "experiment_trial_cap"
    repeated = compile_experiment_command(
        _OWNER, scored, _Observation("item-b", "item-a", tick=4)
    )
    assert repeated.command is not None
    assert repeated.command.hypothesis_id == compiled.command.hypothesis_id
