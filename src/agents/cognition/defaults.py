"""Deterministic V1 placeholder cognition components.

These are explicit stand-ins, not production memory or imagination quality.
They never import or invoke an LLM provider.
"""

from __future__ import annotations

from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    ImaginedFuture,
    IntentionCode,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationCode,
    MotivationEvaluation,
    MotivationScore,
    PerceptionClaimCode,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfBeliefState,
    SituationClaimCode,
    SituationModel,
)
from world.actions import Wait
from world.models import LifeStatus

__all__ = [
    "DirectSelfStateProjector",
    "DirectSituationModeler",
    "EmptyMemoryRetriever",
    "EmptyMemoryUpdateHook",
    "LiteralPerceptionInterpreter",
    "PlaceholderFutureImagination",
    "StableIntentionSelector",
    "StableMotivationEvaluator",
    "WaitFallbackPlanner",
    "default_cognitive_loop",
]

_COMPONENT_VERSION = "v1-placeholder"


class LiteralPerceptionInterpreter:
    """Literal observation interpretation into closed claim codes and counts."""

    async def interpret(self, loop_input: CognitiveLoopInput) -> InterpretedPerception:
        observation = loop_input.observation
        self_body = observation.self_body
        claims: list[PerceptionClaimCode] = []
        life_status: LifeStatus | None = None
        location_id = None
        if self_body is not None:
            claims.append(PerceptionClaimCode.SELF_PRESENT)
            life_status = self_body.life_status
            location_id = self_body.location_id
            if life_status is LifeStatus.DEAD:
                claims.append(PerceptionClaimCode.SELF_DEAD)
            else:
                claims.append(PerceptionClaimCode.SELF_ALIVE)
            claims.append(PerceptionClaimCode.HAS_LOCATION)
        if observation.exits:
            claims.append(PerceptionClaimCode.HAS_EXITS)
        if observation.visible_bodies:
            claims.append(PerceptionClaimCode.HAS_VISIBLE_BODIES)
        if observation.items:
            claims.append(PerceptionClaimCode.HAS_ITEMS)
        if observation.resources:
            claims.append(PerceptionClaimCode.HAS_RESOURCES)
        if observation.occurrences:
            claims.append(PerceptionClaimCode.HAS_OCCURRENCES)
        if observation.communications:
            claims.append(PerceptionClaimCode.HAS_COMMUNICATIONS)
        counts = {
            "exits": len(observation.exits),
            "visible_bodies": len(observation.visible_bodies),
            "items": len(observation.items),
            "resources": len(observation.resources),
            "occurrences": len(observation.occurrences),
            "communications": len(observation.communications),
        }
        return InterpretedPerception(
            owner_id=loop_input.agent_id,
            observer_id=observation.observer_id,
            tick=observation.tick,
            revision=observation.revision,
            life_status=life_status,
            location_id=location_id,
            claim_codes=tuple(claims),
            counts=counts,
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(c.value for c in claims),
                candidate_count=len(claims),
            ),
        )


class EmptyMemoryRetriever:
    """Owner-scoped empty retrieval placeholder (not production memory quality)."""

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
            decision_metadata=DecisionMetadata(candidate_count=0),
        )


class DirectSituationModeler:
    """Map perception claims into a closed situation model."""

    async def model(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
    ) -> SituationModel:
        _ = memory
        claims: list[SituationClaimCode] = []
        if PerceptionClaimCode.SELF_DEAD in perception.claim_codes:
            claims.append(SituationClaimCode.TERMINAL_SELF)
        if PerceptionClaimCode.HAS_COMMUNICATIONS in perception.claim_codes:
            claims.append(SituationClaimCode.SOCIAL_SIGNAL)
        if PerceptionClaimCode.HAS_RESOURCES in perception.claim_codes:
            claims.append(SituationClaimCode.RESOURCE_PRESENT)
        if PerceptionClaimCode.HAS_VISIBLE_BODIES in perception.claim_codes:
            claims.append(SituationClaimCode.THREAT_SIGNAL)
        if PerceptionClaimCode.HAS_LOCATION in perception.claim_codes:
            claims.append(SituationClaimCode.LOCAL_SCENE)
        if not claims:
            claims.append(SituationClaimCode.IDLE)
        return SituationModel(
            owner_id=loop_input.agent_id,
            tick=perception.tick,
            claim_codes=tuple(claims),
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(c.value for c in claims),
                candidate_count=len(claims),
            ),
        )


class DirectSelfStateProjector:
    """Project life status and empty belief/goal id sets from the situation."""

    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfBeliefState:
        life_status = None
        if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
            life_status = LifeStatus.DEAD
        elif SituationClaimCode.LOCAL_SCENE in situation.claim_codes:
            life_status = LifeStatus.ALIVE
        return SelfBeliefState(
            owner_id=loop_input.agent_id,
            life_status=life_status,
            belief_ids=memory.belief_ids,
            goal_ids=(),
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                candidate_count=len(memory.belief_ids),
            ),
        )


class PlaceholderFutureImagination:
    """Bounded placeholder futures derived from situation claims."""

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfBeliefState,
    ) -> PossibleFutures:
        _ = self_state
        futures: list[ImaginedFuture] = []
        if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
            futures.append(
                ImaginedFuture(
                    future_id="terminal",
                    claim_codes=(SituationClaimCode.TERMINAL_SELF,),
                    confidence=1.0,
                )
            )
        else:
            futures.append(
                ImaginedFuture(
                    future_id="idle",
                    claim_codes=(SituationClaimCode.IDLE,),
                    confidence=1.0,
                )
            )
            if SituationClaimCode.LOCAL_SCENE in situation.claim_codes:
                futures.append(
                    ImaginedFuture(
                        future_id="explore",
                        claim_codes=(SituationClaimCode.LOCAL_SCENE,),
                        confidence=0.5,
                    )
                )
            if SituationClaimCode.SOCIAL_SIGNAL in situation.claim_codes:
                futures.append(
                    ImaginedFuture(
                        future_id="social",
                        claim_codes=(SituationClaimCode.SOCIAL_SIGNAL,),
                        confidence=0.4,
                    )
                )
        return PossibleFutures(
            owner_id=loop_input.agent_id,
            futures=tuple(futures),
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(f.future_id for f in futures),
                candidate_count=len(futures),
            ),
        )


class StableMotivationEvaluator:
    """Deterministic motive scores with stable ordering and tie-breaking."""

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfBeliefState,
        futures: PossibleFutures,
    ) -> MotivationEvaluation:
        _ = self_state, futures
        scores: dict[MotivationCode, float] = {
            MotivationCode.WAIT: 0.5,
            MotivationCode.SURVIVE: 0.0,
            MotivationCode.REST: 0.0,
            MotivationCode.EXPLORE: 0.0,
            MotivationCode.SOCIALIZE: 0.0,
        }
        if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
            scores[MotivationCode.WAIT] = 1.0
        else:
            if SituationClaimCode.THREAT_SIGNAL in situation.claim_codes:
                scores[MotivationCode.SURVIVE] = 0.9
            if SituationClaimCode.LOCAL_SCENE in situation.claim_codes:
                scores[MotivationCode.EXPLORE] = 0.6
            if SituationClaimCode.SOCIAL_SIGNAL in situation.claim_codes:
                scores[MotivationCode.SOCIALIZE] = 0.7
            if SituationClaimCode.IDLE in situation.claim_codes:
                scores[MotivationCode.WAIT] = 0.8
        ordered = tuple(
            MotivationScore(motive=motive, score=scores[motive])
            for motive in (
                MotivationCode.SURVIVE,
                MotivationCode.SOCIALIZE,
                MotivationCode.EXPLORE,
                MotivationCode.REST,
                MotivationCode.WAIT,
            )
            if scores[motive] > 0.0
        )
        if not ordered:
            ordered = (MotivationScore(motive=MotivationCode.WAIT, score=1.0),)
        top = max(ordered, key=lambda item: (item.score, -_motive_rank(item.motive)))
        tie = sum(1 for item in ordered if item.score == top.score) > 1
        return MotivationEvaluation(
            owner_id=loop_input.agent_id,
            scores=ordered,
            confidence=top.score,
            decision_metadata=DecisionMetadata(
                selection_codes=(top.motive.value,),
                candidate_count=len(ordered),
                tie_break_applied=tie,
            ),
        )


def _motive_rank(motive: MotivationCode) -> int:
    order = (
        MotivationCode.SURVIVE,
        MotivationCode.SOCIALIZE,
        MotivationCode.EXPLORE,
        MotivationCode.REST,
        MotivationCode.WAIT,
    )
    return order.index(motive)


_INTENTION_FOR_MOTIVE: dict[MotivationCode, IntentionCode] = {
    MotivationCode.SURVIVE: IntentionCode.SURVIVE,
    MotivationCode.SOCIALIZE: IntentionCode.COMMUNICATE,
    MotivationCode.EXPLORE: IntentionCode.MOVE,
    MotivationCode.REST: IntentionCode.REST,
    MotivationCode.WAIT: IntentionCode.WAIT,
}


class StableIntentionSelector:
    """Select intention from the highest motive with stable tie-break."""

    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
    ) -> SelectedIntention:
        if not motivation.scores:
            intention = IntentionCode.WAIT
            source = MotivationCode.WAIT
            confidence = 1.0
            tie = False
        else:
            top = max(
                motivation.scores,
                key=lambda item: (item.score, -_motive_rank(item.motive)),
            )
            tie = sum(1 for item in motivation.scores if item.score == top.score) > 1
            intention = _INTENTION_FOR_MOTIVE[top.motive]
            source = top.motive
            confidence = top.score
        return SelectedIntention(
            owner_id=loop_input.agent_id,
            intention=intention,
            source_motive=source,
            confidence=confidence,
            decision_metadata=DecisionMetadata(
                selection_codes=(intention.value,),
                candidate_count=len(motivation.scores),
                tie_break_applied=tie,
            ),
        )


class WaitFallbackPlanner:
    """Safe V1 planner: always emit a fresh closed ``Wait`` command."""

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
    ) -> ActionPlan:
        _ = intention, futures
        return ActionPlan(
            owner_id=loop_input.agent_id,
            command=Wait(),
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=("wait",),
                candidate_count=1,
            ),
        )


class EmptyMemoryUpdateHook:
    """No-op memory update intents (outcome memories wait for later observations)."""

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


def default_cognitive_loop() -> CognitiveLoop:
    """Build a CognitiveLoop wired with deterministic V1 placeholders."""
    _ = _COMPONENT_VERSION
    return CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=EmptyMemoryRetriever(),
        situation=DirectSituationModeler(),
        self_state=DirectSelfStateProjector(),
        futures=PlaceholderFutureImagination(),
        motivation=StableMotivationEvaluator(),
        intention=StableIntentionSelector(),
        planner=WaitFallbackPlanner(),
        memory_updates=EmptyMemoryUpdateHook(),
    )
