"""Deterministic fake memory components for network-free tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from memory.models import (
    MemoryApplyResult,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryMutationBatch,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryScope,
    MemoryTrace,
)

__all__ = [
    "FakeMemoryCallRecord",
    "FakeMemoryService",
]


class FakeMemoryFailureCode(StrEnum):
    FOREIGN_OWNER = "foreign_owner"


@dataclass(frozen=True, slots=True)
class FakeMemoryCallRecord:
    operation: str
    run_id: str
    owner_id: str
    tick: int | None
    write_count: int
    access_count: int
    result_count: int

    def __repr__(self) -> str:
        return (
            f"FakeMemoryCallRecord(operation={self.operation!r}, "
            f"owner_id={self.owner_id!r}, write_count={self.write_count}, "
            f"access_count={self.access_count}, result_count={self.result_count})"
        )


class FakeMemoryService:
    """Scriptable in-process MemoryService double with metadata-only call history."""

    def __init__(self, scope: MemoryScope) -> None:
        self._scope = scope
        self._records: dict[MemoryId, MemoryTrace] = {}
        self.calls: list[FakeMemoryCallRecord] = []

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        active = [
            trace for trace in self._records.values() if trace.forgotten_at_tick is None
        ]
        self.calls.append(
            FakeMemoryCallRecord(
                operation="retrieve",
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                tick=request.current_tick,
                write_count=0,
                access_count=0,
                result_count=min(len(active), request.limit),
            )
        )
        return MemoryRetrieveResult(
            hits=(),
            pending_accesses=(),
            candidate_count=len(active),
            retrieval_tick=request.current_tick,
            scoring_policy_version=request.scoring_policy.version,
        )

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        written = 0
        for write in batch.writes:
            if write.owner_id != self._scope.owner_id:
                raise ValueError(FakeMemoryFailureCode.FOREIGN_OWNER.value)
            self._records[write.memory_id] = write
            written += 1
        self.calls.append(
            FakeMemoryCallRecord(
                operation="apply",
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                tick=None,
                write_count=written,
                access_count=len(batch.accesses),
                result_count=0,
            )
        )
        return MemoryApplyResult(
            written_count=written,
            access_applied_count=len(batch.accesses),
            access_idempotent_count=0,
        )

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        return self._records.get(memory_id)

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        return tuple(
            trace for trace in self._records.values() if trace.forgotten_at_tick is None
        )

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        _ = request
        return MemoryForgetResult(forgotten_count=0, examined_count=len(self._records))
