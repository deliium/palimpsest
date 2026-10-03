"""Cognition-owned loop configuration and factory.

This module never imports ``simulation`` or ``experiments``. Runner modes are
translated at the composition boundary into these cognition-local policies.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.communication_strategy import (
    CommunicationStrategyPolicy,
    default_communication_strategy_policy,
)
from agents.cognition.competence import (
    CompetenceBeliefPolicy,
    default_competence_belief_policy,
)
from agents.cognition.contracts import (
    EmotionalStateAppraiser,
    FutureImagination,
    GoalManager,
    MemoryRetriever,
    MotivationEvaluator,
)
from agents.cognition.counterfactual import (
    CounterfactualPolicy,
    default_counterfactual_policy,
)
from agents.cognition.epistemic import EpistemicPolicy, default_epistemic_policy
from agents.cognition.group_formation import (
    GroupFormationPolicy,
    default_group_formation_policy,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.production import ProductionKnowledgeMode
from agents.cognition.prospective import ProspectivePolicy, default_prospective_policy
from agents.cognition.reflection import ReflectionPolicy
from agents.cognition.reputation import (
    ReputationFormationPolicy,
    default_reputation_policy,
)
from agents.cognition.social_conventions import (
    SocialConventionPolicy,
    default_social_convention_policy,
)
from agents.cognition.social_norms import (
    SocialNormPolicy,
    default_social_norm_policy,
)
from agents.cognition.territorial import (
    TerritorialClaimPolicy,
    default_territorial_claim_policy,
)
from agents.cognition.theory_of_mind import (
    TheoryOfMindPolicy,
    default_theory_of_mind_policy,
)
from agents.cognition.world_model import WorldModelPolicy, default_world_model_policy
from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveDisposition,
    DriveKind,
    DriveProfile,
)

_LOG = logging.getLogger("agents.cognition.configuration")

COGNITION_FACTORY_VERSION: Final[str] = "cognition-factory-v1"
MEMORY_POLICY_VERSION: Final[str] = "memory-policy-v1"
IMAGINATION_POLICY_VERSION: Final[str] = "imagination-policy-v1"
MORTALITY_APPRAISAL_POLICY_VERSION: Final[str] = "mortality-appraisal-policy-v1"
GOAL_MANAGEMENT_POLICY_VERSION: Final[str] = "goals.v1"
EMOTIONAL_STATE_POLICY_VERSION: Final[str] = "emotion.v1"

_OVERRIDEABLE: Final[frozenset[DriveKind]] = frozenset(
    {
        DriveKind.CURIOSITY,
        DriveKind.SAFETY,
        DriveKind.BELONGING,
        DriveKind.STATUS,
    }
)


class CognitionMemoryMode(StrEnum):
    """Closed memory retrieval treatments owned by cognition."""

    REFERENCE = "reference"
    RECONSTRUCTIVE = "reconstructive"
    RECONSTRUCTIVE_V2 = "reconstructive_v2"


class CognitionImaginationMode(StrEnum):
    """Closed imagination treatments. Disabled is non-counterfactual."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class CognitionMortalityAppraisalMode(StrEnum):
    """Whether motivation appraises mortality/opportunity foreclosure."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class CognitionGoalManagementMode(StrEnum):
    """Hierarchical goal-management treatment for ``CognitiveLoop``."""

    ENABLED = "enabled"
    PASSTHROUGH = "passthrough"


class CognitionEmotionalStateMode(StrEnum):
    """Short-term emotional-state treatment for ``CognitiveLoop``."""

    ENABLED = "enabled"
    PASSTHROUGH = "passthrough"


class CognitionConsolidationMode(StrEnum):
    """Lockstep with ``simulation.ConsolidationMode``. Default is disabled."""

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CognitionReflectionMode(StrEnum):
    """Lockstep with ``simulation.ReflectionMode``. Default is disabled."""

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CognitionIdentityMode(StrEnum):
    """History-derived self-beliefs. Passthrough leaves the V1 self-model."""

    PASSTHROUGH = "passthrough"
    ENABLED = "enabled"


class CognitionWorldModelMode(StrEnum):
    """Causal world-model treatment. Passthrough leaves commands unchanged."""

    PASSTHROUGH = "passthrough"
    ENABLED = "enabled"


class CognitionTheoryOfMindMode(StrEnum):
    """First-order theory of mind. Passthrough stores no hypotheses."""

    PASSTHROUGH = "passthrough"
    ENABLED = "enabled"


class CognitionProspectiveMode(StrEnum):
    """Bounded prospective imagination. Disabled keeps the one-step path.

    Lockstep with ``simulation.ProspectiveImaginationMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CognitionCounterfactualMode(StrEnum):
    """Subjective counterfactuals. Disabled captures nothing.

    Lockstep with ``simulation.CounterfactualMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CognitionCommunicationStrategyMode(StrEnum):
    """Per-utterance strategy. Disabled leaves commands and audits unchanged.

    Lockstep with ``simulation.CommunicationStrategyMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionReputationMode(StrEnum):
    """Owner-scoped reputation ledger. Disabled leaves the snapshot unset.

    Lockstep with ``simulation.ReputationMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionSkillLearningMode(StrEnum):
    """Opt-in skill learning. Disabled does not change probabilities or beliefs.

    Lockstep with ``simulation.SkillLearningMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionTeachingInteractionMode(StrEnum):
    """Opt-in teaching acts. Disabled does not change skill growth or beliefs.

    Lockstep with ``simulation.TeachingInteractionMode``. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionTerritorialClaimMode(StrEnum):
    """Owner-scoped claim ledger. Disabled leaves the snapshot field unset.

    Lockstep with ``simulation.TerritorialClaimMode``. This is not a
    ``V2CapabilityFlags`` slot. ``DISABLED`` does not allocate a ledger.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionGroupFormationMode(StrEnum):
    """Owner-scoped membership ledger. Disabled leaves the snapshot field unset.

    Lockstep with ``simulation.GroupFormationMode``. This is not a
    ``V2CapabilityFlags`` slot. ``DISABLED`` does not allocate a ledger.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionSocialNormMode(StrEnum):
    """Owner-scoped norm ledger. Disabled leaves the snapshot field unset.

    Lockstep with ``simulation.SocialNormMode``. This is not a
    ``V2CapabilityFlags`` slot. ``DISABLED`` does not allocate a ledger.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitionSocialConventionMode(StrEnum):
    """Owner-scoped convention ledger. Disabled leaves the snapshot field unset.

    Lockstep with ``simulation.SocialConventionMode``. This is not a
    ``V2CapabilityFlags`` slot. ``DISABLED`` does not allocate a ledger.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    return 0.0 if number == 0.0 else number


@dataclass(frozen=True, slots=True)
class CognitionDriveOverride:
    """Sparse override for one experiment-controlled drive disposition."""

    kind: DriveKind
    baseline: float | None = None
    sensitivity: float | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("CognitionDriveOverride.kind must be DriveKind")
        if self.kind not in _OVERRIDEABLE:
            raise ValueError("CognitionDriveOverride.kind is not overrideable")
        if self.baseline is None and self.sensitivity is None:
            raise ValueError("CognitionDriveOverride requires baseline or sensitivity")
        if self.baseline is not None:
            object.__setattr__(
                self, "baseline", _unit_interval("baseline", self.baseline)
            )
        if self.sensitivity is not None:
            object.__setattr__(
                self, "sensitivity", _unit_interval("sensitivity", self.sensitivity)
            )


@dataclass(frozen=True, slots=True)
class CognitionLoopConfig:
    """Explicit policies used to assemble a fixed ``CognitiveLoop``."""

    memory_mode: CognitionMemoryMode = CognitionMemoryMode.RECONSTRUCTIVE
    imagination_mode: CognitionImaginationMode = CognitionImaginationMode.ENABLED
    mortality_appraisal_mode: CognitionMortalityAppraisalMode = (
        CognitionMortalityAppraisalMode.ENABLED
    )
    goal_management_mode: CognitionGoalManagementMode = (
        CognitionGoalManagementMode.ENABLED
    )
    emotional_state_mode: CognitionEmotionalStateMode = (
        CognitionEmotionalStateMode.PASSTHROUGH
    )
    consolidation_mode: CognitionConsolidationMode = CognitionConsolidationMode.DISABLED
    reflection_mode: CognitionReflectionMode = CognitionReflectionMode.DISABLED
    reflection_policy: ReflectionPolicy | None = None
    identity_mode: CognitionIdentityMode = CognitionIdentityMode.PASSTHROUGH
    world_model_mode: CognitionWorldModelMode = CognitionWorldModelMode.PASSTHROUGH
    world_model_policy: WorldModelPolicy | None = None
    theory_of_mind_mode: CognitionTheoryOfMindMode = (
        CognitionTheoryOfMindMode.PASSTHROUGH
    )
    theory_of_mind_policy: TheoryOfMindPolicy | None = None
    epistemic_policy: EpistemicPolicy | None = None
    prospective_mode: CognitionProspectiveMode = CognitionProspectiveMode.DISABLED
    prospective_policy: ProspectivePolicy | None = None
    counterfactual_mode: CognitionCounterfactualMode = (
        CognitionCounterfactualMode.DISABLED
    )
    counterfactual_policy: CounterfactualPolicy | None = None
    communication_strategy_mode: CognitionCommunicationStrategyMode = (
        CognitionCommunicationStrategyMode.DISABLED
    )
    communication_strategy_policy: CommunicationStrategyPolicy | None = None
    reputation_mode: CognitionReputationMode = CognitionReputationMode.DISABLED
    reputation_policy: ReputationFormationPolicy | None = None
    skill_learning_mode: CognitionSkillLearningMode = (
        CognitionSkillLearningMode.DISABLED
    )
    competence_belief_policy: CompetenceBeliefPolicy | None = None
    teaching_interaction_mode: CognitionTeachingInteractionMode = (
        CognitionTeachingInteractionMode.DISABLED
    )
    teaching_claim_policy: object | None = None
    territorial_claim_mode: CognitionTerritorialClaimMode = (
        CognitionTerritorialClaimMode.DISABLED
    )
    territorial_claim_policy: TerritorialClaimPolicy | None = None
    group_formation_mode: CognitionGroupFormationMode = (
        CognitionGroupFormationMode.DISABLED
    )
    group_formation_policy: GroupFormationPolicy | None = None
    social_norm_mode: CognitionSocialNormMode = CognitionSocialNormMode.DISABLED
    social_norm_policy: SocialNormPolicy | None = None
    social_convention_mode: CognitionSocialConventionMode = (
        CognitionSocialConventionMode.DISABLED
    )
    social_convention_policy: SocialConventionPolicy | None = None
    production_knowledge_mode: ProductionKnowledgeMode = (
        ProductionKnowledgeMode.DISABLED
    )
    drive_overrides: tuple[CognitionDriveOverride, ...] = ()
    memory_policy_version: str = MEMORY_POLICY_VERSION
    imagination_policy_version: str = IMAGINATION_POLICY_VERSION
    mortality_appraisal_policy_version: str = MORTALITY_APPRAISAL_POLICY_VERSION
    goal_management_policy_version: str = GOAL_MANAGEMENT_POLICY_VERSION
    emotional_state_policy_version: str = EMOTIONAL_STATE_POLICY_VERSION
    factory_version: str = COGNITION_FACTORY_VERSION

    def __post_init__(self) -> None:
        if type(self.memory_mode) is not CognitionMemoryMode:
            raise TypeError("memory_mode must be CognitionMemoryMode")
        if type(self.imagination_mode) is not CognitionImaginationMode:
            raise TypeError("imagination_mode must be CognitionImaginationMode")
        if type(self.mortality_appraisal_mode) is not CognitionMortalityAppraisalMode:
            raise TypeError(
                "mortality_appraisal_mode must be CognitionMortalityAppraisalMode"
            )
        if type(self.goal_management_mode) is not CognitionGoalManagementMode:
            raise TypeError("goal_management_mode must be CognitionGoalManagementMode")
        if type(self.emotional_state_mode) is not CognitionEmotionalStateMode:
            raise TypeError("emotional_state_mode must be CognitionEmotionalStateMode")
        if type(self.consolidation_mode) is not CognitionConsolidationMode:
            _LOG.error("invalid_enum path=consolidation_mode reason_code=invalid_mode")
            raise TypeError("consolidation_mode must be CognitionConsolidationMode")
        if type(self.reflection_mode) is not CognitionReflectionMode:
            _LOG.error("invalid_enum path=reflection_mode reason_code=invalid_mode")
            raise TypeError("reflection_mode must be CognitionReflectionMode")
        if type(self.identity_mode) is not CognitionIdentityMode:
            _LOG.error("invalid_enum path=identity_mode reason_code=invalid_mode")
            raise TypeError("identity_mode must be CognitionIdentityMode")
        if type(self.world_model_mode) is not CognitionWorldModelMode:
            _LOG.error("invalid_enum path=world_model_mode reason_code=invalid_mode")
            raise TypeError("world_model_mode must be CognitionWorldModelMode")
        if self.world_model_policy is None:
            if self.world_model_mode is CognitionWorldModelMode.ENABLED:
                object.__setattr__(
                    self,
                    "world_model_policy",
                    default_world_model_policy(allow_provider=False),
                )
        elif type(self.world_model_policy) is not WorldModelPolicy:
            _LOG.error("invalid_enum path=world_model_policy reason_code=invalid_type")
            raise TypeError("world_model_policy must be WorldModelPolicy or None")
        if type(self.theory_of_mind_mode) is not CognitionTheoryOfMindMode:
            _LOG.error("invalid_enum path=theory_of_mind_mode reason_code=invalid_mode")
            raise TypeError("theory_of_mind_mode must be CognitionTheoryOfMindMode")
        if self.theory_of_mind_policy is None:
            if self.theory_of_mind_mode is CognitionTheoryOfMindMode.ENABLED:
                object.__setattr__(
                    self,
                    "theory_of_mind_policy",
                    default_theory_of_mind_policy(allow_provider=False),
                )
        elif type(self.theory_of_mind_policy) is not TheoryOfMindPolicy:
            _LOG.error(
                "invalid_enum path=theory_of_mind_policy reason_code=invalid_type"
            )
            raise TypeError("theory_of_mind_policy must be TheoryOfMindPolicy or None")
        if self.theory_of_mind_mode is not CognitionTheoryOfMindMode.ENABLED:
            object.__setattr__(self, "epistemic_policy", None)
        elif self.epistemic_policy is None:
            object.__setattr__(self, "epistemic_policy", default_epistemic_policy())
        elif type(self.epistemic_policy) is not EpistemicPolicy:
            _LOG.error("invalid_enum path=epistemic_policy reason_code=invalid_type")
            raise TypeError("epistemic_policy must be EpistemicPolicy or None")
        if type(self.prospective_mode) is not CognitionProspectiveMode:
            _LOG.error("invalid_enum path=prospective_mode reason_code=invalid_mode")
            raise TypeError("prospective_mode must be CognitionProspectiveMode")
        if self.prospective_mode is CognitionProspectiveMode.DISABLED:
            object.__setattr__(self, "prospective_policy", None)
        elif self.prospective_policy is None:
            object.__setattr__(
                self,
                "prospective_policy",
                default_prospective_policy(
                    allow_provider=(
                        self.prospective_mode is CognitionProspectiveMode.LLM_ASSISTED
                    )
                ),
            )
        elif type(self.prospective_policy) is not ProspectivePolicy:
            _LOG.error("invalid_enum path=prospective_policy reason_code=invalid_type")
            raise TypeError("prospective_policy must be ProspectivePolicy or None")
        if type(self.counterfactual_mode) is not CognitionCounterfactualMode:
            _LOG.error("invalid_enum path=counterfactual_mode reason_code=invalid_mode")
            raise TypeError("counterfactual_mode must be CognitionCounterfactualMode")
        if self.counterfactual_mode is CognitionCounterfactualMode.DISABLED:
            object.__setattr__(self, "counterfactual_policy", None)
        elif self.counterfactual_policy is None:
            object.__setattr__(
                self,
                "counterfactual_policy",
                default_counterfactual_policy(
                    allow_provider=(
                        self.counterfactual_mode
                        is CognitionCounterfactualMode.LLM_ASSISTED
                    )
                ),
            )
        elif type(self.counterfactual_policy) is not CounterfactualPolicy:
            _LOG.error(
                "invalid_enum path=counterfactual_policy reason_code=invalid_type"
            )
            raise TypeError(
                "counterfactual_policy must be CounterfactualPolicy or None"
            )
        if type(self.communication_strategy_mode) is not (
            CognitionCommunicationStrategyMode
        ):
            _LOG.error(
                "invalid_enum path=communication_strategy_mode reason_code=invalid_mode"
            )
            raise TypeError(
                "communication_strategy_mode must be CognitionCommunicationStrategyMode"
            )
        if self.communication_strategy_mode is (
            CognitionCommunicationStrategyMode.DISABLED
        ):
            object.__setattr__(self, "communication_strategy_policy", None)
        elif self.communication_strategy_policy is None:
            object.__setattr__(
                self,
                "communication_strategy_policy",
                default_communication_strategy_policy(),
            )
        elif type(self.communication_strategy_policy) is not (
            CommunicationStrategyPolicy
        ):
            _LOG.error(
                "invalid_enum path=communication_strategy_policy "
                "reason_code=invalid_type"
            )
            raise TypeError(
                "communication_strategy_policy must be "
                "CommunicationStrategyPolicy or None"
            )
        if type(self.reputation_mode) is not CognitionReputationMode:
            _LOG.error("invalid_enum path=reputation_mode reason_code=invalid_mode")
            raise TypeError("reputation_mode must be CognitionReputationMode")
        if self.reputation_mode is CognitionReputationMode.DISABLED:
            object.__setattr__(self, "reputation_policy", None)
        elif self.reputation_policy is None:
            object.__setattr__(self, "reputation_policy", default_reputation_policy())
        elif type(self.reputation_policy) is not ReputationFormationPolicy:
            _LOG.error("invalid_enum path=reputation_policy reason_code=invalid_type")
            raise TypeError(
                "reputation_policy must be ReputationFormationPolicy or None"
            )
        if type(self.skill_learning_mode) is not CognitionSkillLearningMode:
            _LOG.error("invalid_enum path=skill_learning_mode reason_code=invalid_mode")
            raise TypeError("skill_learning_mode must be CognitionSkillLearningMode")
        if self.skill_learning_mode is CognitionSkillLearningMode.DISABLED:
            object.__setattr__(self, "competence_belief_policy", None)
        elif self.competence_belief_policy is None:
            object.__setattr__(
                self,
                "competence_belief_policy",
                default_competence_belief_policy(),
            )
        elif type(self.competence_belief_policy) is not CompetenceBeliefPolicy:
            _LOG.error(
                "invalid_enum path=competence_belief_policy reason_code=invalid_type"
            )
            raise TypeError(
                "competence_belief_policy must be CompetenceBeliefPolicy or None"
            )
        if type(self.teaching_interaction_mode) is not CognitionTeachingInteractionMode:
            _LOG.error(
                "invalid_enum path=teaching_interaction_mode reason_code=invalid_mode"
            )
            raise TypeError(
                "teaching_interaction_mode must be CognitionTeachingInteractionMode"
            )
        if self.teaching_interaction_mode is CognitionTeachingInteractionMode.DISABLED:
            object.__setattr__(self, "teaching_claim_policy", None)
        elif self.teaching_claim_policy is None:
            from agents.cognition.teaching import TeachingClaimPolicy

            object.__setattr__(self, "teaching_claim_policy", TeachingClaimPolicy())
        else:
            from agents.cognition.teaching import TeachingClaimPolicy

            if type(self.teaching_claim_policy) is not TeachingClaimPolicy:
                _LOG.error(
                    "invalid_enum path=teaching_claim_policy reason_code=invalid_type"
                )
                raise TypeError(
                    "teaching_claim_policy must be TeachingClaimPolicy or None"
                )
        if type(self.territorial_claim_mode) is not CognitionTerritorialClaimMode:
            _LOG.error(
                "invalid_enum path=territorial_claim_mode reason_code=invalid_mode"
            )
            raise TypeError(
                "territorial_claim_mode must be CognitionTerritorialClaimMode"
            )
        if self.territorial_claim_mode is CognitionTerritorialClaimMode.DISABLED:
            object.__setattr__(self, "territorial_claim_policy", None)
        elif self.territorial_claim_policy is None:
            object.__setattr__(
                self,
                "territorial_claim_policy",
                default_territorial_claim_policy(),
            )
        elif type(self.territorial_claim_policy) is not TerritorialClaimPolicy:
            _LOG.error(
                "invalid_enum path=territorial_claim_policy reason_code=invalid_type"
            )
            raise TypeError(
                "territorial_claim_policy must be TerritorialClaimPolicy or None"
            )
        if type(self.group_formation_mode) is not CognitionGroupFormationMode:
            _LOG.error(
                "invalid_enum path=group_formation_mode reason_code=invalid_mode"
            )
            raise TypeError("group_formation_mode must be CognitionGroupFormationMode")
        if self.group_formation_mode is CognitionGroupFormationMode.DISABLED:
            object.__setattr__(self, "group_formation_policy", None)
        elif self.group_formation_policy is None:
            object.__setattr__(
                self,
                "group_formation_policy",
                default_group_formation_policy(),
            )
        elif type(self.group_formation_policy) is not GroupFormationPolicy:
            _LOG.error(
                "invalid_enum path=group_formation_policy reason_code=invalid_type"
            )
            raise TypeError(
                "group_formation_policy must be GroupFormationPolicy or None"
            )
        if type(self.social_norm_mode) is not CognitionSocialNormMode:
            _LOG.error("invalid_enum path=social_norm_mode reason_code=invalid_mode")
            raise TypeError("social_norm_mode must be CognitionSocialNormMode")
        if self.social_norm_mode is CognitionSocialNormMode.DISABLED:
            object.__setattr__(self, "social_norm_policy", None)
        elif self.social_norm_policy is None:
            object.__setattr__(self, "social_norm_policy", default_social_norm_policy())
        elif type(self.social_norm_policy) is not SocialNormPolicy:
            _LOG.error("invalid_enum path=social_norm_policy reason_code=invalid_type")
            raise TypeError("social_norm_policy must be SocialNormPolicy or None")
        if type(self.social_convention_mode) is not CognitionSocialConventionMode:
            _LOG.error(
                "invalid_enum path=social_convention_mode reason_code=invalid_mode"
            )
            raise TypeError(
                "social_convention_mode must be CognitionSocialConventionMode"
            )
        if self.social_convention_mode is CognitionSocialConventionMode.DISABLED:
            object.__setattr__(self, "social_convention_policy", None)
        elif self.social_convention_policy is None:
            object.__setattr__(
                self,
                "social_convention_policy",
                default_social_convention_policy(),
            )
        elif type(self.social_convention_policy) is not SocialConventionPolicy:
            _LOG.error(
                "invalid_enum path=social_convention_policy reason_code=invalid_type"
            )
            raise TypeError(
                "social_convention_policy must be SocialConventionPolicy or None"
            )
        if type(self.production_knowledge_mode) is not ProductionKnowledgeMode:
            _LOG.error(
                "invalid_enum path=production_knowledge_mode reason_code=invalid_mode"
            )
            raise TypeError("production_knowledge_mode must be ProductionKnowledgeMode")
        if (
            self.reflection_policy is not None
            and type(self.reflection_policy) is not ReflectionPolicy
        ):
            raise TypeError("reflection_policy must be ReflectionPolicy or None")
        if self.memory_policy_version != MEMORY_POLICY_VERSION:
            raise ValueError("unsupported memory_policy_version")
        if self.imagination_policy_version != IMAGINATION_POLICY_VERSION:
            raise ValueError("unsupported imagination_policy_version")
        if self.mortality_appraisal_policy_version != (
            MORTALITY_APPRAISAL_POLICY_VERSION
        ):
            raise ValueError("unsupported mortality_appraisal_policy_version")
        if self.goal_management_policy_version != GOAL_MANAGEMENT_POLICY_VERSION:
            raise ValueError("unsupported goal_management_policy_version")
        if self.emotional_state_policy_version != EMOTIONAL_STATE_POLICY_VERSION:
            raise ValueError("unsupported emotional_state_policy_version")
        if self.factory_version != COGNITION_FACTORY_VERSION:
            raise ValueError("unsupported factory_version")
        if isinstance(self.drive_overrides, (set, frozenset)):
            raise TypeError("drive_overrides must be ordered")
        if isinstance(self.drive_overrides, (str, bytes)) or not isinstance(
            self.drive_overrides, Sequence
        ):
            raise TypeError("drive_overrides must be ordered")
        overrides = tuple(self.drive_overrides)
        seen: set[DriveKind] = set()
        for item in overrides:
            if type(item) is not CognitionDriveOverride:
                raise TypeError(
                    "drive_overrides entries must be CognitionDriveOverride"
                )
            if item.kind in seen:
                raise ValueError("drive_overrides kinds must be unique")
            seen.add(item.kind)
        object.__setattr__(self, "drive_overrides", overrides)
        _LOG.debug(
            "cognition_config_validated",
            extra={
                "cognition": {
                    "factory_version": self.factory_version,
                    "memory_mode": self.memory_mode.value,
                    "imagination_mode": self.imagination_mode.value,
                    "mortality_appraisal_mode": self.mortality_appraisal_mode.value,
                    "goal_management_mode": self.goal_management_mode.value,
                    "emotional_state_mode": self.emotional_state_mode.value,
                    "consolidation_mode": self.consolidation_mode.value,
                    "reflection_mode": self.reflection_mode.value,
                    "identity_mode": self.identity_mode.value,
                    "world_model_mode": self.world_model_mode.value,
                    "theory_of_mind_mode": self.theory_of_mind_mode.value,
                    "prospective_mode": self.prospective_mode.value,
                    "counterfactual_mode": self.counterfactual_mode.value,
                    "communication_strategy_mode": (
                        self.communication_strategy_mode.value
                    ),
                    "reputation_mode": self.reputation_mode.value,
                    "skill_learning_mode": self.skill_learning_mode.value,
                    "teaching_interaction_mode": self.teaching_interaction_mode.value,
                    "reflection_policy_version": (
                        None
                        if self.reflection_policy is None
                        else self.reflection_policy.version
                    ),
                    "drive_override_count": len(self.drive_overrides),
                    "status": "validated",
                }
            },
        )

    def resolve_drive_profile(self, owner_id: AgentId) -> DriveProfile:
        """Build a complete owner-scoped profile with sparse overrides applied."""
        if type(owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        override_map = {item.kind: item for item in self.drive_overrides}
        dispositions: list[DriveDisposition] = []
        for kind in REQUIRED_DRIVE_KINDS:
            baseline = 0.5
            sensitivity = 0.5
            override = override_map.get(kind)
            if override is not None:
                if override.baseline is not None:
                    baseline = override.baseline
                if override.sensitivity is not None:
                    sensitivity = override.sensitivity
            dispositions.append(
                DriveDisposition(kind=kind, baseline=baseline, sensitivity=sensitivity)
            )
        return DriveProfile(owner_id=owner_id, dispositions=tuple(dispositions))

    def condition_fingerprint_material(self) -> dict[str, object]:
        """Stable, payload-free material for condition fingerprints."""
        return {
            "consolidation_mode": self.consolidation_mode.value,
            "reflection_mode": self.reflection_mode.value,
            "drive_overrides": [
                {
                    "baseline": item.baseline,
                    "kind": item.kind.value,
                    "sensitivity": item.sensitivity,
                }
                for item in self.drive_overrides
            ],
            "factory_version": self.factory_version,
            "goal_management_mode": self.goal_management_mode.value,
            "goal_management_policy_version": self.goal_management_policy_version,
            "emotional_state_mode": self.emotional_state_mode.value,
            "emotional_state_policy_version": self.emotional_state_policy_version,
            "identity_mode": self.identity_mode.value,
            "world_model_mode": self.world_model_mode.value,
            "world_model_policy_version": (
                None
                if self.world_model_policy is None
                else self.world_model_policy.version
            ),
            "theory_of_mind_mode": self.theory_of_mind_mode.value,
            "theory_of_mind_policy_version": (
                None
                if self.theory_of_mind_policy is None
                else self.theory_of_mind_policy.version
            ),
            "epistemic_policy_version": (
                None if self.epistemic_policy is None else self.epistemic_policy.version
            ),
            "prospective_mode": self.prospective_mode.value,
            "prospective_policy_version": (
                None
                if self.prospective_policy is None
                else self.prospective_policy.version
            ),
            "counterfactual_mode": self.counterfactual_mode.value,
            "counterfactual_policy_version": (
                None
                if self.counterfactual_policy is None
                else self.counterfactual_policy.version
            ),
            "communication_strategy_mode": self.communication_strategy_mode.value,
            "communication_strategy_policy_version": (
                None
                if self.communication_strategy_policy is None
                else self.communication_strategy_policy.version
            ),
            "reputation_mode": self.reputation_mode.value,
            "reputation_policy_version": (
                None
                if self.reputation_policy is None
                else self.reputation_policy.version
            ),
            "territorial_claim_mode": self.territorial_claim_mode.value,
            "group_formation_mode": self.group_formation_mode.value,
            "social_norm_mode": self.social_norm_mode.value,
            "social_convention_mode": self.social_convention_mode.value,
            "territorial_claim_policy_version": (
                None
                if self.territorial_claim_policy is None
                else self.territorial_claim_policy.version
            ),
            "skill_learning_mode": self.skill_learning_mode.value,
            "teaching_interaction_mode": self.teaching_interaction_mode.value,
            "competence_belief_policy_version": (
                None
                if self.competence_belief_policy is None
                else self.competence_belief_policy.version
            ),
            "imagination_mode": self.imagination_mode.value,
            "imagination_policy_version": self.imagination_policy_version,
            "memory_mode": self.memory_mode.value,
            "memory_policy_version": self.memory_policy_version,
            "mortality_appraisal_mode": self.mortality_appraisal_mode.value,
            "mortality_appraisal_policy_version": (
                self.mortality_appraisal_policy_version
            ),
        }


def production_cognition_config() -> CognitionLoopConfig:
    """Current production defaults (reconstructive + imagination + mortality)."""
    return CognitionLoopConfig()


def build_cognitive_loop(
    config: CognitionLoopConfig | None = None,
    *,
    memory: MemoryRetriever | None = None,
    futures: FutureImagination | None = None,
    motivation: MotivationEvaluator | None = None,
    goal_manager: GoalManager | None = None,
    emotional_state: EmotionalStateAppraiser | None = None,
    resolve_counterpart: object | None = None,
    pending_evidence: object | None = None,
    consolidation_selector: object | None = None,
    reflection_selector: object | None = None,
    identity_history: object | None = None,
    world_model_provider: object | None = None,
) -> CognitiveLoop:
    """Assemble a ``CognitiveLoop`` from explicit policies.

    Optional component overrides are for tests. Production wiring selects
    memory/imagination/motivation/goal-management/emotional-state
    implementations from ``config`` modes when overrides are omitted.
    ``resolve_counterpart`` maps entity IDs to agent IDs without importing
    simulation types. ``pending_evidence`` is a shared accumulator so
    direct/communicated traces drive same-batch revisions.
    """
    resolved = config if config is not None else production_cognition_config()
    if type(resolved) is not CognitionLoopConfig:
        raise TypeError("config must be CognitionLoopConfig")

    from agents.cognition.communication import (
        CommunicatedMemoryUpdateHook,
        CompositeMemoryUpdateHook,
        PendingEvidenceAccumulator,
    )
    from agents.cognition.defaults import (
        DirectSelfStateProjector,
        DirectSituationModeler,
        EmptyMemoryRetriever,
        LiteralPerceptionInterpreter,
        PresentStateImagination,
        SubjectiveRevisionHook,
    )
    from agents.cognition.deliberation import (
        CommandPlanner,
        MultiCriteriaIntentionSelector,
    )
    from agents.cognition.emotion import PassthroughEmotionalStateAppraiser
    from agents.cognition.goal_manager import (
        HierarchicalGoalManager,
        PassthroughGoalManager,
    )
    from agents.cognition.imagination import ImaginationEngine
    from agents.cognition.memory import DirectObservationMemoryUpdateHook
    from agents.cognition.motivation import MotivationAppraisal

    if memory is None:
        memory = EmptyMemoryRetriever()
        # Caller/runner injects ScopedMemoryRetriever or ReferenceMemoryRetriever.
    if futures is None:
        if resolved.imagination_mode is CognitionImaginationMode.DISABLED:
            futures = PresentStateImagination()
        else:
            futures = ImaginationEngine()
    if motivation is None:
        motivation = MotivationAppraisal(
            mortality_appraisal_enabled=(
                resolved.mortality_appraisal_mode
                is CognitionMortalityAppraisalMode.ENABLED
            )
        )
    if goal_manager is None:
        if resolved.goal_management_mode is CognitionGoalManagementMode.PASSTHROUGH:
            goal_manager = PassthroughGoalManager()
        else:
            goal_manager = HierarchicalGoalManager()
    if emotional_state is None:
        if resolved.emotional_state_mode is CognitionEmotionalStateMode.PASSTHROUGH:
            emotional_state = PassthroughEmotionalStateAppraiser()
        else:
            from agents.cognition.emotion import EmotionalStateEngine

            emotional_state = EmotionalStateEngine()

    emotion_bias = resolved.emotional_state_mode is CognitionEmotionalStateMode.ENABLED

    pending: PendingEvidenceAccumulator
    if pending_evidence is None:
        pending = PendingEvidenceAccumulator()
    elif type(pending_evidence) is PendingEvidenceAccumulator:
        pending = pending_evidence
    else:
        raise TypeError("pending_evidence must be PendingEvidenceAccumulator")

    counterpart = None
    if resolve_counterpart is not None:
        if not callable(resolve_counterpart):
            raise TypeError("resolve_counterpart must be callable")
        counterpart = resolve_counterpart

    _LOG.debug(
        "cognitive_loop_built",
        extra={
            "cognition": {
                "factory_version": resolved.factory_version,
                "memory_mode": resolved.memory_mode.value,
                "imagination_mode": resolved.imagination_mode.value,
                "mortality_appraisal_mode": resolved.mortality_appraisal_mode.value,
                "goal_management_mode": resolved.goal_management_mode.value,
                "emotional_state_mode": resolved.emotional_state_mode.value,
                "identity_mode": resolved.identity_mode.value,
                "world_model_mode": resolved.world_model_mode.value,
                "emotion_bias": emotion_bias,
                "has_counterpart_resolver": counterpart is not None,
                "status": "built",
            }
        },
    )
    from memory.models import OfflineConsolidationPolicy

    consolidation_policy = None
    if resolved.consolidation_mode is not CognitionConsolidationMode.DISABLED:
        consolidation_policy = OfflineConsolidationPolicy(
            allow_provider=(
                resolved.consolidation_mode is CognitionConsolidationMode.LLM_ASSISTED
            )
        )
    return CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=memory,
        situation=DirectSituationModeler(emotion_bias=emotion_bias),
        self_state=DirectSelfStateProjector(
            identity_mode=resolved.identity_mode,
            identity_history=identity_history,
        ),
        goal_manager=goal_manager,
        emotional_state=emotional_state,
        futures=futures,
        motivation=motivation,
        intention=MultiCriteriaIntentionSelector(),
        planner=CommandPlanner(),
        memory_updates=CompositeMemoryUpdateHook(
            (
                DirectObservationMemoryUpdateHook(),
                CommunicatedMemoryUpdateHook(),
                SubjectiveRevisionHook(
                    resolve_counterpart=counterpart,
                    pending=pending,
                ),
            ),
            pending=pending,
        ),
        consolidation_mode=resolved.consolidation_mode,
        consolidation_policy=consolidation_policy,
        consolidation_selector=consolidation_selector,
        reflection_mode=resolved.reflection_mode,
        reflection_policy=resolved.reflection_policy,
        reflection_selector=reflection_selector,
        identity_mode=resolved.identity_mode,
        world_model_mode=resolved.world_model_mode,
        world_model_policy=resolved.world_model_policy,
        world_model_provider=world_model_provider,
        theory_of_mind_mode=resolved.theory_of_mind_mode,
        theory_of_mind_policy=resolved.theory_of_mind_policy,
        epistemic_policy=resolved.epistemic_policy,
        prospective_policy=resolved.prospective_policy,
        counterfactual_mode=resolved.counterfactual_mode,
        counterfactual_policy=resolved.counterfactual_policy,
        communication_strategy_mode=resolved.communication_strategy_mode,
        communication_strategy_policy=resolved.communication_strategy_policy,
        reputation_mode=resolved.reputation_mode,
        reputation_policy=resolved.reputation_policy,
        skill_learning_mode=resolved.skill_learning_mode,
        competence_belief_policy=resolved.competence_belief_policy,
        teaching_interaction_mode=resolved.teaching_interaction_mode,
        teaching_claim_policy=resolved.teaching_claim_policy,
        territorial_claim_mode=resolved.territorial_claim_mode,
        territorial_claim_policy=resolved.territorial_claim_policy,
        group_formation_mode=resolved.group_formation_mode,
        group_formation_policy=resolved.group_formation_policy,
        social_norm_mode=resolved.social_norm_mode,
        social_norm_policy=resolved.social_norm_policy,
        social_convention_mode=resolved.social_convention_mode,
        social_convention_policy=resolved.social_convention_policy,
        production_knowledge_mode=resolved.production_knowledge_mode,
    )
