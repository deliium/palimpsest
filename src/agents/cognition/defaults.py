"""Deterministic V1 cognition stage defaults.

Production imagination, motivation appraisal, intention selection, and
command planning are wired by ``default_cognitive_loop()``. Perception,
situation, self-state, and empty-memory helpers remain literal stand-ins
for retrieval quality and never import or invoke an LLM provider.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Final

from agents.cognition.configuration import CognitionIdentityMode
from agents.cognition.goal_manager import PassthroughGoalManager
from agents.cognition.identity import identity_stability_band
from agents.cognition.loop import CognitiveLoop
from agents.cognition.models import (
    ActionPlan,
    CognitiveLoopInput,
    DecisionMetadata,
    GoalBoard,
    ImaginedFuture,
    IntentionCode,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
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
    project_identity_state,
    project_self_model,
)
from agents.models import GoalId, GoalStatus
from memory.beliefs import SemanticBelief, SemanticBeliefHistory
from memory.models import BeliefId
from world.actions import Wait
from world.models import LifeStatus

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.defaults")

__all__ = [
    "DirectSelfStateProjector",
    "DirectSituationModeler",
    "EmptyMemoryRetriever",
    "EmptyMemoryUpdateHook",
    "LiteralPerceptionInterpreter",
    "PassthroughGoalManager",
    "PlaceholderFutureImagination",
    "PresentStateImagination",
    "StableIntentionSelector",
    "StableMotivationEvaluator",
    "SubjectiveRevisionHook",
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
        semantic: tuple[SemanticBelief, ...] = ()
        belief_ids: tuple[BeliefId, ...] = ()
        if loop_input.snapshot is not None:
            semantic = loop_input.snapshot.semantic_beliefs
            belief_ids = tuple(item.belief_id for item in semantic)
        return RetrievedMemoryContext(
            owner_id=loop_input.agent_id,
            memory_ids=(),
            belief_ids=belief_ids,
            confidence=1.0,
            decision_metadata=DecisionMetadata(candidate_count=0),
            semantic_beliefs=semantic,
        )


class DirectSituationModeler:
    """Map perception claims into a closed situation model."""

    __slots__ = ("_emotion_bias",)

    def __init__(self, *, emotion_bias: bool = False) -> None:
        if type(emotion_bias) is not bool:
            raise TypeError("emotion_bias must be bool")
        self._emotion_bias = emotion_bias

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
        prior = (
            None
            if loop_input.snapshot is None
            else loop_input.snapshot.emotional_state
        )
        from agents.cognition.emotion_bias import (
            EMOTION_BIAS_POLICY_VERSION,
            apply_situation_focus_bias,
        )

        ordered, focus_counts, bias_applied = apply_situation_focus_bias(
            claims,
            prior,
            enabled=self._emotion_bias,
        )
        selection = list(c.value for c in ordered)
        if bias_applied:
            selection.append(f"emotion_bias:{EMOTION_BIAS_POLICY_VERSION}")
            selection.extend(
                f"emotion_focus:{code}" for code in sorted(focus_counts)
            )
        return SituationModel(
            owner_id=loop_input.agent_id,
            tick=perception.tick,
            claim_codes=ordered,
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=tuple(selection),
                candidate_count=len(ordered),
            ),
        )


class DirectSelfStateProjector:
    """Project an emergent ``SelfModel`` from semantic beliefs and situation."""

    def __init__(
        self,
        *,
        identity_mode: CognitionIdentityMode = CognitionIdentityMode.PASSTHROUGH,
        belief_histories: Sequence[SemanticBeliefHistory] = (),
        identity_history: object | None = None,
    ) -> None:
        if type(identity_mode) is not CognitionIdentityMode:
            raise TypeError("identity_mode must be CognitionIdentityMode")
        if isinstance(belief_histories, (str, bytes)) or not isinstance(
            belief_histories, Sequence
        ):
            raise TypeError("belief_histories must be ordered")
        if identity_history is not None and not callable(identity_history):
            raise TypeError("identity_history must be callable")
        self._identity_mode = identity_mode
        self._belief_histories = tuple(belief_histories)
        self._identity_history = identity_history

    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfModel:
        life_status = None
        if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
            life_status = LifeStatus.DEAD
        elif SituationClaimCode.LOCAL_SCENE in situation.claim_codes:
            life_status = LifeStatus.ALIVE
        beliefs = memory.semantic_beliefs
        if not beliefs and loop_input.snapshot is not None:
            beliefs = loop_input.snapshot.semantic_beliefs
        goal_ids: tuple[GoalId, ...] = ()
        if loop_input.snapshot is not None:
            goal_ids = tuple(
                goal.goal_id
                for goal in loop_input.snapshot.goals
                if goal.status is GoalStatus.ACTIVE
            )
        model = project_self_model(
            owner_id=loop_input.agent_id,
            life_status=life_status,
            beliefs=beliefs,
            goal_ids=goal_ids,
        )
        identity_state = None
        if self._identity_mode is CognitionIdentityMode.ENABLED:
            by_id = {
                history.belief.belief_id.value: history
                for history in self._belief_histories
            }
            selected_histories: list[SemanticBeliefHistory] = []
            for belief in beliefs:
                if type(belief) is not SemanticBelief:
                    continue
                if belief.claim.predicate.split(".", 1)[0] != "identity":
                    continue
                history = by_id.get(belief.belief_id.value)
                if history is None and self._identity_history is not None:
                    history = self._identity_history(belief.belief_id)
                if history is None:
                    _LOG.error(
                        "identity_projection_rejected",
                        extra={
                            "reason_code": "missing_history",
                            "owner_id": loop_input.agent_id.value,
                        },
                    )
                    raise ValueError("project_identity_state: missing_history")
                selected_histories.append(history)
            identity_state = project_identity_state(
                owner_id=loop_input.agent_id,
                histories=selected_histories,
            )
            model = replace(model, identity=identity_state)
        band_counts = {"low": 0, "mid": 0, "high": 0}
        identity_candidate_count = 0
        identity_active_count = 0
        if identity_state is not None:
            for view in identity_state.views:
                band_counts[identity_stability_band(view.derived_stability)] += 1
                if view.activation.value == "candidate":
                    identity_candidate_count += 1
                elif view.activation.value == "active":
                    identity_active_count += 1
        _LOG.debug(
            "self_model_projected",
            extra={
                "stage": "self_state",
                "version": model.policy_version,
                "owner_id": loop_input.agent_id.value,
                "tick": situation.tick,
                "candidate_count": model.candidate_count,
                "selected_count": len(model.beliefs),
                "aggregate_confidence": model.confidence,
                "identity_mode": self._identity_mode.value,
                "identity_belief_count": (
                    0 if identity_state is None else len(identity_state.views)
                ),
                "identity_candidate_count": identity_candidate_count,
                "active_count": identity_active_count,
                "stability_band_low": band_counts["low"],
                "stability_band_mid": band_counts["mid"],
                "stability_band_high": band_counts["high"],
                "status": "complete",
            },
        )
        return model


class PlaceholderFutureImagination:
    """Bounded placeholder futures derived from situation claims."""

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
        causal_world_model: object | None = None,
        prospective_policy: object | None = None,
        llm_provider: object | None = None,
    ) -> PossibleFutures:
        _ = self_state, memory, goal_board, emotional_state, prospective_policy
        _ = llm_provider
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


class PresentStateImagination:
    """Non-counterfactual imagination-disabled policy.

    Emits a single present-state continuation derived only from current
    situation claims. Does not invent alternate action futures.
    """

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
        causal_world_model: object | None = None,
        prospective_policy: object | None = None,
        llm_provider: object | None = None,
    ) -> PossibleFutures:
        _ = self_state, memory, goal_board, emotional_state, prospective_policy
        _ = llm_provider
        if SituationClaimCode.TERMINAL_SELF in situation.claim_codes:
            claim_codes = (SituationClaimCode.TERMINAL_SELF,)
            future_id = "present-terminal"
        else:
            claim_codes = tuple(situation.claim_codes) or (SituationClaimCode.IDLE,)
            future_id = "present"
        future = ImaginedFuture(
            future_id=future_id,
            claim_codes=claim_codes,
            confidence=1.0,
        )
        return PossibleFutures(
            owner_id=loop_input.agent_id,
            futures=(future,),
            confidence=1.0,
            decision_metadata=DecisionMetadata(
                selection_codes=(future_id,),
                candidate_count=1,
            ),
        )


class StableMotivationEvaluator:
    """Deterministic motive scores with stable ordering and tie-breaking."""

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
        causal_world_model: object | None = None,
    ) -> MotivationEvaluation:
        _ = self_state, futures, goal_board, emotional_state
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
        futures: PossibleFutures | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
        self_state: object | None = None,
        causal_world_model: object | None = None,
        *,
        counterfactual_bias: Mapping[str, float] | None = None,
    ) -> SelectedIntention:
        _ = futures, goal_board, emotional_state, self_state, counterfactual_bias
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
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: object | None = None,
        causal_world_model: object | None = None,
    ) -> ActionPlan:
        _ = intention, futures, memory, goal_board, emotional_state
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
        self_state: object | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = loop_input, plan, perception, memory, intention, self_state
        return ()


class SubjectiveRevisionHook:
    """Propose deferred semantic-belief and relationship revisions from episodes.

    Uses only the frozen snapshot, pending same-tick traces from earlier hooks,
    and current-tick owned traces. Never mutates stores; revisions become
    visible on the next cognition invocation after a successful commit boundary.
    """

    __slots__ = (
        "_belief_policy",
        "_pending",
        "_relationship_policy",
        "_resolve_counterpart",
    )

    def __init__(
        self,
        *,
        belief_policy: object | None = None,
        relationship_policy: object | None = None,
        resolve_counterpart: Callable[..., object] | None = None,
        pending: object | None = None,
    ) -> None:
        from memory.belief_formation import (
            DEFAULT_BELIEF_FORMATION_POLICY,
            BeliefFormationPolicy,
        )
        from social.relationships import (
            DEFAULT_RELATIONSHIP_POLICY,
            RelationshipFormationPolicy,
        )

        if belief_policy is None:
            belief_policy = DEFAULT_BELIEF_FORMATION_POLICY
        elif type(belief_policy) is not BeliefFormationPolicy:
            raise TypeError("belief_policy must be BeliefFormationPolicy")
        if relationship_policy is None:
            relationship_policy = DEFAULT_RELATIONSHIP_POLICY
        elif type(relationship_policy) is not RelationshipFormationPolicy:
            raise TypeError("relationship_policy must be RelationshipFormationPolicy")
        self._belief_policy = belief_policy
        self._relationship_policy = relationship_policy
        self._resolve_counterpart: Callable[..., object] | None = resolve_counterpart
        self._pending = pending

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: object | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        _ = plan, intention
        from agents.models import AgentId
        from memory.belief_formation import (
            BeliefEvidenceCandidate,
            belief_id_for_claim,
            bundle_from_candidates,
            extract_evidence_candidates,
            lineage_root_for_trace,
        )
        from memory.beliefs import (
            BeliefRevisionRequest,
            SemanticClaim,
            canonical_claim_identity,
            canonical_subject_predicate_key,
        )
        from memory.models import MemorySourceKind, MemoryTrace
        from social.relationships import (
            RelationshipInteractionSignal,
            RelationshipRevisionRequest,
            RelationshipSignalKind,
        )

        tick = perception.tick
        owner = loop_input.agent_id
        traces: list[MemoryTrace] = []
        if loop_input.snapshot is not None:
            for trace in loop_input.snapshot.memories:
                if trace.created_tick == tick or trace.source_tick == tick:
                    traces.append(trace)
        pending = self._pending
        if pending is not None:
            pending_traces = getattr(pending, "traces", None)
            if callable(pending_traces):
                for trace in pending_traces():
                    if type(trace) is MemoryTrace:
                        traces.append(trace)
        if memory.reconsolidation is not None:
            derived = memory.reconsolidation.derived_trace
            if type(derived) is MemoryTrace and derived.owner_id == owner:
                traces.append(derived)

        if not traces:
            return ()

        seen: set[str] = set()
        unique_traces: list[MemoryTrace] = []
        for trace in traces:
            if trace.owner_id != owner:
                _LOG.error(
                    "subjective_revision_ownership",
                    extra={
                        "cognition": {
                            "owner_id": owner.value,
                            "tick": tick,
                            "reason_code": "ownership",
                        }
                    },
                )
                raise ValueError("foreign-owner trace rejected")
            if trace.memory_id.value in seen:
                continue
            seen.add(trace.memory_id.value)
            unique_traces.append(trace)

        index = {trace.memory_id: trace for trace in unique_traces}
        candidates = extract_evidence_candidates(
            unique_traces,
            owner_id=owner,
            policy=self._belief_policy,
            trace_index=index,
        )
        from agents.cognition.communication import (
            project_trust_inputs,
            scale_trust_for_identity,
        )
        from agents.cognition.identity import IdentityState
        from memory.belief_formation import (
            BeliefEvidenceCandidate as EvidenceCandidate,
        )
        from memory.belief_formation import (
            evaluate_communicated_testimony,
        )
        from memory.beliefs import CommunicatedEvidenceDecision, EvidenceStance

        resolver = self._resolve_counterpart
        trust_by_speaker: dict[str, tuple[float, float]] = {}
        if loop_input.snapshot is not None:
            for profile in loop_input.snapshot.relationships:
                trust_by_speaker[profile.target_id.value] = project_trust_inputs(
                    profile
                )

        adjusted: list[BeliefEvidenceCandidate] = []
        testimony_signals: list[
            tuple[AgentId, RelationshipSignalKind, MemoryTrace]
        ] = []
        for candidate in candidates:
            trace = index.get(candidate.memory_id)
            if (
                trace is None
                or candidate.provenance_kind is not MemorySourceKind.COMMUNICATED
                or trace.provenance.transmission is None
            ):
                adjusted.append(candidate)
                continue
            meta = trace.provenance.transmission
            speaker_agent: AgentId | None = None
            if resolver is not None and trace.provenance.speaker_id is not None:
                resolved = resolver(trace.provenance.speaker_id)
                if type(resolved) is AgentId:
                    speaker_agent = resolved
            trust, trust_conf = (0.5, 0.2)
            social_factor = 1.0
            if speaker_agent is not None:
                trust, trust_conf = trust_by_speaker.get(
                    speaker_agent.value, (0.5, 0.2)
                )
                identity = getattr(self_state, "identity", None)
                if type(identity) is IdentityState:
                    trust, social_factor = scale_trust_for_identity(
                        trust,
                        identity=identity,
                        counterpart_id=speaker_agent.value,
                    )
            factors = evaluate_communicated_testimony(
                sender_confidence=meta.sender_confidence,
                receiver_confidence=meta.receiver_confidence,
                trust=trust,
                trust_confidence=trust_conf,
                hop_count=meta.hop_count,
                context_relevance=max(0.2, trace.confidence),
                base_contribution=candidate.contribution,
                policy=self._belief_policy,
            )
            _LOG.debug(
                "communicated_testimony_evaluated",
                extra={
                    "cognition": {
                        "owner_id": owner.value,
                        "source_id": (
                            None if speaker_agent is None else speaker_agent.value
                        ),
                        "policy_version": self._belief_policy.version,
                        "hop_count": meta.hop_count,
                        "decision": factors.decision.value,
                        "confidence_delta": factors.confidence_delta,
                        "deduplication_root": candidate.lineage_root_id.value,
                    }
                },
            )
            if (
                speaker_agent is not None
                and type(getattr(self_state, "identity", None)) is IdentityState
            ):
                if social_factor < 0.95:
                    factor_band = "low"
                elif social_factor > 1.05:
                    factor_band = "high"
                else:
                    factor_band = "mid"
                _LOG.debug(
                    "identity_social_scale",
                    extra={
                        "owner_id": owner.value,
                        "counterpart_id": speaker_agent.value,
                        "factor_band": factor_band,
                        "decision": factors.decision.value,
                    },
                )
            if factors.decision is CommunicatedEvidenceDecision.DEFER:
                continue
            stance = candidate.stance
            if factors.decision is CommunicatedEvidenceDecision.CONTRADICT:
                stance = EvidenceStance.CONTRADICTING
            adjusted.append(
                EvidenceCandidate(
                    memory_id=candidate.memory_id,
                    claim=candidate.claim,
                    stance=stance,
                    contribution=factors.adjusted_contribution,
                    lineage_root_id=candidate.lineage_root_id,
                    source_tick=candidate.source_tick,
                    provenance_kind=candidate.provenance_kind,
                    applied_factors=factors,
                )
            )
            if speaker_agent is not None:
                if factors.decision is CommunicatedEvidenceDecision.ACCEPT:
                    testimony_signals.append(
                        (
                            speaker_agent,
                            RelationshipSignalKind.CORROBORATION_RECEIVED,
                            trace,
                        )
                    )
                elif factors.decision is CommunicatedEvidenceDecision.CONTRADICT:
                    testimony_signals.append(
                        (
                            speaker_agent,
                            RelationshipSignalKind.CONTRADICTION_RECEIVED,
                            trace,
                        )
                    )
        candidates = tuple(adjusted)

        groups: dict[str, list[BeliefEvidenceCandidate]] = {}
        claim_for_key: dict[str, SemanticClaim] = {}
        for candidate in candidates:
            key = canonical_subject_predicate_key(candidate.claim)
            groups.setdefault(key, []).append(candidate)
            existing = claim_for_key.get(key)
            if existing is None or canonical_claim_identity(
                candidate.claim
            ) < canonical_claim_identity(existing):
                claim_for_key[key] = candidate.claim

        intents: list[MemoryUpdateIntent] = []
        op_base = f"subj:{owner.value}:t{tick}"
        for index_key, key in enumerate(sorted(groups)):
            claim = claim_for_key[key]
            evidence = bundle_from_candidates(groups[key], target_claim=claim)
            if evidence.total_count == 0:
                continue
            belief_key = belief_id_for_claim(owner_id=owner, claim=claim)
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.REVISE_SEMANTIC_BELIEF,
                    belief_revision=BeliefRevisionRequest(
                        owner_id=owner,
                        operation_id=(
                            f"{op_base}:belief:{index_key}:{belief_key.value}"
                        ),
                        logical_tick=tick,
                        claim=claim,
                        evidence=evidence,
                        policy=self._belief_policy.as_ref(),
                        belief_id=belief_key,
                    ),
                )
            )

        signals_by_target: dict[str, list[RelationshipInteractionSignal]] = {}
        for trace in unique_traces:
            if resolver is None:
                break
            root = lineage_root_for_trace(trace, index)
            kind = RelationshipSignalKind.PROXIMITY
            if trace.provenance.kind is MemorySourceKind.COMMUNICATED:
                kind = RelationshipSignalKind.COMMUNICATION
            counterparts: list[AgentId] = []
            if trace.provenance.speaker_id is not None:
                resolved = resolver(trace.provenance.speaker_id)
                if type(resolved) is AgentId and resolved != owner:
                    counterparts.append(resolved)
            for entity in trace.entities:
                if entity.entity_id is None:
                    continue
                resolved = resolver(entity.entity_id)
                if type(resolved) is AgentId and resolved != owner:
                    counterparts.append(resolved)
            for counterpart in counterparts:
                signal = RelationshipInteractionSignal(
                    counterpart_id=counterpart,
                    kind=kind,
                    strength=min(1.0, max(0.05, trace.confidence * 0.5)),
                    memory_ref=trace.memory_id.value,
                    lineage_root_ref=root.value,
                    source_tick=trace.source_tick,
                )
                signals_by_target.setdefault(counterpart.value, []).append(signal)

        for speaker_agent, signal_kind, trace in testimony_signals:
            if resolver is None:
                break
            root = lineage_root_for_trace(trace, index)
            if trace.provenance.transmission is not None:
                from memory.belief_formation import transmission_root_for_trace

                root = transmission_root_for_trace(trace)
            signal = RelationshipInteractionSignal(
                counterpart_id=speaker_agent,
                kind=signal_kind,
                strength=min(1.0, max(0.05, trace.confidence * 0.5)),
                memory_ref=trace.memory_id.value,
                lineage_root_ref=root.value,
                source_tick=trace.source_tick,
            )
            signals_by_target.setdefault(speaker_agent.value, []).append(signal)

        for target_key, signals in sorted(signals_by_target.items()):
            target = AgentId(target_key)
            deduped: list[RelationshipInteractionSignal] = []
            seen_sig: set[tuple[str, str]] = set()
            for signal in signals:
                sig_key = (signal.kind.value, signal.lineage_root_ref)
                if sig_key in seen_sig:
                    continue
                seen_sig.add(sig_key)
                deduped.append(signal)
            if not deduped:
                continue
            intents.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.REVISE_RELATIONSHIP,
                    relationship_revision=RelationshipRevisionRequest(
                        source_id=owner,
                        target_id=target,
                        operation_id=f"{op_base}:rel:{target_key}",
                        logical_tick=tick,
                        signals=tuple(deduped),
                        policy=self._relationship_policy.as_ref(),
                    ),
                )
            )

        _LOG.debug(
            "subjective_revisions_proposed",
            extra={
                "cognition": {
                    "owner_id": owner.value,
                    "tick": tick,
                    "trace_count": len(unique_traces),
                    "belief_intent_count": sum(
                        1
                        for item in intents
                        if item.kind is MemoryUpdateKind.REVISE_SEMANTIC_BELIEF
                    ),
                    "relationship_intent_count": sum(
                        1
                        for item in intents
                        if item.kind is MemoryUpdateKind.REVISE_RELATIONSHIP
                    ),
                }
            },
        )
        return tuple(intents)


def default_cognitive_loop() -> CognitiveLoop:
    """Build a CognitiveLoop whose counterfactual mode stays disabled.

    ``prepare`` still accepts remembered decisions. The disabled policy
    records no scenarios before emotional appraisal.
    """
    from agents.cognition.configuration import (
        build_cognitive_loop,
        production_cognition_config,
    )

    return build_cognitive_loop(production_cognition_config())
