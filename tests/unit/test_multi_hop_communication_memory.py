"""Deterministic Alice -> Bob -> Carol multi-hop communication scenario."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.communication import (
    DeterministicSocialMessagePolicy,
    build_communicated_memory_trace,
    project_trust_inputs,
)
from agents.cognition.models import DecisionMetadata, RetrievedMemoryContext
from agents.models import AgentId
from analysis.social_transmission import build_social_transmission_report
from memory.belief_formation import (
    DEFAULT_BELIEF_FORMATION_POLICY,
    evaluate_communicated_testimony,
)
from memory.beliefs import CommunicatedEvidenceDecision
from world.actions import Tell
from world.communications import origin_utterance, retell_utterance
from world.effects import ActionCause
from world.events import (
    OccurrenceContext,
    Told,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import (
    CoarseHealth,
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedSelf,
    VisibleBody,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _self(body: str) -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId(body),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def test_alice_bob_carol_transmission_chain(caplog: pytest.LogCaptureFixture) -> None:
    alice = EntityId("body-alice")
    bob = EntityId("body-bob")
    carol = EntityId("body-carol")
    origin = origin_utterance(
        text="spring-north",
        speaker_id=alice,
        communication_id="comm-alice-1",
        concepts=("spring",),
        sender_confidence=0.9,
    )
    # Alice tells Bob (world-verified delivery).
    alice_to_bob = make_physical_replayable_event(
        event_id=EventId("evt-a2b"),
        run_id="run-mh",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-a2b"), alice),
        resulting_revision=WorldRevision(1),
        details=Told(bob, origin),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(bob,),
            affected_entity_ids=(alice, bob),
        ),
    )
    bob_obs = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=1,
            source_event_id=EventId("evt-a2b"),
        ),
        speaker_id=alice,
        listener_id=bob,
        utterance=origin,
        action_kind="tell",
    )
    bob_trace = build_communicated_memory_trace(
        owner_id=AgentId("agent-bob"),
        observation_tick=2,
        observation_revision=WorldRevision(1),
        message=bob_obs,
        location_id=EntityId("loc-1"),
    )
    assert bob_trace.provenance.transmission is not None
    assert bob_trace.provenance.transmission.hop_count == 0
    assert bob_trace.owner_id == AgentId("agent-bob")

    # Bob retells to Carol from owned communicated trace (hop append).
    policy = DeterministicSocialMessagePolicy()
    speak_obs = Observation(
        observer_id=bob,
        world_id=WorldId("world-1"),
        revision=WorldRevision(2),
        tick=3,
        self_body=_self("body-bob"),
        visible_bodies=(
            VisibleBody(
                entity_id=carol,
                life_status=LifeStatus.ALIVE,
                coarse_health=CoarseHealth.STABLE,
            ),
        ),
        visibility=1.0,
    )
    decision = policy.select(
        owner_id=AgentId("agent-bob"),
        speaker_id=bob,
        observation=speak_obs,
        memory=RetrievedMemoryContext(
            owner_id=AgentId("agent-bob"),
            memory_ids=(bob_trace.memory_id,),
            belief_ids=(),
            confidence=1.0,
            decision_metadata=DecisionMetadata(candidate_count=1),
        ),
        preferred_recipient_id=carol,
        snapshot_memories=(bob_trace,),
    )
    assert decision is not None
    assert type(decision.command) is Tell
    assert decision.hop_count == 1
    assert decision.command.utterance.declared.parent_communication_id is not None
    assert decision.command.utterance.declared.source_agent_chain == (alice, bob)

    retell = decision.command.utterance
    bob_to_carol = make_physical_replayable_event(
        event_id=EventId("evt-b2c"),
        run_id="run-mh",
        world_id=WorldId("world-1"),
        tick=3,
        sequence=0,
        cause=ActionCause(RequestId("req-b2c"), bob),
        resulting_revision=WorldRevision(3),
        details=Told(carol, retell),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            private_recipient_ids=(carol,),
            affected_entity_ids=(bob, carol),
        ),
    )
    carol_obs = ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=3,
            source_event_id=EventId("evt-b2c"),
        ),
        speaker_id=bob,
        listener_id=carol,
        utterance=retell,
        action_kind="tell",
    )
    carol_trace = build_communicated_memory_trace(
        owner_id=AgentId("agent-carol"),
        observation_tick=4,
        observation_revision=WorldRevision(3),
        message=carol_obs,
        location_id=EntityId("loc-1"),
    )
    assert carol_trace.provenance.transmission is not None
    assert carol_trace.provenance.transmission.hop_count == 1
    # Owner isolation: distinct memory identities, no shared lineage.
    assert carol_trace.memory_id != bob_trace.memory_id
    assert carol_trace.lineage.source_memory_ids == ()

    # Trust-weighted belief handling for Carol (high trust -> accept).
    trust, trust_conf = 0.8, 0.7
    factors = evaluate_communicated_testimony(
        sender_confidence=carol_trace.provenance.transmission.sender_confidence,
        receiver_confidence=carol_trace.provenance.transmission.receiver_confidence,
        trust=trust,
        trust_confidence=trust_conf,
        hop_count=carol_trace.provenance.transmission.hop_count,
        context_relevance=0.6,
        base_contribution=0.35,
        policy=DEFAULT_BELIEF_FORMATION_POLICY,
    )
    assert factors.decision is CommunicatedEvidenceDecision.ACCEPT

    # Low trust defers/contradicts without dropping the memory trace.
    low = evaluate_communicated_testimony(
        sender_confidence=0.9,
        receiver_confidence=0.8,
        trust=0.1,
        trust_confidence=0.7,
        hop_count=1,
        context_relevance=0.6,
        base_contribution=0.35,
        policy=DEFAULT_BELIEF_FORMATION_POLICY,
    )
    assert low.decision is CommunicatedEvidenceDecision.CONTRADICT
    assert carol_trace.provenance.kind.value == "communicated"

    report = build_social_transmission_report(
        experiment_id="exp-mh",
        run_id="run-mh",
        events=(alice_to_bob, bob_to_carol),
        traces=(bob_trace, carol_trace),
        transmission_root_id="comm-alice-1",
    )
    assert report.max_hop_count == 1
    assert report.unique_agent_count >= 3
    assert report.event_count == 2

    with caplog.at_level(logging.DEBUG):
        _ = project_trust_inputs(None)
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "spring-north" not in messages
    assert "spring" not in messages
    # Retell helper remains available for scripted distortion scenarios.
    distorted = retell_utterance(
        prior=retell,
        speaker_id=carol,
        communication_id="comm-c2d",
        text="spring-maybe",
        concepts=("spring",),
    )
    assert distorted.declared.hop_count == 2
