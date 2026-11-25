"""Opt-in societal-resilience capture over finalized disaster-active runs.

Trusted experiments wrapper only. Never installs an arbiter, stop selector,
observer mode, runtime callback, or runner-config sibling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, Literal

from analysis.resilience_windows import (
    ScheduleEntry,
    ShockReceipt,
    build_shock_windows,
)
from simulation.resilience_evidence import (
    MAX_RESILIENCE_APPLIED_SHOCK_TICKS,
    MAX_RESILIENCE_CUMULATIVE_EVENTS,
    MAX_RESILIENCE_CUMULATIVE_FRAME_ROWS,
    MAX_RESILIENCE_HORIZON,
    MAX_RESILIENCE_ROSTER,
    ResilienceBatchEvents,
    ResilienceBoundaryFacts,
    ResilienceEvidenceError,
    count_normalized_rows,
    project_resilience_batch_events,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V63,
    RunnerAttemptStatus,
    RunnerStopReasonCode,
    is_failure_stop_reason,
)

__all__ = [
    "ResilienceCaptureResult",
    "ResilienceSealedEvidence",
    "run_with_resilience_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.resilience_capture")

CaptureStatus = Literal[
    "disabled",
    "unsupported",
    "captured",
    "sealed",
    "aborted",
]


@dataclass(frozen=True, slots=True)
class ResilienceSealedEvidence:
    """In-process sealed prefix for detached resilience reducers."""

    run_id: str
    config_fingerprint: str
    finalized_through: int
    capture_through: int
    frames: tuple[ResilienceBoundaryFacts, ...]
    batches: tuple[ResilienceBatchEvents, ...]
    schedule: tuple[ScheduleEntry, ...]
    seal_reason: str | None


@dataclass(frozen=True, slots=True)
class ResilienceCaptureResult:
    """Original runner result plus closed capture status."""

    result: object
    status: CaptureStatus
    evidence: ResilienceSealedEvidence | None
    reason_code: str | None = None


def _capture_supported(runner: SimulationRunner) -> tuple[bool, str | None]:
    config = runner.config
    if getattr(config, "schema_version", None) != RUNNER_SCHEMA_VERSION_V63:
        return False, "schema_unsupported"
    if getattr(config, "disasters", None) is None:
        return False, "disasters_required"
    max_ticks = config.stop_policy.max_ticks
    if (
        type(max_ticks) is not int
        or isinstance(max_ticks, bool)
        or max_ticks < 1
        or max_ticks > MAX_RESILIENCE_HORIZON
    ):
        return False, "horizon_unsupported"
    if runner.ticks_committed != 0 or runner.engine.tick.value != 0:
        return False, "pre_start_required"
    if runner.engine.history_length != 0:
        return False, "history_not_empty"
    if len(runner.engine.ordered_registrations) > MAX_RESILIENCE_ROSTER:
        return False, "roster_overflow"
    return True, None


def _schedule_entries(config: object) -> tuple[ScheduleEntry, ...]:
    disasters = getattr(config, "disasters", None)
    if disasters is None:
        return ()
    return tuple(
        ScheduleEntry(tick=entry.tick, rule_id=entry.rule_id)
        for entry in disasters.schedule
    )


class _Accumulator:
    """Bounded in-process prefix; seals before first overflow/mismatch."""

    def __init__(self, *, run_id: str, config_fingerprint: str) -> None:
        self.run_id = run_id
        self.config_fingerprint = config_fingerprint
        self.frames: list[ResilienceBoundaryFacts] = []
        self.batches: list[ResilienceBatchEvents] = []
        self._event_count = 0
        self._row_count = 0
        self._applied_shock_ticks: set[int] = set()
        self._prev_history_length = 0
        self.seal_reason: str | None = None
        self._seal_warned = False

    @property
    def sealed(self) -> bool:
        return self.seal_reason is not None

    def seal(self, reason: str, *, stage: str) -> None:
        if self.seal_reason is not None:
            return
        self.seal_reason = reason
        if not self._seal_warned:
            self._seal_warned = True
            _LOG.warning(
                "resilience_capture_sealed reason=%s stage=%s run_id=%s "
                "frames=%s events=%s",
                reason,
                stage,
                self.run_id,
                len(self.frames),
                self._event_count,
            )

    def accept_frame(
        self,
        frame: ResilienceBoundaryFacts,
        *,
        batch: ResilienceBatchEvents | None,
    ) -> bool:
        if self.sealed:
            return False
        if frame.run_id != self.run_id:
            self.seal("run_mismatch", stage="frame")
            return False
        if self.frames and frame.boundary_tick != self.frames[-1].boundary_tick + 1:
            if frame.boundary_tick == self.frames[-1].boundary_tick:
                return True
            self.seal("capture_gap", stage="frame")
            return False
        incoming_rows = count_normalized_rows(
            bodies=frame.bodies,
            stocks=frame.stocks,
            infrastructure=frame.infrastructure,
            owners=frame.owners,
        )
        incoming_events = 0 if batch is None else batch.event_count
        if (
            self._event_count + incoming_events > MAX_RESILIENCE_CUMULATIVE_EVENTS
            or self._row_count + incoming_rows > MAX_RESILIENCE_CUMULATIVE_FRAME_ROWS
        ):
            self.seal("capture_cap", stage="frame")
            return False
        if batch is not None:
            applied_ticks = {
                receipt.tick
                for receipt in batch.shock_receipts
                if receipt.outcome == "applied"
            }
            projected = self._applied_shock_ticks | applied_ticks
            if len(projected) > MAX_RESILIENCE_APPLIED_SHOCK_TICKS:
                self.seal("applied_shock_cap", stage="frame")
                return False
            expected_history = self._prev_history_length + batch.event_count
            if frame.history_length != expected_history:
                self.seal("history_append_mismatch", stage="frame")
                return False
            if batch.tick != frame.boundary_tick - 1:
                self.seal("batch_tick_mismatch", stage="frame")
                return False
            if batch.resulting_revision != frame.revision:
                self.seal("batch_revision_mismatch", stage="frame")
                return False
            self.batches.append(batch)
            self._applied_shock_ticks = projected
            self._event_count += batch.event_count
            self._prev_history_length = frame.history_length
        elif frame.boundary_tick == 0:
            if frame.history_length != 0:
                self.seal("history_append_mismatch", stage="baseline")
                return False
            self._prev_history_length = 0
        else:
            self.seal("batch_required", stage="frame")
            return False
        self.frames.append(frame)
        self._row_count += incoming_rows
        _LOG.debug(
            "resilience_boundary_accepted run_id=%s boundary_tick=%s row_count=%s",
            self.run_id,
            frame.boundary_tick,
            incoming_rows,
        )
        return True

async def _sample_boundary(
    runner: SimulationRunner,
    *,
    accumulator: _Accumulator,
    expect_batch: bool,
) -> bool:
    frame = await runner.export_resilience_boundary()
    if type(frame) is not ResilienceBoundaryFacts:
        raise TypeError("export_resilience_boundary must return ResilienceBoundaryFacts")
    batch: ResilienceBatchEvents | None = None
    if expect_batch:
        tick_result = runner.engine.last_tick_result
        if tick_result is None:
            accumulator.seal("batch_missing", stage="sample")
            return False
        # Budget check before projecting rows from an oversized batch.
        remaining = MAX_RESILIENCE_CUMULATIVE_EVENTS - accumulator._event_count
        if len(tick_result.events) > remaining:
            accumulator.seal("capture_cap", stage="batch_budget")
            return False
        world_events = tuple(record.event for record in tick_result.events)
        batch = project_resilience_batch_events(
            world_events,
            tick=tick_result.tick.value,
            resulting_revision=tick_result.resulting_revision.value,
        )
    return accumulator.accept_frame(frame, batch=batch)


async def run_with_resilience_capture(
    runner: SimulationRunner,
    *,
    capture: bool = False,
) -> ResilienceCaptureResult:
    """Run once with optional finalized-boundary resilience capture."""

    from simulation.runner_serialization import runner_config_fingerprint

    if not capture:
        result = await runner.run()
        _LOG.info(
            "resilience_capture_disabled run_id=%s",
            result.run_id.value,
        )
        return ResilienceCaptureResult(
            result=result,
            status="disabled",
            evidence=None,
            reason_code="capture_disabled",
        )

    supported, reason = _capture_supported(runner)
    if not supported:
        result = await runner.run()
        _LOG.info(
            "resilience_capture_unsupported run_id=%s reason=%s",
            result.run_id.value,
            reason,
        )
        return ResilienceCaptureResult(
            result=result,
            status="unsupported",
            evidence=None,
            reason_code=reason,
        )

    await runner.initialize_finalized_boundary()
    schedule = _schedule_entries(runner.config)
    accumulator = _Accumulator(
        run_id=runner.run_id.value,
        config_fingerprint=runner_config_fingerprint(runner.config),
    )
    status: CaptureStatus = "captured"
    aborted = False

    try:
        await _sample_boundary(runner, accumulator=accumulator, expect_batch=False)
    except Exception:
        accumulator.seal("capture_failed", stage="baseline")
        status = "sealed"

    stop_reason: RunnerStopReasonCode | None = None
    while stop_reason is None:
        receipt = await runner.run_tick()
        if receipt.status is RunnerAttemptStatus.ABORTED:
            aborted = True
            stop_reason = (
                receipt.stop_reason
                if receipt.stop_reason is not None
                else RunnerStopReasonCode.AUTHORITY_FAILURE
            )
            break
        stop_reason = receipt.stop_reason
        if (
            stop_reason is None
            and runner.ticks_committed >= runner.config.stop_policy.max_ticks
        ):
            stop_reason = RunnerStopReasonCode.MAX_TICKS
        if accumulator.sealed or stop_reason is not None:
            continue
        try:
            accepted = await _sample_boundary(
                runner, accumulator=accumulator, expect_batch=True
            )
            if not accepted:
                status = "sealed"
        except Exception:
            accumulator.seal("capture_failed", stage="tick")
            status = "sealed"

    result = await runner.finish_run(stop_reason)
    result_stop = getattr(result, "stop_reason", None)
    if aborted or (
        type(result_stop) is RunnerStopReasonCode
        and is_failure_stop_reason(result_stop)
    ):
        _LOG.info(
            "resilience_capture_aborted run_id=%s frames=%s",
            result.run_id.value,
            len(accumulator.frames),
        )
        return ResilienceCaptureResult(
            result=result,
            status="aborted",
            evidence=None,
            reason_code="scientific_abort",
        )

    if not accumulator.sealed:
        try:
            if (
                not accumulator.frames
                or accumulator.frames[-1].boundary_tick != result.ticks_committed
            ):
                accepted = await _sample_boundary(
                    runner, accumulator=accumulator, expect_batch=True
                )
                if not accepted:
                    status = "sealed"
        except Exception:
            accumulator.seal("capture_failed", stage="terminal")
            status = "sealed"

    # Join schedule against projected shock receipts for sealed evidence.
    receipts: list[ShockReceipt] = []
    for batch in accumulator.batches:
        for row in batch.shock_receipts:
            receipts.append(
                ShockReceipt(
                    tick=row.tick,
                    sequence=row.sequence,
                    event_id=row.event_id,
                    kind=row.kind,
                    origin=row.origin,
                    outcome=row.outcome,
                    rule_id=row.rule_id,
                )
            )
    capture_through = (
        accumulator.frames[-1].boundary_tick if accumulator.frames else 0
    )
    finalized_through = result.ticks_committed
    try:
        build_shock_windows(
            tuple(receipts),
            run_id=runner.run_id.value,
            finalized_through=finalized_through,
            capture_through=capture_through,
            schedule=schedule,
        )
    except Exception:
        accumulator.seal("window_build_failed", stage="seal")
        status = "sealed"

    evidence = ResilienceSealedEvidence(
        run_id=runner.run_id.value,
        config_fingerprint=accumulator.config_fingerprint,
        finalized_through=finalized_through,
        capture_through=capture_through,
        frames=tuple(accumulator.frames),
        batches=tuple(accumulator.batches),
        schedule=schedule,
        seal_reason=accumulator.seal_reason,
    )
    if accumulator.sealed:
        status = "sealed"
    _LOG.info(
        "resilience_capture_complete run_id=%s status=%s frames=%s events=%s",
        result.run_id.value,
        status,
        len(evidence.frames),
        sum(batch.event_count for batch in evidence.batches),
    )
    return ResilienceCaptureResult(
        result=result,
        status=status,
        evidence=evidence,
        reason_code=accumulator.seal_reason,
    )
