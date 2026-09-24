"""Type-check fixtures for async CognitiveLoop component protocols.

Positive cases must type-check. Negative authority substitutions live under
``tests/typecheck/invalid/``.
"""

from __future__ import annotations

from agents.cognition.contracts import (
    CognitionStrategy,
    EmotionalStateAppraiser,
    FutureImagination,
    GoalManager,
    IntentionSelector,
    MemoryRetriever,
    MemoryUpdateHook,
    MotivationEvaluator,
    PerceptionInterpreter,
    Perspective,
    Planner,
    SelfStateProjector,
    SituationModeler,
)
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    GoalBoard,
    ImaginedFuture,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationClaimCode,
    SituationModel,
)
from agents.models import AgentId
from world.actions import AgentCommand, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import LifeStatus
from world.observations import Observation


def _loop_input() -> CognitiveLoopInput:
    agent_id = AgentId("agent-1")
    return CognitiveLoopInput(
        agent_id=agent_id,
        observation=Observation(
            world_id=WorldId("world-1"),
            observer_id=EntityId("body-1"),
            revision=WorldRevision(0),
        ),
        internal_state=InternalAgentState(owner_id=agent_id),
    )


class ScriptedPerceptionInterpreter:
    async def interpret(self, loop_input: CognitiveLoopInput) -> InterpretedPerception:
        return InterpretedPerception(
            owner_id=loop_input.agent_id,
            observer_id=loop_input.observation.observer_id,
            tick=loop_input.observation.tick,
            revision=loop_input.observation.revision,
            life_status=LifeStatus.ALIVE,
            location_id=None,
            claim_codes=(PerceptionClaimCode.SELF_PRESENT,),
            counts={},
            confidence=1.0,
        )


class ScriptedMemoryRetriever:
    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        _ = perception
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=(),
            belief_ids=(),
            confidence=1.0,
        )


class ScriptedSituationModeler:
    async def model(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
    ) -> SituationModel:
        _ = perception, memory
        return SituationModel(
            owner_id=loop_input.agent_id,
            tick=loop_input.observation.tick,
            claim_codes=(SituationClaimCode.IDLE,),
            confidence=1.0,
        )


class ScriptedSelfStateProjector:
    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfModel:
        _ = situation, memory
        return SelfModel(
            owner_id=loop_input.agent_id,
            policy_id="self-model-projection",
            policy_version="1",
            life_status=LifeStatus.ALIVE,
            beliefs=(),
            goal_ids=(),
            confidence=1.0,
            candidate_count=0,
        )


class ScriptedGoalManager:
    async def manage(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
    ) -> GoalBoard:
        from agents.cognition.goal_manager import PassthroughGoalManager

        return await PassthroughGoalManager().manage(
            loop_input, situation, self_state, memory
        )


class ScriptedEmotionalStateAppraiser:
    async def appraise(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
        self_state: SelfModel,
        goal_board: GoalBoard,
        prior_state: object | None = None,
    ):
        from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
        from agents.cognition.models import AgentEmotionalState

        prior: AgentEmotionalState | None = None
        if type(prior_state) is AgentEmotionalState:
            prior = prior_state
        return await PassthroughEmotionalStateAppraiser().appraise(
            loop_input,
            perception,
            situation,
            memory,
            self_state,
            goal_board,
            prior,
        )


class ScriptedFutureImagination:
    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
    ) -> PossibleFutures:
        _ = situation, self_state, memory, goal_board, emotional_state
        return PossibleFutures(
            owner_id=loop_input.agent_id,
            futures=(
                ImaginedFuture(
                    future_id="idle",
                    claim_codes=(SituationClaimCode.IDLE,),
                    confidence=1.0,
                ),
            ),
            confidence=1.0,
        )


class ScriptedMotivationEvaluator:
    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
    ) -> MotivationEvaluation:
        _ = situation, self_state, futures, goal_board, emotional_state
        return MotivationEvaluation(
            owner_id=loop_input.agent_id,
            scores=(MotivationScore(motive=MotivationCode.WAIT, score=1.0),),
            confidence=1.0,
        )


class ScriptedIntentionSelector:
    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
    ) -> SelectedIntention:
        _ = motivation, futures, goal_board, emotional_state
        return SelectedIntention(
            owner_id=loop_input.agent_id,
            intention=IntentionCode.WAIT,
            source_motive=MotivationCode.WAIT,
            confidence=1.0,
        )


class ScriptedPlanner:
    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
    ) -> ActionPlan:
        _ = intention, futures, memory, goal_board, emotional_state
        return ActionPlan(owner_id=loop_input.agent_id, command=Wait(), confidence=1.0)


class ScriptedMemoryUpdateHook:
    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = loop_input, plan, perception, memory, intention
        return ()


def _assert_protocols_assignable() -> None:
    perception: PerceptionInterpreter = ScriptedPerceptionInterpreter()
    memory: MemoryRetriever = ScriptedMemoryRetriever()
    situation: SituationModeler = ScriptedSituationModeler()
    self_state: SelfStateProjector = ScriptedSelfStateProjector()
    goal_manager: GoalManager = ScriptedGoalManager()
    emotional_state: EmotionalStateAppraiser = ScriptedEmotionalStateAppraiser()
    futures: FutureImagination = ScriptedFutureImagination()
    motivation: MotivationEvaluator = ScriptedMotivationEvaluator()
    intention: IntentionSelector = ScriptedIntentionSelector()
    planner: Planner = ScriptedPlanner()
    updates: MemoryUpdateHook = ScriptedMemoryUpdateHook()
    _ = (
        perception,
        memory,
        situation,
        self_state,
        goal_manager,
        emotional_state,
        futures,
        motivation,
        intention,
        planner,
        updates,
        Perspective,
        CognitionStrategy,
        AgentCommand,
        _loop_input,
    )
