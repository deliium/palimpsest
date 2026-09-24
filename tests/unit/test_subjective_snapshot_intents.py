"""Frozen subjective snapshot and deferred revision-intent coverage."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.defaults import (
    DirectSelfStateProjector,
    DirectSituationModeler,
    EmptyMemoryRetriever,
    LiteralPerceptionInterpreter,
    PassthroughGoalManager,
    PlaceholderFutureImagination,
    StableIntentionSelector,
    StableMotivationEvaluator,
    SubjectiveRevisionHook,
    WaitFallbackPlanner,
)
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateKind,
    MotivationCode,
    SelectedIntention,
    SituationClaimCode,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.models import Agent, AgentId
from memory.belief_formation import BeliefFormationPolicy
from memory.beliefs import (
    BeliefActivationState,
    BeliefConfidenceState,
    BeliefPolicyRef,
    BeliefRevisionId,
    BeliefValueKind,
    ClaimSubject,
    ClaimSubjectKind,
    ClaimValue,
    SemanticBelief,
    SemanticBeliefStore,
    SemanticClaim,
)
from memory.models import (
    BeliefId,
    BeliefStore,
    ConceptMention,
    EntityMention,
    MemoryId,
    MemoryProvenance,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
)
from simulation.agent_runtime import AgentRuntime
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from tests.simulation_helpers import make_location, weather_for_locations
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _body(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _bootstrap() -> WorldBootstrap:
    locations = (make_location("loc-1", name="Camp"),)
    return WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=(_body("body-1"), _body("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )


def _observation(*, tick: int = 0) -> Observation:
    body = _body("body-1")
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(tick),
        tick=tick,
        self_body=ObservedSelf(
            entity_id=body.entity_id,
            location_id=body.location_id,
            health=body.health,
            hunger=body.hunger,
            thirst=body.thirst,
            fatigue=body.fatigue,
            temperature=body.temperature,
            inventory=body.inventory,
            life_status=body.life_status,
            carry_capacity=body.carry_capacity,
        ),
    )


def _token(tick: int) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


def _trace(*, memory_id: str, tick: int, concept: str = "food") -> MemoryTrace:
    return MemoryTrace(
        memory_id=MemoryId(memory_id),
        owner_id=AgentId("agent-1"),
        world_revision=WorldRevision(tick),
        concepts=(ConceptMention(mention_id=MentionId("c-1"), concept=concept),),
        entities=(
            EntityMention(
                mention_id=MentionId("e-1"),
                label="other",
                entity_id=EntityId("body-2"),
            ),
        ),
        relations=(),
        context=MemorySituationContext(location_id=EntityId("loc-1")),
        emotional_salience=0.2,
        confidence=1.0,
        provenance=MemoryProvenance(
            kind=MemorySourceKind.DIRECT_OBSERVATION,
            source_tick=tick,
        ),
        created_tick=tick,
        source_tick=tick,
        last_access_tick=tick,
        access_count=0,
    )


def _semantic_belief() -> SemanticBelief:
    owner = AgentId("agent-1")
    return SemanticBelief(
        belief_id=BeliefId("b-food"),
        owner_id=owner,
        claim=SemanticClaim(
            subject=ClaimSubject(kind=ClaimSubjectKind.AGENT, agent_id=owner),
            predicate="experienced_concept",
            value=ClaimValue(kind=BeliefValueKind.TEXT, text_value="food"),
        ),
        confidence=BeliefConfidenceState(
            confidence=0.8,
            support_mass=0.8,
            contradiction_mass=0.0,
        ),
        activation_state=BeliefActivationState.ACTIVE,
        current_revision_id=BeliefRevisionId("rev-b-food"),
        revision_ordinal=0,
        created_tick=0,
        updated_tick=0,
        policy=BeliefPolicyRef(policy_id="semantic-v1", version="1"),
        evidence_support_count=2,
        evidence_contradiction_count=0,
    )


def test_subjective_snapshot_carries_semantic_content() -> None:
    owner = AgentId("agent-1")
    belief = _semantic_belief()
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=3,
        memories=(_trace(memory_id="m-1", tick=1),),
        legacy_beliefs=(),
        semantic_beliefs=(belief,),
        relationships=(),
    )
    assert snapshot.revision == 3
    assert len(snapshot.semantic_beliefs) == 1
    assert "food" not in repr(snapshot)


@pytest.mark.asyncio
async def test_self_state_uses_snapshot_semantic_beliefs() -> None:
    owner = AgentId("agent-1")
    belief = _semantic_belief()
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=1,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(belief,),
        relationships=(),
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(tick=1),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )
    memory = await EmptyMemoryRetriever().retrieve(
        loop_input,
        InterpretedPerception(
            owner_id=owner,
            observer_id=EntityId("body-1"),
            tick=1,
            revision=WorldRevision(1),
            life_status=LifeStatus.ALIVE,
            location_id=EntityId("loc-1"),
            claim_codes=(),
            counts={},
            confidence=1.0,
        ),
    )
    assert memory.semantic_beliefs == (belief,)
    model = await DirectSelfStateProjector().project(
        loop_input,
        SituationModel(
            owner_id=owner,
            tick=1,
            claim_codes=(SituationClaimCode.LOCAL_SCENE,),
            confidence=1.0,
        ),
        memory,
    )
    assert len(model.beliefs) == 1
    assert "food" not in repr(model)


@pytest.mark.asyncio
async def test_subjective_revision_hook_proposes_deferred_intents() -> None:
    owner = AgentId("agent-1")
    tick = 2
    snapshot = SubjectiveSnapshot(
        owner_id=owner,
        revision=0,
        memories=(_trace(memory_id="m-1", tick=tick),),
        legacy_beliefs=(),
        semantic_beliefs=(),
        relationships=(),
    )
    loop_input = CognitiveLoopInput(
        agent_id=owner,
        observation=_observation(tick=tick),
        internal_state=InternalAgentState(owner_id=owner),
        snapshot=snapshot,
    )
    perception = InterpretedPerception(
        owner_id=owner,
        observer_id=EntityId("body-1"),
        tick=tick,
        revision=WorldRevision(tick),
        life_status=LifeStatus.ALIVE,
        location_id=EntityId("loc-1"),
        claim_codes=(),
        counts={},
        confidence=1.0,
    )
    memory = await EmptyMemoryRetriever().retrieve(loop_input, perception)
    hook = SubjectiveRevisionHook(
        belief_policy=BeliefFormationPolicy(
            policy_id="test",
            version="1",
            min_independent_observations=1,
        ),
        resolve_counterpart=lambda entity_id: (
            AgentId("agent-2") if entity_id == EntityId("body-2") else None
        ),
    )
    intents = await hook.propose_updates(
        loop_input,
        ActionPlan(owner_id=owner, command=Wait(), confidence=1.0),
        perception,
        memory,
        SelectedIntention(
            owner_id=owner,
            intention=IntentionCode.WAIT,
            source_motive=MotivationCode.WAIT,
            confidence=1.0,
        ),
    )
    kinds = {intent.kind for intent in intents}
    assert MemoryUpdateKind.REVISE_SEMANTIC_BELIEF in kinds
    assert MemoryUpdateKind.REVISE_RELATIONSHIP in kinds
    for intent in intents:
        assert "food" not in repr(intent)


@pytest.mark.asyncio
async def test_runtime_defers_revise_intents_without_mutation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bootstrap = _bootstrap()
    memories = MemoryStore(AgentId("agent-1"))
    memories.write(_trace(memory_id="m-1", tick=0))
    beliefs = BeliefStore(AgentId("agent-1"))
    semantic = SemanticBeliefStore(AgentId("agent-1"))

    loop = CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=EmptyMemoryRetriever(),
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=PlaceholderFutureImagination(),
        motivation=StableMotivationEvaluator(),
        intention=StableIntentionSelector(),
        planner=WaitFallbackPlanner(),
        memory_updates=SubjectiveRevisionHook(
            belief_policy=BeliefFormationPolicy(
                policy_id="test",
                version="1",
                min_independent_observations=1,
            ),
            resolve_counterpart=lambda entity_id: (
                AgentId("agent-2") if entity_id == EntityId("body-2") else None
            ),
        ),
    )
    runtime = AgentRuntime(
        agent=Agent(agent_id=AgentId("agent-1"), name="Ada", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
        semantic_belief_reader=semantic,
    )
    runtime.start()
    caplog.set_level(logging.DEBUG, logger="simulation.agent_runtime")
    result = await runtime.process_observation(_observation(tick=0), token=_token(0))
    assert result.submission is not None
    assert semantic.snapshot() == ()
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "runtime_snapshot_frozen" in messages
    assert "runtime_deferred_subjective_intents" in messages
    assert "food" not in messages
