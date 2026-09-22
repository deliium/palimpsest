"""Minimal resume/recovery contracts for simulation run control.

Task 5 owns finalization-command recovery and mode discrimination. Task 6
expands this module into the full lifecycle/lease graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.cognition.models import InternalAgentState
from agents.models import AgentId, Goal
from memory.models import Belief
from simulation.agent_runtime import AgentRuntimeStatus
from simulation.clock import require_exact_nonneg_int
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
    "FINALIZATION_COMMAND_CODEC_VERSION",
    "AgentRuntimeCheckpoint",
    "FinalizationCommand",
    "ResumeMode",
    "RunnerCrashInjected",
    "RunnerCrashPoint",
    "RunnerResumePlan",
    "RunnerRuntimeCheckpoint",
    "classify_resume_mode",
]

FINALIZATION_COMMAND_CODEC_VERSION: Final[str] = "finalization-command-v1"


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
