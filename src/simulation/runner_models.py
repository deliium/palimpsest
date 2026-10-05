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

# Owned by v3-02 population lifecycle; other V3 flags remain fail-closed.
_V3_OWNED_CAPABILITY_FLAGS: Final[frozenset[str]] = frozenset(
    {"generational_population"}
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
class PopulationLifecycleSpec:
    """Closed run-level population/lifecycle configuration (runner-config-v24).

    Forbidden biology fields (sex, fertility, mating, pregnancy, parentage,
    kinship) are rejected at construction. Demographic policies are experimental
    entry schedules — not reproductive mechanics.
    """

    lifespan_ticks: int
    stage_thresholds: tuple[LifecycleStageThreshold, ...]
    dependent_until_stage: LifecycleStageId
    demographic_policy_id: str
    demographic_policy_params: Mapping[str, object]
    max_population: int
    natural_death_on_lifespan: bool

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

    @property
    def stage_order(self) -> tuple[LifecycleStageId, ...]:
        return tuple(item.stage_id for item in self.stage_thresholds)

    def canonical_payload(self) -> dict[str, object]:
        """Exact wire object for runner-config-v24 ``population_lifecycle``."""
        return {
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


BOOTSTRAP_LIFECYCLE_COHORT_ID: Final[str] = "cohort-bootstrap"
BOOTSTRAP_LIFECYCLE_GENERATION_INDEX: Final[int] = 0


def seed_bootstrap_lifecycle_records(
    *,
    registrations: Sequence[AgentRegistration],
    spec: PopulationLifecycleSpec,
) -> tuple[AgentLifecycleRecord, ...]:
    """Seed lifecycle records for bootstrap roster (no created/entered events)."""
    if type(spec) is not PopulationLifecycleSpec:
        raise TypeError("spec must be PopulationLifecycleSpec")
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
            )
        )
    _LOGGER.debug(
        "bootstrap_lifecycle_records_seeded record_count=%s stage=%s "
        "dependency_status=%s",
        len(records),
        stage.value,
        dependency.value,
    )
    return tuple(records)


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
                "generational_population requires runner-config-v24 or "
                "runner-config-v25 (code=generational_population_requires_v24)"
            )
        other_v3_enabled = tuple(
            name
            for name in self.v3_capability_flags.enabled_names()
            if name != "generational_population"
        )
        if other_v3_enabled and self.schema_version not in {
            RUNNER_SCHEMA_VERSION_V23,
            RUNNER_SCHEMA_VERSION_V24,
            RUNNER_SCHEMA_VERSION_V25,
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
        if self.schema_version in _lifecycle_schemas:
            if self.population_lifecycle is None:
                code = (
                    "v25_requires_population_lifecycle"
                    if self.schema_version == RUNNER_SCHEMA_VERSION_V25
                    else "v24_requires_population_lifecycle"
                )
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
                "population_lifecycle requires runner-config-v24 or "
                "runner-config-v25 (code=population_lifecycle_requires_v24)"
            )
        if (
            self.v3_capability_flags.generational_population
            and self.population_lifecycle is None
        ):
            raise ValueError(
                "generational_population requires population_lifecycle "
                "(code=generational_population_requires_lifecycle_spec)"
            )
        if self.schema_version == RUNNER_SCHEMA_VERSION_V25:
            if self.new_agent_initialization is None:
                _LOGGER.error(
                    "v25_requires_new_agent_initialization schema_version=%s "
                    "reason_code=v25_requires_new_agent_initialization",
                    self.schema_version,
                )
                raise ValueError(
                    "runner-config-v25 requires new_agent_initialization "
                    "(code=v25_requires_new_agent_initialization)"
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
                    "new_agent_initialization requires runner-config-v25 "
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
