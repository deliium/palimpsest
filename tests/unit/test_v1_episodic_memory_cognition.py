"""Cognition episodic memory retrieval and deferred apply integration."""

from __future__ import annotations

import pytest

from agents.cognition.defaults import (
    DirectSelfStateProjector,
    DirectSituationModeler,
    EmptyMemoryRetriever,
    EmptyMemoryUpdateHook,
    LiteralPerceptionInterpreter,
    PassthroughGoalManager,
    PlaceholderFutureImagination,
    StableIntentionSelector,
    StableMotivationEvaluator,
    WaitFallbackPlanner,
)
from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
from agents.cognition.loop import CognitiveLoop
from agents.cognition.memory import ScopedMemoryRetriever
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
)
from agents.models import Agent, AgentId
from memory.models import (
    BeliefStore,
    ConceptMention,
    MemoryId,
    MemoryMutationBatch,
    MemoryProvenance,
    MemoryRunId,
    MemoryScope,
    MemoryScoreWeights,
    MemoryScoringPolicy,
    MemorySituationContext,
    MemorySourceKind,
    MemoryStore,
    MemoryTrace,
    MentionId,
)
from memory.service import InMemoryMemoryService
from simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeError,
    AgentRuntimeErrorCode,
)
from simulation.bootstrap import (
    AgentRegistration,
    WorldBootstrap,
    registration_translator,
)
from simulation.clock import Tick
from simulation.lifecycle import TickToken
from tests.simulation_helpers import make_location, weather_for_locations
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


def _policy() -> MemoryScoringPolicy:
    return MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0, current_context_overlap=1.0),
    )


def _body(entity_id: str = "body-1") -> AgentBody:
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
        bodies=(_body("body-1"),),
        weather=weather_for_locations(locations),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
    )


def _observation(*, tick: int = 0) -> Observation:
    body = _body()
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId("body-1"),
        revision=WorldRevision(0),
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


def _token(tick: int = 0) -> TickToken:
    return TickToken(value=f"tok-{tick}", tick=Tick(tick))


@pytest.mark.asyncio
async def test_scoped_retriever_maps_service_hits_and_pending_accesses() -> None:
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    tick = 0
    await service.apply(
        MemoryMutationBatch(
            writes=(
                MemoryTrace(
                    memory_id=MemoryId("m-1"),
                    owner_id=AgentId("agent-1"),
                    world_revision=WorldRevision(0),
                    concepts=(
                        ConceptMention(mention_id=MentionId("c-1"), concept="camp"),
                    ),
                    entities=(),
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
                ),
            )
        )
    )
    beliefs = BeliefStore(AgentId("agent-1"))
    retriever = ScopedMemoryRetriever(
        service, scoring_policy=_policy(), belief_reader=beliefs
    )
    observation = _observation(tick=tick)
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
        counts={},
        confidence=1.0,
    )
    context = await retriever.retrieve(loop_input, perception)
    assert context.memory_ids == (MemoryId("m-1"),)
    assert len(context.ranked_hits) == 1
    assert len(context.pending_accesses) == 1
    assert context.belief_ids == ()
    assert "camp" not in repr(context)


@pytest.mark.asyncio
async def test_runtime_applies_service_batch_after_successful_cognition() -> None:
    bootstrap = _bootstrap()
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
    retriever = ScopedMemoryRetriever(service, scoring_policy=_policy())

    class WriteHook:
        async def propose_updates(
            self,
            loop_input: CognitiveLoopInput,
            plan: object,
            perception: object,
            memory: object,
            intention: object,
        ) -> tuple[MemoryUpdateIntent, ...]:
            _ = plan, perception, memory, intention
            obs = loop_input.observation
            return (
                MemoryUpdateIntent(
                    owner_id=loop_input.agent_id,
                    kind=MemoryUpdateKind.WRITE_MEMORY,
                    memory=MemoryTrace(
                        memory_id=MemoryId("m-new"),
                        owner_id=loop_input.agent_id,
                        world_revision=obs.revision,
                        concepts=(
                            ConceptMention(
                                mention_id=MentionId("c-1"), concept="decision"
                            ),
                        ),
                        entities=(),
                        relations=(),
                        context=MemorySituationContext(),
                        emotional_salience=0.0,
                        confidence=1.0,
                        provenance=MemoryProvenance(
                            kind=MemorySourceKind.DIRECT_OBSERVATION,
                            source_tick=obs.tick,
                        ),
                        created_tick=obs.tick,
                        source_tick=obs.tick,
                        last_access_tick=obs.tick,
                        access_count=0,
                    ),
                ),
            )

    loop = CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=retriever,
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=PlaceholderFutureImagination(),
        motivation=StableMotivationEvaluator(),
        intention=StableIntentionSelector(),
        planner=WaitFallbackPlanner(),
        memory_updates=WriteHook(),
    )
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=Agent(agent_id=AgentId("agent-1"), name="Ada", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
        memory_service=service,
    )
    runtime.start()
    observation = _observation(tick=0)
    result = await runtime.process_observation(observation, token=_token(0))
    assert result.submission is not None
    stored = await service.get(MemoryId("m-new"))
    assert stored is not None
    assert stored.created_tick == observation.tick
    assert memories.snapshot() == ()


@pytest.mark.asyncio
async def test_failed_cognition_does_not_mutate_memory_service() -> None:
    class BoomPlanner:
        async def plan(
            self,
            loop_input: CognitiveLoopInput,
            intention: SelectedIntention,
            futures: PossibleFutures,
            memory: RetrievedMemoryContext | None = None,
            goal_board=None,
            emotional_state=None,
        ) -> ActionPlan:
            _ = loop_input, intention, futures, memory, goal_board, emotional_state
            raise RuntimeError("planner boom")

    bootstrap = _bootstrap()
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    service = InMemoryMemoryService(scope)
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
        planner=BoomPlanner(),
        memory_updates=EmptyMemoryUpdateHook(),
    )
    memories = MemoryStore(AgentId("agent-1"))
    beliefs = BeliefStore(AgentId("agent-1"))
    runtime = AgentRuntime(
        agent=Agent(agent_id=AgentId("agent-1"), name="Ada", goals=()),
        translator=registration_translator(bootstrap),
        cognitive_loop=loop,
        memory_reader=memories,
        memory_writer=memories,
        belief_reader=beliefs,
        belief_writer=beliefs,
        memory_service=service,
    )
    runtime.start()
    with pytest.raises(AgentRuntimeError) as exc:
        await runtime.process_observation(_observation(), token=_token())
    assert exc.value.code is AgentRuntimeErrorCode.COGNITION_FAILED
    assert await service.snapshot() == ()
