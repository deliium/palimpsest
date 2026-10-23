"""Complete process-local runner fork checkpoints.

These contracts never become a durable wire schema and never expose mutable
engine, provider, lock, or session objects. They bind a finalized objective
boundary to every registered owner's complete runtime and subjective state.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from agents.cognition.counterfactual import CounterfactualState
from agents.cognition.fork_state import CognitiveLoopForkState
from agents.models import AgentId
from memory.models import Belief, MemoryTrace
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick, require_exact_nonneg_int
from simulation.models import RunId
from simulation.persistence import WorldSnapshot
from simulation.run_control import AgentRuntimeCheckpoint, RunnerRuntimeCheckpoint
from simulation.runner_models import SimulationRunnerConfig
from simulation.subjective_state import SubjectiveOwnerForkState
from world.identifiers import WorldRevision

RUNNER_FORK_CHECKPOINT_VERSION: Final[str] = "runner-fork-checkpoint-v1"
AGENT_RUNTIME_FORK_STATE_VERSION: Final[str] = "agent-runtime-fork-state-v1"

AUDIT_FIELD_NAMES: Final[tuple[str, ...]] = (
    "offline_consolidation_audits",
    "reflection_audits",
    "world_model_audits",
    "developmental_audits",
    "mentorship_audits",
    "cultural_feature_audits",
    "practical_knowledge_audits",
    "mind_audits",
    "prospective_audits",
    "cognitive_budget_audits",
    "counterfactual_audits",
    "communication_intent_audits",
)


class ForkCheckpointError(ValueError):
    """Fail-closed fork checkpoint error with a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


def _ordered[T](name: str, values: object, model_type: type[T]) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise ForkCheckpointError("fork_state_invalid", f"{name} must be ordered")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ForkCheckpointError("fork_state_invalid", f"{name} must be a sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise ForkCheckpointError(
                "fork_state_invalid", f"{name} entries must be {model_type.__name__}"
            )
    return items


def _str_set(name: str, values: object) -> frozenset[str]:
    if not isinstance(values, (set, frozenset)):
        raise ForkCheckpointError("fork_state_invalid", f"{name} must be a set")
    copied = frozenset(values)
    for item in copied:
        if type(item) is not str:
            raise ForkCheckpointError(
                "fork_state_invalid", f"{name} entries must be str"
            )
    return copied


@dataclass(frozen=True, slots=True)
class AgentRuntimeForkState:
    """Complete continuation state for one runtime, beyond the durable checkpoint."""

    checkpoint: AgentRuntimeCheckpoint
    processed_invocations: frozenset[str]
    finalized_hashes: frozenset[str]
    invocation_counts: tuple[tuple[str, int, int], ...]
    goal_revision_counters: tuple[tuple[str, int], ...]
    applied_identity_operation_ids: frozenset[str]
    applied_reflection_operation_ids: frozenset[str]
    legacy_memories: tuple[MemoryTrace, ...]
    legacy_beliefs: tuple[Belief, ...]
    cultural_restored: bool
    cultural_fresh_channels: frozenset[str]
    counterfactual_state: CounterfactualState
    loop_state: CognitiveLoopForkState
    audits: tuple[tuple[str, tuple[object, ...]], ...] = ()
    state_format_version: str = AGENT_RUNTIME_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != AGENT_RUNTIME_FORK_STATE_VERSION:
            raise ForkCheckpointError(
                "fork_state_unsupported", "unsupported runtime fork-state version"
            )
        if type(self.checkpoint) is not AgentRuntimeCheckpoint:
            raise ForkCheckpointError(
                "fork_state_invalid", "invalid runtime checkpoint"
            )
        if type(self.cultural_restored) is not bool:
            raise ForkCheckpointError("fork_state_invalid", "invalid cultural flag")
        if type(self.counterfactual_state) is not CounterfactualState:
            raise ForkCheckpointError(
                "fork_state_invalid", "invalid counterfactual state"
            )
        if type(self.loop_state) is not CognitiveLoopForkState:
            raise ForkCheckpointError("fork_state_invalid", "invalid loop state")
        object.__setattr__(
            self,
            "processed_invocations",
            _str_set("processed_invocations", self.processed_invocations),
        )
        object.__setattr__(
            self,
            "finalized_hashes",
            _str_set("finalized_hashes", self.finalized_hashes),
        )
        object.__setattr__(
            self,
            "applied_identity_operation_ids",
            _str_set(
                "applied_identity_operation_ids",
                self.applied_identity_operation_ids,
            ),
        )
        object.__setattr__(
            self,
            "applied_reflection_operation_ids",
            _str_set(
                "applied_reflection_operation_ids",
                self.applied_reflection_operation_ids,
            ),
        )
        object.__setattr__(
            self,
            "cultural_fresh_channels",
            _str_set("cultural_fresh_channels", self.cultural_fresh_channels),
        )
        object.__setattr__(
            self,
            "legacy_memories",
            _ordered("legacy_memories", self.legacy_memories, MemoryTrace),
        )
        object.__setattr__(
            self,
            "legacy_beliefs",
            _ordered("legacy_beliefs", self.legacy_beliefs, Belief),
        )
        counts: list[tuple[str, int, int]] = []
        seen: set[tuple[str, int]] = set()
        for entry in self.invocation_counts:
            if not isinstance(entry, tuple) or len(entry) != 3:
                raise ForkCheckpointError(
                    "fork_state_invalid", "invalid invocation count"
                )
            agent_id, tick, count = entry
            if type(agent_id) is not str:
                raise ForkCheckpointError(
                    "fork_state_invalid", "invalid invocation agent"
                )
            tick = require_exact_nonneg_int("invocation tick", tick)
            count = require_exact_nonneg_int("invocation count", count)
            if (agent_id, tick) in seen:
                raise ForkCheckpointError(
                    "fork_state_invalid", "duplicate invocation counter"
                )
            seen.add((agent_id, tick))
            counts.append((agent_id, tick, count))
        object.__setattr__(self, "invocation_counts", tuple(counts))
        revisions: list[tuple[str, int]] = []
        seen_goals: set[str] = set()
        for goal_entry in self.goal_revision_counters:
            if not isinstance(goal_entry, tuple) or len(goal_entry) != 2:
                raise ForkCheckpointError(
                "fork_state_invalid", "invalid goal counter"
            )
            goal_id, count = goal_entry
            if type(goal_id) is not str or goal_id in seen_goals:
                raise ForkCheckpointError(
                "fork_state_invalid", "invalid goal counter"
            )
            seen_goals.add(goal_id)
            revisions.append(
                (goal_id, require_exact_nonneg_int("goal revision count", count))
            )
        object.__setattr__(self, "goal_revision_counters", tuple(revisions))
        audit_names = {name for name, _ in self.audits}
        if audit_names != set(AUDIT_FIELD_NAMES):
            raise ForkCheckpointError(
                "fork_state_invalid", "audit inventory is incomplete"
            )
        for name, values in self.audits:
            if type(name) is not str or not isinstance(values, tuple):
                raise ForkCheckpointError("fork_state_invalid", "invalid audit state")


@dataclass(frozen=True, slots=True)
class RunnerForkCheckpoint:
    """Snapshot of one coherent finalized runner boundary."""

    run_id: RunId
    config: SimulationRunnerConfig
    config_fingerprint: str
    boundary_tick: Tick
    boundary_revision: WorldRevision
    snapshot: WorldSnapshot
    bootstrap: WorldBootstrap
    bootstrap_snapshot: WorldSnapshot
    registrations: tuple[AgentRegistration, ...]
    runtime_states: tuple[AgentRuntimeForkState, ...]
    owner_states: tuple[SubjectiveOwnerForkState, ...]
    runner_control: RunnerRuntimeCheckpoint
    capture_format_version: str = RUNNER_FORK_CHECKPOINT_VERSION

    def __post_init__(self) -> None:
        if self.capture_format_version != RUNNER_FORK_CHECKPOINT_VERSION:
            raise ForkCheckpointError(
                "fork_state_unsupported", "unsupported runner checkpoint version"
            )
        if type(self.run_id) is not RunId:
            raise ForkCheckpointError("fork_state_invalid", "invalid run_id")
        if type(self.config) is not SimulationRunnerConfig:
            raise ForkCheckpointError("fork_state_invalid", "invalid config")
        if type(self.boundary_tick) is not Tick:
            raise ForkCheckpointError("fork_state_invalid", "invalid boundary tick")
        if type(self.boundary_revision) is not WorldRevision:
            raise ForkCheckpointError("fork_state_invalid", "invalid revision")
        if type(self.snapshot) is not WorldSnapshot:
            raise ForkCheckpointError("fork_state_invalid", "invalid snapshot")
        if type(self.bootstrap) is not WorldBootstrap:
            raise ForkCheckpointError("fork_state_invalid", "invalid bootstrap")
        if type(self.bootstrap_snapshot) is not WorldSnapshot:
            raise ForkCheckpointError(
                "fork_state_invalid", "invalid bootstrap snapshot"
            )
        if self.bootstrap_snapshot.next_tick != Tick(0):
            raise ForkCheckpointError(
                "fork_state_invalid", "bootstrap snapshot must be tick zero"
            )
        if self.snapshot.run_id != self.run_id:
            raise ForkCheckpointError("fork_state_invalid", "snapshot run mismatch")
        if self.snapshot.next_tick != self.boundary_tick:
            raise ForkCheckpointError("fork_state_invalid", "snapshot tick mismatch")
        if self.snapshot.revision != self.boundary_revision:
            raise ForkCheckpointError(
                "fork_state_invalid", "snapshot revision mismatch"
            )
        registrations = _ordered(
            "registrations", self.registrations, AgentRegistration
        )
        if len({item.agent_id for item in registrations}) != len(registrations):
            raise ForkCheckpointError("fork_roster_mismatch", "duplicate registrations")
        owners = _ordered("owner_states", self.owner_states, SubjectiveOwnerForkState)
        runtimes = _ordered(
            "runtime_states", self.runtime_states, AgentRuntimeForkState
        )
        if len(owners) != len(runtimes) or len(owners) != len(registrations):
            raise ForkCheckpointError("fork_roster_mismatch", "incomplete roster")
        owner_ids = {state.scope.owner_id for state in owners}
        runtime_ids = {state.checkpoint.agent_id for state in runtimes}
        registration_ids = {item.agent_id for item in registrations}
        if owner_ids != registration_ids or runtime_ids != registration_ids:
            raise ForkCheckpointError(
                "fork_roster_mismatch", "roster identity mismatch"
            )
        for state in owners:
            if state.scope.run_id.value != self.run_id.value:
                raise ForkCheckpointError("fork_state_invalid", "owner run mismatch")
        if type(self.runner_control) is not RunnerRuntimeCheckpoint:
            raise ForkCheckpointError(
                "fork_state_invalid", "invalid runner control"
            )
        if self.runner_control.run_id != self.run_id:
            raise ForkCheckpointError(
                "fork_state_invalid", "runner control run mismatch"
            )
        if self.runner_control.ticks_committed != self.boundary_tick.value:
            raise ForkCheckpointError(
                "fork_boundary_not_finalized", "runner tick mismatch"
            )
        if self.runner_control.engine_revision != self.boundary_revision.value:
            raise ForkCheckpointError(
                "fork_state_invalid", "runner revision mismatch"
            )
        object.__setattr__(self, "registrations", registrations)
        object.__setattr__(self, "owner_states", owners)
        object.__setattr__(self, "runtime_states", runtimes)

    def owner_state(self, agent_id: AgentId) -> SubjectiveOwnerForkState:
        for state in self.owner_states:
            if state.scope.owner_id == agent_id:
                return state
        raise ForkCheckpointError("fork_roster_mismatch", "unknown owner")

    def runtime_state(self, agent_id: AgentId) -> AgentRuntimeForkState:
        for state in self.runtime_states:
            if state.checkpoint.agent_id == agent_id:
                return state
        raise ForkCheckpointError("fork_roster_mismatch", "unknown runtime")


def _audit_payload(state: AgentRuntimeForkState) -> list[object]:
    return [
        {
            "name": name,
            "row_count": len(values),
        }
        for name, values in state.audits
    ]


def fork_state_digest(checkpoint: RunnerForkCheckpoint) -> str:
    """Canonical scientific digest of explicit complete fork state values."""
    if type(checkpoint) is not RunnerForkCheckpoint:
        raise TypeError("fork_state_digest requires RunnerForkCheckpoint")
    owners = []
    for owner_state in sorted(
        checkpoint.owner_states, key=lambda item: item.scope.owner_id.value
    ):
        owners.append(
            {
                "agent_id": owner_state.scope.owner_id.value,
                "memory_trace_ids": sorted(
                    trace.memory_id.value for trace in owner_state.memory.traces
                ),
                "memory_reconstruction_ids": sorted(
                    record.reconstruction_id.value
                    for record in owner_state.memory.reconstructions
                ),
                "memory_access_operations": sorted(
                    owner_state.memory.access_operations
                ),
                "belief_ids": sorted(
                    belief.belief_id.value for belief in owner_state.belief.beliefs
                ),
                "belief_revision_ids": sorted(
                    revision.revision_id.value
                    for _, revisions in owner_state.belief.histories
                    for revision in revisions
                ),
                "relationship_ids": sorted(
                    profile.relationship_id.value
                    for profile in owner_state.relationship.profiles
                ),
                "relationship_revision_ids": sorted(
                    revision.revision_id.value
                    for _, revisions in owner_state.relationship.histories
                    for revision in revisions
                ),
                "revision": owner_state.commit.revision,
                "operations": sorted(
                    operation.operation_id
                    for operation in owner_state.commit.operations
                ),
            }
        )
    runtimes = []
    for runtime_state in sorted(
        checkpoint.runtime_states, key=lambda item: item.checkpoint.agent_id.value
    ):
        runtimes.append(
            {
                "agent_id": runtime_state.checkpoint.agent_id.value,
                "status": runtime_state.checkpoint.status.value,
                "internal_state": {
                    "invocation_count": (
                        runtime_state.checkpoint.internal_state.invocation_count
                    ),
                    "last_intention": (
                        None
                        if runtime_state.checkpoint.internal_state.last_intention
                        is None
                        else (
                            runtime_state.checkpoint.internal_state.last_intention.value
                        )
                    ),
                    "last_command_kind": (
                        runtime_state.checkpoint.internal_state.last_command_kind
                    ),
                },
                "last_observation_key": (
                    None
                    if runtime_state.checkpoint.last_observation_key is None
                    else list(runtime_state.checkpoint.last_observation_key)
                ),
                "goal_ids": sorted(
                    goal.goal_id.value for goal in runtime_state.checkpoint.goals
                ),
                "processed_invocations": sorted(runtime_state.processed_invocations),
                "finalized_hashes": sorted(runtime_state.finalized_hashes),
                "invocation_counts": [
                    [agent_id, tick, count]
                    for agent_id, tick, count in runtime_state.invocation_counts
                ],
                "goal_revision_counters": [
                    [goal_id, count]
                    for goal_id, count in runtime_state.goal_revision_counters
                ],
                "applied_identity_operation_ids": sorted(
                    runtime_state.applied_identity_operation_ids
                ),
                "applied_reflection_operation_ids": sorted(
                    runtime_state.applied_reflection_operation_ids
                ),
                "loop_deferred_count": len(
                    runtime_state.loop_state.deferred_dissonance
                ),
                "loop_scenario_count": len(
                    runtime_state.loop_state.last_counterfactual_scenarios
                ),
                "loop_entity_rates": list(
                    runtime_state.loop_state.developmental_entity_learning_rates
                ),
                "loop_stage_rates": list(
                    runtime_state.loop_state.developmental_stage_learning_rates
                ),
                "cultural_restored": runtime_state.cultural_restored,
                "cultural_fresh_channels": sorted(
                    runtime_state.cultural_fresh_channels
                ),
                "legacy_memory_ids": sorted(
                    trace.memory_id.value
                    for trace in runtime_state.legacy_memories
                ),
                "legacy_belief_ids": sorted(
                    belief.belief_id.value
                    for belief in runtime_state.legacy_beliefs
                ),
                "audits": _audit_payload(runtime_state),
            }
        )
    document = {
        "version": RUNNER_FORK_CHECKPOINT_VERSION,
        "run_id": checkpoint.run_id.value,
        "config_fingerprint": checkpoint.config_fingerprint,
        "boundary_tick": checkpoint.boundary_tick.value,
        "boundary_revision": checkpoint.boundary_revision.value,
        "snapshot_id": checkpoint.snapshot.snapshot_id.value,
        "snapshot_integrity_hash": checkpoint.snapshot.integrity_hash.value,
        "registrations": [
            [item.agent_id.value, item.entity_id.value]
            for item in checkpoint.registrations
        ],
        "owners": owners,
        "runtimes": runtimes,
    }
    encoded = json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AGENT_RUNTIME_FORK_STATE_VERSION",
    "AUDIT_FIELD_NAMES",
    "RUNNER_FORK_CHECKPOINT_VERSION",
    "AgentRuntimeForkState",
    "ForkCheckpointError",
    "RunnerForkCheckpoint",
    "fork_state_digest",
]
