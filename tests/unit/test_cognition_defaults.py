"""Deterministic placeholder cognition defaults and fake harness tests."""

from __future__ import annotations

from agents.cognition.emotion import PassthroughEmotionalStateAppraiser

import pytest

from agents.cognition.defaults import (
    PassthroughGoalManager,
    DirectSelfStateProjector,
    DirectSituationModeler,
    EmptyMemoryRetriever,
    EmptyMemoryUpdateHook,
    LiteralPerceptionInterpreter,
    PlaceholderFutureImagination,
    StableIntentionSelector,
    StableMotivationEvaluator,
    WaitFallbackPlanner,
    default_cognitive_loop,
)
from agents.cognition.loop import CognitiveLoop, CognitiveLoopError
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    ComponentKind,
    ComponentStatus,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    SituationClaimCode,
    SituationModel,
)
from agents.models import AgentId
from tests.fakes.cognition import (
    FakeCognitionFailureCode,
    FakeCognitionHarnessError,
    FakeMemoryUpdateHook,
    FakePerceptionInterpreter,
    FakePlanner,
    ScriptedStageFailure,
    ScriptedStageSuccess,
    invocation_context,
)
from tests.typecheck.cognitive_loop import (
    ScriptedFutureImagination,
    ScriptedIntentionSelector,
    ScriptedMemoryRetriever,
    ScriptedMotivationEvaluator,
    ScriptedSelfStateProjector,
    ScriptedSituationModeler,
)
from world.actions import Wait, require_agent_command
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation, ObservedSelf
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _alive_self() -> ObservedSelf:
    return ObservedSelf(
        entity_id=EntityId("body-1"),
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


def _loop_input() -> CognitiveLoopInput:
    agent = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_alive_self(),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )


@pytest.mark.asyncio
async def test_defaults_are_deterministic_and_owner_scoped() -> None:
    loop = default_cognitive_loop()
    first = await loop.run(_loop_input(), invocation_id="inv-a")
    second = await loop.run(_loop_input(), invocation_id="inv-b")
    assert type(first.command) is Wait
    assert type(second.command) is Wait
    assert require_agent_command(first.command) is first.command
    assert [r.component_kind for r in first.boundary_records] == [
        r.component_kind for r in second.boundary_records
    ]
    assert first.final_confidence == second.final_confidence
    assert first.agent_id == AgentId("agent-1")
    perception = first.boundary_records[0].output_artifact
    assert type(perception) is InterpretedPerception
    assert perception.owner_id == AgentId("agent-1")
    assert PerceptionClaimCode.SELF_ALIVE in perception.claim_codes
    futures = first.boundary_records[5].output_artifact
    from agents.cognition.models import GoalBoard, PossibleFutures

    assert type(first.boundary_records[4].output_artifact) is GoalBoard
    assert type(futures) is PossibleFutures
    assert len(futures.futures) >= 1


@pytest.mark.asyncio
async def test_default_loop_critical_thirst_drinks_when_water_visible() -> None:
    from world.actions import Drink
    from world.observations import ObservedResource
    from world.values import ResourceKind

    agent = AgentId("agent-1")
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=ObservedSelf(
                entity_id=EntityId("body-1"),
                location_id=EntityId("loc-1"),
                health=Health(100),
                hunger=Hunger(0),
                thirst=Thirst(90),
                fatigue=Fatigue(0),
                temperature=TemperatureCelsius(36.5),
                inventory=(),
                life_status=LifeStatus.ALIVE,
                carry_capacity=CarryCapacity(10),
            ),
            resources=(
                ObservedResource(
                    entity_id=EntityId("water-1"),
                    name="spring",
                    kind=ResourceKind.WATER,
                    quantity=4.0,
                    unit="L",
                ),
            ),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )
    result = await default_cognitive_loop().run(loop_input, invocation_id="inv-drink")
    assert type(result.command) is Drink
    assert result.command.source_id == EntityId("water-1")


@pytest.mark.asyncio
async def test_defaults_replaceable_planner() -> None:
    class AlwaysWait(WaitFallbackPlanner):
        async def plan(self, loop_input, intention, futures, memory=None, goal_board=None):  # type: ignore[no-untyped-def]
            plan = await super().plan(loop_input, intention, futures)
            assert type(plan.command) is Wait
            return plan

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
        planner=AlwaysWait(),
        memory_updates=EmptyMemoryUpdateHook(),
    )
    result = await loop.run(_loop_input(), invocation_id="inv-replace")
    assert type(result.command) is Wait


@pytest.mark.asyncio
async def test_motivation_and_intention_tie_break_stable() -> None:
    selector = StableIntentionSelector()
    loop_input = _loop_input()
    tied = MotivationEvaluation(
        owner_id=loop_input.agent_id,
        scores=(
            MotivationScore(motive=MotivationCode.EXPLORE, score=0.8),
            MotivationScore(motive=MotivationCode.SOCIALIZE, score=0.8),
            MotivationScore(motive=MotivationCode.WAIT, score=0.8),
        ),
        confidence=0.8,
    )
    first = await selector.select(loop_input, tied)
    second = await selector.select(loop_input, tied)
    assert first.intention is second.intention
    assert first.intention is IntentionCode.COMMUNICATE
    assert first.decision_metadata.tie_break_applied is True
    assert first.source_motive is MotivationCode.SOCIALIZE


@pytest.mark.asyncio
async def test_fake_scripts_and_metadata_only_history() -> None:
    perception = InterpretedPerception(
        owner_id=AgentId("agent-1"),
        observer_id=EntityId("body-1"),
        tick=0,
        revision=WorldRevision(0),
        life_status=LifeStatus.ALIVE,
        location_id=None,
        claim_codes=(PerceptionClaimCode.SELF_PRESENT,),
        counts={},
        confidence=1.0,
    )
    fake = FakePerceptionInterpreter(
        {
            "inv-1": [ScriptedStageSuccess(ordinal=0, output=perception)],
            "inv-2": [ScriptedStageSuccess(ordinal=0, output=perception)],
        }
    )
    with invocation_context("inv-1"):
        out = await fake.interpret(_loop_input())
    assert out is not perception
    assert out.owner_id == perception.owner_id
    assert len(fake.calls) == 1
    assert fake.calls[0].component_kind is ComponentKind.PERCEPTION
    assert fake.calls[0].status is ComponentStatus.COMPLETED
    assert "Observation(" not in repr(fake.calls[0])
    assert "SELF_PRESENT" not in repr(fake.calls[0])

    with invocation_context("inv-missing"):
        with pytest.raises(FakeCognitionHarnessError) as exc_info:
            await fake.interpret(_loop_input())
    assert exc_info.value.code is FakeCognitionFailureCode.UNEXPECTED_KEY


@pytest.mark.asyncio
async def test_fake_planner_in_loop_and_exhausted_script() -> None:
    plan = ActionPlan(owner_id=AgentId("agent-1"), command=Wait(), confidence=1.0)
    planner = FakePlanner({"inv-plan": [ScriptedStageSuccess(ordinal=8, output=plan)]})
    updates = FakeMemoryUpdateHook(
        {"inv-plan": [ScriptedStageSuccess(ordinal=9, output=())]}
    )
    loop = CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=ScriptedMemoryRetriever(),
        situation=ScriptedSituationModeler(),
        self_state=ScriptedSelfStateProjector(),
        goal_manager=PassthroughGoalManager(),
        emotional_state=PassthroughEmotionalStateAppraiser(),
        futures=ScriptedFutureImagination(),
        motivation=ScriptedMotivationEvaluator(),
        intention=ScriptedIntentionSelector(),
        planner=planner,
        memory_updates=updates,
    )
    with invocation_context("inv-plan"):
        result = await loop.run(_loop_input(), invocation_id="inv-plan")
    assert type(result.command) is Wait
    assert planner.calls[0].ordinal == 8
    assert "Wait(" not in repr(planner.calls[0])

    with invocation_context("inv-plan"):
        with pytest.raises(CognitiveLoopError):
            await loop.run(_loop_input(), invocation_id="inv-plan")


@pytest.mark.asyncio
async def test_fake_scripted_failure_code_is_safe() -> None:
    fake = FakePerceptionInterpreter(
        {
            "inv-fail": [
                ScriptedStageFailure(ordinal=0, code="scripted_failure"),
            ]
        }
    )
    with invocation_context("inv-fail"):
        with pytest.raises(RuntimeError, match="scripted_failure"):
            await fake.interpret(_loop_input())
    assert fake.calls[0].status is ComponentStatus.FAILED
    assert fake.calls[0].output_type is None


@pytest.mark.asyncio
async def test_empty_observation_defaults_to_wait() -> None:
    agent = AgentId("agent-1")
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
        ),
        internal_state=InternalAgentState(owner_id=agent),
    )
    result = await default_cognitive_loop().run(loop_input, invocation_id="inv-empty")
    assert type(result.command) is Wait
    situation = result.boundary_records[2].output_artifact
    assert type(situation) is SituationModel
    assert SituationClaimCode.IDLE in situation.claim_codes


@pytest.mark.asyncio
async def test_direct_self_state_projector_passes_active_goal_ids() -> None:
    from agents.cognition.models import (
        RetrievedMemoryContext,
        SubjectiveSnapshot,
    )
    from agents.models import Goal, GoalId, GoalStatus

    agent = AgentId("agent-1")
    snapshot = SubjectiveSnapshot(
        owner_id=agent,
        revision=1,
        memories=(),
        legacy_beliefs=(),
        semantic_beliefs=(),
        goals=(
            Goal(
                goal_id=GoalId("goal-active"),
                owner_id=agent,
                description="secret-active",
                priority=0.8,
                status=GoalStatus.ACTIVE,
            ),
            Goal(
                goal_id=GoalId("goal-done"),
                owner_id=agent,
                description="secret-done",
                priority=0.2,
                status=GoalStatus.COMPLETED,
            ),
        ),
    )
    loop_input = CognitiveLoopInput(
        agent_id=agent,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
            tick=1,
            self_body=_alive_self(),
        ),
        internal_state=InternalAgentState(owner_id=agent),
        snapshot=snapshot,
    )
    situation = SituationModel(
        owner_id=agent,
        tick=1,
        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
        confidence=1.0,
    )
    memory = RetrievedMemoryContext(
        owner_id=agent,
        memory_ids=(),
        belief_ids=(),
        confidence=1.0,
    )
    model = await DirectSelfStateProjector().project(loop_input, situation, memory)
    assert model.goal_ids == (GoalId("goal-active"),)
    assert "secret-active" not in repr(model)
