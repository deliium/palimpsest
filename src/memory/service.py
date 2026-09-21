"""Owner-bound in-memory ``MemoryService`` reference implementation.

Deterministic, wall-clock-free, and metadata-only in operational logs. Conflicting
ID reuse is rejected; access receipts are idempotent by operation ID.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from enum import StrEnum
from typing import Final

from memory.models import (
    MemoryAccessReceipt,
    MemoryApplyResult,
    MemoryEmbedding,
    MemoryForgetRequest,
    MemoryForgetResult,
    MemoryId,
    MemoryMutationBatch,
    MemoryRetrieveRequest,
    MemoryRetrieveResult,
    MemoryScope,
    MemoryTrace,
)
from memory.scoring import rank_traces, should_forget

__all__ = [
    "InMemoryMemoryService",
    "MemoryServiceError",
    "MemoryServiceErrorCode",
]

_LOG: Final[logging.Logger] = logging.getLogger("memory.service")


class MemoryServiceErrorCode(StrEnum):
    """Stable ERROR/WARN reason codes for the memory application boundary."""

    CONFLICT = "conflict"
    OWNERSHIP = "ownership"
    NOT_FOUND = "not_found"
    INVALID_BATCH = "invalid_batch"
    INVALID_REQUEST = "invalid_request"


class MemoryServiceError(ValueError):
    """Fail-closed service error with a stable reason code only."""

    def __init__(self, code: MemoryServiceErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


class InMemoryMemoryService:
    """Pure in-process episodic memory service bound to one :class:`MemoryScope`."""

    __slots__ = (
        "_access_ops",
        "_records",
        "_scope",
    )

    def __init__(self, scope: MemoryScope) -> None:
        if type(scope) is not MemoryScope:
            raise TypeError("InMemoryMemoryService requires MemoryScope")
        self._scope = scope
        self._records: dict[MemoryId, MemoryTrace] = {}
        self._access_ops: set[tuple[str, str]] = set()
        _LOG.info(
            "memory_service_created",
            extra={
                "operation": "create",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
            },
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        if type(request) is not MemoryRetrieveRequest:
            _LOG.error(
                "memory_retrieve_invalid",
                extra={
                    "operation": "retrieve",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": MemoryServiceErrorCode.INVALID_REQUEST.value,
                },
            )
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        embeddings: dict[str, MemoryEmbedding] = {
            trace.memory_id.value: trace.embedding
            for trace in self._records.values()
            if trace.embedding is not None
        }
        hits, candidate_count = rank_traces(
            tuple(self._records.values()),
            policy=request.scoring_policy,
            current_tick=request.current_tick,
            filters=request.filters,
            context=request.context,
            query_embedding=request.query_embedding,
            embeddings=embeddings,
            limit=request.limit,
        )
        operation_id = request.operation_id or (
            f"retrieve:{request.current_tick}:{request.scoring_policy.version}"
        )
        pending = tuple(
            MemoryAccessReceipt(
                memory_id=hit.trace.memory_id,
                access_tick=request.current_tick,
                operation_id=operation_id,
            )
            for hit in hits
        )
        _LOG.debug(
            "memory_retrieve_complete",
            extra={
                "operation": "retrieve",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "tick": request.current_tick,
                "policy_version": request.scoring_policy.version,
                "enabled_components": list(
                    request.scoring_policy.weights.enabled_components()
                ),
                "candidate_count": candidate_count,
                "result_count": len(hits),
            },
        )
        return MemoryRetrieveResult(
            hits=hits,
            pending_accesses=pending,
            candidate_count=candidate_count,
            retrieval_tick=request.current_tick,
            scoring_policy_version=request.scoring_policy.version,
        )

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        if type(batch) is not MemoryMutationBatch:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        for write in batch.writes:
            if write.owner_id != self._scope.owner_id:
                _LOG.error(
                    "memory_apply_ownership",
                    extra={
                        "operation": "apply",
                        "run_id": self._scope.run_id.value,
                        "owner_id": self._scope.owner_id.value,
                        "reason_code": MemoryServiceErrorCode.OWNERSHIP.value,
                    },
                )
                raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
            if write.memory_id in self._records:
                _LOG.error(
                    "memory_apply_conflict",
                    extra={
                        "operation": "apply",
                        "run_id": self._scope.run_id.value,
                        "owner_id": self._scope.owner_id.value,
                        "reason_code": MemoryServiceErrorCode.CONFLICT.value,
                    },
                )
                raise MemoryServiceError(MemoryServiceErrorCode.CONFLICT)
        for access in batch.accesses:
            if access.memory_id not in self._records:
                raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)
            existing = self._records[access.memory_id]
            if existing.owner_id != self._scope.owner_id:
                raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
            if access.access_tick < existing.created_tick:
                raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)

        written = 0
        applied = 0
        idempotent = 0
        for write in batch.writes:
            self._records[write.memory_id] = write
            written += 1
        for access in batch.accesses:
            key = (access.operation_id, access.memory_id.value)
            if key in self._access_ops:
                idempotent += 1
                continue
            current = self._records[access.memory_id]
            updated = replace(
                current,
                last_access_tick=max(current.last_access_tick, access.access_tick),
                access_count=current.access_count + 1,
            )
            self._records[access.memory_id] = updated
            self._access_ops.add(key)
            applied += 1
        _LOG.debug(
            "memory_apply_complete",
            extra={
                "operation": "apply",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "write_count": written,
                "access_count": applied,
                "status": "ok",
            },
        )
        _LOG.info(
            "memory_apply_counts",
            extra={
                "operation": "apply",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "write_count": written,
                "access_count": applied,
            },
        )
        return MemoryApplyResult(
            written_count=written,
            access_applied_count=applied,
            access_idempotent_count=idempotent,
        )

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        if type(memory_id) is not MemoryId:
            raise TypeError("get requires MemoryId")
        trace = self._records.get(memory_id)
        if trace is None or trace.owner_id != self._scope.owner_id:
            return None
        return trace

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        return tuple(
            trace for trace in self._records.values() if trace.forgotten_at_tick is None
        )

    async def forget(self, request: MemoryForgetRequest) -> MemoryForgetResult:
        if type(request) is not MemoryForgetRequest:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        examined = 0
        forgotten = 0
        for memory_id, trace in list(self._records.items()):
            examined += 1
            if should_forget(
                trace,
                current_tick=request.current_tick,
                policy=request.retention_policy,
            ):
                self._records[memory_id] = replace(
                    trace, forgotten_at_tick=request.current_tick
                )
                forgotten += 1
        _LOG.info(
            "memory_forget_complete",
            extra={
                "operation": "forget",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "tick": request.current_tick,
                "policy_version": request.retention_policy.version,
                "forgotten_count": forgotten,
                "examined_count": examined,
            },
        )
        return MemoryForgetResult(forgotten_count=forgotten, examined_count=examined)
