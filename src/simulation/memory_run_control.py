"""In-memory run-control repository for unit tests."""

from __future__ import annotations

from simulation.models import RunId
from simulation.run_control import (
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
    RunLifecycleTransition,
    assert_lifecycle_transition,
    is_lifecycle_transition_allowed,
)


class InMemoryRunControlRepository:
    """Copy-on-write run-control head with optimistic versioning."""

    __slots__ = ("_records", "_transitions")

    def __init__(self) -> None:
        self._records: dict[str, RunControlRecord] = {}
        self._transitions: dict[str, list[RunLifecycleTransition]] = {}

    async def upsert_configured(self, record: RunControlRecord) -> RunControlRecord:
        if type(record) is not RunControlRecord:
            raise TypeError("upsert_configured requires RunControlRecord")
        existing = self._records.get(record.run_id.value)
        if existing is None:
            self._records[record.run_id.value] = record
            return record
        if existing == record:
            return existing
        if (
            existing.config_availability.value == "unavailable"
            and record.config_availability.value == "available"
        ):
            self._records[record.run_id.value] = record
            return record
        raise ValueError("run_control_conflict")

    async def get(self, run_id: RunId) -> RunControlRecord | None:
        if type(run_id) is not RunId:
            raise TypeError("run_id must be RunId")
        return self._records.get(run_id.value)

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
        record = self._records.get(run_id.value)
        if record is None:
            raise KeyError("run_control_missing")
        if record.lifecycle_version != expected_version:
            raise ValueError("version_conflict")
        if not is_lifecycle_transition_allowed(record.lifecycle_state, to_state):
            raise ValueError("illegal_lifecycle_transition")
        if record.lifecycle_state == to_state:
            return record
        resulting = expected_version + 1
        transition = RunLifecycleTransition(
            run_id=run_id,
            from_state=record.lifecycle_state,
            to_state=to_state,
            expected_version=expected_version,
            resulting_version=resulting,
            reason_code=reason_code,
            operation_id=operation_id,
        )
        updated = RunControlRecord(
            run_id=record.run_id,
            lifecycle_state=to_state,
            lifecycle_version=resulting,
            config_availability=record.config_availability,
            ticks_committed=(
                record.ticks_committed if ticks_committed is None else ticks_committed
            ),
            progress_cursor=(
                record.progress_cursor if progress_cursor is None else progress_cursor
            ),
            config_schema_version=record.config_schema_version,
            config_fingerprint=record.config_fingerprint,
            config_payload=record.config_payload,
            lease=record.lease,
            terminal_reason_code=(
                record.terminal_reason_code
                if terminal_reason_code is None
                else terminal_reason_code
            ),
        )
        self._records[run_id.value] = updated
        self._transitions.setdefault(run_id.value, []).append(transition)
        return updated

    async def claim_lease(
        self,
        *,
        run_id: RunId,
        expected_version: int,
        lease: ExecutionLease,
        operation_id: str,
    ) -> RunControlRecord:
        record = self._records.get(run_id.value)
        if record is None:
            raise KeyError("run_control_missing")
        if record.lifecycle_version != expected_version:
            raise ValueError("version_conflict")
        if record.lease is not None and record.lease.lease_id != lease.lease_id:
            if not record.lease.is_expired(now_unix_ms=lease.claimed_at_unix_ms):
                raise ValueError("lease_held")
        assert_lifecycle_transition(record.lifecycle_state, record.lifecycle_state)
        updated = RunControlRecord(
            run_id=record.run_id,
            lifecycle_state=record.lifecycle_state,
            lifecycle_version=expected_version + 1,
            config_availability=record.config_availability,
            ticks_committed=record.ticks_committed,
            progress_cursor=record.progress_cursor,
            config_schema_version=record.config_schema_version,
            config_fingerprint=record.config_fingerprint,
            config_payload=record.config_payload,
            lease=lease,
            terminal_reason_code=record.terminal_reason_code,
        )
        self._records[run_id.value] = updated
        self._transitions.setdefault(run_id.value, []).append(
            RunLifecycleTransition(
                run_id=run_id,
                from_state=record.lifecycle_state,
                to_state=record.lifecycle_state,
                expected_version=expected_version,
                resulting_version=expected_version + 1,
                reason_code="lease_claimed",
                operation_id=operation_id,
            )
        )
        return updated

    async def heartbeat_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        heartbeat_at_unix_ms: int,
        expires_at_unix_ms: int,
        operation_id: str,
    ) -> RunControlRecord:
        del operation_id
        record = self._records.get(run_id.value)
        if record is None:
            raise KeyError("run_control_missing")
        if record.lease is None or record.lease.lease_id != lease_id:
            raise ValueError("lease_mismatch")
        if record.lease.is_expired(now_unix_ms=heartbeat_at_unix_ms):
            raise ValueError("lease_expired")
        lease = ExecutionLease(
            lease_id=record.lease.lease_id,
            owner_id=record.lease.owner_id,
            claimed_at_unix_ms=record.lease.claimed_at_unix_ms,
            heartbeat_at_unix_ms=heartbeat_at_unix_ms,
            expires_at_unix_ms=expires_at_unix_ms,
        )
        updated = RunControlRecord(
            run_id=record.run_id,
            lifecycle_state=record.lifecycle_state,
            lifecycle_version=record.lifecycle_version,
            config_availability=record.config_availability,
            ticks_committed=record.ticks_committed,
            progress_cursor=record.progress_cursor,
            config_schema_version=record.config_schema_version,
            config_fingerprint=record.config_fingerprint,
            config_payload=record.config_payload,
            lease=lease,
            terminal_reason_code=record.terminal_reason_code,
        )
        self._records[run_id.value] = updated
        return updated

    async def release_lease(
        self,
        *,
        run_id: RunId,
        lease_id: str,
        operation_id: str,
    ) -> RunControlRecord:
        del operation_id
        record = self._records.get(run_id.value)
        if record is None:
            raise KeyError("run_control_missing")
        if record.lease is not None and record.lease.lease_id != lease_id:
            raise ValueError("lease_mismatch")
        updated = RunControlRecord(
            run_id=record.run_id,
            lifecycle_state=record.lifecycle_state,
            lifecycle_version=record.lifecycle_version,
            config_availability=record.config_availability,
            ticks_committed=record.ticks_committed,
            progress_cursor=record.progress_cursor,
            config_schema_version=record.config_schema_version,
            config_fingerprint=record.config_fingerprint,
            config_payload=record.config_payload,
            lease=None,
            terminal_reason_code=record.terminal_reason_code,
        )
        self._records[run_id.value] = updated
        return updated

    async def list_transitions(
        self, *, run_id: RunId
    ) -> tuple[RunLifecycleTransition, ...]:
        return tuple(self._transitions.get(run_id.value, ()))
