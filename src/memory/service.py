"""Owner-bound in-memory ``MemoryService`` reference implementation.

Deterministic, wall-clock-free, and metadata-only in operational logs. Conflicting
ID reuse is rejected; access receipts are idempotent by operation ID.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from memory.errors import MemoryServiceError, MemoryServiceErrorCode
from memory.models import (
    MemoryAccessReceipt,
    MemoryApplyResult,
    MemoryEmbedding,
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
    ReconstructionId,
    ReconstructionRecord,
)
from memory.mutation import prepare_memory_mutation
from memory.reconstruction import MemoryRecallOrchestrator
from memory.scoring import rank_traces, should_forget

__all__ = [
    "InMemoryMemoryService",
    "MemoryServiceError",
    "MemoryServiceErrorCode",
]

_LOG: Final[logging.Logger] = logging.getLogger("memory.service")


class InMemoryMemoryService:
    """Pure in-process episodic memory service bound to one :class:`MemoryScope`."""

    __slots__ = (
        "_access_ops",
        "_derivation_edges",
        "_orchestrator",
        "_reconstructions",
        "_records",
        "_scope",
    )

    def __init__(
        self,
        scope: MemoryScope,
        *,
        reconstructor: object | None = None,
    ) -> None:
        if type(scope) is not MemoryScope:
            raise TypeError("InMemoryMemoryService requires MemoryScope")
        self._scope = scope
        self._records: dict[MemoryId, MemoryTrace] = {}
        self._reconstructions: dict[ReconstructionId, ReconstructionRecord] = {}
        self._derivation_edges: dict[
            MemoryId, tuple[tuple[MemoryId, ...], ReconstructionId | None]
        ] = {}
        self._access_ops: set[tuple[str, str]] = set()
        from memory.contracts import MemoryReconstructor

        typed: MemoryReconstructor | None
        if reconstructor is None:
            typed = None
        else:
            typed = reconstructor  # type: ignore[assignment]
        self._orchestrator = MemoryRecallOrchestrator(typed)
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

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        if type(request) is not MemoryRecallRequest:
            _LOG.error(
                "memory_recall_invalid",
                extra={
                    "operation": "recall",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": MemoryServiceErrorCode.INVALID_REQUEST.value,
                },
            )
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_REQUEST)
        for belief in request.beliefs:
            if belief.owner_id != self._scope.owner_id:
                _LOG.error(
                    "memory_recall_ownership",
                    extra={
                        "operation": "recall",
                        "run_id": self._scope.run_id.value,
                        "owner_id": self._scope.owner_id.value,
                        "reason_code": MemoryServiceErrorCode.OWNERSHIP.value,
                    },
                )
                raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        return await self._orchestrator.recall(self, request)

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        if type(batch) is not MemoryMutationBatch:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        from memory.codec import reconstructed_memory_payload_sha256

        existing_hashes = {
            reconstruction_id: reconstructed_memory_payload_sha256(record.reconstructed)
            for reconstruction_id, record in self._reconstructions.items()
        }
        try:
            prepared = prepare_memory_mutation(
                batch,
                scope=self._scope,
                existing_traces=self._records,
                existing_reconstruction_hashes=existing_hashes,
            )
        except MemoryServiceError as exc:
            _LOG.error(
                "memory_apply_rejected",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": exc.code.value,
                    "write_count": len(batch.writes),
                    "access_count": len(batch.accesses),
                    "reconstruction_count": len(batch.reconstructions),
                },
            )
            raise

        records = dict(self._records)
        reconstructions = dict(self._reconstructions)
        derivation_edges = dict(self._derivation_edges)
        access_ops = set(self._access_ops)

        for record in prepared.reconstructions_to_insert:
            reconstructions[record.reconstruction_id] = record
        for write in prepared.writes_to_insert:
            records[write.memory_id] = write
            if write.lineage.source_memory_ids:
                derivation_edges[write.memory_id] = (
                    write.lineage.source_memory_ids,
                    write.lineage.reconstruction_id,
                )

        applied = 0
        idempotent = 0
        for access in batch.accesses:
            key = (access.operation_id, access.memory_id.value)
            if key in access_ops:
                idempotent += 1
                continue
            current = records[access.memory_id]
            records[access.memory_id] = replace(
                current,
                last_access_tick=max(current.last_access_tick, access.access_tick),
                access_count=current.access_count + 1,
            )
            access_ops.add(key)
            applied += 1

        self._records = records
        self._reconstructions = reconstructions
        self._derivation_edges = derivation_edges
        self._access_ops = access_ops

        written = len(prepared.writes_to_insert)
        reconstruction_written = len(prepared.reconstructions_to_insert)
        _LOG.debug(
            "memory_apply_complete",
            extra={
                "operation": "apply",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "write_count": written,
                "access_count": applied,
                "access_idempotent_count": idempotent,
                "reconstruction_written_count": reconstruction_written,
                "reconstruction_idempotent_count": (
                    prepared.reconstruction_idempotent_count
                ),
                "status": "ok",
            },
        )
        if reconstruction_written:
            _LOG.info(
                "memory_reconsolidation_committed",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reconstruction_written_count": reconstruction_written,
                    "write_count": written,
                },
            )
        elif prepared.reconstruction_idempotent_count:
            _LOG.warning(
                "memory_reconsolidation_idempotent",
                extra={
                    "operation": "apply",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "reason_code": "duplicate_reconstruction",
                    "reconstruction_idempotent_count": (
                        prepared.reconstruction_idempotent_count
                    ),
                },
            )
        else:
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
            reconstruction_written_count=reconstruction_written,
            reconstruction_idempotent_count=prepared.reconstruction_idempotent_count,
        )

    async def get(self, memory_id: MemoryId) -> MemoryTrace | None:
        if type(memory_id) is not MemoryId:
            raise TypeError("get requires MemoryId")
        trace = self._records.get(memory_id)
        if trace is None or trace.owner_id != self._scope.owner_id:
            return None
        return self._with_lineage_edges(trace)

    async def snapshot(self) -> tuple[MemoryTrace, ...]:
        return tuple(
            self._with_lineage_edges(trace)
            for trace in self._records.values()
            if trace.forgotten_at_tick is None
        )

    def _with_lineage_edges(self, trace: MemoryTrace) -> MemoryTrace:
        edges = self._derivation_edges.get(trace.memory_id)
        if edges is None:
            return trace
        sources, reconstruction_id = edges
        lineage = trace.lineage
        if (
            lineage.source_memory_ids == sources
            and lineage.reconstruction_id == reconstruction_id
        ):
            return trace
        return replace(
            trace,
            lineage=replace(
                lineage,
                source_memory_ids=sources,
                reconstruction_id=reconstruction_id,
            ),
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
