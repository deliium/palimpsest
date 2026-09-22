"""SQLAlchemy adapters for runner pending-finalization outbox."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import PersistenceAdapterError, PersistenceConflictError
from persistence.orm import RunnerAttemptStateOrm, RunnerPendingFinalizationOrm
from simulation.models import RunId
from simulation.persistence import (
    PENDING_FINALIZATION_CODEC_VERSION,
    PendingFinalizationRecord,
    PendingFinalizationStatus,
    RunnerAttemptStateRecord,
)

_LOGGER = get_logger("persistence.runner_sqlalchemy")

__all__ = [
    "SqlAlchemyPendingFinalizationRepository",
    "SqlAlchemyRunnerAttemptStateRepository",
    "create_pending_finalization_repository",
    "create_runner_attempt_state_repository",
]


def create_pending_finalization_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyPendingFinalizationRepository:
    return SqlAlchemyPendingFinalizationRepository(session_factory)


def create_runner_attempt_state_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyRunnerAttemptStateRepository:
    return SqlAlchemyRunnerAttemptStateRepository(session_factory)


class SqlAlchemyPendingFinalizationRepository:
    """Append-only PostgreSQL pending finalization outbox."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_pending(self, record: PendingFinalizationRecord) -> None:
        if type(record) is not PendingFinalizationRecord:
            raise TypeError("append_pending requires PendingFinalizationRecord")
        fields = {
            "run_id": record.run_id.value,
            "agent_id": record.agent_id,
            "invocation_id": record.invocation_id,
            "tick": record.tick,
        }
        _LOGGER.debug("pending_finalization_append_started", **fields)
        key = (record.run_id.value, record.agent_id, record.invocation_id)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(RunnerPendingFinalizationOrm, key)
                if existing is not None:
                    if (
                        existing.integrity_hash == record.integrity_hash
                        and existing.status == PendingFinalizationStatus.PENDING.value
                    ):
                        _LOGGER.warning("pending_finalization_idempotent", **fields)
                        return
                    raise PersistenceConflictError(
                        "pending_conflict", operation="append_pending"
                    )
                session.add(
                    RunnerPendingFinalizationOrm(
                        run_id=record.run_id.value,
                        agent_id=record.agent_id,
                        tick=record.tick,
                        invocation_id=record.invocation_id,
                        integrity_hash=record.integrity_hash,
                        codec_version=record.codec_version
                        or PENDING_FINALIZATION_CODEC_VERSION,
                        payload_json=dict(record.payload),
                        status=record.status.value,
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_pending"
            ) from exc
        _LOGGER.info("pending_finalization_appended", **fields)

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
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(RunnerPendingFinalizationOrm)
                .where(RunnerPendingFinalizationOrm.run_id == run_id.value)
                .where(RunnerPendingFinalizationOrm.tick == tick)
                .where(
                    RunnerPendingFinalizationOrm.status
                    == PendingFinalizationStatus.PENDING.value
                )
                .order_by(
                    RunnerPendingFinalizationOrm.created_ordinal,
                    RunnerPendingFinalizationOrm.agent_id,
                )
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_pending_from_orm(row) for row in rows)

    async def list_pending_for_run(
        self, *, run_id: RunId
    ) -> tuple[PendingFinalizationRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(RunnerPendingFinalizationOrm)
                .where(RunnerPendingFinalizationOrm.run_id == run_id.value)
                .where(
                    RunnerPendingFinalizationOrm.status
                    == PendingFinalizationStatus.PENDING.value
                )
                .order_by(
                    RunnerPendingFinalizationOrm.tick,
                    RunnerPendingFinalizationOrm.created_ordinal,
                    RunnerPendingFinalizationOrm.agent_id,
                )
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(_pending_from_orm(row) for row in rows)

    async def _mark(
        self,
        *,
        run_id: RunId,
        agent_id: str,
        invocation_id: str,
        status: PendingFinalizationStatus,
    ) -> None:
        # Append-only: status transitions require a new row semantics via
        # UPDATE, but AUTHORITATIVE reject triggers are not on these tables.
        # Alembic 0009 did not add reject triggers; status mark is allowed.
        fields = {
            "run_id": run_id.value,
            "agent_id": agent_id,
            "invocation_id": invocation_id,
            "status": status.value,
        }
        async with session_scope(self._session_factory) as session:
            row = await session.get(
                RunnerPendingFinalizationOrm,
                (run_id.value, agent_id, invocation_id),
            )
            if row is None:
                raise PersistenceConflictError(
                    "pending_missing", operation="mark_pending"
                )
            if row.status == status.value:
                _LOGGER.warning("pending_finalization_mark_idempotent", **fields)
                return
            if row.status != PendingFinalizationStatus.PENDING.value:
                raise PersistenceConflictError(
                    "pending_status_conflict", operation="mark_pending"
                )
            row.status = status.value
            await session.commit()
        _LOGGER.info("pending_finalization_marked", **fields)


class SqlAlchemyRunnerAttemptStateRepository:
    """Append-only PostgreSQL runner attempt recovery records."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append_attempt(self, record: RunnerAttemptStateRecord) -> None:
        if type(record) is not RunnerAttemptStateRecord:
            raise TypeError("append_attempt requires RunnerAttemptStateRecord")
        fields = {
            "run_id": record.run_id.value,
            "attempt_id": record.attempt_id,
            "tick": record.tick,
            "phase": record.phase,
            "recovery_required": record.recovery_required,
        }
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(
                    RunnerAttemptStateOrm, (record.run_id.value, record.attempt_id)
                )
                if existing is not None:
                    if existing.integrity_hash == record.integrity_hash:
                        _LOGGER.warning("runner_attempt_idempotent", **fields)
                        return
                    raise PersistenceConflictError(
                        "attempt_conflict", operation="append_attempt"
                    )
                session.add(
                    RunnerAttemptStateOrm(
                        run_id=record.run_id.value,
                        attempt_id=record.attempt_id,
                        tick=record.tick,
                        phase=record.phase,
                        recovery_required=record.recovery_required,
                        integrity_hash=record.integrity_hash,
                        codec_version=record.codec_version,
                        payload_json=dict(record.payload),
                    )
                )
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            raise PersistenceConflictError(
                "integrity_conflict", operation="append_attempt"
            ) from exc
        _LOGGER.info("runner_attempt_appended", **fields)

    async def list_recovery_required(
        self, *, run_id: RunId
    ) -> tuple[RunnerAttemptStateRecord, ...]:
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(RunnerAttemptStateOrm)
                .where(RunnerAttemptStateOrm.run_id == run_id.value)
                .where(RunnerAttemptStateOrm.recovery_required.is_(True))
                .order_by(
                    RunnerAttemptStateOrm.created_ordinal,
                    RunnerAttemptStateOrm.attempt_id,
                )
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(
                RunnerAttemptStateRecord(
                    run_id=RunId(row.run_id),
                    attempt_id=row.attempt_id,
                    tick=row.tick,
                    phase=row.phase,
                    recovery_required=row.recovery_required,
                    integrity_hash=row.integrity_hash,
                    codec_version=row.codec_version,
                    payload=dict(row.payload_json),
                )
                for row in rows
            )


def _pending_from_orm(row: RunnerPendingFinalizationOrm) -> PendingFinalizationRecord:
    return PendingFinalizationRecord(
        run_id=RunId(row.run_id),
        agent_id=row.agent_id,
        tick=row.tick,
        invocation_id=row.invocation_id,
        integrity_hash=row.integrity_hash,
        codec_version=row.codec_version,
        payload=dict(row.payload_json),
        status=PendingFinalizationStatus(row.status),
    )
