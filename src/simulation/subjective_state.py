"""Atomic owner-scoped subjective state commit boundary.

Applies episodic memory mutations, semantic belief revisions, and relationship
revisions for one ``(run_id, owner_id)`` scope with full prevalidation,
copy-then-swap rollback, and idempotent operation receipts. Objective world
commit/replay is never touched.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from agents.models import AgentId
from memory.beliefs import BeliefRevisionRequest
from memory.models import (
    MemoryAccessReceipt,
    MemoryMutationBatch,
    MemoryRunId,
    MemoryScope,
    MemoryTrace,
    ReconstructionRecord,
)
from social.relationships import RelationshipRevisionRequest
from world.identifiers import (
    require_bounded_text,
    require_exact_nonneg_int,
    require_stable_id,
)

__all__ = [
    "InMemorySubjectiveStateService",
    "SubjectiveApplyReceipt",
    "SubjectiveMutationBatch",
    "SubjectiveStateError",
    "SubjectiveStateErrorCode",
    "SubjectiveStateService",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.subjective_state")
_MAX_BATCH_ITEMS: Final[int] = 256
_MAX_OPERATION_CHARS: Final[int] = 128


class SubjectiveStateErrorCode(StrEnum):
    """Stable reason codes for subjective commit failures."""

    INVALID_REQUEST = "invalid_request"
    OWNERSHIP = "ownership"
    CONFLICT = "conflict"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ADAPTER_FAILED = "adapter_failed"
    ROLLBACK = "rollback"


class SubjectiveStateError(Exception):
    """Fail-closed subjective commit error (metadata-only public surface)."""

    def __init__(
        self,
        code: SubjectiveStateErrorCode,
        *,
        run_id: str | None = None,
        owner_id: str | None = None,
        operation_id: str | None = None,
        adapter: str | None = None,
    ) -> None:
        if type(code) is not SubjectiveStateErrorCode:
            raise TypeError("code must be SubjectiveStateErrorCode")
        self.code = code
        self.run_id = run_id
        self.owner_id = owner_id
        self.operation_id = operation_id
        self.adapter = adapter
        parts = [f"code={code.value}"]
        if run_id is not None:
            parts.append(f"run_id={run_id}")
        if owner_id is not None:
            parts.append(f"owner_id={owner_id}")
        if operation_id is not None:
            parts.append(f"operation_id={operation_id}")
        if adapter is not None:
            parts.append(f"adapter={adapter}")
        super().__init__(",".join(parts))

    def __repr__(self) -> str:
        return f"SubjectiveStateError({self})"


@dataclass(frozen=True, slots=True)
class SubjectiveMutationBatch:
    """Atomic subjective mutation request for one owner scope."""

    operation_id: str
    logical_tick: int
    memory_writes: tuple[MemoryTrace, ...] = ()
    memory_accesses: tuple[MemoryAccessReceipt, ...] = ()
    reconstructions: tuple[ReconstructionRecord, ...] = ()
    belief_revisions: tuple[BeliefRevisionRequest, ...] = ()
    relationship_revisions: tuple[RelationshipRevisionRequest, ...] = ()
    expected_revision: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            require_bounded_text(
                "SubjectiveMutationBatch.operation_id",
                self.operation_id,
                max_length=_MAX_OPERATION_CHARS,
            ),
        )
        object.__setattr__(
            self,
            "logical_tick",
            require_exact_nonneg_int(
                "SubjectiveMutationBatch.logical_tick", self.logical_tick
            ),
        )
        for name, values, model in (
            ("memory_writes", self.memory_writes, MemoryTrace),
            ("memory_accesses", self.memory_accesses, MemoryAccessReceipt),
            ("reconstructions", self.reconstructions, ReconstructionRecord),
            ("belief_revisions", self.belief_revisions, BeliefRevisionRequest),
            (
                "relationship_revisions",
                self.relationship_revisions,
                RelationshipRevisionRequest,
            ),
        ):
            if isinstance(values, (set, frozenset)):
                raise TypeError(f"SubjectiveMutationBatch.{name}: not_ordered")
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise TypeError(f"SubjectiveMutationBatch.{name}: not_ordered")
            items = tuple(values)
            if len(items) > _MAX_BATCH_ITEMS:
                raise ValueError(f"SubjectiveMutationBatch.{name}: exceeds_max")
            for item in items:
                if type(item) is not model:
                    raise TypeError(f"SubjectiveMutationBatch.{name}: invalid_type")
            object.__setattr__(self, name, items)
        if self.expected_revision is not None:
            object.__setattr__(
                self,
                "expected_revision",
                require_exact_nonneg_int(
                    "SubjectiveMutationBatch.expected_revision",
                    self.expected_revision,
                ),
            )

    def __repr__(self) -> str:
        return (
            f"SubjectiveMutationBatch(operation_id={self.operation_id!r}, "
            f"logical_tick={self.logical_tick}, "
            f"memory_write_count={len(self.memory_writes)}, "
            f"belief_revision_count={len(self.belief_revisions)}, "
            f"relationship_revision_count={len(self.relationship_revisions)}, "
            f"expected_revision={self.expected_revision})"
        )


@dataclass(frozen=True, slots=True)
class SubjectiveApplyReceipt:
    """Idempotent receipt for one subjective commit (counts/IDs only)."""

    operation_id: str
    revision: int
    memory_written_count: int
    memory_access_count: int
    reconstruction_written_count: int
    belief_revision_count: int
    relationship_revision_count: int
    belief_activated_count: int = 0
    belief_retired_count: int = 0
    idempotent: bool = False

    def __post_init__(self) -> None:
        require_stable_id("SubjectiveApplyReceipt.operation_id", self.operation_id)
        for name in (
            "revision",
            "memory_written_count",
            "memory_access_count",
            "reconstruction_written_count",
            "belief_revision_count",
            "relationship_revision_count",
            "belief_activated_count",
            "belief_retired_count",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"SubjectiveApplyReceipt.{name}", getattr(self, name)
                ),
            )
        if type(self.idempotent) is not bool:
            raise TypeError("SubjectiveApplyReceipt.idempotent must be bool")

    def __repr__(self) -> str:
        return (
            f"SubjectiveApplyReceipt(operation_id={self.operation_id!r}, "
            f"revision={self.revision}, idempotent={self.idempotent}, "
            f"memory_written_count={self.memory_written_count}, "
            f"belief_revision_count={self.belief_revision_count}, "
            f"relationship_revision_count={self.relationship_revision_count})"
        )


class _MemoryAdapter(Protocol):
    @property
    def scope(self) -> MemoryScope: ...

    async def apply(self, batch: MemoryMutationBatch) -> object: ...

    def capture_transaction_state(self) -> object: ...

    def restore_transaction_state(self, state: object) -> None: ...


class _BeliefAdapter(Protocol):
    async def revise(self, request: BeliefRevisionRequest) -> object: ...

    def capture_transaction_state(self) -> object: ...

    def restore_transaction_state(self, state: object) -> None: ...


class _RelationshipAdapter(Protocol):
    async def revise(self, request: RelationshipRevisionRequest) -> object: ...

    def capture_transaction_state(self) -> object: ...

    def restore_transaction_state(self, state: object) -> None: ...


class SubjectiveStateService(Protocol):
    """Owner-scoped atomic subjective commit port."""

    @property
    def scope(self) -> MemoryScope: ...

    @property
    def revision(self) -> int: ...

    async def commit(
        self, batch: SubjectiveMutationBatch
    ) -> SubjectiveApplyReceipt: ...


def _batch_fingerprint(batch: SubjectiveMutationBatch) -> str:
    parts = [
        batch.operation_id,
        str(batch.logical_tick),
        str(batch.expected_revision),
        str(len(batch.memory_writes)),
        str(len(batch.memory_accesses)),
        str(len(batch.reconstructions)),
        str(len(batch.belief_revisions)),
        str(len(batch.relationship_revisions)),
    ]
    for write in batch.memory_writes:
        parts.append(write.memory_id.value)
    for access in batch.memory_accesses:
        parts.append(f"{access.memory_id.value}:{access.operation_id}")
    for reconstruction in batch.reconstructions:
        parts.append(reconstruction.reconstruction_id.value)
    for belief_revision in batch.belief_revisions:
        parts.append(belief_revision.operation_id)
    for relationship_revision in batch.relationship_revisions:
        parts.append(relationship_revision.operation_id)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


class InMemorySubjectiveStateService:
    """Copy-then-swap in-memory subjective commit service."""

    __slots__ = (
        "_belief",
        "_lock",
        "_memory",
        "_ops",
        "_relationship",
        "_revision",
        "_scope",
    )

    def __init__(
        self,
        scope: MemoryScope,
        *,
        memory_service: _MemoryAdapter,
        belief_service: _BeliefAdapter | None = None,
        relationship_service: _RelationshipAdapter | None = None,
    ) -> None:
        if type(scope) is not MemoryScope:
            raise TypeError("InMemorySubjectiveStateService requires MemoryScope")
        if memory_service.scope != scope:
            raise ValueError("memory_service scope mismatch")
        self._scope = scope
        self._memory = memory_service
        self._belief = belief_service
        self._relationship = relationship_service
        self._revision = 0
        self._ops: dict[str, tuple[str, SubjectiveApplyReceipt]] = {}
        self._lock = asyncio.Lock()
        _LOG.info(
            "subjective_service_created",
            extra={
                "operation": "create",
                "run_id": scope.run_id.value,
                "owner_id": scope.owner_id.value,
            },
        )

    @property
    def scope(self) -> MemoryScope:
        return self._scope

    @property
    def revision(self) -> int:
        return self._revision

    async def commit(self, batch: SubjectiveMutationBatch) -> SubjectiveApplyReceipt:
        if type(batch) is not SubjectiveMutationBatch:
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.INVALID_REQUEST,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
            )
        async with self._lock:
            return await self._commit_locked(batch)

    async def _commit_locked(
        self, batch: SubjectiveMutationBatch
    ) -> SubjectiveApplyReceipt:
        owner = self._scope.owner_id
        run_id = self._scope.run_id.value
        fingerprint = _batch_fingerprint(batch)
        prior = self._ops.get(batch.operation_id)
        if prior is not None:
            prior_fp, prior_receipt = prior
            if prior_fp != fingerprint:
                _LOG.warning(
                    "subjective_commit_idempotency_conflict",
                    extra={
                        "operation": "commit",
                        "run_id": run_id,
                        "owner_id": owner.value,
                        "operation_id": batch.operation_id,
                        "reason_code": (
                            SubjectiveStateErrorCode.IDEMPOTENCY_CONFLICT.value
                        ),
                    },
                )
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.IDEMPOTENCY_CONFLICT,
                    run_id=run_id,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                )
            _LOG.debug(
                "subjective_commit_idempotent",
                extra={
                    "operation": "commit",
                    "run_id": run_id,
                    "owner_id": owner.value,
                    "operation_id": batch.operation_id,
                    "revision": prior_receipt.revision,
                    "status": "idempotent",
                },
            )
            return prior_receipt

        if (
            batch.expected_revision is not None
            and batch.expected_revision != self._revision
        ):
            _LOG.warning(
                "subjective_commit_conflict",
                extra={
                    "operation": "commit",
                    "run_id": run_id,
                    "owner_id": owner.value,
                    "operation_id": batch.operation_id,
                    "expected_revision": batch.expected_revision,
                    "actual_revision": self._revision,
                    "reason_code": SubjectiveStateErrorCode.CONFLICT.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.CONFLICT,
                run_id=run_id,
                owner_id=owner.value,
                operation_id=batch.operation_id,
            )

        self._prevalidate(batch)

        _LOG.debug(
            "subjective_commit_start",
            extra={
                "operation": "commit",
                "run_id": run_id,
                "owner_id": owner.value,
                "operation_id": batch.operation_id,
                "expected_revision": batch.expected_revision,
                "tick": batch.logical_tick,
                "memory_write_count": len(batch.memory_writes),
                "memory_access_count": len(batch.memory_accesses),
                "reconstruction_count": len(batch.reconstructions),
                "belief_revision_count": len(batch.belief_revisions),
                "relationship_revision_count": len(batch.relationship_revisions),
                "status": "start",
            },
        )

        memory_state = self._memory.capture_transaction_state()
        belief_state = (
            None if self._belief is None else self._belief.capture_transaction_state()
        )
        relationship_state = (
            None
            if self._relationship is None
            else self._relationship.capture_transaction_state()
        )

        belief_activated = 0
        belief_retired = 0
        try:
            memory_result = await self._memory.apply(
                MemoryMutationBatch(
                    writes=batch.memory_writes,
                    accesses=batch.memory_accesses,
                    reconstructions=batch.reconstructions,
                    operation_id=batch.operation_id,
                )
            )
            for belief_request in batch.belief_revisions:
                if self._belief is None:
                    raise SubjectiveStateError(
                        SubjectiveStateErrorCode.ADAPTER_FAILED,
                        run_id=run_id,
                        owner_id=owner.value,
                        operation_id=batch.operation_id,
                        adapter="belief",
                    )
                result = await self._belief.revise(belief_request)
                created = getattr(result, "created", False)
                retired = getattr(result, "retired", False)
                if created:
                    belief_activated += 1
                if retired:
                    belief_retired += 1
            for relationship_request in batch.relationship_revisions:
                if self._relationship is None:
                    raise SubjectiveStateError(
                        SubjectiveStateErrorCode.ADAPTER_FAILED,
                        run_id=run_id,
                        owner_id=owner.value,
                        operation_id=batch.operation_id,
                        adapter="relationship",
                    )
                await self._relationship.revise(relationship_request)
        except SubjectiveStateError:
            self._rollback(
                memory_state=memory_state,
                belief_state=belief_state,
                relationship_state=relationship_state,
                operation_id=batch.operation_id,
            )
            raise
        except Exception as exc:
            adapter = type(exc).__module__.split(".")[0]
            self._rollback(
                memory_state=memory_state,
                belief_state=belief_state,
                relationship_state=relationship_state,
                operation_id=batch.operation_id,
                adapter=adapter,
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.ADAPTER_FAILED,
                run_id=run_id,
                owner_id=owner.value,
                operation_id=batch.operation_id,
                adapter=adapter,
            ) from None

        self._revision += 1
        receipt = SubjectiveApplyReceipt(
            operation_id=batch.operation_id,
            revision=self._revision,
            memory_written_count=int(getattr(memory_result, "written_count", 0)),
            memory_access_count=int(getattr(memory_result, "access_applied_count", 0)),
            reconstruction_written_count=int(
                getattr(memory_result, "reconstruction_written_count", 0)
            ),
            belief_revision_count=len(batch.belief_revisions),
            relationship_revision_count=len(batch.relationship_revisions),
            belief_activated_count=belief_activated,
            belief_retired_count=belief_retired,
            idempotent=False,
        )
        self._ops[batch.operation_id] = (fingerprint, receipt)
        _LOG.debug(
            "subjective_commit_complete",
            extra={
                "operation": "commit",
                "run_id": run_id,
                "owner_id": owner.value,
                "operation_id": batch.operation_id,
                "revision": receipt.revision,
                "tick": batch.logical_tick,
                "memory_write_count": receipt.memory_written_count,
                "belief_revision_count": receipt.belief_revision_count,
                "relationship_revision_count": receipt.relationship_revision_count,
                "status": "complete",
            },
        )
        if belief_activated or belief_retired:
            _LOG.info(
                "subjective_commit_activation",
                extra={
                    "operation": "commit",
                    "run_id": run_id,
                    "owner_id": owner.value,
                    "operation_id": batch.operation_id,
                    "belief_activated_count": belief_activated,
                    "belief_retired_count": belief_retired,
                },
            )
        return receipt

    def _prevalidate(self, batch: SubjectiveMutationBatch) -> None:
        owner = self._scope.owner_id
        for write in batch.memory_writes:
            if write.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
            if write.created_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
        for reconstruction in batch.reconstructions:
            if reconstruction.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="memory",
                )
        for belief_request in batch.belief_revisions:
            if belief_request.owner_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="belief",
                )
            if belief_request.logical_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="belief",
                )
        for relationship_request in batch.relationship_revisions:
            if relationship_request.source_id != owner:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.OWNERSHIP,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="relationship",
                )
            if relationship_request.logical_tick != batch.logical_tick:
                raise SubjectiveStateError(
                    SubjectiveStateErrorCode.INVALID_REQUEST,
                    run_id=self._scope.run_id.value,
                    owner_id=owner.value,
                    operation_id=batch.operation_id,
                    adapter="relationship",
                )

    def _rollback(
        self,
        *,
        memory_state: object,
        belief_state: object | None,
        relationship_state: object | None,
        operation_id: str,
        adapter: str | None = None,
    ) -> None:
        try:
            self._memory.restore_transaction_state(memory_state)
            if belief_state is not None and self._belief is not None:
                self._belief.restore_transaction_state(belief_state)
            if relationship_state is not None and self._relationship is not None:
                self._relationship.restore_transaction_state(relationship_state)
        except Exception:
            _LOG.error(
                "subjective_commit_rollback_failed",
                extra={
                    "operation": "commit",
                    "run_id": self._scope.run_id.value,
                    "owner_id": self._scope.owner_id.value,
                    "operation_id": operation_id,
                    "adapter": adapter,
                    "reason_code": SubjectiveStateErrorCode.ROLLBACK.value,
                },
            )
            raise SubjectiveStateError(
                SubjectiveStateErrorCode.ROLLBACK,
                run_id=self._scope.run_id.value,
                owner_id=self._scope.owner_id.value,
                operation_id=operation_id,
                adapter=adapter,
            ) from None
        _LOG.error(
            "subjective_commit_rolled_back",
            extra={
                "operation": "commit",
                "run_id": self._scope.run_id.value,
                "owner_id": self._scope.owner_id.value,
                "operation_id": operation_id,
                "adapter": adapter,
                "reason_code": SubjectiveStateErrorCode.ADAPTER_FAILED.value,
            },
        )


def subjective_operation_id(*, owner_id: AgentId, invocation_id: str) -> str:
    """Deterministic subjective operation id derived from a runtime invocation."""
    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    require_stable_id("invocation_id", invocation_id)
    return f"subj:{owner_id.value}:{invocation_id}"


def require_memory_run_id(value: str) -> MemoryRunId:
    return MemoryRunId(value)
