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

from agents.cognition.contracts import (
    EmotionalStateAppraiser,
    FutureImagination,
    GoalManager,
    MemoryRetriever,
    MotivationEvaluator,
)
from agents.cognition.loop import CognitiveLoop
from agents.cognition.reflection import ReflectionPolicy
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
                resolved.consolidation_mode
                is CognitionConsolidationMode.LLM_ASSISTED
            )
        )
    return CognitiveLoop(
        perception=LiteralPerceptionInterpreter(),
        memory=memory,
        situation=DirectSituationModeler(emotion_bias=emotion_bias),
        self_state=DirectSelfStateProjector(identity_mode=resolved.identity_mode),
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
    )
