"""SQLAlchemy adapter for durable run-control lifecycle and leases.

Implements ``simulation.persistence.RunControlRepository``. Never logs
configuration payloads, seeds, DSNs, or SQL parameters.
"""

from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.database import session_scope
from infrastructure.logging import get_logger
from persistence.errors import (
    PersistenceAdapterError,
    PersistenceConflictError,
    PersistenceNotFoundError,
)
from persistence.orm import RunControlStateOrm, RunLifecycleTransitionOrm
from simulation.models import RunId
from simulation.persistence import RunControlRepository
from simulation.run_control import (
    ConfigAvailability,
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
    RunLifecycleTransition,
    assert_lifecycle_transition,
    is_lifecycle_transition_allowed,
)

_LOGGER = get_logger("persistence.run_control_sqlalchemy")

__all__ = [
    "SqlAlchemyRunControlRepository",
    "create_run_control_repository",
]


def create_run_control_repository(
    session_factory: async_sessionmaker[AsyncSession],
) -> SqlAlchemyRunControlRepository:
    return SqlAlchemyRunControlRepository(session_factory)


class SqlAlchemyRunControlRepository:
    """PostgreSQL run-control head with optimistic lifecycle transitions."""

    __slots__ = ("_session_factory",)

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert_configured(self, record: RunControlRecord) -> RunControlRecord:
        if type(record) is not RunControlRecord:
            raise TypeError("upsert_configured requires RunControlRecord")
        fields = {
            "operation": "upsert_configured",
            "run_id": record.run_id.value,
            "lifecycle_code": record.lifecycle_state.value,
            "lifecycle_version": record.lifecycle_version,
            "config_availability": record.config_availability.value,
        }
        started = time.perf_counter()
        _LOGGER.debug("run_control_upsert_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                existing = await session.get(RunControlStateOrm, record.run_id.value)
                if existing is not None:
                    if (
                        existing.config_availability
                        == ConfigAvailability.UNAVAILABLE.value
                        and record.config_availability
                        is ConfigAvailability.AVAILABLE
                    ):
                        _apply_record(existing, record)
                        await session.commit()
                        _LOGGER.info("run_control_legacy_upgraded", **fields)
                        return record
                    if _record_matches(existing, record):
                        _LOGGER.debug("run_control_upsert_idempotent", **fields)
                        return _to_record(existing)
                    raise PersistenceConflictError(
                        "run_control_conflict", operation="upsert_configured"
                    )
                session.add(_from_record(record))
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "run_control_upsert_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="upsert_configured"
            ) from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        _LOGGER.info("run_control_upserted", **fields, duration_ms=duration_ms)
        return record

    async def get(self, run_id: RunId) -> RunControlRecord | None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        async with session_scope(self._session_factory) as session:
            row = await session.get(RunControlStateOrm, run_id.value)
            if row is None:
                return None
            return _to_record(row)

    async def replace_configuration(
        self,
        record: RunControlRecord,
        *,
        expected_version: int,
    ) -> RunControlRecord:
        if type(record) is not RunControlRecord:
            raise TypeError("replace_configuration requires RunControlRecord")
        fields = {
            "operation": "replace_configuration",
            "run_id": record.run_id.value,
            "expected_version": expected_version,
        }
        _LOGGER.debug("run_control_replace_started", **fields)
        async with session_scope(self._session_factory) as session:
            row = await session.get(RunControlStateOrm, record.run_id.value)
            if row is None:
                raise PersistenceNotFoundError(
                    "run_control_missing", operation="replace_configuration"
                )
            if row.lifecycle_version != expected_version:
                raise PersistenceConflictError(
                    "version_conflict", operation="replace_configuration"
                )
            current = RunLifecycleState(row.lifecycle_state)
            if current not in {
                RunLifecycleState.CONFIGURED,
                RunLifecycleState.READY,
                RunLifecycleState.PAUSED,
            }:
                raise PersistenceConflictError(
                    "illegal_lifecycle_transition",
                    operation="replace_configuration",
                )
            row.lifecycle_state = RunLifecycleState.CONFIGURED.value
            row.lifecycle_version = expected_version + 1
            row.config_availability = record.config_availability.value
            row.config_schema_version = record.config_schema_version
            row.config_fingerprint = record.config_fingerprint
            row.config_payload = record.config_payload
            result = _to_record(row)
            await session.commit()
        _LOGGER.info("run_control_replaced", **fields, lifecycle_version=result.lifecycle_version)
        return result

    async def transition(
        self,
        *,
        run_id: RunId,
        expected_version: int,
        to_state: RunLifecycleState,
        reason_code: str,
        operation_id: str,
        ticks_committed: int | None = None,
        progress_cursor: int | None = None,
        terminal_reason_code: str | None = None,
    ) -> RunControlRecord:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(to_state) is not RunLifecycleState:
            raise TypeError("to_state must be RunLifecycleState")
        fields = {
            "operation": "transition",
            "run_id": run_id.value,
            "operation_id": operation_id,
            "lifecycle_code": to_state.value,
            "expected_version": expected_version,
        }
        started = time.perf_counter()
        _LOGGER.debug("run_control_transition_started", **fields)
        try:
            async with session_scope(self._session_factory) as session:
                row = await session.get(RunControlStateOrm, run_id.value)
                if row is None:
                    raise PersistenceNotFoundError(
                        "run_control_missing", operation="transition"
                    )
                current = RunLifecycleState(row.lifecycle_state)
                if row.lifecycle_version != expected_version:
                    _LOGGER.warning(
                        "run_control_transition_contention",
                        **fields,
                        actual_version=row.lifecycle_version,
                    )
                    raise PersistenceConflictError(
                        "version_conflict", operation="transition"
                    )
                if not is_lifecycle_transition_allowed(current, to_state):
                    _LOGGER.error(
                        "run_control_illegal_transition",
                        **fields,
                        from_state=current.value,
                        reason_code="illegal_lifecycle_transition",
                    )
                    raise PersistenceConflictError(
                        "illegal_lifecycle_transition", operation="transition"
                    )
                if current == to_state:
                    _LOGGER.debug("run_control_transition_noop", **fields)
                    return _to_record(row)
                resulting = expected_version + 1
                transition = RunLifecycleTransition(
                    run_id=run_id,
                    from_state=current,
                    to_state=to_state,
                    expected_version=expected_version,
                    resulting_version=resulting,
                    reason_code=reason_code,
                    operation_id=operation_id,
                )
                row.lifecycle_state = to_state.value
                row.lifecycle_version = resulting
                if ticks_committed is not None:
                    row.ticks_committed = ticks_committed
                if progress_cursor is not None:
                    row.progress_cursor = progress_cursor
                if terminal_reason_code is not None:
                    row.terminal_reason_code = terminal_reason_code
                session.add(
                    RunLifecycleTransitionOrm(
                        run_id=run_id.value,
                        from_state=transition.from_state.value,
                        to_state=transition.to_state.value,
                        expected_version=transition.expected_version,
                        resulting_version=transition.resulting_version,
                        reason_code=transition.reason_code,
                        operation_id=transition.operation_id,
                    )
                )
                result = _to_record(row)
                await session.commit()
        except PersistenceAdapterError:
            raise
        except IntegrityError as exc:
            _LOGGER.error(
                "run_control_transition_conflict",
                **fields,
                reason_code="integrity_conflict",
            )
            raise PersistenceConflictError(
                "integrity_conflict", operation="transition"
            ) from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        _LOGGER.info(
            "run_control_transitioned",
            **fields,
            resulting_version=result.lifecycle_version,
            duration_ms=duration_ms,
        )
        return result

    async def claim_lease(
        self,
        *,
        run_id: RunId,
        expected_version: int,
        lease: ExecutionLease,
        operation_id: str,
    ) -> RunControlRecord:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        if type(lease) is not ExecutionLease:
            raise TypeError("lease must be ExecutionLease")
        fields = {
            "operation": "claim_lease",
            "run_id": run_id.value,
            "lease_id": lease.lease_id,
            "operation_id": operation_id,
            "expected_version": expected_version,
        }
        _LOGGER.debug("run_control_claim_started", **fields)
        async with session_scope(self._session_factory) as session:
            row = await session.get(RunControlStateOrm, run_id.value)
            if row is None:
                raise PersistenceNotFoundError(
                    "run_control_missing", operation="claim_lease"
                )
            if row.lifecycle_version != expected_version:
                _LOGGER.warning(
                    "run_control_claim_contention",
                    **fields,
                    actual_version=row.lifecycle_version,
                )
                raise PersistenceConflictError(
                    "version_conflict", operation="claim_lease"
                )
            now = lease.claimed_at_unix_ms
            if row.lease_id is not None and row.lease_expires_at_unix_ms is not None:
                if (
                    row.lease_id != lease.lease_id
                    and now < row.lease_expires_at_unix_ms
                ):
                    _LOGGER.warning(
                        "run_control_lease_held",
                        **fields,
                        held_lease_id=row.lease_id,
                    )
                    raise PersistenceConflictError(
                        "lease_held", operation="claim_lease"
                    )
                if (
                    row.lease_id != lease.lease_id
                    and now >= row.lease_expires_at_unix_ms
                ):
                    _LOGGER.warning(
                        "run_control_lease_expired_taken",
                        **fields,
                        held_lease_id=row.lease_id,
                    )
            row.lease_id = lease.lease_id
            row.lease_owner_id = lease.owner_id
            row.lease_claimed_at_unix_ms = lease.claimed_at_unix_ms
            row.lease_heartbeat_at_unix_ms = lease.heartbeat_at_unix_ms
            row.lease_expires_at_unix_ms = lease.expires_at_unix_ms
            row.lifecycle_version = expected_version + 1
            session.add(
                RunLifecycleTransitionOrm(
                    run_id=run_id.value,
                    from_state=row.lifecycle_state,
                    to_state=row.lifecycle_state,
                    expected_version=expected_version,
                    resulting_version=row.lifecycle_version,
                    reason_code="lease_claimed",
                    operation_id=operation_id,
                )
            )
            # Same-state transition is allowed by graph; assert for audit shape.
            assert_lifecycle_transition(
                RunLifecycleState(row.lifecycle_state),
                RunLifecycleState(row.lifecycle_state),
            )
            result = _to_record(row)
            await session.commit()
        _LOGGER.info("run_control_lease_claimed", **fields)
        return result

    async def heartbeat_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        heartbeat_at_unix_ms: int,
        expires_at_unix_ms: int,
        operation_id: str,
    ) -> RunControlRecord:
        fields = {
            "operation": "heartbeat_lease",
            "run_id": run_id.value,
            "lease_id": lease_id,
            "operation_id": operation_id,
        }
        _LOGGER.debug("run_control_heartbeat_started", **fields)
        async with session_scope(self._session_factory) as session:
            row = await session.get(RunControlStateOrm, run_id.value)
            if row is None:
                raise PersistenceNotFoundError(
                    "run_control_missing", operation="heartbeat_lease"
                )
            if row.lease_id != lease_id:
                _LOGGER.warning("run_control_heartbeat_mismatch", **fields)
                raise PersistenceConflictError(
                    "lease_mismatch", operation="heartbeat_lease"
                )
            if (
                row.lease_expires_at_unix_ms is not None
                and heartbeat_at_unix_ms >= row.lease_expires_at_unix_ms
            ):
                _LOGGER.warning("run_control_lease_expired", **fields)
                raise PersistenceConflictError(
                    "lease_expired", operation="heartbeat_lease"
                )
            row.lease_heartbeat_at_unix_ms = heartbeat_at_unix_ms
            row.lease_expires_at_unix_ms = expires_at_unix_ms
            result = _to_record(row)
            await session.commit()
        _LOGGER.debug("run_control_heartbeat_applied", **fields)
        return result

    async def release_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        operation_id: str,
    ) -> RunControlRecord:
        fields = {
            "operation": "release_lease",
            "run_id": run_id.value,
            "lease_id": lease_id,
            "operation_id": operation_id,
        }
        _LOGGER.debug("run_control_release_started", **fields)
        async with session_scope(self._session_factory) as session:
            row = await session.get(RunControlStateOrm, run_id.value)
            if row is None:
                raise PersistenceNotFoundError(
                    "run_control_missing", operation="release_lease"
                )
            if row.lease_id is not None and row.lease_id != lease_id:
                _LOGGER.warning("run_control_release_mismatch", **fields)
                raise PersistenceConflictError(
                    "lease_mismatch", operation="release_lease"
                )
            row.lease_id = None
            row.lease_owner_id = None
            row.lease_claimed_at_unix_ms = None
            row.lease_heartbeat_at_unix_ms = None
            row.lease_expires_at_unix_ms = None
            result = _to_record(row)
            await session.commit()
        _LOGGER.info("run_control_lease_released", **fields)
        return result

    async def list_transitions(
        self, *, run_id: RunId
    ) -> tuple[RunLifecycleTransition, ...]:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        async with session_scope(self._session_factory) as session:
            stmt = (
                select(RunLifecycleTransitionOrm)
                .where(RunLifecycleTransitionOrm.run_id == run_id.value)
                .order_by(RunLifecycleTransitionOrm.resulting_version)
            )
            rows = (await session.execute(stmt)).scalars().all()
            return tuple(
                RunLifecycleTransition(
                    run_id=run_id,
                    from_state=RunLifecycleState(row.from_state),
                    to_state=RunLifecycleState(row.to_state),
                    expected_version=row.expected_version,
                    resulting_version=row.resulting_version,
                    reason_code=row.reason_code,
                    operation_id=row.operation_id,
                )
                for row in rows
            )

    async def list_runs(
        self,
        *,
        after_run_id: str | None = None,
        limit: int = 100,
    ) -> tuple[RunControlRecord, ...]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if limit > 1000:
            raise ValueError("limit exceeds maximum")
        async with session_scope(self._session_factory) as session:
            stmt = select(RunControlStateOrm).order_by(RunControlStateOrm.run_id)
            if after_run_id is not None:
                stmt = stmt.where(RunControlStateOrm.run_id > after_run_id)
            stmt = stmt.limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            records = tuple(_to_record(row) for row in rows)
        _LOGGER.debug(
            "run_control_list_runs",
            operation="list_runs",
            count=len(records),
            limit=limit,
            has_cursor=after_run_id is not None,
        )
        return records


def _from_record(record: RunControlRecord) -> RunControlStateOrm:
    lease = record.lease
    return RunControlStateOrm(
        run_id=record.run_id.value,
        lifecycle_state=record.lifecycle_state.value,
        lifecycle_version=record.lifecycle_version,
        config_availability=record.config_availability.value,
        config_schema_version=record.config_schema_version,
        config_fingerprint=record.config_fingerprint,
        config_payload=record.config_payload,
        ticks_committed=record.ticks_committed,
        progress_cursor=record.progress_cursor,
        lease_id=None if lease is None else lease.lease_id,
        lease_owner_id=None if lease is None else lease.owner_id,
        lease_claimed_at_unix_ms=None if lease is None else lease.claimed_at_unix_ms,
        lease_heartbeat_at_unix_ms=(
            None if lease is None else lease.heartbeat_at_unix_ms
        ),
        lease_expires_at_unix_ms=None if lease is None else lease.expires_at_unix_ms,
        terminal_reason_code=record.terminal_reason_code,
    )


def _apply_record(row: RunControlStateOrm, record: RunControlRecord) -> None:
    row.lifecycle_state = record.lifecycle_state.value
    row.lifecycle_version = record.lifecycle_version
    row.config_availability = record.config_availability.value
    row.config_schema_version = record.config_schema_version
    row.config_fingerprint = record.config_fingerprint
    row.config_payload = record.config_payload
    row.ticks_committed = record.ticks_committed
    row.progress_cursor = record.progress_cursor
    row.terminal_reason_code = record.terminal_reason_code


def _to_record(row: RunControlStateOrm) -> RunControlRecord:
    lease: ExecutionLease | None = None
    if (
        row.lease_id is not None
        and row.lease_owner_id is not None
        and row.lease_claimed_at_unix_ms is not None
        and row.lease_heartbeat_at_unix_ms is not None
        and row.lease_expires_at_unix_ms is not None
    ):
        lease = ExecutionLease(
            lease_id=row.lease_id,
            owner_id=row.lease_owner_id,
            claimed_at_unix_ms=int(row.lease_claimed_at_unix_ms),
            heartbeat_at_unix_ms=int(row.lease_heartbeat_at_unix_ms),
            expires_at_unix_ms=int(row.lease_expires_at_unix_ms),
        )
    payload = row.config_payload
    if payload is not None and not isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload)
    return RunControlRecord(
        run_id=RunId(row.run_id),
        lifecycle_state=RunLifecycleState(row.lifecycle_state),
        lifecycle_version=row.lifecycle_version,
        config_availability=ConfigAvailability(row.config_availability),
        ticks_committed=row.ticks_committed,
        progress_cursor=row.progress_cursor,
        config_schema_version=row.config_schema_version,
        config_fingerprint=row.config_fingerprint,
        config_payload=None if payload is None else bytes(payload),
        lease=lease,
        terminal_reason_code=row.terminal_reason_code,
    )


def _record_matches(row: RunControlStateOrm, record: RunControlRecord) -> bool:
    payload = row.config_payload
    if payload is not None and not isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload)
    return (
        row.lifecycle_state == record.lifecycle_state.value
        and row.lifecycle_version == record.lifecycle_version
        and row.config_availability == record.config_availability.value
        and row.config_schema_version == record.config_schema_version
        and row.config_fingerprint == record.config_fingerprint
        and (
            (payload is None and record.config_payload is None)
            or (
                payload is not None
                and record.config_payload is not None
                and bytes(payload) == record.config_payload
            )
        )
        and row.ticks_committed == record.ticks_committed
        and row.progress_cursor == record.progress_cursor
    )


# Protocol satisfaction for type checkers.
_: type[RunControlRepository] = SqlAlchemyRunControlRepository
