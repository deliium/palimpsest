"""Unit tests for run-control lifecycle contracts."""

from __future__ import annotations

import pytest

from simulation.models import RunId
from simulation.run_control import (
    ALLOWED_LIFECYCLE_TRANSITIONS,
    ConfigAvailability,
    ExecutionLease,
    LifecycleTransitionError,
    ProcessRestartClass,
    RunControlRecord,
    RunLifecycleState,
    RunLifecycleTransition,
    assert_lifecycle_transition,
    classify_process_restart,
    is_lifecycle_transition_allowed,
    is_terminal_lifecycle_state,
)

pytestmark = pytest.mark.unit


def test_lifecycle_graph_covers_required_states() -> None:
    required = {
        "configured",
        "ready",
        "paused",
        "starting",
        "running",
        "stopping",
        "completed",
        "failed",
        "fenced",
        "recovery-required",
        "interrupted",
    }
    assert {state.value for state in RunLifecycleState} == required
    assert set(ALLOWED_LIFECYCLE_TRANSITIONS) == set(RunLifecycleState)


def test_one_tick_ready_paused_roundtrip() -> None:
    assert is_lifecycle_transition_allowed(
        RunLifecycleState.RUNNING, RunLifecycleState.READY
    )
    assert is_lifecycle_transition_allowed(
        RunLifecycleState.RUNNING, RunLifecycleState.PAUSED
    )
    assert is_lifecycle_transition_allowed(
        RunLifecycleState.READY, RunLifecycleState.STARTING
    )
    assert is_lifecycle_transition_allowed(
        RunLifecycleState.PAUSED, RunLifecycleState.READY
    )
    assert_lifecycle_transition(RunLifecycleState.READY, RunLifecycleState.READY)
    with pytest.raises(LifecycleTransitionError):
        assert_lifecycle_transition(
            RunLifecycleState.COMPLETED, RunLifecycleState.READY
        )


def test_terminal_states_are_closed() -> None:
    for state in (
        RunLifecycleState.COMPLETED,
        RunLifecycleState.FAILED,
        RunLifecycleState.FENCED,
    ):
        assert is_terminal_lifecycle_state(state)
        assert ALLOWED_LIFECYCLE_TRANSITIONS[state] == frozenset()


def test_legacy_record_forbids_fabricated_config() -> None:
    with pytest.raises(ValueError, match="legacy_config"):
        RunControlRecord(
            run_id=RunId("run-1"),
            lifecycle_state=RunLifecycleState.CONFIGURED,
            lifecycle_version=0,
            config_availability=ConfigAvailability.UNAVAILABLE,
            ticks_committed=0,
            progress_cursor=0,
            config_schema_version="runner-config-v2",
        )


def test_process_restart_classification() -> None:
    legacy = RunControlRecord(
        run_id=RunId("run-legacy"),
        lifecycle_state=RunLifecycleState.CONFIGURED,
        lifecycle_version=0,
        config_availability=ConfigAvailability.UNAVAILABLE,
        ticks_committed=2,
        progress_cursor=2,
    )
    assert (
        classify_process_restart(legacy, now_unix_ms=100)
        is ProcessRestartClass.CONFIGURATION_UNAVAILABLE
    )

    lease = ExecutionLease(
        lease_id="lease-1",
        owner_id="owner-1",
        claimed_at_unix_ms=0,
        heartbeat_at_unix_ms=0,
        expires_at_unix_ms=50,
    )
    running = RunControlRecord(
        run_id=RunId("run-2"),
        lifecycle_state=RunLifecycleState.RUNNING,
        lifecycle_version=3,
        config_availability=ConfigAvailability.AVAILABLE,
        ticks_committed=1,
        progress_cursor=1,
        config_schema_version="runner-config-v2",
        config_fingerprint="a" * 64,
        config_payload=b"{}",
        lease=lease,
    )
    assert (
        classify_process_restart(running, now_unix_ms=100)
        is ProcessRestartClass.LEASE_EXPIRED
    )
    assert (
        classify_process_restart(running, now_unix_ms=10, pending_count=1)
        is ProcessRestartClass.RECOVERY_REQUIRED
    )


def test_transition_audit_requires_version_increment() -> None:
    with pytest.raises(ValueError, match="resulting_version"):
        RunLifecycleTransition(
            run_id=RunId("run-1"),
            from_state=RunLifecycleState.READY,
            to_state=RunLifecycleState.STARTING,
            expected_version=1,
            resulting_version=1,
            reason_code="start",
            operation_id="op-1",
        )
