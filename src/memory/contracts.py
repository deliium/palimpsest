"""Ports for owner-validating memory and belief access."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from memory.models import (
    Belief,
    MemoryApplyResult,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryMutationBatch,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryScope,
    MemoryTrace,
    OwnershipError,
)

__all__ = [
    "BeliefReader",
    "BeliefWriter",
    "MemoryReader",
    "MemoryService",
    "MemoryWriter",
    "OwnershipError",
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
