"""Explicit async CognitiveLoop with fixed stage order and boundary records.

No LangGraph, LangChain, DAG engine, plugin discovery, or hidden callbacks.
Components are constructor-injected and invoked sequentially.
"""

from __future__ import annotations

import hashlib
import logging
from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from inspect import Parameter, signature
from typing import Any, Final, TypeVar, cast

from agents.cognition.contracts import (
    EmotionalStateAppraiser,
    FutureImagination,
    GoalManager,
    IntentionSelector,
    MemoryRetriever,
    MemoryUpdateHook,
    MotivationEvaluator,
    PerceptionInterpreter,
    Planner,
    SelfStateProjector,
    SituationModeler,
)
from agents.cognition.models import (
    ActionPlan,
    CognitionFailureReason,
    CognitiveLoopInput,
    CognitiveLoopProposal,
    CognitiveLoopResult,
    ComponentBoundaryRecord,
    ComponentKind,
    ComponentStatus,
    DecisionMetadata,
    EmotionalStateEvaluation,
    GoalBoard,
    IntentionCode,
    InternalAgentState,
    InterpretedPerception,
    MemoryUpdateIntent,
    MemoryUpdateKind,
    MotivationEvaluation,
    PossibleFutures,
    RetrievedMemoryContext,
    SelectedIntention,
    SelfModel,
    SituationModel,
)
from world.actions import AgentCommand, require_agent_command

__all__ = [
    "COMPONENT_VERSION",
    "CognitiveLoop",
    "CognitiveLoopError",
    "CognitiveLoopFailure",
]

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.loop")
COMPONENT_VERSION: Final[str] = "v1"

_STAGE_ORDER: Final[tuple[ComponentKind, ...]] = (
    ComponentKind.PERCEPTION,
    ComponentKind.MEMORY_RETRIEVAL,
    ComponentKind.SITUATION,
    ComponentKind.SELF_STATE,
    ComponentKind.GOAL_MANAGEMENT,
    ComponentKind.EMOTIONAL_STATE,
    ComponentKind.FUTURES,
    ComponentKind.MOTIVATION,
    ComponentKind.INTENTION,
    ComponentKind.PLANNING,
    ComponentKind.MEMORY_UPDATE,
)

T = TypeVar("T")


class CognitiveLoopError(Exception):
    """Terminal loop failure with a safe receipt of completed boundaries."""

    def __init__(self, failure: CognitiveLoopFailure) -> None:
        if type(failure) is not CognitiveLoopFailure:
            raise TypeError("failure must be CognitiveLoopFailure")
        self.failure = failure
        super().__init__(
            f"code={failure.reason.value},component={failure.component_kind.value},"
            f"ordinal={failure.ordinal}"
        )

    def log_fields(self) -> dict[str, object]:
        return self.failure.log_fields()

    def __repr__(self) -> str:
        return f"CognitiveLoopError({self})"


@dataclass(frozen=True, slots=True)
class CognitiveLoopFailure:
    """Typed failure receipt without private model reasoning payloads."""

    invocation_id: str
    agent_id: str
    reason: CognitionFailureReason
    component_kind: ComponentKind
    ordinal: int
    boundary_records: tuple[ComponentBoundaryRecord, ...]

    def __post_init__(self) -> None:
        if type(self.reason) is not CognitionFailureReason:
            raise TypeError("reason must be CognitionFailureReason")
        if type(self.component_kind) is not ComponentKind:
            raise TypeError("component_kind must be ComponentKind")
        if type(self.boundary_records) is not tuple:
            raise TypeError("boundary_records must be a tuple")
        for record in self.boundary_records:
            if type(record) is not ComponentBoundaryRecord:
                raise TypeError(
                    "boundary_records entries must be ComponentBoundaryRecord"
                )

    def log_fields(self) -> dict[str, object]:
        return {
            "invocation_id": self.invocation_id,
            "agent_id": self.agent_id,
            "reason": self.reason.value,
            "component_kind": self.component_kind.value,
            "ordinal": self.ordinal,
            "boundary_count": len(self.boundary_records),
        }

    def __repr__(self) -> str:
        return (
            f"CognitiveLoopFailure(invocation_id={self.invocation_id!r}, "
            f"reason={self.reason.value!r}, "
            f"component_kind={self.component_kind.value!r}, "
            f"ordinal={self.ordinal}, "
            f"boundary_count={len(self.boundary_records)})"
        )


def _tick_memories(
    proposal: CognitiveLoopProposal, updates: tuple[object, ...]
) -> tuple[object, ...]:
    from memory.models import MemoryTrace

    snapshot = proposal.loop_input.snapshot
    memories: list[MemoryTrace] = [] if snapshot is None else list(snapshot.memories)
    seen = {memory.memory_id.value for memory in memories}
    for intent in updates:
        if type(intent) is not MemoryUpdateIntent:
            continue
        if intent.kind is not MemoryUpdateKind.WRITE_MEMORY:
            continue
        memory = intent.memory
        if type(memory) is not MemoryTrace or memory.memory_id.value in seen:
            continue
        memories.append(memory)
        seen.add(memory.memory_id.value)
    return tuple(memories)


class CognitiveLoop:
    """Sequential cognitive pipeline returning one closed ``AgentCommand``."""

    __slots__ = (
        "_artifact_interpretation_mode",
        "_semantic_naming_mode",
        "_semantic_naming_policy",
        "_communication_strategy_mode",
        "_communication_strategy_policy",
        "_competence_policy",
        "_consolidation_mode",
        "_consolidation_policy",
        "_consolidation_selector",
        "_counterfactual_fallback",
        "_counterfactual_llm_calls",
        "_counterfactual_mode",
        "_counterfactual_policy",
        "_counterfactual_skipped",
        "_counterfactual_state",
        "_deferred_dissonance",
        "_emotional_state",
        "_epistemic_policy",
        "_futures",
        "_goal_manager",
        "_group_formation_mode",
        "_group_formation_policy",
        "_identity_mode",
        "_intention",
        "_last_counterfactual_scenarios",
        "_memory",
        "_memory_updates",
        "_motivation",
        "_perception",
        "_planner",
        "_production_allow_provider",
        "_production_knowledge_mode",
        "_prospective_policy",
        "_reflection_mode",
        "_reflection_policy",
        "_reflection_selector",
        "_reputation_mode",
        "_reputation_policy",
        "_self_state",
        "_situation",
        "_skill_learning_mode",
        "_social_convention_mode",
        "_social_convention_policy",
        "_social_norm_mode",
        "_social_norm_policy",
        "_teaching_mode",
        "_teaching_policy",
        "_territorial_claim_mode",
        "_territorial_claim_policy",
        "_theory_of_mind_mode",
        "_theory_of_mind_policy",
        "_world_model_mode",
        "_world_model_policy",
        "_world_model_provider",
    )

    def __init__(
        self,
        *,
        perception: PerceptionInterpreter,
        memory: MemoryRetriever,
        situation: SituationModeler,
        self_state: SelfStateProjector,
        goal_manager: GoalManager,
        emotional_state: EmotionalStateAppraiser,
        futures: FutureImagination,
        motivation: MotivationEvaluator,
        intention: IntentionSelector,
        planner: Planner,
        memory_updates: MemoryUpdateHook,
        consolidation_mode: object | None = None,
        consolidation_policy: object | None = None,
        consolidation_selector: object | None = None,
        reflection_mode: object | None = None,
        reflection_policy: object | None = None,
        reflection_selector: object | None = None,
        identity_mode: object | None = None,
        world_model_mode: object | None = None,
        world_model_policy: object | None = None,
        world_model_provider: object | None = None,
        theory_of_mind_mode: object | None = None,
        theory_of_mind_policy: object | None = None,
        epistemic_policy: object | None = None,
        prospective_policy: object | None = None,
        counterfactual_mode: object | None = None,
        counterfactual_policy: object | None = None,
        communication_strategy_mode: object | None = None,
        communication_strategy_policy: object | None = None,
        reputation_mode: object | None = None,
        reputation_policy: object | None = None,
        skill_learning_mode: object | None = None,
        competence_belief_policy: object | None = None,
        teaching_interaction_mode: object | None = None,
        teaching_claim_policy: object | None = None,
        territorial_claim_mode: object | None = None,
        territorial_claim_policy: object | None = None,
        group_formation_mode: object | None = None,
        group_formation_policy: object | None = None,
        social_norm_mode: object | None = None,
        social_norm_policy: object | None = None,
        social_convention_mode: object | None = None,
        social_convention_policy: object | None = None,
        artifact_interpretation_mode: object | None = None,
        semantic_naming_mode: object | None = None,
        semantic_naming_policy: object | None = None,
        production_knowledge_mode: object | None = None,
        production_allow_provider: bool = False,
    ) -> None:
        self._perception = perception
        self._memory = memory
        self._situation = situation
        self._self_state = self_state
        self._goal_manager = goal_manager
        self._emotional_state = emotional_state
        self._futures = futures
        self._motivation = motivation
        self._intention = intention
        self._planner = planner
        self._memory_updates = memory_updates
        from agents.cognition.configuration import CognitionConsolidationMode

        mode = (
            CognitionConsolidationMode.DISABLED
            if consolidation_mode is None
            else consolidation_mode
        )
        if type(mode) is not CognitionConsolidationMode:
            raise TypeError("consolidation_mode must be CognitionConsolidationMode")
        self._consolidation_mode = mode
        self._consolidation_policy = consolidation_policy
        self._consolidation_selector = consolidation_selector
        from agents.cognition.configuration import CognitionReflectionMode

        reflection = (
            CognitionReflectionMode.DISABLED
            if reflection_mode is None
            else reflection_mode
        )
        if type(reflection) is not CognitionReflectionMode:
            raise TypeError("reflection_mode must be CognitionReflectionMode")
        self._reflection_mode = reflection
        self._reflection_policy = reflection_policy
        self._reflection_selector = reflection_selector
        from agents.cognition.configuration import CognitionIdentityMode

        identity = (
            CognitionIdentityMode.PASSTHROUGH
            if identity_mode is None
            else identity_mode
        )
        if type(identity) is not CognitionIdentityMode:
            raise TypeError("identity_mode must be CognitionIdentityMode")
        self._identity_mode = identity
        from agents.cognition.configuration import CognitionWorldModelMode
        from agents.cognition.world_model import WorldModelPolicy

        world_mode = (
            CognitionWorldModelMode.PASSTHROUGH
            if world_model_mode is None
            else world_model_mode
        )
        if type(world_mode) is not CognitionWorldModelMode:
            raise TypeError("world_model_mode must be CognitionWorldModelMode")
        if world_model_policy is None:
            policy = None
        elif type(world_model_policy) is not WorldModelPolicy:
            raise TypeError("world_model_policy must be WorldModelPolicy")
        else:
            policy = world_model_policy
        self._world_model_mode = world_mode
        self._world_model_policy = policy
        self._world_model_provider = world_model_provider
        from agents.cognition.configuration import CognitionTheoryOfMindMode
        from agents.cognition.theory_of_mind import TheoryOfMindPolicy

        mind_mode = (
            CognitionTheoryOfMindMode.PASSTHROUGH
            if theory_of_mind_mode is None
            else theory_of_mind_mode
        )
        if type(mind_mode) is not CognitionTheoryOfMindMode:
            raise TypeError("theory_of_mind_mode must be CognitionTheoryOfMindMode")
        if theory_of_mind_policy is None:
            mind_policy = None
        elif type(theory_of_mind_policy) is not TheoryOfMindPolicy:
            raise TypeError("theory_of_mind_policy must be TheoryOfMindPolicy")
        else:
            mind_policy = theory_of_mind_policy
        self._theory_of_mind_mode = mind_mode
        self._theory_of_mind_policy = mind_policy
        if epistemic_policy is not None:
            from agents.cognition.epistemic import EpistemicPolicy

            if type(epistemic_policy) is not EpistemicPolicy:
                raise TypeError("epistemic_policy must be EpistemicPolicy")
        self._epistemic_policy = epistemic_policy
        if prospective_policy is not None:
            from agents.cognition.prospective import ProspectivePolicy

            if type(prospective_policy) is not ProspectivePolicy:
                raise TypeError("prospective_policy must be ProspectivePolicy")
        self._prospective_policy = prospective_policy
        from agents.cognition.configuration import CognitionCounterfactualMode

        counterfactual = (
            CognitionCounterfactualMode.DISABLED
            if counterfactual_mode is None
            else counterfactual_mode
        )
        if type(counterfactual) is not CognitionCounterfactualMode:
            raise TypeError("counterfactual_mode must be CognitionCounterfactualMode")
        if counterfactual_policy is not None:
            from agents.cognition.counterfactual import CounterfactualPolicy

            if type(counterfactual_policy) is not CounterfactualPolicy:
                raise TypeError("counterfactual_policy must be CounterfactualPolicy")
        self._counterfactual_mode = counterfactual
        self._counterfactual_policy = counterfactual_policy
        self._last_counterfactual_scenarios: tuple[object, ...] = ()
        from agents.cognition.counterfactual import CounterfactualState

        self._counterfactual_state = CounterfactualState()
        self._counterfactual_skipped = 0
        self._counterfactual_fallback = False
        self._counterfactual_llm_calls = 0
        from agents.cognition.communication_strategy import CommunicationStrategyPolicy
        from agents.cognition.configuration import CognitionCommunicationStrategyMode

        message_mode = (
            CognitionCommunicationStrategyMode.DISABLED
            if communication_strategy_mode is None
            else communication_strategy_mode
        )
        if type(message_mode) is not CognitionCommunicationStrategyMode:
            raise TypeError(
                "communication_strategy_mode must be CognitionCommunicationStrategyMode"
            )
        if message_mode is CognitionCommunicationStrategyMode.DISABLED:
            message_policy = None
        elif communication_strategy_policy is None:
            from agents.cognition.communication_strategy import (
                default_communication_strategy_policy,
            )

            message_policy = default_communication_strategy_policy()
        elif type(communication_strategy_policy) is not CommunicationStrategyPolicy:
            raise TypeError(
                "communication_strategy_policy must be CommunicationStrategyPolicy"
            )
        else:
            message_policy = communication_strategy_policy
        self._communication_strategy_mode = message_mode
        self._communication_strategy_policy = message_policy
        from agents.cognition.configuration import CognitionReputationMode
        from agents.cognition.reputation import ReputationFormationPolicy

        reputation = (
            CognitionReputationMode.DISABLED
            if reputation_mode is None
            else reputation_mode
        )
        if type(reputation) is not CognitionReputationMode:
            raise TypeError("reputation_mode must be CognitionReputationMode")
        if reputation is CognitionReputationMode.DISABLED:
            reputation_policy = None
        elif reputation_policy is None:
            from agents.cognition.reputation import default_reputation_policy

            reputation_policy = default_reputation_policy()
        elif type(reputation_policy) is not ReputationFormationPolicy:
            raise TypeError("reputation_policy must be ReputationFormationPolicy")
        self._reputation_mode = reputation
        self._reputation_policy = reputation_policy
        from agents.cognition.configuration import CognitionTerritorialClaimMode
        from agents.cognition.territorial import TerritorialClaimPolicy

        territorial = (
            CognitionTerritorialClaimMode.DISABLED
            if territorial_claim_mode is None
            else territorial_claim_mode
        )
        if type(territorial) is not CognitionTerritorialClaimMode:
            raise TypeError(
                "territorial_claim_mode must be CognitionTerritorialClaimMode"
            )
        if territorial is CognitionTerritorialClaimMode.DISABLED:
            territorial_policy = None
        elif territorial_claim_policy is None:
            from agents.cognition.territorial import default_territorial_claim_policy

            territorial_policy = default_territorial_claim_policy()
        elif type(territorial_claim_policy) is not TerritorialClaimPolicy:
            raise TypeError("territorial_claim_policy must be TerritorialClaimPolicy")
        else:
            territorial_policy = territorial_claim_policy
        self._territorial_claim_mode = territorial
        self._territorial_claim_policy = territorial_policy
        from agents.cognition.configuration import CognitionGroupFormationMode
        from agents.cognition.group_formation import GroupFormationPolicy

        grouped = (
            CognitionGroupFormationMode.DISABLED
            if group_formation_mode is None
            else group_formation_mode
        )
        if type(grouped) is not CognitionGroupFormationMode:
            raise TypeError("group_formation_mode must be CognitionGroupFormationMode")
        if grouped is CognitionGroupFormationMode.DISABLED:
            group_policy = None
        elif group_formation_policy is None:
            from agents.cognition.group_formation import default_group_formation_policy

            group_policy = default_group_formation_policy()
        elif type(group_formation_policy) is not GroupFormationPolicy:
            raise TypeError("group_formation_policy must be GroupFormationPolicy")
        else:
            group_policy = group_formation_policy
        self._group_formation_mode = grouped
        self._group_formation_policy = group_policy
        from agents.cognition.configuration import CognitionSocialNormMode
        from agents.cognition.social_norms import SocialNormPolicy

        normed = (
            CognitionSocialNormMode.DISABLED
            if social_norm_mode is None
            else social_norm_mode
        )
        if type(normed) is not CognitionSocialNormMode:
            raise TypeError("social_norm_mode must be CognitionSocialNormMode")
        if normed is CognitionSocialNormMode.DISABLED:
            norm_policy = None
        elif social_norm_policy is None:
            from agents.cognition.social_norms import default_social_norm_policy

            norm_policy = default_social_norm_policy()
        elif type(social_norm_policy) is not SocialNormPolicy:
            raise TypeError("social_norm_policy must be SocialNormPolicy")
        else:
            norm_policy = social_norm_policy
        self._social_norm_mode = normed
        self._social_norm_policy = norm_policy
        from agents.cognition.configuration import CognitionSocialConventionMode
        from agents.cognition.social_conventions import SocialConventionPolicy

        conventioned = (
            CognitionSocialConventionMode.DISABLED
            if social_convention_mode is None
            else social_convention_mode
        )
        if type(conventioned) is not CognitionSocialConventionMode:
            raise TypeError(
                "social_convention_mode must be CognitionSocialConventionMode"
            )
        if conventioned is CognitionSocialConventionMode.DISABLED:
            convention_policy = None
        elif social_convention_policy is None:
            from agents.cognition.social_conventions import (
                default_social_convention_policy,
            )

            convention_policy = default_social_convention_policy()
        elif type(social_convention_policy) is not SocialConventionPolicy:
            raise TypeError(
                "social_convention_policy must be SocialConventionPolicy"
            )
        else:
            convention_policy = social_convention_policy
        self._social_convention_mode = conventioned
        self._social_convention_policy = convention_policy
        from agents.cognition.artifacts import ArtifactInterpretationMode

        artifact_mode = (
            ArtifactInterpretationMode.DISABLED
            if artifact_interpretation_mode is None
            else artifact_interpretation_mode
        )
        if type(artifact_mode) is not ArtifactInterpretationMode:
            raise TypeError(
                "artifact_interpretation_mode must be ArtifactInterpretationMode"
            )
        self._artifact_interpretation_mode = artifact_mode
        from agents.cognition.configuration import CognitionSemanticNamingMode
        from agents.cognition.semantic_naming import SemanticNamingPolicy

        naming_mode = (
            CognitionSemanticNamingMode.DISABLED
            if semantic_naming_mode is None
            else semantic_naming_mode
        )
        if type(naming_mode) is not CognitionSemanticNamingMode:
            raise TypeError(
                "semantic_naming_mode must be CognitionSemanticNamingMode"
            )
        if naming_mode is CognitionSemanticNamingMode.DISABLED:
            naming_policy = None
        elif semantic_naming_policy is None:
            from agents.cognition.semantic_naming import default_semantic_naming_policy

            naming_policy = default_semantic_naming_policy()
        elif type(semantic_naming_policy) is not SemanticNamingPolicy:
            raise TypeError("semantic_naming_policy must be SemanticNamingPolicy")
        else:
            naming_policy = semantic_naming_policy
        self._semantic_naming_mode = naming_mode
        self._semantic_naming_policy = naming_policy
        from agents.cognition.competence import CompetenceBeliefPolicy
        from agents.cognition.configuration import CognitionSkillLearningMode

        skill_mode = (
            CognitionSkillLearningMode.DISABLED
            if skill_learning_mode is None
            else skill_learning_mode
        )
        if type(skill_mode) is not CognitionSkillLearningMode:
            raise TypeError("skill_learning_mode must be CognitionSkillLearningMode")
        if skill_mode is CognitionSkillLearningMode.DISABLED:
            competence_belief_policy = None
        elif competence_belief_policy is None:
            from agents.cognition.competence import default_competence_belief_policy

            competence_belief_policy = default_competence_belief_policy()
        elif type(competence_belief_policy) is not CompetenceBeliefPolicy:
            raise TypeError("competence_belief_policy must be CompetenceBeliefPolicy")
        self._skill_learning_mode = skill_mode
        self._competence_policy = competence_belief_policy
        from agents.cognition.configuration import CognitionTeachingInteractionMode
        from agents.cognition.teaching import TeachingClaimPolicy

        teaching_mode = (
            CognitionTeachingInteractionMode.DISABLED
            if teaching_interaction_mode is None
            else teaching_interaction_mode
        )
        if type(teaching_mode) is not CognitionTeachingInteractionMode:
            raise TypeError(
                "teaching_interaction_mode must be CognitionTeachingInteractionMode"
            )
        if teaching_mode is CognitionTeachingInteractionMode.DISABLED:
            teaching_policy = None
        elif teaching_claim_policy is None:
            teaching_policy = TeachingClaimPolicy()
        elif type(teaching_claim_policy) is not TeachingClaimPolicy:
            raise TypeError("teaching_claim_policy must be TeachingClaimPolicy")
        else:
            teaching_policy = teaching_claim_policy
        self._teaching_mode = teaching_mode
        self._teaching_policy = teaching_policy
        from agents.cognition.production import ProductionKnowledgeMode

        production_mode = (
            ProductionKnowledgeMode.DISABLED
            if production_knowledge_mode is None
            else production_knowledge_mode
        )
        if type(production_mode) is not ProductionKnowledgeMode:
            raise TypeError("production_knowledge_mode must be ProductionKnowledgeMode")
        self._production_knowledge_mode = production_mode
        if type(production_allow_provider) is not bool:
            raise TypeError("production_allow_provider must be bool")
        self._production_allow_provider = (
            production_allow_provider
            if production_mode is ProductionKnowledgeMode.DETERMINISTIC
            else False
        )
        self._deferred_dissonance: tuple[object, ...] = ()

    def _prepare_reputation(self, loop_input: CognitiveLoopInput) -> object | None:
        from agents.cognition.configuration import CognitionReputationMode
        from agents.cognition.reputation import (
            ReputationLedger,
            apply_reputation_update,
        )

        if self._reputation_mode is not CognitionReputationMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        if snapshot is None or snapshot.social_identity is None:
            return None
        from agents.cognition.communication import project_trust_inputs

        carried = snapshot.reputation
        ledger = carried if type(carried) is ReputationLedger else None
        trust_by_speaker: dict[str, float] = {}
        identity = snapshot.social_identity
        for communication in loop_input.observation.communications:
            speaker = _reputation_agent(identity, communication.speaker_id)
            if speaker is None or speaker.value in trust_by_speaker:
                continue
            profile = next(
                (
                    item
                    for item in snapshot.relationships
                    if getattr(item, "target_id", None) == speaker
                ),
                None,
            )
            if profile is None:
                continue
            trust, _confidence = project_trust_inputs(profile)
            trust_by_speaker[speaker.value] = trust
        for envelope in snapshot.inbox:
            speaker_id = envelope.sender_id
            if speaker_id.value in trust_by_speaker:
                continue
            profile = next(
                (
                    item
                    for item in snapshot.relationships
                    if getattr(item, "target_id", None) == speaker_id
                ),
                None,
            )
            if profile is None:
                continue
            trust, _confidence = project_trust_inputs(profile)
            trust_by_speaker[speaker_id.value] = trust
        return apply_reputation_update(
            owner_id=loop_input.agent_id,
            tick=loop_input.observation.tick,
            observation=loop_input.observation,
            social_identity=identity,
            ledger=ledger,
            policy=self._reputation_policy,
            memories=snapshot.memories,
            source_trust_by_speaker=trust_by_speaker,
            inbox=snapshot.inbox,
        )

    def _prepare_territorial_claims(
        self, loop_input: CognitiveLoopInput
    ) -> object | None:
        from agents.cognition.configuration import CognitionTerritorialClaimMode
        from agents.cognition.territorial import (
            TerritorialClaimLedger,
            apply_territorial_update,
            relationship_projection,
        )

        if (
            self._territorial_claim_mode
            is not CognitionTerritorialClaimMode.DETERMINISTIC
        ):
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.territorial_claims
        ledger = carried if type(carried) is TerritorialClaimLedger else None
        identity = None if snapshot is None else snapshot.social_identity
        trust_by_speaker: dict[str, float] = {}
        if snapshot is not None and identity is not None:
            speakers: list[object] = []
            for communication in loop_input.observation.communications:
                resolved = _reputation_agent(identity, communication.speaker_id)
                if resolved is not None:
                    speakers.append(resolved)
            for envelope in snapshot.inbox:
                speakers.append(envelope.sender_id)
            for speaker in speakers:
                key = getattr(speaker, "value", None)
                if not isinstance(key, str) or key in trust_by_speaker:
                    continue
                profile = next(
                    (
                        item
                        for item in snapshot.relationships
                        if getattr(item, "target_id", None) == speaker
                    ),
                    None,
                )
                trust, _resentment, _fear = relationship_projection(profile)
                trust_by_speaker[key] = trust
        return apply_territorial_update(
            owner_id=loop_input.agent_id,
            tick=loop_input.observation.tick,
            observation=loop_input.observation,
            social_identity=identity,
            ledger=ledger,
            policy=self._territorial_claim_policy,
            memories=() if snapshot is None else snapshot.memories,
            source_trust_by_speaker=trust_by_speaker,
            inbox=() if snapshot is None else snapshot.inbox,
        )

    def _prepare_group_formation(
        self, loop_input: CognitiveLoopInput
    ) -> object | None:
        """Refresh one owner's ledger. Disabled mode does not call the updater."""
        from agents.cognition.configuration import CognitionGroupFormationMode
        from agents.cognition.group_formation import GroupLedger, apply_group_update

        owner_id = loop_input.agent_id.value
        tick = loop_input.observation.tick
        _LOG.debug(
            "group_command_unchanged owner_id=%s tick=%s",
            owner_id,
            tick,
        )
        if self._group_formation_mode is not CognitionGroupFormationMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.group_formation
        ledger = carried if type(carried) is GroupLedger else None
        identity = None if snapshot is None else snapshot.social_identity
        if snapshot is None or identity is None:
            return None
        from agents.cognition.communication import project_trust_inputs

        trust: dict[str, float] = {}
        for profile in snapshot.relationships:
            target = getattr(profile, "target_id", None)
            key = getattr(target, "value", None)
            if not isinstance(key, str) or key in trust:
                continue
            mapped, _confidence = project_trust_inputs(profile)
            trust[key] = mapped
        return apply_group_update(
            loop_input.observation,
            identity,
            trust,
            ledger,
            self._group_formation_policy,
        )

    def _prepare_social_norms(self, loop_input: CognitiveLoopInput) -> object | None:
        """Refresh one owner's norm ledger. Disabled mode leaves it absent."""
        from agents.cognition.configuration import CognitionSocialNormMode
        from agents.cognition.social_norms import NormLedger, apply_norm_update

        owner_id = loop_input.agent_id.value
        tick = loop_input.observation.tick
        if self._social_norm_mode is not CognitionSocialNormMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.social_norms
        ledger = carried if type(carried) is NormLedger else None
        identity = None if snapshot is None else snapshot.social_identity
        if snapshot is None or identity is None:
            _LOG.warning(
                "norm_carry_rejected reason=%s",
                "invalid_type" if snapshot is None else "owner_mismatch",
            )
            return None
        updated = apply_norm_update(
            loop_input.observation,
            identity,
            ledger,
            self._social_norm_policy,
        )
        _LOG.debug(
            "social_norms_carried owner_id=%s belief_count=%s tick=%s",
            owner_id,
            0 if updated is None else len(updated.beliefs),
            tick,
        )
        return updated

    def _prepare_social_conventions(
        self, loop_input: CognitiveLoopInput
    ) -> object | None:
        """Refresh one owner's convention ledger. Disabled mode leaves it absent."""
        from agents.cognition.configuration import CognitionSocialConventionMode
        from agents.cognition.social_conventions import (
            ConventionLedger,
            apply_convention_update,
        )

        owner_id = loop_input.agent_id.value
        tick = loop_input.observation.tick
        if self._social_convention_mode is not (
            CognitionSocialConventionMode.DETERMINISTIC
        ):
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.social_conventions
        ledger = carried if type(carried) is ConventionLedger else None
        identity = None if snapshot is None else snapshot.social_identity
        if snapshot is None or identity is None:
            _LOG.warning(
                "convention_carry_rejected reason=%s",
                "invalid_type" if snapshot is None else "owner_mismatch",
            )
            return None
        memories = () if snapshot is None else snapshot.memories
        updated = apply_convention_update(
            loop_input.observation,
            identity,
            ledger,
            memories=memories,
            policy=self._social_convention_policy,
        )
        _LOG.debug(
            "social_conventions_carried owner_id=%s belief_count=%s tick=%s",
            owner_id,
            0 if updated is None else len(updated.beliefs),
            tick,
        )
        return updated

    def _social_convention_penalties(
        self,
        loop_input: CognitiveLoopInput,
        ledger: object | None,
        futures: object,
    ) -> dict[str, float] | None:
        """Habit bias once futures exist. Disabled callers pass ``None``."""
        from agents.cognition.configuration import CognitionSocialConventionMode
        from agents.cognition.social_conventions import convention_habit_penalties

        if (
            self._social_convention_mode
            is not CognitionSocialConventionMode.DETERMINISTIC
            or ledger is None
        ):
            return None
        penalties = convention_habit_penalties(
            ledger,
            loop_input.observation,
            getattr(futures, "futures", ()),
            mode=self._social_convention_mode,
            policy=self._social_convention_policy,
        )
        mapped = dict(penalties)
        _LOG.debug(
            "convention_penalty_applied future_count=%s",
            len(mapped),
        )
        return mapped

    def _prepare_artifact_interpretations(
        self, loop_input: CognitiveLoopInput
    ) -> object | None:
        """Refresh one owner's artifact readings. Disabled mode leaves it absent."""
        from agents.cognition.artifacts import (
            ArtifactInterpretationLedger,
            ArtifactInterpretationMode,
            apply_artifact_interpretation_update,
        )

        owner_id = loop_input.agent_id
        tick = loop_input.observation.tick
        if self._artifact_interpretation_mode is not (
            ArtifactInterpretationMode.DETERMINISTIC
        ):
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.artifact_interpretations
        ledger = carried if type(carried) is ArtifactInterpretationLedger else None
        updated = apply_artifact_interpretation_update(
            loop_input.observation,
            owner_id,
            ledger,
        )
        _LOG.debug(
            "artifact_interpretations_carried owner_id=%s entry_count=%s tick=%s",
            owner_id.value,
            0 if updated is None else len(updated.interpretations),
            tick,
        )
        return updated


    def _prepare_semantic_naming(
        self,
        loop_input: CognitiveLoopInput,
        *,
        group_formation: object | None = None,
        social_norms: object | None = None,
        social_conventions: object | None = None,
    ) -> object | None:
        """Refresh one owner's terminology ledger. Disabled mode leaves it absent."""
        from agents.cognition.configuration import CognitionSemanticNamingMode
        from agents.cognition.semantic_naming import (
            TerminologyLedger,
            apply_naming_update,
        )

        owner_id = loop_input.agent_id.value
        if self._semantic_naming_mode is not CognitionSemanticNamingMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.semantic_naming
        ledger = carried if type(carried) is TerminologyLedger else None
        identity = None if snapshot is None else snapshot.social_identity
        if snapshot is None or identity is None:
            _LOG.warning(
                "naming_carry_rejected reason=%s",
                "invalid_type" if snapshot is None else "owner_mismatch",
            )
            return None
        cues = _build_naming_cue_summary(
            group_formation=group_formation,
            social_norms=social_norms,
            social_conventions=social_conventions,
        )
        memories = () if snapshot is None else snapshot.memories
        updated = apply_naming_update(
            loop_input.observation,
            identity,
            ledger,
            memories=memories,
            cues=cues,
            policy=self._semantic_naming_policy,
        )
        _LOG.debug(
            "semantic_naming_carried owner_id=%s binding_count=%s",
            owner_id,
            0 if updated is None else len(updated.bindings),
        )
        return updated

    def _naming_communicate_penalties(
        self,
        loop_input: CognitiveLoopInput,
        ledger: object | None,
        futures: object,
    ) -> dict[str, float] | None:
        """Prefer an existing communicate future for a speakable label."""
        from agents.cognition.configuration import CognitionSemanticNamingMode
        from agents.cognition.semantic_naming import naming_communicate_penalties

        if (
            self._semantic_naming_mode
            is not CognitionSemanticNamingMode.DETERMINISTIC
            or ledger is None
        ):
            return None
        penalties = naming_communicate_penalties(
            ledger,
            getattr(futures, "futures", ()),
            tick=loop_input.observation.tick,
            mode=self._semantic_naming_mode,
            policy=self._semantic_naming_policy,
        )
        mapped = dict(penalties)
        _LOG.debug(
            "naming_penalty_applied future_count=%s",
            len(mapped),
        )
        return mapped

    def _artifact_inscribe_penalties(
        self,
        loop_input: CognitiveLoopInput,
        futures: object,
    ) -> dict[str, float] | None:
        """Prefer depositing a note when alone with a communicate future."""
        from agents.cognition.artifacts import (
            ArtifactInterpretationMode,
            artifact_inscribe_penalties,
        )

        if self._artifact_interpretation_mode is not (
            ArtifactInterpretationMode.DETERMINISTIC
        ):
            return None
        snapshot = loop_input.snapshot
        inbox = () if snapshot is None else snapshot.inbox
        penalties = artifact_inscribe_penalties(
            loop_input.observation,
            getattr(futures, "futures", ()),
            mode=self._artifact_interpretation_mode,
            inbox=inbox,
        )
        mapped = dict(penalties)
        _LOG.debug(
            "artifact_inscribe_penalty_applied future_count=%s",
            len(mapped),
        )
        return mapped

    def _social_norm_penalties(
        self,
        loop_input: CognitiveLoopInput,
        ledger: object | None,
        futures: object,
    ) -> tuple[object, dict[str, float]] | None:
        """Select responses once futures exist. Disabled callers pass ``None``."""
        from agents.cognition.configuration import CognitionSocialNormMode
        from agents.cognition.social_norms import norm_response_penalties

        if (
            self._social_norm_mode is not CognitionSocialNormMode.DETERMINISTIC
            or ledger is None
        ):
            return None
        snapshot = loop_input.snapshot
        body = loop_input.observation.self_body
        result = norm_response_penalties(
            ledger,
            loop_input.observation,
            getattr(futures, "futures", ()),
            0.0 if body is None else body.hunger.value,
            0.0 if body is None else body.thirst.value,
            identity=None if snapshot is None else snapshot.social_identity,
            relationships=() if snapshot is None else snapshot.relationships,
            mode=self._social_norm_mode,
        )
        updated = ledger if result.ledger is None else result.ledger
        return updated, result.as_dict()

    def _append_norm_trust(
        self,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
    ) -> tuple[object, ...]:
        """Queue one trust revision when reduced_trust was applied."""
        from agents.cognition.configuration import CognitionSocialNormMode
        from agents.cognition.models import MemoryUpdateIntent, MemoryUpdateKind
        from social.relationships import (
            DEFAULT_RELATIONSHIP_POLICY,
            RelationshipInteractionSignal,
            RelationshipRevisionRequest,
            RelationshipSignalKind,
        )

        if self._social_norm_mode is not CognitionSocialNormMode.DETERMINISTIC:
            return updates
        ledger = proposal.social_norms
        requests = () if ledger is None else getattr(ledger, "trust_requests", ())
        if not requests:
            return updates
        owner = proposal.agent_id
        tick = proposal.loop_input.observation.tick
        extra: list[MemoryUpdateIntent] = []
        for request in requests:
            target = request.target_id
            material = f"{owner.value}|{target.value}|{tick}".encode()
            digest = hashlib.sha256(material).hexdigest()
            signal = RelationshipInteractionSignal(
                counterpart_id=target,
                kind=RelationshipSignalKind.CONTRADICTION_RECEIVED,
                strength=1.0,
                memory_ref=digest,
                lineage_root_ref=digest,
                source_tick=tick,
            )
            extra.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.REVISE_RELATIONSHIP,
                    relationship_revision=RelationshipRevisionRequest(
                        source_id=owner,
                        target_id=target,
                        operation_id=digest,
                        logical_tick=tick,
                        signals=(signal,),
                        policy=DEFAULT_RELATIONSHIP_POLICY.as_ref(),
                    ),
                )
            )
        return updates + tuple(extra)

    def _annotate_claim_violations(
        self,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
    ) -> tuple[object, ...]:
        """Attach ``violated`` only when this tick recorded breach evidence."""
        from agents.cognition.configuration import CognitionTerritorialClaimMode
        from agents.cognition.memory import with_violation_relation
        from agents.cognition.models import MemoryUpdateIntent, MemoryUpdateKind
        from agents.cognition.territorial import ClaimChannel, TerritorialClaimLedger

        if self._territorial_claim_mode is not (
            CognitionTerritorialClaimMode.DETERMINISTIC
        ):
            return updates
        ledger = proposal.territorial_claims
        if type(ledger) is not TerritorialClaimLedger:
            return updates
        observation = proposal.loop_input.observation
        by_event: dict[str, list[object]] = {}
        for claim in ledger.claims:
            for item in claim.evidence:
                if (
                    item.channel is not ClaimChannel.VIOLATION
                    or item.tick != observation.tick
                ):
                    continue
                by_event.setdefault(item.lineage_ref, []).append(claim.target_entity_id)
        if not by_event:
            return updates
        occurrences = {
            occurrence.provenance.source_event_id.value: occurrence.actor_id
            for occurrence in observation.occurrences
            if occurrence.provenance.source_event_id is not None
            and occurrence.actor_id is not None
        }
        annotated: list[object] = []
        for update in updates:
            if (
                type(update) is not MemoryUpdateIntent
                or update.kind is not MemoryUpdateKind.WRITE_MEMORY
                or update.memory is None
            ):
                annotated.append(update)
                continue
            source = update.memory.provenance.observed_source_id
            if source is None or source.value not in by_event:
                annotated.append(update)
                continue
            actor = occurrences.get(source.value)
            if actor is None:
                annotated.append(update)
                continue
            trace = update.memory
            for target in by_event[source.value]:
                trace = with_violation_relation(
                    trace,
                    subject_entity_id=actor,
                    object_entity_id=target,
                )
            annotated.append(
                MemoryUpdateIntent(
                    owner_id=update.owner_id,
                    kind=update.kind,
                    memory=trace,
                )
            )
        return tuple(annotated)

    def _prepare_competence(
        self, loop_input: CognitiveLoopInput, memory: object
    ) -> object | None:
        from agents.cognition.competence import (
            empty_competence_model,
            update_competence,
        )
        from agents.cognition.configuration import CognitionSkillLearningMode

        if self._skill_learning_mode is not CognitionSkillLearningMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.competence_model
        model = (
            carried
            if type(carried).__name__ == "CompetenceSelfModel"
            else empty_competence_model(loop_input.agent_id)
        )
        reconstructions = tuple(getattr(memory, "reconstructions", ()))
        return update_competence(
            model,
            loop_input.observation,
            reconstructions,
            self._competence_policy,
        )

    def _prepare_recipe_beliefs(self, loop_input: CognitiveLoopInput) -> object | None:
        from agents.cognition.production import (
            ProductionKnowledgeMode,
            update_recipe_beliefs,
        )

        if self._production_knowledge_mode is not ProductionKnowledgeMode.DETERMINISTIC:
            return None
        snapshot = loop_input.snapshot
        carried = (
            None if snapshot is None else getattr(snapshot, "recipe_beliefs", None)
        )
        return update_recipe_beliefs(
            carried,
            owner_id=loop_input.agent_id,
            observation=loop_input.observation,
        )

    def _prepare_teaching(
        self, loop_input: CognitiveLoopInput, competence: object | None
    ) -> tuple[object | None, object | None]:
        from agents.cognition.competence import empty_competence_model
        from agents.cognition.configuration import CognitionTeachingInteractionMode
        from agents.cognition.teaching import (
            AdviceStore,
            apply_teaching_belief,
            empty_advice_store,
            record_teaching,
        )

        if self._teaching_mode is not CognitionTeachingInteractionMode.DETERMINISTIC:
            return competence, None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.declarative_advice
        owner = loop_input.agent_id
        advice = (
            carried
            if type(carried) is AdviceStore and carried.owner_id == owner
            else empty_advice_store(owner)
        )
        identity = None if snapshot is None else snapshot.social_identity
        relationships = () if snapshot is None else snapshot.relationships
        updated_advice = record_teaching(
            advice,
            loop_input.observation,
            relationships,
            self._teaching_policy,
            identity,
        )
        prior_ids = {row.occurrence_id for row in advice.rows}
        delta = tuple(
            row for row in updated_advice.rows if row.occurrence_id not in prior_ids
        )
        model = competence if competence is not None else empty_competence_model(owner)
        updated_model = apply_teaching_belief(
            model,
            delta,
            self._teaching_policy,
            relationships,
        )
        return updated_model, updated_advice

    def _prepare_world_model(
        self,
        loop_input: CognitiveLoopInput,
        emotional_evaluation: EmotionalStateEvaluation,
        memory: RetrievedMemoryContext,
    ) -> object | None:
        from agents.cognition.configuration import CognitionWorldModelMode
        from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
        from agents.cognition.world_model import (
            CausalWorldModel,
            empty_world_model,
            episodes_from_observation,
            episodes_from_reconstructions,
            update_world_model,
        )

        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        mode = self._world_model_mode
        if mode is not CognitionWorldModelMode.ENABLED:
            _LOG.debug(
                "world_model_prepare owner_id=%s tick=%s mode=%s hypothesis_count=%s",
                owner.value,
                tick,
                mode.value,
                0,
            )
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.causal_world_model
        prior = (
            carried if type(carried) is CausalWorldModel else empty_world_model(owner)
        )
        policy = self._world_model_policy
        if policy is None:
            from agents.cognition.world_model import default_world_model_policy

            policy = default_world_model_policy(allow_provider=False)
        emotion = None
        if type(self._emotional_state) is not PassthroughEmotionalStateAppraiser:
            emotion = emotional_evaluation.state
        health = None
        body = loop_input.observation.self_body
        if body is not None:
            health = body.health.value
        observed = episodes_from_observation(loop_input.observation, owner, prior)
        recalled = episodes_from_reconstructions(
            memory,
            owner_id=owner,
            observer_id=loop_input.observation.observer_id,
            used_provenance_ids=tuple(episode.evidence_id for episode in observed),
        )
        episodes = observed + tuple(replace(episode, tick=tick) for episode in recalled)
        updated = update_world_model(
            prior,
            episodes,
            policy,
            tick=tick,
            observed_health=health,
            emotional_state=emotion,
        )
        _LOG.debug(
            "world_model_prepare owner_id=%s tick=%s mode=%s hypothesis_count=%s",
            owner.value,
            tick,
            mode.value,
            len(updated.hypotheses),
        )
        return updated

    def _prepare_theory_of_mind(
        self,
        loop_input: CognitiveLoopInput,
        emotional_evaluation: EmotionalStateEvaluation,
        memory: RetrievedMemoryContext,
    ) -> object | None:
        from agents.cognition.configuration import CognitionTheoryOfMindMode
        from agents.cognition.theory_of_mind import (
            TheoryOfMind,
            cues_from_observation,
            cues_from_reconstructions,
            default_theory_of_mind_policy,
            empty_theory_of_mind,
            update_theory_of_mind,
        )

        owner = loop_input.agent_id
        tick = loop_input.observation.tick
        mode = self._theory_of_mind_mode
        if mode is not CognitionTheoryOfMindMode.ENABLED:
            _LOG.debug(
                "theory_of_mind_prepare owner_id=%s tick=%s mode=%s "
                "hypothesis_count=%s",
                owner.value,
                tick,
                mode.value,
                0,
            )
            _LOG.debug(
                "epistemic_prepare_skipped owner_id=%s tick=%s status=passthrough",
                owner.value,
                tick,
            )
            return None
        snapshot = loop_input.snapshot
        carried = None if snapshot is None else snapshot.theory_of_mind
        prior = (
            carried if type(carried) is TheoryOfMind else empty_theory_of_mind(owner)
        )
        policy = self._theory_of_mind_policy
        if policy is None:
            policy = default_theory_of_mind_policy(allow_provider=False)
        intensity = None
        state = emotional_evaluation.state
        if state is not None:
            intensity = state.max_intensity()
        profiles = () if snapshot is None else snapshot.relationships
        observed = cues_from_observation(
            loop_input.observation,
            owner_id=owner,
            profiles=profiles,
            cue_cursor=prior.cue_cursor,
            owner_emotion_intensity=intensity,
            model=prior,
            policy=policy,
        )
        used = tuple(
            cue.evidence_id
            for cue in observed
            if cue.drop_code is None and cue.evidence_id
        )
        recalled = cues_from_reconstructions(
            memory,
            owner_id=owner,
            observer_id=loop_input.observation.observer_id,
            used_provenance_ids=used,
            policy=policy,
        )
        updated = update_theory_of_mind(
            prior,
            observed + recalled,
            policy,
            owner_entity_id=loop_input.observation.observer_id,
        )
        _LOG.debug(
            "theory_of_mind_prepare owner_id=%s tick=%s mode=%s hypothesis_count=%s",
            owner.value,
            tick,
            mode.value,
            len(updated.hypotheses),
        )
        from agents.cognition.epistemic import (
            default_epistemic_policy,
            update_epistemic_state,
        )

        epistemic = self._epistemic_policy
        if epistemic is None:
            epistemic = default_epistemic_policy()
        beliefs = memory.semantic_beliefs
        if not beliefs and snapshot is not None:
            beliefs = snapshot.semantic_beliefs
        if epistemic.max_depth == 0:
            _LOG.debug(
                "epistemic_prepare_skipped owner_id=%s tick=%s status=depth_zero",
                owner.value,
                tick,
            )
            return updated
        updated = update_epistemic_state(
            updated,
            loop_input.observation,
            beliefs,
            epistemic,
        )
        _LOG.debug(
            "epistemic_prepare owner_id=%s tick=%s mode=%s max_depth=%s "
            "attribution_count=%s",
            owner.value,
            tick,
            mode.value,
            epistemic.max_depth,
            len(updated.attributions),
        )
        return updated

    async def prepare(
        self,
        loop_input: CognitiveLoopInput,
        *,
        invocation_id: str,
        remembered_decisions: tuple[object, ...] = (),
    ) -> CognitiveLoopProposal:
        """Run perception through planning without memory updates or next state."""
        if type(loop_input) is not CognitiveLoopInput:
            raise TypeError("CognitiveLoop.prepare requires CognitiveLoopInput")
        if not isinstance(invocation_id, str) or not invocation_id.strip():
            raise ValueError("invocation_id must be a non-blank str")

        records: list[ComponentBoundaryRecord] = []
        agent_id = loop_input.agent_id.value
        fail = self._make_fail(
            records=records, invocation_id=invocation_id, agent_id=agent_id
        )
        run_stage = self._make_run_stage(
            loop_input=loop_input,
            records=records,
            invocation_id=invocation_id,
            agent_id=agent_id,
            fail=fail,
        )

        perception = await run_stage(
            kind=ComponentKind.PERCEPTION,
            ordinal=0,
            input_artifact=loop_input,
            awaitable=self._perception.interpret(loop_input),
            expected_type=InterpretedPerception,
        )
        memory = await run_stage(
            kind=ComponentKind.MEMORY_RETRIEVAL,
            ordinal=1,
            input_artifact=perception,
            awaitable=self._memory.retrieve(loop_input, perception),
            expected_type=RetrievedMemoryContext,
        )
        situation = await run_stage(
            kind=ComponentKind.SITUATION,
            ordinal=2,
            input_artifact=memory,
            awaitable=self._situation.model(loop_input, perception, memory),
            expected_type=SituationModel,
        )
        self_state = await run_stage(
            kind=ComponentKind.SELF_STATE,
            ordinal=3,
            input_artifact=situation,
            awaitable=self._self_state.project(loop_input, situation, memory),
            expected_type=SelfModel,
        )
        goal_board = await run_stage(
            kind=ComponentKind.GOAL_MANAGEMENT,
            ordinal=4,
            input_artifact=self_state,
            awaitable=self._goal_manager.manage(
                loop_input, situation, self_state, memory
            ),
            expected_type=GoalBoard,
        )
        considered, skipped = self._consider(
            loop_input,
            remembered_decisions,
            memory=memory,
            goal_board=goal_board,
            self_model=self_state,
        )
        self._counterfactual_skipped = skipped
        self._last_counterfactual_scenarios = await self._rank_counterfactuals(
            loop_input, considered
        )
        from agents.cognition.counterfactual import counterfactual_state_for

        self._counterfactual_state = counterfactual_state_for(
            self._last_counterfactual_scenarios  # type: ignore[arg-type]
        )
        prior_emotion = None
        if loop_input.snapshot is not None:
            prior_emotion = loop_input.snapshot.emotional_state
        emotional_evaluation = await run_stage(
            kind=ComponentKind.EMOTIONAL_STATE,
            ordinal=5,
            input_artifact=goal_board,
            awaitable=self._emotional_state.appraise(
                loop_input,
                perception,
                situation,
                memory,
                self_state,
                goal_board,
                prior_emotion,
                counterfactual_scenarios=self._last_counterfactual_scenarios,
            ),
            expected_type=EmotionalStateEvaluation,
        )
        world_model = self._prepare_world_model(
            loop_input, emotional_evaluation, memory
        )
        mind = self._prepare_theory_of_mind(loop_input, emotional_evaluation, memory)
        reputation = self._prepare_reputation(loop_input)
        territorial_claims = self._prepare_territorial_claims(loop_input)
        group_formation = self._prepare_group_formation(loop_input)
        social_norms = self._prepare_social_norms(loop_input)
        social_conventions = self._prepare_social_conventions(loop_input)
        artifact_interpretations = self._prepare_artifact_interpretations(loop_input)
        semantic_naming = self._prepare_semantic_naming(
            loop_input,
            group_formation=group_formation,
            social_norms=social_norms,
            social_conventions=social_conventions,
        )
        competence = self._prepare_competence(loop_input, memory)
        competence, advice = self._prepare_teaching(loop_input, competence)
        recipe_beliefs = self._prepare_recipe_beliefs(loop_input)
        production_recipe_id = None
        if recipe_beliefs is not None and self._production_allow_provider:
            from agents.cognition.production_selection import select_production_recipe

            selection = await select_production_recipe(
                recipe_beliefs,
                allow_provider=True,
                provider=self._world_model_provider,
                tick=loop_input.observation.tick,
            )
            if selection.recipe_id is not None and not selection.fallback_used:
                production_recipe_id = selection.recipe_id
        competence_policy = self._competence_policy
        if (
            competence is not None
            and competence_policy is not None
            and competence_policy.allow_provider
        ):
            from agents.cognition.competence_selection import select_competence_domains

            competence = await select_competence_domains(
                competence,
                competence_policy,
                provider=self._world_model_provider,
                tick=loop_input.observation.tick,
            )
        teaching_selection = None
        claim_policy = self._teaching_policy
        if (
            claim_policy is not None
            and claim_policy.allow_provider
            and competence is not None
        ):
            from agents.cognition.teaching_selection import select_teaching_act

            chosen_act = await select_teaching_act(
                competence,
                claim_policy,
                provider=self._world_model_provider,
                tick=loop_input.observation.tick,
                observation=loop_input.observation,
            )
            if chosen_act is not None and not chosen_act.fallback_used:
                teaching_selection = (chosen_act.act, chosen_act.domain)
        policy = self._world_model_policy
        if world_model is not None and policy is not None and policy.allow_provider:
            from agents.cognition.world_model_selection import (
                select_world_model_hypotheses,
            )

            world_model = await select_world_model_hypotheses(
                world_model,
                policy,
                provider=self._world_model_provider,
                tick=loop_input.observation.tick,
            )
        mind_policy = self._theory_of_mind_policy
        if mind is not None and mind_policy is not None and mind_policy.allow_provider:
            from agents.cognition.theory_of_mind_selection import (
                select_theory_of_mind_hypotheses,
            )

            mind = await select_theory_of_mind_hypotheses(
                mind,
                mind_policy,
                provider=self._world_model_provider,
                tick=loop_input.observation.tick,
            )
        futures = await run_stage(
            kind=ComponentKind.FUTURES,
            ordinal=6,
            input_artifact=emotional_evaluation,
            awaitable=self._futures.imagine(
                loop_input,
                situation,
                self_state,
                memory,
                goal_board,
                emotional_evaluation,
                causal_world_model=world_model,
                theory_of_mind=mind,
                prospective_policy=self._prospective_policy,
                llm_provider=self._world_model_provider,
            ),
            expected_type=PossibleFutures,
        )
        motivation = await run_stage(
            kind=ComponentKind.MOTIVATION,
            ordinal=7,
            input_artifact=futures,
            awaitable=self._motivation.evaluate(
                loop_input,
                situation,
                self_state,
                futures,
                goal_board,
                emotional_evaluation,
                causal_world_model=world_model,
                theory_of_mind=mind,
            ),
            expected_type=MotivationEvaluation,
        )
        norm_penalties = self._social_norm_penalties(loop_input, social_norms, futures)
        if norm_penalties is not None:
            social_norms = norm_penalties[0]
            norm_penalty_map = norm_penalties[1]
        else:
            norm_penalty_map = None
        convention_penalty_map = self._social_convention_penalties(
            loop_input, social_conventions, futures
        )
        artifact_penalty_map = self._artifact_inscribe_penalties(loop_input, futures)
        naming_penalty_map = self._naming_communicate_penalties(
            loop_input, semantic_naming, futures
        )
        intention = await run_stage(
            kind=ComponentKind.INTENTION,
            ordinal=8,
            input_artifact=motivation,
            awaitable=self._intention.select(
                loop_input,
                motivation,
                futures,
                goal_board,
                emotional_evaluation,
                self_state,
                causal_world_model=world_model,
                theory_of_mind=mind,
                **_planner_options(
                    self._intention.select,
                    counterfactual_bias=self._counterfactual_bias(loop_input, futures),
                    competence_policy=self._competence_policy,
                    competence_model=competence,
                    teaching_policy=self._teaching_policy,
                    territorial_claims=territorial_claims,
                    territorial_claim_mode=self._territorial_claim_mode,
                    social_norms=social_norms,
                    social_norm_mode=self._social_norm_mode,
                    norm_penalties=norm_penalty_map,
                    social_conventions=social_conventions,
                    social_convention_mode=self._social_convention_mode,
                    convention_penalties=convention_penalty_map,
                    artifact_interpretations=artifact_interpretations,
                    artifact_interpretation_mode=self._artifact_interpretation_mode,
                    artifact_penalties=artifact_penalty_map,
                    semantic_naming=semantic_naming,
                    semantic_naming_mode=self._semantic_naming_mode,
                    naming_penalties=naming_penalty_map,
                ),
            ),
            expected_type=SelectedIntention,
        )
        plan = await run_stage(
            kind=ComponentKind.PLANNING,
            ordinal=9,
            input_artifact=intention,
            awaitable=self._planner.plan(
                loop_input,
                intention,
                futures,
                memory,
                goal_board,
                emotional_evaluation,
                **_planner_options(
                    self._planner.plan,
                    causal_world_model=world_model,
                    theory_of_mind=mind,
                    self_model=self_state,
                    strategy_mode=self._communication_strategy_mode,
                    strategy_policy=self._communication_strategy_policy,
                    reputation=reputation,
                    reputation_mode=self._reputation_mode,
                    reputation_policy=self._reputation_policy,
                    competence_model=competence,
                    teaching_mode=self._teaching_mode,
                    teaching_policy=self._teaching_policy,
                    teaching_selection=teaching_selection,
                    recipe_beliefs=recipe_beliefs,
                    selected_recipe_id=production_recipe_id,
                    territorial_claims=territorial_claims,
                    territorial_claim_mode=self._territorial_claim_mode,
                    social_norms=social_norms,
                    social_norm_mode=self._social_norm_mode,
                    social_conventions=social_conventions,
                    social_convention_mode=self._social_convention_mode,
                    artifact_interpretations=artifact_interpretations,
                    artifact_interpretation_mode=self._artifact_interpretation_mode,
                    semantic_naming=semantic_naming,
                    semantic_naming_mode=self._semantic_naming_mode,
                ),
            ),
            expected_type=ActionPlan,
        )
        try:
            command = require_agent_command(plan.command)
        except TypeError:
            fail(
                reason=CognitionFailureReason.COMMAND_REJECTED,
                kind=ComponentKind.PLANNING,
                ordinal=9,
                input_artifact=intention,
            )
            raise  # pragma: no cover

        proposal = CognitiveLoopProposal(
            invocation_id=invocation_id,
            agent_id=loop_input.agent_id,
            loop_input=loop_input,
            perception=perception,
            memory=memory,
            situation=situation,
            self_state=self_state,
            goal_board=goal_board,
            emotional_state=emotional_evaluation,
            futures=futures,
            motivation=motivation,
            intention=intention,
            plan=plan,
            proposed_command=command,
            boundary_records=tuple(records),
            final_confidence=plan.confidence,
            causal_world_model=world_model,
            theory_of_mind=mind,
            reputation=reputation,
            territorial_claims=territorial_claims,
            group_formation=group_formation,
            social_norms=social_norms,
            social_conventions=social_conventions,
            artifact_interpretations=artifact_interpretations,
            semantic_naming=semantic_naming,
            competence_model=competence,
            declarative_advice=advice,
            recipe_beliefs=recipe_beliefs,
            communication_intent=plan.communication_intent,
            communication_intent_audit=plan.communication_intent_audit,
        )
        _LOG.debug(
            "cognitive_loop_prepared",
            extra={
                "cognition": {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "boundary_count": len(records),
                    "final_confidence": plan.confidence,
                    "command_type": type(command).__name__,
                    "goal_count": len(goal_board.goals),
                    "status": "prepared",
                }
            },
        )
        return proposal

    async def complete(
        self,
        proposal: CognitiveLoopProposal,
        *,
        effective_command: AgentCommand,
        reflection_cursor: object | None = None,
        decision_journal: tuple[object, ...] | None = None,
    ) -> CognitiveLoopResult:
        """Bind the effective command and complete memory-update / next state.

        ``effective_command`` may differ from ``proposal.proposed_command`` after
        trusted intervention. Memory hooks and ``last_command_kind`` always use
        the effective command, never a suppressed proposal.
        """
        if type(proposal) is not CognitiveLoopProposal:
            raise TypeError("complete requires CognitiveLoopProposal")
        command = require_agent_command(effective_command)
        records = list(proposal.boundary_records)
        loop_input = proposal.loop_input
        agent_id = loop_input.agent_id.value
        invocation_id = proposal.invocation_id
        fail = self._make_fail(
            records=records, invocation_id=invocation_id, agent_id=agent_id
        )
        run_stage = self._make_run_stage(
            loop_input=loop_input,
            records=records,
            invocation_id=invocation_id,
            agent_id=agent_id,
            fail=fail,
        )

        effective_plan = ActionPlan(
            owner_id=proposal.plan.owner_id,
            command=command,
            confidence=proposal.plan.confidence,
            decision_metadata=proposal.plan.decision_metadata,
            communication_intent=proposal.plan.communication_intent,
            communication_intent_audit=proposal.plan.communication_intent_audit,
        )
        updates = await run_stage(
            kind=ComponentKind.MEMORY_UPDATE,
            ordinal=10,
            input_artifact=effective_plan,
            awaitable=self._memory_updates.propose_updates(
                loop_input,
                effective_plan,
                proposal.perception,
                proposal.memory,
                proposal.intention,
                proposal.self_state,
            ),
            expected_type=tuple,
        )
        assert type(updates) is tuple
        updates = self._annotate_claim_violations(proposal, updates)
        updates = self._append_norm_trust(proposal, updates)
        consolidation = await self._plan_sleep_consolidation(
            proposal=proposal,
            command=command,
            updates=updates,
        )
        reflection = await self._plan_reflection(
            proposal=proposal,
            updates=updates,
            consolidation=consolidation,
            reflection_cursor=reflection_cursor,
            decision_journal=decision_journal,
        )
        identity_revisions, identity_dissonance = self._identity_revisions(
            proposal=proposal,
            updates=updates,
            consolidation=consolidation,
            reflection=reflection,
            command=command,
        )
        updates, identity_revisions = self._merge_counterfactual_conclusions(
            proposal=proposal,
            updates=updates,
            identity_revisions=identity_revisions,
        )

        next_state = InternalAgentState(
            owner_id=loop_input.agent_id,
            invocation_count=loop_input.internal_state.invocation_count + 1,
            last_intention=(
                proposal.intention.intention
                if type(proposal.intention.intention) is IntentionCode
                else None
            ),
            last_command_kind=type(command).__name__.lower(),
        )
        pending_accesses = proposal.memory.pending_accesses
        if consolidation is not None:
            from memory.models import MemoryAccessReceipt

            stored_ids = {
                trace.memory_id for trace in proposal.loop_input.snapshot.memories
            }
            pending_accesses = pending_accesses + tuple(
                MemoryAccessReceipt(
                    memory_id=memory_id,
                    access_tick=consolidation.audit.tick,
                    operation_id=(
                        f"offline-consolidation:{consolidation.audit.tick}:"
                        f"{memory_id.value}"
                    ),
                )
                for memory_id in consolidation.selection.strengthen_ids
                if memory_id in stored_ids
            )
        result = CognitiveLoopResult(
            invocation_id=invocation_id,
            agent_id=loop_input.agent_id,
            command=command,
            boundary_records=tuple(records),
            memory_update_intents=updates,
            final_confidence=proposal.final_confidence,
            internal_state=next_state,
            pending_accesses=pending_accesses,
            pending_reconsolidation=proposal.memory.reconsolidation,
            pending_semanticization=proposal.memory.pending_semanticization,
            offline_consolidation=consolidation,
            reflection=reflection,
            identity_revisions=identity_revisions,
            identity_dissonance=identity_dissonance,
            causal_world_model=proposal.causal_world_model,
            theory_of_mind=proposal.theory_of_mind,
            reputation=proposal.reputation,
            territorial_claims=proposal.territorial_claims,
            group_formation=proposal.group_formation,
            social_norms=proposal.social_norms,
            social_conventions=proposal.social_conventions,
            artifact_interpretations=proposal.artifact_interpretations,
            semantic_naming=proposal.semantic_naming,
            competence_model=proposal.competence_model,
            declarative_advice=proposal.declarative_advice,
            recipe_beliefs=proposal.recipe_beliefs,
            territorial_audits=getattr(proposal.plan, "territorial_audits", None),
            communication_intent=proposal.communication_intent,
            communication_intent_audit=proposal.communication_intent_audit,
        )
        _LOG.debug(
            "cognitive_loop_complete",
            extra={
                "cognition": {
                    "invocation_id": invocation_id,
                    "agent_id": agent_id,
                    "boundary_count": len(records),
                    "memory_update_count": len(updates),
                    "pending_access_count": len(proposal.memory.pending_accesses),
                    "reconstruction_count": len(proposal.memory.reconstructions),
                    "pending_write_count": 1 if proposal.memory.reconsolidation else 0,
                    "semanticization_pending": (
                        proposal.memory.pending_semanticization is not None
                    ),
                    "final_confidence": proposal.final_confidence,
                    "command_type": type(command).__name__,
                    "effective_matches_proposal": command == proposal.proposed_command,
                    "status": "completed",
                }
            },
        )
        _ = _STAGE_ORDER
        return result

    def _identity_revisions(
        self,
        *,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
        consolidation: object | None,
        reflection: object | None,
        command: object,
    ) -> tuple[tuple[object, ...], tuple[object, ...]]:
        from agents.cognition.configuration import CognitionIdentityMode
        from agents.cognition.identity import (
            appraise_identity,
            detect_identity_dissonance,
            parse_identity_predicate,
            without_overlapping_identity_requests,
        )
        from social.relationships import DirectedRelationshipProfile

        if self._identity_mode is not CognitionIdentityMode.ENABLED:
            return (), ()
        snapshot = proposal.loop_input.snapshot
        memories = list(_tick_memories(proposal, updates))
        relationships = (
            ()
            if snapshot is None
            else tuple(
                item
                for item in snapshot.relationships
                if type(item) is DirectedRelationshipProfile
            )
        )
        beliefs = () if snapshot is None else snapshot.semantic_beliefs
        appraisal = appraise_identity(
            owner_id=proposal.agent_id,
            tick=proposal.loop_input.observation.tick,
            memories=tuple(memories),
            occurrences=proposal.loop_input.observation.occurrences,
            goals=proposal.goal_board.goals,
            relationships=relationships,
            futures=proposal.futures,
            beliefs=beliefs,
            self_model=proposal.self_state,
        )
        kept = without_overlapping_identity_requests(
            appraisal.requests,
            consolidation=consolidation,
            reflection=reflection,
        )
        aspect_counts: dict[str, int] = {}
        for request in kept:
            aspect, _provenance, _token = parse_identity_predicate(
                request.claim.predicate
            )
            aspect_counts[aspect.value] = aspect_counts.get(aspect.value, 0) + 1
        _LOG.debug(
            "identity_pending",
            extra={
                "request_count": len(kept),
                "aspect_counts": aspect_counts,
            },
        )
        selected_future_id = getattr(proposal.intention, "selected_future_id", None)
        dissonance = detect_identity_dissonance(
            owner_id=proposal.agent_id,
            tick=proposal.loop_input.observation.tick,
            command=command,
            goals=proposal.goal_board.goals,
            futures=proposal.futures,
            identity=proposal.self_state.identity,
            memories=tuple(memories),
            selected_future_id=(
                selected_future_id if type(selected_future_id) is str else None
            ),
            deferred=self._deferred_dissonance,  # type: ignore[arg-type]
        )
        self._deferred_dissonance = dissonance.deferred
        combined = without_overlapping_identity_requests(
            (*kept, *dissonance.requests),
            consolidation=consolidation,
            reflection=reflection,
        )
        return combined, dissonance.notices

    async def _plan_reflection(
        self,
        *,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
        consolidation: object | None,
        reflection_cursor: object | None,
        decision_journal: tuple[object, ...] | None,
    ) -> object | None:
        from agents.cognition.configuration import CognitionReflectionMode
        from agents.cognition.models import EmotionDriverCode, MemoryUpdateKind
        from agents.cognition.reflection import (
            LLMReflectionSelector,
            ReflectionContext,
            ReflectionCursor,
            ReflectionEngine,
            ReflectionTriggerInput,
            SubjectiveDecisionRecord,
            _drop_consolidation_overlaps,
            default_reflection_policy,
            drop_unprovenanced_candidates,
            log_reflection_aborted,
            materialize_reflection_candidates,
            plan_reflection,
        )
        from agents.models import GoalId, GoalStatus
        from memory.models import MemoryTrace
        from social.relationships import DirectedRelationshipProfile

        mode = self._reflection_mode
        if mode is CognitionReflectionMode.DISABLED:
            return None
        owner = proposal.agent_id
        observation = proposal.loop_input.observation
        tick = observation.tick
        if type(proposal.self_state) is not SelfModel:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="invalid_type"
            )
            return None
        snapshot = proposal.loop_input.snapshot
        if snapshot is None or snapshot.owner_id != owner:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="snapshot_missing"
            )
            return None
        policy = self._reflection_policy
        if policy is None:
            policy = default_reflection_policy(
                allow_provider=mode is CognitionReflectionMode.LLM_ASSISTED
            )
        cursor = reflection_cursor
        if cursor is None:
            cursor = ReflectionCursor(owner_id=owner)
        if type(cursor) is not ReflectionCursor:
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="invalid_type"
            )
            return None
        journal_items = () if decision_journal is None else decision_journal
        journal: list[SubjectiveDecisionRecord] = []
        for record in journal_items:
            if type(record) is not SubjectiveDecisionRecord:
                log_reflection_aborted(
                    owner_id=owner.value, tick=tick, reason_code="invalid_type"
                )
                return None
            if record.tick == tick and record.outcome_code.value == "unknown":
                continue
            journal.append(record)
        evaluation = proposal.emotional_state
        intensity = None
        if EmotionDriverCode.PASSTHROUGH not in evaluation.driver_codes:
            intensity = evaluation.state.max_intensity()
        occurrence_kinds = tuple(item.kind for item in observation.occurrences)
        failures = sum(
            1
            for item in observation.occurrences
            if item.actor_id == observation.observer_id and item.success is False
        )
        horizons = set(policy.major_goal_horizons)
        completed: list[GoalId] = []
        for goal in snapshot.goals:
            if goal.status is not GoalStatus.COMPLETED:
                continue
            if goal.horizon not in horizons:
                continue
            completed.append(goal.goal_id)
        masses = tuple(
            belief.confidence.contradiction_mass for belief in snapshot.semantic_beliefs
        )
        counts = tuple(
            belief.evidence_contradiction_count for belief in snapshot.semantic_beliefs
        )
        ordinals: list[tuple[str, str, int]] = []
        cited: list[str] = []
        for profile in snapshot.relationships:
            if type(profile) is not DirectedRelationshipProfile:
                continue
            if profile.source_id != owner:
                continue
            ordinals.append(
                (
                    profile.source_id.value,
                    profile.target_id.value,
                    profile.revision_ordinal,
                )
            )
            for dimension in profile.dimensions:
                for evidence in dimension.evidence:
                    cited.append(evidence.memory_ref)
        memories = list(snapshot.memories)
        for intent in updates:
            if (
                type(intent) is MemoryUpdateIntent
                and intent.kind is MemoryUpdateKind.WRITE_MEMORY
                and type(intent.memory) is MemoryTrace
            ):
                memories.append(intent.memory)
        try:
            matched = ReflectionEngine().triggers(
                ReflectionTriggerInput(
                    owner_id=owner,
                    tick=tick,
                    policy=policy,
                    cursor=cursor,
                    mode=mode.value,
                    occurrence_kinds=occurrence_kinds,
                    emotion_max_intensity=intensity,
                    journal=tuple(journal),
                    observation_owner_failures=failures,
                    completed_goal_ids=tuple(completed),
                    contradiction_masses=masses,
                    contradiction_counts=counts,
                    relationship_ordinals=tuple(ordinals),
                )
            )
            if not matched.matched:
                return None
            from agents.cognition.configuration import CognitionIdentityMode
            from agents.cognition.identity import (
                IdentityState,
                reflection_cue_memory_ids,
            )

            identity = proposal.self_state.identity
            if (
                self._identity_mode is CognitionIdentityMode.ENABLED
                and type(identity) is IdentityState
            ):
                cues = reflection_cue_memory_ids(identity)
                cited.extend(cues)
                known = {trace.memory_id.value for trace in memories}
                preferred = sum(1 for item in dict.fromkeys(cues) if item in known)
                remaining = policy.max_memories - min(preferred, policy.max_memories)
                _LOG.debug(
                    "identity_reflection_cue",
                    extra={
                        "owner_id": owner.value,
                        "tick": tick,
                        "preferred_count": preferred,
                        "remaining_cap": remaining,
                    },
                )
            context = ReflectionContext(
                owner_id=owner,
                tick=tick,
                policy=policy,
                memories=tuple(memories),
                beliefs=snapshot.semantic_beliefs,
                goals=snapshot.goals,
                decisions=tuple(journal),
                owner_entity_id=observation.observer_id,
                cited_memory_ids=tuple(dict.fromkeys(cited)),
            )
            candidates = _drop_consolidation_overlaps(
                drop_unprovenanced_candidates(
                    context, materialize_reflection_candidates(context)
                ),
                consolidation,
            )
            selected_ids = None
            fallback_used = False
            if mode is CognitionReflectionMode.LLM_ASSISTED:
                selector = self._reflection_selector
                if type(selector) is not LLMReflectionSelector:
                    selector = LLMReflectionSelector(None)
                selected_ids, fallback_used = await selector.select(
                    candidates,
                    policy=policy,
                    owner_id=owner,
                    tick=tick,
                )
            return plan_reflection(
                context=context,
                triggers=matched,
                mode=mode.value,
                consolidation=consolidation,
                acknowledged_goal_ids=tuple(completed),
                selected_ids=selected_ids,
                fallback_used=fallback_used,
                causal_world_model=proposal.causal_world_model,
            )
        except (TypeError, ValueError):
            log_reflection_aborted(
                owner_id=owner.value, tick=tick, reason_code="schema_invalid"
            )
            return None

    async def _plan_sleep_consolidation(
        self,
        *,
        proposal: CognitiveLoopProposal,
        command: AgentCommand,
        updates: tuple[object, ...],
    ) -> object | None:
        from agents.cognition.configuration import CognitionConsolidationMode
        from agents.cognition.consolidation import orchestrate_offline_consolidation
        from agents.cognition.models import MemoryUpdateIntent, MemoryUpdateKind
        from memory.models import OfflineConsolidationPolicy
        from world.actions import Sleep
        from world.models import LifeStatus

        mode = self._consolidation_mode
        terminal = proposal.perception.life_status is LifeStatus.DEAD
        is_sleep = type(command) is Sleep
        if mode is CognitionConsolidationMode.DISABLED or not is_sleep or terminal:
            if is_sleep or mode is not CognitionConsolidationMode.DISABLED:
                if mode is CognitionConsolidationMode.DISABLED:
                    reason = "disabled"
                elif terminal and is_sleep:
                    reason = "terminal"
                else:
                    reason = "not_sleep"
                _LOG.info(
                    "offline_consolidation_skipped reason=%s agent_id=%s tick=%s",
                    reason,
                    proposal.agent_id.value,
                    proposal.loop_input.observation.tick,
                )
            return None
        snapshot = proposal.loop_input.snapshot
        if snapshot is None:
            _LOG.error(
                "offline_consolidation_aborted agent_id=%s tick=%s "
                "reason_code=snapshot_missing",
                proposal.agent_id.value,
                proposal.loop_input.observation.tick,
            )
            return None
        write_intents = tuple(
            intent
            for intent in updates
            if type(intent) is MemoryUpdateIntent
            and intent.kind is MemoryUpdateKind.WRITE_MEMORY
        )
        policy = self._consolidation_policy
        if type(policy) is not OfflineConsolidationPolicy:
            policy = OfflineConsolidationPolicy(
                allow_provider=mode is CognitionConsolidationMode.LLM_ASSISTED
            )
        plan = orchestrate_offline_consolidation(
            snapshot=snapshot,
            self_model=proposal.self_state,
            write_intents=write_intents,
            tick=proposal.loop_input.observation.tick,
            mode=mode.value,
            policy=policy,
        )
        if mode is CognitionConsolidationMode.LLM_ASSISTED:
            from agents.cognition.consolidation import LLMOfflineConsolidationSelector

            selector = self._consolidation_selector
            if type(selector) is not LLMOfflineConsolidationSelector:
                selector = LLMOfflineConsolidationSelector(None)
            restricted = await selector.restrict(plan.selection, policy=policy)
            if restricted != plan.selection:
                plan = orchestrate_offline_consolidation(
                    snapshot=snapshot,
                    self_model=proposal.self_state,
                    write_intents=write_intents,
                    tick=proposal.loop_input.observation.tick,
                    mode=mode.value,
                    policy=policy,
                    selection_override=restricted,
                )
        _LOG.debug(
            "offline_consolidation_pending agent_id=%s tick=%s mode=%s "
            "merge_count=%s strengthen_count=%s soft_forget_count=%s",
            proposal.agent_id.value,
            plan.audit.tick,
            mode.value,
            plan.audit.merge_count,
            plan.audit.strengthen_count,
            plan.audit.soft_forget_count,
        )
        return plan

    def last_counterfactual_scenarios(self) -> tuple[object, ...]:
        """Scenarios from the latest prepare. Not a proposal field."""
        return self._last_counterfactual_scenarios

    def counterfactual_state(self) -> object:
        """Latest regret-like affect. Not an ``EmotionKind``."""
        return self._counterfactual_state

    def _counterfactual_bias(
        self, loop_input: CognitiveLoopInput, futures: object
    ) -> dict[str, float] | None:
        policy = self._counterfactual_policy
        scenarios = self._last_counterfactual_scenarios
        if policy is None or not scenarios:
            return None
        from agents.cognition.counterfactual import counterfactual_direction_bias

        members = getattr(futures, "futures", ())
        return counterfactual_direction_bias(
            scenarios,  # type: ignore[arg-type]
            members,
            bonus=policy.direction_bonus,
            owner_id=loop_input.agent_id,
            tick=loop_input.observation.tick,
        )

    def _merge_counterfactual_conclusions(
        self,
        *,
        proposal: CognitiveLoopProposal,
        updates: tuple[object, ...],
        identity_revisions: tuple[object, ...],
    ) -> tuple[tuple[object, ...], tuple[object, ...]]:
        policy = self._counterfactual_policy
        scenarios = self._last_counterfactual_scenarios
        if policy is None or not scenarios:
            return updates, identity_revisions
        from agents.cognition.configuration import CognitionIdentityMode
        from agents.cognition.counterfactual import (
            counterfactual_belief_requests,
            counterfactual_relationship_requests,
        )
        from agents.cognition.identity import counterfactual_regret_request

        owner = proposal.agent_id
        tick = proposal.loop_input.observation.tick
        beliefs = counterfactual_belief_requests(
            scenarios,  # type: ignore[arg-type]
            policy=policy,
            owner_id=owner,
            tick=tick,
        )
        relationships = counterfactual_relationship_requests(
            scenarios,  # type: ignore[arg-type]
            policy=policy,
            owner_id=owner,
            tick=tick,
            resolve_counterpart=getattr(
                self._memory_updates, "_resolve_counterpart", None
            ),
        )
        extra: list[MemoryUpdateIntent] = []
        for request in beliefs:
            extra.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.REVISE_SEMANTIC_BELIEF,
                    belief_revision=request,
                )
            )
        for request in relationships:
            extra.append(
                MemoryUpdateIntent(
                    owner_id=owner,
                    kind=MemoryUpdateKind.REVISE_RELATIONSHIP,
                    relationship_revision=request,
                )
            )
        identity = identity_revisions
        if self._identity_mode is CognitionIdentityMode.ENABLED:
            regret = [
                request
                for scenario in scenarios
                if (
                    request := counterfactual_regret_request(
                        scenario, owner_id=owner, tick=tick
                    )
                )
                is not None
            ]
            identity = (*identity_revisions, *regret)
        return (*updates, *extra), identity

    def _consider(
        self,
        loop_input: CognitiveLoopInput,
        remembered_decisions: tuple[object, ...],
        *,
        memory: object,
        goal_board: object,
        self_model: object,
    ) -> tuple[tuple[object, ...], int]:
        from agents.cognition.configuration import CognitionCounterfactualMode
        from agents.cognition.counterfactual import consider_counterfactuals

        if (
            self._counterfactual_mode is CognitionCounterfactualMode.DISABLED
            or self._counterfactual_policy is None
        ):
            return (), 0
        relationships: tuple[object, ...] = ()
        if loop_input.snapshot is not None:
            relationships = loop_input.snapshot.relationships
        skipped: list[int] = []
        scenarios = consider_counterfactuals(
            loop_input,
            remembered_decisions,  # type: ignore[arg-type]
            policy=self._counterfactual_policy,
            memory=memory,
            goal_board=goal_board,
            self_model=self_model,
            relationships=relationships,
            skipped_out=skipped,
        )
        return scenarios, skipped[0] if skipped else 0

    async def _rank_counterfactuals(
        self,
        loop_input: CognitiveLoopInput,
        scenarios: tuple[object, ...],
    ) -> tuple[object, ...]:
        policy = self._counterfactual_policy
        self._counterfactual_fallback = False
        self._counterfactual_llm_calls = 0
        if policy is None or not policy.allow_provider or not scenarios:
            return scenarios
        from agents.cognition.counterfactual_selection import (
            rank_counterfactual_scenarios,
        )

        result = await rank_counterfactual_scenarios(
            scenarios,  # type: ignore[arg-type]
            policy,
            provider=self._world_model_provider,
            owner_id=loop_input.agent_id.value,
            tick=loop_input.observation.tick,
        )
        self._counterfactual_fallback = result.fallback_used
        self._counterfactual_llm_calls = result.llm_call_count
        if result.fallback_used:
            return scenarios
        chosen = set(result.selected_ids)
        return tuple(item for item in scenarios if item.scenario_id in chosen)

    def last_counterfactual_audit(
        self, *, owner_id: object, tick: int
    ) -> object | None:
        """Audit for the latest prepare. Disabled mode returns none."""
        from agents.cognition.configuration import CognitionCounterfactualMode
        from agents.cognition.counterfactual import build_counterfactual_audit
        from agents.models import AgentId

        if (
            self._counterfactual_mode is CognitionCounterfactualMode.DISABLED
            or self._counterfactual_policy is None
            or type(owner_id) is not AgentId
        ):
            return None
        return build_counterfactual_audit(
            owner_id=owner_id,
            tick=tick,
            mode=self._counterfactual_mode.value,
            scenarios=self._last_counterfactual_scenarios,  # type: ignore[arg-type]
            skipped_count=self._counterfactual_skipped,
            llm_call_count=self._counterfactual_llm_calls,
            fallback_used=self._counterfactual_fallback,
        )

    async def run(
        self,
        loop_input: CognitiveLoopInput,
        *,
        invocation_id: str,
        remembered_decisions: tuple[object, ...] = (),
    ) -> CognitiveLoopResult:
        """Prepare then complete with the proposed command (one-call path)."""
        proposal = await self.prepare(
            loop_input,
            invocation_id=invocation_id,
            remembered_decisions=remembered_decisions,
        )
        return await self.complete(
            proposal, effective_command=proposal.proposed_command
        )

    def _make_fail(
        self,
        *,
        records: list[ComponentBoundaryRecord],
        invocation_id: str,
        agent_id: str,
    ):
        def fail(
            *,
            reason: CognitionFailureReason,
            kind: ComponentKind,
            ordinal: int,
            input_artifact: object,
            status: ComponentStatus = ComponentStatus.FAILED,
        ) -> None:
            failure_reason = (
                CognitionFailureReason.CANCELLED
                if status is ComponentStatus.CANCELLED
                else reason
            )
            records.append(
                ComponentBoundaryRecord(
                    invocation_id=invocation_id,
                    component_kind=kind,
                    component_version=COMPONENT_VERSION,
                    ordinal=ordinal,
                    status=status,
                    confidence=0.0,
                    input_artifact=input_artifact,
                    output_artifact=None,
                    decision_metadata=DecisionMetadata(),
                    failure_reason=failure_reason,
                )
            )
            failure = CognitiveLoopFailure(
                invocation_id=invocation_id,
                agent_id=agent_id,
                reason=failure_reason,
                component_kind=kind,
                ordinal=ordinal,
                boundary_records=tuple(records),
            )
            _LOG.error(
                "cognitive_loop_failed",
                extra={"cognition": failure.log_fields()},
            )
            raise CognitiveLoopError(failure)

        return fail

    def _make_run_stage(
        self,
        *,
        loop_input: CognitiveLoopInput,
        records: list[ComponentBoundaryRecord],
        invocation_id: str,
        agent_id: str,
        fail: object,
    ):
        async def run_stage(
            *,
            kind: ComponentKind,
            ordinal: int,
            input_artifact: object,
            awaitable: Awaitable[T],
            expected_type: type[T],
        ) -> T:
            _LOG.debug(
                "cognitive_stage_start",
                extra={
                    "cognition": {
                        "invocation_id": invocation_id,
                        "agent_id": agent_id,
                        "component_kind": kind.value,
                        "component_version": COMPONENT_VERSION,
                        "ordinal": ordinal,
                    }
                },
            )
            try:
                output = await awaitable
            except CancelledError:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.CANCELLED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                    status=ComponentStatus.CANCELLED,
                )
                raise  # pragma: no cover
            except Exception:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.COMPONENT_FAILED,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
                raise  # pragma: no cover

            if type(output) is not expected_type:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.TYPE_MISMATCH,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )
            owner = getattr(output, "owner_id", None)
            if owner is not None and owner != loop_input.agent_id:
                fail(  # type: ignore[operator]
                    reason=CognitionFailureReason.OWNERSHIP,
                    kind=kind,
                    ordinal=ordinal,
                    input_artifact=input_artifact,
                )

            if kind is ComponentKind.MEMORY_UPDATE:
                if not isinstance(output, tuple):
                    fail(  # type: ignore[operator]
                        reason=CognitionFailureReason.TYPE_MISMATCH,
                        kind=kind,
                        ordinal=ordinal,
                        input_artifact=input_artifact,
                    )
                intents = cast(tuple[object, ...], output)
                for item in intents:
                    if type(item) is not MemoryUpdateIntent:
                        fail(  # type: ignore[operator]
                            reason=CognitionFailureReason.TYPE_MISMATCH,
                            kind=kind,
                            ordinal=ordinal,
                            input_artifact=input_artifact,
                        )
                    intent = cast(MemoryUpdateIntent, item)
                    if intent.owner_id != loop_input.agent_id:
                        fail(  # type: ignore[operator]
                            reason=CognitionFailureReason.OWNERSHIP,
                            kind=kind,
                            ordinal=ordinal,
                            input_artifact=input_artifact,
                        )
                confidence = 1.0
                metadata = DecisionMetadata(
                    selection_codes=(),
                    candidate_count=len(intents),
                )
                output_artifact: object = intents
            else:
                typed = cast(Any, output)
                confidence = float(typed.confidence)
                metadata_obj = typed.decision_metadata
                if type(metadata_obj) is not DecisionMetadata:
                    fail(  # type: ignore[operator]
                        reason=CognitionFailureReason.INVALID_OUTPUT,
                        kind=kind,
                        ordinal=ordinal,
                        input_artifact=input_artifact,
                    )
                metadata = metadata_obj
                output_artifact = output

            records.append(
                ComponentBoundaryRecord(
                    invocation_id=invocation_id,
                    component_kind=kind,
                    component_version=COMPONENT_VERSION,
                    ordinal=ordinal,
                    status=ComponentStatus.COMPLETED,
                    confidence=confidence,
                    input_artifact=input_artifact,
                    output_artifact=output_artifact,
                    decision_metadata=metadata,
                )
            )
            _LOG.debug(
                "cognitive_stage_complete",
                extra={
                    "cognition": {
                        "invocation_id": invocation_id,
                        "agent_id": agent_id,
                        "component_kind": kind.value,
                        "component_version": COMPONENT_VERSION,
                        "ordinal": ordinal,
                        "status": ComponentStatus.COMPLETED.value,
                        "confidence": confidence,
                        "boundary_count": len(records),
                    }
                },
            )
            return output

        return run_stage


def _reputation_agent(identity: object, entity_id: object) -> object | None:
    from agents.models import AgentId

    owner_entity = getattr(identity, "owner_entity_id", None)
    owner_id = getattr(identity, "owner_id", None)
    if entity_id == owner_entity and type(owner_id) is AgentId:
        return owner_id
    for binding in getattr(identity, "counterparts", ()):
        if getattr(binding, "entity_id", None) == entity_id:
            agent_id = getattr(binding, "agent_id", None)
            if type(agent_id) is AgentId:
                return agent_id
    return None



def _build_naming_cue_summary(
    *,
    group_formation: object | None,
    social_norms: object | None,
    social_conventions: object | None,
) -> object:
    """Duck-typed cue bag from already-updated group/norm/convention fields."""
    from agents.cognition.semantic_naming import NamingCueSummary

    group_ids: list[str] = []
    practice_actions: list[str] = []
    for concept in getattr(group_formation, "concepts", ()) or ():
        status = getattr(concept, "status", None)
        if str(getattr(status, "value", status)) != "active":
            continue
        concept_id = getattr(concept, "concept_id", None)
        if isinstance(concept_id, str) and concept_id:
            group_ids.append(concept_id)
    for belief in getattr(social_conventions, "beliefs", ()) or ():
        status = getattr(belief, "status", None)
        if str(getattr(status, "value", status)) != "active":
            continue
        content = getattr(belief, "content", None)
        action = getattr(content, "usual_action", None)
        if isinstance(action, str) and action:
            practice_actions.append(action)
    for belief in getattr(social_norms, "beliefs", ()) or ():
        status = getattr(belief, "status", None)
        if str(getattr(status, "value", status)) != "active":
            continue
        expectation = getattr(belief, "expectation", None)
        action = getattr(expectation, "action", None)
        if action is None:
            action = getattr(expectation, "action_kind", None)
        if action is None:
            pattern = getattr(belief, "pattern", None)
            action = getattr(pattern, "expected_action", None)
        if isinstance(action, str) and action:
            practice_actions.append(action)
        elif hasattr(action, "value") and isinstance(action.value, str):
            practice_actions.append(action.value)
    return NamingCueSummary(
        group_concept_ids=tuple(group_ids),
        practice_action_kinds=tuple(practice_actions),
    )


def _planner_options(
    plan: Callable[..., object], **options: object
) -> dict[str, object]:
    """Pass planner keywords the injected planner actually accepts."""
    parameters = signature(plan).parameters
    accepts_extra = any(
        parameter.kind is Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if accepts_extra:
        return dict(options)
    return {key: value for key, value in options.items() if key in parameters}
