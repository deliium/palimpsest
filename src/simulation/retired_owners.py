"""Frozen process-local state for owners retired from active cognition.

A retired owner keeps every objective/subjective export and audit needed by
fork capture, finalization and historical research, but no live cognitive loop,
memory index, retriever or mutable subjective service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agents.models import AgentId
from memory.beliefs import (
    BeliefRevisionResult,
    SemanticBelief,
    SemanticBeliefHistory,
)
from memory.models import (
    BeliefId,
    MemoryApplyResult,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryMutationBatch,
    MemoryRecallRequest,
    MemoryRecallResult,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryScope,
    MemoryTrace,
)
from simulation.clock import Tick
from simulation.fork_checkpoint import AgentRuntimeForkState
from simulation.models import RunId
from simulation.run_control import AgentRuntimeCheckpoint
from simulation.subjective_state import (
    SubjectiveApplyReceipt,
    SubjectiveMutationBatch,
    SubjectiveOwnerForkState,
    SubjectiveOwnerSnapshot,
)
from social.models import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipHistory,
    RelationshipRevisionRequest,
    RelationshipRevisionResult,
)
from world.identifiers import EntityId, require_exact_nonneg_int

if TYPE_CHECKING:
    from memory.beliefs import BeliefRevisionRequest

__all__ = [
    "ReadOnlyBeliefService",
    "ReadOnlyMemoryService",
    "ReadOnlyRelationshipService",
    "ReadOnlySubjectiveState",
    "RetiredOwnerBundle",
    "RetiredOwnerError",
    "RetiredOwnerRecord",
    "RuntimeRetentionPolicy",
]


class RetiredOwnerError(ValueError):
    """A mutation attempted on retired owner state."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(f"retired_owner_read_only: {operation}")


@dataclass(frozen=True, slots=True)
class RuntimeRetentionPolicy:
    """Composition-only activation for dead-owner runtime retirement."""

    retire_dead_owners: bool = False

    def __post_init__(self) -> None:
        if type(self.retire_dead_owners) is not bool:
            raise TypeError("retire_dead_owners must be bool")


@dataclass(frozen=True, slots=True)
class RetiredOwnerRecord:
    """Complete immutable owner state retained after live-graph release."""

    run_id: RunId
    agent_id: AgentId
    entity_id: EntityId
    ordinal: int
    boundary_tick: Tick
    death_tick: Tick
    runtime_checkpoint: AgentRuntimeCheckpoint
    runtime_fork_state: AgentRuntimeForkState
    subjective_state: SubjectiveOwnerForkState
    audits: tuple[tuple[str, tuple[object, ...]], ...]
    cultural_channels: frozenset[str]
    civilization_enabled: tuple[tuple[str, bool], ...]

    def __post_init__(self) -> None:
        if type(self.run_id) is not RunId:
            raise TypeError("RetiredOwnerRecord.run_id must be RunId")
        if type(self.agent_id) is not AgentId:
            raise TypeError("RetiredOwnerRecord.agent_id must be AgentId")
        if type(self.entity_id) is not EntityId:
            raise TypeError("RetiredOwnerRecord.entity_id must be EntityId")
        object.__setattr__(
            self,
            "ordinal",
            require_exact_nonneg_int("RetiredOwnerRecord.ordinal", self.ordinal),
        )
        if type(self.boundary_tick) is not Tick:
            raise TypeError("RetiredOwnerRecord.boundary_tick must be Tick")
        if type(self.death_tick) is not Tick:
            raise TypeError("RetiredOwnerRecord.death_tick must be Tick")
        if type(self.runtime_checkpoint) is not AgentRuntimeCheckpoint:
            raise TypeError("RetiredOwnerRecord.runtime_checkpoint is invalid")
        if type(self.runtime_fork_state) is not AgentRuntimeForkState:
            raise TypeError("RetiredOwnerRecord.runtime_fork_state is invalid")
        if type(self.subjective_state) is not SubjectiveOwnerForkState:
            raise TypeError("RetiredOwnerRecord.subjective_state is invalid")
        if self.runtime_checkpoint.agent_id != self.agent_id:
            raise ValueError("RetiredOwnerRecord runtime identity mismatch")
        if self.subjective_state.scope.owner_id != self.agent_id:
            raise ValueError("RetiredOwnerRecord subjective identity mismatch")
        if not isinstance(self.cultural_channels, frozenset) or any(
            type(item) is not str for item in self.cultural_channels
        ):
            raise TypeError("RetiredOwnerRecord.cultural_channels is invalid")
        for key, enabled in self.civilization_enabled:
            if type(key) is not str or type(enabled) is not bool:
                raise TypeError("RetiredOwnerRecord.civilization_enabled is invalid")


class ReadOnlyMemoryService:
    """Read-only view over frozen memory state; all writes reject."""

    __slots__ = ("_active", "_scope", "_traces")

    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._scope = state.scope
        self._traces = tuple(state.memory.traces)
        self._active = tuple(
            trace for trace in self._traces if trace.forgotten_at_tick is None
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        return self._active

    def sync_snapshot(self) -> tuple[MemoryTrace, ...]:
        return self._active

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        return next(
            (trace for trace in self._traces if trace.memory_id == memory_id),
            None,
        )

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        del request
        raise RetiredOwnerError("memory_retrieve")

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        del request
        raise RetiredOwnerError("memory_recall")

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        del batch
        raise RetiredOwnerError("memory_apply")

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        del request
        raise RetiredOwnerError("memory_forget")

    async def forget_selected_ids(
        self, memory_ids: tuple[MemoryId, ...], *, tick: int
    ) -> int:
        del memory_ids, tick
        raise RetiredOwnerError("memory_forget_selected_ids")


class ReadOnlyBeliefService:
    """Read-only view over frozen semantic beliefs."""

    __slots__ = ("_beliefs", "_histories")

    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._beliefs = tuple(state.belief.beliefs)
        self._histories = dict(state.belief.histories)

    async def snapshot(self) -> tuple[SemanticBelief, ...]:
        return self._beliefs

    async def get(self, belief_id: BeliefId) -> SemanticBelief | None:
        return next(
            (belief for belief in self._beliefs if belief.belief_id == belief_id),
            None,
        )

    async def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        revisions = self._histories.get(belief_id)
        if revisions is None:
            return None
        belief = await self.get(belief_id)
        if belief is None:
            return None
        return SemanticBeliefHistory(belief=belief, revisions=revisions)

    async def revise(self, request: BeliefRevisionRequest) -> BeliefRevisionResult:
        del request
        raise RetiredOwnerError("belief_revise")


class ReadOnlyRelationshipService:
    """Read-only view over frozen directed relationships."""

    __slots__ = ("_histories", "_profiles", "_source_id")

    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._source_id = state.scope.owner_id
        self._profiles = tuple(state.relationship.profiles)
        self._histories = dict(state.relationship.histories)

    @property
    def source_id(self) -> AgentId:
        return self._source_id

    async def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        return self._profiles

    async def get(
        self, relationship_id: RelationshipId
    ) -> DirectedRelationshipProfile | None:
        return next(
            (
                profile
                for profile in self._profiles
                if profile.relationship_id == relationship_id
            ),
            None,
        )

    async def history(
        self, relationship_id: RelationshipId
    ) -> RelationshipHistory | None:
        revisions = self._histories.get(relationship_id)
        if revisions is None:
            return None
        profile = await self.get(relationship_id)
        if profile is None:
            return None
        return RelationshipHistory(profile=profile, revisions=revisions)

    async def revise(
        self, request: RelationshipRevisionRequest
    ) -> RelationshipRevisionResult:
        del request
        raise RetiredOwnerError("relationship_revise")


class ReadOnlySubjectiveState:
    """Frozen commit view; every mutation rejects."""

    __slots__ = ("_state")

    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._state = state

    @property
    def scope(self) -> MemoryScope:
        return self._state.scope

    @property
    def revision(self) -> int:
        return self._state.commit.revision

    async def commit(
        self, batch: SubjectiveMutationBatch
    ) -> SubjectiveApplyReceipt:
        del batch
        raise RetiredOwnerError("subjective_commit")

    async def snapshot(self) -> SubjectiveOwnerSnapshot:
        memory = ReadOnlyMemoryService(self._state)
        belief = ReadOnlyBeliefService(self._state)
        relationship = ReadOnlyRelationshipService(self._state)
        memories = tuple(await memory.snapshot())
        return SubjectiveOwnerSnapshot(
            memories=memories,
            semantic_beliefs=tuple(await belief.snapshot()),
            relationships=tuple(await relationship.snapshot()),
            reconstruction_count=sum(
                1
                for trace in memories
                if trace.lineage.reconstruction_id is not None
            ),
        )


class _MemoryReader:
    def __init__(self, service: ReadOnlyMemoryService) -> None:
        self._service = service

    def snapshot(self) -> tuple[MemoryTrace, ...]:
        return self._service.sync_snapshot()


class _BeliefReader:
    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._beliefs = tuple(state.belief.beliefs)
        self._histories = dict(state.belief.histories)

    def snapshot(self) -> tuple[SemanticBelief, ...]:
        return self._beliefs

    def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        revisions = self._histories.get(belief_id)
        belief = next(
            (
                item
                for item in self._beliefs
                if item.belief_id == belief_id
            ),
            None,
        )
        if revisions is None or belief is None:
            return None
        return SemanticBeliefHistory(belief=belief, revisions=revisions)


class _RelationshipReader:
    def __init__(self, state: SubjectiveOwnerForkState) -> None:
        self._profiles = tuple(state.relationship.profiles)
        self._histories = dict(state.relationship.histories)

    def snapshot(self) -> tuple[DirectedRelationshipProfile, ...]:
        return self._profiles

    def history(self, relationship_id: RelationshipId) -> RelationshipHistory | None:
        revisions = self._histories.get(relationship_id)
        profile = next(
            (
                item
                for item in self._profiles
                if item.relationship_id == relationship_id
            ),
            None,
        )
        if revisions is None or profile is None:
            return None
        return RelationshipHistory(profile=profile, revisions=revisions)


class RetiredOwnerBundle:
    """Read-only subjective bundle backed only by a frozen record."""

    __slots__ = (
        "_belief",
        "_belief_reader",
        "_memory",
        "_memory_reader",
        "_relationship",
        "_relationship_reader",
        "_scope",
        "_subjective",
    )

    def __init__(self, record: RetiredOwnerRecord) -> None:
        state = record.subjective_state
        self._scope = state.scope
        self._memory = ReadOnlyMemoryService(state)
        self._belief = ReadOnlyBeliefService(state)
        self._relationship = ReadOnlyRelationshipService(state)
        self._subjective = ReadOnlySubjectiveState(state)
        self._memory_reader = _MemoryReader(self._memory)
        self._belief_reader = _BeliefReader(state)
        self._relationship_reader = _RelationshipReader(state)

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    @property
    def memory(self) -> ReadOnlyMemoryService:
        return self._memory

    @property
    def belief(self) -> ReadOnlyBeliefService:
        return self._belief

    @property
    def relationship(self) -> ReadOnlyRelationshipService:
        return self._relationship

    @property
    def commit_service(self) -> ReadOnlySubjectiveState:
        return self._subjective

    @property
    def memory_reader(self) -> _MemoryReader:
        return self._memory_reader

    @property
    def semantic_belief_reader(self) -> _BeliefReader:
        return self._belief_reader

    @property
    def relationship_reader(self) -> _RelationshipReader:
        return self._relationship_reader

    async def snapshot(self) -> SubjectiveOwnerSnapshot:
        memories = tuple(self._memory.sync_snapshot())
        return SubjectiveOwnerSnapshot(
            memories=memories,
            semantic_beliefs=tuple(self._belief._beliefs),
            relationships=tuple(self._relationship._profiles),
            reconstruction_count=sum(
                1
                for trace in memories
                if trace.lineage.reconstruction_id is not None
            ),
        )

    async def commit(
        self, batch: SubjectiveMutationBatch
    ) -> SubjectiveApplyReceipt:
        del batch
        raise RetiredOwnerError("bundle_commit")
