"""Opt-in commons governance capture: sink, seal, and report."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.commons_governance_metrics import (
    COMMONS_GOVERNANCE_REPORT_VERSION,
    CommonsGovernanceReport,
    CommonsLaneCoverage,
    build_commons_governance_report,
)
from analysis.overexploitation_history import (
    HistoryCoverage,
    HistoryTick,
    OverexploitationHistory,
    build_overexploitation_history,
)
from experiments.overexploitation_history import (
    applicability_from_config,
    unavailable_scope_unverified,
)
from simulation.commons_governance_evidence import (
    MAX_COMMONS_BOUNDARY_EVENTS,
    MAX_COMMONS_BOUNDARY_TICKS,
    MAX_COMMONS_OWNER_TRANSITION_ROWS,
    CommonsGovernanceBoundaryExport,
    CommonsGovernanceCaptureStatus,
    CommonsLaneStatus,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V61,
    is_failure_stop_reason,
)
from world.identifiers import EntityId

__all__ = [
    "CommonsGovernanceCaptureResult",
    "CommonsGovernanceRecorder",
    "run_with_commons_governance_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.commons_governance_capture"
)


@dataclass(frozen=True, slots=True)
class CommonsGovernanceCaptureResult:
    """Terminal runner result plus sealed report when capture succeeds."""

    result: object
    status: CommonsGovernanceCaptureStatus
    report: CommonsGovernanceReport | None
    reason_codes: tuple[str, ...] = ()
    boundaries: tuple[CommonsGovernanceBoundaryExport, ...] = ()
    expected_ticks: int = 0
    usable_ticks: int = 0
    expected_owner_boundaries: int = 0
    usable_owner_boundaries: int = 0


class CommonsGovernanceRecorder:
    """In-process boundary sink with sticky cap/failure status."""

    def __init__(self) -> None:
        self._frames: list[CommonsGovernanceBoundaryExport] = []
        self._seen: set[int] = set()
        self._event_count = 0
        self._transition_count = 0
        self._failed = False
        self._failure_code: str | None = None
        self._gap_at: int | None = None
        self._capped = False

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def failure_code(self) -> str | None:
        return self._failure_code

    @property
    def frames(self) -> tuple[CommonsGovernanceBoundaryExport, ...]:
        return tuple(self._frames)

    def capture(self, frame: CommonsGovernanceBoundaryExport) -> None:
        if type(frame) is not CommonsGovernanceBoundaryExport:
            raise TypeError("frame must be CommonsGovernanceBoundaryExport")
        if self._failed or self._capped:
            return
        if frame.boundary_tick in self._seen:
            return
        # Contiguous prefix only; first gap seals later as partial.
        if self._frames:
            last = self._frames[-1].boundary_tick
            if frame.boundary_tick != last + 1 and frame.boundary_tick != last:
                self._gap_at = frame.boundary_tick
                self._mark_failure("capture_gap")
                return
        incoming_events = frame.event_count
        incoming_transitions = frame.transition_row_count
        if (
            len(self._frames) >= MAX_COMMONS_BOUNDARY_TICKS
            or self._event_count + incoming_events > MAX_COMMONS_BOUNDARY_EVENTS
            or self._transition_count + incoming_transitions
            > MAX_COMMONS_OWNER_TRANSITION_ROWS
        ):
            self._capped = True
            self._mark_failure("capture_cap")
            return
        self._frames.append(frame)
        self._seen.add(frame.boundary_tick)
        self._event_count += incoming_events
        self._transition_count += incoming_transitions
        _LOG.debug(
            "commons_governance_boundary_captured boundary_tick=%s "
            "owners=%s events=%s transitions=%s",
            frame.boundary_tick,
            len(frame.owners),
            incoming_events,
            incoming_transitions,
        )

    def _mark_failure(self, code: str) -> None:
        if self._failed:
            return
        self._failed = True
        self._failure_code = code
        _LOG.warning(
            "commons_governance_capture_closed reason_code=%s frames=%s",
            code,
            len(self._frames),
        )


def _stock_ids_from_config(
    config: object, stock_ids: Sequence[EntityId] | None
) -> tuple[EntityId, ...] | None:
    commons = getattr(config, "commons_governance", None)
    schema = getattr(config, "schema_version", None)
    if stock_ids is not None:
        selected = tuple(stock_ids)
        for item in selected:
            if type(item) is not EntityId:
                raise TypeError("stock_ids entries must be EntityId")
        if commons is not None:
            configured = tuple(commons.stock_ids)
            if selected != configured:
                raise ValueError("commons_governance_stock_selection_mismatch")
        return selected
    if commons is not None:
        return tuple(commons.stock_ids)
    if schema == RUNNER_SCHEMA_VERSION_V61:
        return None
    return None


def _social_applicable(config: object) -> bool:
    return getattr(config, "commons_governance", None) is not None


def _seal_report(
    *,
    runner: SimulationRunner,
    recorder: CommonsGovernanceRecorder,
    stock_ids: tuple[EntityId, ...],
    result: object,
    reasons: list[str],
) -> CommonsGovernanceReport | None:
    from world.identifiers import WorldId

    frames = list(recorder.frames)
    if recorder.failed and not frames:
        return None
    if recorder.failed and recorder.failure_code == "capture_gap":
        reasons.append("capture_gap")
    if recorder.failed and recorder.failure_code == "capture_cap":
        reasons.append("capture_cap")

    config = runner.config
    run_id = runner.run_id
    world_id = WorldId(str(runner.engine.world_id.value))
    social = _social_applicable(config)

    ticks: list[HistoryTick] = []
    for frame in frames:
        if frame.boundary_tick == 0:
            continue
        ticks.append(
            HistoryTick(
                run_id=run_id,
                world_id=world_id,
                tick=frame.boundary_tick - 1,
                complete=True,
                events=frame.events,
            )
        )

    end_tick = max(0, int(getattr(result, "ticks_committed", 0)) - 1)
    histories: dict[EntityId, OverexploitationHistory] = {}
    for stock in stock_ids:
        applicability = applicability_from_config(config, stock)
        if applicability is None:
            history = unavailable_scope_unverified(
                run_id=run_id,
                world_id=world_id,
                resource_id=stock,
                start_tick=0,
                end_tick=end_tick,
            )
        else:
            history = build_overexploitation_history(
                run_id=run_id,
                world_id=world_id,
                resource_id=stock,
                start_tick=0,
                end_tick=end_tick,
                applicability=applicability,
                ticks=tuple(ticks),
            )
        histories[stock] = history
        if history.coverage is not HistoryCoverage.AVAILABLE:
            reasons.append(f"history_{history.stop_code.value}")

    founder_ids = tuple(
        sorted(agent.agent_id.value for agent in config.agents)
    )
    expected_ticks = int(config.stop_policy.max_ticks)
    usable_ticks = sum(1 for frame in frames if frame.boundary_tick > 0)
    if usable_ticks > expected_ticks:
        usable_ticks = expected_ticks

    lane_objective = CommonsLaneStatus.COMPLETE
    if usable_ticks == 0 and expected_ticks > 0:
        lane_objective = CommonsLaneStatus.UNAVAILABLE
    elif usable_ticks < expected_ticks or recorder.failed:
        lane_objective = CommonsLaneStatus.PARTIAL
    social_status = (
        CommonsLaneStatus.INAPPLICABLE
        if not social
        else lane_objective
    )
    lanes = {
        "objective_sustainability": CommonsLaneCoverage(
            lane="objective_sustainability",
            status=lane_objective,
            expected=expected_ticks,
            usable=usable_ticks,
            reason_codes=tuple(
                code for code in reasons if code.startswith("history_")
            ),
        ),
        "objective_joint_use": CommonsLaneCoverage(
            lane="objective_joint_use",
            status=lane_objective,
            expected=expected_ticks,
            usable=usable_ticks,
        ),
        "subjective_cooperation": CommonsLaneCoverage(
            lane="subjective_cooperation",
            status=social_status,
            expected=0 if not social else expected_ticks,
            usable=0 if not social else usable_ticks,
            reason_codes=(("social_inapplicable",) if not social else ()),
        ),
        "welfare_thirst": CommonsLaneCoverage(
            lane="welfare_thirst",
            status=lane_objective,
            expected=len(founder_ids),
            usable=0,
        ),
    }

    baseline_by_stock: dict[EntityId, int] = {}
    ecology = getattr(config, "ecological_resources", None)
    if ecology is not None:
        for node in ecology.nodes:
            # baseline quantity tenths from scenario resources when available
            for resource in config.scenario.resources:
                if resource.entity_id == node.resource_id:
                    tenths = round(float(resource.quantity) * 10.0)
                    baseline_by_stock[node.resource_id] = tenths
                    break

    report = build_commons_governance_report(
        run_id=run_id.value,
        stock_ids=stock_ids,
        histories=histories,
        boundaries=tuple(frames),
        founder_ids=founder_ids,
        social_applicable=social,
        lane_statuses=lanes,
        baseline_tenths_by_stock=baseline_by_stock,
        expected_ticks=expected_ticks,
        reason_codes=reasons,
    )
    # Refresh welfare lane usable from sealed report.
    lanes["welfare_thirst"] = CommonsLaneCoverage(
        lane="welfare_thirst",
        status=lane_objective,
        expected=len(founder_ids),
        usable=report.welfare.thirst_observation_coverage,
        reason_codes=report.welfare.reason_codes,
    )
    return CommonsGovernanceReport(
        schema_version=COMMONS_GOVERNANCE_REPORT_VERSION,
        run_id=report.run_id,
        stock_ids=report.stock_ids,
        lanes=tuple(lanes[key] for key in sorted(lanes)),
        sustainability=report.sustainability,
        joint_use=report.joint_use,
        cooperation=report.cooperation,
        welfare=report.welfare,
        social_applicable=report.social_applicable,
        reason_codes=report.reason_codes,
    )


async def run_with_commons_governance_capture(
    runner: SimulationRunner,
    *,
    capture: bool = True,
    stock_ids: Sequence[EntityId] | None = None,
) -> CommonsGovernanceCaptureResult:
    """Run once with an opt-in boundary sink and seal a detached report."""

    if type(runner) is not SimulationRunner:
        raise TypeError("runner must be SimulationRunner")
    if type(capture) is not bool:
        raise TypeError("capture must be bool")

    config = runner.config
    if not capture:
        result = await runner.run()
        _LOG.info(
            "commons_governance_capture_disabled run_id=%s",
            result.run_id.value,
        )
        return CommonsGovernanceCaptureResult(
            result=result,
            status=CommonsGovernanceCaptureStatus.DISABLED,
            report=None,
            reason_codes=("capture_disabled",),
        )

    try:
        selected = _stock_ids_from_config(config, stock_ids)
    except ValueError as exc:
        result = await runner.run()
        return CommonsGovernanceCaptureResult(
            result=result,
            status=CommonsGovernanceCaptureStatus.UNAVAILABLE,
            report=None,
            reason_codes=(str(exc),),
        )

    if selected is None:
        # v61 without explicit research stock IDs cannot capture.
        result = await runner.run()
        return CommonsGovernanceCaptureResult(
            result=result,
            status=CommonsGovernanceCaptureStatus.UNAVAILABLE,
            report=None,
            reason_codes=("stock_selection_required",),
        )

    if getattr(config, "overexploitation", None) is None:
        result = await runner.run()
        return CommonsGovernanceCaptureResult(
            result=result,
            status=CommonsGovernanceCaptureStatus.UNAVAILABLE,
            report=None,
            reason_codes=("overexploitation_inactive",),
        )

    recorder = CommonsGovernanceRecorder()
    runner.set_commons_governance_boundary_sink(recorder)
    result = await runner.run()
    reasons: list[str] = []

    if is_failure_stop_reason(result.stop_reason):
        reasons.append("terminal_abort")

    frames = recorder.frames
    if not frames and recorder.failed:
        return CommonsGovernanceCaptureResult(
            result=result,
            status=CommonsGovernanceCaptureStatus.UNAVAILABLE,
            report=None,
            reason_codes=tuple(
                sorted({*reasons, recorder.failure_code or "capture_failed"})
            ),
            expected_ticks=int(config.stop_policy.max_ticks),
            usable_ticks=0,
        )

    if not frames:
        # Enabled zero-activity complete window is still complete with zeros.
        status = CommonsGovernanceCaptureStatus.COMPLETE
        if result.ticks_committed == 0:
            status = CommonsGovernanceCaptureStatus.UNAVAILABLE
            reasons.append("no_boundaries")
        report = None
        if status is CommonsGovernanceCaptureStatus.COMPLETE:
            try:
                report = _seal_report(
                    runner=runner,
                    recorder=recorder,
                    stock_ids=selected,
                    result=result,
                    reasons=reasons,
                )
            except Exception:
                _LOG.warning(
                    "commons_governance_seal_failed run_id=%s",
                    result.run_id.value,
                )
                return CommonsGovernanceCaptureResult(
                    result=result,
                    status=CommonsGovernanceCaptureStatus.UNAVAILABLE,
                    report=None,
                    reason_codes=("seal_failed",),
                )
        return CommonsGovernanceCaptureResult(
            result=result,
            status=status,
            report=report,
            reason_codes=tuple(sorted(set(reasons))),
            boundaries=frames,
            expected_ticks=int(config.stop_policy.max_ticks),
            usable_ticks=0,
        )

    try:
        report = _seal_report(
            runner=runner,
            recorder=recorder,
            stock_ids=selected,
            result=result,
            reasons=reasons,
        )
    except Exception:
        _LOG.warning(
            "commons_governance_seal_failed run_id=%s",
            result.run_id.value,
            exc_info=True,
        )
        return CommonsGovernanceCaptureResult(
            result=result,
            status=(
                CommonsGovernanceCaptureStatus.PARTIAL
                if frames
                else CommonsGovernanceCaptureStatus.UNAVAILABLE
            ),
            report=None,
            reason_codes=tuple(sorted({*reasons, "seal_failed"})),
            boundaries=frames,
            expected_ticks=int(config.stop_policy.max_ticks),
            usable_ticks=sum(1 for frame in frames if frame.boundary_tick > 0),
        )

    usable = sum(1 for frame in frames if frame.boundary_tick > 0)
    expected = int(config.stop_policy.max_ticks)
    if report is None:
        status = CommonsGovernanceCaptureStatus.UNAVAILABLE
    elif recorder.failed or usable < expected or reasons:
        status = CommonsGovernanceCaptureStatus.PARTIAL
    else:
        status = CommonsGovernanceCaptureStatus.COMPLETE

    _LOG.info(
        "commons_governance_capture run_id=%s status=%s usable_ticks=%s "
        "schema=%s stocks=%s",
        result.run_id.value,
        status.value,
        usable,
        getattr(config, "schema_version", None),
        len(selected),
    )
    return CommonsGovernanceCaptureResult(
        result=result,
        status=status,
        report=report,
        reason_codes=tuple(sorted(set(reasons))),
        boundaries=frames,
        expected_ticks=expected,
        usable_ticks=usable,
        expected_owner_boundaries=expected * len(config.agents),
        usable_owner_boundaries=sum(len(frame.owners) for frame in frames),
    )
