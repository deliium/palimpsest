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
from dataclasses import dataclass
from enum import StrEnum
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
from world.identifiers import (
    EntityId,
    WorldId,
    WorldRevision,
    require_bounded_text,
    require_stable_id,
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
RUNNER_SCHEMA_VERSION: Final[str] = RUNNER_SCHEMA_VERSION_V4
SUPPORTED_RUNNER_SCHEMA_VERSIONS: Final[frozenset[str]] = frozenset(
    {
        RUNNER_SCHEMA_VERSION_V1,
        RUNNER_SCHEMA_VERSION_V2,
        RUNNER_SCHEMA_VERSION_V3,
        RUNNER_SCHEMA_VERSION_V4,
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
    {"short_term_emotional_state"}
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


@dataclass(frozen=True, slots=True)
class V2CapabilityFlags:
    """Run-level reserved V2 capability identifiers (configuration only).

    Defaults are all off (V1-equivalent wiring). Enabling a flag that is not
    yet owned by an implemented plan must fail closed at runner construction
    (``capability_unimplemented``). Owned flags (currently
    ``short_term_emotional_state``) may be enabled. These are not cognition
    plugins.
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
        return tuple(
            name for name in _V2_CAPABILITY_FLAG_NAMES if getattr(self, name)
        )

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
            name
            for name in self.enabled_names()
            if name in _V2_OWNED_CAPABILITY_FLAGS
        )


# Alias kept for plan wording; prefer V2CapabilityFlags in new code.
CapabilityProfile = V2CapabilityFlags


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
        command_kind=resolution.command.kind,
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


class CognitionFailurePolicy(StrEnum):
    """Policy when one agent's cognition fails during a tick."""

    ABORT_TICK = "abort_tick"
    OMIT_FAILED_AGENT = "omit_failed_agent"


class RecordingPolicy(StrEnum):
    """LLM reproducibility policy for runner provider settings."""

    LIVE = "live"
    DETERMINISTIC_FAKE = "deterministic_fake"
    RECORDED = "recorded"


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

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("AgentCognitionSpec.agent_id must be AgentId")
        if type(self.memory_mode) is not MemoryMode:
            raise TypeError("AgentCognitionSpec.memory_mode must be MemoryMode")
        if type(self.imagination_mode) is not ImaginationMode:
            raise TypeError(
                "AgentCognitionSpec.imagination_mode must be ImaginationMode"
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
        if not self.locations:
            raise ValueError("WorldScenarioSpec.locations must be non-empty")
        if not self.bodies:
            raise ValueError("WorldScenarioSpec.bodies must be non-empty")
        body_ids = {body.entity_id for body in self.bodies}
        if len(body_ids) != len(self.bodies):
            raise ValueError("WorldScenarioSpec.bodies entity_ids must be unique")


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
                raise ValueError(
                    "exact reproducibility requires deterministic_fake or recorded "
                    "recording_policy"
                )
            if self.adapter_kind is ProviderAdapterKind.OPENAI_COMPATIBLE:
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
    cognition_trace: CognitionTraceSpec = CognitionTraceSpec()
    schema_version: str = RUNNER_SCHEMA_VERSION
    derivation_version: str = DERIVATION_VERSION_V3
    mortality_policy_version: str = MORTALITY_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed", require_seed(self.seed))
        object.__setattr__(
            self,
            "stochastic_identity",
            require_stochastic_identity(self.stochastic_identity),
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
        if type(self.cognition_trace) is not CognitionTraceSpec:
            raise TypeError("cognition_trace must be CognitionTraceSpec")
        if self.schema_version not in SUPPORTED_RUNNER_SCHEMA_VERSIONS:
            raise ValueError("unsupported runner schema_version")
        if require_derivation_version(self.derivation_version) != DERIVATION_VERSION_V3:
            raise ValueError("runner config requires derivation-v3")
        if self.mortality_policy_version != MORTALITY_POLICY_VERSION:
            raise ValueError("unsupported mortality_policy_version")
        if (
            self.schema_version
            in {RUNNER_SCHEMA_VERSION_V1, RUNNER_SCHEMA_VERSION_V2}
            and self.capability_flags.any_enabled()
        ):
            raise ValueError(
                "capability flags require runner-config-v3+ "
                "(code=capability_requires_v3)"
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
            "cognition_trace_enabled=%s cognition_trace_detail=%s",
            self.schema_version,
            len(self.agents),
            len(self.scenario.locations),
            self.stop_policy.max_ticks,
            self.mortality_mode.value,
            len(_V2_CAPABILITY_FLAG_NAMES),
            len(enabled),
            self.cognition_trace.enabled,
            self.cognition_trace.detail.value,
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
            outcome.place_id is not None
            and body.location_id.value == outcome.place_id
        )
    if kind is GoalOutcomeKind.OBTAIN_ENTITY:
        return (
            outcome.entity_id is not None
            and any(item.value == outcome.entity_id for item in body.inventory)
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
                "goal_transition goal_id=%s owner_id=%s tick=%s "
                "reason=%s to_status=%s",
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
                "goal_transition goal_id=%s owner_id=%s tick=%s "
                "reason=%s to_status=%s",
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
                "goal_transition goal_id=%s owner_id=%s tick=%s "
                "reason=%s to_status=%s",
                goal.goal_id.value,
                goal.owner_id.value,
                evidence.tick,
                GoalTransitionReasonCode.RUN_END.value,
                GoalStatus.ABANDONED.value,
            )
    receipts.sort(
        key=lambda item: (item.tick, item.owner_id.value, item.goal_id.value)
    )
    _LOGGER.debug(
        "goal_eval_complete tick=%s run_ending=%s transition_count=%s",
        evidence.tick,
        evidence.run_ending,
        len(receipts),
    )
    return tuple(receipts)
