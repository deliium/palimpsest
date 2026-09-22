"""Direct-observation memory formation from owner-visible Observation data."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.communication import (
    CommunicatedMemoryUpdateHook,
    CompositeMemoryUpdateHook,
    PendingEvidenceAccumulator,
)
from agents.cognition.defaults import SubjectiveRevisionHook
from agents.cognition.memory import (
    DIRECT_OBSERVATION_MEMORY_POLICY_VERSION,
    DirectObservationMemoryUpdateHook,
    build_direct_observation_memory_trace,
)
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateKind,
    RetrievedMemoryContext,
    SelectedIntention,
)
from agents.models import AgentId
from memory.models import MemorySourceKind
from world.actions import Wait
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedOccurrence,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _observation_with_occurrence(
    *,
    tick: int = 4,
    observer: str = "body-1",
    kind: str = "move",
    event_id: str = "evt-occ-1",
) -> Observation:
    return Observation(
        observer_id=EntityId(observer),
        world_id=WorldId("world-1"),
        revision=WorldRevision(3),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId(observer),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0.1),
            thirst=Thirst(0.2),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        occurrences=(
            ObservedOccurrence(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.OCCURRENCE,
                    source_tick=tick - 1,
                    source_event_id=EventId(event_id),
                ),
                kind=kind,
                audience_role=ObservationAudienceRole.WITNESS,
                actor_id=EntityId("body-2"),
                other_entity_id=EntityId("body-3"),
                success=True,
            ),
        ),
    )


def _loop_pieces(observation: Observation):
    loop_input = CognitiveLoopInput(
        agent_id=AgentId("agent-1"),
        observation=observation,
        internal_state=InternalAgentState(owner_id=AgentId("agent-1")),
    )
    perception = InterpretedPerception(
        owner_id=AgentId("agent-1"),
        observer_id=observation.observer_id,
        tick=observation.tick,
        revision=observation.revision,
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(),
        counts={"occurrences": len(observation.occurrences)},
        confidence=1.0,
    )
    plan = ActionPlan(
        owner_id=AgentId("agent-1"),
        command=Wait(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(),
    )
    intention = SelectedIntention(
        owner_id=AgentId("agent-1"),
        intention=IntentionCode.WAIT,
        source_motive=None,
        confidence=1.0,
        decision_metadata=DecisionMetadata(),
    )
    memory = RetrievedMemoryContext(
        owner_id=AgentId("agent-1"),
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(),
    )
    return loop_input, perception, plan, intention, memory


@pytest.mark.asyncio
async def test_direct_hook_proposes_occurrence_trace() -> None:
    observation = _observation_with_occurrence()
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    intents = await DirectObservationMemoryUpdateHook().propose_updates(
        loop_input, plan, perception, memory, intention
    )
    assert len(intents) == 1
    assert intents[0].kind is MemoryUpdateKind.WRITE_MEMORY
    trace = intents[0].memory
    assert trace is not None
    assert trace.owner_id == AgentId("agent-1")
    assert trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
    assert trace.provenance.observed_source_id == EventId("evt-occ-1")
    assert trace.provenance.speaker_id is None
    assert "move" in {item.concept for item in trace.concepts}
    assert DIRECT_OBSERVATION_MEMORY_POLICY_VERSION


@pytest.mark.asyncio
async def test_direct_hook_dedupes_by_event_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observation = _observation_with_occurrence()
    existing = build_direct_observation_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=3,
        observation_revision=WorldRevision(2),
        occurrence=observation.occurrences[0],
        location_id=EntityId("loc-1"),
    )
    from agents.cognition.models import SubjectiveSnapshot

    snap = SubjectiveSnapshot(
        owner_id=AgentId("agent-1"),
        revision=0,
        memories=(existing,),
        legacy_beliefs=(),
        semantic_beliefs=(),
    )
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    loop_input = CognitiveLoopInput(
        agent_id=AgentId("agent-1"),
        observation=observation,
        internal_state=InternalAgentState(owner_id=AgentId("agent-1")),
        snapshot=snap,
    )
    caplog.set_level(logging.DEBUG, logger="agents.cognition.memory")
    intents = await DirectObservationMemoryUpdateHook().propose_updates(
        loop_input, plan, perception, memory, intention
    )
    assert intents == ()
    assert "direct_observation_memory_deduped" in {
        record.getMessage() for record in caplog.records
    }
    joined = " ".join(str(record.__dict__) for record in caplog.records)
    assert "evt-occ-1" in joined
    assert "Camp" not in joined


@pytest.mark.asyncio
async def test_pending_accumulator_feeds_subjective_revision() -> None:
    observation = _observation_with_occurrence()
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    pending = PendingEvidenceAccumulator()
    hook = CompositeMemoryUpdateHook(
        (
            DirectObservationMemoryUpdateHook(),
            CommunicatedMemoryUpdateHook(),
            SubjectiveRevisionHook(
                resolve_counterpart=lambda entity_id: (
                    AgentId("agent-2")
                    if entity_id == EntityId("body-2")
                    else (
                        AgentId("agent-3")
                        if entity_id == EntityId("body-3")
                        else None
                    )
                ),
                pending=pending,
            ),
        ),
        pending=pending,
    )
    intents = await hook.propose_updates(
        loop_input, plan, perception, memory, intention
    )
    write_kinds = [item.kind for item in intents]
    assert MemoryUpdateKind.WRITE_MEMORY in write_kinds
    # Same-tick pending traces should be visible to the revision hook.
    assert len(pending.traces()) >= 1
    assert all(
        trace.provenance.kind is MemorySourceKind.DIRECT_OBSERVATION
        for trace in pending.traces()
    )
