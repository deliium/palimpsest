"""Counterfactual scenarios stay distinct from memory, belief, and events."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from agents.cognition.counterfactual import (
    CounterfactualPolicy,
    CounterfactualProvenanceKind,
    consider_counterfactuals,
    counterfactual_belief_requests,
)
from agents.cognition.imagination import ImaginationEngine
from agents.cognition.memory import build_direct_observation_memory_trace
from agents.cognition.models import EmotionKind, ImaginedFuture, PossibleFutures
from agents.models import AgentId
from memory.beliefs import SemanticBelief
from memory.models import MemorySourceKind, MemoryTrace
from memory.service import InMemoryMemoryService
from tests.unit.test_counterfactual_reasoning import _decision, _input
from tests.unit.test_identity_runtime import _occurrence
from tests.unit.test_memory_dynamics_fixtures import _recall_request
from tests.unit.test_prospective_imagination import (
    _board,
    _loop_input,
    _memory,
    _self_model,
    _situation,
)
from world.events import WorldEvent
from world.identifiers import EntityId, WorldRevision
from world.observations import ObservationSourceKind, ObservedOccurrence

ROOT = Path(__file__).resolve().parents[2]


def test_scenario_is_not_a_memory_belief_future_or_event(caplog) -> None:
    from dataclasses import replace

    caplog.set_level(logging.DEBUG, logger="agents.cognition.counterfactual")
    loop_input = _input()
    decision = _decision()
    scenarios = consider_counterfactuals(
        loop_input,
        (decision,),
        policy=CounterfactualPolicy(),
    )
    scenario = scenarios[0]
    occurrence = replace(_occurrence(), kind="help", success=False)
    assert type(occurrence) is ObservedOccurrence
    trace = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-owner"),
        observation_tick=3,
        observation_revision=WorldRevision(0),
        occurrence=occurrence,
        location_id=EntityId("loc-1"),
    )
    ordinary = SemanticBelief  # type marker for the ordinary belief class
    requests = counterfactual_belief_requests(
        scenarios,
        policy=CounterfactualPolicy(),
        owner_id=AgentId("agent-owner"),
        tick=3,
    )
    assert type(scenario) is not MemoryTrace
    assert type(scenario) is not ordinary
    assert type(scenario) is not ImaginedFuture
    assert type(scenario) is not ObservedOccurrence
    assert type(scenario) is not WorldEvent
    assert type(trace) is MemoryTrace
    assert trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
    assert trace.concepts[0].concept == "help"
    assert scenario.scenario_id not in {trace.memory_id.value}
    assert not hasattr(MemorySourceKind, "IMAGINED")
    assert not any(member.name == "REGRET" for member in EmotionKind)
    assert requests[0].claim.predicate == "counterfactual_alternative"
    assert requests[0].evidence.supporting[0].memory_id.value == "memory-help"
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "direction_code=wait" in messages
    assert "affect_code=regret" in messages
    assert "provenance_code=imagined_alternative" in messages
    assert "Select counterfactual scenario ids" not in messages
    assert scenario.provenance is CounterfactualProvenanceKind.IMAGINED_ALTERNATIVE
    source = (ROOT / "src/agents/cognition/counterfactual.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "WorldEvent",
        "WorldState",
        "PhysicalRules",
        "search_base_probability",
        "time.monotonic",
        "counterfactual_alternative",
    ):
        if forbidden == "counterfactual_alternative":
            formation = (ROOT / "src/memory/belief_formation.py").read_text(
                encoding="utf-8"
            )
            service = (ROOT / "src/memory/belief_service.py").read_text(
                encoding="utf-8"
            )
            assert forbidden not in formation
            assert forbidden not in service
            continue
        assert forbidden not in source
    event = _search_event()
    with pytest.raises(TypeError, match="not a subjective input"):
        consider_counterfactuals(
            loop_input,
            (event,),
            policy=CounterfactualPolicy(),
        )
    with pytest.raises(TypeError, match="invalid_provenance"):
        type(scenario)(
            owner_id=scenario.owner_id,
            scenario_id=scenario.scenario_id,
            decision=decision,
            alternative_direction=scenario.alternative_direction,
            target_id=scenario.target_id,
            predicted_outcome=scenario.predicted_outcome,
            confidence=scenario.confidence,
            goal_ids=scenario.goal_ids,
            emotional_impact=scenario.emotional_impact,
            provenance=ObservationSourceKind.OCCURRENCE,
        )
    assert event.event_id.value != scenario.scenario_id


def _search_event() -> WorldEvent:
    from tests.unit.test_causal_world_model_experiment import _search_event as build

    return build(event_id="ev-1", success=False, sequence=1)


@pytest.mark.asyncio
async def test_recall_and_imagination_omit_the_scenario() -> None:
    from memory.models import MemoryMutationBatch, MemoryRunId, MemoryScope
    from world.observations import ObservationAudienceRole

    occurrence = _occurrence()
    built = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-owner"),
        observation_tick=3,
        observation_revision=WorldRevision(0),
        occurrence=type(occurrence)(
            provenance=occurrence.provenance,
            kind="help",
            audience_role=ObservationAudienceRole.ACTOR,
            actor_id=occurrence.actor_id,
            success=False,
        ),
        location_id=EntityId("loc-1"),
    )
    scope = MemoryScope(run_id=MemoryRunId("run-cf"), owner_id=AgentId("agent-owner"))
    service = InMemoryMemoryService(scope)
    await service.apply(MemoryMutationBatch(writes=(built,)))
    recalled = await service.recall(
        _recall_request(
            tick=10,
            reconstruction_id="recon-help",
            dynamics=None,
            tags=("help",),
        )
    )
    sources = {
        memory_id.value
        for item in recalled.reconstructions
        for memory_id in item.source_memory_ids
    }
    narrative = " ".join(item.narrative for item in recalled.reconstructions)
    scenario = consider_counterfactuals(
        _input(),
        (_decision(),),
        policy=CounterfactualPolicy(),
    )[0]
    assert built.memory_id.value in sources
    assert scenario.scenario_id not in sources
    assert scenario.scenario_id not in narrative
    futures = await ImaginationEngine().imagine(
        _loop_input(),
        _situation(),
        _self_model(),
        _memory(),
        _board(),
    )
    assert type(futures) is PossibleFutures
    assert scenario.scenario_id not in {item.future_id for item in futures.futures}
    assert all(type(item) is ImaginedFuture for item in futures.futures)
    event = _search_event()
    assert event.event_id.value != scenario.scenario_id
