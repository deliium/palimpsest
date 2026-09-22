"""In-memory pending-finalization and attempt-state repositories."""

from __future__ import annotations

from simulation.models import RunId
from simulation.persistence import (
    PendingFinalizationRecord,
    PendingFinalizationStatus,
    RunnerAttemptStateRecord,
)

__all__ = [
    "InMemoryPendingFinalizationRepository",
    "InMemoryRunnerAttemptStateRepository",
]


class InMemoryPendingFinalizationRepository:
    """Copy-on-write in-memory outbox for unit tests."""

    __slots__ = ("_rows",)

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], PendingFinalizationRecord] = {}

    async def append_pending(self, record: PendingFinalizationRecord) -> None:
        key = (record.run_id.value, record.agent_id, record.invocation_id)
        existing = self._rows.get(key)
        if existing is not None:
            if (
                existing.integrity_hash != record.integrity_hash
                or existing.payload != record.payload
                or existing.status is not PendingFinalizationStatus.PENDING
            ):
                raise ValueError("pending_conflict")
            return
        self._rows[key] = record

    async def mark_finalized(
        self, *, run_id: RunId, agent_id: str, invocation_id: str
    ) -> None:
        await self._mark(
            run_id=run_id,
            agent_id=agent_id,
            invocation_id=invocation_id,
            status=PendingFinalizationStatus.FINALIZED,
        )

    async def mark_aborted(
        self, *, run_id: RunId, agent_id: str, invocation_id: str
    ) -> None:
        await self._mark(
            run_id=run_id,
            agent_id=agent_id,
            invocation_id=invocation_id,
            status=PendingFinalizationStatus.ABORTED,
        )

    async def list_pending_for_tick(
        self, *, run_id: RunId, tick: int
    ) -> tuple[PendingFinalizationRecord, ...]:
        items = [
            row
            for row in self._rows.values()
            if row.run_id == run_id
            and row.tick == tick
            and row.status is PendingFinalizationStatus.PENDING
        ]
        items.sort(key=lambda item: (item.agent_id, item.invocation_id))
        return tuple(items)

    async def list_pending_for_run(
        self, *, run_id: RunId
    ) -> tuple[PendingFinalizationRecord, ...]:
        items = [
            row
            for row in self._rows.values()
            if row.run_id == run_id and row.status is PendingFinalizationStatus.PENDING
        ]
        items.sort(key=lambda item: (item.tick, item.agent_id, item.invocation_id))
        return tuple(items)

    async def _mark(
        self,
        *,
        run_id: RunId,
        agent_id: str,
        invocation_id: str,
        status: PendingFinalizationStatus,
    ) -> None:
        key = (run_id.value, agent_id, invocation_id)
        existing = self._rows.get(key)
        if existing is None:
            raise ValueError("pending_missing")
        if existing.status is status:
            return
        if existing.status is not PendingFinalizationStatus.PENDING:
            raise ValueError("pending_status_conflict")
        self._rows[key] = PendingFinalizationRecord(
            run_id=existing.run_id,
            agent_id=existing.agent_id,
            tick=existing.tick,
            invocation_id=existing.invocation_id,
            integrity_hash=existing.integrity_hash,
            codec_version=existing.codec_version,
            payload=existing.payload,
            status=status,
        )


class InMemoryRunnerAttemptStateRepository:
    """In-memory attempt recovery records for unit tests."""

    __slots__ = ("_rows",)

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], RunnerAttemptStateRecord] = {}

    async def append_attempt(self, record: RunnerAttemptStateRecord) -> None:
        key = (record.run_id.value, record.attempt_id)
        existing = self._rows.get(key)
        if existing is not None:
            if existing != record:
                raise ValueError("attempt_conflict")
            return
        self._rows[key] = record

    async def list_recovery_required(
        self, *, run_id: RunId
    ) -> tuple[RunnerAttemptStateRecord, ...]:
        items = [
            row
            for row in self._rows.values()
            if row.run_id == run_id and row.recovery_required
        ]
        items.sort(key=lambda item: (item.tick, item.attempt_id))
        return tuple(items)
