"""Communicated memory formation from observed utterances."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.communication import (
    COMMUNICATED_MEMORY_POLICY_VERSION,
    CommunicatedMemoryUpdateHook,
    CompositeMemoryUpdateHook,
    PendingEvidenceAccumulator,
    build_communicated_memory_trace,
    receiver_confidence_for_transmission,
)
from agents.cognition.defaults import EmptyMemoryUpdateHook
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
    SubjectiveSnapshot,
)
from agents.models import AgentId
from memory.models import (
    MemoryProvenance,
    MemorySourceKind,
    MemoryTrace,
)
from simulation.serialization import decode_domain, encode_domain
from world.actions import Wait
from world.communications import (
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
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


def _observation_with_comm(
    *,
    tick: int = 3,
    listener: str = "body-1",
    speaker: str = "body-2",
    communication_id: str = "comm-1",
    text: str = "water-north",
    concepts: tuple[str, ...] = ("water",),
) -> Observation:
    utterance = origin_utterance(
        text=text,
        speaker_id=EntityId(speaker),
        communication_id=communication_id,
        concepts=concepts,
        source_basis=CommunicationSourceBasis.UNREFERENCED,
        sender_confidence=0.8,
    )
    source_tick = tick - 1
    return Observation(
        observer_id=EntityId(listener),
        world_id=WorldId("world-1"),
        revision=WorldRevision(2),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=EntityId(listener),
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
        communications=(
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=source_tick,
                    source_event_id=EventId("evt-talk-1"),
                ),
                speaker_id=EntityId(speaker),
                listener_id=EntityId(listener),
                utterance=utterance,
                action_kind="tell",
            ),
        ),
    )


def _loop_pieces(
    observation: Observation,
) -> tuple[
    CognitiveLoopInput,
    InterpretedPerception,
    ActionPlan,
    SelectedIntention,
    RetrievedMemoryContext,
]:
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
        counts={"communications": 1},
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
async def test_communicated_hook_proposes_fresh_trace_with_transmission() -> None:
    observation = _observation_with_comm()
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    intents = await CommunicatedMemoryUpdateHook().propose_updates(
        loop_input, plan, perception, memory, intention
    )
    assert len(intents) == 1
    assert intents[0].kind is MemoryUpdateKind.WRITE_MEMORY
    trace = intents[0].memory
    assert type(trace) is MemoryTrace
    assert trace.owner_id == AgentId("agent-1")
    assert trace.provenance.kind is MemorySourceKind.COMMUNICATED
    assert trace.provenance.speaker_id == EntityId("body-2")
    assert trace.provenance.observed_source_id == EventId("evt-talk-1")
    assert trace.lineage.source_memory_ids == ()
    meta = trace.provenance.transmission
    assert meta is not None
    assert meta.communication_id == "comm-1"
    assert meta.action_kind == "tell"
    assert meta.hop_count == 0
    assert meta.policy_version == COMMUNICATED_MEMORY_POLICY_VERSION
    assert "water" in {item.concept for item in trace.concepts}
    assert "water-north" not in repr(trace)
    assert meta.content_fingerprint not in repr(trace)


@pytest.mark.asyncio
async def test_communicated_hook_dedupes_by_communication_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observation = _observation_with_comm()
    existing = build_communicated_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=2,
        observation_revision=WorldRevision(1),
        message=observation.communications[0],
        location_id=EntityId("loc-1"),
    )
    snap = SubjectiveSnapshot(
        owner_id=AgentId("agent-1"),
        revision=1,
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
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.communication"):
        intents = await CommunicatedMemoryUpdateHook().propose_updates(
            loop_input, plan, perception, memory, intention
        )
    assert intents == ()
    assert "water-north" not in caplog.text


@pytest.mark.asyncio
async def test_composite_runs_communicated_then_empty() -> None:
    observation = _observation_with_comm()
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    pending = PendingEvidenceAccumulator()
    hook = CompositeMemoryUpdateHook(
        (CommunicatedMemoryUpdateHook(), EmptyMemoryUpdateHook()),
        pending=pending,
    )
    intents = await hook.propose_updates(
        loop_input, plan, perception, memory, intention
    )
    assert len(intents) == 1
    assert len(pending.traces()) == 1
    assert pending.traces()[0].provenance.kind is MemorySourceKind.COMMUNICATED


@pytest.mark.asyncio
async def test_pending_evidence_drives_same_batch_revisions() -> None:
    """Communicated traces proposed first must feed SubjectiveRevisionHook."""
    from agents.cognition.defaults import SubjectiveRevisionHook

    observation = _observation_with_comm()
    loop_input, perception, plan, intention, memory = _loop_pieces(observation)
    pending = PendingEvidenceAccumulator()
    hook = CompositeMemoryUpdateHook(
        (
            CommunicatedMemoryUpdateHook(),
            SubjectiveRevisionHook(
                resolve_counterpart=lambda entity_id: (
                    AgentId("agent-2") if entity_id == EntityId("body-2") else None
                ),
                pending=pending,
            ),
        ),
        pending=pending,
    )
    intents = await hook.propose_updates(
        loop_input, plan, perception, memory, intention
    )
    assert any(item.kind is MemoryUpdateKind.WRITE_MEMORY for item in intents)
    assert len(pending.traces()) == 1


def test_receiver_confidence_attenuates_with_hops() -> None:
    assert (
        receiver_confidence_for_transmission(sender_confidence=1.0, hop_count=0) == 1.0
    )
    assert receiver_confidence_for_transmission(
        sender_confidence=1.0, hop_count=1
    ) == pytest.approx(0.9)


def test_communicated_trace_round_trips_serialization() -> None:
    observation = _observation_with_comm(concepts=("camp", "fire"))
    trace = build_communicated_memory_trace(
        owner_id=AgentId("agent-1"),
        observation_tick=observation.tick,
        observation_revision=observation.revision,
        message=observation.communications[0],
        location_id=EntityId("loc-1"),
    )
    assert decode_domain(encode_domain(trace)) == trace
    assert type(trace.provenance) is MemoryProvenance
    assert trace.provenance.transmission is not None


def test_social_message_policy_talk_fallback_without_evidence(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from agents.cognition.communication import DeterministicSocialMessagePolicy
    from world.observations import CoarseHealth, VisibleBody

    owner = AgentId("agent-1")
    observation = Observation(
        observer_id=EntityId("body-1"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(1),
        tick=2,
        self_body=ObservedSelf(
            entity_id=EntityId("body-1"),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0.0),
            thirst=Thirst(0.0),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-2"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        visibility=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(candidate_count=0),
    )
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.communication"):
        decision = DeterministicSocialMessagePolicy().select(
            owner_id=owner,
            speaker_id=EntityId("body-1"),
            observation=observation,
            memory=memory,
            preferred_recipient_id=EntityId("body-2"),
        )
    assert decision is not None
    assert decision.action_kind == "talk"
    assert decision.fallback is True
    assert decision.hop_count == 0
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "social_message_selected" in messages
    assert "hello" not in messages


def test_social_message_policy_retells_communicated_trace_with_hop() -> None:
    from agents.cognition.communication import DeterministicSocialMessagePolicy
    from world.actions import Tell
    from world.observations import CoarseHealth, VisibleBody

    owner = AgentId("agent-bob")
    observation = _observation_with_comm(
        tick=5,
        listener="body-bob",
        speaker="body-alice",
        communication_id="comm-alice-1",
        concepts=("water",),
    )
    # Retell uses snapshot memories for the speaker (Bob), not the observation inbox.
    prior = build_communicated_memory_trace(
        owner_id=owner,
        observation_tick=4,
        observation_revision=WorldRevision(1),
        message=observation.communications[0],
        location_id=EntityId("loc-1"),
    )
    speak_obs = Observation(
        observer_id=EntityId("body-bob"),
        world_id=WorldId("world-1"),
        revision=WorldRevision(2),
        tick=5,
        self_body=ObservedSelf(
            entity_id=EntityId("body-bob"),
            location_id=EntityId("loc-1"),
            health=Health(100),
            hunger=Hunger(0.0),
            thirst=Thirst(0.0),
            fatigue=Fatigue(0.0),
            temperature=TemperatureCelsius(36.5),
            inventory=(),
            life_status=LifeStatus.ALIVE,
            carry_capacity=CarryCapacity(10),
        ),
        visible_bodies=(
            VisibleBody(
                entity_id=EntityId("body-carol"),
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        visibility=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=owner,
        memory_ids=(prior.memory_id,),
        belief_ids=(),
        confidence=1.0,
        decision_metadata=DecisionMetadata(candidate_count=1),
    )
    decision = DeterministicSocialMessagePolicy().select(
        owner_id=owner,
        speaker_id=EntityId("body-bob"),
        observation=speak_obs,
        memory=memory,
        preferred_recipient_id=EntityId("body-carol"),
        snapshot_memories=(prior,),
    )
    assert decision is not None
    assert decision.action_kind == "tell"
    assert type(decision.command) is Tell
    assert decision.hop_count == 1
    assert decision.command.utterance.declared.hop_count == 1
    assert decision.command.utterance.declared.parent_communication_id is not None
    assert decision.command.utterance.declared.parent_communication_id.value == (
        "comm-alice-1"
    )
    assert decision.command.utterance.declared.source_agent_chain == (
        EntityId("body-alice"),
        EntityId("body-bob"),
    )
