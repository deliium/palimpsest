"""Shared atomic mutation validation for memory services (log-free helpers).

Services own logging at the apply boundary. Helpers raise
:class:`MemoryServiceError` with stable reason codes only.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from memory.codec import reconstructed_memory_payload_sha256
from memory.errors import MemoryServiceError, MemoryServiceErrorCode
from memory.models import (
    MemoryId,
    MemoryMutationBatch,
    MemoryScope,
    MemoryTrace,
    ReconstructionId,
    ReconstructionRecord,
)

__all__ = [
    "PreparedMemoryMutation",
    "prepare_memory_mutation",
]


@dataclass(frozen=True, slots=True)
class PreparedMemoryMutation:
    """Validated plan for an atomic apply (insert lists + idempotent skips)."""

    reconstructions_to_insert: tuple[ReconstructionRecord, ...]
    reconstruction_hashes: Mapping[ReconstructionId, str]
    reconstruction_idempotent_count: int
    writes_to_insert: tuple[MemoryTrace, ...]
    write_idempotent_count: int


def prepare_memory_mutation(
    batch: MemoryMutationBatch,
    *,
    scope: MemoryScope,
    existing_traces: Mapping[MemoryId, MemoryTrace],
    existing_reconstruction_hashes: Mapping[ReconstructionId, str],
) -> PreparedMemoryMutation:
    """Validate a mutation batch against bound-scope store state.

    Sources must already exist in ``existing_traces`` or appear as earlier writes
    in the same batch. Derived/reconstruction IDs must be fresh unless the
    reconstruction retry is idempotent (same payload hash).
    """
    if type(batch) is not MemoryMutationBatch:
        raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
    if type(scope) is not MemoryScope:
        raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)

    batch_writes: dict[MemoryId, MemoryTrace] = {}
    for write in batch.writes:
        if write.owner_id != scope.owner_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        batch_writes[write.memory_id] = write

    for access in batch.accesses:
        if access.memory_id not in existing_traces:
            raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)
        existing = existing_traces[access.memory_id]
        if existing.owner_id != scope.owner_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        if access.access_tick < existing.created_tick:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)

    reconstruction_hashes: dict[ReconstructionId, str] = {}
    reconstructions_to_insert: list[ReconstructionRecord] = []
    reconstruction_idempotent = 0
    idempotent_reconstruction_ids: set[ReconstructionId] = set()

    for record in batch.reconstructions:
        if record.run_id != scope.run_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        if record.owner_id != scope.owner_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        payload_hash = reconstructed_memory_payload_sha256(record.reconstructed)
        reconstruction_hashes[record.reconstruction_id] = payload_hash
        existing_hash = existing_reconstruction_hashes.get(record.reconstruction_id)
        if existing_hash is not None:
            if existing_hash != payload_hash:
                raise MemoryServiceError(MemoryServiceErrorCode.CONFLICT)
            reconstruction_idempotent += 1
            idempotent_reconstruction_ids.add(record.reconstruction_id)
            continue
        _validate_reconstruction_sources(
            record,
            scope=scope,
            existing_traces=existing_traces,
            batch_writes=batch_writes,
        )
        reconstructions_to_insert.append(record)

    known_reconstruction_ids = set(existing_reconstruction_hashes) | {
        item.reconstruction_id for item in batch.reconstructions
    }

    writes_to_insert: list[MemoryTrace] = []
    write_idempotent = 0
    pending_by_id: dict[MemoryId, MemoryTrace] = dict(existing_traces)

    for write in batch.writes:
        if write.memory_id in existing_traces:
            lineage = write.lineage
            if (
                lineage.reconstruction_id is not None
                and lineage.reconstruction_id in idempotent_reconstruction_ids
            ):
                write_idempotent += 1
                continue
            raise MemoryServiceError(MemoryServiceErrorCode.CONFLICT)
        _validate_write_lineage(
            write,
            scope=scope,
            pending_traces=pending_by_id,
            batch_writes=batch_writes,
            known_reconstruction_ids=known_reconstruction_ids,
        )
        writes_to_insert.append(write)
        pending_by_id[write.memory_id] = write

    _reject_batch_cycles(writes_to_insert)

    return PreparedMemoryMutation(
        reconstructions_to_insert=tuple(reconstructions_to_insert),
        reconstruction_hashes=reconstruction_hashes,
        reconstruction_idempotent_count=reconstruction_idempotent,
        writes_to_insert=tuple(writes_to_insert),
        write_idempotent_count=write_idempotent,
    )


def _resolve_trace(
    memory_id: MemoryId,
    *,
    existing_traces: Mapping[MemoryId, MemoryTrace],
    batch_writes: Mapping[MemoryId, MemoryTrace],
    allow_batch_writes: bool,
) -> MemoryTrace | None:
    if memory_id in existing_traces:
        return existing_traces[memory_id]
    if allow_batch_writes and memory_id in batch_writes:
        return batch_writes[memory_id]
    return None


def _validate_reconstruction_sources(
    record: ReconstructionRecord,
    *,
    scope: MemoryScope,
    existing_traces: Mapping[MemoryId, MemoryTrace],
    batch_writes: Mapping[MemoryId, MemoryTrace],
) -> None:
    derived_ids = {
        write.memory_id
        for write in batch_writes.values()
        if write.lineage.reconstruction_id == record.reconstruction_id
    }
    generations: list[int] = []
    for source_id in record.source_memory_ids:
        if source_id in derived_ids:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        parent = _resolve_trace(
            source_id,
            existing_traces=existing_traces,
            batch_writes=batch_writes,
            allow_batch_writes=True,
        )
        if parent is None:
            raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)
        if parent.owner_id != scope.owner_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        if parent.memory_id in derived_ids:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        generations.append(parent.lineage.generation)
    expected = 1 + max(generations)
    if record.reconstructed.generation != expected:
        raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)


def _validate_write_lineage(
    write: MemoryTrace,
    *,
    scope: MemoryScope,
    pending_traces: Mapping[MemoryId, MemoryTrace],
    batch_writes: Mapping[MemoryId, MemoryTrace],
    known_reconstruction_ids: set[ReconstructionId],
) -> None:
    lineage = write.lineage
    if not lineage.source_memory_ids:
        if lineage.reconstruction_id is not None:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        return
    if lineage.reconstruction_id is not None:
        if lineage.reconstruction_id not in known_reconstruction_ids:
            raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)
    generations: list[int] = []
    for source_id in lineage.source_memory_ids:
        if source_id == write.memory_id:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        parent = pending_traces.get(source_id)
        if parent is None:
            parent = batch_writes.get(source_id)
        if parent is None:
            raise MemoryServiceError(MemoryServiceErrorCode.NOT_FOUND)
        if parent.owner_id != scope.owner_id:
            raise MemoryServiceError(MemoryServiceErrorCode.OWNERSHIP)
        if _ancestry_contains(
            parent,
            target=write.memory_id,
            traces=pending_traces,
            batch_writes=batch_writes,
        ):
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        generations.append(parent.lineage.generation)
    expected = 1 + max(generations)
    if lineage.generation != expected:
        raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)


def _ancestry_contains(
    start: MemoryTrace,
    *,
    target: MemoryId,
    traces: Mapping[MemoryId, MemoryTrace],
    batch_writes: Mapping[MemoryId, MemoryTrace],
) -> bool:
    stack = list(start.lineage.source_memory_ids)
    seen: set[MemoryId] = set()
    while stack:
        current_id = stack.pop()
        if current_id == target:
            return True
        if current_id in seen:
            continue
        seen.add(current_id)
        current = traces.get(current_id) or batch_writes.get(current_id)
        if current is None:
            continue
        stack.extend(current.lineage.source_memory_ids)
    return False


def _reject_batch_cycles(writes: list[MemoryTrace]) -> None:
    edges: dict[MemoryId, tuple[MemoryId, ...]] = {
        write.memory_id: write.lineage.source_memory_ids for write in writes
    }
    write_ids = set(edges)
    visiting: set[MemoryId] = set()
    visited: set[MemoryId] = set()

    def visit(node: MemoryId) -> None:
        if node in visited:
            return
        if node in visiting:
            raise MemoryServiceError(MemoryServiceErrorCode.INVALID_BATCH)
        visiting.add(node)
        for source in edges.get(node, ()):
            if source in write_ids:
                visit(source)
        visiting.remove(node)
        visited.add(node)

    for memory_id in write_ids:
        visit(memory_id)
