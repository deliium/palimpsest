"""Run-control lifecycle, leases, and resume/recovery contracts.

Task 5 owns finalization-command recovery and mode discrimination. Task 6
owns the durable lifecycle graph, optimistic transitions, execution leases,
and process-restart classification. Configuration payloads must never appear
in logs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.models import (
    AgentEmotionalState,
    EmotionIntensity,
    EmotionKind,
    InternalAgentState,
    empty_emotional_state,
)
from agents.models import AgentId, Goal
from memory.models import Belief, quantize_score
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.clock import require_exact_nonneg_int
from simulation.evidence import OpaqueCanonicalEnvelope, opaque_envelope_from_payload
from simulation.lifecycle import ActionSubmission, require_action_submission
from simulation.models import RunId
from simulation.runner_models import (
    CognitionCounters,
    FinalizedTickReceipt,
    GoalTransitionReceipt,
)
from simulation.subjective_state import SubjectiveMutationBatch
from world.identifiers import require_stable_id

__all__ = [
    "ALLOWED_LIFECYCLE_TRANSITIONS",
    "EMOTIONAL_STATE_CODEC_VERSION",
    "FINALIZATION_COMMAND_CODEC_VERSION",
    "STREAM_RECORD_SCHEMA_VERSION",
    "AgentRuntimeCheckpoint",
    "ConfigAvailability",
    "ExecutionLease",
    "FinalizationCommand",
    "LifecycleTransitionError",
    "ProcessRestartClass",
    "ResumeMode",
    "RunControlRecord",
    "RunLifecycleState",
    "RunLifecycleTransition",
    "RunnerCrashInjected",
    "RunnerCrashPoint",
    "RunnerResumePlan",
    "RunnerRuntimeCheckpoint",
    "StreamRecord",
    "StreamRecordDraft",
    "StreamRecordKind",
    "assert_lifecycle_transition",
    "classify_process_restart",
    "classify_resume_mode",
    "decode_emotional_state",
    "encode_emotional_state",
    "is_lifecycle_transition_allowed",
    "is_terminal_lifecycle_state",
    "make_stream_envelope",
]

FINALIZATION_COMMAND_CODEC_VERSION: Final[str] = "finalization-command-v1"
STREAM_RECORD_SCHEMA_VERSION: Final[str] = "stream-record-v1"
EMOTIONAL_STATE_CODEC_VERSION: Final[str] = "emotional-state-v1"
_EMOTIONAL_STATE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "codec_version",
        "owner_id",
        "tick",
        "last_update_tick",
        "policy_version",
        "intensities",
    }
)
_INTENSITY_KEYS: Final[frozenset[str]] = frozenset({"kind", "intensity"})


def make_stream_envelope(payload: bytes) -> OpaqueCanonicalEnvelope:
    """Wrap opaque stream body bytes in a stream-record-v1 envelope."""
    return opaque_envelope_from_payload(
        schema_version=STREAM_RECORD_SCHEMA_VERSION, payload=payload
    )


class ResumeMode(StrEnum):
    """Discriminates objective replay, pending recovery, and continued run."""

    OBJECTIVE_REPLAY = "objective_replay"
    PENDING_SUBJECTIVE_RECOVERY = "pending_subjective_recovery"
    CONTINUED_EXECUTION = "continued_execution"


class RunnerCrashPoint(StrEnum):
    """Injectable crash boundaries for recovery tests (never production)."""

    BEFORE_OBJECTIVE_COMMIT = "before_objective_commit"
    AFTER_OBJECTIVE_COMMIT = "after_objective_commit"
    DURING_OWNER_FINALIZATION = "during_owner_finalization"
    BEFORE_COLLECTOR_PUBLICATION = "before_collector_publication"
    AFTER_ACKNOWLEDGEMENT = "after_acknowledgement"


class RunnerCrashInjected(RuntimeError):
    """Raised by fault-injection hooks at a named recovery boundary."""

    def __init__(self, point: RunnerCrashPoint, *, ordinal: int | None = None) -> None:
        if type(point) is not RunnerCrashPoint:
            raise TypeError("point must be RunnerCrashPoint")
        self.point = point
        self.ordinal = ordinal
        parts = [f"point={point.value}"]
        if ordinal is not None:
            parts.append(f"ordinal={ordinal}")
        super().__init__(",".join(parts))


class RunLifecycleState(StrEnum):
    """Closed durable run-control lifecycle graph."""

    CONFIGURED = "configured"
    READY = "ready"
    PAUSED = "paused"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    FENCED = "fenced"
    RECOVERY_REQUIRED = "recovery-required"
    INTERRUPTED = "interrupted"


class ConfigAvailability(StrEnum):
    """Whether canonical runner-config-v2 bytes are durable for a run."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ProcessRestartClass(StrEnum):
    """Classification after process restart without inspecting payloads."""

    CLEAN_CONTINUE = "clean_continue"
    LEASE_EXPIRED = "lease_expired"
    RECOVERY_REQUIRED = "recovery_required"
    INTERRUPTED_IN_FLIGHT = "interrupted_in_flight"
    TERMINAL = "terminal"
    FENCED = "fenced"
    CONFIGURATION_UNAVAILABLE = "configuration_unavailable"


# Legal edges for optimistic lifecycle transitions (one-tick uses ready/paused).
ALLOWED_LIFECYCLE_TRANSITIONS: Final[
    Mapping[RunLifecycleState, frozenset[RunLifecycleState]]
] = {
    RunLifecycleState.CONFIGURED: frozenset(
        {
            RunLifecycleState.READY,
            RunLifecycleState.STARTING,
            RunLifecycleState.FAILED,
        }
    ),
    RunLifecycleState.READY: frozenset(
        {
            RunLifecycleState.STARTING,
            RunLifecycleState.PAUSED,
            RunLifecycleState.STOPPING,
            RunLifecycleState.FAILED,
            RunLifecycleState.RECOVERY_REQUIRED,
        }
    ),
    RunLifecycleState.PAUSED: frozenset(
        {
            RunLifecycleState.READY,
            RunLifecycleState.STARTING,
            RunLifecycleState.STOPPING,
            RunLifecycleState.FAILED,
            RunLifecycleState.RECOVERY_REQUIRED,
            RunLifecycleState.INTERRUPTED,
        }
    ),
    RunLifecycleState.STARTING: frozenset(
        {
            RunLifecycleState.RUNNING,
            RunLifecycleState.FAILED,
            RunLifecycleState.INTERRUPTED,
            RunLifecycleState.RECOVERY_REQUIRED,
            RunLifecycleState.FENCED,
        }
    ),
    RunLifecycleState.RUNNING: frozenset(
        {
            RunLifecycleState.READY,
            RunLifecycleState.PAUSED,
            RunLifecycleState.STOPPING,
            RunLifecycleState.COMPLETED,
            RunLifecycleState.FAILED,
            RunLifecycleState.FENCED,
            RunLifecycleState.RECOVERY_REQUIRED,
            RunLifecycleState.INTERRUPTED,
        }
    ),
    RunLifecycleState.STOPPING: frozenset(
        {
            RunLifecycleState.COMPLETED,
            RunLifecycleState.FAILED,
            RunLifecycleState.PAUSED,
            RunLifecycleState.READY,
            RunLifecycleState.FENCED,
            RunLifecycleState.RECOVERY_REQUIRED,
            RunLifecycleState.INTERRUPTED,
        }
    ),
    RunLifecycleState.RECOVERY_REQUIRED: frozenset(
        {
            RunLifecycleState.READY,
            RunLifecycleState.PAUSED,
            RunLifecycleState.STARTING,
            RunLifecycleState.FAILED,
            RunLifecycleState.FENCED,
        }
    ),
    RunLifecycleState.INTERRUPTED: frozenset(
        {
            RunLifecycleState.RECOVERY_REQUIRED,
            RunLifecycleState.FAILED,
            RunLifecycleState.FENCED,
        }
    ),
    RunLifecycleState.FENCED: frozenset(),
    RunLifecycleState.COMPLETED: frozenset(),
    RunLifecycleState.FAILED: frozenset(),
}

_TERMINAL_STATES: Final[frozenset[RunLifecycleState]] = frozenset(
    {
        RunLifecycleState.COMPLETED,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    }
)

_IN_FLIGHT_STATES: Final[frozenset[RunLifecycleState]] = frozenset(
    {
        RunLifecycleState.STARTING,
        RunLifecycleState.RUNNING,
        RunLifecycleState.STOPPING,
    }
)


class LifecycleTransitionError(ValueError):
    """Illegal or contended lifecycle transition."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def is_terminal_lifecycle_state(state: RunLifecycleState) -> bool:
    if type(state) is not RunLifecycleState:
        raise TypeError("state must be RunLifecycleState")
    return state in _TERMINAL_STATES


def is_lifecycle_transition_allowed(
    current: RunLifecycleState, target: RunLifecycleState
) -> bool:
    if type(current) is not RunLifecycleState:
        raise TypeError("current must be RunLifecycleState")
    if type(target) is not RunLifecycleState:
        raise TypeError("target must be RunLifecycleState")
    if current == target:
        return True
    return target in ALLOWED_LIFECYCLE_TRANSITIONS[current]


def assert_lifecycle_transition(
    current: RunLifecycleState, target: RunLifecycleState
) -> None:
    if not is_lifecycle_transition_allowed(current, target):
        raise LifecycleTransitionError("illegal_lifecycle_transition")


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    """Cross-process execution claim with heartbeat/expiry metadata."""

    lease_id: str
    owner_id: str
    claimed_at_unix_ms: int
    heartbeat_at_unix_ms: int
    expires_at_unix_ms: int

    def __post_init__(self) -> None:
        require_stable_id("lease_id", self.lease_id)
        require_stable_id("owner_id", self.owner_id)
        object.__setattr__(
            self,
            "claimed_at_unix_ms",
            require_exact_nonneg_int("claimed_at_unix_ms", self.claimed_at_unix_ms),
        )
        object.__setattr__(
            self,
            "heartbeat_at_unix_ms",
            require_exact_nonneg_int("heartbeat_at_unix_ms", self.heartbeat_at_unix_ms),
        )
        object.__setattr__(
            self,
            "expires_at_unix_ms",
            require_exact_nonneg_int("expires_at_unix_ms", self.expires_at_unix_ms),
        )
        if self.expires_at_unix_ms < self.claimed_at_unix_ms:
            raise ValueError("lease_expiry_before_claim")
        if self.heartbeat_at_unix_ms < self.claimed_at_unix_ms:
            raise ValueError("lease_heartbeat_before_claim")

    def is_expired(self, *, now_unix_ms: int) -> bool:
        now = require_exact_nonneg_int("now_unix_ms", now_unix_ms)
        return now >= self.expires_at_unix_ms


@dataclass(frozen=True, slots=True)
class RunLifecycleTransition:
    """One optimistic lifecycle edge attempt (append-only audit shape)."""

    run_id: RunId
    from_state: RunLifecycleState
    to_state: RunLifecycleState
    expected_version: int
    resulting_version: int
    reason_code: str
    operation_id: str

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(self.from_state) is not RunLifecycleState:
            raise TypeError("from_state must be RunLifecycleState")
        if type(self.to_state) is not RunLifecycleState:
            raise TypeError("to_state must be RunLifecycleState")
        object.__setattr__(
            self,
            "expected_version",
            require_exact_nonneg_int("expected_version", self.expected_version),
        )
        object.__setattr__(
            self,
            "resulting_version",
            require_exact_nonneg_int("resulting_version", self.resulting_version),
        )
        if self.resulting_version != self.expected_version + 1:
            raise ValueError("resulting_version_must_increment")
        require_stable_id("reason_code", self.reason_code)
        require_stable_id("operation_id", self.operation_id)
        assert_lifecycle_transition(self.from_state, self.to_state)


@dataclass(frozen=True, slots=True)
class RunControlRecord:
    """Durable run-control head: config envelope, lifecycle, lease, progress."""

    run_id: RunId
    lifecycle_state: RunLifecycleState
    lifecycle_version: int
    config_availability: ConfigAvailability
    ticks_committed: int
    progress_cursor: int
    config_schema_version: str | None = None
    config_fingerprint: str | None = None
    config_payload: bytes | None = None
    lease: ExecutionLease | None = None
    terminal_reason_code: str | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(self.lifecycle_state) is not RunLifecycleState:
            raise TypeError("lifecycle_state must be RunLifecycleState")
        object.__setattr__(
            self,
            "lifecycle_version",
            require_exact_nonneg_int("lifecycle_version", self.lifecycle_version),
        )
        if type(self.config_availability) is not ConfigAvailability:
            raise TypeError("config_availability must be ConfigAvailability")
        object.__setattr__(
            self,
            "ticks_committed",
            require_exact_nonneg_int("ticks_committed", self.ticks_committed),
        )
        object.__setattr__(
            self,
            "progress_cursor",
            require_exact_nonneg_int("progress_cursor", self.progress_cursor),
        )
        if self.config_availability is ConfigAvailability.UNAVAILABLE:
            if (
                self.config_schema_version is not None
                or self.config_fingerprint is not None
                or self.config_payload is not None
            ):
                raise ValueError("legacy_config_must_remain_unavailable")
        else:
            if self.config_schema_version is None or self.config_fingerprint is None:
                raise ValueError("available_config_requires_version_and_fingerprint")
            require_stable_id("config_schema_version", self.config_schema_version)
            require_stable_id("config_fingerprint", self.config_fingerprint)
            if self.config_payload is None:
                raise ValueError("available_config_requires_payload")
            if not isinstance(self.config_payload, (bytes, bytearray)):
                raise TypeError("config_payload must be bytes")
            object.__setattr__(self, "config_payload", bytes(self.config_payload))
        if self.lease is not None and type(self.lease) is not ExecutionLease:
            raise TypeError("lease must be ExecutionLease or None")
        if self.terminal_reason_code is not None:
            require_stable_id("terminal_reason_code", self.terminal_reason_code)

    def __repr__(self) -> str:
        return (
            f"RunControlRecord(run_id={self.run_id.value!r}, "
            f"lifecycle_state={self.lifecycle_state.value!r}, "
            f"lifecycle_version={self.lifecycle_version}, "
            f"config_availability={self.config_availability.value!r}, "
            f"ticks_committed={self.ticks_committed}, "
            f"progress_cursor={self.progress_cursor}, "
            f"has_lease={self.lease is not None})"
        )


def classify_process_restart(
    record: RunControlRecord,
    *,
    now_unix_ms: int,
    pending_count: int = 0,
) -> ProcessRestartClass:
    """Classify process-restart work from durable head + pending count."""
    if type(record) is not RunControlRecord:
        raise TypeError("record must be RunControlRecord")
    now = require_exact_nonneg_int("now_unix_ms", now_unix_ms)
    pending = require_exact_nonneg_int("pending_count", pending_count)
    if record.config_availability is ConfigAvailability.UNAVAILABLE:
        return ProcessRestartClass.CONFIGURATION_UNAVAILABLE
    if record.lifecycle_state is RunLifecycleState.FENCED:
        return ProcessRestartClass.FENCED
    if is_terminal_lifecycle_state(record.lifecycle_state):
        return ProcessRestartClass.TERMINAL
    if record.lifecycle_state is RunLifecycleState.RECOVERY_REQUIRED or pending > 0:
        return ProcessRestartClass.RECOVERY_REQUIRED
    if record.lifecycle_state is RunLifecycleState.INTERRUPTED:
        return ProcessRestartClass.INTERRUPTED_IN_FLIGHT
    lease = record.lease
    if lease is not None and lease.is_expired(now_unix_ms=now):
        return ProcessRestartClass.LEASE_EXPIRED
    if record.lifecycle_state in _IN_FLIGHT_STATES:
        if lease is None or lease.is_expired(now_unix_ms=now):
            return ProcessRestartClass.INTERRUPTED_IN_FLIGHT
        return ProcessRestartClass.CLEAN_CONTINUE
    return ProcessRestartClass.CLEAN_CONTINUE


@dataclass(frozen=True, slots=True)
class FinalizationCommand:
    """Versioned, privacy-reviewed pending finalization transition.

    Contains everything required to finalize after restart without rerunning
    cognition or provider calls. Logs must never dump this payload.
    """

    codec_version: str
    run_id: RunId
    agent_id: AgentId
    tick: int
    invocation_id: str
    observation_key: tuple[int, int]
    prior_status: AgentRuntimeStatus
    next_status: AgentRuntimeStatus
    effective_command_kind: str
    integrity_hash: str
    next_internal_state: InternalAgentState
    submission: ActionSubmission
    subjective_batch: SubjectiveMutationBatch | None
    has_futures_boundary: bool
    final_confidence: float
    legacy_belief_writes: tuple[Belief, ...] = ()
    delivery_id: str | None = None
    delivery_content_hash: str | None = None
    delivery_acknowledged: bool = False

    def __post_init__(self) -> None:
        if self.codec_version != FINALIZATION_COMMAND_CODEC_VERSION:
            raise ValueError("unsupported_finalization_codec_version")
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        object.__setattr__(
            self,
            "tick",
            require_exact_nonneg_int("FinalizationCommand.tick", self.tick),
        )
        require_stable_id("FinalizationCommand.invocation_id", self.invocation_id)
        if (
            not isinstance(self.observation_key, tuple)
            or len(self.observation_key) != 2
        ):
            raise TypeError("observation_key must be (tick, revision)")
        object.__setattr__(
            self,
            "observation_key",
            (
                require_exact_nonneg_int(
                    "FinalizationCommand.observation_key[0]", self.observation_key[0]
                ),
                require_exact_nonneg_int(
                    "FinalizationCommand.observation_key[1]", self.observation_key[1]
                ),
            ),
        )
        if type(self.prior_status) is not AgentRuntimeStatus:
            raise TypeError("prior_status must be AgentRuntimeStatus")
        if type(self.next_status) is not AgentRuntimeStatus:
            raise TypeError("next_status must be AgentRuntimeStatus")
        require_stable_id(
            "FinalizationCommand.effective_command_kind", self.effective_command_kind
        )
        require_stable_id("FinalizationCommand.integrity_hash", self.integrity_hash)
        if type(self.next_internal_state) is not InternalAgentState:
            raise TypeError("next_internal_state must be InternalAgentState")
        object.__setattr__(
            self, "submission", require_action_submission(self.submission)
        )
        if self.submission.agent_id != self.agent_id:
            raise ValueError("submission.agent_id mismatch")
        if (
            self.subjective_batch is not None
            and type(self.subjective_batch) is not SubjectiveMutationBatch
        ):
            raise TypeError("subjective_batch must be SubjectiveMutationBatch or None")
        if type(self.has_futures_boundary) is not bool:
            raise TypeError("has_futures_boundary must be bool")
        if (
            type(self.final_confidence) is not float
            and type(self.final_confidence) is not int
        ):
            raise TypeError("final_confidence must be float")
        object.__setattr__(self, "final_confidence", float(self.final_confidence))
        beliefs = tuple(self.legacy_belief_writes)
        for item in beliefs:
            if type(item) is not Belief:
                raise TypeError("legacy_belief_writes entries must be Belief")
        object.__setattr__(self, "legacy_belief_writes", beliefs)
        if self.delivery_id is not None:
            require_stable_id("FinalizationCommand.delivery_id", self.delivery_id)
        if self.delivery_content_hash is not None:
            require_stable_id(
                "FinalizationCommand.delivery_content_hash", self.delivery_content_hash
            )
        if type(self.delivery_acknowledged) is not bool:
            raise TypeError("delivery_acknowledged must be bool")

    def __repr__(self) -> str:
        return (
            f"FinalizationCommand(run_id={self.run_id.value!r}, "
            f"agent_id={self.agent_id.value!r}, tick={self.tick}, "
            f"invocation_id={self.invocation_id!r}, "
            f"has_batch={self.subjective_batch is not None}, "
            f"delivery_ack={self.delivery_acknowledged})"
        )


@dataclass(frozen=True, slots=True)
class AgentRuntimeCheckpoint:
    """Detached per-owner runtime state for rehydration (no cognition payloads)."""

    agent_id: AgentId
    status: AgentRuntimeStatus
    internal_state: InternalAgentState
    last_observation_key: tuple[int, int] | None
    processed_invocation_count: int
    finalized_hash_count: int
    goals: tuple[Goal, ...]
    emotional_state: AgentEmotionalState | None = None
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
    competence_model: object | None = None
    declarative_advice: object | None = None
    recipe_beliefs: object | None = None
    reflection_cursor: object | None = None
    decision_journal: tuple[object, ...] | None = None
    remembered_decisions: tuple[object, ...] | None = None
    identity_cursor: object | None = None

    def __post_init__(self) -> None:
        if type(self.agent_id) is not AgentId:
            raise TypeError("agent_id must be AgentId")
        if type(self.status) is not AgentRuntimeStatus:
            raise TypeError("status must be AgentRuntimeStatus")
        if type(self.internal_state) is not InternalAgentState:
            raise TypeError("internal_state must be InternalAgentState")
        object.__setattr__(
            self,
            "processed_invocation_count",
            require_exact_nonneg_int(
                "processed_invocation_count", self.processed_invocation_count
            ),
        )
        object.__setattr__(
            self,
            "finalized_hash_count",
            require_exact_nonneg_int("finalized_hash_count", self.finalized_hash_count),
        )
        goals = tuple(self.goals)
        for goal in goals:
            if type(goal) is not Goal:
                raise TypeError("goals entries must be Goal")
        object.__setattr__(self, "goals", goals)
        if self.emotional_state is not None:
            if type(self.emotional_state) is not AgentEmotionalState:
                raise TypeError("emotional_state must be AgentEmotionalState")
            if self.emotional_state.owner_id != self.agent_id:
                raise ValueError("emotional_state owner_id mismatch")
        if self.causal_world_model is not None:
            from agents.cognition.world_model import CausalWorldModel

            if type(self.causal_world_model) is not CausalWorldModel:
                raise TypeError("causal_world_model must be CausalWorldModel")
            if self.causal_world_model.owner_id != self.agent_id:
                raise ValueError("causal_world_model owner_id mismatch")
        from agents.cognition.theory_of_mind import require_owner_theory

        require_owner_theory(
            self.theory_of_mind,
            self.agent_id,
            field_name="theory_of_mind",
        )
        from agents.cognition.reputation import require_owner_reputation

        require_owner_reputation(
            self.reputation,
            self.agent_id,
            field_name="reputation",
        )
        from agents.cognition.territorial import require_owner_territorial_claims

        require_owner_territorial_claims(
            self.territorial_claims,
            self.agent_id,
            field_name="territorial_claims",
        )
        from agents.cognition.group_formation import require_owner_group_formation

        require_owner_group_formation(
            self.group_formation,
            self.agent_id,
            field_name="group_formation",
        )
        from agents.cognition.social_norms import require_owner_social_norms

        require_owner_social_norms(
            self.social_norms,
            self.agent_id,
            field_name="social_norms",
        )
        from agents.cognition.social_conventions import require_owner_social_conventions

        require_owner_social_conventions(
            self.social_conventions,
            self.agent_id,
            field_name="social_conventions",
        )
        from agents.cognition.artifacts import require_owner_artifact_interpretations

        require_owner_artifact_interpretations(
            self.artifact_interpretations,
            self.agent_id,
            field_name="artifact_interpretations",
        )
        from agents.cognition.semantic_naming import require_owner_semantic_naming

        require_owner_semantic_naming(
            self.semantic_naming,
            self.agent_id,
            field_name="semantic_naming",
        )
        from agents.cognition.cultural_narratives import (
            require_owner_cultural_narratives,
        )

        require_owner_cultural_narratives(
            self.cultural_narratives,
            self.agent_id,
            field_name="cultural_narratives",
        )
        from agents.cognition.competence import require_owner_competence

        require_owner_competence(
            self.competence_model,
            self.agent_id,
            field_name="competence_model",
        )
        from agents.cognition.teaching import require_owner_advice

        require_owner_advice(
            self.declarative_advice,
            self.agent_id,
            field_name="declarative_advice",
        )
        if self.reflection_cursor is not None:
            from agents.cognition.reflection import ReflectionCursor

            if type(self.reflection_cursor) is not ReflectionCursor:
                raise TypeError("reflection_cursor must be ReflectionCursor")
            if self.reflection_cursor.owner_id != self.agent_id:
                raise ValueError("reflection_cursor owner_id mismatch")
        if self.identity_cursor is not None:
            from agents.cognition.identity import IdentityCursor

            if type(self.identity_cursor) is not IdentityCursor:
                raise TypeError("identity_cursor must be IdentityCursor")
            if self.identity_cursor.owner_id != self.agent_id:
                raise ValueError("identity_cursor owner_id mismatch")
        if self.decision_journal is not None:
            from agents.cognition.reflection import SubjectiveDecisionRecord

            if isinstance(self.decision_journal, (str, bytes)) or not isinstance(
                self.decision_journal, tuple
            ):
                raise TypeError("decision_journal must be a tuple or None")
            for item in self.decision_journal:
                if type(item) is not SubjectiveDecisionRecord:
                    raise TypeError("decision_journal entries must be records")
                if item.owner_id != self.agent_id:
                    raise ValueError("decision_journal owner_id mismatch")
        if self.remembered_decisions is not None:
            from agents.cognition.counterfactual import RememberedDecision

            if isinstance(self.remembered_decisions, (str, bytes)) or not isinstance(
                self.remembered_decisions, tuple
            ):
                raise TypeError("remembered_decisions must be a tuple or None")
            for item in self.remembered_decisions:
                if type(item) is not RememberedDecision:
                    raise TypeError(
                        "remembered_decisions entries must be RememberedDecision"
                    )
                if item.owner_id != self.agent_id:
                    raise ValueError("remembered_decisions owner_id mismatch")


def encode_emotional_state(
    state: AgentEmotionalState | None,
) -> dict[str, object] | None:
    """Encode owner-scoped emotional carry; ``None`` when unset/neutral-absent."""
    if state is None:
        return None
    if type(state) is not AgentEmotionalState:
        raise TypeError("state must be AgentEmotionalState")
    payload: dict[str, object] = {
        "codec_version": EMOTIONAL_STATE_CODEC_VERSION,
        "owner_id": state.owner_id.value,
        "tick": state.tick,
        "last_update_tick": state.last_update_tick,
        "policy_version": state.policy_version,
        "intensities": [
            {"kind": entry.kind.value, "intensity": entry.intensity}
            for entry in state.intensities
        ],
    }
    if set(payload) != _EMOTIONAL_STATE_KEYS:
        raise ValueError("emotional_state encode key-set mismatch")
    return payload


def decode_emotional_state(
    data: object | None,
    *,
    owner_id: AgentId,
    path: str = "$.emotional_state",
) -> AgentEmotionalState | None:
    """Decode emotional carry; missing/null → ``None`` (legacy empty)."""
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise TypeError(f"{path}: invalid_object")
    raw = dict(data)
    # Legacy documents without the field are handled by callers passing None.
    # Partial/unknown versions fail closed.
    if "codec_version" not in raw:
        return None
    if raw.get("codec_version") != EMOTIONAL_STATE_CODEC_VERSION:
        raise ValueError(f"{path}: unsupported_codec_version")
    if set(raw) != _EMOTIONAL_STATE_KEYS:
        raise ValueError(f"{path}: unexpected_keys")
    owner_raw = raw["owner_id"]
    if type(owner_raw) is not str:
        raise TypeError(f"{path}.owner_id: invalid_type")
    decoded_owner = AgentId(owner_raw)
    if decoded_owner != owner_id:
        raise ValueError(f"{path}: ownership")
    intensities_raw = raw["intensities"]
    if not isinstance(intensities_raw, list):
        raise TypeError(f"{path}.intensities: invalid_type")
    intensities: list[EmotionIntensity] = []
    for index, item in enumerate(intensities_raw):
        item_path = f"{path}.intensities[{index}]"
        if not isinstance(item, Mapping):
            raise TypeError(f"{item_path}: invalid_object")
        entry = dict(item)
        if set(entry) != _INTENSITY_KEYS:
            raise ValueError(f"{item_path}: unexpected_keys")
        kind_raw = entry["kind"]
        if type(kind_raw) is not str:
            raise TypeError(f"{item_path}.kind: invalid_type")
        try:
            kind = EmotionKind(kind_raw)
        except ValueError as exc:
            raise ValueError(f"{item_path}.kind: unknown_kind") from exc
        intensity_raw = entry["intensity"]
        if isinstance(intensity_raw, bool) or not isinstance(
            intensity_raw, (int, float)
        ):
            raise TypeError(f"{item_path}.intensity: invalid_type")
        intensities.append(
            EmotionIntensity(kind=kind, intensity=quantize_score(float(intensity_raw)))
        )
    tick = raw["tick"]
    last_update = raw["last_update_tick"]
    policy = raw["policy_version"]
    if type(tick) is not int or isinstance(tick, bool):
        raise TypeError(f"{path}.tick: invalid_type")
    if type(last_update) is not int or isinstance(last_update, bool):
        raise TypeError(f"{path}.last_update_tick: invalid_type")
    if type(policy) is not str:
        raise TypeError(f"{path}.policy_version: invalid_type")
    if not intensities:
        return empty_emotional_state(decoded_owner, tick=tick)
    return AgentEmotionalState(
        owner_id=decoded_owner,
        tick=tick,
        intensities=tuple(intensities),
        last_update_tick=last_update,
        policy_version=policy,
    )


@dataclass(frozen=True, slots=True)
class RunnerRuntimeCheckpoint:
    """Process-restart snapshot for SimulationRunner rehydration."""

    run_id: RunId
    ticks_committed: int
    engine_tick: int
    engine_revision: int
    runtime_states: tuple[AgentRuntimeCheckpoint, ...]
    finalized_tick_receipts: tuple[FinalizedTickReceipt, ...]
    goal_transition_receipts: tuple[GoalTransitionReceipt, ...]
    cognition_counters: CognitionCounters
    pending_tick: int | None = None
    pending_count: int = 0

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        for name in (
            "ticks_committed",
            "engine_tick",
            "engine_revision",
            "pending_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(name, getattr(self, name)),
            )
        if self.pending_tick is not None:
            object.__setattr__(
                self,
                "pending_tick",
                require_exact_nonneg_int("pending_tick", self.pending_tick),
            )
        states = tuple(self.runtime_states)
        for state in states:
            if type(state) is not AgentRuntimeCheckpoint:
                raise TypeError("runtime_states entries must be AgentRuntimeCheckpoint")
        object.__setattr__(self, "runtime_states", states)
        if type(self.cognition_counters) is not CognitionCounters:
            raise TypeError("cognition_counters must be CognitionCounters")


@dataclass(frozen=True, slots=True)
class RunnerResumePlan:
    """Classified resume action after inspecting durable/checkpoint state."""

    mode: ResumeMode
    run_id: RunId
    ticks_committed: int
    pending_tick: int | None
    pending_count: int

    def __post_init__(self) -> None:
        if type(self.mode) is not ResumeMode:
            raise TypeError("mode must be ResumeMode")
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        object.__setattr__(
            self,
            "ticks_committed",
            require_exact_nonneg_int("ticks_committed", self.ticks_committed),
        )
        object.__setattr__(
            self,
            "pending_count",
            require_exact_nonneg_int("pending_count", self.pending_count),
        )
        if self.pending_tick is not None:
            object.__setattr__(
                self,
                "pending_tick",
                require_exact_nonneg_int("pending_tick", self.pending_tick),
            )


def classify_resume_mode(
    *,
    run_id: RunId,
    ticks_committed: int,
    engine_tick: int,
    pending_count: int,
    pending_tick: int | None,
) -> RunnerResumePlan:
    """Classify resume work without inspecting subjective payloads."""
    if type(run_id) is not RunId:
        raise TypeError("run_id must be RunId")
    ticks_committed = require_exact_nonneg_int("ticks_committed", ticks_committed)
    engine_tick = require_exact_nonneg_int("engine_tick", engine_tick)
    pending_count = require_exact_nonneg_int("pending_count", pending_count)
    if pending_count > 0:
        mode = ResumeMode.PENDING_SUBJECTIVE_RECOVERY
    elif engine_tick > ticks_committed:
        # Objective history ahead of runner cursor: replay/align first.
        mode = ResumeMode.OBJECTIVE_REPLAY
    else:
        mode = ResumeMode.CONTINUED_EXECUTION
    return RunnerResumePlan(
        mode=mode,
        run_id=run_id,
        ticks_committed=ticks_committed,
        pending_tick=pending_tick,
        pending_count=pending_count,
    )


class StreamRecordKind(StrEnum):
    """Closed set of durable unified stream/outbox record kinds."""

    STATUS = "status"
    EVENTLESS_TICK = "eventless_tick"
    EVENT = "event"
    METRIC = "metric"
    RESULT = "result"
    RECOVERABLE_ERROR = "recoverable_error"
    COMPLETION = "completion"


@dataclass(frozen=True, slots=True)
class StreamRecordDraft:
    """Stream publication input before per-run cursor assignment."""

    kind: StreamRecordKind
    envelope: OpaqueCanonicalEnvelope
    related_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not StreamRecordKind:
            raise TypeError("kind must be StreamRecordKind")
        if type(self.envelope) is not OpaqueCanonicalEnvelope:
            raise TypeError("envelope must be OpaqueCanonicalEnvelope")
        if self.envelope.schema_version != STREAM_RECORD_SCHEMA_VERSION:
            raise ValueError("unsupported_stream_record_version")
        if self.related_tick is not None:
            object.__setattr__(
                self,
                "related_tick",
                require_exact_nonneg_int("related_tick", self.related_tick),
            )


@dataclass(frozen=True, slots=True)
class StreamRecord:
    """Durable monotonic stream/outbox record for one run."""

    run_id: RunId
    cursor: int
    kind: StreamRecordKind
    envelope: OpaqueCanonicalEnvelope
    related_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        object.__setattr__(
            self,
            "cursor",
            require_exact_nonneg_int("cursor", self.cursor),
        )
        if self.cursor < 1:
            raise ValueError("cursor must be >= 1")
        if type(self.kind) is not StreamRecordKind:
            raise TypeError("kind must be StreamRecordKind")
        if type(self.envelope) is not OpaqueCanonicalEnvelope:
            raise TypeError("envelope must be OpaqueCanonicalEnvelope")
        if self.envelope.schema_version != STREAM_RECORD_SCHEMA_VERSION:
            raise ValueError("unsupported_stream_record_version")
        if self.related_tick is not None:
            object.__setattr__(
                self,
                "related_tick",
                require_exact_nonneg_int("related_tick", self.related_tick),
            )

    def __repr__(self) -> str:
        return (
            f"StreamRecord(run_id={self.run_id.value!r}, cursor={self.cursor}, "
            f"kind={self.kind.value!r}, "
            f"hash_prefix={self.envelope.content_hash[:12]!r})"
        )
