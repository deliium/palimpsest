"""Process-local recoverable simulation manager for the research API.

Owns per-run locks, leases/heartbeats, one-tick ready transitions, background
run-to-stop tasks, stop-at-finalized-boundary, rehydration hooks, metric-set
lifecycle signals, and graceful draining. Durable truth lives in run-control
and stream repositories — process-local runners are caches only.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from api.errors import (
    ApiError,
    bad_request,
    conflict,
    not_found,
    service_unavailable,
)
from api.schemas import (
    ConfigAvailabilityOut,
    LifecycleStateOut,
    RunControlStatusOut,
    RunListOut,
    TickResultOut,
)
from api.security import generate_operation_id
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.models import RunId
from simulation.persistence import RunControlRepository
from simulation.run_control import (
    ConfigAvailability,
    ExecutionLease,
    RunControlRecord,
    RunLifecycleState,
    is_terminal_lifecycle_state,
)
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS

_LOGGER = get_logger("api.simulation_manager")

TickExecutor = Callable[[str], Awaitable["TickExecutionResult"]]
RunnerFactory = Callable[[RunControlRecord], Awaitable[object]]
MetricLifecycleHook = Callable[[str, str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class TickExecutionResult:
    """Public tick outcome for the manager (no evidence payloads)."""

    ticks_committed: int
    stop_reason: str | None = None
    completed: bool = False


class MetricSetPortal(Protocol):
    """Narrow metric-set lifecycle port (duck-typed; no experiments import)."""

    async def transition_metric_set(
        self,
        *,
        run_id: str,
        metric_set_id: str,
        expected_version: int,
        to_state: object,
    ) -> object: ...


@dataclass
class _RunHandle:
    lock: asyncio.Lock
    stop_requested: bool = False
    task: asyncio.Task[None] | None = None
    lease_id: str | None = None
    runner: object | None = None


class SimulationManager:
    """API-owned run orchestration cache over durable run-control state."""

    def __init__(
        self,
        *,
        settings: Settings,
        run_control: RunControlRepository,
        tick_executor: TickExecutor | None = None,
        runner_factory: RunnerFactory | None = None,
        metric_hook: MetricLifecycleHook | None = None,
        owner_id: str = "api-process",
        clock_ms: Callable[[], int] | None = None,
    ) -> None:
        self._settings = settings
        self._run_control = run_control
        self._tick_executor = tick_executor
        self._runner_factory = runner_factory
        self._metric_hook = metric_hook
        self._owner_id = owner_id
        self._clock_ms = clock_ms or (lambda: int(time.time() * 1000))
        self._handles: dict[str, _RunHandle] = {}
        self._handles_lock = asyncio.Lock()
        self._draining = False
        self._idempotency: dict[str, RunControlStatusOut] = {}

    def owner_runtime_checkpoint(self, run_id: str, owner_id: str) -> object | None:
        """Return one in-process runtime checkpoint, or None when the cache is empty."""
        handle = self._handles.get(run_id)
        runner = None if handle is None else handle.runner
        if runner is None or not hasattr(runner, "export_runtime_checkpoint"):
            return None
        checkpoint = runner.export_runtime_checkpoint()
        states = getattr(checkpoint, "runtime_states", ())
        for state in states:
            agent = getattr(state, "agent_id", None)
            value = getattr(agent, "value", None)
            if value == owner_id:
                return state
        return None

    @property
    def draining(self) -> bool:
        return self._draining

    def _require_active(self) -> None:
        if self._draining:
            raise service_unavailable(code="draining")

    def _warn_unsupported_config_schema(
        self, *, schema_version: str, run_id: str
    ) -> None:
        if schema_version not in SUPPORTED_RUNNER_SCHEMA_VERSIONS:
            _LOGGER.warning(
                "unsupported_config_schema_version",
                run_id=run_id,
                config_schema_version=schema_version,
                reason_code="unsupported_version",
            )

    async def _handle_for(self, run_id: str) -> _RunHandle:
        async with self._handles_lock:
            handle = self._handles.get(run_id)
            if handle is None:
                handle = _RunHandle(lock=asyncio.Lock())
                self._handles[run_id] = handle
            return handle

    def _status_from_record(self, record: RunControlRecord) -> RunControlStatusOut:
        return RunControlStatusOut(
            run_id=record.run_id.value,
            lifecycle_state=LifecycleStateOut(record.lifecycle_state.value),
            lifecycle_version=record.lifecycle_version,
            config_availability=ConfigAvailabilityOut(
                record.config_availability.value
            ),
            ticks_committed=record.ticks_committed,
            progress_cursor=record.progress_cursor,
            config_schema_version=record.config_schema_version,
            config_fingerprint=record.config_fingerprint,
            has_lease=record.lease is not None,
            terminal_reason_code=record.terminal_reason_code,
        )

    async def create(
        self,
        *,
        run_id: str,
        config_schema_version: str,
        config_fingerprint: str,
        config_payload: bytes,
        idempotency_key: str | None = None,
    ) -> RunControlStatusOut:
        self._require_active()
        if idempotency_key is not None:
            cached = self._idempotency.get(f"create:{idempotency_key}")
            if cached is not None and cached.run_id == run_id:
                return cached
        if len(config_payload) == 0 or len(config_payload) > 1_048_576:
            raise bad_request(code="invalid_config_payload", run_id=run_id)
        digest = hashlib.sha256(config_payload).hexdigest()
        if digest != config_fingerprint:
            raise bad_request(code="config_fingerprint_mismatch", run_id=run_id)
        self._warn_unsupported_config_schema(
            schema_version=config_schema_version, run_id=run_id
        )
        handle = await self._handle_for(run_id)
        async with handle.lock:
            existing = await self._run_control.get(RunId(run_id))
            if existing is not None:
                status = self._status_from_record(existing)
                if (
                    existing.config_fingerprint == config_fingerprint
                    and existing.config_payload == config_payload
                ):
                    if idempotency_key is not None:
                        self._idempotency[f"create:{idempotency_key}"] = status
                    return status
                raise conflict(code="run_already_exists", run_id=run_id)
            record = RunControlRecord(
                run_id=RunId(run_id),
                lifecycle_state=RunLifecycleState.CONFIGURED,
                lifecycle_version=0,
                config_availability=ConfigAvailability.AVAILABLE,
                ticks_committed=0,
                progress_cursor=0,
                config_schema_version=config_schema_version,
                config_fingerprint=config_fingerprint,
                config_payload=config_payload,
            )
            if self._runner_factory is not None and handle.runner is None:
                try:
                    handle.runner = await self._runner_factory(record)
                except Exception as exc:
                    code = getattr(exc, "code", None)
                    reason = getattr(code, "value", None) or type(exc).__name__
                    stage = getattr(exc, "stage", None)
                    _LOGGER.error(
                        "simulation_runner_failed",
                        run_id=run_id,
                        reason_code=reason,
                        stage=stage if isinstance(stage, str) else "-",
                    )
                    raise
            stored = await self._run_control.upsert_configured(record)
            status = self._status_from_record(stored)
            if idempotency_key is not None:
                self._idempotency[f"create:{idempotency_key}"] = status
            _LOGGER.info(
                "simulation_created",
                run_id=run_id,
                lifecycle_code=stored.lifecycle_state.value,
            )
            return status

    async def configure(
        self,
        *,
        run_id: str,
        expected_version: int,
        config_schema_version: str,
        config_fingerprint: str,
        config_payload: bytes,
    ) -> RunControlStatusOut:
        self._require_active()
        if len(config_payload) == 0 or len(config_payload) > 1_048_576:
            raise bad_request(code="invalid_config_payload", run_id=run_id)
        if hashlib.sha256(config_payload).hexdigest() != config_fingerprint:
            raise bad_request(code="config_fingerprint_mismatch", run_id=run_id)
        self._warn_unsupported_config_schema(
            schema_version=config_schema_version, run_id=run_id
        )
        handle = await self._handle_for(run_id)
        async with handle.lock:
            current = await self._require_record(run_id)
            if current.lifecycle_version != expected_version:
                raise conflict(code="version_conflict", run_id=run_id)
            if current.lifecycle_state not in {
                RunLifecycleState.CONFIGURED,
                RunLifecycleState.READY,
                RunLifecycleState.PAUSED,
            }:
                raise conflict(code="lifecycle_conflict", run_id=run_id)
            record = RunControlRecord(
                run_id=current.run_id,
                lifecycle_state=RunLifecycleState.CONFIGURED,
                lifecycle_version=current.lifecycle_version,
                config_availability=ConfigAvailability.AVAILABLE,
                ticks_committed=current.ticks_committed,
                progress_cursor=current.progress_cursor,
                config_schema_version=config_schema_version,
                config_fingerprint=config_fingerprint,
                config_payload=config_payload,
                lease=current.lease,
                terminal_reason_code=current.terminal_reason_code,
            )
            stored = await self._run_control.replace_configuration(
                record, expected_version=expected_version
            )
            _LOGGER.info(
                "simulation_configured",
                run_id=run_id,
                lifecycle_code=stored.lifecycle_state.value,
                lifecycle_version=stored.lifecycle_version,
            )
            return self._status_from_record(stored)

    async def start(self, *, run_id: str) -> RunControlStatusOut:
        self._require_active()
        handle = await self._handle_for(run_id)
        async with handle.lock:
            current = await self._require_record(run_id)
            if current.config_availability is ConfigAvailability.UNAVAILABLE:
                raise conflict(code="configuration_unavailable", run_id=run_id)
            if current.lifecycle_state is RunLifecycleState.READY:
                return self._status_from_record(current)
            if current.lifecycle_state not in {
                RunLifecycleState.CONFIGURED,
                RunLifecycleState.PAUSED,
            }:
                raise conflict(code="lifecycle_conflict", run_id=run_id)
            ready = await self._run_control.transition(
                run_id=current.run_id,
                expected_version=current.lifecycle_version,
                to_state=RunLifecycleState.READY,
                reason_code="api_start",
                operation_id=generate_operation_id(),
            )
            await self._maybe_rehydrate(handle, ready)
            _LOGGER.info(
                "simulation_ready",
                run_id=run_id,
                lifecycle_code=ready.lifecycle_state.value,
            )
            return self._status_from_record(ready)

    async def tick(self, *, run_id: str) -> TickResultOut:
        self._require_active()
        handle = await self._handle_for(run_id)
        async with handle.lock:
            if handle.task is not None and not handle.task.done():
                raise conflict(code="run_task_active", run_id=run_id)
            current = await self._require_record(run_id)
            if current.lifecycle_state not in {
                RunLifecycleState.READY,
                RunLifecycleState.PAUSED,
            }:
                raise conflict(code="lifecycle_conflict", run_id=run_id)
            started = time.perf_counter()
            record = await self._claim_and_enter_running(current, handle)
            try:
                result = await self._execute_one_tick(run_id)
                if result.completed:
                    final = await self._run_control.transition(
                        run_id=record.run_id,
                        expected_version=record.lifecycle_version,
                        to_state=RunLifecycleState.COMPLETED,
                        reason_code=result.stop_reason or "completed",
                        operation_id=generate_operation_id(),
                        ticks_committed=result.ticks_committed,
                        progress_cursor=result.ticks_committed,
                        terminal_reason_code=result.stop_reason,
                    )
                    await self._release_lease(handle, final)
                    if self._metric_hook is not None:
                        await self._metric_hook(run_id, "complete")
                    out = TickResultOut(
                        run_id=run_id,
                        lifecycle_state=LifecycleStateOut(final.lifecycle_state.value),
                        ticks_committed=final.ticks_committed,
                        progress_cursor=final.progress_cursor,
                        stop_reason=result.stop_reason,
                    )
                else:
                    paused = await self._run_control.transition(
                        run_id=record.run_id,
                        expected_version=record.lifecycle_version,
                        to_state=RunLifecycleState.READY,
                        reason_code="one_tick",
                        operation_id=generate_operation_id(),
                        ticks_committed=result.ticks_committed,
                        progress_cursor=result.ticks_committed,
                    )
                    await self._release_lease(handle, paused)
                    out = TickResultOut(
                        run_id=run_id,
                        lifecycle_state=LifecycleStateOut(paused.lifecycle_state.value),
                        ticks_committed=paused.ticks_committed,
                        progress_cursor=paused.progress_cursor,
                        stop_reason=result.stop_reason,
                    )
                _LOGGER.info(
                    "simulation_tick_complete",
                    run_id=run_id,
                    lifecycle_code=out.lifecycle_state.value,
                    ticks_committed=out.ticks_committed,
                    duration_ms=round((time.perf_counter() - started) * 1000, 3),
                )
                return out
            except ApiError:
                raise
            except Exception:
                _LOGGER.error(
                    "simulation_tick_failed",
                    run_id=run_id,
                    reason_code="tick_failed",
                )
                await self._fail_run(handle, record, reason_code="tick_failed")
                raise

    async def run(self, *, run_id: str) -> RunControlStatusOut:
        self._require_active()
        handle = await self._handle_for(run_id)
        async with handle.lock:
            if handle.task is not None and not handle.task.done():
                current = await self._require_record(run_id)
                return self._status_from_record(current)
            current = await self._require_record(run_id)
            if current.lifecycle_state not in {
                RunLifecycleState.READY,
                RunLifecycleState.PAUSED,
            }:
                raise conflict(code="lifecycle_conflict", run_id=run_id)
            handle.stop_requested = False
            record = await self._claim_and_enter_running(current, handle)
            handle.task = asyncio.create_task(
                self._run_until_stop(run_id), name=f"sim-run-{run_id}"
            )
            _LOGGER.info(
                "simulation_run_started",
                run_id=run_id,
                lifecycle_code=record.lifecycle_state.value,
            )
            return self._status_from_record(record)

    async def stop(self, *, run_id: str) -> RunControlStatusOut:
        handle = await self._handle_for(run_id)
        async with handle.lock:
            current = await self._require_record(run_id)
            if is_terminal_lifecycle_state(current.lifecycle_state):
                return self._status_from_record(current)
            handle.stop_requested = True
            if current.lifecycle_state is RunLifecycleState.RUNNING:
                stopping = await self._run_control.transition(
                    run_id=current.run_id,
                    expected_version=current.lifecycle_version,
                    to_state=RunLifecycleState.STOPPING,
                    reason_code="api_stop",
                    operation_id=generate_operation_id(),
                )
                _LOGGER.info(
                    "simulation_stopping",
                    run_id=run_id,
                    lifecycle_code=stopping.lifecycle_state.value,
                )
                return self._status_from_record(stopping)
            if current.lifecycle_state in {
                RunLifecycleState.READY,
                RunLifecycleState.PAUSED,
                RunLifecycleState.CONFIGURED,
            }:
                paused = await self._run_control.transition(
                    run_id=current.run_id,
                    expected_version=current.lifecycle_version,
                    to_state=RunLifecycleState.PAUSED,
                    reason_code="api_stop",
                    operation_id=generate_operation_id(),
                )
                return self._status_from_record(paused)
            raise conflict(code="lifecycle_conflict", run_id=run_id)

    async def status(self, *, run_id: str) -> RunControlStatusOut:
        record = await self._require_record(run_id)
        return self._status_from_record(record)

    async def list_runs(
        self, *, after_run_id: str | None = None, limit: int | None = None
    ) -> RunListOut:
        page_limit = limit if limit is not None else self._settings.api_max_page_size
        if page_limit < 1:
            raise bad_request(code="invalid_limit")
        page_limit = min(page_limit, self._settings.api_max_page_size)
        records = await self._run_control.list_runs(
            after_run_id=after_run_id, limit=page_limit + 1
        )
        has_more = len(records) > page_limit
        page = records[:page_limit]
        items = tuple(self._status_from_record(item) for item in page)
        next_cursor = page[-1].run_id.value if has_more and page else None
        return RunListOut(items=items, next_cursor=next_cursor, count=len(items))

    async def drain(self) -> None:
        """Graceful shutdown: stop admitting work and await run tasks."""
        self._draining = True
        _LOGGER.info("simulation_manager_draining")
        timeout = self._settings.api_drain_timeout_seconds
        async with self._handles_lock:
            handles = list(self._handles.values())
        for handle in handles:
            handle.stop_requested = True
        tasks = [handle.task for handle in handles if handle.task is not None]
        if tasks:
            await asyncio.wait(tasks, timeout=timeout)
        _LOGGER.info("simulation_manager_drained", task_count=len(tasks))

    async def _require_record(self, run_id: str) -> RunControlRecord:
        record = await self._run_control.get(RunId(run_id))
        if record is None:
            raise not_found(code="run_not_found", run_id=run_id)
        return record

    async def _claim_and_enter_running(
        self, current: RunControlRecord, handle: _RunHandle
    ) -> RunControlRecord:
        now = self._clock_ms()
        ttl_ms = int(self._settings.api_lease_ttl_seconds * 1000)
        lease = ExecutionLease(
            lease_id=generate_operation_id(),
            owner_id=self._owner_id,
            claimed_at_unix_ms=now,
            heartbeat_at_unix_ms=now,
            expires_at_unix_ms=now + ttl_ms,
        )
        claimed = await self._run_control.claim_lease(
            run_id=current.run_id,
            expected_version=current.lifecycle_version,
            lease=lease,
            operation_id=generate_operation_id(),
        )
        handle.lease_id = lease.lease_id
        if claimed.lifecycle_state is RunLifecycleState.READY:
            starting = await self._run_control.transition(
                run_id=claimed.run_id,
                expected_version=claimed.lifecycle_version,
                to_state=RunLifecycleState.STARTING,
                reason_code="api_claim",
                operation_id=generate_operation_id(),
            )
            running = await self._run_control.transition(
                run_id=starting.run_id,
                expected_version=starting.lifecycle_version,
                to_state=RunLifecycleState.RUNNING,
                reason_code="api_running",
                operation_id=generate_operation_id(),
            )
            return running
        if claimed.lifecycle_state is RunLifecycleState.PAUSED:
            starting = await self._run_control.transition(
                run_id=claimed.run_id,
                expected_version=claimed.lifecycle_version,
                to_state=RunLifecycleState.STARTING,
                reason_code="api_resume",
                operation_id=generate_operation_id(),
            )
            return await self._run_control.transition(
                run_id=starting.run_id,
                expected_version=starting.lifecycle_version,
                to_state=RunLifecycleState.RUNNING,
                reason_code="api_running",
                operation_id=generate_operation_id(),
            )
        if claimed.lifecycle_state is RunLifecycleState.RUNNING:
            return claimed
        raise conflict(code="lifecycle_conflict", run_id=current.run_id.value)

    async def _release_lease(
        self, handle: _RunHandle, record: RunControlRecord
    ) -> None:
        if handle.lease_id is None:
            return
        try:
            await self._run_control.release_lease(
                run_id=record.run_id,
                lease_id=handle.lease_id,
                operation_id=generate_operation_id(),
            )
        except Exception:
            _LOGGER.warning(
                "lease_release_failed",
                run_id=record.run_id.value,
                reason_code="lease_release_failed",
            )
        handle.lease_id = None

    async def _heartbeat(self, handle: _RunHandle, record: RunControlRecord) -> None:
        if handle.lease_id is None:
            return
        now = self._clock_ms()
        ttl_ms = int(self._settings.api_lease_ttl_seconds * 1000)
        await self._run_control.heartbeat_lease(
            run_id=record.run_id,
            lease_id=handle.lease_id,
            heartbeat_at_unix_ms=now,
            expires_at_unix_ms=now + ttl_ms,
            operation_id=generate_operation_id(),
        )

    async def _execute_one_tick(self, run_id: str) -> TickExecutionResult:
        if self._tick_executor is not None:
            return await self._tick_executor(run_id)
        handle = await self._handle_for(run_id)
        runner = handle.runner
        run_tick = getattr(runner, "run_tick", None)
        if runner is None or not callable(run_tick):
            raise bad_request(code="tick_executor_unset", run_id=run_id)
        receipt = await run_tick()
        stop = getattr(receipt, "stop_reason", None)
        stop_text = None if stop is None else str(getattr(stop, "value", stop))
        committed = getattr(runner, "ticks_committed", None)
        ticks = (
            committed
            if isinstance(committed, int)
            else int(getattr(receipt, "tick", 0)) + 1
        )
        return TickExecutionResult(
            ticks_committed=ticks,
            stop_reason=stop_text,
            completed=stop is not None,
        )

    async def _run_until_stop(self, run_id: str) -> None:
        handle = await self._handle_for(run_id)
        try:
            while True:
                async with handle.lock:
                    record = await self._require_record(run_id)
                    if is_terminal_lifecycle_state(record.lifecycle_state):
                        await self._release_lease(handle, record)
                        return
                    if handle.stop_requested or (
                        record.lifecycle_state is RunLifecycleState.STOPPING
                    ):
                        paused = await self._run_control.transition(
                            run_id=record.run_id,
                            expected_version=record.lifecycle_version,
                            to_state=RunLifecycleState.PAUSED,
                            reason_code="stop_at_boundary",
                            operation_id=generate_operation_id(),
                        )
                        await self._release_lease(handle, paused)
                        _LOGGER.info(
                            "simulation_stopped",
                            run_id=run_id,
                            lifecycle_code=paused.lifecycle_state.value,
                            ticks_committed=paused.ticks_committed,
                        )
                        return
                    await self._heartbeat(handle, record)
                    result = await self._execute_one_tick(run_id)
                    if result.completed:
                        final = await self._run_control.transition(
                            run_id=record.run_id,
                            expected_version=record.lifecycle_version,
                            to_state=RunLifecycleState.COMPLETED,
                            reason_code=result.stop_reason or "completed",
                            operation_id=generate_operation_id(),
                            ticks_committed=result.ticks_committed,
                            progress_cursor=result.ticks_committed,
                            terminal_reason_code=result.stop_reason,
                        )
                        await self._release_lease(handle, final)
                        if self._metric_hook is not None:
                            await self._metric_hook(run_id, "complete")
                        _LOGGER.info(
                            "simulation_completed",
                            run_id=run_id,
                            lifecycle_code=final.lifecycle_state.value,
                            ticks_committed=final.ticks_committed,
                        )
                        return
                    # Progress is always written through a ready-state edge
                    # because same-state RUNNING transitions are durable no-ops.
                    ready = await self._run_control.transition(
                        run_id=record.run_id,
                        expected_version=record.lifecycle_version,
                        to_state=RunLifecycleState.READY,
                        reason_code="tick_boundary",
                        operation_id=generate_operation_id(),
                        ticks_committed=result.ticks_committed,
                        progress_cursor=result.ticks_committed,
                    )
                    if handle.stop_requested:
                        paused = await self._run_control.transition(
                            run_id=ready.run_id,
                            expected_version=ready.lifecycle_version,
                            to_state=RunLifecycleState.PAUSED,
                            reason_code="stop_at_boundary",
                            operation_id=generate_operation_id(),
                        )
                        await self._release_lease(handle, paused)
                        _LOGGER.info(
                            "simulation_stopped",
                            run_id=run_id,
                            lifecycle_code=paused.lifecycle_state.value,
                            ticks_committed=paused.ticks_committed,
                        )
                        return
                    starting = await self._run_control.transition(
                        run_id=ready.run_id,
                        expected_version=ready.lifecycle_version,
                        to_state=RunLifecycleState.STARTING,
                        reason_code="continue",
                        operation_id=generate_operation_id(),
                    )
                    await self._run_control.transition(
                        run_id=starting.run_id,
                        expected_version=starting.lifecycle_version,
                        to_state=RunLifecycleState.RUNNING,
                        reason_code="continue",
                        operation_id=generate_operation_id(),
                    )
                await asyncio.sleep(0)
        except Exception:
            _LOGGER.error(
                "simulation_run_failed",
                run_id=run_id,
                reason_code="run_task_failed",
            )
            async with handle.lock:
                failed_record = await self._run_control.get(RunId(run_id))
                if failed_record is not None:
                    await self._fail_run(
                        handle, failed_record, reason_code="run_task_failed"
                    )

    async def _fail_run(
        self, handle: _RunHandle, record: RunControlRecord, *, reason_code: str
    ) -> None:
        try:
            failed = await self._run_control.transition(
                run_id=record.run_id,
                expected_version=record.lifecycle_version,
                to_state=RunLifecycleState.FAILED,
                reason_code=reason_code,
                operation_id=generate_operation_id(),
                terminal_reason_code=reason_code,
            )
            await self._release_lease(handle, failed)
        except Exception:
            _LOGGER.warning(
                "fail_transition_skipped",
                run_id=record.run_id.value,
                reason_code="fail_transition_skipped",
            )

    async def _maybe_rehydrate(
        self, handle: _RunHandle, record: RunControlRecord
    ) -> None:
        if handle.runner is not None or self._runner_factory is None:
            return
        if record.config_availability is ConfigAvailability.UNAVAILABLE:
            return
        handle.runner = await self._runner_factory(record)
        _LOGGER.info(
            "simulation_rehydrated",
            run_id=record.run_id.value,
            lifecycle_code=record.lifecycle_state.value,
            ticks_committed=record.ticks_committed,
        )


def decode_config_payload_b64(payload_b64: str) -> bytes:
    try:
        raw = base64.b64decode(payload_b64, validate=True)
    except Exception as exc:
        raise bad_request(code="invalid_config_encoding") from exc
    return raw
