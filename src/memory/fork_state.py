"""Immutable owner-scoped fork state for in-memory memory and belief services.

These values are process-local continuation contracts, not durable subjective
wire formats. They preserve historical identities and operation receipts while
never exposing mutable service internals.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.models import AgentId
from memory.belief_formation import BeliefFormationPolicy
from memory.beliefs import (
    BeliefRevision,
    BeliefRevisionResult,
    SemanticBelief,
)
from memory.models import (
    Belief,
    BeliefId,
    MemoryId,
    MemoryRunId,
    MemoryScope,
    MemoryTrace,
    ReconstructionId,
    ReconstructionRecord,
)

MEMORY_FORK_STATE_VERSION: Final[str] = "memory-fork-state-v1"
BELIEF_FORK_STATE_VERSION: Final[str] = "belief-fork-state-v1"


class MemoryForkStateError(ValueError):
    """Fail-closed fork-state validation with a stable reason code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail or code}")


def _ordered[T](name: str, values: object, model_type: type[T]) -> tuple[T, ...]:
    if isinstance(values, (set, frozenset, Mapping)):
        raise MemoryForkStateError("fork_state_invalid", f"{name} must be ordered")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise MemoryForkStateError("fork_state_invalid", f"{name} must be a sequence")
    items = tuple(values)
    for item in items:
        if type(item) is not model_type:
            raise MemoryForkStateError(
                "fork_state_invalid", f"{name} entries must be {model_type.__name__}"
            )
    return items


@dataclass(frozen=True, slots=True)
class DerivationEdge:
    """One reconstruction derivation edge keyed by its derived memory."""

    memory_id: MemoryId
    source_memory_ids: tuple[MemoryId, ...]
    reconstruction_id: ReconstructionId | None

    def __post_init__(self) -> None:
        if type(self.memory_id) is not MemoryId:
            raise MemoryForkStateError("fork_state_invalid", "invalid memory_id")
        object.__setattr__(
            self,
            "source_memory_ids",
            _ordered("source_memory_ids", self.source_memory_ids, MemoryId),
        )
        if (
            self.reconstruction_id is not None
            and type(self.reconstruction_id) is not ReconstructionId
        ):
            raise MemoryForkStateError(
                "fork_state_invalid", "invalid reconstruction_id"
            )


@dataclass(frozen=True, slots=True)
class MemoryForkState:
    """Complete continuation state for one in-memory episodic memory service."""

    scope: MemoryScope
    traces: tuple[MemoryTrace, ...]
    reconstructions: tuple[ReconstructionRecord, ...]
    derivation_edges: tuple[DerivationEdge, ...]
    access_operations: tuple[tuple[str, str], ...]
    state_format_version: str = MEMORY_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != MEMORY_FORK_STATE_VERSION:
            raise MemoryForkStateError(
                "fork_state_unsupported", "unsupported memory fork-state version"
            )
        if type(self.scope) is not MemoryScope:
            raise MemoryForkStateError("fork_state_invalid", "invalid scope")
        traces = _ordered("traces", self.traces, MemoryTrace)
        reconstructions = _ordered(
            "reconstructions", self.reconstructions, ReconstructionRecord
        )
        edges = _ordered("derivation_edges", self.derivation_edges, DerivationEdge)
        if isinstance(self.access_operations, (set, frozenset)):
            access_operations = tuple(sorted(self.access_operations))
        elif isinstance(self.access_operations, (str, bytes)) or not isinstance(
            self.access_operations, Sequence
        ):
            raise MemoryForkStateError(
                "fork_state_invalid", "access_operations must be a sequence"
            )
        else:
            access_operations = tuple(self.access_operations)
        trace_ids: set[MemoryId] = set()
        for trace in traces:
            if trace.owner_id != self.scope.owner_id:
                raise MemoryForkStateError(
                    "fork_owner_mismatch", "trace owner does not match scope"
                )
            if trace.memory_id in trace_ids:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate memory_id"
                )
            trace_ids.add(trace.memory_id)
        reconstruction_ids: set[ReconstructionId] = set()
        for record in reconstructions:
            if record.owner_id != self.scope.owner_id:
                raise MemoryForkStateError(
                    "fork_owner_mismatch", "reconstruction owner does not match scope"
                )
            if record.run_id != self.scope.run_id:
                raise MemoryForkStateError(
                    "fork_state_invalid", "reconstruction run does not match scope"
                )
            if record.reconstruction_id in reconstruction_ids:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate reconstruction_id"
                )
            reconstruction_ids.add(record.reconstruction_id)
            for source_id in record.source_memory_ids:
                if source_id not in trace_ids:
                    raise MemoryForkStateError(
                        "fork_state_invalid", "unknown reconstruction source trace"
                    )
        seen_edges: set[MemoryId] = set()
        for edge in edges:
            if edge.memory_id in seen_edges:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate derivation edge"
                )
            seen_edges.add(edge.memory_id)
            for source_id in edge.source_memory_ids:
                if source_id not in trace_ids:
                    raise MemoryForkStateError(
                        "fork_state_invalid", "unknown derivation source trace"
                    )
            if (
                edge.reconstruction_id is not None
                and edge.reconstruction_id not in reconstruction_ids
            ):
                raise MemoryForkStateError(
                    "fork_state_invalid", "unknown derivation reconstruction"
                )
        seen_ops: set[tuple[str, str]] = set()
        for entry in access_operations:
            if (
                not isinstance(entry, tuple)
                or len(entry) != 2
                or type(entry[0]) is not str
                or type(entry[1]) is not str
            ):
                raise MemoryForkStateError(
                    "fork_state_invalid", "invalid access operation entry"
                )
            if entry in seen_ops:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate access operation"
                )
            seen_ops.add(entry)
        object.__setattr__(self, "traces", traces)
        object.__setattr__(self, "reconstructions", reconstructions)
        object.__setattr__(self, "derivation_edges", edges)
        object.__setattr__(
            self, "access_operations", tuple(sorted(access_operations))
        )

    def rebased(self, target_scope: MemoryScope) -> MemoryForkState:
        """Return the same state scoped to a new run with an identical owner."""
        if type(target_scope) is not MemoryScope:
            raise MemoryForkStateError("fork_state_invalid", "invalid target scope")
        if target_scope.owner_id != self.scope.owner_id:
            raise MemoryForkStateError(
                "fork_owner_mismatch", "target owner does not match source owner"
            )
        if target_scope == self.scope:
            return self
        reconstructions = tuple(
            replace(record, run_id=MemoryRunId(target_scope.run_id.value))
            for record in self.reconstructions
        )
        return replace(
            self,
            scope=target_scope,
            reconstructions=reconstructions,
        )


@dataclass(frozen=True, slots=True)
class BeliefOperation:
    """One idempotency receipt retained by the semantic belief service."""

    operation_id: str
    fingerprint: str
    result: BeliefRevisionResult

    def __post_init__(self) -> None:
        if type(self.operation_id) is not str or not self.operation_id:
            raise MemoryForkStateError("fork_state_invalid", "invalid operation_id")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise MemoryForkStateError("fork_state_invalid", "invalid fingerprint")
        if type(self.result) is not BeliefRevisionResult:
            raise MemoryForkStateError("fork_state_invalid", "invalid result")


@dataclass(frozen=True, slots=True)
class BeliefForkState:
    """Complete continuation state for one in-memory semantic belief service."""

    scope: MemoryScope
    policy: BeliefFormationPolicy
    beliefs: tuple[SemanticBelief, ...]
    histories: tuple[tuple[BeliefId, tuple[BeliefRevision, ...]], ...]
    operations: tuple[BeliefOperation, ...]
    state_format_version: str = BELIEF_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != BELIEF_FORK_STATE_VERSION:
            raise MemoryForkStateError(
                "fork_state_unsupported", "unsupported belief fork-state version"
            )
        if type(self.scope) is not MemoryScope:
            raise MemoryForkStateError("fork_state_invalid", "invalid scope")
        if type(self.policy) is not BeliefFormationPolicy:
            raise MemoryForkStateError("fork_state_invalid", "invalid policy")
        beliefs = _ordered("beliefs", self.beliefs, SemanticBelief)
        if isinstance(self.histories, (set, frozenset, Mapping)) or not isinstance(
            self.histories, Sequence
        ):
            raise MemoryForkStateError("fork_state_invalid", "invalid histories")
        histories: list[tuple[BeliefId, tuple[BeliefRevision, ...]]] = []
        belief_ids: set[BeliefId] = set()
        for entry in self.histories:
            if not isinstance(entry, tuple) or len(entry) != 2:
                raise MemoryForkStateError("fork_state_invalid", "invalid history")
            belief_id, revisions = entry
            if type(belief_id) is not BeliefId:
                raise MemoryForkStateError("fork_state_invalid", "invalid history key")
            if isinstance(revisions, (str, bytes)) or not isinstance(
                revisions, Sequence
            ):
                raise MemoryForkStateError(
                    "fork_state_invalid", "invalid history revisions"
                )
            raw_revisions = tuple(revisions)
            if not raw_revisions:
                raise MemoryForkStateError("fork_state_invalid", "empty history")
            for revision in raw_revisions:
                if type(revision) is not BeliefRevision:
                    raise MemoryForkStateError(
                        "fork_state_invalid", "invalid revision"
                    )
                if revision.belief_id != belief_id:
                    raise MemoryForkStateError(
                        "fork_state_invalid", "history belief mismatch"
                    )
            histories.append((belief_id, raw_revisions))
        for belief in beliefs:
            if belief.owner_id != self.scope.owner_id:
                raise MemoryForkStateError(
                    "fork_owner_mismatch", "belief owner does not match scope"
                )
            if belief.belief_id in belief_ids:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate belief_id"
                )
            belief_ids.add(belief.belief_id)
        history_ids = {belief_id for belief_id, _ in histories}
        if history_ids != belief_ids:
            raise MemoryForkStateError(
                "fork_state_invalid", "beliefs and histories disagree"
            )
        for belief in beliefs:
            history = next(
                revisions
                for belief_id, revisions in histories
                if belief_id == belief.belief_id
            )
            if history[-1].revision_id != belief.current_revision_id:
                raise MemoryForkStateError(
                    "fork_state_invalid", "belief history head mismatch"
                )
        operations = _ordered("operations", self.operations, BeliefOperation)
        seen_ops: set[str] = set()
        for operation in operations:
            if operation.operation_id in seen_ops:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate belief operation"
                )
            seen_ops.add(operation.operation_id)
            if operation.result.belief_id not in belief_ids:
                raise MemoryForkStateError(
                    "fork_state_invalid", "operation references unknown belief"
                )
        object.__setattr__(self, "beliefs", beliefs)
        object.__setattr__(self, "histories", tuple(histories))
        object.__setattr__(self, "operations", operations)

    def rebased(self, target_scope: MemoryScope) -> BeliefForkState:
        """Return the same belief state scoped to a new run for one owner."""
        if type(target_scope) is not MemoryScope:
            raise MemoryForkStateError("fork_state_invalid", "invalid target scope")
        if target_scope.owner_id != self.scope.owner_id:
            raise MemoryForkStateError(
                "fork_owner_mismatch", "target owner does not match source owner"
            )
        if target_scope == self.scope:
            return self
        return replace(self, scope=target_scope)

    def histories_for(self, belief_id: BeliefId) -> tuple[BeliefRevision, ...]:
        for current_id, revisions in self.histories:
            if current_id == belief_id:
                return revisions
        raise MemoryForkStateError("fork_state_invalid", "missing belief history")


@dataclass(frozen=True, slots=True)
class LegacyBeliefForkState:
    """Detached state of the legacy ``BeliefStore`` used by runtime intents."""

    owner_id: AgentId
    beliefs: tuple[Belief, ...]
    state_format_version: str = BELIEF_FORK_STATE_VERSION

    def __post_init__(self) -> None:
        if self.state_format_version != BELIEF_FORK_STATE_VERSION:
            raise MemoryForkStateError(
                "fork_state_unsupported", "unsupported legacy belief version"
            )
        if type(self.owner_id) is not AgentId:
            raise MemoryForkStateError("fork_state_invalid", "invalid owner")
        beliefs = _ordered("beliefs", self.beliefs, Belief)
        seen: set[BeliefId] = set()
        for belief in beliefs:
            if belief.owner_id != self.owner_id:
                raise MemoryForkStateError(
                    "fork_owner_mismatch", "legacy belief owner mismatch"
                )
            if belief.belief_id in seen:
                raise MemoryForkStateError(
                    "fork_state_invalid", "duplicate legacy belief_id"
                )
            seen.add(belief.belief_id)
        object.__setattr__(self, "beliefs", beliefs)


def validate_legacy_traces(
    owner_id: AgentId, traces: Sequence[MemoryTrace]
) -> tuple[MemoryTrace, ...]:
    """Validate detached legacy memory rows before installing them."""
    if type(owner_id) is not AgentId:
        raise MemoryForkStateError("fork_state_invalid", "invalid owner")
    values = _ordered("traces", traces, MemoryTrace)
    seen: set[MemoryId] = set()
    for trace in values:
        if trace.owner_id != owner_id:
            raise MemoryForkStateError(
                "fork_owner_mismatch", "legacy trace owner mismatch"
            )
        if trace.memory_id in seen:
            raise MemoryForkStateError("fork_state_invalid", "duplicate trace")
        seen.add(trace.memory_id)
    return values


__all__ = [
    "BELIEF_FORK_STATE_VERSION",
    "MEMORY_FORK_STATE_VERSION",
    "BeliefForkState",
    "BeliefOperation",
    "DerivationEdge",
    "LegacyBeliefForkState",
    "MemoryForkState",
    "MemoryForkStateError",
    "validate_legacy_traces",
]
