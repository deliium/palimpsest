"""Unit tests for in-memory run-control repository behavior."""

from __future__ import annotations

import pytest

from simulation.memory_run_control import InMemoryRunControlRepository
from simulation.models import RunId
from simulation.run_control import (
    ConfigAvailability,
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
)

pytestmark = pytest.mark.unit

_HASH = "a" * 64


def _configured(*, run_id: str = "run-1") -> RunControlRecord:
    return RunControlRecord(
        run_id=RunId(run_id),
        lifecycle_state=RunLifecycleState.CONFIGURED,
        lifecycle_version=0,
        config_availability=ConfigAvailability.AVAILABLE,
        ticks_committed=0,
        progress_cursor=0,
        config_schema_version="runner-config-v2",
        config_fingerprint=_HASH,
        config_payload=b'{"schema_version":"runner-config-v2"}',
    )


@pytest.mark.asyncio
async def test_optimistic_transition_and_one_tick_pause() -> None:
    repo = InMemoryRunControlRepository()
    record = await repo.upsert_configured(_configured())
    ready = await repo.transition(
        run_id=record.run_id,
        expected_version=0,
        to_state=RunLifecycleState.READY,
        reason_code="arm",
        operation_id="op-ready",
    )
    starting = await repo.transition(
        run_id=ready.run_id,
        expected_version=1,
        to_state=RunLifecycleState.STARTING,
        reason_code="start",
        operation_id="op-start",
    )
    running = await repo.transition(
        run_id=starting.run_id,
        expected_version=2,
        to_state=RunLifecycleState.RUNNING,
        reason_code="claimed",
        operation_id="op-run",
    )
    paused = await repo.transition(
        run_id=running.run_id,
        expected_version=3,
        to_state=RunLifecycleState.PAUSED,
        reason_code="one_tick",
        operation_id="op-pause",
        ticks_committed=1,
        progress_cursor=1,
    )
    assert paused.lifecycle_state is RunLifecycleState.PAUSED
    assert paused.ticks_committed == 1
    with pytest.raises(ValueError, match="version_conflict"):
        await repo.transition(
            run_id=paused.run_id,
            expected_version=3,
            to_state=RunLifecycleState.READY,
            reason_code="stale",
            operation_id="op-stale",
        )
    transitions = await repo.list_transitions(run_id=paused.run_id)
    assert [item.to_state for item in transitions] == [
        RunLifecycleState.READY,
        RunLifecycleState.STARTING,
        RunLifecycleState.RUNNING,
        RunLifecycleState.PAUSED,
    ]


@pytest.mark.asyncio
async def test_lease_claim_heartbeat_expiry_and_release() -> None:
    repo = InMemoryRunControlRepository()
    record = await repo.upsert_configured(_configured())
    lease = ExecutionLease(
        lease_id="lease-1",
        owner_id="owner-a",
        claimed_at_unix_ms=1000,
        heartbeat_at_unix_ms=1000,
        expires_at_unix_ms=2000,
    )
    claimed = await repo.claim_lease(
        run_id=record.run_id,
        expected_version=0,
        lease=lease,
        operation_id="op-claim",
    )
    assert claimed.lease is not None
    assert claimed.lifecycle_version == 1
    heartbeated = await repo.heartbeat_lease(
        run_id=record.run_id,
        lease_id="lease-1",
        heartbeat_at_unix_ms=1500,
        expires_at_unix_ms=2500,
        operation_id="op-hb",
    )
    assert heartbeated.lease is not None
    assert heartbeated.lease.expires_at_unix_ms == 2500
    with pytest.raises(ValueError, match="lease_held"):
        await repo.claim_lease(
            run_id=record.run_id,
            expected_version=1,
            lease=ExecutionLease(
                lease_id="lease-2",
                owner_id="owner-b",
                claimed_at_unix_ms=1600,
                heartbeat_at_unix_ms=1600,
                expires_at_unix_ms=3000,
            ),
            operation_id="op-steal",
        )
    stolen = await repo.claim_lease(
        run_id=record.run_id,
        expected_version=1,
        lease=ExecutionLease(
            lease_id="lease-2",
            owner_id="owner-b",
            claimed_at_unix_ms=2600,
            heartbeat_at_unix_ms=2600,
            expires_at_unix_ms=4000,
        ),
        operation_id="op-expire-take",
    )
    assert stolen.lease is not None
    assert stolen.lease.lease_id == "lease-2"
    released = await repo.release_lease(
        run_id=record.run_id,
        lease_id="lease-2",
        operation_id="op-release",
    )
    assert released.lease is None


@pytest.mark.asyncio
async def test_legacy_unavailable_upgrade_is_idempotent_path() -> None:
    repo = InMemoryRunControlRepository()
    legacy = RunControlRecord(
        run_id=RunId("run-legacy"),
        lifecycle_state=RunLifecycleState.CONFIGURED,
        lifecycle_version=0,
        config_availability=ConfigAvailability.UNAVAILABLE,
        ticks_committed=0,
        progress_cursor=0,
    )
    await repo.upsert_configured(legacy)
    upgraded = await repo.upsert_configured(_configured(run_id="run-legacy"))
    assert upgraded.config_availability is ConfigAvailability.AVAILABLE
    again = await repo.upsert_configured(upgraded)
    assert again == upgraded
