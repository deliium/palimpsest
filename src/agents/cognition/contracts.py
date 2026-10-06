"""Architecture-neutral cognition strategy and async component protocols.

``Perspective`` remains the sole ``CognitionStrategy.propose()`` input.
``CognitiveLoop`` uses narrow async stage protocols with typed Task-1
artifacts. Components must not accept ``WorldState``, ``World``, engine
snapshots, raw event batches, repositories, mutable writers, or another
agent's observation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from agents.cognition.models import (
    ActionPlan,
    AgentEmotionalState,
    CognitiveLoopInput,
    EmotionalStateEvaluation,
    GoalBoard,
    InterpretedPerception,
    MemoryUpdateIntent,
    MotivationEvaluation,
    OwnerSafeSocialIdentity,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationModel,
    SubjectiveSnapshot,
)
from agents.models import AgentId, DriveProfile, Goal, default_drive_profile
from memory.beliefs import SemanticBelief
from memory.models import Belief, MemoryTrace
from social.models import CommunicationEnvelope
from social.relationships import DirectedRelationshipProfile
from world.actions import AgentCommand
from world.observations import Observation

__all__ = [
    "BeliefRevisionStage",
    "CognitionContractError",
    "CognitionContractErrorCode",
    "CognitionStrategy",
    "EmotionalStateAppraiser",
    "FutureImagination",
    "GoalManager",
    "IntentionSelector",
    "MemoryRetriever",
    "MemoryUpdateHook",
    "MotivationEvaluator",
    "PerceptionInterpreter",
    "Perspective",
    "Planner",
    "ReconstructionStage",
    "ReflectionStage",
    "SelfStateProjector",
    "SituationModeler",
    "SocialMessagePolicy",
    "TheoryOfMindStage",
    "WorldModelStage",
]


class CognitionContractErrorCode(StrEnum):
    """Stable contract failure codes (no payload or exception text)."""

    TYPE_MISMATCH = "type_mismatch"
    OWNERSHIP = "ownership"
    INVALID_SEQUENCE = "invalid_sequence"


class CognitionContractError(Exception):
    """Fail-closed boundary error exposing only safe identifiers."""

    def __init__(
        self,
        code: CognitionContractErrorCode,
        *,
        component: str,
        ordinal: int | None = None,
    ) -> None:
        if type(code) is not CognitionContractErrorCode:
            raise TypeError("code must be CognitionContractErrorCode")
        component_name = component.strip()
        if not component_name:
            raise ValueError("component must be non-blank")
        self.code = code
        self.component = component_name
        self.ordinal = ordinal
        parts = [f"code={code.value}", f"component={component_name}"]
        if ordinal is not None:
            parts.append(f"ordinal={ordinal}")
        super().__init__(",".join(parts))

    def log_fields(self) -> dict[str, object]:
        fields: dict[str, object] = {
            "code": self.code.value,
            "component": self.component,
        }
        if self.ordinal is not None:
            fields["ordinal"] = self.ordinal
        return fields

    def __repr__(self) -> str:
        return f"CognitionContractError({self})"


def _owned_tuple(
    name: str,
    values: Sequence[object],
    *,
    model_type: type,
    owner_id: AgentId,
) -> tuple[object, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
        item_owner = item.owner_id  # type: ignore[attr-defined]
        if item_owner != owner_id:
            raise ValueError(f"{name} entries must belong to perspective agent")
    return items


@dataclass(frozen=True, slots=True)
class Perspective:
    """Immutable cognition context. Contains no LLM, store, or world authority.

    ``inbox`` is out-of-band social mail addressed to ``agent_id``. Perceived
    communication claims remain on ``observation.communications`` only.
    """

    agent_id: AgentId
    observation: Observation
    memories: tuple[MemoryTrace, ...]
    beliefs: tuple[Belief, ...]
    inbox: tuple[CommunicationEnvelope, ...]
    semantic_beliefs: tuple[SemanticBelief, ...] = ()
    relationships: tuple[DirectedRelationshipProfile, ...] = ()
    snapshot_revision: int = 0
    goals: tuple[Goal, ...] = ()
    drives: DriveProfile | None = None
    social_identity: OwnerSafeSocialIdentity | None = None
    emotional_state: object | None = None
    causal_world_model: object | None = None
    theory_of_mind: object | None = None
    reputation: object | None = None
    territorial_claims: object | None = None
    group_formation: object | None = None
    social_norms: object | None = None
    social_conventions: object | None = None
    artifact_interpretations: object | None = None
    semantic_naming: object | None = None
    cultural_narratives: object | None = None
    developmental_knowledge: object | None = None
    mentorship: object | None = None
    cultural_features: object | None = None
    competence_model: object | None = None
    declarative_advice: object | None = None
    recipe_beliefs: object | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("Perspective.agent_id must be AgentId")
        if type(self.observation) is not Observation:
            raise TypeError("Perspective.observation must be Observation")
        object.__setattr__(
            self,
            "memories",
            _owned_tuple(
                "Perspective.memories",
                self.memories,
                model_type=MemoryTrace,
                owner_id=self.agent_id,
            ),
        )
        object.__setattr__(
            self,
            "beliefs",
            _owned_tuple(
                "Perspective.beliefs",
                self.beliefs,
                model_type=Belief,
                owner_id=self.agent_id,
            ),
        )
        object.__setattr__(
            self,
            "semantic_beliefs",
            _owned_tuple(
                "Perspective.semantic_beliefs",
                self.semantic_beliefs,
                model_type=SemanticBelief,
                owner_id=self.agent_id,
            ),
        )
        if isinstance(self.relationships, (set, frozenset)):
            raise TypeError("Perspective.relationships must be an ordered sequence")
        if isinstance(self.relationships, (str, bytes)) or not isinstance(
            self.relationships, Sequence
        ):
            raise TypeError("Perspective.relationships must be an ordered sequence")
        relationships = tuple(self.relationships)
        for profile in relationships:
            if type(profile) is not DirectedRelationshipProfile:
                raise TypeError(
                    "Perspective.relationships entries must be "
                    "DirectedRelationshipProfile"
                )
            if profile.source_id != self.agent_id:
                raise ValueError(
                    "Perspective.relationships source_id must match agent_id"
                )
        object.__setattr__(self, "relationships", relationships)
        from world.identifiers import require_exact_nonneg_int

        object.__setattr__(
            self,
            "snapshot_revision",
            require_exact_nonneg_int(
                "Perspective.snapshot_revision", self.snapshot_revision
            ),
        )
        if isinstance(self.inbox, (set, frozenset)):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        if isinstance(self.inbox, (str, bytes)) or not isinstance(self.inbox, Sequence):
            raise TypeError("Perspective.inbox must be an ordered sequence")
        inbox = tuple(self.inbox)
        for envelope in inbox:
            if type(envelope) is not CommunicationEnvelope:
                raise TypeError(
                    "Perspective.inbox entries must be CommunicationEnvelope"
                )
            if envelope.recipient_id != self.agent_id:
                raise ValueError(
                    "Perspective.inbox envelope recipient_id must match agent_id"
                )
        object.__setattr__(self, "inbox", inbox)
        if isinstance(self.goals, (set, frozenset)):
            raise TypeError("Perspective.goals: not_ordered")
        if isinstance(self.goals, (str, bytes)) or not isinstance(self.goals, Sequence):
            raise TypeError("Perspective.goals: not_ordered")
        goals = tuple(self.goals)
        seen_goals: set[str] = set()
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("Perspective.goals: invalid_entry_type")
            if goal.owner_id != self.agent_id:
                raise ValueError("Perspective.goals: ownership")
            if goal.goal_id.value in seen_goals:
                raise ValueError("Perspective.goals: duplicate")
            seen_goals.add(goal.goal_id.value)
        object.__setattr__(self, "goals", goals)
        if self.drives is None:
            object.__setattr__(self, "drives", default_drive_profile(self.agent_id))
        else:
            if type(self.drives) is not DriveProfile:
                raise TypeError("Perspective.drives: invalid_type")
            if self.drives.owner_id != self.agent_id:
                raise ValueError("Perspective.drives: ownership")
        if self.social_identity is not None:
            if type(self.social_identity) is not OwnerSafeSocialIdentity:
                raise TypeError("Perspective.social_identity: invalid_type")
            if self.social_identity.owner_id != self.agent_id:
                raise ValueError("Perspective.social_identity: ownership")
            if self.social_identity.owner_entity_id != self.observation.observer_id:
                raise ValueError("Perspective.social_identity: entity_mismatch")
        if self.emotional_state is not None:
            from agents.cognition.models import AgentEmotionalState

            if type(self.emotional_state) is not AgentEmotionalState:
                raise TypeError("Perspective.emotional_state: invalid_type")
            if self.emotional_state.owner_id != self.agent_id:
                raise ValueError("Perspective.emotional_state: ownership")
        if self.causal_world_model is not None:
            from agents.cognition.world_model import CausalWorldModel

            if type(self.causal_world_model) is not CausalWorldModel:
                raise TypeError("Perspective.causal_world_model: invalid_type")
            if self.causal_world_model.owner_id != self.agent_id:
                raise ValueError("Perspective.causal_world_model: ownership")
        from agents.cognition.theory_of_mind import require_owner_theory

        require_owner_theory(
            self.theory_of_mind,
            self.agent_id,
            field_name="Perspective.theory_of_mind",
        )
        from agents.cognition.reputation import require_owner_reputation

        require_owner_reputation(
            self.reputation,
            self.agent_id,
            field_name="Perspective.reputation",
        )
        from agents.cognition.territorial import require_owner_territorial_claims

        require_owner_territorial_claims(
            self.territorial_claims,
            self.agent_id,
            field_name="Perspective.territorial_claims",
        )
        from agents.cognition.group_formation import require_owner_group_formation

        require_owner_group_formation(
            self.group_formation,
            self.agent_id,
            field_name="Perspective.group_formation",
        )
        from agents.cognition.social_norms import require_owner_social_norms

        require_owner_social_norms(
            self.social_norms,
            self.agent_id,
            field_name="Perspective.social_norms",
        )
        from agents.cognition.social_conventions import require_owner_social_conventions

        require_owner_social_conventions(
            self.social_conventions,
            self.agent_id,
            field_name="Perspective.social_conventions",
        )
        from agents.cognition.artifacts import require_owner_artifact_interpretations

        require_owner_artifact_interpretations(
            self.artifact_interpretations,
            self.agent_id,
            field_name="Perspective.artifact_interpretations",
        )
        from agents.cognition.semantic_naming import require_owner_semantic_naming

        require_owner_semantic_naming(
            self.semantic_naming,
            self.agent_id,
            field_name="Perspective.semantic_naming",
        )
        from agents.cognition.cultural_narratives import (
            require_owner_cultural_narratives,
        )

        require_owner_cultural_narratives(
            self.cultural_narratives,
            self.agent_id,
            field_name="Perspective.cultural_narratives",
        )
        from agents.cognition.developmental_learning import (
            require_owner_developmental_knowledge,
        )

        require_owner_developmental_knowledge(
            self.developmental_knowledge,
            self.agent_id,
            field_name="Perspective.developmental_knowledge",
        )
        from agents.cognition.mentorship import require_owner_mentorship

        require_owner_mentorship(
            self.mentorship,
            self.agent_id,
            field_name="Perspective.mentorship",
        )
        from agents.cognition.cultural_features import require_owner_cultural_features

        require_owner_cultural_features(
            self.cultural_features,
            self.agent_id,
            field_name="Perspective.cultural_features",
        )
        from agents.cognition.competence import require_owner_competence

        require_owner_competence(
            self.competence_model,
            self.agent_id,
            field_name="Perspective.competence_model",
        )
        from agents.cognition.teaching import require_owner_advice

        require_owner_advice(
            self.declarative_advice,
            self.agent_id,
            field_name="Perspective.declarative_advice",
        )
        from agents.cognition.production import require_owner_recipe_beliefs

        require_owner_recipe_beliefs(
            self.recipe_beliefs,
            self.agent_id,
            field_name="Perspective.recipe_beliefs",
        )

    def to_snapshot(self) -> SubjectiveSnapshot:
        """Freeze this perspective into a ``SubjectiveSnapshot``."""
        from agents.cognition.models import AgentEmotionalState

        emotion = self.emotional_state
        if emotion is not None and type(emotion) is not AgentEmotionalState:
            raise TypeError("Perspective.emotional_state: invalid_type")
        return SubjectiveSnapshot(
            owner_id=self.agent_id,
            revision=self.snapshot_revision,
            memories=self.memories,
            legacy_beliefs=self.beliefs,
            semantic_beliefs=self.semantic_beliefs,
            relationships=self.relationships,
            goals=self.goals,
            drives=self.drives,
            inbox=self.inbox,
            social_identity=self.social_identity,
            emotional_state=emotion,  # type: ignore[arg-type]
            causal_world_model=self.causal_world_model,
            theory_of_mind=self.theory_of_mind,
            reputation=self.reputation,
            territorial_claims=self.territorial_claims,
            group_formation=self.group_formation,
            social_norms=self.social_norms,
            social_conventions=self.social_conventions,
            artifact_interpretations=self.artifact_interpretations,
            semantic_naming=self.semantic_naming,
            cultural_narratives=self.cultural_narratives,
            developmental_knowledge=self.developmental_knowledge,
            mentorship=self.mentorship,
            cultural_features=self.cultural_features,
            competence_model=self.competence_model,
            declarative_advice=self.declarative_advice,
            recipe_beliefs=self.recipe_beliefs,
        )

    def __repr__(self) -> str:
        drive_count = 0 if self.drives is None else len(self.drives.dispositions)
        counterpart_count = (
            0
            if self.social_identity is None
            else len(self.social_identity.counterparts)
        )
        return (
            f"Perspective(agent_id={self.agent_id.value!r}, "
            f"memory_count={len(self.memories)}, "
            f"belief_count={len(self.beliefs)}, "
            f"semantic_belief_count={len(self.semantic_beliefs)}, "
            f"relationship_count={len(self.relationships)}, "
            f"goal_count={len(self.goals)}, "
            f"drive_count={drive_count}, "
            f"inbox_count={len(self.inbox)}, "
            f"counterpart_count={counterpart_count}, "
            f"snapshot_revision={self.snapshot_revision})"
        )


class CognitionStrategy(Protocol):
    """Produce a non-authoritative command from an immutable perspective."""

    def propose(self, perspective: Perspective) -> AgentCommand:
        """Return an agent command. Must not mutate world state."""
        ...


class PerceptionInterpreter(Protocol):
    """Interpret one observation into structured perception claims."""

    async def interpret(self, loop_input: CognitiveLoopInput) -> InterpretedPerception:
        """Return interpreted perception for ``loop_input.agent_id`` only."""
        ...


class MemoryRetriever(Protocol):
    """Read-only owner-scoped memory/belief retrieval."""

    async def retrieve(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
    ) -> RetrievedMemoryContext:
        """Return references only; must not mutate memory stores."""
        ...


class ReconstructionStage(Protocol):
    """Cognition-facing reconstruction slot.

    Selects or wraps an existing ``memory.contracts.MemoryReconstructor``
    implementation (for example ``DeterministicMemoryReconstructor`` or
    ``LLMMemoryReconstructor``). This Protocol must **not** be named
    ``MemoryReconstructor`` — that name belongs to ``memory.contracts``.

    Inputs/outputs stay on memory reconstruction artifacts
    (``RecallEvidence`` → ``ReconstructedMemory``). Implementations must not
    accept ``WorldState``, event stores, or another agent's private cognition.
    """

    async def reconstruct(self, evidence: object) -> object:
        """Project owner-scoped recall evidence into reconstructed memory."""
        ...


class BeliefRevisionStage(Protocol):
    """Owner-scoped belief/relationship revision intent production.

    This is a **memory-update slot**, not a new ``CognitiveLoop`` ordinal.
    Typical binding is ``SubjectiveRevisionHook``. Fail closed on owner
    mismatch via ``CognitionContractError`` patterns where applicable.
    """

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: SelfModel | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]:
        """Return deferred revision intents; must not mutate stores."""
        ...


class WorldModelStage(Protocol):
    """Causal world-model stage over owner-scoped hypotheses.

    Wraps ``WorldModelPolicy`` plus mode selection. Passthrough bindings leave
    the model unchanged. Must not import ``WorldState`` or simulation types.
    """

    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        """Re-rank or pass through owner-scoped causal hypotheses."""
        ...


class ReflectionStage(Protocol):
    """Periodic reflection stage over owner-scoped evidence.

    Wraps ``ReflectionPolicy`` / reflection planning. Disabled bindings return
    ``None`` (no pass). Not a loop ordinal; runs after command selection when
    reflection mode is enabled.
    """

    def plan(
        self,
        *,
        context: object,
        triggers: object,
        mode: str,
        consolidation: object | None = None,
        acknowledged_goal_ids: tuple[object, ...] = (),
        selected_ids: tuple[str, ...] | None = None,
        fallback_used: bool = False,
        causal_world_model: object | None = None,
    ) -> object | None:
        """Materialize a reflection plan, or ``None`` when no pass runs."""
        ...


class TheoryOfMindStage(Protocol):
    """First-order theory-of-mind stage over owner-scoped hypotheses.

    Wraps ``TheoryOfMindPolicy`` plus mode selection. Passthrough bindings
    store no hypotheses. Must not accept another agent's private cognition.
    """

    async def select(
        self,
        model: object,
        *,
        tick: int,
        provider: object | None = None,
    ) -> object:
        """Re-rank or pass through owner-scoped ToM hypotheses."""
        ...


class SituationModeler(Protocol):
    """Build a situation model from perception and memory context."""

    async def model(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
    ) -> SituationModel: ...


class SelfStateProjector(Protocol):
    """Project an emergent self-model from owner-scoped beliefs."""

    async def project(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
    ) -> SelfModel: ...


class GoalManager(Protocol):
    """Maintain hierarchical goals and emit a frozen ``GoalBoard``."""

    async def manage(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
    ) -> GoalBoard: ...


class EmotionalStateAppraiser(Protocol):
    """Appraise owner-scoped short-term emotional state after goal management."""

    async def appraise(
        self,
        loop_input: CognitiveLoopInput,
        perception: InterpretedPerception,
        situation: SituationModel,
        memory: RetrievedMemoryContext,
        self_state: SelfModel,
        goal_board: GoalBoard,
        prior_state: AgentEmotionalState | None = None,
        *,
        counterfactual_scenarios: tuple[object, ...] = (),
    ) -> EmotionalStateEvaluation: ...


class FutureImagination(Protocol):
    """Produce bounded imagined futures from subjective evidence only."""

    async def imagine(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        memory: RetrievedMemoryContext,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
        prospective_policy: object | None = None,
        llm_provider: object | None = None,
        budget_ledger: object | None = None,
    ) -> PossibleFutures: ...


class MotivationEvaluator(Protocol):
    """Score closed motives from situation, self-state, and futures."""

    async def evaluate(
        self,
        loop_input: CognitiveLoopInput,
        situation: SituationModel,
        self_state: SelfModel,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
    ) -> MotivationEvaluation: ...


class IntentionSelector(Protocol):
    """Select one closed intention from motivation appraisals and futures."""

    async def select(
        self,
        loop_input: CognitiveLoopInput,
        motivation: MotivationEvaluation,
        futures: PossibleFutures,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        self_state: SelfModel | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
        *,
        counterfactual_bias: Mapping[str, float] | None = None,
    ) -> SelectedIntention: ...


class Planner(Protocol):
    """Construct a fresh closed ``AgentCommand`` plan from the intention."""

    async def plan(
        self,
        loop_input: CognitiveLoopInput,
        intention: SelectedIntention,
        futures: PossibleFutures,
        memory: RetrievedMemoryContext | None = None,
        goal_board: GoalBoard | None = None,
        emotional_state: EmotionalStateEvaluation | None = None,
        causal_world_model: object | None = None,
        theory_of_mind: object | None = None,
        self_model: object | None = None,
        strategy_mode: object | None = None,
        strategy_policy: object | None = None,
        reputation: object | None = None,
        reputation_mode: object | None = None,
        reputation_policy: object | None = None,
    ) -> ActionPlan: ...


class SocialMessagePolicy(Protocol):
    """Deterministic or provider-backed talk/ask/tell selection (non-authoritative)."""

    def select(
        self,
        *,
        owner_id: object,
        speaker_id: object,
        observation: object,
        memory: RetrievedMemoryContext,
        preferred_recipient_id: object | None = None,
        snapshot_memories: object = (),
        emotional_state: EmotionalStateEvaluation | None = None,
        mind: object | None = None,
        strategy_mode: object | None = None,
        goal_board: object | None = None,
        relationships: object | None = None,
        risks: object | None = None,
        self_model: object | None = None,
        norms: object | None = None,
        strategy_policy: object | None = None,
    ) -> object | None: ...


class MemoryUpdateHook(Protocol):
    """Return post-cognition memory/belief write intents (no store mutation)."""

    async def propose_updates(
        self,
        loop_input: CognitiveLoopInput,
        plan: ActionPlan,
        perception: InterpretedPerception,
        memory: RetrievedMemoryContext,
        intention: SelectedIntention,
        self_state: SelfModel | None = None,
    ) -> tuple[MemoryUpdateIntent, ...]: ...
