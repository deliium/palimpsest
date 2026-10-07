"""Immutable simulation runner configuration contracts.

These specifications are replay-significant and credential-free. Credentials,
base URLs, seeds in diagnostic projections, drive values in logs, and story
payloads are out of scope for this module's public diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final

from agents.models import (
    REQUIRED_DRIVE_KINDS,
    AgentId,
    DriveDisposition,
    DriveKind,
    DriveProfile,
    Goal,
    GoalId,
    GoalOutcomeKind,
    GoalStatus,
)
from llm.factory import ProviderAdapterKind
from llm.models import StructuredOutputMode
from simulation.bootstrap import AgentRegistration
from simulation.clock import require_exact_nonneg_int
from simulation.lifecycle import (
    ActionResolution,
    ActionResolutionReason,
    ActionResolutionStatus,
)
from simulation.models import (
    DERIVATION_VERSION_V3,
    StochasticIdentity,
    require_derivation_version,
    require_seed,
    require_stochastic_identity,
    stochastic_identity_fingerprint,
)
from world import ProductionCatalog
from world.actions import agent_command_tag
from world.artifacts import InformationArtifact
from world.environment import EnvironmentalDynamicsSpec
from world.identifiers import (
    EntityId,
    WorldId,
    WorldRevision,
    require_bounded_text,
    require_stable_id,
)
from world.lifecycle import (
    AgentLifecycleRecord,
    LifecycleStageId,
    LifecycleStageThreshold,
    OriginProvenance,
    resolve_dependency_status,
    resolve_lifecycle_stage,
)
from world.lifecycle_effects import StageCapabilityEffect
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    PhysicalRules,
    Resource,
    Weather,
    non_lethal_physical_rules,
    physical_rules_fingerprint,
)

_LOGGER = logging.getLogger("simulation.runner_models")

RUNNER_SCHEMA_VERSION_V1: Final[str] = "runner-config-v1"
RUNNER_SCHEMA_VERSION_V2: Final[str] = "runner-config-v2"
RUNNER_SCHEMA_VERSION_V3: Final[str] = "runner-config-v3"
RUNNER_SCHEMA_VERSION_V4: Final[str] = "runner-config-v4"
RUNNER_SCHEMA_VERSION_V5: Final[str] = "runner-config-v5"
RUNNER_SCHEMA_VERSION_V6: Final[str] = "runner-config-v6"
RUNNER_SCHEMA_VERSION_V7: Final[str] = "runner-config-v7"
RUNNER_SCHEMA_VERSION_V8: Final[str] = "runner-config-v8"
RUNNER_SCHEMA_VERSION_V9: Final[str] = "runner-config-v9"
RUNNER_SCHEMA_VERSION_V10: Final[str] = "runner-config-v10"
RUNNER_SCHEMA_VERSION_V11: Final[str] = "runner-config-v11"
RUNNER_SCHEMA_VERSION_V12: Final[str] = "runner-config-v12"
RUNNER_SCHEMA_VERSION_V13: Final[str] = "runner-config-v13"
RUNNER_SCHEMA_VERSION_V14: Final[str] = "runner-config-v14"
RUNNER_SCHEMA_VERSION_V15: Final[str] = "runner-config-v15"
RUNNER_SCHEMA_VERSION_V16: Final[str] = "runner-config-v16"
RUNNER_SCHEMA_VERSION_V17: Final[str] = "runner-config-v17"
RUNNER_SCHEMA_VERSION_V18: Final[str] = "runner-config-v18"
RUNNER_SCHEMA_VERSION_V19: Final[str] = "runner-config-v19"
RUNNER_SCHEMA_VERSION_V20: Final[str] = "runner-config-v20"
RUNNER_SCHEMA_VERSION_V21: Final[str] = "runner-config-v21"
RUNNER_SCHEMA_VERSION_V22: Final[str] = "runner-config-v22"
RUNNER_SCHEMA_VERSION_V23: Final[str] = "runner-config-v23"
RUNNER_SCHEMA_VERSION_V24: Final[str] = "runner-config-v24"
RUNNER_SCHEMA_VERSION_V25: Final[str] = "runner-config-v25"
RUNNER_SCHEMA_VERSION_V26: Final[str] = "runner-config-v26"
RUNNER_SCHEMA_VERSION_V27: Final[str] = "runner-config-v27"
RUNNER_SCHEMA_VERSION_V28: Final[str] = "runner-config-v28"
RUNNER_SCHEMA_VERSION_V29: Final[str] = "runner-config-v29"
RUNNER_SCHEMA_VERSION_V30: Final[str] = "runner-config-v30"
RUNNER_SCHEMA_VERSION_V31: Final[str] = "runner-config-v31"
RUNNER_SCHEMA_VERSION_V32: Final[str] = "runner-config-v32"
RUNNER_SCHEMA_VERSION_V33: Final[str] = "runner-config-v33"
RUNNER_SCHEMA_VERSION_V34: Final[str] = "runner-config-v34"
RUNNER_SCHEMA_VERSION_V35: Final[str] = "runner-config-v35"
RUNNER_SCHEMA_VERSION: Final[str] = RUNNER_SCHEMA_VERSION_V4
SUPPORTED_RUNNER_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V1,
        RUNNER_SCHEMA_VERSION_V2,
        RUNNER_SCHEMA_VERSION_V3,
        RUNNER_SCHEMA_VERSION_V4,
        RUNNER_SCHEMA_VERSION_V5,
        RUNNER_SCHEMA_VERSION_V6,
        RUNNER_SCHEMA_VERSION_V7,
        RUNNER_SCHEMA_VERSION_V8,
        RUNNER_SCHEMA_VERSION_V9,
        RUNNER_SCHEMA_VERSION_V10,
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
        RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
    }
)
RESULT_SCHEMA_VERSION_V1: Final[str] = "runner-result-v1"
RESULT_SCHEMA_VERSION_V2: Final[str] = "runner-result-v2"
RESULT_SCHEMA_VERSION: Final[str] = RESULT_SCHEMA_VERSION_V2
SUPPORTED_RESULT_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {RESULT_SCHEMA_VERSION_V1, RESULT_SCHEMA_VERSION_V2}
)
COGNITION_POLICY_VERSION: Final[str] = "cognition-policy-v1"
PROVIDER_SETTINGS_VERSION: Final[str] = "provider-settings-v1"
MORTALITY_POLICY_VERSION: Final[str] = "mortality-policy-v1"
OBJECTIVE_PROJECTION_VERSION: Final[str] = "objective-projection-v1"

_V2_CAPABILITY_FLAG_NAMES: Final[tuple[str, ...]] = (
    "advanced_social_inference",
    "multi_hop_testimony_tracking",
    "predictive_world_model",
    "extended_self_model",
    "short_term_emotional_state",
)

# Flags owned by an implemented plan may be enabled without fail-closed.
_V2_OWNED_CAPABILITY_FLAGS: Final[frozenset[str]] = frozenset(
    {
        "advanced_social_inference",
        "extended_self_model",
        "predictive_world_model",
        "short_term_emotional_state",
    }
)

_V3_CAPABILITY_FLAG_NAMES: Final[tuple[str, ...]] = (
    "generational_population",
    "kinship_inheritance",
    "multi_polity_migration",
    "institutional_economy",
    "cultural_historical_memory",
)

# Owned by v3-02/v3-05/v3-09; other V3 flags remain fail-closed.
_V3_OWNED_CAPABILITY_FLAGS: Final[frozenset[str]] = frozenset(
    {
        "generational_population",
        "kinship_inheritance",
        "cultural_historical_memory",
    }
)

_OVERRIDEABLE_DRIVE_KINDS: Final[frozenset[DriveKind]] = frozenset(
    {
        DriveKind.CURIOSITY,
        DriveKind.SAFETY,
        DriveKind.BELONGING,
        DriveKind.STATUS,
    }
)

_DEFAULT_MAX_REQUEST_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_RESPONSE_BYTES: Final[int] = 1_048_576
_DEFAULT_MAX_HEADER_BYTES: Final[int] = 8_192


def _unit_interval(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: not_unit_interval")
    number = float(value)
    if not math.isfinite(number) or number < 0.0 or number > 1.0:
        raise ValueError(f"{name}: not_unit_interval")
    if number == 0.0:
        return 0.0
    return number


class MemoryMode(StrEnum):
    """Closed memory retrieval treatments for experiment arms."""

    REFERENCE = "reference"
    RECONSTRUCTIVE = "reconstructive"
    RECONSTRUCTIVE_V2 = "reconstructive_v2"


class ImaginationMode(StrEnum):
    """Closed imagination treatments. Disabled is non-counterfactual."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class MortalityMode(StrEnum):
    """Closed mortality treatment applied to physical rules and appraisal."""

    DISABLED = "disabled"
    ENABLED = "enabled"


class ConsolidationMode(StrEnum):
    """Closed offline sleep-consolidation treatments.

    Default is ``DISABLED``: physical sleep only. This is not a
    ``V2CapabilityFlags`` slot.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class ReflectionMode(StrEnum):
    """Closed periodic-reflection treatments.

    Default is ``DISABLED``. This is not a ``V2CapabilityFlags`` slot.
    Lockstep with ``agents.cognition.CognitionReflectionMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class ProspectiveImaginationMode(StrEnum):
    """Closed bounded prospective-imagination treatments.

    Default is ``DISABLED``, which keeps the one-step ``imagination.v1`` path.
    This is not a ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionProspectiveMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CounterfactualMode(StrEnum):
    """Closed subjective counterfactual treatments.

    Default is ``DISABLED``. This is not a ``V2CapabilityFlags`` slot.
    Lockstep with ``agents.cognition.CognitionCounterfactualMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"
    LLM_ASSISTED = "llm_assisted"


class CommunicationStrategyMode(StrEnum):
    """Closed per-utterance communication-strategy treatments.

    Default is ``DISABLED``, which leaves commands and audits unchanged.
    This is not a ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionCommunicationStrategyMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class ReputationMode(StrEnum):
    """Closed owner-scoped reputation treatments.

    Default is ``DISABLED``, which leaves commands, memories, relationships,
    beliefs, and audits unchanged. This is not a ``V2CapabilityFlags`` slot.
    Lockstep with ``agents.cognition.CognitionReputationMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class SkillLearningMode(StrEnum):
    """Closed skill-learning treatments.

    Default is ``DISABLED``, which does not change probabilities, fatigue,
    help gain, commands, memories, beliefs, or audits. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionSkillLearningMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class TeachingInteractionMode(StrEnum):
    """Closed teaching treatments.

    Default is ``DISABLED``, which does not change skill growth, probabilities,
    commands, memories, beliefs, or audits. This is not a ``V2CapabilityFlags``
    slot. Lockstep with ``agents.cognition.CognitionTeachingInteractionMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class TerritorialClaimMode(StrEnum):
    """Closed owner-scoped claim treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, relationships, beliefs, reputation, or
    audits. This is not a ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionTerritorialClaimMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class GroupFormationMode(StrEnum):
    """Closed owner-scoped group-formation treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, relationships, beliefs, reputation,
    territorial claims, or audits. This is not a ``V2CapabilityFlags`` slot.
    Lockstep with ``agents.cognition.CognitionGroupFormationMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class SocialNormMode(StrEnum):
    """Closed owner-scoped social-norm treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, semantic beliefs, relationships, reputation,
    territorial claims, group formation, or audits. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionSocialNormMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class SocialConventionMode(StrEnum):
    """Closed owner-scoped social-convention treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, semantic beliefs, relationships, reputation,
    territorial claims, group formation, social norms, or audits. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionSocialConventionMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class ArtifactInterpretationMode(StrEnum):
    """Closed owner-scoped artifact-interpretation treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not compile artifact commands from cognition. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.artifacts.ArtifactInterpretationMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class SemanticNamingMode(StrEnum):
    """Closed owner-scoped semantic-naming treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, semantic beliefs, relationships,
    reputation, territorial claims, group formation, social norms, social
    conventions, artifact interpretation, or audits. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionSemanticNamingMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CulturalNarrativeMode(StrEnum):
    """Closed owner-scoped cultural-narrative treatments.

    Default is ``DISABLED``, which leaves the snapshot field unset and does
    not change commands, memories, semantic beliefs, relationships,
    reputation, territorial claims, group formation, social norms, social
    conventions, semantic naming, artifact interpretation, or audits. This
    is not a ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionCulturalNarrativeMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class CognitiveBudgetMode(StrEnum):
    """Closed per-tick computational budget treatments.

    Default is ``DISABLED``, which leaves stage-local caps alone and does
    not construct a cross-stage tick ledger. This is not a
    ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.CognitionBudgetMode``.
    """

    DISABLED = "disabled"
    ENFORCED = "enforced"


@dataclass(frozen=True, slots=True)
class CognitiveBudgetLimits:
    """Flat numeric tick-budget limits nested on ``AgentCognitionSpec``.

    Required / non-``None`` iff ``cognitive_budget_mode`` is ``ENFORCED``.
    Runner JSON flattens these eight fields onto the cognition dict on v22.
    """

    max_llm_calls_per_tick: int
    max_tokens_per_tick: int
    max_imagination_branches: int
    max_planning_depth: int
    max_recalled_memories: int
    max_tom_targets: int
    reflection_interval_ticks: int
    timeout_seconds: float

    def __post_init__(self) -> None:
        def _nonneg_int(name: str, value: object) -> int:
            if isinstance(value, bool) or type(value) is not int:
                raise TypeError(f"CognitiveBudgetLimits.{name} must be int")
            if value < 0:
                raise ValueError(f"CognitiveBudgetLimits.{name} must be >= 0")
            return value

        def _pos_int(name: str, value: object) -> int:
            number = _nonneg_int(name, value)
            if number < 1:
                raise ValueError(f"CognitiveBudgetLimits.{name} must be >= 1")
            return number

        object.__setattr__(
            self,
            "max_llm_calls_per_tick",
            _nonneg_int("max_llm_calls_per_tick", self.max_llm_calls_per_tick),
        )
        object.__setattr__(
            self,
            "max_tokens_per_tick",
            _nonneg_int("max_tokens_per_tick", self.max_tokens_per_tick),
        )
        object.__setattr__(
            self,
            "max_imagination_branches",
            _pos_int("max_imagination_branches", self.max_imagination_branches),
        )
        object.__setattr__(
            self,
            "max_planning_depth",
            _pos_int("max_planning_depth", self.max_planning_depth),
        )
        object.__setattr__(
            self,
            "max_recalled_memories",
            _pos_int("max_recalled_memories", self.max_recalled_memories),
        )
        object.__setattr__(
            self,
            "max_tom_targets",
            _nonneg_int("max_tom_targets", self.max_tom_targets),
        )
        object.__setattr__(
            self,
            "reflection_interval_ticks",
            _pos_int("reflection_interval_ticks", self.reflection_interval_ticks),
        )
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            raise TypeError("CognitiveBudgetLimits.timeout_seconds must be float")
        timeout = float(self.timeout_seconds)
        if not math.isfinite(timeout) or timeout < 0.0:
            raise ValueError(
                "CognitiveBudgetLimits.timeout_seconds must be finite >= 0"
            )
        object.__setattr__(
            self, "timeout_seconds", 0.0 if timeout == 0.0 else timeout
        )


class ProductionKnowledgeMode(StrEnum):
    """Closed production-belief treatments.

    Default is ``DISABLED``. An empty catalog plus this mode does not change
    commands, probabilities, fatigue, events, memories, beliefs, or audits.
    This is not a ``V2CapabilityFlags`` slot. Lockstep with
    ``agents.cognition.ProductionKnowledgeMode``.
    """

    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


class SkillAuditSide(StrEnum):
    """Which store a harvested skill row came from."""

    OBJECTIVE = "objective"
    SUBJECTIVE = "subjective"


_SKILL_AUDIT_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "foraging",
        "navigation",
        "resource_detection",
        "crafting",
        "building",
        "healing",
        "communication",
        "teaching",
    }
)


@dataclass(frozen=True, slots=True)
class SkillAudit:
    """Analysis-only skill row. Not stored on the runner-result document."""

    agent_id: AgentId
    side: SkillAuditSide
    domain: str
    level: float
    tick: int

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("SkillAudit.agent_id must be AgentId")
        if type(self.side) is not SkillAuditSide:
            raise TypeError("SkillAudit.side must be SkillAuditSide")
        if type(self.domain) is not str or self.domain not in _SKILL_AUDIT_DOMAINS:
            raise ValueError("SkillAudit.domain unknown_domain")
        if type(self.level) is not float or self.level != self.level:
            raise ValueError("SkillAudit.level not_finite")
        if self.level < 0.0 or self.level > 1.0:
            raise ValueError("SkillAudit.level out_of_range")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("SkillAudit.tick", self.tick),
        )


class TeachingAuditStore(StrEnum):
    """Which teaching store a harvested row copies."""

    ADVICE = "advice"
    BELIEF = "belief"
    OBJECTIVE = "objective"


@dataclass(frozen=True, slots=True)
class TeachingAudit:
    """Analysis-only teaching row. Not stored on the runner-result document."""

    agent_id: AgentId
    store: TeachingAuditStore
    token: str
    band_or_level: str
    tick: int
    domain: str
    source_agent_id: AgentId | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("TeachingAudit.agent_id must be AgentId")
        if type(self.store) is not TeachingAuditStore:
            raise TypeError("TeachingAudit.store must be TeachingAuditStore")
        if type(self.token) is not str or not self.token:
            raise ValueError("TeachingAudit.token unknown_token")
        if type(self.band_or_level) is not str or not self.band_or_level:
            raise ValueError("TeachingAudit.band_or_level unknown_token")
        if type(self.domain) is not str or self.domain not in _SKILL_AUDIT_DOMAINS:
            raise ValueError("TeachingAudit.domain unknown_domain")
        if self.source_agent_id is not None and type(self.source_agent_id) is not (
            AgentId
        ):
            raise TypeError("TeachingAudit.source_agent_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("TeachingAudit.tick", self.tick),
        )


_SKILL_RATE_NAMES: Final[tuple[str, ...]] = (
    "practice_rate",
    "success_rate",
    "failure_rate",
    "instruction_rate",
    "observation_rate",
    "probability_gain",
    "efficiency_gain",
    "belief_practice_rate",
    "belief_success_rate",
    "belief_failure_rate",
    "belief_instruction_rate",
    "belief_observation_rate",
    "belief_prior",
    "belief_action_weight",
)


_TEACHING_WEIGHT_NAMES: Final[tuple[str, ...]] = (
    "demonstration_rate",
    "practice_together_rate",
    "offer_window",
    "belief_explain_rate",
    "explain_low_below",
    "explain_high_at",
    "teaching_response_weight",
)
_SKILL_SCHEMAS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V11,
        RUNNER_SCHEMA_VERSION_V12,
        RUNNER_SCHEMA_VERSION_V13,
        RUNNER_SCHEMA_VERSION_V14,
        RUNNER_SCHEMA_VERSION_V15,
        RUNNER_SCHEMA_VERSION_V16,
        RUNNER_SCHEMA_VERSION_V17,
        RUNNER_SCHEMA_VERSION_V18,
        RUNNER_SCHEMA_VERSION_V19,
        RUNNER_SCHEMA_VERSION_V20,
        RUNNER_SCHEMA_VERSION_V21,
        RUNNER_SCHEMA_VERSION_V22,
        RUNNER_SCHEMA_VERSION_V23,
        RUNNER_SCHEMA_VERSION_V24,
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    RUNNER_SCHEMA_VERSION_V29,
    RUNNER_SCHEMA_VERSION_V30,
    RUNNER_SCHEMA_VERSION_V31,
    RUNNER_SCHEMA_VERSION_V32,
    RUNNER_SCHEMA_VERSION_V33,
    RUNNER_SCHEMA_VERSION_V34,
    RUNNER_SCHEMA_VERSION_V35,
    }
)


def teaching_weight_tuple(spec: AgentCognitionSpec) -> tuple[float | int, ...]:
    """Shared numeric contract for one v12 agent. Values are not logged."""
    return tuple(getattr(spec, name) for name in _TEACHING_WEIGHT_NAMES)


def _validate_shared_teaching_weights(spec: AgentCognitionSpec) -> None:
    """Reject a v12 weight tuple the teaching policy would refuse."""
    _skill_number("demonstration_rate", spec.demonstration_rate, unit=False)
    _skill_number("practice_together_rate", spec.practice_together_rate, unit=False)
    _skill_number("belief_explain_rate", spec.belief_explain_rate, unit=False)
    _skill_number("explain_low_below", spec.explain_low_below, unit=True)
    _skill_number("explain_high_at", spec.explain_high_at, unit=True)
    _skill_number("teaching_response_weight", spec.teaching_response_weight, unit=True)
    if isinstance(spec.offer_window, bool) or not isinstance(spec.offer_window, int):
        _LOGGER.error(
            "teaching_weight_invalid field=%s reason_code=invalid_type",
            "offer_window",
        )
        raise ValueError("offer_window: invalid_type")
    if spec.offer_window < 1 or spec.offer_window > 64:
        _LOGGER.error(
            "teaching_weight_invalid field=%s reason_code=offer_window",
            "offer_window",
        )
        raise ValueError("offer_window: offer_window")
    if spec.explain_low_below >= spec.explain_high_at:
        _LOGGER.error(
            "teaching_weight_invalid field=%s reason_code=threshold_order",
            "explain_low_below",
        )
        raise ValueError("explain_low_below: threshold_order")


def skill_rate_tuple(spec: AgentCognitionSpec) -> tuple[float, ...]:
    """Shared numeric contract for one v11 agent. Values are not logged."""
    return tuple(float(getattr(spec, name)) for name in _SKILL_RATE_NAMES)


def _validate_shared_skill_rates(spec: AgentCognitionSpec) -> None:
    """Reject a v11 rate tuple the objective or belief policy would refuse.

    Checked here so runner configuration does not import the private skill
    module. The objective and belief constructors use the same bounds.
    """
    _skill_number("practice_rate", spec.practice_rate, unit=False)
    _skill_number("success_rate", spec.success_rate, unit=False)
    _skill_number("failure_rate", spec.failure_rate, unit=False)
    _skill_number("instruction_rate", spec.instruction_rate, unit=False)
    _skill_number("observation_rate", spec.observation_rate, unit=False)
    _skill_number("probability_gain", spec.probability_gain, unit=True)
    _skill_number("efficiency_gain", spec.efficiency_gain, unit=True)
    _skill_number("belief_practice_rate", spec.belief_practice_rate, unit=False)
    _skill_number("belief_success_rate", spec.belief_success_rate, unit=False)
    _skill_number("belief_failure_rate", spec.belief_failure_rate, unit=False)
    _skill_number("belief_instruction_rate", spec.belief_instruction_rate, unit=False)
    _skill_number("belief_observation_rate", spec.belief_observation_rate, unit=False)
    _skill_number("belief_prior", spec.belief_prior, unit=False)
    _skill_number("belief_action_weight", spec.belief_action_weight, unit=True)


def _skill_number(field_name: str, value: object, *, unit: bool) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _LOGGER.error(
            "skill_rate_invalid field=%s reason_code=not_finite",
            field_name,
        )
        raise ValueError(f"{field_name}: not_finite")
    number = float(value)
    if not math.isfinite(number):
        _LOGGER.error(
            "skill_rate_invalid field=%s reason_code=not_finite",
            field_name,
        )
        raise ValueError(f"{field_name}: not_finite")
    if number < 0.0 or (unit and number > 1.0):
        code = "out_of_range" if unit else "negative_rate"
        _LOGGER.error(
            "skill_rate_invalid field=%s reason_code=%s",
            field_name,
            code,
        )
        raise ValueError(f"{field_name}: {code}")


@dataclass(frozen=True, slots=True)
class V2CapabilityFlags:
    """Run-level reserved V2 capability identifiers (configuration only).

    Defaults are all off (V1-equivalent wiring). Enabling a flag that is not
    yet owned by an implemented plan must fail closed at runner construction
    (``capability_unimplemented``). Owned flags (currently
    ``advanced_social_inference``, ``extended_self_model``,
    ``predictive_world_model``, and ``short_term_emotional_state``) may be
    enabled.
    These are not cognition plugins.
    """

    advanced_social_inference: bool = False
    multi_hop_testimony_tracking: bool = False
    predictive_world_model: bool = False
    extended_self_model: bool = False
    short_term_emotional_state: bool = False

    def __post_init__(self) -> None:
        for name in _V2_CAPABILITY_FLAG_NAMES:
            value = getattr(self, name)
            if type(value) is not bool:
                raise TypeError(f"V2CapabilityFlags.{name} must be bool")

    def any_enabled(self) -> bool:
        return any(getattr(self, name) for name in _V2_CAPABILITY_FLAG_NAMES)

    def enabled_names(self) -> tuple[str, ...]:
        return tuple(name for name in _V2_CAPABILITY_FLAG_NAMES if getattr(self, name))

    def unimplemented_enabled_names(self) -> tuple[str, ...]:
        """Enabled flags that are not yet owned by an implementation plan."""
        return tuple(
            name
            for name in self.enabled_names()
            if name not in _V2_OWNED_CAPABILITY_FLAGS
        )

    def owned_enabled_names(self) -> tuple[str, ...]:
        """Enabled flags owned by an implemented plan."""
        return tuple(
            name for name in self.enabled_names() if name in _V2_OWNED_CAPABILITY_FLAGS
        )


# Alias kept for plan wording; prefer V2CapabilityFlags in new code.
CapabilityProfile = V2CapabilityFlags


@dataclass(frozen=True, slots=True)
class V3CapabilityFlags:
    """Run-level reserved V3 capability identifiers (configuration only).

    Defaults are all off (V2-equivalent wiring). ``generational_population`` is
    owned and may enable on ``runner-config-v24`` or ``runner-config-v25``.
    Other flags still fail closed at ``SimulationRunner.from_config`` with
    ``capability_unimplemented`` until an owning plan lands. Wire key
    ``v3_capability_flags`` is a sibling of V2 ``capability_flags``.
    """

    generational_population: bool = False
    kinship_inheritance: bool = False
    multi_polity_migration: bool = False
    institutional_economy: bool = False
    cultural_historical_memory: bool = False

    def __post_init__(self) -> None:
        for name in _V3_CAPABILITY_FLAG_NAMES:
            value = getattr(self, name)
            if type(value) is not bool:
                raise TypeError(f"V3CapabilityFlags.{name} must be bool")

    def any_enabled(self) -> bool:
        return any(getattr(self, name) for name in _V3_CAPABILITY_FLAG_NAMES)

    def enabled_names(self) -> tuple[str, ...]:
        return tuple(name for name in _V3_CAPABILITY_FLAG_NAMES if getattr(self, name))

    def unimplemented_enabled_names(self) -> tuple[str, ...]:
        """Enabled flags that are not yet owned by an implementation plan."""
        return tuple(
            name
            for name in self.enabled_names()
            if name not in _V3_OWNED_CAPABILITY_FLAGS
        )

    def owned_enabled_names(self) -> tuple[str, ...]:
        """Enabled flags owned by an implemented plan."""
        return tuple(
            name for name in self.enabled_names() if name in _V3_OWNED_CAPABILITY_FLAGS
        )


_DEMOGRAPHIC_POLICY_PARAM_KEYS: Final[Mapping[str, frozenset[str]]] = {
    "disabled": frozenset(),
    "fixed_interval_entry": frozenset(
        {
            "interval_ticks",
            "entries_per_interval",
            "name_prefix",
            "cohort_id_prefix",
            "generation_index",
            "spawn_location_id",
        }
    ),
}

_POPULATION_LIFECYCLE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "lifespan_ticks",
        "stage_thresholds",
        "dependent_until_stage",
        "demographic_policy_id",
        "demographic_policy_params",
        "max_population",
        "natural_death_on_lifespan",
    }
)

_POPULATION_LIFECYCLE_DEVELOPMENTAL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "stage_capability_effects",
        "gradual_aging",
        "lifespan_distribution",
    }
)

_POPULATION_LIFECYCLE_KEYS_V26: Final[frozenset[str]] = (
    _POPULATION_LIFECYCLE_KEYS | _POPULATION_LIFECYCLE_DEVELOPMENTAL_KEYS
)

_GRADUAL_AGING_KEYS: Final[frozenset[str]] = frozenset({"intra_stage_interpolation"})

_LIFESPAN_DISTRIBUTION_KEYS: Final[frozenset[str]] = frozenset(
    {"distribution_id", "params"}
)

_LIFESPAN_DISTRIBUTION_PARAM_KEYS: Final[dict[str, frozenset[str]]] = {
    "fixed": frozenset(),
    "uniform_int": frozenset({"min_ticks", "max_ticks"}),
    "discrete_table": frozenset({"weights"}),
}

_STAGE_CAPABILITY_EFFECT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "stage_id",
        "physical_capacity_factor",
        "learning_rate_factor",
        "fatigue_accrual_factor",
        "denied_command_kinds",
    }
)

_FORBIDDEN_EFFECT_AUTHORITY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "authority",
        "leader",
        "social_rank",
        "respect",
        "role",
        "parent_id",
        "parent_ids",
        "child_id",
        "child_ids",
        "kinship",
        "heavy_labor",
        "long_travel",
        "teach",
        "combat_initiate",
    }
)

_FORBIDDEN_LIFECYCLE_PARAM_KEYS: Final[frozenset[str]] = frozenset(
    {
        "sex",
        "fertility",
        "mating",
        "pregnancy",
        "gestation",
        "parent_id",
        "parent_ids",
        "child_id",
        "child_ids",
        "kinship",
    }
)


def _exact_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True, slots=True)
class GradualAgingSpec:
    """Intra-stage continuous-factor interpolation toggle."""

    intra_stage_interpolation: bool = False

    def __post_init__(self) -> None:
        if type(self.intra_stage_interpolation) is not bool:
            raise TypeError("intra_stage_interpolation must be bool")

    def canonical_payload(self) -> dict[str, object]:
        return {"intra_stage_interpolation": self.intra_stage_interpolation}

    def is_passthrough_default(self) -> bool:
        return self.intra_stage_interpolation is False


@dataclass(frozen=True, slots=True)
class LifespanDistributionSpec:
    """Closed per-agent assigned-lifespan distribution."""

    distribution_id: str = "fixed"
    params: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "distribution_id",
            require_stable_id("distribution_id", self.distribution_id),
        )
        if self.distribution_id not in _LIFESPAN_DISTRIBUTION_PARAM_KEYS:
            raise ValueError(
                "unknown lifespan distribution_id "
                f"{self.distribution_id!r} "
                "(code=unknown_lifespan_distribution_id)"
            )
        if isinstance(self.params, (str, bytes)) or not isinstance(
            self.params, Mapping
        ):
            raise TypeError("lifespan_distribution.params must be a mapping")
        expected = _LIFESPAN_DISTRIBUTION_PARAM_KEYS[self.distribution_id]
        actual = frozenset(self.params.keys())
        if actual != expected:
            raise ValueError(
                "lifespan_distribution.params exact key set mismatch "
                f"distribution_id={self.distribution_id!r} "
                f"expected={sorted(expected)!r} actual={sorted(actual)!r} "
                "(code=lifespan_distribution_params_key_set)"
            )
        frozen_params: dict[str, object] = {}
        for key, value in self.params.items():
            if type(key) is not str:
                raise TypeError("lifespan_distribution.params keys must be str")
            frozen_params[key] = value
        if self.distribution_id == "uniform_int":
            min_ticks = _exact_positive_int(
                "lifespan_distribution.params.min_ticks",
                frozen_params["min_ticks"],
            )
            max_ticks = _exact_positive_int(
                "lifespan_distribution.params.max_ticks",
                frozen_params["max_ticks"],
            )
            if min_ticks > max_ticks:
                raise ValueError(
                    "uniform_int requires 1 <= min_ticks <= max_ticks "
                    "(code=lifespan_distribution_uniform_bounds)"
                )
            frozen_params["min_ticks"] = min_ticks
            frozen_params["max_ticks"] = max_ticks
        elif self.distribution_id == "discrete_table":
            weights_raw = frozen_params["weights"]
            if isinstance(weights_raw, (str, bytes)) or not isinstance(
                weights_raw, Mapping
            ):
                raise TypeError(
                    "discrete_table weights must be a mapping "
                    "(code=lifespan_distribution_weights_type)"
                )
            weights: dict[str, object] = {}
            for age_key, weight in weights_raw.items():
                if type(age_key) is not str:
                    raise TypeError(
                        "discrete_table weight keys must be str ages"
                    )
                age = int(age_key) if age_key.isdigit() else age_key
                if isinstance(age, bool) or type(age) is not int or age < 1:
                    raise ValueError(
                        "discrete_table ages must be positive ints "
                        "(code=lifespan_distribution_weight_age)"
                    )
                if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                    raise TypeError(
                        "discrete_table weights must be numbers "
                        "(code=lifespan_distribution_weight_type)"
                    )
                if float(weight) < 0.0:
                    raise ValueError(
                        "discrete_table weights must be non-negative "
                        "(code=lifespan_distribution_weight_negative)"
                    )
                weights[str(age)] = float(weight) if type(weight) is float else weight
            if len(weights) == 0:
                raise ValueError(
                    "discrete_table weights must be non-empty "
                    "(code=lifespan_distribution_weights_empty)"
                )
            frozen_params["weights"] = MappingProxyType(weights)
        object.__setattr__(self, "params", MappingProxyType(frozen_params))

    def canonical_payload(self) -> dict[str, object]:
        params: dict[str, object]
        if self.distribution_id == "discrete_table":
            raw_weights = self.params["weights"]
            assert isinstance(raw_weights, Mapping)
            params = {
                "weights": {
                    key: raw_weights[key] for key in sorted(raw_weights, key=int)
                }
            }
        else:
            params = {key: self.params[key] for key in sorted(self.params)}
        return {
            "distribution_id": self.distribution_id,
            "params": params,
        }

    def is_passthrough_default(self) -> bool:
        return self.distribution_id == "fixed" and len(self.params) == 0


def default_gradual_aging_spec() -> GradualAgingSpec:
    return GradualAgingSpec(intra_stage_interpolation=False)


def default_lifespan_distribution_spec() -> LifespanDistributionSpec:
    return LifespanDistributionSpec(distribution_id="fixed", params={})


@dataclass(frozen=True, slots=True)
class PopulationLifecycleSpec:
    """Closed run-level population/lifecycle configuration (runner-config-v24+).

    Forbidden biology fields (sex, fertility, mating, pregnancy, parentage,
    kinship) are rejected at construction. Demographic policies are experimental
    entry schedules — not reproductive mechanics. Developmental children
    (stage effects, gradual aging, lifespan distribution) default to passthrough
    equivalents synthesized on v24/v25 decode.
    """

    lifespan_ticks: int
    stage_thresholds: tuple[LifecycleStageThreshold, ...]
    dependent_until_stage: LifecycleStageId
    demographic_policy_id: str
    demographic_policy_params: Mapping[str, object]
    max_population: int
    natural_death_on_lifespan: bool
    stage_capability_effects: tuple[StageCapabilityEffect, ...] = ()
    gradual_aging: GradualAgingSpec = field(default_factory=default_gradual_aging_spec)
    lifespan_distribution: LifespanDistributionSpec = field(
        default_factory=default_lifespan_distribution_spec
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lifespan_ticks",
            _exact_positive_int("lifespan_ticks", self.lifespan_ticks),
        )
        object.__setattr__(
            self,
            "max_population",
            _exact_positive_int("max_population", self.max_population),
        )
        if type(self.natural_death_on_lifespan) is not bool:
            raise TypeError("natural_death_on_lifespan must be bool")
        if type(self.dependent_until_stage) is not LifecycleStageId:
            raise TypeError("dependent_until_stage must be LifecycleStageId")
        object.__setattr__(
            self,
            "demographic_policy_id",
            require_stable_id(
                "demographic_policy_id", self.demographic_policy_id
            ),
        )
        if self.demographic_policy_id not in _DEMOGRAPHIC_POLICY_PARAM_KEYS:
            raise ValueError(
                "unknown demographic_policy_id "
                f"{self.demographic_policy_id!r} "
                "(code=unknown_demographic_policy_id)"
            )
        if isinstance(self.stage_thresholds, (str, bytes)) or not isinstance(
            self.stage_thresholds, Sequence
        ):
            raise TypeError("stage_thresholds must be a sequence")
        if len(self.stage_thresholds) == 0:
            raise ValueError(
                "stage_thresholds must be non-empty "
                "(code=lifecycle_stage_thresholds_empty)"
            )
        thresholds = tuple(self.stage_thresholds)
        for threshold in thresholds:
            if type(threshold) is not LifecycleStageThreshold:
                raise TypeError(
                    "stage_thresholds entries must be LifecycleStageThreshold"
                )
        # Validate ordering / uniqueness via pure resolver (age 0 always covered).
        resolve_lifecycle_stage(0, thresholds)
        object.__setattr__(self, "stage_thresholds", thresholds)
        stage_order = tuple(item.stage_id for item in thresholds)
        resolve_dependency_status(
            stage_order[0],
            self.dependent_until_stage,
            stage_order=stage_order,
        )
        if isinstance(self.demographic_policy_params, (str, bytes)) or not isinstance(
            self.demographic_policy_params, Mapping
        ):
            raise TypeError("demographic_policy_params must be a mapping")
        expected = _DEMOGRAPHIC_POLICY_PARAM_KEYS[self.demographic_policy_id]
        actual = frozenset(self.demographic_policy_params.keys())
        forbidden = actual & _FORBIDDEN_LIFECYCLE_PARAM_KEYS
        if forbidden:
            raise ValueError(
                "demographic_policy_params forbid biology keys "
                f"{sorted(forbidden)!r} (code=lifecycle_biology_forbidden)"
            )
        if actual != expected:
            raise ValueError(
                "demographic_policy_params exact key set mismatch "
                f"policy_id={self.demographic_policy_id!r} "
                f"expected={sorted(expected)!r} actual={sorted(actual)!r} "
                "(code=demographic_policy_params_key_set)"
            )
        frozen_params: dict[str, object] = {}
        for key, value in self.demographic_policy_params.items():
            if type(key) is not str:
                raise TypeError("demographic_policy_params keys must be str")
            frozen_params[key] = value
        if self.demographic_policy_id == "fixed_interval_entry":
            frozen_params["interval_ticks"] = _exact_positive_int(
                "demographic_policy_params.interval_ticks",
                frozen_params["interval_ticks"],
            )
            frozen_params["entries_per_interval"] = require_exact_nonneg_int(
                "demographic_policy_params.entries_per_interval",
                frozen_params["entries_per_interval"],
            )
            frozen_params["name_prefix"] = require_stable_id(
                "demographic_policy_params.name_prefix",
                frozen_params["name_prefix"],
            )
            frozen_params["cohort_id_prefix"] = require_stable_id(
                "demographic_policy_params.cohort_id_prefix",
                frozen_params["cohort_id_prefix"],
            )
            frozen_params["generation_index"] = require_exact_nonneg_int(
                "demographic_policy_params.generation_index",
                frozen_params["generation_index"],
            )
            frozen_params["spawn_location_id"] = require_stable_id(
                "demographic_policy_params.spawn_location_id",
                frozen_params["spawn_location_id"],
            )
        object.__setattr__(
            self, "demographic_policy_params", MappingProxyType(frozen_params)
        )
        final_max = thresholds[-1].inclusive_max_age
        if self.lifespan_ticks - 1 > final_max:
            raise ValueError(
                "stage_thresholds must cover ages through lifespan_ticks-1 "
                "(code=lifecycle_stage_uncovered_lifespan)"
            )
        if type(self.gradual_aging) is not GradualAgingSpec:
            raise TypeError("gradual_aging must be GradualAgingSpec")
        if type(self.lifespan_distribution) is not LifespanDistributionSpec:
            raise TypeError(
                "lifespan_distribution must be LifespanDistributionSpec"
            )
        if isinstance(self.stage_capability_effects, (str, bytes)) or not isinstance(
            self.stage_capability_effects, Sequence
        ):
            raise TypeError("stage_capability_effects must be a sequence")
        effects = tuple(self.stage_capability_effects)
        for effect in effects:
            if type(effect) is not StageCapabilityEffect:
                raise TypeError(
                    "stage_capability_effects entries must be StageCapabilityEffect"
                )
        if len(effects) > 0:
            from world.lifecycle_effects import validate_stage_capability_effects_cover

            effects = validate_stage_capability_effects_cover(effects, stage_order)
        object.__setattr__(self, "stage_capability_effects", effects)
        # Distribution draws must be coverable by stage thresholds.
        if self.lifespan_distribution.distribution_id == "uniform_int":
            max_ticks = int(self.lifespan_distribution.params["max_ticks"])
            if max_ticks - 1 > final_max:
                raise ValueError(
                    "stage_thresholds must cover ages through "
                    "uniform_int max_ticks-1 "
                    "(code=lifecycle_stage_uncovered_lifespan)"
                )
        elif self.lifespan_distribution.distribution_id == "discrete_table":
            weights = self.lifespan_distribution.params["weights"]
            assert isinstance(weights, Mapping)
            for age_key in weights:
                age = int(age_key)
                if age - 1 > final_max:
                    raise ValueError(
                        "stage_thresholds must cover ages through "
                        "discrete_table age-1 "
                        "(code=lifecycle_stage_uncovered_lifespan)"
                    )

    @property
    def stage_order(self) -> tuple[LifecycleStageId, ...]:
        return tuple(item.stage_id for item in self.stage_thresholds)

    def has_developmental_extensions(self) -> bool:
        """True when any developmental child differs from passthrough defaults."""
        if len(self.stage_capability_effects) > 0:
            return True
        if not self.gradual_aging.is_passthrough_default():
            return True
        if not self.lifespan_distribution.is_passthrough_default():
            return True
        return False

    def canonical_payload(
        self, *, include_developmental: bool = False
    ) -> dict[str, object]:
        """Exact wire object for ``population_lifecycle``.

        Base keys are always present. Developmental children are included only
        when ``include_developmental`` is true (runner-config-v26).
        """
        payload: dict[str, object] = {
            "demographic_policy_id": self.demographic_policy_id,
            "demographic_policy_params": {
                key: self.demographic_policy_params[key]
                for key in sorted(self.demographic_policy_params)
            },
            "dependent_until_stage": self.dependent_until_stage.value,
            "lifespan_ticks": self.lifespan_ticks,
            "max_population": self.max_population,
            "natural_death_on_lifespan": self.natural_death_on_lifespan,
            "stage_thresholds": [
                {
                    "inclusive_max_age": item.inclusive_max_age,
                    "stage_id": item.stage_id.value,
                }
                for item in self.stage_thresholds
            ],
        }
        if include_developmental:
            payload["gradual_aging"] = self.gradual_aging.canonical_payload()
            payload["lifespan_distribution"] = (
                self.lifespan_distribution.canonical_payload()
            )
            payload["stage_capability_effects"] = [
                {
                    "denied_command_kinds": list(effect.denied_command_kinds),
                    "fatigue_accrual_factor": effect.fatigue_accrual_factor,
                    "learning_rate_factor": effect.learning_rate_factor,
                    "physical_capacity_factor": effect.physical_capacity_factor,
                    "stage_id": effect.stage_id.value,
                }
                for effect in self.stage_capability_effects
            ]
        return payload


_KINSHIP_PERCEPTION_MODES: Final[frozenset[str]] = frozenset(
    {"none", "self_incident_public"}
)
_KINSHIP_FORBIDDEN_CONFIG_KEYS: Final[frozenset[str]] = frozenset(
    {
        "affection",
        "trust",
        "loyalty",
        "obligation",
        "inheritance_rights",
        "group_id",
        "clan",
        "dynasty",
        "spouse",
        "mate",
        "sex",
        "fertility",
        "pregnancy",
    }
)
_KINSHIP_MAX_QUERY_DEPTH_CEILING: Final[int] = 32
_KINSHIP_MAX_PARENTS_CEILING: Final[int] = 4


@dataclass(frozen=True, slots=True)
class KinshipBootstrapEdgeSpec:
    """One bootstrap parent→child edge among registered agents."""

    parent_agent_id: AgentId
    child_agent_id: AgentId
    established_tick: int = 0

    def __post_init__(self) -> None:
        if type(self.parent_agent_id) is not AgentId:
            raise TypeError("parent_agent_id must be AgentId")
        if type(self.child_agent_id) is not AgentId:
            raise TypeError("child_agent_id must be AgentId")
        if self.parent_agent_id == self.child_agent_id:
            raise ValueError(
                "parent and child must differ (code=kinship_self_parent)"
            )
        object.__setattr__(
            self,
            "established_tick",
            require_exact_nonneg_int(
                "KinshipBootstrapEdgeSpec.established_tick",
                self.established_tick,
            ),
        )


@dataclass(frozen=True, slots=True)
class KinshipAdmitLinkPolicy:
    """Mid-run admit parent link policy (requires generational_population)."""

    allow_parent_links_on_admit: bool = False
    require_living_parent: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_parent_links_on_admit) is not bool:
            raise TypeError("allow_parent_links_on_admit must be bool")
        if type(self.require_living_parent) is not bool:
            raise TypeError("require_living_parent must be bool")


@dataclass(frozen=True, slots=True)
class KinshipSpec:
    """Objective kinship configuration (runner-config-v27 sibling)."""

    bootstrap_edges: tuple[KinshipBootstrapEdgeSpec, ...] = ()
    max_query_depth: int = 8
    max_parents_per_child: int = 2
    perception_mode: str = "none"
    admit_link_policy: KinshipAdmitLinkPolicy = field(
        default_factory=KinshipAdmitLinkPolicy
    )

    def __post_init__(self) -> None:
        if isinstance(self.bootstrap_edges, (str, bytes)) or not isinstance(
            self.bootstrap_edges, Sequence
        ):
            raise TypeError("bootstrap_edges must be a sequence")
        edges = tuple(self.bootstrap_edges)
        for edge in edges:
            if type(edge) is not KinshipBootstrapEdgeSpec:
                raise TypeError(
                    "bootstrap_edges entries must be KinshipBootstrapEdgeSpec"
                )
        object.__setattr__(self, "bootstrap_edges", edges)
        depth = require_exact_nonneg_int(
            "KinshipSpec.max_query_depth", self.max_query_depth
        )
        if depth < 1 or depth > _KINSHIP_MAX_QUERY_DEPTH_CEILING:
            raise ValueError(
                "max_query_depth out of range "
                "(code=kinship_max_query_depth_invalid)"
            )
        object.__setattr__(self, "max_query_depth", depth)
        max_parents = require_exact_nonneg_int(
            "KinshipSpec.max_parents_per_child", self.max_parents_per_child
        )
        if max_parents < 1 or max_parents > _KINSHIP_MAX_PARENTS_CEILING:
            raise ValueError(
                "max_parents_per_child out of range "
                "(code=kinship_max_parents_invalid)"
            )
        object.__setattr__(self, "max_parents_per_child", max_parents)
        mode = require_stable_id("KinshipSpec.perception_mode", self.perception_mode)
        if mode not in _KINSHIP_PERCEPTION_MODES:
            raise ValueError(
                f"unknown perception_mode {mode!r} (code=kinship_perception_mode)"
            )
        object.__setattr__(self, "perception_mode", mode)
        if type(self.admit_link_policy) is not KinshipAdmitLinkPolicy:
            raise TypeError("admit_link_policy must be KinshipAdmitLinkPolicy")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "admit_link_policy": {
                "allow_parent_links_on_admit": (
                    self.admit_link_policy.allow_parent_links_on_admit
                ),
                "require_living_parent": (
                    self.admit_link_policy.require_living_parent
                ),
            },
            "bootstrap_edges": [
                {
                    "child_agent_id": edge.child_agent_id.value,
                    "established_tick": edge.established_tick,
                    "parent_agent_id": edge.parent_agent_id.value,
                }
                for edge in self.bootstrap_edges
            ],
            "max_parents_per_child": self.max_parents_per_child,
            "max_query_depth": self.max_query_depth,
            "perception_mode": self.perception_mode,
        }


def default_kinship_spec() -> KinshipSpec:
    return KinshipSpec()


def example_kinship_spec(
    *,
    parent_agent_id: str = "agent-1",
    child_agent_id: str = "agent-2",
) -> KinshipSpec:
    """Reference kinship spec with one bootstrap edge."""
    return KinshipSpec(
        bootstrap_edges=(
            KinshipBootstrapEdgeSpec(
                parent_agent_id=AgentId(parent_agent_id),
                child_agent_id=AgentId(child_agent_id),
                established_tick=0,
            ),
        ),
    )


_DEPENDENCY_CARE_PERCEPTION_MODES: Final[frozenset[str]] = frozenset(
    {"none", "self_and_colocated"}
)
_DEPENDENCY_CARE_COGNITION_MODES: Final[frozenset[str]] = frozenset(
    {"disabled", "deterministic"}
)
_DEPENDENCY_CARE_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "love",
        "attention",
        "emotion",
        "parenting",
        "attachment",
        "sex",
        "fertility",
        "pregnancy",
        "lactation",
        "nanny",
        "guardian",
        "caregiver",
        "ward",
        "parent_id",
        "assigned_caregiver",
    }
)


@dataclass(frozen=True, slots=True)
class CareActionPolicySpec:
    """Gates which structured care actions are legal."""

    allow_feed: bool = False
    allow_transport: bool = False
    allow_help_safety: bool = True
    allow_teach_learning: bool = False
    require_colocated: bool = True

    def __post_init__(self) -> None:
        for name in (
            "allow_feed",
            "allow_transport",
            "allow_help_safety",
            "allow_teach_learning",
            "require_colocated",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class DependencyCareNeedPolicySpec:
    """Exact per-need policy under dependency_care.need_policies."""

    self_satisfy: bool
    unmet_accrual_per_tick: float
    critical_threshold: float
    critical_consequence: str

    def __post_init__(self) -> None:
        from world.dependency_care import CareNeedPolicy

        # Validate numeric/bool shape via domain CareNeedPolicy.
        CareNeedPolicy(
            self_satisfy=self.self_satisfy,
            unmet_accrual_per_tick=self.unmet_accrual_per_tick,
            critical_threshold=self.critical_threshold,
            critical_consequence=self.critical_consequence,
        )


@dataclass(frozen=True, slots=True)
class DependencyCareSpec:
    """Objective dependency-care configuration (runner-config-v28 sibling).

    Lives under owned ``generational_population`` — not a new V3 flag.
    ``caregiving_cognition_mode`` is config-only (no AgentCognitionSpec bump).
    """

    enabled_needs: tuple[str, ...]
    need_policies: Mapping[str, DependencyCareNeedPolicySpec]
    care_action_policy: CareActionPolicySpec = field(
        default_factory=CareActionPolicySpec
    )
    perception_mode: str = "none"
    caregiving_cognition_mode: str = "disabled"

    def __post_init__(self) -> None:
        from world.dependency_care import (
            FORBIDDEN_NEED_ALIASES,
            CareNeedId,
            CareNeedPolicy,
            require_care_need_policy,
        )

        if isinstance(self.enabled_needs, (str, bytes)) or not isinstance(
            self.enabled_needs, Sequence
        ):
            raise TypeError("enabled_needs must be a sequence")
        if not self.enabled_needs:
            raise ValueError(
                "enabled_needs must be non-empty when dependency_care present "
                "(code=dependency_care_enabled_needs_empty)"
            )
        needs: list[str] = []
        seen: set[str] = set()
        for raw in self.enabled_needs:
            if type(raw) is not str:
                raise TypeError("enabled_needs entries must be str")
            if raw in FORBIDDEN_NEED_ALIASES or raw in _DEPENDENCY_CARE_FORBIDDEN_KEYS:
                raise ValueError(
                    f"forbidden need id {raw!r} "
                    "(code=dependency_care_forbidden_need)"
                )
            try:
                need = CareNeedId(raw)
            except ValueError as exc:
                raise ValueError(
                    f"unknown need id {raw!r} (code=dependency_care_unknown_need)"
                ) from exc
            if need.value in seen:
                raise ValueError(
                    f"duplicate enabled need {need.value!r} "
                    "(code=dependency_care_need_duplicate)"
                )
            seen.add(need.value)
            needs.append(need.value)
        object.__setattr__(self, "enabled_needs", tuple(needs))
        if isinstance(self.need_policies, (str, bytes)) or not isinstance(
            self.need_policies, Mapping
        ):
            raise TypeError("need_policies must be a mapping")
        policy_keys = set(self.need_policies)
        if policy_keys != set(needs):
            raise ValueError(
                "need_policies must cover enabled_needs exactly once "
                "(code=dependency_care_need_policies_mismatch)"
            )
        cleaned_policies: dict[str, DependencyCareNeedPolicySpec] = {}
        for need_id in needs:
            raw_policy = self.need_policies[need_id]
            if type(raw_policy) is not DependencyCareNeedPolicySpec:
                raise TypeError(
                    "need_policies values must be DependencyCareNeedPolicySpec"
                )
            domain = CareNeedPolicy(
                self_satisfy=raw_policy.self_satisfy,
                unmet_accrual_per_tick=raw_policy.unmet_accrual_per_tick,
                critical_threshold=raw_policy.critical_threshold,
                critical_consequence=raw_policy.critical_consequence,
            )
            require_care_need_policy(CareNeedId(need_id), domain)
            cleaned_policies[need_id] = DependencyCareNeedPolicySpec(
                self_satisfy=domain.self_satisfy,
                unmet_accrual_per_tick=domain.unmet_accrual_per_tick,
                critical_threshold=domain.critical_threshold,
                critical_consequence=domain.critical_consequence,
            )
        object.__setattr__(self, "need_policies", dict(cleaned_policies))
        if type(self.care_action_policy) is not CareActionPolicySpec:
            raise TypeError("care_action_policy must be CareActionPolicySpec")
        mode = require_stable_id(
            "DependencyCareSpec.perception_mode", self.perception_mode
        )
        if mode not in _DEPENDENCY_CARE_PERCEPTION_MODES:
            raise ValueError(
                f"unknown perception_mode {mode!r} "
                "(code=dependency_care_perception_mode)"
            )
        object.__setattr__(self, "perception_mode", mode)
        cognition = require_stable_id(
            "DependencyCareSpec.caregiving_cognition_mode",
            self.caregiving_cognition_mode,
        )
        if cognition not in _DEPENDENCY_CARE_COGNITION_MODES:
            raise ValueError(
                f"unknown caregiving_cognition_mode {cognition!r} "
                "(code=dependency_care_cognition_mode)"
            )
        object.__setattr__(self, "caregiving_cognition_mode", cognition)

    def to_domain_policies(self) -> Mapping[object, object]:
        from world.dependency_care import CareNeedId, CareNeedPolicy

        return {
            CareNeedId(need_id): CareNeedPolicy(
                self_satisfy=policy.self_satisfy,
                unmet_accrual_per_tick=policy.unmet_accrual_per_tick,
                critical_threshold=policy.critical_threshold,
                critical_consequence=policy.critical_consequence,
            )
            for need_id, policy in self.need_policies.items()
        }

    def canonical_payload(self) -> dict[str, object]:
        return {
            "care_action_policy": {
                "allow_feed": self.care_action_policy.allow_feed,
                "allow_help_safety": self.care_action_policy.allow_help_safety,
                "allow_teach_learning": self.care_action_policy.allow_teach_learning,
                "allow_transport": self.care_action_policy.allow_transport,
                "require_colocated": self.care_action_policy.require_colocated,
            },
            "caregiving_cognition_mode": self.caregiving_cognition_mode,
            "enabled_needs": list(self.enabled_needs),
            "need_policies": {
                need_id: {
                    "critical_consequence": policy.critical_consequence,
                    "critical_threshold": policy.critical_threshold,
                    "self_satisfy": policy.self_satisfy,
                    "unmet_accrual_per_tick": policy.unmet_accrual_per_tick,
                }
                for need_id, policy in self.need_policies.items()
            },
            "perception_mode": self.perception_mode,
        }


def example_dependency_care_spec(
    *,
    enabled_needs: tuple[str, ...] = ("food", "water", "safety"),
    caregiving_cognition_mode: str = "disabled",
    perception_mode: str = "none",
    allow_feed: bool = True,
    allow_transport: bool = True,
) -> DependencyCareSpec:
    """Reference dependency-care spec for tests and Experiment AI."""
    consequence_by_need = {
        "food": "accelerate_hunger",
        "water": "accelerate_thirst",
        "safety": "health_damage",
        "movement": "no_extra",
        "shelter": "fatigue_accrual",
        "learning": "learning_rate_zero",
    }
    policies = {
        need: DependencyCareNeedPolicySpec(
            self_satisfy=False,
            unmet_accrual_per_tick=0.05,
            critical_threshold=0.8,
            critical_consequence=consequence_by_need[need],
        )
        for need in enabled_needs
    }
    return DependencyCareSpec(
        enabled_needs=enabled_needs,
        need_policies=policies,
        care_action_policy=CareActionPolicySpec(
            allow_feed=allow_feed,
            allow_transport=allow_transport,
            allow_help_safety=True,
            allow_teach_learning=False,
            require_colocated=True,
        ),
        perception_mode=perception_mode,
        caregiving_cognition_mode=caregiving_cognition_mode,
    )


_DEVELOPMENTAL_LEARNING_APPLICABILITY: Final[frozenset[str]] = frozenset(
    {
        "mid_run_new_agents",
        "lifecycle_learning_stage",
        "all_live_agents",
    }
)
_DEVELOPMENTAL_LEARNING_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_DEVELOPMENTAL_BUDGET_COUPLING_MODES: Final[frozenset[str]] = frozenset(
    {"ignore", "respect_enforced"}
)
_DEVELOPMENTAL_BUDGET_DEGRADE: Final[frozenset[str]] = frozenset(
    {"skip_acquisition", "reduce_rate"}
)
_DEVELOPMENTAL_DIVERGENCE_SALT: Final[frozenset[str]] = frozenset({"owner_stream"})
_DEVELOPMENTAL_DOMAIN_RATE_KEYS: Final[frozenset[str]] = frozenset(
    {"base_rate", "stage_compose", "min_exposures", "confidence_floor"}
)
_DEVELOPMENTAL_BUDGET_KEYS: Final[frozenset[str]] = frozenset(
    {"mode", "acquisition_cost_units", "degrade_policy"}
)
_DEVELOPMENTAL_LEARNING_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enabled_domains",
        "enabled_sources",
        "domain_rates",
        "source_weights",
        "applicability",
        "cognitive_budget_coupling",
        "developmental_learning_mode",
        "learner_species_defaults_id",
        "max_entries_per_domain",
        "divergence_salt_policy",
    }
)


@dataclass(frozen=True, slots=True)
class DevelopmentalCognitiveBudgetCoupling:
    """Exact cognitive_budget_coupling object under developmental_learning."""

    mode: str = "respect_enforced"
    acquisition_cost_units: int = 0
    degrade_policy: str = "skip_acquisition"

    def __post_init__(self) -> None:
        mode = require_stable_id(
            "DevelopmentalCognitiveBudgetCoupling.mode", self.mode
        )
        if mode not in _DEVELOPMENTAL_BUDGET_COUPLING_MODES:
            raise ValueError(
                f"unknown cognitive_budget_coupling.mode {mode!r} "
                "(code=developmental_budget_mode_invalid)"
            )
        object.__setattr__(self, "mode", mode)
        units = require_exact_nonneg_int(
            "acquisition_cost_units", self.acquisition_cost_units
        )
        object.__setattr__(self, "acquisition_cost_units", units)
        policy = require_stable_id(
            "DevelopmentalCognitiveBudgetCoupling.degrade_policy",
            self.degrade_policy,
        )
        if policy not in _DEVELOPMENTAL_BUDGET_DEGRADE:
            raise ValueError(
                f"unknown degrade_policy {policy!r} "
                "(code=developmental_budget_degrade_invalid)"
            )
        object.__setattr__(self, "degrade_policy", policy)


@dataclass(frozen=True, slots=True)
class DevelopmentalLearningSpec:
    """Opt-in developmental learning channel (runner-config-v29 sibling).

    Deepens owned ``generational_population`` — not a new V3 flag and not an
    ``AgentCognitionSpec`` enum. Absent object means channel off.
    """

    enabled_domains: tuple[str, ...]
    enabled_sources: tuple[str, ...]
    domain_rates: Mapping[str, object]
    source_weights: Mapping[str, float]
    applicability: str = "mid_run_new_agents"
    cognitive_budget_coupling: DevelopmentalCognitiveBudgetCoupling = field(
        default_factory=DevelopmentalCognitiveBudgetCoupling
    )
    developmental_learning_mode: str = "deterministic"
    learner_species_defaults_id: str = "species_default_developmental_v1"
    max_entries_per_domain: int = 256
    divergence_salt_policy: str = "owner_stream"

    def __post_init__(self) -> None:
        from agents.cognition.developmental_learning import (
            DevelopmentalDomainId,
            DevelopmentalDomainRate,
            DevelopmentalSourceId,
            DevelopmentalStageCompose,
            parse_developmental_domain_id,
            parse_developmental_source_id,
        )
        from simulation.new_agent_initialization import (
            SPECIES_DEFAULT_DEVELOPMENTAL_V1,
            SPECIES_DEFAULT_V1,
        )

        mode = require_stable_id(
            "DevelopmentalLearningSpec.developmental_learning_mode",
            self.developmental_learning_mode,
        )
        if mode == "disabled":
            raise ValueError(
                "developmental_learning_mode=disabled is rejected; omit the "
                "object for off (code=developmental_learning_mode_invalid)"
            )
        if mode not in _DEVELOPMENTAL_LEARNING_MODE:
            raise ValueError(
                f"unknown developmental_learning_mode {mode!r} "
                "(code=developmental_learning_mode_invalid)"
            )
        object.__setattr__(self, "developmental_learning_mode", mode)

        if isinstance(self.enabled_domains, (str, bytes)) or not isinstance(
            self.enabled_domains, Sequence
        ):
            raise TypeError("enabled_domains must be a sequence")
        if not self.enabled_domains:
            raise ValueError(
                "enabled_domains must be non-empty when developmental_learning "
                "present (code=developmental_enabled_domains_empty)"
            )
        domains: list[str] = []
        seen_domains: set[str] = set()
        for raw in self.enabled_domains:
            domain = parse_developmental_domain_id(raw)
            if domain.value in seen_domains:
                raise ValueError(
                    f"duplicate enabled domain {domain.value!r} "
                    "(code=developmental_domain_duplicate)"
                )
            seen_domains.add(domain.value)
            domains.append(domain.value)
        object.__setattr__(self, "enabled_domains", tuple(domains))

        if isinstance(self.enabled_sources, (str, bytes)) or not isinstance(
            self.enabled_sources, Sequence
        ):
            raise TypeError("enabled_sources must be a sequence")
        if not self.enabled_sources:
            raise ValueError(
                "enabled_sources must be non-empty when developmental_learning "
                "present (code=developmental_enabled_sources_empty)"
            )
        sources: list[str] = []
        seen_sources: set[str] = set()
        for raw in self.enabled_sources:
            source = parse_developmental_source_id(raw)
            if source.value in seen_sources:
                raise ValueError(
                    f"duplicate enabled source {source.value!r} "
                    "(code=developmental_source_duplicate)"
                )
            seen_sources.add(source.value)
            sources.append(source.value)
        object.__setattr__(self, "enabled_sources", tuple(sources))

        if isinstance(self.domain_rates, (str, bytes)) or not isinstance(
            self.domain_rates, Mapping
        ):
            raise TypeError("domain_rates must be a mapping")
        if set(self.domain_rates) != set(domains):
            raise ValueError(
                "domain_rates must cover enabled_domains exactly once "
                "(code=developmental_domain_rates_mismatch)"
            )
        cleaned_rates: dict[str, DevelopmentalDomainRate] = {}
        for domain_id in domains:
            raw_rate = self.domain_rates[domain_id]
            if type(raw_rate) is DevelopmentalDomainRate:
                rate = raw_rate
            elif isinstance(raw_rate, Mapping):
                if set(raw_rate) != _DEVELOPMENTAL_DOMAIN_RATE_KEYS:
                    raise ValueError(
                        "domain_rates entry exact keys mismatch "
                        "(code=developmental_domain_rate_keys)"
                    )
                compose_raw = raw_rate["stage_compose"]
                if type(compose_raw) is DevelopmentalStageCompose:
                    compose = compose_raw
                else:
                    try:
                        compose = DevelopmentalStageCompose(str(compose_raw))
                    except ValueError as exc:
                        raise ValueError(
                            f"unknown stage_compose {compose_raw!r} "
                            "(code=developmental_stage_compose_invalid)"
                        ) from exc
                rate = DevelopmentalDomainRate(
                    base_rate=raw_rate["base_rate"],  # type: ignore[arg-type]
                    stage_compose=compose,
                    min_exposures=raw_rate["min_exposures"],  # type: ignore[arg-type]
                    confidence_floor=raw_rate["confidence_floor"],  # type: ignore[arg-type]
                )
            else:
                raise TypeError(
                    "domain_rates values must be DevelopmentalDomainRate or mapping"
                )
            cleaned_rates[domain_id] = rate
        object.__setattr__(self, "domain_rates", dict(cleaned_rates))

        if isinstance(self.source_weights, (str, bytes)) or not isinstance(
            self.source_weights, Mapping
        ):
            raise TypeError("source_weights must be a mapping")
        if set(self.source_weights) != set(sources):
            raise ValueError(
                "source_weights must cover enabled_sources exactly once "
                "(code=developmental_source_weights_mismatch)"
            )
        cleaned_weights: dict[str, float] = {}
        for source_id in sources:
            weight = self.source_weights[source_id]
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError(
                    f"source_weights[{source_id!r}] must be float in (0, 1] "
                    "(code=developmental_source_weight_invalid)"
                )
            number = float(weight)
            if not math.isfinite(number) or number <= 0.0 or number > 1.0:
                raise ValueError(
                    f"source_weights[{source_id!r}] must be float in (0, 1] "
                    "(code=developmental_source_weight_invalid)"
                )
            cleaned_weights[source_id] = number
        object.__setattr__(self, "source_weights", dict(cleaned_weights))

        applicability = require_stable_id(
            "DevelopmentalLearningSpec.applicability", self.applicability
        )
        if applicability not in _DEVELOPMENTAL_LEARNING_APPLICABILITY:
            raise ValueError(
                f"unknown applicability {applicability!r} "
                "(code=developmental_applicability_invalid)"
            )
        object.__setattr__(self, "applicability", applicability)

        if (
            type(self.cognitive_budget_coupling)
            is not DevelopmentalCognitiveBudgetCoupling
        ):
            raise TypeError(
                "cognitive_budget_coupling must be "
                "DevelopmentalCognitiveBudgetCoupling"
            )

        species_id = require_stable_id(
            "DevelopmentalLearningSpec.learner_species_defaults_id",
            self.learner_species_defaults_id,
        )
        if species_id not in {SPECIES_DEFAULT_V1, SPECIES_DEFAULT_DEVELOPMENTAL_V1}:
            raise ValueError(
                f"unknown learner_species_defaults_id {species_id!r} "
                "(code=unknown_species_defaults_id)"
            )
        object.__setattr__(self, "learner_species_defaults_id", species_id)
        if species_id != SPECIES_DEFAULT_DEVELOPMENTAL_V1:
            _LOGGER.debug(
                "developmental_learner_species_defaults_id=%s "
                "(not species_default_developmental_v1)",
                species_id,
            )

        cap = require_exact_nonneg_int(
            "max_entries_per_domain", self.max_entries_per_domain
        )
        if cap < 1:
            raise ValueError(
                "max_entries_per_domain must be >= 1 "
                "(code=developmental_max_entries_invalid)"
            )
        object.__setattr__(self, "max_entries_per_domain", cap)

        salt = require_stable_id(
            "DevelopmentalLearningSpec.divergence_salt_policy",
            self.divergence_salt_policy,
        )
        if salt not in _DEVELOPMENTAL_DIVERGENCE_SALT:
            raise ValueError(
                f"unknown divergence_salt_policy {salt!r} "
                "(code=developmental_divergence_salt_invalid)"
            )
        object.__setattr__(self, "divergence_salt_policy", salt)
        # Silence unused import lint for enum membership documentation.
        _ = (DevelopmentalDomainId, DevelopmentalSourceId)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "applicability": self.applicability,
            "cognitive_budget_coupling": {
                "acquisition_cost_units": (
                    self.cognitive_budget_coupling.acquisition_cost_units
                ),
                "degrade_policy": self.cognitive_budget_coupling.degrade_policy,
                "mode": self.cognitive_budget_coupling.mode,
            },
            "developmental_learning_mode": self.developmental_learning_mode,
            "divergence_salt_policy": self.divergence_salt_policy,
            "domain_rates": {
                domain_id: {
                    "base_rate": rate.base_rate,
                    "confidence_floor": rate.confidence_floor,
                    "min_exposures": rate.min_exposures,
                    "stage_compose": rate.stage_compose.value,
                }
                for domain_id, rate in self.domain_rates.items()
            },
            "enabled_domains": list(self.enabled_domains),
            "enabled_sources": list(self.enabled_sources),
            "learner_species_defaults_id": self.learner_species_defaults_id,
            "max_entries_per_domain": self.max_entries_per_domain,
            "source_weights": {
                source_id: self.source_weights[source_id]
                for source_id in self.enabled_sources
            },
        }


def example_developmental_learning_spec(
    *,
    enabled_domains: tuple[str, ...] = ("locations", "resources", "hazards", "skills"),
    enabled_sources: tuple[str, ...] = ("observation", "experimentation"),
    applicability: str = "mid_run_new_agents",
) -> DevelopmentalLearningSpec:
    """Reference developmental-learning spec for tests and Experiment AJ."""
    from agents.cognition.developmental_learning import (
        DevelopmentalDomainRate,
        DevelopmentalStageCompose,
    )

    rates = {
        domain: DevelopmentalDomainRate(
            base_rate=1.0,
            stage_compose=DevelopmentalStageCompose.MULTIPLY_LIFECYCLE_LEARNING_RATE,
            min_exposures=0,
            confidence_floor=0.1,
        )
        for domain in enabled_domains
    }
    weights = {source: 1.0 for source in enabled_sources}
    return DevelopmentalLearningSpec(
        enabled_domains=enabled_domains,
        enabled_sources=enabled_sources,
        domain_rates=rates,
        source_weights=weights,
        applicability=applicability,
    )


_MENTORSHIP_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_MENTORSHIP_APPLICABILITY: Final[frozenset[str]] = frozenset(
    {"all_live_agents", "mid_run_new_agents", "lifecycle_learning_stage"}
)
_MENTORSHIP_PARTNER_BIAS_MODES: Final[frozenset[str]] = frozenset(
    {"ignore", "prefer_bonded"}
)
_MENTORSHIP_CONFIDENCE_INHERIT: Final[frozenset[str]] = frozenset(
    {"learner_trust_scaled", "fresh_floor"}
)
_MENTORSHIP_BOND_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "form_after_successful_acts",
        "min_trust",
        "reinforce_on_learning_evidence",
        "decay_per_tick",
        "offer_window_extend",
        "symmetric",
    }
)
_MENTORSHIP_LINEAGE_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "max_hop_depth",
        "record_attempts",
        "allow_learner_mutation",
        "mutation_requires_evidence",
        "confidence_inherit_mode",
    }
)
_MENTORSHIP_PARTNER_BIAS_KEYS: Final[frozenset[str]] = frozenset(
    {"mode", "communicate_weight", "content_kind_affinity"}
)
_MENTORSHIP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enabled_content_kinds",
        "bond_policy",
        "lineage_policy",
        "partner_bias",
        "mentorship_mode",
        "requires_teaching_interaction",
        "max_bonds_per_owner",
        "max_lineage_entries_per_owner",
        "applicability",
    }
)


@dataclass(frozen=True, slots=True)
class MentorshipBondPolicy:
    """Exact bond_policy object under mentorship."""

    form_after_successful_acts: int = 2
    min_trust: float = 0.2
    reinforce_on_learning_evidence: bool = True
    decay_per_tick: float = 0.0
    offer_window_extend: int = 0
    symmetric: bool = False

    def __post_init__(self) -> None:
        acts = require_exact_nonneg_int(
            "form_after_successful_acts", self.form_after_successful_acts
        )
        object.__setattr__(self, "form_after_successful_acts", acts)
        trust = float(self.min_trust)
        if isinstance(self.min_trust, bool) or not isinstance(
            self.min_trust, (int, float)
        ):
            raise ValueError("min_trust: not_finite")
        if not math.isfinite(trust) or trust < 0.0 or trust > 1.0:
            raise ValueError("min_trust: out_of_range")
        object.__setattr__(self, "min_trust", trust)
        if type(self.reinforce_on_learning_evidence) is not bool:
            raise TypeError("reinforce_on_learning_evidence must be bool")
        decay = float(self.decay_per_tick)
        if isinstance(self.decay_per_tick, bool) or not isinstance(
            self.decay_per_tick, (int, float)
        ):
            raise ValueError("decay_per_tick: not_finite")
        if not math.isfinite(decay) or decay < 0.0 or decay > 1.0:
            raise ValueError("decay_per_tick: out_of_range")
        object.__setattr__(self, "decay_per_tick", decay)
        extend = require_exact_nonneg_int(
            "offer_window_extend", self.offer_window_extend
        )
        object.__setattr__(self, "offer_window_extend", extend)
        if type(self.symmetric) is not bool:
            raise TypeError("symmetric must be bool")


@dataclass(frozen=True, slots=True)
class MentorshipLineagePolicy:
    """Exact lineage_policy object under mentorship."""

    max_hop_depth: int = 4
    record_attempts: bool = True
    allow_learner_mutation: bool = True
    mutation_requires_evidence: bool = True
    confidence_inherit_mode: str = "learner_trust_scaled"

    def __post_init__(self) -> None:
        depth = require_exact_nonneg_int("max_hop_depth", self.max_hop_depth)
        if depth < 1 or depth > 8:
            raise ValueError(
                "max_hop_depth must be in [1, 8] (code=mentorship_max_hop_invalid)"
            )
        object.__setattr__(self, "max_hop_depth", depth)
        for name in (
            "record_attempts",
            "allow_learner_mutation",
            "mutation_requires_evidence",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        mode = require_stable_id(
            "MentorshipLineagePolicy.confidence_inherit_mode",
            self.confidence_inherit_mode,
        )
        if mode not in _MENTORSHIP_CONFIDENCE_INHERIT:
            raise ValueError(
                f"unknown confidence_inherit_mode {mode!r} "
                "(code=mentorship_confidence_inherit_invalid)"
            )
        object.__setattr__(self, "confidence_inherit_mode", mode)


@dataclass(frozen=True, slots=True)
class MentorshipPartnerBias:
    """Exact partner_bias object under mentorship."""

    mode: str = "prefer_bonded"
    communicate_weight: float = 0.15
    content_kind_affinity: bool = True

    def __post_init__(self) -> None:
        mode = require_stable_id("MentorshipPartnerBias.mode", self.mode)
        if mode not in _MENTORSHIP_PARTNER_BIAS_MODES:
            raise ValueError(
                f"unknown partner_bias.mode {mode!r} "
                "(code=mentorship_partner_bias_mode_invalid)"
            )
        object.__setattr__(self, "mode", mode)
        weight = float(self.communicate_weight)
        if isinstance(self.communicate_weight, bool) or not isinstance(
            self.communicate_weight, (int, float)
        ):
            raise ValueError("communicate_weight: not_finite")
        if not math.isfinite(weight) or weight < 0.0 or weight > 1.0:
            raise ValueError("communicate_weight: out_of_range")
        object.__setattr__(self, "communicate_weight", weight)
        if type(self.content_kind_affinity) is not bool:
            raise TypeError("content_kind_affinity must be bool")


@dataclass(frozen=True, slots=True)
class MentorshipSpec:
    """Opt-in mentorship channel (runner-config-v30 sibling).

    Deepens owned ``generational_population`` — not a new V3 flag and not an
    ``AgentCognitionSpec`` enum. Absent object means channel off.
    """

    enabled_content_kinds: tuple[str, ...]
    bond_policy: MentorshipBondPolicy = field(default_factory=MentorshipBondPolicy)
    lineage_policy: MentorshipLineagePolicy = field(
        default_factory=MentorshipLineagePolicy
    )
    partner_bias: MentorshipPartnerBias = field(default_factory=MentorshipPartnerBias)
    mentorship_mode: str = "deterministic"
    requires_teaching_interaction: bool = True
    max_bonds_per_owner: int = 16
    max_lineage_entries_per_owner: int = 256
    applicability: str = "all_live_agents"

    def __post_init__(self) -> None:
        from agents.cognition.mentorship import parse_mentorship_content_kind

        mode = require_stable_id(
            "MentorshipSpec.mentorship_mode", self.mentorship_mode
        )
        if mode == "disabled":
            raise ValueError(
                "mentorship_mode=disabled is rejected; omit the object for off "
                "(code=mentorship_mode_invalid)"
            )
        if mode not in _MENTORSHIP_MODE:
            raise ValueError(
                f"unknown mentorship_mode {mode!r} (code=mentorship_mode_invalid)"
            )
        object.__setattr__(self, "mentorship_mode", mode)

        if isinstance(self.enabled_content_kinds, (str, bytes)) or not isinstance(
            self.enabled_content_kinds, Sequence
        ):
            raise TypeError("enabled_content_kinds must be a sequence")
        if not self.enabled_content_kinds:
            raise ValueError(
                "enabled_content_kinds must be non-empty when mentorship present "
                "(code=mentorship_enabled_content_kinds_empty)"
            )
        kinds: list[str] = []
        seen: set[str] = set()
        for raw in self.enabled_content_kinds:
            kind = parse_mentorship_content_kind(raw)
            if kind.value in seen:
                raise ValueError(
                    f"duplicate enabled content kind {kind.value!r} "
                    "(code=mentorship_content_kind_duplicate)"
                )
            seen.add(kind.value)
            kinds.append(kind.value)
        object.__setattr__(self, "enabled_content_kinds", tuple(kinds))

        if type(self.bond_policy) is not MentorshipBondPolicy:
            raise TypeError("bond_policy must be MentorshipBondPolicy")
        if type(self.lineage_policy) is not MentorshipLineagePolicy:
            raise TypeError("lineage_policy must be MentorshipLineagePolicy")
        if type(self.partner_bias) is not MentorshipPartnerBias:
            raise TypeError("partner_bias must be MentorshipPartnerBias")
        if type(self.requires_teaching_interaction) is not bool:
            raise TypeError("requires_teaching_interaction must be bool")

        max_bonds = require_exact_nonneg_int(
            "max_bonds_per_owner", self.max_bonds_per_owner
        )
        if max_bonds < 1:
            raise ValueError(
                "max_bonds_per_owner must be >= 1 "
                "(code=mentorship_max_bonds_invalid)"
            )
        object.__setattr__(self, "max_bonds_per_owner", max_bonds)
        max_lineage = require_exact_nonneg_int(
            "max_lineage_entries_per_owner", self.max_lineage_entries_per_owner
        )
        if max_lineage < 1:
            raise ValueError(
                "max_lineage_entries_per_owner must be >= 1 "
                "(code=mentorship_max_lineage_invalid)"
            )
        object.__setattr__(self, "max_lineage_entries_per_owner", max_lineage)

        applicability = require_stable_id(
            "MentorshipSpec.applicability", self.applicability
        )
        if applicability not in _MENTORSHIP_APPLICABILITY:
            raise ValueError(
                f"unknown applicability {applicability!r} "
                "(code=mentorship_applicability_invalid)"
            )
        object.__setattr__(self, "applicability", applicability)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "applicability": self.applicability,
            "bond_policy": {
                "decay_per_tick": self.bond_policy.decay_per_tick,
                "form_after_successful_acts": (
                    self.bond_policy.form_after_successful_acts
                ),
                "min_trust": self.bond_policy.min_trust,
                "offer_window_extend": self.bond_policy.offer_window_extend,
                "reinforce_on_learning_evidence": (
                    self.bond_policy.reinforce_on_learning_evidence
                ),
                "symmetric": self.bond_policy.symmetric,
            },
            "enabled_content_kinds": list(self.enabled_content_kinds),
            "lineage_policy": {
                "allow_learner_mutation": self.lineage_policy.allow_learner_mutation,
                "confidence_inherit_mode": self.lineage_policy.confidence_inherit_mode,
                "max_hop_depth": self.lineage_policy.max_hop_depth,
                "mutation_requires_evidence": (
                    self.lineage_policy.mutation_requires_evidence
                ),
                "record_attempts": self.lineage_policy.record_attempts,
            },
            "max_bonds_per_owner": self.max_bonds_per_owner,
            "max_lineage_entries_per_owner": self.max_lineage_entries_per_owner,
            "mentorship_mode": self.mentorship_mode,
            "partner_bias": {
                "communicate_weight": self.partner_bias.communicate_weight,
                "content_kind_affinity": self.partner_bias.content_kind_affinity,
                "mode": self.partner_bias.mode,
            },
            "requires_teaching_interaction": self.requires_teaching_interaction,
        }


def example_mentorship_spec(
    *,
    enabled_content_kinds: tuple[str, ...] = (
        "practical_skills",
        "factual_beliefs",
        "warnings",
    ),
    applicability: str = "all_live_agents",
    max_hop_depth: int = 4,
) -> MentorshipSpec:
    """Reference mentorship spec for tests and Experiment AK."""
    return MentorshipSpec(
        enabled_content_kinds=enabled_content_kinds,
        applicability=applicability,
        lineage_policy=MentorshipLineagePolicy(max_hop_depth=max_hop_depth),
    )


_CULTURAL_FEATURE_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_CULTURAL_FEATURE_APPLICABILITY: Final[frozenset[str]] = frozenset(
    {"all_live_agents", "mid_run_new_agents"}
)
_CULTURAL_FEATURE_BIAS_MODES: Final[frozenset[str]] = frozenset(
    {"ignore", "prefer_aligned_features"}
)
_CULTURAL_FEATURE_MUTATION_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "allow_mutation",
        "mutation_requires_evidence",
        "max_token_edits",
        "rng_namespace",
    }
)
_CULTURAL_FEATURE_RECOMBINATION_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {"allow_recombination", "max_parents", "min_token_overlap"}
)
_CULTURAL_FEATURE_UPTAKE_COMPOSE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "naming",
        "narrative",
        "norms",
        "conventions",
        "teaching",
        "artifacts",
        "mentorship",
        "repositories",
    }
)
_CULTURAL_FEATURE_BIAS_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {"mode", "communicate_weight", "content_affinity"}
)
_CULTURAL_FEATURE_PROVENANCE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "enabled_feature_kinds",
        "enabled_provenance_channels",
        "mutation_policy",
        "recombination_policy",
        "uptake_compose",
        "bias_policy",
        "cultural_feature_mode",
        "max_beliefs_per_owner",
        "max_evidence_refs",
        "applicability",
    }
)


@dataclass(frozen=True, slots=True)
class CulturalFeatureMutationPolicy:
    """Exact mutation_policy object under cultural_feature_provenance."""

    allow_mutation: bool = True
    mutation_requires_evidence: bool = True
    max_token_edits: int = 1
    rng_namespace: str = "cultural_features"

    def __post_init__(self) -> None:
        if type(self.allow_mutation) is not bool:
            raise TypeError("allow_mutation must be bool")
        if type(self.mutation_requires_evidence) is not bool:
            raise TypeError("mutation_requires_evidence must be bool")
        edits = require_exact_nonneg_int("max_token_edits", self.max_token_edits)
        if edits > 8:
            raise ValueError(
                "max_token_edits must be in [0, 8] "
                "(code=cultural_feature_max_token_edits_invalid)"
            )
        object.__setattr__(self, "max_token_edits", edits)
        namespace = require_stable_id(
            "CulturalFeatureMutationPolicy.rng_namespace", self.rng_namespace
        )
        object.__setattr__(self, "rng_namespace", namespace)


@dataclass(frozen=True, slots=True)
class CulturalFeatureRecombinationPolicy:
    """Exact recombination_policy object under cultural_feature_provenance."""

    allow_recombination: bool = True
    max_parents: int = 2
    min_token_overlap: float = 0.5

    def __post_init__(self) -> None:
        if type(self.allow_recombination) is not bool:
            raise TypeError("allow_recombination must be bool")
        parents = require_exact_nonneg_int("max_parents", self.max_parents)
        if parents < 2 or parents > 4:
            raise ValueError(
                "max_parents must be in [2, 4] "
                "(code=cultural_feature_max_parents_invalid)"
            )
        object.__setattr__(self, "max_parents", parents)
        overlap = float(self.min_token_overlap)
        if isinstance(self.min_token_overlap, bool) or not isinstance(
            self.min_token_overlap, (int, float)
        ):
            raise ValueError("min_token_overlap: not_finite")
        if not math.isfinite(overlap) or overlap < 0.0 or overlap > 1.0:
            raise ValueError("min_token_overlap: out_of_range")
        object.__setattr__(self, "min_token_overlap", overlap)


@dataclass(frozen=True, slots=True)
class CulturalFeatureUptakeCompose:
    """Exact uptake_compose object under cultural_feature_provenance."""

    naming: bool = False
    narrative: bool = False
    norms: bool = False
    conventions: bool = False
    teaching: bool = False
    artifacts: bool = False
    mentorship: bool = False
    repositories: bool = False

    def __post_init__(self) -> None:
        for name in _CULTURAL_FEATURE_UPTAKE_COMPOSE_KEYS:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class CulturalFeatureBiasPolicy:
    """Exact bias_policy object under cultural_feature_provenance."""

    mode: str = "ignore"
    communicate_weight: float = 0.0
    content_affinity: bool = False

    def __post_init__(self) -> None:
        mode = require_stable_id("CulturalFeatureBiasPolicy.mode", self.mode)
        if mode not in _CULTURAL_FEATURE_BIAS_MODES:
            raise ValueError(
                f"unknown bias_policy.mode {mode!r} "
                "(code=cultural_feature_bias_mode_invalid)"
            )
        object.__setattr__(self, "mode", mode)
        weight = float(self.communicate_weight)
        if isinstance(self.communicate_weight, bool) or not isinstance(
            self.communicate_weight, (int, float)
        ):
            raise ValueError("communicate_weight: not_finite")
        if not math.isfinite(weight) or weight < 0.0 or weight > 1.0:
            raise ValueError("communicate_weight: out_of_range")
        object.__setattr__(self, "communicate_weight", weight)
        if type(self.content_affinity) is not bool:
            raise TypeError("content_affinity must be bool")


@dataclass(frozen=True, slots=True)
class CulturalFeatureProvenanceSpec:
    """Opt-in cultural feature provenance channel (runner-config-v31 sibling).

    Owns reserved ``cultural_historical_memory``. Absent object means channel
    off. Not an ``AgentCognitionSpec`` enum.
    """

    enabled_feature_kinds: tuple[str, ...]
    enabled_provenance_channels: tuple[str, ...]
    mutation_policy: CulturalFeatureMutationPolicy = field(
        default_factory=CulturalFeatureMutationPolicy
    )
    recombination_policy: CulturalFeatureRecombinationPolicy = field(
        default_factory=CulturalFeatureRecombinationPolicy
    )
    uptake_compose: CulturalFeatureUptakeCompose = field(
        default_factory=CulturalFeatureUptakeCompose
    )
    bias_policy: CulturalFeatureBiasPolicy = field(
        default_factory=CulturalFeatureBiasPolicy
    )
    cultural_feature_mode: str = "deterministic"
    max_beliefs_per_owner: int = 64
    max_evidence_refs: int = 16
    applicability: str = "all_live_agents"

    def __post_init__(self) -> None:
        from agents.cognition.cultural_features import (
            parse_cultural_feature_kind,
            parse_cultural_transmission_channel,
        )

        mode = require_stable_id(
            "CulturalFeatureProvenanceSpec.cultural_feature_mode",
            self.cultural_feature_mode,
        )
        if mode == "disabled":
            raise ValueError(
                "cultural_feature_mode=disabled is rejected; omit the object "
                "for off (code=cultural_feature_mode_invalid)"
            )
        if mode not in _CULTURAL_FEATURE_MODE:
            raise ValueError(
                f"unknown cultural_feature_mode {mode!r} "
                "(code=cultural_feature_mode_invalid)"
            )
        object.__setattr__(self, "cultural_feature_mode", mode)

        if isinstance(self.enabled_feature_kinds, (str, bytes)) or not isinstance(
            self.enabled_feature_kinds, Sequence
        ):
            raise TypeError("enabled_feature_kinds must be a sequence")
        if not self.enabled_feature_kinds:
            raise ValueError(
                "enabled_feature_kinds must be non-empty when cultural "
                "feature provenance present "
                "(code=cultural_feature_kinds_empty)"
            )
        kinds: list[str] = []
        seen_kinds: set[str] = set()
        for raw in self.enabled_feature_kinds:
            kind = parse_cultural_feature_kind(raw)
            if kind.value in seen_kinds:
                raise ValueError(
                    f"duplicate enabled feature kind {kind.value!r} "
                    "(code=cultural_feature_kind_duplicate)"
                )
            seen_kinds.add(kind.value)
            kinds.append(kind.value)
        object.__setattr__(self, "enabled_feature_kinds", tuple(kinds))

        if isinstance(
            self.enabled_provenance_channels, (str, bytes)
        ) or not isinstance(self.enabled_provenance_channels, Sequence):
            raise TypeError("enabled_provenance_channels must be a sequence")
        if not self.enabled_provenance_channels:
            raise ValueError(
                "enabled_provenance_channels must be non-empty when cultural "
                "feature provenance present "
                "(code=cultural_feature_channels_empty)"
            )
        channels: list[str] = []
        seen_channels: set[str] = set()
        for raw in self.enabled_provenance_channels:
            channel = parse_cultural_transmission_channel(raw)
            if channel.value in seen_channels:
                raise ValueError(
                    f"duplicate enabled provenance channel {channel.value!r} "
                    "(code=cultural_feature_channel_duplicate)"
                )
            seen_channels.add(channel.value)
            channels.append(channel.value)
        object.__setattr__(self, "enabled_provenance_channels", tuple(channels))

        if type(self.mutation_policy) is not CulturalFeatureMutationPolicy:
            raise TypeError("mutation_policy must be CulturalFeatureMutationPolicy")
        if type(self.recombination_policy) is not CulturalFeatureRecombinationPolicy:
            raise TypeError(
                "recombination_policy must be CulturalFeatureRecombinationPolicy"
            )
        if type(self.uptake_compose) is not CulturalFeatureUptakeCompose:
            raise TypeError("uptake_compose must be CulturalFeatureUptakeCompose")
        if type(self.bias_policy) is not CulturalFeatureBiasPolicy:
            raise TypeError("bias_policy must be CulturalFeatureBiasPolicy")

        max_beliefs = require_exact_nonneg_int(
            "max_beliefs_per_owner", self.max_beliefs_per_owner
        )
        if max_beliefs < 1:
            raise ValueError(
                "max_beliefs_per_owner must be >= 1 "
                "(code=cultural_feature_max_beliefs_invalid)"
            )
        object.__setattr__(self, "max_beliefs_per_owner", max_beliefs)
        max_refs = require_exact_nonneg_int("max_evidence_refs", self.max_evidence_refs)
        if max_refs < 1:
            raise ValueError(
                "max_evidence_refs must be >= 1 "
                "(code=cultural_feature_max_evidence_refs_invalid)"
            )
        object.__setattr__(self, "max_evidence_refs", max_refs)

        applicability = require_stable_id(
            "CulturalFeatureProvenanceSpec.applicability", self.applicability
        )
        if applicability not in _CULTURAL_FEATURE_APPLICABILITY:
            raise ValueError(
                f"unknown applicability {applicability!r} "
                "(code=cultural_feature_applicability_invalid)"
            )
        object.__setattr__(self, "applicability", applicability)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "applicability": self.applicability,
            "bias_policy": {
                "communicate_weight": self.bias_policy.communicate_weight,
                "content_affinity": self.bias_policy.content_affinity,
                "mode": self.bias_policy.mode,
            },
            "cultural_feature_mode": self.cultural_feature_mode,
            "enabled_feature_kinds": list(self.enabled_feature_kinds),
            "enabled_provenance_channels": list(self.enabled_provenance_channels),
            "max_beliefs_per_owner": self.max_beliefs_per_owner,
            "max_evidence_refs": self.max_evidence_refs,
            "mutation_policy": {
                "allow_mutation": self.mutation_policy.allow_mutation,
                "max_token_edits": self.mutation_policy.max_token_edits,
                "mutation_requires_evidence": (
                    self.mutation_policy.mutation_requires_evidence
                ),
                "rng_namespace": self.mutation_policy.rng_namespace,
            },
            "recombination_policy": {
                "allow_recombination": self.recombination_policy.allow_recombination,
                "max_parents": self.recombination_policy.max_parents,
                "min_token_overlap": self.recombination_policy.min_token_overlap,
            },
            "uptake_compose": {
                "artifacts": self.uptake_compose.artifacts,
                "conventions": self.uptake_compose.conventions,
                "mentorship": self.uptake_compose.mentorship,
                "naming": self.uptake_compose.naming,
                "narrative": self.uptake_compose.narrative,
                "norms": self.uptake_compose.norms,
                "repositories": self.uptake_compose.repositories,
                "teaching": self.uptake_compose.teaching,
            },
        }


def example_cultural_feature_provenance_spec(
    *,
    enabled_feature_kinds: tuple[str, ...] = (
        "practice",
        "term",
        "narrative_element",
    ),
    enabled_provenance_channels: tuple[str, ...] = (
        "observation",
        "teaching",
        "communication",
    ),
    applicability: str = "all_live_agents",
) -> CulturalFeatureProvenanceSpec:
    """Reference cultural feature provenance spec for tests and Experiment AL."""
    return CulturalFeatureProvenanceSpec(
        enabled_feature_kinds=enabled_feature_kinds,
        enabled_provenance_channels=enabled_provenance_channels,
        applicability=applicability,
    )


_HISTORICAL_MEMORY_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_HISTORICAL_MEMORY_WITNESS_DEFINITIONS: Final[frozenset[str]] = frozenset(
    {
        "occurrence_participants",
        "occurrence_participants_plus_colocated_observers",
    }
)
_HISTORICAL_MEMORY_QUERY_SELECTORS: Final[frozenset[str]] = frozenset(
    {"all_tracked_sources", "experiment_marked_only"}
)
_HISTORICAL_MEMORY_TRANSITION_RESOLUTIONS: Final[frozenset[str]] = frozenset(
    {"on_death_and_generation_boundary", "every_tick"}
)
_HISTORICAL_MEMORY_APPLICABILITY: Final[frozenset[str]] = frozenset(
    {"all_tracked_sources"}
)
_HISTORICAL_MEMORY_FORBIDDEN_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "inject_into_agents",
        "label_agent_memories",
        "assmann_cognition_mode",
        "auto_layer_beliefs",
        "assmann_label_for_agent",
        "agent_memory_class",
        "self_knowledge_layer",
        "lived_experience_flag",
        "living_memory",
        "communicative_memory",
        "cultural_memory",
        "society_memory_tier",
    }
)
_HISTORICAL_MEMORY_CULTURAL_SCHEMAS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
    }
)
_DURABLE_RECORDS_SCHEMAS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
    }
)
_HISTORICAL_MEMORY_LAYER_SCHEMAS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
    }
)
_KNOWLEDGE_REPOSITORIES_SCHEMAS: Final[frozenset[str]] = frozenset(
    {RUNNER_SCHEMA_VERSION_V34, RUNNER_SCHEMA_VERSION_V35}
)
_KNOWLEDGE_GENEALOGY_SCHEMAS: Final[frozenset[str]] = frozenset(
    {RUNNER_SCHEMA_VERSION_V35}
)


@dataclass(frozen=True, slots=True)
class HistoricalMemoryLayersSpec:
    """Opt-in analysis-only historical memory layers (runner-config-v32).

    Researcher harvest/query config only. Never an AgentCognitionSpec mode.
    Absent object means analysis layers off.
    """

    mode: str = "deterministic"
    max_communicative_hops: int = 2
    witness_definition: str = "occurrence_participants"
    include_narrative_lineage: bool = True
    include_cultural_features: bool = True
    include_artifact_edges: bool = True
    include_teaching_edges: bool = True
    generation_distance_weight: float = 0.0
    query_event_selector: str = "all_tracked_sources"
    transition_tick_resolution: str = "on_death_and_generation_boundary"
    applicability: str = "all_tracked_sources"

    def __post_init__(self) -> None:
        mode = require_stable_id("HistoricalMemoryLayersSpec.mode", self.mode)
        if mode == "disabled":
            raise ValueError(
                "historical_memory mode=disabled is rejected; omit the object "
                "for off (code=historical_memory_mode_invalid)"
            )
        if mode not in _HISTORICAL_MEMORY_MODE:
            raise ValueError(
                f"unknown historical_memory mode {mode!r} "
                "(code=historical_memory_mode_invalid)"
            )
        object.__setattr__(self, "mode", mode)

        hops = require_exact_nonneg_int(
            "max_communicative_hops", self.max_communicative_hops
        )
        if hops < 1 or hops > 8:
            raise ValueError(
                "max_communicative_hops must be in [1, 8] "
                "(code=historical_memory_max_hops_invalid)"
            )
        object.__setattr__(self, "max_communicative_hops", hops)

        witness = require_stable_id(
            "HistoricalMemoryLayersSpec.witness_definition",
            self.witness_definition,
        )
        if witness not in _HISTORICAL_MEMORY_WITNESS_DEFINITIONS:
            raise ValueError(
                f"unknown witness_definition {witness!r} "
                "(code=historical_memory_witness_definition_invalid)"
            )
        object.__setattr__(self, "witness_definition", witness)

        if type(self.include_narrative_lineage) is not bool:
            raise TypeError("include_narrative_lineage must be bool")
        if type(self.include_cultural_features) is not bool:
            raise TypeError("include_cultural_features must be bool")
        if type(self.include_artifact_edges) is not bool:
            raise TypeError("include_artifact_edges must be bool")
        if type(self.include_teaching_edges) is not bool:
            raise TypeError("include_teaching_edges must be bool")

        if isinstance(self.generation_distance_weight, bool) or not isinstance(
            self.generation_distance_weight, (int, float)
        ):
            raise ValueError(
                "generation_distance_weight must be a finite float "
                "(code=historical_memory_generation_weight_invalid)"
            )
        weight = float(self.generation_distance_weight)
        if not math.isfinite(weight) or weight < 0.0 or weight > 1.0:
            raise ValueError(
                "generation_distance_weight must be in [0, 1] "
                "(code=historical_memory_generation_weight_invalid)"
            )
        object.__setattr__(self, "generation_distance_weight", weight)

        selector = require_stable_id(
            "HistoricalMemoryLayersSpec.query_event_selector",
            self.query_event_selector,
        )
        if selector not in _HISTORICAL_MEMORY_QUERY_SELECTORS:
            raise ValueError(
                f"unknown query_event_selector {selector!r} "
                "(code=historical_memory_query_selector_invalid)"
            )
        object.__setattr__(self, "query_event_selector", selector)

        resolution = require_stable_id(
            "HistoricalMemoryLayersSpec.transition_tick_resolution",
            self.transition_tick_resolution,
        )
        if resolution not in _HISTORICAL_MEMORY_TRANSITION_RESOLUTIONS:
            raise ValueError(
                f"unknown transition_tick_resolution {resolution!r} "
                "(code=historical_memory_transition_resolution_invalid)"
            )
        object.__setattr__(self, "transition_tick_resolution", resolution)

        applicability = require_stable_id(
            "HistoricalMemoryLayersSpec.applicability", self.applicability
        )
        if applicability not in _HISTORICAL_MEMORY_APPLICABILITY:
            raise ValueError(
                f"unknown applicability {applicability!r} "
                "(code=historical_memory_applicability_invalid)"
            )
        object.__setattr__(self, "applicability", applicability)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "applicability": self.applicability,
            "generation_distance_weight": self.generation_distance_weight,
            "include_artifact_edges": self.include_artifact_edges,
            "include_cultural_features": self.include_cultural_features,
            "include_narrative_lineage": self.include_narrative_lineage,
            "include_teaching_edges": self.include_teaching_edges,
            "max_communicative_hops": self.max_communicative_hops,
            "mode": self.mode,
            "query_event_selector": self.query_event_selector,
            "transition_tick_resolution": self.transition_tick_resolution,
            "witness_definition": self.witness_definition,
        }


def example_historical_memory_layers_spec(
    *,
    max_communicative_hops: int = 2,
    witness_definition: str = "occurrence_participants",
    applicability: str = "all_tracked_sources",
) -> HistoricalMemoryLayersSpec:
    """Reference historical memory layers spec for tests and Experiment AM."""
    return HistoricalMemoryLayersSpec(
        max_communicative_hops=max_communicative_hops,
        witness_definition=witness_definition,
        applicability=applicability,
    )




_DURABLE_RECORD_GENRES: Final[frozenset[str]] = frozenset(
    {
        "warning",
        "instruction",
        "map",
        "story",
        "agreement",
        "inventory_record",
        "genealogy",
        "chronicle",
    }
)
_DURABLE_RECORDS_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_DURABLE_COPY_FIDELITY: Final[frozenset[str]] = frozenset(
    {"perfect", "deterministic_mutation", "lossy"}
)
_DURABLE_PERCEPTION_MODES: Final[frozenset[str]] = frozenset(
    {"marks_and_meta", "marks_only"}
)
_DURABLE_RECORDS_FORBIDDEN_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "canonical_archive",
        "true_history",
        "society_library",
        "verified_archive",
        "meaning",
        "interpretation",
        "truth",
        "verified",
        "canonical_history",
        "archive_must_persist",
        "true_history_restored",
    }
)


@dataclass(frozen=True, slots=True)
class DurableCopyFidelityPolicy:
    """Exact copy_fidelity_policy object under durable_records."""

    default_fidelity: str = "perfect"
    max_mark_edits: int = 2
    max_relation_edits: int = 1
    preserve_genre: bool = True
    copy_requires_hold_or_colocation: bool = True

    def __post_init__(self) -> None:
        fidelity = require_stable_id(
            "DurableCopyFidelityPolicy.default_fidelity", self.default_fidelity
        )
        if fidelity not in _DURABLE_COPY_FIDELITY:
            raise ValueError(
                f"unknown default_fidelity {fidelity!r} "
                "(code=durable_copy_fidelity_invalid)"
            )
        object.__setattr__(self, "default_fidelity", fidelity)
        marks = require_exact_nonneg_int("max_mark_edits", self.max_mark_edits)
        if marks > 32:
            raise ValueError(
                "max_mark_edits must be in [0, 32] "
                "(code=durable_max_mark_edits_invalid)"
            )
        object.__setattr__(self, "max_mark_edits", marks)
        relations = require_exact_nonneg_int(
            "max_relation_edits", self.max_relation_edits
        )
        if relations > 32:
            raise ValueError(
                "max_relation_edits must be in [0, 32] "
                "(code=durable_max_relation_edits_invalid)"
            )
        object.__setattr__(self, "max_relation_edits", relations)
        if type(self.preserve_genre) is not bool:
            raise TypeError("preserve_genre must be bool")
        if type(self.copy_requires_hold_or_colocation) is not bool:
            raise TypeError("copy_requires_hold_or_colocation must be bool")


@dataclass(frozen=True, slots=True)
class DurableIntegrityPolicy:
    """Exact integrity_policy object under durable_records."""

    allow_damage: bool = True
    allow_partial_loss: bool = True
    tombstone_on_destroy: bool = True
    partial_loss_min_marks_remaining: int = 0

    def __post_init__(self) -> None:
        if type(self.allow_damage) is not bool:
            raise TypeError("allow_damage must be bool")
        if type(self.allow_partial_loss) is not bool:
            raise TypeError("allow_partial_loss must be bool")
        if type(self.tombstone_on_destroy) is not bool:
            raise TypeError("tombstone_on_destroy must be bool")
        remaining = require_exact_nonneg_int(
            "partial_loss_min_marks_remaining",
            self.partial_loss_min_marks_remaining,
        )
        object.__setattr__(self, "partial_loss_min_marks_remaining", remaining)


@dataclass(frozen=True, slots=True)
class DurableAnnotationPolicy:
    """Exact annotation_policy object under durable_records."""

    max_annotations_per_record: int = 8
    annotations_survive_author_death: bool = True

    def __post_init__(self) -> None:
        max_ann = require_exact_nonneg_int(
            "max_annotations_per_record", self.max_annotations_per_record
        )
        if max_ann < 1:
            raise ValueError(
                "max_annotations_per_record must be >= 1 "
                "(code=durable_annotation_cap_invalid)"
            )
        object.__setattr__(self, "max_annotations_per_record", max_ann)
        if type(self.annotations_survive_author_death) is not bool:
            raise TypeError("annotations_survive_author_death must be bool")


@dataclass(frozen=True, slots=True)
class DurableLineagePolicy:
    """Exact lineage_policy object under durable_records."""

    max_copy_generation: int = 8
    track_source_on_edit: bool = True
    destroyed_parent_blocks_copy: bool = True

    def __post_init__(self) -> None:
        max_gen = require_exact_nonneg_int(
            "max_copy_generation", self.max_copy_generation
        )
        if max_gen < 1:
            raise ValueError(
                "max_copy_generation must be >= 1 "
                "(code=durable_copy_generation_cap_invalid)"
            )
        object.__setattr__(self, "max_copy_generation", max_gen)
        if type(self.track_source_on_edit) is not bool:
            raise TypeError("track_source_on_edit must be bool")
        if type(self.destroyed_parent_blocks_copy) is not bool:
            raise TypeError("destroyed_parent_blocks_copy must be bool")


@dataclass(frozen=True, slots=True)
class DurableRecordsSpec:
    """Opt-in durable records channel (runner-config-v33 sibling).

    Deepens owned ``cultural_historical_memory``. Absent object means durable
    channel off. Not an ``AgentCognitionSpec`` enum.
    """

    enabled_genres: tuple[str, ...]
    copy_fidelity_policy: DurableCopyFidelityPolicy = field(
        default_factory=DurableCopyFidelityPolicy
    )
    integrity_policy: DurableIntegrityPolicy = field(
        default_factory=DurableIntegrityPolicy
    )
    annotation_policy: DurableAnnotationPolicy = field(
        default_factory=DurableAnnotationPolicy
    )
    lineage_policy: DurableLineagePolicy = field(default_factory=DurableLineagePolicy)
    durable_records_mode: str = "deterministic"
    perception_mode: str = "marks_and_meta"
    rng_namespace: str = "durable_records"

    def __post_init__(self) -> None:
        mode = require_stable_id(
            "DurableRecordsSpec.durable_records_mode", self.durable_records_mode
        )
        if mode == "disabled":
            raise ValueError(
                "durable_records_mode=disabled is rejected; omit the object "
                "for off (code=durable_records_mode_invalid)"
            )
        if mode not in _DURABLE_RECORDS_MODE:
            raise ValueError(
                f"unknown durable_records_mode {mode!r} "
                "(code=durable_records_mode_invalid)"
            )
        object.__setattr__(self, "durable_records_mode", mode)

        if isinstance(self.enabled_genres, (str, bytes)) or not isinstance(
            self.enabled_genres, Sequence
        ):
            raise TypeError("enabled_genres must be a sequence")
        if not self.enabled_genres:
            raise ValueError(
                "enabled_genres must be non-empty when durable_records present "
                "(code=durable_genres_empty)"
            )
        genres: list[str] = []
        seen: set[str] = set()
        for raw in self.enabled_genres:
            genre = require_stable_id("DurableRecordsSpec.enabled_genres", raw)
            if genre not in _DURABLE_RECORD_GENRES:
                raise ValueError(
                    f"unknown durable record genre {genre!r} "
                    "(code=durable_genre_invalid)"
                )
            if genre in seen:
                raise ValueError(
                    f"duplicate enabled genre {genre!r} "
                    "(code=durable_genre_duplicate)"
                )
            seen.add(genre)
            genres.append(genre)
        object.__setattr__(self, "enabled_genres", tuple(genres))

        if type(self.copy_fidelity_policy) is not DurableCopyFidelityPolicy:
            raise TypeError(
                "copy_fidelity_policy must be DurableCopyFidelityPolicy"
            )
        if type(self.integrity_policy) is not DurableIntegrityPolicy:
            raise TypeError("integrity_policy must be DurableIntegrityPolicy")
        if type(self.annotation_policy) is not DurableAnnotationPolicy:
            raise TypeError("annotation_policy must be DurableAnnotationPolicy")
        if type(self.lineage_policy) is not DurableLineagePolicy:
            raise TypeError("lineage_policy must be DurableLineagePolicy")

        perception = require_stable_id(
            "DurableRecordsSpec.perception_mode", self.perception_mode
        )
        if perception not in _DURABLE_PERCEPTION_MODES:
            raise ValueError(
                f"unknown perception_mode {perception!r} "
                "(code=durable_perception_mode_invalid)"
            )
        object.__setattr__(self, "perception_mode", perception)
        namespace = require_stable_id(
            "DurableRecordsSpec.rng_namespace", self.rng_namespace
        )
        object.__setattr__(self, "rng_namespace", namespace)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "annotation_policy": {
                "annotations_survive_author_death": (
                    self.annotation_policy.annotations_survive_author_death
                ),
                "max_annotations_per_record": (
                    self.annotation_policy.max_annotations_per_record
                ),
            },
            "copy_fidelity_policy": {
                "copy_requires_hold_or_colocation": (
                    self.copy_fidelity_policy.copy_requires_hold_or_colocation
                ),
                "default_fidelity": self.copy_fidelity_policy.default_fidelity,
                "max_mark_edits": self.copy_fidelity_policy.max_mark_edits,
                "max_relation_edits": self.copy_fidelity_policy.max_relation_edits,
                "preserve_genre": self.copy_fidelity_policy.preserve_genre,
            },
            "durable_records_mode": self.durable_records_mode,
            "enabled_genres": list(self.enabled_genres),
            "integrity_policy": {
                "allow_damage": self.integrity_policy.allow_damage,
                "allow_partial_loss": self.integrity_policy.allow_partial_loss,
                "partial_loss_min_marks_remaining": (
                    self.integrity_policy.partial_loss_min_marks_remaining
                ),
                "tombstone_on_destroy": self.integrity_policy.tombstone_on_destroy,
            },
            "lineage_policy": {
                "destroyed_parent_blocks_copy": (
                    self.lineage_policy.destroyed_parent_blocks_copy
                ),
                "max_copy_generation": self.lineage_policy.max_copy_generation,
                "track_source_on_edit": self.lineage_policy.track_source_on_edit,
            },
            "perception_mode": self.perception_mode,
            "rng_namespace": self.rng_namespace,
        }


def example_durable_records_spec(
    *,
    default_fidelity: str = "perfect",
    perception_mode: str = "marks_and_meta",
) -> DurableRecordsSpec:
    """Reference durable records spec for tests and Experiment AN."""
    return DurableRecordsSpec(
        enabled_genres=tuple(sorted(_DURABLE_RECORD_GENRES)),
        copy_fidelity_policy=DurableCopyFidelityPolicy(
            default_fidelity=default_fidelity
        ),
        perception_mode=perception_mode,
    )




_KNOWLEDGE_REPOSITORIES_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_KNOWLEDGE_REPOSITORIES_ACCESS_MODES: Final[frozenset[str]] = frozenset(
    {"open", "colocated_only", "founder_list"}
)
_KNOWLEDGE_REPOSITORIES_PERCEPTION_MODES: Final[frozenset[str]] = frozenset(
    {"container_and_meta", "container_only"}
)
_KNOWLEDGE_REPOSITORIES_FORBIDDEN_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "library_institution",
        "global_archive",
        "society_library",
        "canonical_catalog",
        "true_history_index",
        "library",
        "archive",
        "sacred",
        "family_records",
        "trade_ledger",
        "librarian",
        "archivist",
        "library_must_form",
        "archive_must_persist",
        "true_catalog_restored",
    }
)


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoryAccessPolicy:
    """Exact access_policy object under knowledge_repositories."""

    default_access_mode: str = "open"
    deposit_requires_colocation: bool = True
    retrieve_requires_colocation: bool = True
    founder_list_survives_death: bool = True

    def __post_init__(self) -> None:
        mode = require_stable_id(
            "KnowledgeRepositoryAccessPolicy.default_access_mode",
            self.default_access_mode,
        )
        if mode not in _KNOWLEDGE_REPOSITORIES_ACCESS_MODES:
            raise ValueError(
                f"unknown default_access_mode {mode!r} "
                "(code=knowledge_repositories_access_mode_invalid)"
            )
        object.__setattr__(self, "default_access_mode", mode)
        if type(self.deposit_requires_colocation) is not bool:
            raise TypeError("deposit_requires_colocation must be bool")
        if type(self.retrieve_requires_colocation) is not bool:
            raise TypeError("retrieve_requires_colocation must be bool")
        if type(self.founder_list_survives_death) is not bool:
            raise TypeError("founder_list_survives_death must be bool")


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoryCapacityPolicy:
    """Exact capacity_policy object under knowledge_repositories."""

    max_repositories: int = 8
    max_members_per_repository: int = 32
    max_index_entries: int = 64

    def __post_init__(self) -> None:
        max_repos = require_exact_nonneg_int(
            "max_repositories", self.max_repositories
        )
        if max_repos < 1:
            raise ValueError(
                "max_repositories must be >= 1 "
                "(code=knowledge_repositories_capacity_invalid)"
            )
        object.__setattr__(self, "max_repositories", max_repos)
        max_members = require_exact_nonneg_int(
            "max_members_per_repository", self.max_members_per_repository
        )
        if max_members < 1:
            raise ValueError(
                "max_members_per_repository must be >= 1 "
                "(code=knowledge_repositories_capacity_invalid)"
            )
        object.__setattr__(self, "max_members_per_repository", max_members)
        max_index = require_exact_nonneg_int(
            "max_index_entries", self.max_index_entries
        )
        object.__setattr__(self, "max_index_entries", max_index)


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoryMaintenancePolicy:
    """Exact maintenance_policy object under knowledge_repositories."""

    neglect_ticks: int = 24
    allow_destruction: bool = True
    inaccessible_blocks_access: bool = True
    neglect_corrupts_index: bool = True

    def __post_init__(self) -> None:
        neglect = require_exact_nonneg_int("neglect_ticks", self.neglect_ticks)
        if neglect < 1:
            raise ValueError(
                "neglect_ticks must be >= 1 "
                "(code=knowledge_repositories_neglect_ticks_invalid)"
            )
        object.__setattr__(self, "neglect_ticks", neglect)
        if type(self.allow_destruction) is not bool:
            raise TypeError("allow_destruction must be bool")
        if type(self.inaccessible_blocks_access) is not bool:
            raise TypeError("inaccessible_blocks_access must be bool")
        if type(self.neglect_corrupts_index) is not bool:
            raise TypeError("neglect_corrupts_index must be bool")


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoryIndexPolicy:
    """Exact index_policy object under knowledge_repositories."""

    index_optional: bool = True
    max_entries_per_index_op: int = 4
    allow_corrupt_entries: bool = True

    def __post_init__(self) -> None:
        if type(self.index_optional) is not bool:
            raise TypeError("index_optional must be bool")
        max_op = require_exact_nonneg_int(
            "max_entries_per_index_op", self.max_entries_per_index_op
        )
        if max_op < 1:
            raise ValueError(
                "max_entries_per_index_op must be >= 1 "
                "(code=knowledge_repositories_index_op_invalid)"
            )
        object.__setattr__(self, "max_entries_per_index_op", max_op)
        if type(self.allow_corrupt_entries) is not bool:
            raise TypeError("allow_corrupt_entries must be bool")


@dataclass(frozen=True, slots=True)
class KnowledgeRepositoriesSpec:
    """Opt-in knowledge repositories channel (runner-config-v34 sibling).

    Deepens owned ``cultural_historical_memory``. Absent object means repository
    channel off. Not an ``AgentCognitionSpec`` enum. Requires durable_records.
    """

    access_policy: KnowledgeRepositoryAccessPolicy = field(
        default_factory=KnowledgeRepositoryAccessPolicy
    )
    capacity_policy: KnowledgeRepositoryCapacityPolicy = field(
        default_factory=KnowledgeRepositoryCapacityPolicy
    )
    maintenance_policy: KnowledgeRepositoryMaintenancePolicy = field(
        default_factory=KnowledgeRepositoryMaintenancePolicy
    )
    index_policy: KnowledgeRepositoryIndexPolicy = field(
        default_factory=KnowledgeRepositoryIndexPolicy
    )
    knowledge_repositories_mode: str = "deterministic"
    perception_mode: str = "container_and_meta"
    rng_namespace: str = "knowledge_repositories"

    def __post_init__(self) -> None:
        mode = require_stable_id(
            "KnowledgeRepositoriesSpec.knowledge_repositories_mode",
            self.knowledge_repositories_mode,
        )
        if mode == "disabled":
            raise ValueError(
                "knowledge_repositories_mode=disabled is rejected; omit the "
                "object for off (code=knowledge_repositories_mode_invalid)"
            )
        if mode not in _KNOWLEDGE_REPOSITORIES_MODE:
            raise ValueError(
                f"unknown knowledge_repositories_mode {mode!r} "
                "(code=knowledge_repositories_mode_invalid)"
            )
        object.__setattr__(self, "knowledge_repositories_mode", mode)
        if type(self.access_policy) is not KnowledgeRepositoryAccessPolicy:
            raise TypeError(
                "access_policy must be KnowledgeRepositoryAccessPolicy"
            )
        if type(self.capacity_policy) is not KnowledgeRepositoryCapacityPolicy:
            raise TypeError(
                "capacity_policy must be KnowledgeRepositoryCapacityPolicy"
            )
        if (
            type(self.maintenance_policy)
            is not KnowledgeRepositoryMaintenancePolicy
        ):
            raise TypeError(
                "maintenance_policy must be KnowledgeRepositoryMaintenancePolicy"
            )
        if type(self.index_policy) is not KnowledgeRepositoryIndexPolicy:
            raise TypeError("index_policy must be KnowledgeRepositoryIndexPolicy")
        perception = require_stable_id(
            "KnowledgeRepositoriesSpec.perception_mode", self.perception_mode
        )
        if perception not in _KNOWLEDGE_REPOSITORIES_PERCEPTION_MODES:
            raise ValueError(
                f"unknown perception_mode {perception!r} "
                "(code=knowledge_repositories_perception_mode_invalid)"
            )
        object.__setattr__(self, "perception_mode", perception)
        namespace = require_stable_id(
            "KnowledgeRepositoriesSpec.rng_namespace", self.rng_namespace
        )
        object.__setattr__(self, "rng_namespace", namespace)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "access_policy": {
                "default_access_mode": self.access_policy.default_access_mode,
                "deposit_requires_colocation": (
                    self.access_policy.deposit_requires_colocation
                ),
                "founder_list_survives_death": (
                    self.access_policy.founder_list_survives_death
                ),
                "retrieve_requires_colocation": (
                    self.access_policy.retrieve_requires_colocation
                ),
            },
            "capacity_policy": {
                "max_index_entries": self.capacity_policy.max_index_entries,
                "max_members_per_repository": (
                    self.capacity_policy.max_members_per_repository
                ),
                "max_repositories": self.capacity_policy.max_repositories,
            },
            "index_policy": {
                "allow_corrupt_entries": self.index_policy.allow_corrupt_entries,
                "index_optional": self.index_policy.index_optional,
                "max_entries_per_index_op": (
                    self.index_policy.max_entries_per_index_op
                ),
            },
            "knowledge_repositories_mode": self.knowledge_repositories_mode,
            "maintenance_policy": {
                "allow_destruction": self.maintenance_policy.allow_destruction,
                "inaccessible_blocks_access": (
                    self.maintenance_policy.inaccessible_blocks_access
                ),
                "neglect_corrupts_index": (
                    self.maintenance_policy.neglect_corrupts_index
                ),
                "neglect_ticks": self.maintenance_policy.neglect_ticks,
            },
            "perception_mode": self.perception_mode,
            "rng_namespace": self.rng_namespace,
        }


def example_knowledge_repositories_spec(
    *,
    default_access_mode: str = "open",
    perception_mode: str = "container_and_meta",
    neglect_ticks: int = 24,
) -> KnowledgeRepositoriesSpec:
    """Reference knowledge repositories spec for tests and Experiment AO."""
    return KnowledgeRepositoriesSpec(
        access_policy=KnowledgeRepositoryAccessPolicy(
            default_access_mode=default_access_mode
        ),
        maintenance_policy=KnowledgeRepositoryMaintenancePolicy(
            neglect_ticks=neglect_ticks
        ),
        perception_mode=perception_mode,
    )


_KNOWLEDGE_GENEALOGY_MODE: Final[frozenset[str]] = frozenset({"deterministic"})
_KNOWLEDGE_GENEALOGY_APPLICABILITY: Final[frozenset[str]] = frozenset(
    {"all_live_agents", "mid_run_new_agents", "lifecycle_learning_stage"}
)
_KNOWLEDGE_GENEALOGY_KINDS: Final[frozenset[str]] = frozenset(
    {
        "foraging_method",
        "healing_technique",
        "crafting_process",
        "navigation_knowledge",
        "building_method",
    }
)
_KNOWLEDGE_GENEALOGY_INDEPENDENT_ROOT_MATCH: Final[frozenset[str]] = frozenset(
    {"content_key", "content_key_and_kind"}
)
_KNOWLEDGE_GENEALOGY_MAX_HOP_DEPTH_CEILING: Final[int] = 32
_KNOWLEDGE_GENEALOGY_LINEAGE_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "max_entries_per_owner",
        "max_parent_ids",
        "max_hop_depth",
        "allow_multi_parent",
    }
)
_KNOWLEDGE_GENEALOGY_MUTATION_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "allow_mutation",
        "allow_combination",
        "mutation_distance_threshold",
        "max_token_edits",
        "mutation_requires_evidence",
        "min_token_overlap",
        "require_combination_distinct_roots",
    }
)
_KNOWLEDGE_GENEALOGY_UPTAKE_COMPOSE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "teaching",
        "imitation",
        "written_record",
        "reconstruction",
        "developmental",
        "independent_discovery",
    }
)
_KNOWLEDGE_GENEALOGY_QUERY_POLICY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "max_query_depth",
        "include_dead_holders",
        "independent_root_match",
    }
)
_KNOWLEDGE_GENEALOGY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "knowledge_genealogy_mode",
        "lineage_policy",
        "mutation_policy",
        "uptake_compose",
        "query_policy",
        "enabled_kinds",
        "applicability",
        "max_evidence_refs",
        "rng_namespace",
    }
)
_KNOWLEDGE_GENEALOGY_FORBIDDEN_ALIASES: Final[frozenset[str]] = frozenset(
    {
        "global_technique_registry",
        "society_encyclopedia",
        "true_method_catalog",
        "knowledge_pack",
        "parent_technique_copy",
        "technique_pack",
        "GlobalTechniqueRegistry",
        "GlobalKnowledge",
        "TechniqueRegistry",
        "technique_must_spread",
        "true_method_restored",
        "independent_discovery_forced",
    }
)


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyLineagePolicy:
    """Exact lineage_policy object under knowledge_genealogy."""

    max_entries_per_owner: int = 64
    max_parent_ids: int = 4
    max_hop_depth: int = 16
    allow_multi_parent: bool = True

    def __post_init__(self) -> None:
        max_entries = require_exact_nonneg_int(
            "max_entries_per_owner", self.max_entries_per_owner
        )
        if max_entries < 1:
            raise ValueError(
                "max_entries_per_owner must be >= 1 "
                "(code=knowledge_genealogy_max_entries_invalid)"
            )
        object.__setattr__(self, "max_entries_per_owner", max_entries)
        max_parents = require_exact_nonneg_int("max_parent_ids", self.max_parent_ids)
        if max_parents < 1:
            raise ValueError(
                "max_parent_ids must be >= 1 "
                "(code=knowledge_genealogy_max_parent_ids_invalid)"
            )
        object.__setattr__(self, "max_parent_ids", max_parents)
        depth = require_exact_nonneg_int("max_hop_depth", self.max_hop_depth)
        if depth < 1 or depth > _KNOWLEDGE_GENEALOGY_MAX_HOP_DEPTH_CEILING:
            raise ValueError(
                "max_hop_depth must be in "
                f"[1, {_KNOWLEDGE_GENEALOGY_MAX_HOP_DEPTH_CEILING}] "
                "(code=knowledge_genealogy_max_hop_invalid)"
            )
        object.__setattr__(self, "max_hop_depth", depth)
        if type(self.allow_multi_parent) is not bool:
            raise TypeError("allow_multi_parent must be bool")


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyMutationPolicy:
    """Exact mutation_policy object under knowledge_genealogy."""

    allow_mutation: bool = True
    allow_combination: bool = True
    mutation_distance_threshold: float = 0.15
    max_token_edits: int = 2
    mutation_requires_evidence: bool = True
    min_token_overlap: float = 0.25
    require_combination_distinct_roots: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_mutation) is not bool:
            raise TypeError("allow_mutation must be bool")
        if type(self.allow_combination) is not bool:
            raise TypeError("allow_combination must be bool")
        if type(self.mutation_requires_evidence) is not bool:
            raise TypeError("mutation_requires_evidence must be bool")
        if type(self.require_combination_distinct_roots) is not bool:
            raise TypeError("require_combination_distinct_roots must be bool")
        threshold = float(self.mutation_distance_threshold)
        if isinstance(self.mutation_distance_threshold, bool) or not isinstance(
            self.mutation_distance_threshold, (int, float)
        ):
            raise ValueError("mutation_distance_threshold: not_finite")
        if not math.isfinite(threshold) or threshold <= 0.0 or threshold > 1.0:
            raise ValueError(
                "mutation_distance_threshold must be in (0, 1] "
                "(code=knowledge_genealogy_mutation_threshold_invalid)"
            )
        object.__setattr__(self, "mutation_distance_threshold", threshold)
        edits = require_exact_nonneg_int("max_token_edits", self.max_token_edits)
        if edits > 8:
            raise ValueError(
                "max_token_edits must be in [0, 8] "
                "(code=knowledge_genealogy_max_token_edits_invalid)"
            )
        object.__setattr__(self, "max_token_edits", edits)
        overlap = float(self.min_token_overlap)
        if isinstance(self.min_token_overlap, bool) or not isinstance(
            self.min_token_overlap, (int, float)
        ):
            raise ValueError("min_token_overlap: not_finite")
        if not math.isfinite(overlap) or overlap < 0.0 or overlap > 1.0:
            raise ValueError(
                "min_token_overlap must be in [0, 1] "
                "(code=knowledge_genealogy_min_token_overlap_invalid)"
            )
        object.__setattr__(self, "min_token_overlap", overlap)


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyUptakeCompose:
    """Exact uptake_compose object under knowledge_genealogy."""

    teaching: bool = False
    imitation: bool = False
    written_record: bool = False
    reconstruction: bool = False
    developmental: bool = False
    independent_discovery: bool = False

    def __post_init__(self) -> None:
        for name in _KNOWLEDGE_GENEALOGY_UPTAKE_COMPOSE_KEYS:
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogyQueryPolicy:
    """Exact query_policy object under knowledge_genealogy."""

    max_query_depth: int = 32
    include_dead_holders: bool = True
    independent_root_match: str = "content_key"

    def __post_init__(self) -> None:
        depth = require_exact_nonneg_int("max_query_depth", self.max_query_depth)
        if depth < 1 or depth > _KINSHIP_MAX_QUERY_DEPTH_CEILING:
            raise ValueError(
                "max_query_depth must be in "
                f"[1, {_KINSHIP_MAX_QUERY_DEPTH_CEILING}] "
                "(code=knowledge_genealogy_max_query_depth_invalid)"
            )
        object.__setattr__(self, "max_query_depth", depth)
        if type(self.include_dead_holders) is not bool:
            raise TypeError("include_dead_holders must be bool")
        match = require_stable_id(
            "KnowledgeGenealogyQueryPolicy.independent_root_match",
            self.independent_root_match,
        )
        if match not in _KNOWLEDGE_GENEALOGY_INDEPENDENT_ROOT_MATCH:
            raise ValueError(
                f"unknown independent_root_match {match!r} "
                "(code=knowledge_genealogy_independent_root_match_invalid)"
            )
        object.__setattr__(self, "independent_root_match", match)


@dataclass(frozen=True, slots=True)
class KnowledgeGenealogySpec:
    """Opt-in knowledge genealogy channel (runner-config-v35 sibling).

    Deepens owned ``cultural_historical_memory``. Absent object means genealogy
    channel off. Not an ``AgentCognitionSpec`` enum. Requires cultural
    feature provenance; durable/repository remain optional compose sources.
    """

    enabled_kinds: tuple[str, ...]
    lineage_policy: KnowledgeGenealogyLineagePolicy = field(
        default_factory=KnowledgeGenealogyLineagePolicy
    )
    mutation_policy: KnowledgeGenealogyMutationPolicy = field(
        default_factory=KnowledgeGenealogyMutationPolicy
    )
    uptake_compose: KnowledgeGenealogyUptakeCompose = field(
        default_factory=KnowledgeGenealogyUptakeCompose
    )
    query_policy: KnowledgeGenealogyQueryPolicy = field(
        default_factory=KnowledgeGenealogyQueryPolicy
    )
    knowledge_genealogy_mode: str = "deterministic"
    applicability: str = "all_live_agents"
    max_evidence_refs: int = 8
    rng_namespace: str = "knowledge_genealogy"

    def __post_init__(self) -> None:
        mode = require_stable_id(
            "KnowledgeGenealogySpec.knowledge_genealogy_mode",
            self.knowledge_genealogy_mode,
        )
        if mode == "disabled":
            raise ValueError(
                "knowledge_genealogy_mode=disabled is rejected; omit the "
                "object for off (code=knowledge_genealogy_mode_invalid)"
            )
        if mode not in _KNOWLEDGE_GENEALOGY_MODE:
            raise ValueError(
                f"unknown knowledge_genealogy_mode {mode!r} "
                "(code=knowledge_genealogy_mode_invalid)"
            )
        object.__setattr__(self, "knowledge_genealogy_mode", mode)

        if isinstance(self.enabled_kinds, (str, bytes)) or not isinstance(
            self.enabled_kinds, Sequence
        ):
            raise TypeError("enabled_kinds must be a sequence")
        if not self.enabled_kinds:
            raise ValueError(
                "enabled_kinds must be non-empty when knowledge genealogy "
                "present (code=knowledge_genealogy_kinds_empty)"
            )
        kinds: list[str] = []
        seen_kinds: set[str] = set()
        for raw in self.enabled_kinds:
            kind = require_stable_id("KnowledgeGenealogySpec.enabled_kinds", raw)
            if kind not in _KNOWLEDGE_GENEALOGY_KINDS:
                raise ValueError(
                    f"unknown enabled kind {kind!r} "
                    "(code=knowledge_genealogy_kind_invalid)"
                )
            if kind in seen_kinds:
                raise ValueError(
                    f"duplicate enabled kind {kind!r} "
                    "(code=knowledge_genealogy_kind_duplicate)"
                )
            seen_kinds.add(kind)
            kinds.append(kind)
        object.__setattr__(self, "enabled_kinds", tuple(kinds))

        if type(self.lineage_policy) is not KnowledgeGenealogyLineagePolicy:
            raise TypeError(
                "lineage_policy must be KnowledgeGenealogyLineagePolicy"
            )
        if type(self.mutation_policy) is not KnowledgeGenealogyMutationPolicy:
            raise TypeError(
                "mutation_policy must be KnowledgeGenealogyMutationPolicy"
            )
        if type(self.uptake_compose) is not KnowledgeGenealogyUptakeCompose:
            raise TypeError(
                "uptake_compose must be KnowledgeGenealogyUptakeCompose"
            )
        if type(self.query_policy) is not KnowledgeGenealogyQueryPolicy:
            raise TypeError("query_policy must be KnowledgeGenealogyQueryPolicy")

        max_refs = require_exact_nonneg_int(
            "max_evidence_refs", self.max_evidence_refs
        )
        if max_refs < 1:
            raise ValueError(
                "max_evidence_refs must be >= 1 "
                "(code=knowledge_genealogy_max_evidence_refs_invalid)"
            )
        object.__setattr__(self, "max_evidence_refs", max_refs)

        applicability = require_stable_id(
            "KnowledgeGenealogySpec.applicability", self.applicability
        )
        if applicability not in _KNOWLEDGE_GENEALOGY_APPLICABILITY:
            raise ValueError(
                f"unknown applicability {applicability!r} "
                "(code=knowledge_genealogy_applicability_invalid)"
            )
        object.__setattr__(self, "applicability", applicability)
        namespace = require_stable_id(
            "KnowledgeGenealogySpec.rng_namespace", self.rng_namespace
        )
        object.__setattr__(self, "rng_namespace", namespace)

    def canonical_payload(self) -> dict[str, object]:
        return {
            "applicability": self.applicability,
            "enabled_kinds": list(self.enabled_kinds),
            "knowledge_genealogy_mode": self.knowledge_genealogy_mode,
            "lineage_policy": {
                "allow_multi_parent": self.lineage_policy.allow_multi_parent,
                "max_entries_per_owner": self.lineage_policy.max_entries_per_owner,
                "max_hop_depth": self.lineage_policy.max_hop_depth,
                "max_parent_ids": self.lineage_policy.max_parent_ids,
            },
            "max_evidence_refs": self.max_evidence_refs,
            "mutation_policy": {
                "allow_combination": self.mutation_policy.allow_combination,
                "allow_mutation": self.mutation_policy.allow_mutation,
                "max_token_edits": self.mutation_policy.max_token_edits,
                "min_token_overlap": self.mutation_policy.min_token_overlap,
                "mutation_distance_threshold": (
                    self.mutation_policy.mutation_distance_threshold
                ),
                "mutation_requires_evidence": (
                    self.mutation_policy.mutation_requires_evidence
                ),
                "require_combination_distinct_roots": (
                    self.mutation_policy.require_combination_distinct_roots
                ),
            },
            "query_policy": {
                "include_dead_holders": self.query_policy.include_dead_holders,
                "independent_root_match": self.query_policy.independent_root_match,
                "max_query_depth": self.query_policy.max_query_depth,
            },
            "rng_namespace": self.rng_namespace,
            "uptake_compose": {
                "developmental": self.uptake_compose.developmental,
                "imitation": self.uptake_compose.imitation,
                "independent_discovery": self.uptake_compose.independent_discovery,
                "reconstruction": self.uptake_compose.reconstruction,
                "teaching": self.uptake_compose.teaching,
                "written_record": self.uptake_compose.written_record,
            },
        }


def example_knowledge_genealogy_spec(
    *,
    enabled_kinds: tuple[str, ...] = (
        "foraging_method",
        "healing_technique",
        "crafting_process",
        "navigation_knowledge",
        "building_method",
    ),
    applicability: str = "all_live_agents",
    max_hop_depth: int = 16,
    independent_discovery: bool = False,
    teaching: bool = False,
) -> KnowledgeGenealogySpec:
    """Reference knowledge genealogy spec for tests and Experiment AP."""
    return KnowledgeGenealogySpec(
        enabled_kinds=enabled_kinds,
        applicability=applicability,
        lineage_policy=KnowledgeGenealogyLineagePolicy(max_hop_depth=max_hop_depth),
        uptake_compose=KnowledgeGenealogyUptakeCompose(
            independent_discovery=independent_discovery,
            teaching=teaching,
        ),
    )


def example_population_lifecycle_spec(
    *,
    lifespan_ticks: int = 20,
    max_population: int = 8,
    policy_id: str = "disabled",
) -> PopulationLifecycleSpec:
    """Deterministic reference spec for tests and catalog arms."""
    thresholds = (
        LifecycleStageThreshold(LifecycleStageId("infant"), 2),
        LifecycleStageThreshold(LifecycleStageId("juvenile"), 5),
        LifecycleStageThreshold(LifecycleStageId("adult"), max(lifespan_ticks - 1, 5)),
    )
    if policy_id == "disabled":
        params: Mapping[str, object] = {}
    elif policy_id == "fixed_interval_entry":
        params = {
            "interval_ticks": 5,
            "entries_per_interval": 1,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "generation_index": 1,
            "spawn_location_id": "loc-1",
        }
    else:
        raise ValueError(f"unknown policy_id {policy_id!r}")
    return PopulationLifecycleSpec(
        lifespan_ticks=lifespan_ticks,
        stage_thresholds=thresholds,
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id=policy_id,
        demographic_policy_params=params,
        max_population=max_population,
        natural_death_on_lifespan=True,
    )


def example_developmental_lifecycle_spec(
    *,
    lifespan_ticks: int = 24,
    max_population: int = 4,
    policy_id: str = "disabled",
    intra_stage_interpolation: bool = False,
    min_assigned_ticks: int = 16,
) -> PopulationLifecycleSpec:
    """Reference v26 developmental stages (opaque example ids, no authority).

    Stage ids ``dependent`` / ``learning`` / ``independent`` / ``elder`` are
    configurable labels only — ELDER grants no social authority.
    """
    if min_assigned_ticks > lifespan_ticks:
        raise ValueError("min_assigned_ticks must be <= lifespan_ticks")
    # Build demographic params from a lifespan that fits the infant/juvenile/adult
    # reference thresholds, then replace with developmental stages.
    base = example_population_lifecycle_spec(
        lifespan_ticks=max(lifespan_ticks, 20),
        max_population=max_population,
        policy_id=policy_id,
    )
    final_max = max(lifespan_ticks - 1, 3)
    if lifespan_ticks >= 20:
        caps = (2, 5, 12, final_max)
    else:
        caps = (
            max(final_max // 4, 0),
            max(final_max // 2, 1),
            max((3 * final_max) // 4, 2),
            final_max,
        )
    fixed_caps: list[int] = []
    previous = -1
    for cap in caps:
        value = max(int(cap), previous + 1)
        fixed_caps.append(value)
        previous = value
    if fixed_caps[-1] < final_max:
        fixed_caps[-1] = final_max
    if fixed_caps[-1] <= fixed_caps[-2]:
        # Extremely short lifespan: collapse to three progressive edges then final.
        fixed_caps = [0, 1, 2, final_max]
        previous = -1
        rebuilt: list[int] = []
        for cap in fixed_caps:
            value = max(cap, previous + 1)
            rebuilt.append(value)
            previous = value
        if rebuilt[-1] < final_max:
            rebuilt[-1] = final_max
        fixed_caps = rebuilt
    thresholds = (
        LifecycleStageThreshold(LifecycleStageId("dependent"), fixed_caps[0]),
        LifecycleStageThreshold(LifecycleStageId("learning"), fixed_caps[1]),
        LifecycleStageThreshold(LifecycleStageId("independent"), fixed_caps[2]),
        LifecycleStageThreshold(LifecycleStageId("elder"), fixed_caps[3]),
    )
    effects = (
        StageCapabilityEffect(
            stage_id=LifecycleStageId("dependent"),
            physical_capacity_factor=0.5,
            learning_rate_factor=0.8,
            fatigue_accrual_factor=1.2,
            denied_command_kinds=("attack", "harvest"),
        ),
        StageCapabilityEffect(
            stage_id=LifecycleStageId("learning"),
            physical_capacity_factor=0.8,
            learning_rate_factor=1.2,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        ),
        StageCapabilityEffect(
            stage_id=LifecycleStageId("independent"),
            physical_capacity_factor=1.0,
            learning_rate_factor=1.0,
            fatigue_accrual_factor=1.0,
            denied_command_kinds=(),
        ),
        StageCapabilityEffect(
            stage_id=LifecycleStageId("elder"),
            physical_capacity_factor=0.7,
            learning_rate_factor=0.9,
            fatigue_accrual_factor=1.1,
            denied_command_kinds=(),
        ),
    )
    return PopulationLifecycleSpec(
        lifespan_ticks=lifespan_ticks,
        stage_thresholds=thresholds,
        dependent_until_stage=LifecycleStageId("learning"),
        demographic_policy_id=base.demographic_policy_id,
        demographic_policy_params=dict(base.demographic_policy_params),
        max_population=base.max_population,
        natural_death_on_lifespan=True,
        stage_capability_effects=effects,
        gradual_aging=GradualAgingSpec(
            intra_stage_interpolation=intra_stage_interpolation
        ),
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="uniform_int",
            params={
                "min_ticks": min_assigned_ticks,
                "max_ticks": lifespan_ticks,
            },
        ),
    )


BOOTSTRAP_LIFECYCLE_COHORT_ID: Final[str] = "cohort-bootstrap"
BOOTSTRAP_LIFECYCLE_GENERATION_INDEX: Final[int] = 0


def seed_bootstrap_lifecycle_records(
    *,
    registrations: Sequence[AgentRegistration],
    spec: PopulationLifecycleSpec,
    run_config: object | None = None,
    run_id: str | None = None,
    world_id: str | None = None,
) -> tuple[AgentLifecycleRecord, ...]:
    """Seed lifecycle records for bootstrap roster (no created/entered events)."""
    from simulation.lifespan_distribution import assign_lifespan_ticks
    from simulation.models import SimulationRunConfig

    if type(spec) is not PopulationLifecycleSpec:
        raise TypeError("spec must be PopulationLifecycleSpec")
    if run_config is not None and type(run_config) is not SimulationRunConfig:
        raise TypeError("run_config must be SimulationRunConfig or None")
    stage = resolve_lifecycle_stage(0, spec.stage_thresholds)
    dependency = resolve_dependency_status(
        stage,
        spec.dependent_until_stage,
        stage_order=spec.stage_order,
    )
    records: list[AgentLifecycleRecord] = []
    for registration in registrations:
        if type(registration) is not AgentRegistration:
            raise TypeError("registrations entries must be AgentRegistration")
        assigned = assign_lifespan_ticks(
            spec=spec,
            run_config=run_config,  # type: ignore[arg-type]
            run_id=run_id,
            world_id=world_id,
            agent_id=registration.agent_id.value,
            entry_tick=0,
        )
        records.append(
            AgentLifecycleRecord(
                body_id=registration.entity_id,
                agent_id=registration.agent_id.value,
                entry_tick=0,
                stage=stage,
                dependency_status=dependency,
                generation_index=BOOTSTRAP_LIFECYCLE_GENERATION_INDEX,
                cohort_id=BOOTSTRAP_LIFECYCLE_COHORT_ID,
                provenance=OriginProvenance.BOOTSTRAP,
                assigned_lifespan_ticks=assigned,
            )
        )
    _LOGGER.debug(
        "bootstrap_lifecycle_records_seeded record_count=%s stage=%s "
        "dependency_status=%s distribution_id=%s",
        len(records),
        stage.value,
        dependency.value,
        spec.lifespan_distribution.distribution_id,
    )
    return tuple(records)


def seed_bootstrap_kinship_graph(
    *,
    spec: KinshipSpec,
    registered_agent_ids: Sequence[AgentId],
) -> object:
    """Seed objective kinship graph from bootstrap edges (no edge events)."""
    from world.kinship import (
        KinshipEdge,
        stable_kinship_edge_id,
        validate_bootstrap_edges,
    )

    if type(spec) is not KinshipSpec:
        raise TypeError("spec must be KinshipSpec")
    edges = tuple(
        KinshipEdge(
            parent_agent_id=edge.parent_agent_id,
            child_agent_id=edge.child_agent_id,
            established_tick=edge.established_tick,
            edge_id=stable_kinship_edge_id(
                parent_agent_id=edge.parent_agent_id,
                child_agent_id=edge.child_agent_id,
                established_tick=edge.established_tick,
            ),
        )
        for edge in spec.bootstrap_edges
    )
    graph = validate_bootstrap_edges(
        edges,
        registered_agent_ids=registered_agent_ids,
        max_parents_per_child=spec.max_parents_per_child,
    )
    _LOGGER.info(
        "bootstrap_kinship_graph_seeded edge_count=%s perception_mode=%s",
        len(graph.edges),
        spec.perception_mode,
    )
    return graph


class CognitionTraceDetail(StrEnum):
    """Closed detail levels for optional cognitive execution tracing."""

    SUMMARY = "summary"
    STRUCTURED = "structured"


@dataclass(frozen=True, slots=True)
class CognitionTraceSpec:
    """Optional run-level cognition trace recording (not a V2 capability flag).

    Default disabled. When disabled, ``detail`` / sampling / byte limits are
    ignored for behavior. Soft volume limits truncate with reason codes rather
    than failing the run (enforced by the sink in a later task).
    """

    enabled: bool = False
    detail: CognitionTraceDetail = CognitionTraceDetail.SUMMARY
    sample_every_n_ticks: int | None = None
    max_bytes_per_invocation: int | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("CognitionTraceSpec.enabled must be bool")
        if type(self.detail) is not CognitionTraceDetail:
            raise TypeError("CognitionTraceSpec.detail must be CognitionTraceDetail")
        if self.sample_every_n_ticks is not None:
            object.__setattr__(
                self,
                "sample_every_n_ticks",
                require_exact_nonneg_int(
                    "CognitionTraceSpec.sample_every_n_ticks",
                    self.sample_every_n_ticks,
                ),
            )
            if self.sample_every_n_ticks < 1:
                raise ValueError(
                    "CognitionTraceSpec.sample_every_n_ticks must be >= 1 "
                    "(code=invalid_sample_every)"
                )
        if self.max_bytes_per_invocation is not None:
            object.__setattr__(
                self,
                "max_bytes_per_invocation",
                require_exact_nonneg_int(
                    "CognitionTraceSpec.max_bytes_per_invocation",
                    self.max_bytes_per_invocation,
                ),
            )
            if self.max_bytes_per_invocation < 1:
                raise ValueError(
                    "CognitionTraceSpec.max_bytes_per_invocation must be >= 1 "
                    "(code=invalid_max_bytes)"
                )


class RunnerStopReasonCode(StrEnum):
    """Closed stop reasons evaluable at finalized committed boundaries."""

    MAX_TICKS = "max_ticks"
    ALL_AGENTS_TERMINAL = "all_agents_terminal"
    INJECTED_STOP = "injected_stop"
    CANCELLED = "cancelled"
    COGNITION_FAILURE = "cognition_failure"
    AUTHORITY_FAILURE = "authority_failure"
    FINALIZATION_RECOVERY_REQUIRED = "finalization_recovery_required"


class RunnerAttemptStatus(StrEnum):
    """Closed attempt receipt statuses for one tick orchestration attempt."""

    STARTED = "started"
    ABORTED = "aborted"
    COMMITTED_AWAITING_FINALIZATION = "committed_awaiting_finalization"
    RECOVERY_REQUIRED = "recovery_required"
    FINALIZED = "finalized"


@dataclass(frozen=True, slots=True)
class RunnerAttemptReceipt:
    """Immutable receipt for one tick attempt (not a final run result)."""

    tick: int
    status: RunnerAttemptStatus
    submission_count: int
    finalized_count: int
    stop_reason: RunnerStopReasonCode | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("RunnerAttemptReceipt.tick", self.tick),
        )
        if type(self.status) is not RunnerAttemptStatus:
            raise TypeError("status must be RunnerAttemptStatus")
        object.__setattr__(
            self,
            "submission_count",
            require_exact_nonneg_int(
                "RunnerAttemptReceipt.submission_count", self.submission_count
            ),
        )
        object.__setattr__(
            self,
            "finalized_count",
            require_exact_nonneg_int(
                "RunnerAttemptReceipt.finalized_count", self.finalized_count
            ),
        )
        if (
            self.stop_reason is not None
            and type(self.stop_reason) is not RunnerStopReasonCode
        ):
            raise TypeError("stop_reason must be RunnerStopReasonCode or None")


@dataclass(frozen=True, slots=True)
class CognitionCounters:
    """Aggregate cognition/imagination invocation counts for one run."""

    cognition_invocations: int = 0
    imagination_evaluations: int = 0
    imagined_future_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cognition_invocations",
            require_exact_nonneg_int(
                "CognitionCounters.cognition_invocations", self.cognition_invocations
            ),
        )
        object.__setattr__(
            self,
            "imagination_evaluations",
            require_exact_nonneg_int(
                "CognitionCounters.imagination_evaluations",
                self.imagination_evaluations,
            ),
        )
        object.__setattr__(
            self,
            "imagined_future_count",
            require_exact_nonneg_int(
                "CognitionCounters.imagined_future_count", self.imagined_future_count
            ),
        )


@dataclass(frozen=True, slots=True)
class ActionResolutionEvidence:
    """Detached public ActionResolution evidence (scientific, not for logs)."""

    ordinal: int
    agent_id: AgentId
    command_kind: str
    status: ActionResolutionStatus
    reason: ActionResolutionReason
    tick: int
    base_revision: int
    resulting_revision: int
    request_id: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("ActionResolutionEvidence.ordinal", self.ordinal),
        )
        if type(self.agent_id) is not AgentId:
            raise TypeError("ActionResolutionEvidence.agent_id must be AgentId")
        require_stable_id("ActionResolutionEvidence.command_kind", self.command_kind)
        if type(self.status) is not ActionResolutionStatus:
            raise TypeError("status must be ActionResolutionStatus")
        if type(self.reason) is not ActionResolutionReason:
            raise TypeError("reason must be ActionResolutionReason")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ActionResolutionEvidence.tick", self.tick),
        )
        object.__setattr__(
            self,
            "base_revision",
            require_exact_nonneg_int(
                "ActionResolutionEvidence.base_revision", self.base_revision
            ),
        )
        object.__setattr__(
            self,
            "resulting_revision",
            require_exact_nonneg_int(
                "ActionResolutionEvidence.resulting_revision", self.resulting_revision
            ),
        )
        require_stable_id("ActionResolutionEvidence.request_id", self.request_id)
        if self.resulting_revision < self.base_revision:
            raise ValueError("resulting_revision must be >= base_revision")


def detach_action_resolution_evidence(
    resolution: ActionResolution,
) -> ActionResolutionEvidence:
    """Project an ActionResolution into detached public evidence."""
    if type(resolution) is not ActionResolution:
        raise TypeError("detach_action_resolution_evidence requires ActionResolution")
    return ActionResolutionEvidence(
        ordinal=resolution.ordinal,
        agent_id=resolution.agent_id,
        command_kind=agent_command_tag(resolution.command),
        status=resolution.status,
        reason=resolution.reason,
        tick=resolution.tick.value,
        base_revision=resolution.base_revision.value,
        resulting_revision=resolution.resulting_revision.value,
        request_id=resolution.request_id.value,
    )


@dataclass(frozen=True, slots=True)
class BodyObjectiveFact:
    """Observable body facts for post-finalization goal evaluation."""

    entity_id: EntityId
    location_id: EntityId
    life_status: LifeStatus
    inventory: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if type(self.entity_id) is not EntityId:
            raise TypeError("BodyObjectiveFact.entity_id must be EntityId")
        if type(self.location_id) is not EntityId:
            raise TypeError("BodyObjectiveFact.location_id must be EntityId")
        if type(self.life_status) is not LifeStatus:
            raise TypeError("BodyObjectiveFact.life_status must be LifeStatus")
        if isinstance(self.inventory, (set, frozenset)):
            raise TypeError("inventory must be ordered")
        inventory = tuple(self.inventory)
        for item in inventory:
            if type(item) is not EntityId:
                raise TypeError("inventory entries must be EntityId")
        object.__setattr__(self, "inventory", inventory)


@dataclass(frozen=True, slots=True)
class DetachedObjectiveProjection:
    """Public hashable objective projection without WorldEngine access."""

    tick: int
    revision: int
    bodies: tuple[BodyObjectiveFact, ...]
    projection_version: str = OBJECTIVE_PROJECTION_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("DetachedObjectiveProjection.tick", self.tick),
        )
        object.__setattr__(
            self,
            "revision",
            require_exact_nonneg_int(
                "DetachedObjectiveProjection.revision", self.revision
            ),
        )
        if self.projection_version != OBJECTIVE_PROJECTION_VERSION:
            raise ValueError("unsupported objective projection_version")
        bodies = _copy_ordered(
            "DetachedObjectiveProjection.bodies",
            self.bodies,
            model_type=BodyObjectiveFact,
        )
        entity_ids = [body.entity_id for body in bodies]
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("body entity_ids must be unique")
        object.__setattr__(self, "bodies", bodies)


@dataclass(frozen=True, slots=True)
class FinalizedTickReceipt:
    """Detached receipt for one successfully finalized committed tick."""

    tick: int
    resulting_tick: int
    base_revision: int
    resulting_revision: int
    resolutions: tuple[ActionResolutionEvidence, ...]
    objective_state_hash: str
    event_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("FinalizedTickReceipt.tick", self.tick),
        )
        object.__setattr__(
            self,
            "resulting_tick",
            require_exact_nonneg_int(
                "FinalizedTickReceipt.resulting_tick", self.resulting_tick
            ),
        )
        if self.resulting_tick != self.tick + 1:
            raise ValueError("resulting_tick must be exactly tick + 1")
        object.__setattr__(
            self,
            "base_revision",
            require_exact_nonneg_int(
                "FinalizedTickReceipt.base_revision", self.base_revision
            ),
        )
        object.__setattr__(
            self,
            "resulting_revision",
            require_exact_nonneg_int(
                "FinalizedTickReceipt.resulting_revision", self.resulting_revision
            ),
        )
        if self.resulting_revision < self.base_revision:
            raise ValueError("resulting_revision must be >= base_revision")
        resolutions = _copy_ordered(
            "FinalizedTickReceipt.resolutions",
            self.resolutions,
            model_type=ActionResolutionEvidence,
        )
        object.__setattr__(self, "resolutions", resolutions)
        require_stable_id(
            "FinalizedTickReceipt.objective_state_hash", self.objective_state_hash
        )
        object.__setattr__(
            self,
            "event_count",
            require_exact_nonneg_int(
                "FinalizedTickReceipt.event_count", self.event_count
            ),
        )


class GoalTransitionReasonCode(StrEnum):
    """Closed reason codes for simulation-owned goal status transitions.

    Objective boundary evaluation emits ``COMPLETED`` / ``ABANDONED`` /
    ``DEATH`` / ``RUN_END``. Subjective GoalBoard commits may emit
    ``FAILED`` / ``SUSPENDED`` / ``RESUMED`` / ``DECOMPOSED`` / ``REVISED``
    (and ``ABANDONED``) when mapped into revision receipts.
    """

    COMPLETED = "completed"
    ABANDONED = "abandoned"
    DEATH = "death"
    RUN_END = "run_end"
    FAILED = "failed"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    DECOMPOSED = "decomposed"
    REVISED = "revised"


@dataclass(frozen=True, slots=True)
class GoalTransitionReceipt:
    """Immutable receipt for one post-finalization goal status transition."""

    goal_id: GoalId
    owner_id: AgentId
    outcome_kind: GoalOutcomeKind
    from_status: GoalStatus
    to_status: GoalStatus
    tick: int
    reason_code: GoalTransitionReasonCode

    def __post_init__(self) -> None:
        if type(self.goal_id) is not GoalId:
            raise TypeError("goal_id must be GoalId")
        if type(self.owner_id) is not AgentId:
            raise TypeError("owner_id must be AgentId")
        if type(self.outcome_kind) is not GoalOutcomeKind:
            raise TypeError("outcome_kind must be GoalOutcomeKind")
        if type(self.from_status) is not GoalStatus:
            raise TypeError("from_status must be GoalStatus")
        if type(self.to_status) is not GoalStatus:
            raise TypeError("to_status must be GoalStatus")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalTransitionReceipt.tick", self.tick),
        )
        if type(self.reason_code) is not GoalTransitionReasonCode:
            raise TypeError("reason_code must be GoalTransitionReasonCode")


@dataclass(frozen=True, slots=True)
class GoalEvaluationEvidence:
    """Observable evidence for deterministic post-finalization goal evaluation.

    Imagined ``GoalEffect`` values are never accepted as committed outcomes.
    """

    tick: int
    run_ending: bool
    owner_entity_ids: Mapping[str, str]
    bodies: tuple[BodyObjectiveFact, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("GoalEvaluationEvidence.tick", self.tick),
        )
        if type(self.run_ending) is not bool:
            raise TypeError("run_ending must be bool")
        if not isinstance(self.owner_entity_ids, Mapping):
            raise TypeError("owner_entity_ids must be a mapping")
        mapping = {str(key): str(value) for key, value in self.owner_entity_ids.items()}
        for key, value in mapping.items():
            require_stable_id("GoalEvaluationEvidence.owner_id", key)
            require_stable_id("GoalEvaluationEvidence.entity_id", value)
        object.__setattr__(self, "owner_entity_ids", mapping)
        object.__setattr__(
            self,
            "bodies",
            _copy_ordered(
                "GoalEvaluationEvidence.bodies",
                self.bodies,
                model_type=BodyObjectiveFact,
            ),
        )


@dataclass(frozen=True, slots=True)
class SimulationRunnerResult:
    """Final result after objective commit and all finalizations succeed."""

    run_id: object
    ticks_committed: int
    stop_reason: RunnerStopReasonCode
    attempt_receipts: tuple[RunnerAttemptReceipt, ...]
    finalized_tick_receipts: tuple[FinalizedTickReceipt, ...] = ()
    goal_transition_receipts: tuple[GoalTransitionReceipt, ...] = ()
    cognition_counters: CognitionCounters = CognitionCounters()
    final_objective_projection: DetachedObjectiveProjection | None = None
    objective_state_hash: str | None = None
    memory_dynamics_audits: tuple[object, ...] = ()
    offline_consolidation_audits: tuple[object, ...] = ()
    reflection_audits: tuple[object, ...] = ()
    world_model_audits: tuple[object, ...] = ()
    mind_audits: tuple[object, ...] = ()
    prospective_audits: tuple[object, ...] = ()
    counterfactual_audits: tuple[object, ...] = ()
    communication_intent_audits: tuple[object, ...] = ()
    cognitive_budget_audits: tuple[object, ...] = ()
    skill_audits: tuple[object, ...] = ()
    teaching_audits: tuple[object, ...] = ()
    developmental_acquisition_audits: tuple[object, ...] = ()
    mentorship_audits: tuple[object, ...] = ()
    cultural_feature_audits: tuple[object, ...] = ()
    practical_knowledge_audits: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        from simulation.models import RunId

        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        object.__setattr__(
            self,
            "ticks_committed",
            require_exact_nonneg_int(
                "SimulationRunnerResult.ticks_committed", self.ticks_committed
            ),
        )
        if type(self.stop_reason) is not RunnerStopReasonCode:
            raise TypeError("stop_reason must be RunnerStopReasonCode")
        if isinstance(self.attempt_receipts, (set, frozenset)):
            raise TypeError("attempt_receipts must be ordered")
        receipts = tuple(self.attempt_receipts)
        for item in receipts:
            if type(item) is not RunnerAttemptReceipt:
                raise TypeError("attempt_receipts entries must be RunnerAttemptReceipt")
        object.__setattr__(self, "attempt_receipts", receipts)
        object.__setattr__(
            self,
            "finalized_tick_receipts",
            _copy_ordered(
                "finalized_tick_receipts",
                self.finalized_tick_receipts,
                model_type=FinalizedTickReceipt,
            ),
        )
        object.__setattr__(
            self,
            "goal_transition_receipts",
            _copy_ordered(
                "goal_transition_receipts",
                self.goal_transition_receipts,
                model_type=GoalTransitionReceipt,
            ),
        )
        if type(self.cognition_counters) is not CognitionCounters:
            raise TypeError("cognition_counters must be CognitionCounters")
        if (
            self.final_objective_projection is not None
            and type(self.final_objective_projection) is not DetachedObjectiveProjection
        ):
            raise TypeError(
                "final_objective_projection must be DetachedObjectiveProjection or None"
            )
        if self.objective_state_hash is not None:
            require_stable_id("objective_state_hash", self.objective_state_hash)
        if isinstance(self.memory_dynamics_audits, (set, frozenset)):
            raise TypeError("memory_dynamics_audits must be ordered")
        object.__setattr__(
            self, "memory_dynamics_audits", tuple(self.memory_dynamics_audits)
        )
        if isinstance(self.offline_consolidation_audits, (set, frozenset)):
            raise TypeError("offline_consolidation_audits must be ordered")
        object.__setattr__(
            self,
            "offline_consolidation_audits",
            tuple(self.offline_consolidation_audits),
        )
        if isinstance(self.reflection_audits, (set, frozenset)):
            raise TypeError("reflection_audits must be ordered")
        object.__setattr__(
            self,
            "reflection_audits",
            tuple(self.reflection_audits),
        )
        if isinstance(self.world_model_audits, (set, frozenset)):
            raise TypeError("world_model_audits must be ordered")
        object.__setattr__(
            self,
            "world_model_audits",
            tuple(self.world_model_audits),
        )
        if isinstance(self.mind_audits, (set, frozenset)):
            raise TypeError("mind_audits must be ordered")
        object.__setattr__(
            self,
            "mind_audits",
            tuple(self.mind_audits),
        )
        if isinstance(self.prospective_audits, (set, frozenset)):
            raise TypeError("prospective_audits must be ordered")
        object.__setattr__(
            self,
            "prospective_audits",
            tuple(self.prospective_audits),
        )
        if isinstance(self.counterfactual_audits, (set, frozenset)):
            raise TypeError("counterfactual_audits must be ordered")
        object.__setattr__(
            self,
            "counterfactual_audits",
            tuple(self.counterfactual_audits),
        )
        if isinstance(self.cognitive_budget_audits, (set, frozenset)):
            raise TypeError("cognitive_budget_audits must be ordered")
        object.__setattr__(
            self,
            "cognitive_budget_audits",
            tuple(self.cognitive_budget_audits),
        )
        if isinstance(self.communication_intent_audits, (set, frozenset)):
            raise TypeError("communication_intent_audits must be ordered")
        from agents.cognition.communication_strategy import CommunicationIntentAudit

        audits = tuple(self.communication_intent_audits)
        for audit in audits:
            if type(audit) is not CommunicationIntentAudit:
                raise TypeError("communication_intent_audits: invalid_item")
        object.__setattr__(self, "communication_intent_audits", audits)
        if isinstance(self.skill_audits, (set, frozenset)):
            raise TypeError("skill_audits must be ordered")
        skill_rows = tuple(self.skill_audits)
        for row in skill_rows:
            if type(row) is not SkillAudit:
                raise TypeError("skill_audits: invalid_item")
        object.__setattr__(self, "skill_audits", skill_rows)
        if isinstance(self.teaching_audits, (set, frozenset)):
            raise TypeError("teaching_audits must be ordered")
        teaching_rows = tuple(self.teaching_audits)
        for row in teaching_rows:
            if type(row) is not TeachingAudit:
                raise TypeError("teaching_audits: invalid_item")
        object.__setattr__(self, "teaching_audits", teaching_rows)
        if isinstance(self.developmental_acquisition_audits, (set, frozenset)):
            raise TypeError("developmental_acquisition_audits must be ordered")
        from agents.cognition.developmental_learning import (
            DevelopmentalAcquisitionAudit,
        )

        developmental_rows = tuple(self.developmental_acquisition_audits)
        for row in developmental_rows:
            if type(row) is not DevelopmentalAcquisitionAudit:
                raise TypeError("developmental_acquisition_audits: invalid_item")
        object.__setattr__(
            self, "developmental_acquisition_audits", developmental_rows
        )
        if isinstance(self.mentorship_audits, (set, frozenset)):
            raise TypeError("mentorship_audits must be ordered")
        from agents.cognition.mentorship import MentorshipAudit

        mentorship_rows = tuple(self.mentorship_audits)
        for row in mentorship_rows:
            if type(row) is not MentorshipAudit:
                raise TypeError("mentorship_audits: invalid_item")
        object.__setattr__(self, "mentorship_audits", mentorship_rows)
        if isinstance(self.cultural_feature_audits, (set, frozenset)):
            raise TypeError("cultural_feature_audits must be ordered")
        from agents.cognition.cultural_features import CulturalFeatureAudit

        cultural_rows = tuple(self.cultural_feature_audits)
        for row in cultural_rows:
            if type(row) is not CulturalFeatureAudit:
                raise TypeError("cultural_feature_audits: invalid_item")
        object.__setattr__(self, "cultural_feature_audits", cultural_rows)
        if isinstance(self.practical_knowledge_audits, (set, frozenset)):
            raise TypeError("practical_knowledge_audits must be ordered")
        from agents.cognition.practical_knowledge import PracticalKnowledgeAudit

        pk_rows = tuple(self.practical_knowledge_audits)
        for row in pk_rows:
            if type(row) is not PracticalKnowledgeAudit:
                raise TypeError("practical_knowledge_audits: invalid_item")
        object.__setattr__(self, "practical_knowledge_audits", pk_rows)


class CognitionFailurePolicy(StrEnum):
    """Policy when one agent's cognition fails during a tick."""

    ABORT_TICK = "abort_tick"
    OMIT_FAILED_AGENT = "omit_failed_agent"


class RecordingPolicy(StrEnum):
    """LLM reproducibility policy for runner provider settings."""

    LIVE = "live"
    DETERMINISTIC_FAKE = "deterministic_fake"
    RECORD = "record"
    CACHE = "cache"
    REPLAY = "replay"


class ExactReproducibilityMode(StrEnum):
    """Whether exact reproduction is required for the run."""

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"


def _require_positive_int(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive int")
    return value


def _require_finite_float(
    name: str, value: object, *, minimum: float, maximum: float
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if number < minimum or number > maximum:
        raise ValueError(f"{name} out of range")
    return number


def _require_positive_float(name: str, value: object) -> float:
    return _require_finite_float(name, value, minimum=math.ulp(0.0), maximum=1e12)


def _copy_ordered(
    name: str, values: Sequence[object], *, model_type: type
) -> tuple[Any, ...]:
    if isinstance(values, (set, frozenset)):
        raise TypeError(f"{name} must be an ordered sequence")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{name} must be an ordered sequence")
    copied = tuple(values)
    for item in copied:
        if type(item) is not model_type:
            raise TypeError(f"{name} entries must be {model_type.__name__}")
    return copied


@dataclass(frozen=True, slots=True)
class DriveOverrideSpec:
    """Sparse override for one experiment-controlled drive disposition."""

    kind: DriveKind
    baseline: float | None = None
    sensitivity: float | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not DriveKind:
            raise TypeError("DriveOverrideSpec.kind must be DriveKind")
        if self.kind not in _OVERRIDEABLE_DRIVE_KINDS:
            raise ValueError("DriveOverrideSpec.kind is not overrideable")
        if self.baseline is None and self.sensitivity is None:
            raise ValueError("DriveOverrideSpec requires baseline or sensitivity")
        if self.baseline is not None:
            object.__setattr__(
                self,
                "baseline",
                _unit_interval("DriveOverrideSpec.baseline", self.baseline),
            )
        if self.sensitivity is not None:
            object.__setattr__(
                self,
                "sensitivity",
                _unit_interval("DriveOverrideSpec.sensitivity", self.sensitivity),
            )


@dataclass(frozen=True, slots=True)
class AgentCognitionSpec:
    """Per-agent cognition/memory/imagination/drive treatment."""

    agent_id: AgentId
    memory_mode: MemoryMode = MemoryMode.RECONSTRUCTIVE
    imagination_mode: ImaginationMode = ImaginationMode.ENABLED
    drive_overrides: tuple[DriveOverrideSpec, ...] = ()
    policy_version: str = COGNITION_POLICY_VERSION
    consolidation_mode: ConsolidationMode = ConsolidationMode.DISABLED
    reflection_mode: ReflectionMode = ReflectionMode.DISABLED
    prospective_mode: ProspectiveImaginationMode = ProspectiveImaginationMode.DISABLED
    counterfactual_mode: CounterfactualMode = CounterfactualMode.DISABLED
    communication_strategy_mode: CommunicationStrategyMode = (
        CommunicationStrategyMode.DISABLED
    )
    reputation_mode: ReputationMode = ReputationMode.DISABLED
    skill_learning_mode: SkillLearningMode = SkillLearningMode.DISABLED
    teaching_interaction_mode: TeachingInteractionMode = (
        TeachingInteractionMode.DISABLED
    )
    practice_rate: float = 0.02
    success_rate: float = 0.05
    failure_rate: float = 0.01
    instruction_rate: float = 0.04
    observation_rate: float = 0.01
    probability_gain: float = 0.50
    efficiency_gain: float = 0.50
    belief_practice_rate: float = 0.00
    belief_success_rate: float = 0.10
    belief_failure_rate: float = 0.00
    belief_instruction_rate: float = 0.08
    belief_observation_rate: float = 0.02
    belief_prior: float = 1.0
    belief_action_weight: float = 0.25
    demonstration_rate: float = 0.02
    practice_together_rate: float = 0.02
    offer_window: int = 8
    belief_explain_rate: float = 0.08
    explain_low_below: float = 0.34
    explain_high_at: float = 0.67
    teaching_response_weight: float = 0.25
    production_knowledge_mode: ProductionKnowledgeMode = (
        ProductionKnowledgeMode.DISABLED
    )
    production_catalog: ProductionCatalog = field(default_factory=ProductionCatalog)
    territorial_claim_mode: TerritorialClaimMode = TerritorialClaimMode.DISABLED
    group_formation_mode: GroupFormationMode = GroupFormationMode.DISABLED
    social_norm_mode: SocialNormMode = SocialNormMode.DISABLED
    social_convention_mode: SocialConventionMode = SocialConventionMode.DISABLED
    artifact_interpretation_mode: ArtifactInterpretationMode = (
        ArtifactInterpretationMode.DISABLED
    )
    semantic_naming_mode: SemanticNamingMode = SemanticNamingMode.DISABLED
    cultural_narrative_mode: CulturalNarrativeMode = CulturalNarrativeMode.DISABLED
    cognitive_budget_mode: CognitiveBudgetMode = CognitiveBudgetMode.DISABLED
    cognitive_budget_limits: CognitiveBudgetLimits | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentCognitionSpec.agent_id must be AgentId")
        if type(self.memory_mode) is not MemoryMode:
            raise TypeError("AgentCognitionSpec.memory_mode must be MemoryMode")
        if type(self.imagination_mode) is not ImaginationMode:
            raise TypeError(
                "AgentCognitionSpec.imagination_mode must be ImaginationMode"
            )
        if type(self.consolidation_mode) is not ConsolidationMode:
            raise TypeError(
                "AgentCognitionSpec.consolidation_mode must be ConsolidationMode"
            )
        if type(self.reflection_mode) is not ReflectionMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.reflection_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError("AgentCognitionSpec.reflection_mode must be ReflectionMode")
        if type(self.prospective_mode) is not ProspectiveImaginationMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.prospective_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.prospective_mode must be ProspectiveImaginationMode"
            )
        if type(self.counterfactual_mode) is not CounterfactualMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.counterfactual_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.counterfactual_mode must be CounterfactualMode"
            )
        if type(self.communication_strategy_mode) is not CommunicationStrategyMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.communication_strategy_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.communication_strategy_mode must be "
                "CommunicationStrategyMode"
            )
        if type(self.reputation_mode) is not ReputationMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.reputation_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError("AgentCognitionSpec.reputation_mode must be ReputationMode")
        if type(self.skill_learning_mode) is not SkillLearningMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.skill_learning_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.skill_learning_mode must be SkillLearningMode"
            )
        if type(self.teaching_interaction_mode) is not TeachingInteractionMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.teaching_interaction_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.teaching_interaction_mode must be "
                "TeachingInteractionMode"
            )
        if type(self.production_knowledge_mode) is not ProductionKnowledgeMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.production_knowledge_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.production_knowledge_mode must be "
                "ProductionKnowledgeMode"
            )
        if type(self.production_catalog) is not ProductionCatalog:
            raise TypeError(
                "AgentCognitionSpec.production_catalog must be ProductionCatalog"
            )
        if type(self.territorial_claim_mode) is not TerritorialClaimMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.territorial_claim_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.territorial_claim_mode must be TerritorialClaimMode"
            )
        if type(self.group_formation_mode) is not GroupFormationMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.group_formation_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.group_formation_mode must be GroupFormationMode"
            )
        if type(self.social_norm_mode) is not SocialNormMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.social_norm_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.social_norm_mode must be SocialNormMode"
            )
        if type(self.social_convention_mode) is not SocialConventionMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.social_convention_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.social_convention_mode must be "
                "SocialConventionMode"
            )
        if type(self.artifact_interpretation_mode) is not ArtifactInterpretationMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.artifact_interpretation_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.artifact_interpretation_mode must be "
                "ArtifactInterpretationMode"
            )
        if type(self.semantic_naming_mode) is not SemanticNamingMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.semantic_naming_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.semantic_naming_mode must be SemanticNamingMode"
            )
        if type(self.cultural_narrative_mode) is not CulturalNarrativeMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.cultural_narrative_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.cultural_narrative_mode must be "
                "CulturalNarrativeMode"
            )
        if type(self.cognitive_budget_mode) is not CognitiveBudgetMode:
            _LOGGER.error(
                "invalid_enum path=AgentCognitionSpec.cognitive_budget_mode "
                "reason_code=invalid_mode"
            )
            raise TypeError(
                "AgentCognitionSpec.cognitive_budget_mode must be CognitiveBudgetMode"
            )
        if self.cognitive_budget_mode is CognitiveBudgetMode.DISABLED:
            if self.cognitive_budget_limits is not None:
                _LOGGER.error(
                    "invalid_fields path=AgentCognitionSpec.cognitive_budget_limits "
                    "reason_code=limits_require_enforced"
                )
                raise ValueError(
                    "cognitive_budget_limits must be None when mode is DISABLED "
                    "(code=limits_require_enforced)"
                )
        elif self.cognitive_budget_limits is None:
            _LOGGER.error(
                "invalid_fields path=AgentCognitionSpec.cognitive_budget_limits "
                "reason_code=limits_required"
            )
            raise ValueError(
                "cognitive_budget_limits is required when mode is ENFORCED "
                "(code=limits_required)"
            )
        elif type(self.cognitive_budget_limits) is not CognitiveBudgetLimits:
            raise TypeError(
                "AgentCognitionSpec.cognitive_budget_limits must be "
                "CognitiveBudgetLimits or None"
            )
        if self.policy_version != COGNITION_POLICY_VERSION:
            raise ValueError("unsupported cognition policy_version")
        overrides = _copy_ordered(
            "AgentCognitionSpec.drive_overrides",
            self.drive_overrides,
            model_type=DriveOverrideSpec,
        )
        seen: set[DriveKind] = set()
        for override in overrides:
            if override.kind in seen:
                raise ValueError("DriveOverrideSpec kinds must be unique")
            seen.add(override.kind)
        object.__setattr__(self, "drive_overrides", overrides)

    def resolve_drive_profile(self) -> DriveProfile:
        """Build a complete owner-scoped profile with sparse overrides applied."""
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
        return DriveProfile(owner_id=self.agent_id, dispositions=tuple(dispositions))


@dataclass(frozen=True, slots=True)
class AgentRunnerSpec:
    """One registered agent with body ownership and cognition treatment."""

    agent_id: AgentId
    entity_id: EntityId
    cognition: AgentCognitionSpec
    name: str | None = None
    initial_goals: tuple[Goal, ...] = ()

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentRunnerSpec.agent_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("AgentRunnerSpec.entity_id must be EntityId")
        if type(self.cognition) is not AgentCognitionSpec:
            raise TypeError("AgentRunnerSpec.cognition must be AgentCognitionSpec")
        if self.cognition.agent_id != self.agent_id:
            raise ValueError("AgentRunnerSpec cognition.agent_id must match agent_id")
        resolved_name = self.agent_id.value if self.name is None else self.name
        object.__setattr__(
            self, "name", require_bounded_text("AgentRunnerSpec.name", resolved_name)
        )
        goals = _copy_ordered(
            "AgentRunnerSpec.initial_goals", self.initial_goals, model_type=Goal
        )
        seen: set[GoalId] = set()
        for goal in goals:
            if goal.owner_id != self.agent_id:
                raise ValueError("initial_goals owner_id must match agent_id")
            if goal.goal_id in seen:
                raise ValueError("initial_goals goal_id values must be unique")
            seen.add(goal.goal_id)
        object.__setattr__(self, "initial_goals", goals)

    def registration(self) -> AgentRegistration:
        return AgentRegistration(agent_id=self.agent_id, entity_id=self.entity_id)


@dataclass(frozen=True, slots=True)
class WorldScenarioSpec:
    """Replay-significant world topology and initial objective state."""

    world_id: WorldId
    revision: WorldRevision
    physical_rules: PhysicalRules
    locations: tuple[Location, ...]
    bodies: tuple[AgentBody, ...]
    items: tuple[Item, ...] = ()
    resources: tuple[Resource, ...] = ()
    weather: tuple[Weather, ...] = ()
    artifacts: tuple[InformationArtifact, ...] = ()

    def __post_init__(self) -> None:
        if type(self.world_id) is not WorldId:
            raise TypeError("WorldScenarioSpec.world_id must be WorldId")
        if type(self.revision) is not WorldRevision:
            raise TypeError("WorldScenarioSpec.revision must be WorldRevision")
        if type(self.physical_rules) is not PhysicalRules:
            raise TypeError("WorldScenarioSpec.physical_rules must be PhysicalRules")
        object.__setattr__(
            self,
            "locations",
            _copy_ordered(
                "WorldScenarioSpec.locations", self.locations, model_type=Location
            ),
        )
        object.__setattr__(
            self,
            "bodies",
            _copy_ordered(
                "WorldScenarioSpec.bodies", self.bodies, model_type=AgentBody
            ),
        )
        object.__setattr__(
            self,
            "items",
            _copy_ordered("WorldScenarioSpec.items", self.items, model_type=Item),
        )
        object.__setattr__(
            self,
            "resources",
            _copy_ordered(
                "WorldScenarioSpec.resources", self.resources, model_type=Resource
            ),
        )
        object.__setattr__(
            self,
            "weather",
            _copy_ordered(
                "WorldScenarioSpec.weather", self.weather, model_type=Weather
            ),
        )
        object.__setattr__(
            self,
            "artifacts",
            _copy_ordered(
                "WorldScenarioSpec.artifacts",
                self.artifacts,
                model_type=InformationArtifact,
            ),
        )
        if not self.locations:
            raise ValueError("WorldScenarioSpec.locations must be non-empty")
        if not self.bodies:
            raise ValueError("WorldScenarioSpec.bodies must be non-empty")
        body_ids = {body.entity_id for body in self.bodies}
        if len(body_ids) != len(self.bodies):
            raise ValueError("WorldScenarioSpec.bodies entity_ids must be unique")
        artifact_ids = {artifact.artifact_id for artifact in self.artifacts}
        if len(artifact_ids) != len(self.artifacts):
            raise ValueError("WorldScenarioSpec.artifacts artifact_ids must be unique")


@dataclass(frozen=True, slots=True)
class RunnerStopPolicy:
    """Closed stop evaluation policy for a configured run."""

    max_ticks: int
    stop_on_all_agents_terminal: bool = True
    allow_injected_stop: bool = True
    allow_cancellation: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_ticks",
            _require_positive_int("RunnerStopPolicy.max_ticks", self.max_ticks),
        )
        if type(self.stop_on_all_agents_terminal) is not bool:
            raise TypeError("stop_on_all_agents_terminal must be bool")
        if type(self.allow_injected_stop) is not bool:
            raise TypeError("allow_injected_stop must be bool")
        if type(self.allow_cancellation) is not bool:
            raise TypeError("allow_cancellation must be bool")


@dataclass(frozen=True, slots=True)
class RunnerCheckpointPolicy:
    """Durable checkpoint cadence. Cadence is in committed ticks."""

    enabled: bool = False
    cadence_ticks: int | None = None

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("RunnerCheckpointPolicy.enabled must be bool")
        if self.enabled:
            if self.cadence_ticks is None:
                raise ValueError("checkpoint cadence_ticks required when enabled")
            object.__setattr__(
                self,
                "cadence_ticks",
                _require_positive_int(
                    "RunnerCheckpointPolicy.cadence_ticks", self.cadence_ticks
                ),
            )
        elif self.cadence_ticks is not None:
            raise ValueError("checkpoint cadence_ticks forbidden when disabled")


@dataclass(frozen=True, slots=True)
class RunnerPersistenceSpec:
    """Whether the run is durable and how checkpoints are taken."""

    durable: bool = False
    checkpoint: RunnerCheckpointPolicy = RunnerCheckpointPolicy()

    def __post_init__(self) -> None:
        if type(self.durable) is not bool:
            raise TypeError("RunnerPersistenceSpec.durable must be bool")
        if type(self.checkpoint) is not RunnerCheckpointPolicy:
            raise TypeError("checkpoint must be RunnerCheckpointPolicy")
        if self.checkpoint.enabled and not self.durable:
            raise ValueError("checkpoints require durable persistence")


# Documented long-run cadence presets (opt-in; short-run default stays off).
LONG_RUN_CHECKPOINT_CADENCE_100: Final[int] = 100
LONG_RUN_CHECKPOINT_CADENCE_500: Final[int] = 500
LONG_RUN_CHECKPOINT_CADENCE_1000: Final[int] = 1000
LONG_RUN_CHECKPOINT_CADENCES: Final[tuple[int, ...]] = (
    LONG_RUN_CHECKPOINT_CADENCE_100,
    LONG_RUN_CHECKPOINT_CADENCE_500,
    LONG_RUN_CHECKPOINT_CADENCE_1000,
)


def long_run_checkpoint_policy(
    cadence_ticks: int = LONG_RUN_CHECKPOINT_CADENCE_100,
) -> RunnerCheckpointPolicy:
    """Enable durable checkpoints at a positive committed-tick cadence.

    Does **not** change short-run defaults. Callers must still set
    ``RunnerPersistenceSpec(durable=True, checkpoint=...)``. Never deletes
    snapshot rows — storage is bounded only by write cadence.

    Documented presets: 100 / 500 / 1000 committed ticks. Any positive int is
    accepted.
    """
    return RunnerCheckpointPolicy(
        enabled=True,
        cadence_ticks=_require_positive_int(
            "long_run_checkpoint_policy.cadence_ticks", cadence_ticks
        ),
    )


def long_run_persistence_spec(
    *,
    cadence_ticks: int = LONG_RUN_CHECKPOINT_CADENCE_100,
) -> RunnerPersistenceSpec:
    """Durable persistence with an opt-in long-run checkpoint cadence."""
    return RunnerPersistenceSpec(
        durable=True,
        checkpoint=long_run_checkpoint_policy(cadence_ticks),
    )


@dataclass(frozen=True, slots=True)
class RunnerProviderSettings:
    """Credential-free, fingerprintable LLM settings for a run.

    API keys and base URLs are resolved by an injected credential/provider
    resolver at construction time and never appear in this contract.
    """

    adapter_kind: ProviderAdapterKind = ProviderAdapterKind.DISABLED
    model: str | None = None
    structured_output_mode: StructuredOutputMode = StructuredOutputMode.JSON_SCHEMA
    temperature: float | None = None
    top_p: float | None = None
    provider_seed: int | None = None
    max_output_tokens: int | None = None
    stop_sequences: tuple[str, ...] = ()
    retry_count: int = 3
    per_attempt_timeout_seconds: float = 30.0
    total_deadline_seconds: float | None = None
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES
    max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES
    max_header_bytes: int = _DEFAULT_MAX_HEADER_BYTES
    send_correlation_header: bool = False
    recording_policy: RecordingPolicy = RecordingPolicy.DETERMINISTIC_FAKE
    exact_reproducibility: ExactReproducibilityMode = ExactReproducibilityMode.REQUIRED
    settings_version: str = PROVIDER_SETTINGS_VERSION

    def __post_init__(self) -> None:
        if type(self.adapter_kind) is not ProviderAdapterKind:
            raise TypeError("adapter_kind must be ProviderAdapterKind")
        if type(self.structured_output_mode) is not StructuredOutputMode:
            raise TypeError("structured_output_mode must be StructuredOutputMode")
        if type(self.recording_policy) is not RecordingPolicy:
            raise TypeError("recording_policy must be RecordingPolicy")
        if type(self.exact_reproducibility) is not ExactReproducibilityMode:
            raise TypeError("exact_reproducibility must be ExactReproducibilityMode")
        if self.settings_version != PROVIDER_SETTINGS_VERSION:
            raise ValueError("unsupported provider settings_version")
        if self.model is not None:
            require_stable_id("RunnerProviderSettings.model", self.model)
        if self.temperature is not None:
            object.__setattr__(
                self,
                "temperature",
                _require_finite_float(
                    "temperature", self.temperature, minimum=0.0, maximum=2.0
                ),
            )
        if self.top_p is not None:
            object.__setattr__(
                self,
                "top_p",
                _require_finite_float(
                    "top_p", self.top_p, minimum=math.ulp(0.0), maximum=1.0
                ),
            )
        if self.provider_seed is not None:
            object.__setattr__(
                self,
                "provider_seed",
                require_exact_nonneg_int("provider_seed", self.provider_seed),
            )
        if self.max_output_tokens is not None:
            object.__setattr__(
                self,
                "max_output_tokens",
                _require_positive_int("max_output_tokens", self.max_output_tokens),
            )
        stops = (
            _copy_ordered("stop_sequences", self.stop_sequences, model_type=str)
            if self.stop_sequences
            else ()
        )
        if len(stops) > 8:
            raise ValueError("stop_sequences exceeds maximum entries")
        for item in stops:
            if not item or item.strip() != item:
                raise ValueError("stop_sequences entries must be non-blank")
            if len(item) > 64:
                raise ValueError("stop_sequences entry exceeds maximum length")
        object.__setattr__(self, "stop_sequences", stops)
        object.__setattr__(
            self, "retry_count", _require_positive_int("retry_count", self.retry_count)
        )
        object.__setattr__(
            self,
            "per_attempt_timeout_seconds",
            _require_positive_float(
                "per_attempt_timeout_seconds", self.per_attempt_timeout_seconds
            ),
        )
        if self.total_deadline_seconds is not None:
            object.__setattr__(
                self,
                "total_deadline_seconds",
                _require_positive_float(
                    "total_deadline_seconds", self.total_deadline_seconds
                ),
            )
        object.__setattr__(
            self,
            "max_request_bytes",
            _require_positive_int("max_request_bytes", self.max_request_bytes),
        )
        object.__setattr__(
            self,
            "max_response_bytes",
            _require_positive_int("max_response_bytes", self.max_response_bytes),
        )
        object.__setattr__(
            self,
            "max_header_bytes",
            _require_positive_int("max_header_bytes", self.max_header_bytes),
        )
        if type(self.send_correlation_header) is not bool:
            raise TypeError("send_correlation_header must be bool")
        if self.exact_reproducibility is ExactReproducibilityMode.REQUIRED:
            if self.recording_policy is RecordingPolicy.LIVE:
                raise ValueError("exact_reproducibility_forbids_live")
            if self.recording_policy is RecordingPolicy.RECORD:
                raise ValueError("exact_reproducibility_forbids_record")
            if self.recording_policy is RecordingPolicy.CACHE:
                raise ValueError("exact_reproducibility_forbids_cache")
            if self.recording_policy not in {
                RecordingPolicy.DETERMINISTIC_FAKE,
                RecordingPolicy.REPLAY,
            }:
                raise ValueError(
                    f"exact_reproducibility_forbids_{self.recording_policy.value}"
                )
            if (
                self.recording_policy is RecordingPolicy.DETERMINISTIC_FAKE
                and self.adapter_kind is ProviderAdapterKind.OPENAI_COMPATIBLE
            ):
                raise ValueError("exact reproducibility forbids live external adapters")
        forbidden = {"api_key", "base_url", "endpoint", "authorization"}
        # Structural guard: dataclass has no credential fields by construction.
        for name in forbidden:
            if hasattr(self, name):
                raise ValueError(f"provider settings must not include {name}")


@dataclass(frozen=True, slots=True)
class ExperimentAssignmentRef:
    """Optional experiment condition/replicate identity for a run."""

    experiment_id: str
    condition_id: str
    replicate_index: int = 0
    seed_ordinal: int = 0

    def __post_init__(self) -> None:
        require_stable_id("experiment_id", self.experiment_id)
        require_stable_id("condition_id", self.condition_id)
        object.__setattr__(
            self,
            "replicate_index",
            require_exact_nonneg_int("replicate_index", self.replicate_index),
        )
        object.__setattr__(
            self,
            "seed_ordinal",
            require_exact_nonneg_int("seed_ordinal", self.seed_ordinal),
        )


@dataclass(frozen=True, slots=True)
class SimulationRunnerConfig:
    """Top-level immutable runner specification for one configured run.

    Durable ``RunId`` is assigned at construction/execution time and is not part
    of this replay-significant world/cognition specification. Paired arms share
    ``seed`` + ``stochastic_identity`` + scenario while varying cognition modes.
    """

    seed: int
    stochastic_identity: StochasticIdentity
    scenario: WorldScenarioSpec
    agents: tuple[AgentRunnerSpec, ...]
    stop_policy: RunnerStopPolicy
    mortality_mode: MortalityMode = MortalityMode.ENABLED
    cognition_failure_policy: CognitionFailurePolicy = CognitionFailurePolicy.ABORT_TICK
    provider: RunnerProviderSettings = RunnerProviderSettings()
    persistence: RunnerPersistenceSpec = RunnerPersistenceSpec()
    experiment: ExperimentAssignmentRef | None = None
    capability_flags: V2CapabilityFlags = V2CapabilityFlags()
    v3_capability_flags: V3CapabilityFlags = V3CapabilityFlags()
    cognition_trace: CognitionTraceSpec = CognitionTraceSpec()
    schema_version: str = RUNNER_SCHEMA_VERSION
    derivation_version: str = DERIVATION_VERSION_V3
    mortality_policy_version: str = MORTALITY_POLICY_VERSION
    environmental_dynamics: EnvironmentalDynamicsSpec | None = None
    artifacts_enabled: bool = False
    population_lifecycle: PopulationLifecycleSpec | None = None
    new_agent_initialization: object | None = None
    kinship: KinshipSpec | None = None
    dependency_care: DependencyCareSpec | None = None
    developmental_learning: DevelopmentalLearningSpec | None = None
    mentorship: MentorshipSpec | None = None
    cultural_feature_provenance: CulturalFeatureProvenanceSpec | None = None
    historical_memory_layers: HistoricalMemoryLayersSpec | None = None
    durable_records: DurableRecordsSpec | None = None
    knowledge_repositories: KnowledgeRepositoriesSpec | None = None
    knowledge_genealogy: KnowledgeGenealogySpec | None = None

    def __post_init__(self) -> None:
        # Late import avoids circular import with new_agent_initialization.
        from simulation.new_agent_initialization import (
            NewAgentInitializationSpec,
            default_new_agent_initialization_spec,
        )

        object.__setattr__(self, "seed", require_seed(self.seed))
        object.__setattr__(
            self,
            "stochastic_identity",
            require_stochastic_identity(self.stochastic_identity),
        )
        if type(self.artifacts_enabled) is not bool:
            raise TypeError("artifacts_enabled must be bool")
        if (
            self.population_lifecycle is not None
            and type(self.population_lifecycle) is not PopulationLifecycleSpec
        ):
            raise TypeError(
                "population_lifecycle must be PopulationLifecycleSpec or None"
            )
        if self.new_agent_initialization is not None and type(
            self.new_agent_initialization
        ) is not NewAgentInitializationSpec:
            raise TypeError(
                "new_agent_initialization must be NewAgentInitializationSpec or None"
            )
        if self.kinship is not None and type(self.kinship) is not KinshipSpec:
            raise TypeError("kinship must be KinshipSpec or None")
        if (
            self.dependency_care is not None
            and type(self.dependency_care) is not DependencyCareSpec
        ):
            raise TypeError("dependency_care must be DependencyCareSpec or None")
        if (
            self.developmental_learning is not None
            and type(self.developmental_learning) is not DevelopmentalLearningSpec
        ):
            raise TypeError(
                "developmental_learning must be DevelopmentalLearningSpec or None"
            )
        if self.mentorship is not None and type(self.mentorship) is not MentorshipSpec:
            raise TypeError("mentorship must be MentorshipSpec or None")
        if (
            self.cultural_feature_provenance is not None
            and type(self.cultural_feature_provenance)
            is not CulturalFeatureProvenanceSpec
        ):
            raise TypeError(
                "cultural_feature_provenance must be "
                "CulturalFeatureProvenanceSpec or None"
            )
        if (
            self.historical_memory_layers is not None
            and type(self.historical_memory_layers) is not HistoricalMemoryLayersSpec
        ):
            raise TypeError(
                "historical_memory_layers must be "
                "HistoricalMemoryLayersSpec or None"
            )
        if (
            self.durable_records is not None
            and type(self.durable_records) is not DurableRecordsSpec
        ):
            raise TypeError(
                "durable_records must be DurableRecordsSpec or None"
            )
        if (
            self.knowledge_repositories is not None
            and type(self.knowledge_repositories) is not KnowledgeRepositoriesSpec
        ):
            raise TypeError(
                "knowledge_repositories must be KnowledgeRepositoriesSpec or None"
            )
        if (
            self.knowledge_genealogy is not None
            and type(self.knowledge_genealogy) is not KnowledgeGenealogySpec
        ):
            raise TypeError(
                "knowledge_genealogy must be KnowledgeGenealogySpec or None"
            )
        if type(self.scenario) is not WorldScenarioSpec:
            raise TypeError("scenario must be WorldScenarioSpec")
        agents = _copy_ordered(
            "SimulationRunnerConfig.agents", self.agents, model_type=AgentRunnerSpec
        )
        if not agents:
            raise ValueError("agents must be non-empty")
        agent_ids = [agent.agent_id for agent in agents]
        entity_ids = [agent.entity_id for agent in agents]
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent_ids must be unique")
        if len(set(entity_ids)) != len(entity_ids):
            raise ValueError("entity_ids must be unique")
        body_ids = {body.entity_id for body in self.scenario.bodies}
        for agent in agents:
            if agent.entity_id not in body_ids:
                raise ValueError("agent entity_id must reference a scenario body")
        if set(entity_ids) != body_ids:
            raise ValueError("agents must cover scenario bodies exactly")
        object.__setattr__(self, "agents", agents)
        if self.kinship is not None:
            registered = {agent.agent_id for agent in agents}
            for edge in self.kinship.bootstrap_edges:
                if edge.parent_agent_id not in registered:
                    _LOGGER.error(
                        "kinship_bootstrap_unknown_agent role=parent agent=%s "
                        "reason_code=kinship_unknown_agent",
                        edge.parent_agent_id.value,
                    )
                    raise ValueError(
                        "kinship bootstrap parent unknown "
                        "(code=kinship_unknown_agent)"
                    )
                if edge.child_agent_id not in registered:
                    _LOGGER.error(
                        "kinship_bootstrap_unknown_agent role=child agent=%s "
                        "reason_code=kinship_unknown_agent",
                        edge.child_agent_id.value,
                    )
                    raise ValueError(
                        "kinship bootstrap child unknown "
                        "(code=kinship_unknown_agent)"
                    )
        if type(self.stop_policy) is not RunnerStopPolicy:
            raise TypeError("stop_policy must be RunnerStopPolicy")
        if type(self.mortality_mode) is not MortalityMode:
            raise TypeError("mortality_mode must be MortalityMode")
        if type(self.cognition_failure_policy) is not CognitionFailurePolicy:
            raise TypeError("cognition_failure_policy must be CognitionFailurePolicy")
        if type(self.provider) is not RunnerProviderSettings:
            raise TypeError("provider must be RunnerProviderSettings")
        if type(self.persistence) is not RunnerPersistenceSpec:
            raise TypeError("persistence must be RunnerPersistenceSpec")
        if (
            self.experiment is not None
            and type(self.experiment) is not ExperimentAssignmentRef
        ):
            raise TypeError("experiment must be ExperimentAssignmentRef or None")
        if type(self.capability_flags) is not V2CapabilityFlags:
            raise TypeError("capability_flags must be V2CapabilityFlags")
        if type(self.v3_capability_flags) is not V3CapabilityFlags:
            raise TypeError("v3_capability_flags must be V3CapabilityFlags")
        if type(self.cognition_trace) is not CognitionTraceSpec:
            raise TypeError("cognition_trace must be CognitionTraceSpec")
        if self.schema_version not in SUPPORTED_RUNNER_SCHEMA_VERSIONS:
            logging.getLogger("simulation.runner").error(
                "unsupported_schema_version schema_version=%s "
                "reason_code=unsupported_schema_version",
                self.schema_version,
            )
            raise ValueError("unsupported runner schema_version")
        if require_derivation_version(self.derivation_version) != DERIVATION_VERSION_V3:
            raise ValueError("runner config requires derivation-v3")
        if self.mortality_policy_version != MORTALITY_POLICY_VERSION:
            raise ValueError("unsupported mortality_policy_version")
        if (
            self.schema_version in {RUNNER_SCHEMA_VERSION_V1, RUNNER_SCHEMA_VERSION_V2}
            and self.capability_flags.any_enabled()
        ):
            raise ValueError(
                "capability flags require runner-config-v3+ "
                "(code=capability_requires_v3)"
            )
        _lifecycle_schemas = {
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            RUNNER_SCHEMA_VERSION_V33,
            RUNNER_SCHEMA_VERSION_V34,
            RUNNER_SCHEMA_VERSION_V35,
        }
        if (
            self.v3_capability_flags.generational_population
            and self.schema_version not in _lifecycle_schemas
        ):
            _LOGGER.error(
                "generational_population_requires_v24 schema_version=%s "
                "reason_code=generational_population_requires_v24",
                self.schema_version,
            )
            raise ValueError(
                "generational_population requires runner-config-v24, "
                "runner-config-v25, runner-config-v26, runner-config-v27, "
                "runner-config-v28, runner-config-v29, runner-config-v30, "
                "runner-config-v31, runner-config-v32, or runner-config-v33 "
                "(code=generational_population_requires_v24)"
            )
        _kinship_schemas = {
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            RUNNER_SCHEMA_VERSION_V33,
            RUNNER_SCHEMA_VERSION_V34,
            RUNNER_SCHEMA_VERSION_V35,
        }
        if self.v3_capability_flags.kinship_inheritance:
            if self.schema_version not in _kinship_schemas:
                _LOGGER.error(
                    "kinship_requires_v27 schema_version=%s "
                    "reason_code=kinship_requires_v27",
                    self.schema_version,
                )
                raise ValueError(
                    "kinship_inheritance requires runner-config-v27, "
                    "runner-config-v28, runner-config-v29, runner-config-v30, "
                    "runner-config-v31, or runner-config-v32 "
                    "(code=kinship_requires_v27)"
                )
            if self.kinship is None:
                _LOGGER.error(
                    "kinship_config_required schema_version=%s "
                    "reason_code=kinship_config_required",
                    self.schema_version,
                )
                raise ValueError(
                    "kinship_inheritance requires kinship config "
                    "(code=kinship_config_required)"
                )
        elif self.kinship is not None:
            _LOGGER.error(
                "kinship_config_without_flag schema_version=%s "
                "reason_code=kinship_config_without_flag",
                self.schema_version,
            )
            raise ValueError(
                "kinship config requires kinship_inheritance flag "
                "(code=kinship_config_without_flag)"
            )
        if self.dependency_care is not None:
            if self.schema_version not in {
                RUNNER_SCHEMA_VERSION_V28,
                RUNNER_SCHEMA_VERSION_V29,
                RUNNER_SCHEMA_VERSION_V30,
                RUNNER_SCHEMA_VERSION_V31,
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }:
                _LOGGER.error(
                    "dependency_care_requires_v28 schema_version=%s "
                    "reason_code=dependency_care_requires_v28",
                    self.schema_version,
                )
                raise ValueError(
                    "dependency_care requires runner-config-v28, "
                    "runner-config-v29, runner-config-v30, runner-config-v31, "
                    "or runner-config-v32 "
                    "(code=dependency_care_requires_v28)"
                )
            if not self.v3_capability_flags.generational_population:
                _LOGGER.error(
                    "dependency_care_without_lifecycle_flag schema_version=%s "
                    "reason_code=dependency_care_without_lifecycle_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "dependency_care requires generational_population "
                    "(code=dependency_care_without_lifecycle_flag)"
                )
            if self.population_lifecycle is None:
                _LOGGER.error(
                    "dependency_care_requires_lifecycle schema_version=%s "
                    "reason_code=dependency_care_requires_lifecycle",
                    self.schema_version,
                )
                raise ValueError(
                    "dependency_care requires population_lifecycle "
                    "(code=dependency_care_requires_lifecycle)"
                )
            _LOGGER.info(
                "dependency_care_schema_select schema_version=%s "
                "generational_population=%s enabled_needs=%s "
                "caregiving_cognition_mode=%s perception_mode=%s",
                self.schema_version,
                self.v3_capability_flags.generational_population,
                list(self.dependency_care.enabled_needs),
                self.dependency_care.caregiving_cognition_mode,
                self.dependency_care.perception_mode,
            )
        if self.developmental_learning is not None:
            if self.schema_version not in {
                RUNNER_SCHEMA_VERSION_V29,
                RUNNER_SCHEMA_VERSION_V30,
                RUNNER_SCHEMA_VERSION_V31,
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }:
                _LOGGER.error(
                    "developmental_learning_requires_v29 schema_version=%s "
                    "reason_code=developmental_learning_requires_v29",
                    self.schema_version,
                )
                raise ValueError(
                    "developmental_learning requires runner-config-v29, "
                    "runner-config-v30, runner-config-v31, or runner-config-v32 "
                    "(code=developmental_learning_requires_v29)"
                )
            if not self.v3_capability_flags.generational_population:
                _LOGGER.error(
                    "developmental_learning_without_lifecycle_flag "
                    "schema_version=%s "
                    "reason_code=developmental_learning_without_lifecycle_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "developmental_learning requires generational_population "
                    "(code=developmental_learning_without_lifecycle_flag)"
                )
            if self.population_lifecycle is None:
                _LOGGER.error(
                    "developmental_learning_requires_lifecycle schema_version=%s "
                    "reason_code=developmental_learning_requires_lifecycle",
                    self.schema_version,
                )
                raise ValueError(
                    "developmental_learning requires population_lifecycle "
                    "(code=developmental_learning_requires_lifecycle)"
                )
            _LOGGER.info(
                "developmental_learning_schema_select schema_version=%s "
                "generational_population=%s enabled_domains=%s "
                "enabled_sources=%s developmental_learning_mode=%s "
                "applicability=%s learner_species_defaults_id=%s",
                self.schema_version,
                self.v3_capability_flags.generational_population,
                list(self.developmental_learning.enabled_domains),
                list(self.developmental_learning.enabled_sources),
                self.developmental_learning.developmental_learning_mode,
                self.developmental_learning.applicability,
                self.developmental_learning.learner_species_defaults_id,
            )
        elif self.schema_version == RUNNER_SCHEMA_VERSION_V29:
            _LOGGER.error(
                "v29_requires_developmental_learning schema_version=%s "
                "reason_code=v29_requires_developmental_learning",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v29 requires developmental_learning "
                "(code=v29_requires_developmental_learning)"
            )
        if self.mentorship is not None:
            if self.schema_version not in {
                RUNNER_SCHEMA_VERSION_V30,
                RUNNER_SCHEMA_VERSION_V31,
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }:
                _LOGGER.error(
                    "mentorship_requires_v30 schema_version=%s "
                    "reason_code=mentorship_requires_v30",
                    self.schema_version,
                )
                raise ValueError(
                    "mentorship requires runner-config-v30, runner-config-v31, "
                    "or runner-config-v32 "
                    "(code=mentorship_requires_v30)"
                )
            if not self.v3_capability_flags.generational_population:
                _LOGGER.error(
                    "mentorship_without_lifecycle_flag schema_version=%s "
                    "reason_code=mentorship_without_lifecycle_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "mentorship requires generational_population "
                    "(code=mentorship_without_lifecycle_flag)"
                )
            if self.population_lifecycle is None:
                _LOGGER.error(
                    "mentorship_requires_lifecycle schema_version=%s "
                    "reason_code=mentorship_requires_lifecycle",
                    self.schema_version,
                )
                raise ValueError(
                    "mentorship requires population_lifecycle "
                    "(code=mentorship_requires_lifecycle)"
                )
            if self.mentorship.requires_teaching_interaction:
                missing = [
                    agent.agent_id.value
                    for agent in self.agents
                    if agent.cognition.teaching_interaction_mode
                    is not TeachingInteractionMode.DETERMINISTIC
                ]
                if missing:
                    _LOGGER.error(
                        "mentorship_requires_teaching agent_count=%s "
                        "reason_code=mentorship_requires_teaching",
                        len(missing),
                    )
                    raise ValueError(
                        "mentorship requires TeachingInteractionMode.DETERMINISTIC "
                        "on participants (code=mentorship_requires_teaching)"
                    )
            _LOGGER.info(
                "mentorship_schema_select schema_version=%s "
                "generational_population=%s content_kind_count=%s "
                "bond_policy_form_after=%s max_hop_depth=%s "
                "mentorship_mode=%s applicability=%s",
                self.schema_version,
                self.v3_capability_flags.generational_population,
                len(self.mentorship.enabled_content_kinds),
                self.mentorship.bond_policy.form_after_successful_acts,
                self.mentorship.lineage_policy.max_hop_depth,
                self.mentorship.mentorship_mode,
                self.mentorship.applicability,
            )
        elif self.schema_version == RUNNER_SCHEMA_VERSION_V30:
            _LOGGER.error(
                "v30_requires_mentorship schema_version=%s "
                "reason_code=v30_requires_mentorship",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v30 requires mentorship "
                "(code=v30_requires_mentorship)"
            )
        if self.cultural_feature_provenance is not None:
            if self.schema_version not in _HISTORICAL_MEMORY_CULTURAL_SCHEMAS:
                _LOGGER.error(
                    "cultural_feature_requires_v31 schema_version=%s "
                    "reason_code=cultural_feature_requires_v31",
                    self.schema_version,
                )
                raise ValueError(
                    "cultural_feature_provenance requires runner-config-v31, "
                    "runner-config-v32, runner-config-v33, "
                    "runner-config-v34, or runner-config-v35 "
                    "(code=cultural_feature_requires_v31)"
                )
            if not self.v3_capability_flags.cultural_historical_memory:
                _LOGGER.error(
                    "cultural_feature_without_flag schema_version=%s "
                    "reason_code=cultural_feature_without_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "cultural_feature_provenance requires "
                    "cultural_historical_memory "
                    "(code=cultural_feature_without_flag)"
                )
            _LOGGER.info(
                "cultural_feature_schema_select schema_version=%s "
                "feature_kind_count=%s channel_count=%s mutation_allowed=%s "
                "recombination_allowed=%s applicability=%s",
                self.schema_version,
                len(self.cultural_feature_provenance.enabled_feature_kinds),
                len(self.cultural_feature_provenance.enabled_provenance_channels),
                self.cultural_feature_provenance.mutation_policy.allow_mutation,
                self.cultural_feature_provenance.recombination_policy.allow_recombination,
                self.cultural_feature_provenance.applicability,
            )
        elif self.schema_version == RUNNER_SCHEMA_VERSION_V31:
            _LOGGER.error(
                "v31_requires_cultural_feature_provenance schema_version=%s "
                "reason_code=v31_requires_cultural_feature_provenance",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v31 requires cultural_feature_provenance "
                "(code=v31_requires_cultural_feature_provenance)"
            )
        elif (
            self.schema_version
            not in {
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }
            and self.v3_capability_flags.cultural_historical_memory
        ):
            _LOGGER.error(
                "cultural_feature_requires_flag schema_version=%s "
                "reason_code=cultural_feature_requires_flag",
                self.schema_version,
            )
            raise ValueError(
                "cultural_historical_memory requires cultural_feature_provenance "
                "(code=cultural_feature_requires_flag)"
            )
        if self.historical_memory_layers is not None:
            if self.schema_version not in _HISTORICAL_MEMORY_LAYER_SCHEMAS:
                _LOGGER.error(
                    "historical_memory_requires_v32 schema_version=%s "
                    "reason_code=historical_memory_requires_v32",
                    self.schema_version,
                )
                raise ValueError(
                    "historical_memory_layers requires runner-config-v32, "
                    "runner-config-v33, runner-config-v34, or "
                    "runner-config-v35 "
                    "(code=historical_memory_requires_v32)"
                )
            if not self.v3_capability_flags.cultural_historical_memory:
                _LOGGER.error(
                    "historical_memory_without_cultural_flag schema_version=%s "
                    "reason_code=historical_memory_without_cultural_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "historical_memory_layers requires "
                    "cultural_historical_memory "
                    "(code=historical_memory_without_cultural_flag)"
                )
            if self.cultural_feature_provenance is None:
                _LOGGER.error(
                    "historical_memory_requires_cultural_provenance "
                    "schema_version=%s "
                    "reason_code=historical_memory_requires_cultural_provenance",
                    self.schema_version,
                )
                raise ValueError(
                    "historical_memory_layers requires "
                    "cultural_feature_provenance "
                    "(code=historical_memory_requires_cultural_provenance)"
                )
            _LOGGER.info(
                "historical_memory_schema_select schema_version=%s "
                "max_communicative_hops=%s witness_definition=%s "
                "query_event_selector=%s transition_tick_resolution=%s "
                "applicability=%s",
                self.schema_version,
                self.historical_memory_layers.max_communicative_hops,
                self.historical_memory_layers.witness_definition,
                self.historical_memory_layers.query_event_selector,
                self.historical_memory_layers.transition_tick_resolution,
                self.historical_memory_layers.applicability,
            )
        elif self.schema_version == RUNNER_SCHEMA_VERSION_V32:
            _LOGGER.error(
                "v32_requires_historical_memory_layers schema_version=%s "
                "reason_code=v32_requires_historical_memory_layers",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v32 requires historical_memory_layers "
                "(code=v32_requires_historical_memory_layers)"
            )
        if self.knowledge_repositories is not None:
            if self.schema_version not in _KNOWLEDGE_REPOSITORIES_SCHEMAS:
                _LOGGER.error(
                    "knowledge_repositories_requires_v34 schema_version=%s "
                    "reason_code=knowledge_repositories_requires_v34",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_repositories requires runner-config-v34 or "
                    "runner-config-v35 "
                    "(code=knowledge_repositories_requires_v34)"
                )
            if not self.v3_capability_flags.cultural_historical_memory:
                _LOGGER.error(
                    "knowledge_repositories_without_cultural_flag "
                    "schema_version=%s "
                    "reason_code=knowledge_repositories_without_cultural_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_repositories requires "
                    "cultural_historical_memory "
                    "(code=knowledge_repositories_without_cultural_flag)"
                )
            if self.cultural_feature_provenance is None:
                _LOGGER.error(
                    "knowledge_repositories_requires_cultural_provenance "
                    "schema_version=%s "
                    "reason_code=knowledge_repositories_requires_cultural_provenance",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_repositories requires "
                    "cultural_feature_provenance "
                    "(code=knowledge_repositories_requires_cultural_provenance)"
                )
            if self.durable_records is None:
                _LOGGER.error(
                    "knowledge_repositories_requires_durable_records "
                    "schema_version=%s "
                    "reason_code=knowledge_repositories_requires_durable_records",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_repositories requires durable_records "
                    "(code=knowledge_repositories_requires_durable_records)"
                )
            _LOGGER.info(
                "knowledge_repositories_schema_select schema_version=%s "
                "default_access_mode=%s max_repositories=%s "
                "neglect_ticks=%s perception_mode=%s",
                self.schema_version,
                self.knowledge_repositories.access_policy.default_access_mode,
                self.knowledge_repositories.capacity_policy.max_repositories,
                self.knowledge_repositories.maintenance_policy.neglect_ticks,
                self.knowledge_repositories.perception_mode,
            )
        if self.durable_records is not None:
            if self.schema_version not in _DURABLE_RECORDS_SCHEMAS:
                _LOGGER.error(
                    "durable_records_requires_v33 schema_version=%s "
                    "reason_code=durable_records_requires_v33",
                    self.schema_version,
                )
                raise ValueError(
                    "durable_records requires runner-config-v33, "
                    "runner-config-v34, or runner-config-v35 "
                    "(code=durable_records_requires_v33)"
                )
            if not self.v3_capability_flags.cultural_historical_memory:
                _LOGGER.error(
                    "durable_records_without_cultural_flag schema_version=%s "
                    "reason_code=durable_records_without_cultural_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "durable_records requires cultural_historical_memory "
                    "(code=durable_records_without_cultural_flag)"
                )
            if self.cultural_feature_provenance is None:
                _LOGGER.error(
                    "durable_records_requires_cultural_provenance "
                    "schema_version=%s "
                    "reason_code=durable_records_requires_cultural_provenance",
                    self.schema_version,
                )
                raise ValueError(
                    "durable_records requires cultural_feature_provenance "
                    "(code=durable_records_requires_cultural_provenance)"
                )
            _LOGGER.info(
                "durable_records_schema_select schema_version=%s "
                "genre_count=%s default_fidelity=%s "
                "tombstone_on_destroy=%s perception_mode=%s",
                self.schema_version,
                len(self.durable_records.enabled_genres),
                self.durable_records.copy_fidelity_policy.default_fidelity,
                self.durable_records.integrity_policy.tombstone_on_destroy,
                self.durable_records.perception_mode,
            )
        elif self.schema_version == RUNNER_SCHEMA_VERSION_V33:
            _LOGGER.error(
                "v33_requires_durable_records schema_version=%s "
                "reason_code=v33_requires_durable_records",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v33 requires durable_records "
                "(code=v33_requires_durable_records)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V34:
            if self.durable_records is None:
                _LOGGER.error(
                    "v34_requires_durable_records schema_version=%s "
                    "reason_code=v34_requires_durable_records",
                    self.schema_version,
                )
                raise ValueError(
                    "runner-config-v34 requires durable_records "
                    "(code=v34_requires_durable_records)"
                )
            if self.knowledge_repositories is None:
                _LOGGER.error(
                    "v34_requires_knowledge_repositories schema_version=%s "
                    "reason_code=v34_requires_knowledge_repositories",
                    self.schema_version,
                )
                raise ValueError(
                    "runner-config-v34 requires knowledge_repositories "
                    "(code=v34_requires_knowledge_repositories)"
                )
        if self.knowledge_genealogy is not None:
            if self.schema_version not in _KNOWLEDGE_GENEALOGY_SCHEMAS:
                _LOGGER.error(
                    "knowledge_genealogy_requires_v35 schema_version=%s "
                    "reason_code=knowledge_genealogy_requires_v35",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_genealogy requires runner-config-v35 "
                    "(code=knowledge_genealogy_requires_v35)"
                )
            if not self.v3_capability_flags.cultural_historical_memory:
                _LOGGER.error(
                    "knowledge_genealogy_without_cultural_flag "
                    "schema_version=%s "
                    "reason_code=knowledge_genealogy_without_cultural_flag",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_genealogy requires "
                    "cultural_historical_memory "
                    "(code=knowledge_genealogy_without_cultural_flag)"
                )
            if self.cultural_feature_provenance is None:
                _LOGGER.error(
                    "knowledge_genealogy_requires_cultural_provenance "
                    "schema_version=%s "
                    "reason_code=knowledge_genealogy_requires_cultural_provenance",
                    self.schema_version,
                )
                raise ValueError(
                    "knowledge_genealogy requires "
                    "cultural_feature_provenance "
                    "(code=knowledge_genealogy_requires_cultural_provenance)"
                )
            _LOGGER.info(
                "knowledge_genealogy_schema_select schema_version=%s "
                "kind_count=%s max_entries=%s max_hop_depth=%s "
                "allow_mutation=%s allow_combination=%s applicability=%s",
                self.schema_version,
                len(self.knowledge_genealogy.enabled_kinds),
                self.knowledge_genealogy.lineage_policy.max_entries_per_owner,
                self.knowledge_genealogy.lineage_policy.max_hop_depth,
                self.knowledge_genealogy.mutation_policy.allow_mutation,
                self.knowledge_genealogy.mutation_policy.allow_combination,
                self.knowledge_genealogy.applicability,
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V35:
            if self.cultural_feature_provenance is None:
                _LOGGER.error(
                    "v35_requires_cultural_provenance schema_version=%s "
                    "reason_code=v35_requires_cultural_provenance",
                    self.schema_version,
                )
                raise ValueError(
                    "runner-config-v35 requires cultural_feature_provenance "
                    "(code=v35_requires_cultural_provenance)"
                )
            if self.knowledge_genealogy is None:
                _LOGGER.error(
                    "v35_requires_knowledge_genealogy schema_version=%s "
                    "reason_code=v35_requires_knowledge_genealogy",
                    self.schema_version,
                )
                raise ValueError(
                    "runner-config-v35 requires knowledge_genealogy "
                    "(code=v35_requires_knowledge_genealogy)"
                )
        other_v3_enabled = tuple(
            name
            for name in self.v3_capability_flags.enabled_names()
            if name not in _V3_OWNED_CAPABILITY_FLAGS
        )
        if other_v3_enabled and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
            RUNNER_SCHEMA_VERSION_V28,
            RUNNER_SCHEMA_VERSION_V29,
            RUNNER_SCHEMA_VERSION_V30,
            RUNNER_SCHEMA_VERSION_V31,
            RUNNER_SCHEMA_VERSION_V32,
            RUNNER_SCHEMA_VERSION_V33,
            RUNNER_SCHEMA_VERSION_V34,
            RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "v3_capability_requires_v23 schema_version=%s "
                "flag_count=%s reason_code=v3_capability_requires_v23",
                self.schema_version,
                len(other_v3_enabled),
            )
            raise ValueError(
                "V3 capability flags require runner-config-v23+ "
                "(code=v3_capability_requires_v23)"
            )
        _v27_or_v28_kinship_only = (
            self.schema_version in _kinship_schemas
            and self.v3_capability_flags.kinship_inheritance
            and not self.v3_capability_flags.generational_population
        )
        if _v27_or_v28_kinship_only:
            if self.population_lifecycle is not None:
                _LOGGER.error(
                    "kinship_only_forbids_lifecycle_spec schema_version=%s "
                    "reason_code=kinship_only_forbids_lifecycle_spec",
                    self.schema_version,
                )
                raise ValueError(
                    "kinship-only v27/v28 forbids population_lifecycle "
                    "(code=kinship_only_forbids_lifecycle_spec)"
                )
            if self.new_agent_initialization is not None:
                _LOGGER.error(
                    "kinship_only_forbids_new_agent_init schema_version=%s "
                    "reason_code=kinship_only_forbids_new_agent_init",
                    self.schema_version,
                )
                raise ValueError(
                    "kinship-only v27/v28 forbids new_agent_initialization "
                    "(code=kinship_only_forbids_new_agent_init)"
                )
            if self.dependency_care is not None:
                raise ValueError(
                    "dependency_care requires generational_population "
                    "(code=dependency_care_without_lifecycle_flag)"
                )
            if self.developmental_learning is not None:
                raise ValueError(
                    "developmental_learning requires generational_population "
                    "(code=developmental_learning_without_lifecycle_flag)"
                )
            if self.mentorship is not None:
                raise ValueError(
                    "mentorship requires generational_population "
                    "(code=mentorship_without_lifecycle_flag)"
                )
        _cultural_only = (
            self.schema_version in _HISTORICAL_MEMORY_CULTURAL_SCHEMAS
            and self.v3_capability_flags.cultural_historical_memory
            and not self.v3_capability_flags.generational_population
        )
        if _cultural_only:
            if self.population_lifecycle is not None:
                _LOGGER.error(
                    "cultural_only_forbids_lifecycle_spec schema_version=%s "
                    "reason_code=cultural_only_forbids_lifecycle_spec",
                    self.schema_version,
                )
                raise ValueError(
                    "cultural-only v31/v32/v33/v34/v35 forbids "
                    "population_lifecycle "
                    "(code=cultural_only_forbids_lifecycle_spec)"
                )
            if self.new_agent_initialization is not None:
                _LOGGER.error(
                    "cultural_only_forbids_new_agent_init schema_version=%s "
                    "reason_code=cultural_only_forbids_new_agent_init",
                    self.schema_version,
                )
                raise ValueError(
                    "cultural-only v31/v32/v33/v34/v35 forbids "
                    "new_agent_initialization "
                    "(code=cultural_only_forbids_new_agent_init)"
                )
            if self.dependency_care is not None:
                raise ValueError(
                    "dependency_care requires generational_population "
                    "(code=dependency_care_without_lifecycle_flag)"
                )
            if self.developmental_learning is not None:
                raise ValueError(
                    "developmental_learning requires generational_population "
                    "(code=developmental_learning_without_lifecycle_flag)"
                )
            if self.mentorship is not None:
                raise ValueError(
                    "mentorship requires generational_population "
                    "(code=mentorship_without_lifecycle_flag)"
                )
        if self.schema_version in _lifecycle_schemas:
            requires_lifecycle = (
                self.schema_version
                not in {
                    RUNNER_SCHEMA_VERSION_V27,
                    RUNNER_SCHEMA_VERSION_V28,
                    RUNNER_SCHEMA_VERSION_V29,
                    RUNNER_SCHEMA_VERSION_V30,
                    RUNNER_SCHEMA_VERSION_V31,
                    RUNNER_SCHEMA_VERSION_V32,
                    RUNNER_SCHEMA_VERSION_V33,
                    RUNNER_SCHEMA_VERSION_V34,
                    RUNNER_SCHEMA_VERSION_V35,
                }
                or self.v3_capability_flags.generational_population
            )
            if requires_lifecycle and self.population_lifecycle is None:
                if self.schema_version == RUNNER_SCHEMA_VERSION_V33:
                    code = "v33_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V32:
                    code = "v32_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V31:
                    code = "v31_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V30:
                    code = "v30_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V29:
                    code = "v29_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V28:
                    code = "v28_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V27:
                    code = "v27_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V26:
                    code = "v26_requires_population_lifecycle"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V25:
                    code = "v25_requires_population_lifecycle"
                else:
                    code = "v24_requires_population_lifecycle"
                _LOGGER.error(
                    "%s schema_version=%s reason_code=%s",
                    code,
                    self.schema_version,
                    code,
                )
                raise ValueError(
                    f"{self.schema_version} requires population_lifecycle "
                    f"(code={code})"
                )
        elif self.population_lifecycle is not None:
            _LOGGER.error(
                "population_lifecycle_requires_v24 schema_version=%s "
                "reason_code=population_lifecycle_requires_v24",
                self.schema_version,
            )
            raise ValueError(
                "population_lifecycle requires runner-config-v24+ "
                "(code=population_lifecycle_requires_v24)"
            )
        if (
            self.v3_capability_flags.generational_population
            and self.population_lifecycle is None
        ):
            raise ValueError(
                "generational_population requires population_lifecycle "
                "(code=generational_population_requires_lifecycle_spec)"
            )
        if (
            self.population_lifecycle is not None
            and self.population_lifecycle.has_developmental_extensions()
            and self.schema_version
            not in {
                RUNNER_SCHEMA_VERSION_V26,
                RUNNER_SCHEMA_VERSION_V27,
                RUNNER_SCHEMA_VERSION_V28,
                RUNNER_SCHEMA_VERSION_V29,
                RUNNER_SCHEMA_VERSION_V30,
                RUNNER_SCHEMA_VERSION_V31,
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }
        ):
            _LOGGER.error(
                "developmental_stages_require_v26 schema_version=%s "
                "reason_code=developmental_stages_require_v26",
                self.schema_version,
            )
            raise ValueError(
                "developmental stage extensions require runner-config-v26+ "
                "(code=developmental_stages_require_v26)"
            )
        _requires_new_agent_init = self.schema_version in {
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
        } or (
            self.schema_version
            in {
                RUNNER_SCHEMA_VERSION_V27,
                RUNNER_SCHEMA_VERSION_V28,
                RUNNER_SCHEMA_VERSION_V29,
                RUNNER_SCHEMA_VERSION_V30,
                RUNNER_SCHEMA_VERSION_V31,
                RUNNER_SCHEMA_VERSION_V32,
                RUNNER_SCHEMA_VERSION_V33,
                RUNNER_SCHEMA_VERSION_V34,
                RUNNER_SCHEMA_VERSION_V35,
            }
            and self.v3_capability_flags.generational_population
        )
        if _requires_new_agent_init:
            if self.new_agent_initialization is None:
                if self.schema_version == RUNNER_SCHEMA_VERSION_V33:
                    code = "v33_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V32:
                    code = "v32_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V31:
                    code = "v31_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V30:
                    code = "v30_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V29:
                    code = "v29_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V28:
                    code = "v28_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V27:
                    code = "v27_requires_new_agent_initialization"
                elif self.schema_version == RUNNER_SCHEMA_VERSION_V26:
                    code = "v26_requires_new_agent_initialization"
                else:
                    code = "v25_requires_new_agent_initialization"
                _LOGGER.error(
                    "%s schema_version=%s reason_code=%s",
                    code,
                    self.schema_version,
                    code,
                )
                raise ValueError(
                    f"{self.schema_version} requires new_agent_initialization "
                    f"(code={code})"
                )
        elif self.new_agent_initialization is not None:
            default_init = default_new_agent_initialization_spec()
            is_default = (
                type(self.new_agent_initialization) is NewAgentInitializationSpec
                and self.new_agent_initialization.canonical_payload()
                == default_init.canonical_payload()
            )
            if self.schema_version != RUNNER_SCHEMA_VERSION_V24 or not is_default:
                _LOGGER.error(
                    "new_agent_initialization_requires_v25 schema_version=%s "
                    "reason_code=new_agent_initialization_requires_v25",
                    self.schema_version,
                )
                raise ValueError(
                    "new_agent_initialization requires runner-config-v25+ "
                    "(code=new_agent_initialization_requires_v25)"
                )
        if (
            self.schema_version
            in {
                RUNNER_SCHEMA_VERSION_V1,
                RUNNER_SCHEMA_VERSION_V2,
                RUNNER_SCHEMA_VERSION_V3,
            }
            and self.cognition_trace.enabled
        ):
            raise ValueError(
                "cognition_trace.enabled requires runner-config-v4 "
                "(code=cognition_trace_requires_v4)"
            )
        if self.schema_version in {
            RUNNER_SCHEMA_VERSION_V1,
            RUNNER_SCHEMA_VERSION_V2,
            RUNNER_SCHEMA_VERSION_V3,
        }:
            _LOGGER.warning(
                "runner_config_legacy_schema schema_version=%s agent_count=%s",
                self.schema_version,
                len(self.agents),
            )
        enabled = self.capability_flags.enabled_names()
        if enabled:
            _LOGGER.info(
                "runner_config_capability_flags_enabled schema_version=%s "
                "flag_count=%s flag_names=%s",
                self.schema_version,
                len(enabled),
                ",".join(enabled),
            )
        v3_enabled = self.v3_capability_flags.enabled_names()
        if v3_enabled:
            _LOGGER.info(
                "runner_config_v3_capability_flags_enabled schema_version=%s "
                "flag_count=%s flag_names=%s",
                self.schema_version,
                len(v3_enabled),
                ",".join(v3_enabled),
            )
        _LOGGER.debug(
            "runner_config_v3_capability_flags schema_version=%s "
            "flag_names=%s flag_values=%s",
            self.schema_version,
            ",".join(_V3_CAPABILITY_FLAG_NAMES),
            ",".join(
                str(getattr(self.v3_capability_flags, name)).lower()
                for name in _V3_CAPABILITY_FLAG_NAMES
            ),
        )
        consolidation_modes = tuple(
            agent.cognition.consolidation_mode for agent in self.agents
        )
        non_disabled = tuple(
            mode
            for mode in consolidation_modes
            if mode is not ConsolidationMode.DISABLED
        )
        consolidation_schemas = {
            RUNNER_SCHEMA_VERSION_V5,
            RUNNER_SCHEMA_VERSION_V6,
            RUNNER_SCHEMA_VERSION_V7,
            RUNNER_SCHEMA_VERSION_V8,
            RUNNER_SCHEMA_VERSION_V9,
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if non_disabled and self.schema_version not in consolidation_schemas:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.consolidation_mode "
                "reason_code=consolidation_mode_requires_v5 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled consolidation_mode requires runner-config-v5, "
                "runner-config-v6, runner-config-v7, runner-config-v8, "
                "runner-config-v9, runner-config-v10, runner-config-v11, "
                "or runner-config-v12 "
                "(code=consolidation_mode_requires_v5)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V5 and not non_disabled:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v5_requires_consolidation schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v5 requires a non-disabled consolidation_mode "
                "(code=v5_requires_consolidation)"
            )
        reflection_modes = tuple(
            agent.cognition.reflection_mode for agent in self.agents
        )
        reflecting = tuple(
            mode for mode in reflection_modes if mode is not ReflectionMode.DISABLED
        )
        reflection_schemas = {
            RUNNER_SCHEMA_VERSION_V6,
            RUNNER_SCHEMA_VERSION_V7,
            RUNNER_SCHEMA_VERSION_V8,
            RUNNER_SCHEMA_VERSION_V9,
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if reflecting and self.schema_version not in reflection_schemas:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.reflection_mode "
                "reason_code=reflection_mode_requires_v6 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled reflection_mode requires runner-config-v6, "
                "runner-config-v7, runner-config-v8, runner-config-v9, "
                "runner-config-v10, runner-config-v11, or runner-config-v12 "
                "(code=reflection_mode_requires_v6)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V6 and not reflecting:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v6_requires_reflection schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v6 requires a non-disabled reflection_mode "
                "(code=v6_requires_reflection)"
            )
        prospective_modes = tuple(
            agent.cognition.prospective_mode for agent in self.agents
        )
        planning = tuple(
            mode
            for mode in prospective_modes
            if mode is not ProspectiveImaginationMode.DISABLED
        )
        prospective_schemas = {
            RUNNER_SCHEMA_VERSION_V7,
            RUNNER_SCHEMA_VERSION_V8,
            RUNNER_SCHEMA_VERSION_V9,
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if planning and self.schema_version not in prospective_schemas:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.prospective_mode "
                "reason_code=prospective_mode_requires_v7 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled prospective_mode requires runner-config-v7, "
                "runner-config-v8, runner-config-v9, runner-config-v10, "
                "runner-config-v11, or runner-config-v12 "
                "(code=prospective_mode_requires_v7)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V7 and not planning:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v7_requires_prospective schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v7 requires a non-disabled prospective_mode "
                "(code=v7_requires_prospective)"
            )
        counterfactual_modes = tuple(
            agent.cognition.counterfactual_mode for agent in self.agents
        )
        considering = tuple(
            mode
            for mode in counterfactual_modes
            if mode is not CounterfactualMode.DISABLED
        )
        counterfactual_schemas = {
            RUNNER_SCHEMA_VERSION_V8,
            RUNNER_SCHEMA_VERSION_V9,
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if considering and self.schema_version not in counterfactual_schemas:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.counterfactual_mode "
                "reason_code=counterfactual_mode_requires_v8 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled counterfactual_mode requires runner-config-v8, "
                "runner-config-v9, runner-config-v10, runner-config-v11, "
                "or runner-config-v12 "
                "(code=counterfactual_mode_requires_v8)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V8 and not considering:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v8_requires_counterfactual schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v8 requires a non-disabled counterfactual_mode "
                "(code=v8_requires_counterfactual)"
            )
        strategy_modes = tuple(
            agent.cognition.communication_strategy_mode for agent in self.agents
        )
        strategizing = tuple(
            mode
            for mode in strategy_modes
            if mode is not CommunicationStrategyMode.DISABLED
        )
        if strategizing and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V9,
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.communication_strategy_mode "
                "reason_code=communication_strategy_mode_requires_v9 "
                "schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled communication_strategy_mode requires "
                "runner-config-v9, runner-config-v10, runner-config-v11, "
                "or runner-config-v12 "
                "(code=communication_strategy_mode_requires_v9)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V9 and not strategizing:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v9_requires_communication_strategy schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v9 requires a non-disabled "
                "communication_strategy_mode "
                "(code=v9_requires_communication_strategy)"
            )
        reputation_modes = tuple(
            agent.cognition.reputation_mode for agent in self.agents
        )
        reputing = tuple(
            mode for mode in reputation_modes if mode is not ReputationMode.DISABLED
        )
        if reputing and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V10,
            RUNNER_SCHEMA_VERSION_V11,
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.reputation_mode "
                "reason_code=reputation_mode_requires_v10 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled reputation_mode requires runner-config-v10, "
                "runner-config-v11, or runner-config-v12 "
                "(code=reputation_mode_requires_v10)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V10 and not reputing:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v10_requires_reputation schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v10 requires a non-disabled reputation_mode "
                "(code=v10_requires_reputation)"
            )
        skill_modes = tuple(
            agent.cognition.skill_learning_mode for agent in self.agents
        )
        learning = tuple(
            mode for mode in skill_modes if mode is not SkillLearningMode.DISABLED
        )
        if learning and self.schema_version not in _SKILL_SCHEMAS:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.skill_learning_mode "
                "reason_code=skill_learning_mode_requires_v11 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled skill_learning_mode requires runner-config-v11, "
                "runner-config-v12, or runner-config-v13 "
                "(code=skill_learning_mode_requires_v11)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V11 and not learning:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v11_requires_skill_learning schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v11 requires a deterministic skill_learning_mode "
                "(code=v11_requires_skill_learning)"
            )
        teaching_modes = tuple(
            agent.cognition.teaching_interaction_mode for agent in self.agents
        )
        teaching = tuple(
            mode
            for mode in teaching_modes
            if mode is not TeachingInteractionMode.DISABLED
        )
        missing_skill = tuple(
            agent
            for agent in self.agents
            if agent.cognition.teaching_interaction_mode
            is TeachingInteractionMode.DETERMINISTIC
            and agent.cognition.skill_learning_mode
            is not SkillLearningMode.DETERMINISTIC
        )
        if missing_skill:
            _LOGGER.error(
                "teaching_requires_skill_learning agent_count=%s "
                "reason_code=teaching_requires_skill_learning",
                len(self.agents),
            )
            raise ValueError(
                "deterministic teaching requires deterministic skill learning "
                "(code=teaching_requires_skill_learning)"
            )
        if teaching and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.teaching_interaction_mode "
                "reason_code=teaching_interaction_mode_requires_v12 "
                "schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "non-disabled teaching_interaction_mode requires "
                "runner-config-v12 or runner-config-v13 "
                "(code=teaching_interaction_mode_requires_v12)"
            )
        production_modes = tuple(
            agent.cognition.production_knowledge_mode for agent in self.agents
        )
        production_on = any(
            mode is ProductionKnowledgeMode.DETERMINISTIC for mode in production_modes
        ) or any(
            agent.cognition.production_catalog.recipe_count > 0 for agent in self.agents
        )
        dynamics = self.environmental_dynamics
        if dynamics is not None and type(dynamics) is not EnvironmentalDynamicsSpec:
            raise TypeError(
                "environmental_dynamics must be EnvironmentalDynamicsSpec or None"
            )
        dynamics_schemas = {
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if (dynamics is not None and self.schema_version not in dynamics_schemas) or (
            self.schema_version == RUNNER_SCHEMA_VERSION_V14 and dynamics is None
        ):
            logging.getLogger("simulation.runner").error(
                "environment_spec_mismatch schema_version=%s reason_code=%s",
                self.schema_version,
                "environment_spec_mismatch",
            )
            raise ValueError(
                "environmental dynamics require runner-config-v14, "
                "runner-config-v15, runner-config-v16, runner-config-v17, "
                "runner-config-v18, or runner-config-v19 "
                "(code=environment_spec_mismatch)"
            )
        claim_modes = tuple(
            agent.cognition.territorial_claim_mode for agent in self.agents
        )
        claiming = tuple(
            mode for mode in claim_modes if mode is not TerritorialClaimMode.DISABLED
        )
        if claiming and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.territorial_claim_mode "
                "reason_code=territorial_claim_mode_requires_v15 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic territorial_claim_mode requires runner-config-v15, "
                "runner-config-v16, runner-config-v17, runner-config-v18, "
                "or runner-config-v19 "
                "(code=territorial_claim_mode_requires_v15)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V15 and not claiming:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v15_requires_territorial_claims schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v15 requires a deterministic territorial_claim_mode "
                "(code=v15_requires_territorial_claims)"
            )
        group_modes = tuple(
            agent.cognition.group_formation_mode for agent in self.agents
        )
        grouping = any(
            mode is GroupFormationMode.DETERMINISTIC for mode in group_modes
        )
        if grouping and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.group_formation_mode "
                "reason_code=group_formation_mode_requires_v16 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic group_formation_mode requires runner-config-v16, "
                "runner-config-v17, runner-config-v18, or runner-config-v19 "
                "(code=group_formation_mode_requires_v16)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V16 and not grouping:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v16_requires_group_formation schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v16 requires a deterministic group_formation_mode "
                "(code=v16_requires_group_formation)"
            )
        norm_modes = tuple(agent.cognition.social_norm_mode for agent in self.agents)
        norms_on = any(mode is SocialNormMode.DETERMINISTIC for mode in norm_modes)
        if norms_on and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.social_norm_mode "
                "reason_code=social_norm_mode_requires_v17 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic social_norm_mode requires runner-config-v17, "
                "runner-config-v18, or runner-config-v19 "
                "(code=social_norm_mode_requires_v17)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V17 and not norms_on:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v17_requires_social_norms schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v17 requires a deterministic social_norm_mode "
                "(code=v17_requires_social_norms)"
            )
        convention_modes = tuple(
            agent.cognition.social_convention_mode for agent in self.agents
        )
        conventions_on = any(
            mode is SocialConventionMode.DETERMINISTIC for mode in convention_modes
        )
        convention_schemas = {
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if conventions_on and self.schema_version not in convention_schemas:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.social_convention_mode "
                "reason_code=social_convention_mode_requires_v18 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic social_convention_mode requires runner-config-v18 "
                "or runner-config-v19 or runner-config-v20 "
                "(code=social_convention_mode_requires_v18)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V18 and not conventions_on:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v18_requires_social_conventions schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v18 requires a deterministic social_convention_mode "
                "(code=v18_requires_social_conventions)"
            )
        artifact_modes = tuple(
            agent.cognition.artifact_interpretation_mode for agent in self.agents
        )
        artifacts_on = any(
            mode is ArtifactInterpretationMode.DETERMINISTIC for mode in artifact_modes
        )
        artifacts_active = bool(self.scenario.artifacts) or self.artifacts_enabled
        mode_count = sum(
            mode is ArtifactInterpretationMode.DETERMINISTIC for mode in artifact_modes
        )
        runner_log = logging.getLogger("simulation.runner")
        artifact_schemas = {
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if artifacts_on and self.schema_version not in artifact_schemas:
            runner_log.error(
                "invalid_fields path=agents.cognition.artifact_interpretation_mode "
                "reason_code=artifact_interpretation_mode_requires_v19 "
                "schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic artifact_interpretation_mode requires "
                "runner-config-v19 or runner-config-v20 "
                "(code=artifact_interpretation_mode_requires_v19)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V19 and not artifacts_on:
            runner_log.error(
                "invalid_fields path=schema_version "
                "reason_code=v19_requires_artifact_interpretation schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v19 requires a deterministic "
                "artifact_interpretation_mode "
                "(code=v19_requires_artifact_interpretation)"
            )
        naming_modes = tuple(
            agent.cognition.semantic_naming_mode for agent in self.agents
        )
        naming_on = any(
            mode is SemanticNamingMode.DETERMINISTIC for mode in naming_modes
        )
        naming_schemas = {
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if naming_on and self.schema_version not in naming_schemas:
            runner_log.error(
                "invalid_fields path=agents.cognition.semantic_naming_mode "
                "reason_code=semantic_naming_mode_requires_v20 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic semantic_naming_mode requires runner-config-v20, "
                "runner-config-v21, or runner-config-v22 "
                "(code=semantic_naming_mode_requires_v20)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V20 and not naming_on:
            runner_log.error(
                "invalid_fields path=schema_version "
                "reason_code=v20_requires_semantic_naming schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v20 requires a deterministic semantic_naming_mode "
                "(code=v20_requires_semantic_naming)"
            )
        narrative_modes = tuple(
            agent.cognition.cultural_narrative_mode for agent in self.agents
        )
        narratives_on = any(
            mode is CulturalNarrativeMode.DETERMINISTIC for mode in narrative_modes
        )
        narrative_schemas = {
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        budget_modes = tuple(
            agent.cognition.cognitive_budget_mode for agent in self.agents
        )
        budgets_on = any(mode is CognitiveBudgetMode.ENFORCED for mode in budget_modes)
        budget_schemas = {
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }
        if budgets_on and self.schema_version not in budget_schemas:
            runner_log.error(
                "invalid_fields path=agents.cognition.cognitive_budget_mode "
                "reason_code=cognitive_budget_mode_requires_v22 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "enforced cognitive_budget_mode requires runner-config-v22 "
                "or runner-config-v23 "
                "(code=cognitive_budget_mode_requires_v22)"
            )
        if narratives_on and self.schema_version not in narrative_schemas:
            runner_log.error(
                "invalid_fields path=agents.cognition.cultural_narrative_mode "
                "reason_code=cultural_narrative_mode_requires_v21 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "deterministic cultural_narrative_mode requires runner-config-v21 "
                "or runner-config-v22 "
                "(code=cultural_narrative_mode_requires_v21)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V21 and not narratives_on:
            runner_log.error(
                "invalid_fields path=schema_version "
                "reason_code=v21_requires_cultural_narratives schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v21 requires a deterministic cultural_narrative_mode "
                "(code=v21_requires_cultural_narratives)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V22 and not budgets_on:
            runner_log.error(
                "invalid_fields path=schema_version "
                "reason_code=v22_requires_cognitive_budget schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v22 requires an enforced cognitive_budget_mode "
                "(code=v22_requires_cognitive_budget)"
            )
        if budgets_on:
            runner_log.info(
                "cognitive_budget_config schema_version=%s enforced_agent_count=%s",
                self.schema_version,
                sum(1 for mode in budget_modes if mode is CognitiveBudgetMode.ENFORCED),
            )
        if (
            self.schema_version in artifact_schemas
            or artifacts_on
            or artifacts_active
        ):
            runner_log.info(
                "artifact_config schema_version=%s mode_count=%s artifacts_active=%s",
                self.schema_version,
                mode_count,
                artifacts_active,
            )
            runner_log.debug(
                "artifact_config_detail agent_count=%s mode_count=%s "
                "seed_artifact_count=%s",
                len(self.agents),
                mode_count,
                len(self.scenario.artifacts),
            )
        if dynamics is not None:
            logging.getLogger("simulation.runner").info(
                "environment_config schema_version=%s season_length=%s "
                "hazard_rule_count=%s",
                self.schema_version,
                dynamics.season_length_ticks,
                len(dynamics.hazard_rules),
            )
            logging.getLogger("simulation.runner").debug(
                "environment_config_detail season_count=%s window_count=%s "
                "hazard_rule_count=%s digest=%s",
                4,
                len(dynamics.shortage_windows),
                len(dynamics.hazard_rules),
                dynamics.digest,
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V13 and not production_on:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v13_requires_production schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v13 requires a non-empty production catalog "
                "or a deterministic production_knowledge_mode "
                "(code=v13_requires_production)"
            )
        if production_on and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            _LOGGER.error(
                "invalid_fields path=agents.cognition.production_knowledge_mode "
                "reason_code=production_requires_v13 schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "production requires runner-config-v13, runner-config-v14, "
                "runner-config-v15, runner-config-v16, runner-config-v17, "
                "runner-config-v18, or runner-config-v19 "
                "(code=production_requires_v13)"
            )
        if self.schema_version in {
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            from world.production import production_catalog_digest

            catalogs = tuple(
                agent.cognition.production_catalog for agent in self.agents
            )
            if any(catalog != catalogs[0] for catalog in catalogs):
                digest = production_catalog_digest(
                    tuple(recipe.recipe_id.value for recipe in catalogs[0].recipes)
                )
                logging.getLogger("simulation.runner").error(
                    "production_catalog_mismatch digest=%s", digest
                )
                raise ValueError(
                    "agents must share one production catalog "
                    "(code=production_catalog_mismatch)"
                )
            mode_count = sum(
                mode is ProductionKnowledgeMode.DETERMINISTIC
                for mode in production_modes
            )
            logging.getLogger("simulation.runner").info(
                "production_config schema_version=%s recipe_count=%s mode_count=%s",
                self.schema_version,
                catalogs[0].recipe_count,
                mode_count,
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V12 and not teaching:
            _LOGGER.error(
                "invalid_fields path=schema_version "
                "reason_code=v12_requires_teaching schema_version=%s",
                self.schema_version,
            )
            raise ValueError(
                "runner-config-v12 requires a deterministic "
                "teaching_interaction_mode (code=v12_requires_teaching)"
            )
        if self.schema_version in _SKILL_SCHEMAS:
            shared = skill_rate_tuple(self.agents[0].cognition)
            if any(
                skill_rate_tuple(agent.cognition) != shared for agent in self.agents
            ):
                _LOGGER.error(
                    "skill_rate_mismatch agent_count=%s "
                    "reason_code=skill_rate_mismatch",
                    len(self.agents),
                )
                raise ValueError(
                    "skill agents must share skill rates (code=skill_rate_mismatch)"
                )
            _validate_shared_skill_rates(self.agents[0].cognition)
        if self.schema_version in {
            RUNNER_SCHEMA_VERSION_V12,
            RUNNER_SCHEMA_VERSION_V13,
            RUNNER_SCHEMA_VERSION_V14,
            RUNNER_SCHEMA_VERSION_V15,
            RUNNER_SCHEMA_VERSION_V16,
            RUNNER_SCHEMA_VERSION_V17,
            RUNNER_SCHEMA_VERSION_V18,
            RUNNER_SCHEMA_VERSION_V19,
            RUNNER_SCHEMA_VERSION_V20,
            RUNNER_SCHEMA_VERSION_V21,
            RUNNER_SCHEMA_VERSION_V22,
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
            RUNNER_SCHEMA_VERSION_V26,
            RUNNER_SCHEMA_VERSION_V27,
        RUNNER_SCHEMA_VERSION_V28,
        RUNNER_SCHEMA_VERSION_V29,
        RUNNER_SCHEMA_VERSION_V30,
        RUNNER_SCHEMA_VERSION_V31,
        RUNNER_SCHEMA_VERSION_V32,
        RUNNER_SCHEMA_VERSION_V33,
        RUNNER_SCHEMA_VERSION_V34,
        RUNNER_SCHEMA_VERSION_V35,
        }:
            shared_teaching = teaching_weight_tuple(self.agents[0].cognition)
            if any(
                teaching_weight_tuple(agent.cognition) != shared_teaching
                for agent in self.agents
            ):
                _LOGGER.error(
                    "teaching_weight_mismatch agent_count=%s "
                    "reason_code=teaching_weight_mismatch",
                    len(self.agents),
                )
                raise ValueError(
                    "v12 agents must share teaching weights "
                    "(code=teaching_weight_mismatch)"
                )
            _validate_shared_teaching_weights(self.agents[0].cognition)
        if self.cognition_trace.enabled:
            _LOGGER.info(
                "runner_config_cognition_trace_enabled schema_version=%s "
                "detail=%s sample_every_n_ticks=%s max_bytes_per_invocation=%s",
                self.schema_version,
                self.cognition_trace.detail.value,
                self.cognition_trace.sample_every_n_ticks,
                self.cognition_trace.max_bytes_per_invocation,
            )
        _LOGGER.debug(
            "runner_config_validated schema_version=%s agent_count=%s "
            "location_count=%s max_ticks=%s mortality_mode=%s "
            "capability_flag_count=%s enabled_flag_count=%s "
            "cognition_trace_enabled=%s cognition_trace_detail=%s "
            "consolidation_mode=%s reflection_mode=%s prospective_mode=%s "
            "counterfactual_mode=%s communication_strategy_mode=%s "
            "reputation_mode=%s skill_learning_mode=%s teaching_interaction_mode=%s",
            self.schema_version,
            len(self.agents),
            len(self.scenario.locations),
            self.stop_policy.max_ticks,
            self.mortality_mode.value,
            len(_V2_CAPABILITY_FLAG_NAMES),
            len(enabled),
            self.cognition_trace.enabled,
            self.cognition_trace.detail.value,
            ",".join(mode.value for mode in consolidation_modes),
            ",".join(mode.value for mode in reflection_modes),
            ",".join(mode.value for mode in prospective_modes),
            ",".join(mode.value for mode in counterfactual_modes),
            ",".join(mode.value for mode in strategy_modes),
            ",".join(mode.value for mode in reputation_modes),
            ",".join(mode.value for mode in skill_modes),
            ",".join(mode.value for mode in teaching_modes),
        )
        _LOGGER.debug(
            "runner_config_decoded schema_version=%s consolidation_mode=%s "
            "reflection_mode=%s prospective_mode=%s counterfactual_mode=%s "
            "communication_strategy_mode=%s reputation_mode=%s "
            "skill_learning_mode=%s",
            self.schema_version,
            ",".join(mode.value for mode in consolidation_modes),
            ",".join(mode.value for mode in reflection_modes),
            ",".join(mode.value for mode in prospective_modes),
            ",".join(mode.value for mode in counterfactual_modes),
            ",".join(mode.value for mode in strategy_modes),
            ",".join(mode.value for mode in reputation_modes),
            ",".join(mode.value for mode in skill_modes),
        )

    def ordered_registrations(self) -> tuple[AgentRegistration, ...]:
        return tuple(agent.registration() for agent in self.agents)

    def resolve_physical_rules(self) -> PhysicalRules:
        """Map mortality mode onto the effective world physical ruleset.

        Mortality disabled selects the named non-lethal variant derived from the
        scenario rules template. Mortality enabled rejects a non-lethal version
        so lethal and non-lethal treatments cannot silently alias.
        """
        from world.models import NON_LETHAL_PHYSICAL_RULES_VERSION

        if self.mortality_mode is MortalityMode.DISABLED:
            rules = non_lethal_physical_rules(base=self.scenario.physical_rules)
            _LOGGER.debug(
                "physical_rules_resolved mortality_mode=%s rules_version=%s",
                self.mortality_mode.value,
                rules.version,
            )
            return rules
        rules = self.scenario.physical_rules
        if rules.version == NON_LETHAL_PHYSICAL_RULES_VERSION:
            raise ValueError(
                "mortality enabled forbids non-lethal physical rules "
                "(code=mortality_rules_mismatch)"
            )
        _LOGGER.debug(
            "physical_rules_resolved mortality_mode=%s rules_version=%s",
            self.mortality_mode.value,
            rules.version,
        )
        return rules


@dataclass(frozen=True, slots=True)
class RunnerConfigDiagnostics:
    """Metadata-only projection safe for DEBUG/INFO logs."""

    schema_version: str
    derivation_version: str
    agent_count: int
    location_count: int
    resource_count: int
    max_ticks: int
    memory_modes: tuple[str, ...]
    imagination_modes: tuple[str, ...]
    mortality_mode: str
    provider_adapter: str
    recording_policy: str
    durable: bool
    config_fingerprint_prefix: str
    scenario_fingerprint_prefix: str
    cognition_fingerprint_prefix: str
    provider_fingerprint_prefix: str
    stochastic_fingerprint_prefix: str
    rules_fingerprint_prefix: str
    capability_flag_names: tuple[str, ...]
    enabled_capability_flags: tuple[str, ...]
    capability_flags_digest_prefix: str
    v3_capability_flag_names: tuple[str, ...]
    enabled_v3_capability_flags: tuple[str, ...]
    v3_capability_flags_digest_prefix: str
    cognition_trace_enabled: bool
    cognition_trace_detail: str


def runner_config_diagnostics(
    config: SimulationRunnerConfig,
    *,
    config_fingerprint: str,
    scenario_fingerprint: str,
    cognition_fingerprint: str,
    provider_fingerprint: str,
) -> RunnerConfigDiagnostics:
    """Build a payload-free diagnostic projection for logging."""
    if type(config) is not SimulationRunnerConfig:
        raise TypeError("runner_config_diagnostics requires SimulationRunnerConfig")
    enabled = config.capability_flags.enabled_names()
    flags_digest = capability_flags_digest(config.capability_flags)
    v3_enabled = config.v3_capability_flags.enabled_names()
    v3_flags_digest = v3_capability_flags_digest(config.v3_capability_flags)
    return RunnerConfigDiagnostics(
        schema_version=config.schema_version,
        derivation_version=config.derivation_version,
        agent_count=len(config.agents),
        location_count=len(config.scenario.locations),
        resource_count=len(config.scenario.resources),
        max_ticks=config.stop_policy.max_ticks,
        memory_modes=tuple(
            agent.cognition.memory_mode.value for agent in config.agents
        ),
        imagination_modes=tuple(
            agent.cognition.imagination_mode.value for agent in config.agents
        ),
        mortality_mode=config.mortality_mode.value,
        provider_adapter=config.provider.adapter_kind.value,
        recording_policy=config.provider.recording_policy.value,
        durable=config.persistence.durable,
        config_fingerprint_prefix=config_fingerprint[:12],
        scenario_fingerprint_prefix=scenario_fingerprint[:12],
        cognition_fingerprint_prefix=cognition_fingerprint[:12],
        provider_fingerprint_prefix=provider_fingerprint[:12],
        stochastic_fingerprint_prefix=stochastic_identity_fingerprint(
            config.stochastic_identity
        )[:12],
        rules_fingerprint_prefix=physical_rules_fingerprint(
            config.scenario.physical_rules
        )[:12],
        capability_flag_names=_V2_CAPABILITY_FLAG_NAMES,
        enabled_capability_flags=enabled,
        capability_flags_digest_prefix=flags_digest[:12],
        v3_capability_flag_names=_V3_CAPABILITY_FLAG_NAMES,
        enabled_v3_capability_flags=v3_enabled,
        v3_capability_flags_digest_prefix=v3_flags_digest[:12],
        cognition_trace_enabled=config.cognition_trace.enabled,
        cognition_trace_detail=config.cognition_trace.detail.value,
    )


def capability_flags_digest(flags: V2CapabilityFlags) -> str:
    """Stable hex digest over closed flag names/values (no payloads)."""
    if type(flags) is not V2CapabilityFlags:
        raise TypeError("capability_flags_digest requires V2CapabilityFlags")
    document = {name: getattr(flags, name) for name in _V2_CAPABILITY_FLAG_NAMES}
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def v3_capability_flags_digest(flags: V3CapabilityFlags) -> str:
    """Stable hex digest over closed V3 flag names/values (no payloads)."""
    if type(flags) is not V3CapabilityFlags:
        raise TypeError("v3_capability_flags_digest requires V3CapabilityFlags")
    document = {name: getattr(flags, name) for name in _V3_CAPABILITY_FLAG_NAMES}
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def describe_runner_config(
    diagnostics: RunnerConfigDiagnostics,
) -> Mapping[str, object]:
    """Dict form of diagnostics for structured logs (no secrets/payloads)."""
    if type(diagnostics) is not RunnerConfigDiagnostics:
        raise TypeError("describe_runner_config requires RunnerConfigDiagnostics")
    return {
        "schema_version": diagnostics.schema_version,
        "derivation_version": diagnostics.derivation_version,
        "agent_count": diagnostics.agent_count,
        "location_count": diagnostics.location_count,
        "resource_count": diagnostics.resource_count,
        "max_ticks": diagnostics.max_ticks,
        "memory_modes": diagnostics.memory_modes,
        "imagination_modes": diagnostics.imagination_modes,
        "mortality_mode": diagnostics.mortality_mode,
        "provider_adapter": diagnostics.provider_adapter,
        "recording_policy": diagnostics.recording_policy,
        "durable": diagnostics.durable,
        "config_fingerprint_prefix": diagnostics.config_fingerprint_prefix,
        "scenario_fingerprint_prefix": diagnostics.scenario_fingerprint_prefix,
        "cognition_fingerprint_prefix": diagnostics.cognition_fingerprint_prefix,
        "provider_fingerprint_prefix": diagnostics.provider_fingerprint_prefix,
        "stochastic_fingerprint_prefix": diagnostics.stochastic_fingerprint_prefix,
        "rules_fingerprint_prefix": diagnostics.rules_fingerprint_prefix,
        "capability_flag_names": diagnostics.capability_flag_names,
        "enabled_capability_flags": diagnostics.enabled_capability_flags,
        "capability_flags_digest_prefix": diagnostics.capability_flags_digest_prefix,
        "v3_capability_flag_names": diagnostics.v3_capability_flag_names,
        "enabled_v3_capability_flags": diagnostics.enabled_v3_capability_flags,
        "v3_capability_flags_digest_prefix": (
            diagnostics.v3_capability_flags_digest_prefix
        ),
        "cognition_trace_enabled": diagnostics.cognition_trace_enabled,
        "cognition_trace_detail": diagnostics.cognition_trace_detail,
    }


OBSERVATION_DELIVERY_SCHEMA_VERSION: Final[str] = "observation-delivery-v1"


@dataclass(frozen=True, slots=True)
class ObservationDeliveryAck:
    """Idempotent acknowledgement bound to a delivery ID and content hash."""

    delivery_id: str
    content_hash: str
    schema_version: str = OBSERVATION_DELIVERY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_stable_id("ObservationDeliveryAck.delivery_id", self.delivery_id)
        require_stable_id("ObservationDeliveryAck.content_hash", self.content_hash)
        if self.schema_version != OBSERVATION_DELIVERY_SCHEMA_VERSION:
            raise ValueError("unsupported observation delivery schema_version")


@dataclass(frozen=True, slots=True)
class ObservationDelivery:
    """Detached post-finalization delivery for trusted collectors only."""

    delivery_id: str
    content_hash: str
    tick: int
    kind: str
    schema_version: str = OBSERVATION_DELIVERY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_stable_id("ObservationDelivery.delivery_id", self.delivery_id)
        require_stable_id("ObservationDelivery.content_hash", self.content_hash)
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("ObservationDelivery.tick", self.tick),
        )
        require_stable_id("ObservationDelivery.kind", self.kind)
        if self.schema_version != OBSERVATION_DELIVERY_SCHEMA_VERSION:
            raise ValueError("unsupported observation delivery schema_version")


class ExperimentalObservationSink:
    """Idempotent sink protocol implemented by trusted experiment collectors.

    Concrete collectors may subclass or duck-type this interface. Re-delivery of
    identical content must return the same acknowledgement; divergent reuse of
    a delivery ID must fail closed.
    """

    def __init__(self) -> None:
        self._acks: dict[str, ObservationDeliveryAck] = {}

    def deliver(self, delivery: ObservationDelivery) -> ObservationDeliveryAck:
        if type(delivery) is not ObservationDelivery:
            raise TypeError("delivery must be ObservationDelivery")
        existing = self._acks.get(delivery.delivery_id)
        if existing is not None:
            if existing.content_hash != delivery.content_hash:
                raise ValueError("delivery_id content mismatch")
            return existing
        ack = ObservationDeliveryAck(
            delivery_id=delivery.delivery_id,
            content_hash=delivery.content_hash,
        )
        self._acks[delivery.delivery_id] = ack
        return ack


@dataclass(frozen=True, slots=True)
class SimulationRunnerResultDocument:
    """Versioned machine-readable final run result (no narrative payloads)."""

    schema_version: str
    run_id: str
    stop_reason: str
    ticks_committed: int
    config_fingerprint: str
    scenario_fingerprint: str
    cognition_fingerprint: str
    exact_trajectory_hash: str
    replica_normalized_trajectory_hash: str
    attempt_count: int
    objective_state_hash: str | None = None
    cognition_invocations: int = 0
    imagination_evaluations: int = 0
    imagined_future_count: int = 0
    goal_transition_count: int = 0
    finalized_tick_count: int = 0

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_RESULT_SCHEMA_VERSIONS:
            raise ValueError("unsupported result schema_version")
        require_stable_id("run_id", self.run_id)
        require_stable_id("stop_reason", self.stop_reason)
        object.__setattr__(
            self,
            "ticks_committed",
            require_exact_nonneg_int("ticks_committed", self.ticks_committed),
        )
        for name in (
            "config_fingerprint",
            "scenario_fingerprint",
            "cognition_fingerprint",
            "exact_trajectory_hash",
            "replica_normalized_trajectory_hash",
        ):
            require_stable_id(name, getattr(self, name))
        object.__setattr__(
            self,
            "attempt_count",
            require_exact_nonneg_int("attempt_count", self.attempt_count),
        )
        if self.objective_state_hash is not None:
            require_stable_id("objective_state_hash", self.objective_state_hash)
        for name in (
            "cognition_invocations",
            "imagination_evaluations",
            "imagined_future_count",
            "goal_transition_count",
            "finalized_tick_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )
        if self.schema_version == RESULT_SCHEMA_VERSION_V1:
            if (
                self.objective_state_hash is not None
                or self.cognition_invocations
                or self.imagination_evaluations
                or self.imagined_future_count
                or self.goal_transition_count
                or self.finalized_tick_count
            ):
                raise ValueError("runner-result-v1 forbids v2 result fields")


def project_bodies_to_facts(
    bodies: Sequence[AgentBody],
) -> tuple[BodyObjectiveFact, ...]:
    """Build ordered body facts from immutable AgentBody values."""
    if isinstance(bodies, (set, frozenset)):
        raise TypeError("bodies must be ordered")
    facts: list[BodyObjectiveFact] = []
    for body in bodies:
        if type(body) is not AgentBody:
            raise TypeError("bodies entries must be AgentBody")
        facts.append(
            BodyObjectiveFact(
                entity_id=body.entity_id,
                location_id=body.location_id,
                life_status=body.life_status,
                inventory=tuple(body.inventory),
            )
        )
    facts.sort(key=lambda item: item.entity_id.value)
    return tuple(facts)


def build_detached_objective_projection(
    *,
    tick: int,
    revision: int,
    bodies: Sequence[AgentBody],
) -> DetachedObjectiveProjection:
    """Construct a detached objective projection from public body values."""
    return DetachedObjectiveProjection(
        tick=tick,
        revision=revision,
        bodies=project_bodies_to_facts(bodies),
    )


def _body_index(
    evidence: GoalEvaluationEvidence,
) -> dict[str, BodyObjectiveFact]:
    return {body.entity_id.value: body for body in evidence.bodies}


def _owner_body(
    evidence: GoalEvaluationEvidence, owner_id: AgentId
) -> BodyObjectiveFact | None:
    entity_id = evidence.owner_entity_ids.get(owner_id.value)
    if entity_id is None:
        return None
    return _body_index(evidence).get(entity_id)


def _entity_location(
    evidence: GoalEvaluationEvidence, entity_id: str
) -> EntityId | None:
    bodies = _body_index(evidence)
    body = bodies.get(entity_id)
    if body is not None:
        return body.location_id
    return None


def _outcome_satisfied(
    goal: Goal, evidence: GoalEvaluationEvidence, body: BodyObjectiveFact
) -> bool:
    """Return True only when observable objective facts confirm completion.

    Imagined GoalEffect values are ignored. Kinds without objective evaluators
    never return True here (they close only via death or run_end).
    """
    outcome = goal.outcome
    if outcome is None:
        return False
    kind = outcome.kind
    if kind is GoalOutcomeKind.REACH_PLACE:
        return (
            outcome.place_id is not None and body.location_id.value == outcome.place_id
        )
    if kind is GoalOutcomeKind.OBTAIN_ENTITY:
        return outcome.entity_id is not None and any(
            item.value == outcome.entity_id for item in body.inventory
        )
    if kind is GoalOutcomeKind.AVOID_ENTITY:
        if outcome.entity_id is None:
            return False
        other_location = _entity_location(evidence, outcome.entity_id)
        if other_location is None:
            # Target not present in objective projection: avoidance holds.
            return True
        return other_location != body.location_id
    if kind is GoalOutcomeKind.PRESERVE_LIFE:
        return body.life_status is LifeStatus.ALIVE and evidence.run_ending
    # SATISFY_DRIVE, RELATE_TO_AGENT, GATHER_INFORMATION, ACHIEVE_CODE:
    # not objectively decidable from body/location/inventory alone.
    return False


def evaluate_goals_after_finalization(
    goals: Sequence[Goal],
    evidence: GoalEvaluationEvidence,
) -> tuple[GoalTransitionReceipt, ...]:
    """Deterministically evaluate active goals against observable evidence.

    Semantics per ``GoalOutcomeKind`` (imagined effects never commit outcomes):

    - ``REACH_PLACE`` / ``OBTAIN_ENTITY`` / ``AVOID_ENTITY``: ``COMPLETED`` when
      observable facts match; ``DEATH`` abandons on owner death; ``RUN_END``
      abandons remaining active goals at run end.
    - ``PRESERVE_LIFE``: ``COMPLETED`` at run end while alive; ``DEATH`` abandons
      on owner death.
    - ``SATISFY_DRIVE`` / ``RELATE_TO_AGENT`` / ``GATHER_INFORMATION`` /
      ``ACHIEVE_CODE``: never completed from objective facts alone; ``DEATH`` or
      ``RUN_END`` abandon active goals.
    """
    if type(evidence) is not GoalEvaluationEvidence:
        raise TypeError("evidence must be GoalEvaluationEvidence")
    if isinstance(goals, (set, frozenset)):
        raise TypeError("goals must be ordered")
    receipts: list[GoalTransitionReceipt] = []
    for goal in goals:
        if type(goal) is not Goal:
            raise TypeError("goals entries must be Goal")
        # Subjective FAILED/SUSPENDED on the same tick remain eligible for
        # objective COMPLETED overwrite; skip other non-ACTIVE statuses.
        if goal.status is not GoalStatus.ACTIVE and goal.status not in (
            GoalStatus.FAILED,
            GoalStatus.SUSPENDED,
        ):
            continue
        outcome_kind = (
            goal.outcome.kind
            if goal.outcome is not None
            else GoalOutcomeKind.PRESERVE_LIFE
        )
        from_status = goal.status
        body = _owner_body(evidence, goal.owner_id)
        if body is None:
            _LOGGER.debug(
                "goal_eval_missing_body goal_id=%s owner_id=%s tick=%s",
                goal.goal_id.value,
                goal.owner_id.value,
                evidence.tick,
            )
            if evidence.run_ending and from_status is GoalStatus.ACTIVE:
                receipts.append(
                    GoalTransitionReceipt(
                        goal_id=goal.goal_id,
                        owner_id=goal.owner_id,
                        outcome_kind=outcome_kind,
                        from_status=from_status,
                        to_status=GoalStatus.ABANDONED,
                        tick=evidence.tick,
                        reason_code=GoalTransitionReasonCode.RUN_END,
                    )
                )
            continue
        if body.life_status is LifeStatus.DEAD:
            if from_status is not GoalStatus.ACTIVE:
                continue
            receipts.append(
                GoalTransitionReceipt(
                    goal_id=goal.goal_id,
                    owner_id=goal.owner_id,
                    outcome_kind=outcome_kind,
                    from_status=from_status,
                    to_status=GoalStatus.ABANDONED,
                    tick=evidence.tick,
                    reason_code=GoalTransitionReasonCode.DEATH,
                )
            )
            _LOGGER.debug(
                "goal_transition goal_id=%s owner_id=%s tick=%s reason=%s to_status=%s",
                goal.goal_id.value,
                goal.owner_id.value,
                evidence.tick,
                GoalTransitionReasonCode.DEATH.value,
                GoalStatus.ABANDONED.value,
            )
            continue
        if _outcome_satisfied(goal, evidence, body):
            receipts.append(
                GoalTransitionReceipt(
                    goal_id=goal.goal_id,
                    owner_id=goal.owner_id,
                    outcome_kind=outcome_kind,
                    from_status=from_status,
                    to_status=GoalStatus.COMPLETED,
                    tick=evidence.tick,
                    reason_code=GoalTransitionReasonCode.COMPLETED,
                )
            )
            _LOGGER.debug(
                "goal_transition goal_id=%s owner_id=%s tick=%s reason=%s to_status=%s",
                goal.goal_id.value,
                goal.owner_id.value,
                evidence.tick,
                GoalTransitionReasonCode.COMPLETED.value,
                GoalStatus.COMPLETED.value,
            )
            continue
        if evidence.run_ending and from_status is GoalStatus.ACTIVE:
            receipts.append(
                GoalTransitionReceipt(
                    goal_id=goal.goal_id,
                    owner_id=goal.owner_id,
                    outcome_kind=outcome_kind,
                    from_status=from_status,
                    to_status=GoalStatus.ABANDONED,
                    tick=evidence.tick,
                    reason_code=GoalTransitionReasonCode.RUN_END,
                )
            )
            _LOGGER.debug(
                "goal_transition goal_id=%s owner_id=%s tick=%s reason=%s to_status=%s",
                goal.goal_id.value,
                goal.owner_id.value,
                evidence.tick,
                GoalTransitionReasonCode.RUN_END.value,
                GoalStatus.ABANDONED.value,
            )
    receipts.sort(key=lambda item: (item.tick, item.owner_id.value, item.goal_id.value))
    _LOGGER.debug(
        "goal_eval_complete tick=%s run_ending=%s transition_count=%s",
        evidence.tick,
        evidence.run_ending,
        len(receipts),
    )
    return tuple(receipts)
