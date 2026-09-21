"""Deterministic fake memory components for network-free tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from memory.codec import reconstructed_memory_payload_sha256
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
from memory.scoring import rank_traces

__all__ = [
    "FakeEmbedder",
    "FakeEmbedderCallRecord",
    "FakeLogicalTickSource",
    "FakeMemoryCallRecord",
    "FakeMemoryService",
]


class FakeMemoryFailureCode(StrEnum):
    FOREIGN_OWNER = "foreign_owner"
    UNKNOWN_EMBED_KEY = "unknown_embed_key"
    DIMENSION_MISMATCH = "dimension_mismatch"


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


@dataclass(frozen=True, slots=True)
class FakeEmbedderCallRecord:
    key: str
    dimension: int
    status: str

    def __repr__(self) -> str:
        return (
            f"FakeEmbedderCallRecord(key={self.key!r}, "
            f"dimension={self.dimension}, status={self.status!r})"
        )


class FakeLogicalTickSource:
    """Explicit logical tick source; never reads wall clocks."""

    def __init__(self, initial: int = 0) -> None:
        if isinstance(initial, bool) or not isinstance(initial, int) or initial < 0:
            raise ValueError("FakeLogicalTickSource: invalid_initial_tick")
        self._tick = initial

    def current(self) -> int:
        return self._tick

    def advance(self, steps: int = 1) -> int:
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise ValueError("FakeLogicalTickSource: invalid_steps")
        self._tick += steps
        return self._tick

    def __repr__(self) -> str:
        return f"FakeLogicalTickSource(tick={self._tick})"


class FakeEmbedder:
    """Scriptable embedder keyed by canonical strings; metadata-only call history."""

    def __init__(
        self,
        *,
        vectors: dict[str, tuple[float, ...]],
        model: str = "fake",
        version: str = "1",
    ) -> None:
        if not vectors:
            raise ValueError("FakeEmbedder: empty_vectors")
        dims = {len(vector) for vector in vectors.values()}
        if len(dims) != 1:
            raise ValueError("FakeEmbedder: inconsistent_dimensions")
        self._vectors = {key: tuple(vector) for key, vector in vectors.items()}
        self._dimension = next(iter(dims))
        self._model = model
        self._version = version
        self.calls: list[FakeEmbedderCallRecord] = []

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, key: str, *, dimension: int | None = None) -> MemoryEmbedding:
        expected = self._dimension if dimension is None else dimension
        if expected != self._dimension:
            self.calls.append(
                FakeEmbedderCallRecord(
                    key=key,
                    dimension=expected,
                    status=FakeMemoryFailureCode.DIMENSION_MISMATCH.value,
                )
            )
            raise ValueError(FakeMemoryFailureCode.DIMENSION_MISMATCH.value)
        vector = self._vectors.get(key)
        if vector is None:
            self.calls.append(
                FakeEmbedderCallRecord(
                    key=key,
                    dimension=expected,
                    status=FakeMemoryFailureCode.UNKNOWN_EMBED_KEY.value,
                )
            )
            raise ValueError(FakeMemoryFailureCode.UNKNOWN_EMBED_KEY.value)
        self.calls.append(
            FakeEmbedderCallRecord(key=key, dimension=expected, status="ok")
        )
        return MemoryEmbedding(vector=vector, model=self._model, version=self._version)

    def __repr__(self) -> str:
        return (
            f"FakeEmbedder(dimension={self._dimension}, "
            f"key_count={len(self._vectors)}, call_count={len(self.calls)})"
        )


class FakeMemoryService:
    """Scriptable in-process MemoryService double with metadata-only call history."""

    def __init__(self, scope: MemoryScope) -> None:
        self._scope = scope
        self._records: dict[MemoryId, MemoryTrace] = {}
        self._reconstructions: dict[ReconstructionId, ReconstructionRecord] = {}
        self.calls: list[FakeMemoryCallRecord] = []
        self._orchestrator = MemoryRecallOrchestrator()

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    async def retrieve(self, request: MemoryRetrieveRequest) -> MemoryRetrieveResult:
        embeddings = {
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
        self.calls.append(
            FakeMemoryCallRecord(
                operation="retrieve",
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                tick=request.current_tick,
                write_count=0,
                access_count=len(pending),
                result_count=len(hits),
            )
        )
        return MemoryRetrieveResult(
            hits=hits,
            pending_accesses=pending,
            candidate_count=candidate_count,
            retrieval_tick=request.current_tick,
            scoring_policy_version=request.scoring_policy.version,
        )

    async def recall(self, request: MemoryRecallRequest) -> MemoryRecallResult:
        self.calls.append(
            FakeMemoryCallRecord(
                operation="recall",
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                tick=request.retrieve.current_tick,
                write_count=0,
                access_count=0,
                result_count=0,
            )
        )
        return await self._orchestrator.recall(self, request)

    async def apply(self, batch: MemoryMutationBatch) -> MemoryApplyResult:
        existing_hashes = {
            reconstruction_id: reconstructed_memory_payload_sha256(record.reconstructed)
            for reconstruction_id, record in self._reconstructions.items()
        }
        prepared = prepare_memory_mutation(
            batch,
            scope=self._scope,
            existing_traces=self._records,
            existing_reconstruction_hashes=existing_hashes,
        )
        for record in prepared.reconstructions_to_insert:
            self._reconstructions[record.reconstruction_id] = record
        for write in prepared.writes_to_insert:
            self._records[write.memory_id] = write
        written = len(prepared.writes_to_insert)
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
            reconstruction_written_count=len(prepared.reconstructions_to_insert),
            reconstruction_idempotent_count=prepared.reconstruction_idempotent_count,
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
