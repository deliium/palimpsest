"""Ports for owner-validating memory and belief access."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from memory.beliefs import (
    BeliefRevisionRequest,
    BeliefRevisionResult,
    SemanticBelief,
    SemanticBeliefHistory,
)
from memory.models import (
    Belief,
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
    OwnershipError,
    RecallEvidence,
    ReconstructedMemory,
)

__all__ = [
    "BeliefReader",
    "BeliefWriter",
    "MemoryReader",
    "MemoryReconstructor",
    "MemoryService",
    "MemoryWriter",
    "OwnershipError",
    "SemanticBeliefReader",
    "SemanticBeliefService",
    "SemanticBeliefWriter",
]


class MemoryReader(Protocol):
    def snapshot(self) -> tuple[MemoryTrace, ...]:
        """Return a defensive immutable snapshot of owned memories."""
        ...


class MemoryWriter(Protocol):
    def write(self, record: MemoryTrace) -> None:
        """Persist ``record`` if it belongs to this aggregate's owner."""
        ...


class BeliefReader(Protocol):
    def snapshot(self) -> tuple[Belief, ...]:
        """Return a defensive immutable snapshot of owned beliefs."""
        ...


class BeliefWriter(Protocol):
    def write(self, belief: Belief) -> None:
        """Persist ``belief`` if it belongs to this aggregate's owner."""
        ...


class SemanticBeliefReader(Protocol):
    def snapshot(self) -> tuple[SemanticBelief, ...]:
        """Return a defensive immutable snapshot of owned semantic beliefs."""
        ...

    def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        """Return append-only revision history for one owned belief."""
        ...


class SemanticBeliefWriter(Protocol):
    def write(self, history: SemanticBeliefHistory) -> None:
        """Persist ``history`` if it belongs to this aggregate's owner."""
        ...


@runtime_checkable
class SemanticBeliefService(Protocol):
    """Owner-bound semantic belief formation and revision service."""

    async def revise(self, request: BeliefRevisionRequest) -> BeliefRevisionResult:
        """Form or revise a belief; same operation ID retries are idempotent."""
        ...

    async def get(self, belief_id: BeliefId) -> SemanticBelief | None:
        """Fetch one scoped belief head; foreign/missing IDs are indistinguishable."""
        ...

    async def history(self, belief_id: BeliefId) -> SemanticBeliefHistory | None:
        """Return complete append-only history for one scoped belief."""
        ...

    async def snapshot(self) -> tuple[SemanticBelief, ...]:
        """Return all semantic belief heads for this owner scope."""
        ...


@runtime_checkable
class MemoryReconstructor(Protocol):
    """Pure reconstruction policy over bounded recall evidence.

    Implementations must not accept ``WorldEvent``, event repositories, or
    other world authority. Output remains subjective and non-authoritative.
    """

    async def reconstruct(self, evidence: RecallEvidence) -> ReconstructedMemory:
        """Project ``evidence`` into one validated reconstructed episode."""
        ...


@runtime_checkable
class MemoryService(Protocol):
    """Owner-bound asynchronous episodic memory service.

    Implementations bind exactly one :class:`MemoryScope` at construction and
    must not expose unscoped get/list/query methods. Retrieve is observational;
    writes and access receipts apply only through :meth:`apply`.
    """

    @property
    def scope(self) -> MemoryScope:
        """Fixed run and owner binding for this service instance."""
        ...

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        """Rank scoped traces; return snapshots and pending access receipts."""
        ...

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        """Owner-scoped reconstructive recall over retrieved evidence."""
        ...

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        """Atomically apply writes and access receipts within this scope."""
        ...

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        """Fetch one scoped snapshot; foreign/missing IDs are indistinguishable."""
        ...

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        """Return all active (non-forgotten) traces for this scope."""
        ...

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        """Soft-forget traces under the bound scope at an explicit tick."""
        ...
