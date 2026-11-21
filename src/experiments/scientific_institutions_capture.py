"""Explicit bounded capture driver for scientific-institution evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.scientific_institutions_contract import (
    MAX_BOUNDARY_OWNERS,
    MAX_CUMULATIVE_EVENTS,
    MAX_PRACTICE_TICKS,
)
from experiments.scientific_institutions_completed_run import (
    ScientificInstitutionBoundaryInput,
    ScientificInstitutionEvidence,
    build_scientific_institution_windows,
)
from experiments.scientific_institutions_context import (
    ScientificInstitutionContextEvidence,
    build_scientific_institution_context,
)
from simulation import (
    ObjectiveFacts,
    SimulationRunnerConfig,
    SimulationRunnerResult,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerAttemptStatus,
    RunnerStopReasonCode,
)
from world.events import WorldEvent

__all__ = [
    "ScientificInstitutionCaptureResult",
    "capture_supported",
    "run_with_scientific_institution_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_institutions_capture"
)


@dataclass(frozen=True, slots=True)
class ScientificInstitutionCaptureResult:
    """Typed result plus detached, non-authoritative capture material."""

    result: SimulationRunnerResult
    evidence: ScientificInstitutionEvidence | None
    context: ScientificInstitutionContextEvidence | None
    boundaries: tuple[ScientificInstitutionBoundaryInput, ...]
    baseline_events: tuple[WorldEvent, ...]
    status: str


def capture_supported(config: SimulationRunnerConfig) -> bool:
    """Capture needs both owned channels and bounded run controls."""

    if type(config) is not SimulationRunnerConfig:
        return False
    if not config.v4_capability_flags.organizations:
        return False
    if not config.v4_capability_flags.science:
        return False
    if config.durable_records is None:
        return False
    if config.stop_policy.max_ticks > MAX_PRACTICE_TICKS:
        return False
    return True


def _bounds_ok(runner: SimulationRunner, inventory: ObjectiveFacts) -> bool:
    if len(inventory.registrations) > MAX_BOUNDARY_OWNERS:
        return False
    if len(runner.engine.export_events().events) > MAX_CUMULATIVE_EVENTS:
        return False
    return True


async def _capture(
    runner: SimulationRunner,
) -> ScientificInstitutionBoundaryInput | None:
    inventory = runner.engine.detached_objective_facts()
    if not _bounds_ok(runner, inventory):
        return None
    boundary = await runner.export_finalized_research_boundary()
    return ScientificInstitutionBoundaryInput(
        boundary=boundary,  # type: ignore[arg-type]
        inventory=inventory,
    )


async def run_with_scientific_institution_capture(
    runner: SimulationRunner,
    *,
    capture: bool = True,
) -> ScientificInstitutionCaptureResult:
    """Run with explicit full-window capture; never installs a runtime sink."""

    config = runner.config
    if not capture or not capture_supported(config):
        result = await runner.run()
        _LOG.info(
            "scientific_institutions_capture_disabled run_id=%s",
            result.run_id.value,
        )
        return ScientificInstitutionCaptureResult(
            result=result,
            evidence=None,
            context=None,
            boundaries=(),
            baseline_events=(),
            status="unavailable",
        )
    await runner.initialize_finalized_boundary()
    baseline = tuple(runner.engine.export_events().events)
    boundaries: list[ScientificInstitutionBoundaryInput] = []
    status = "captured"
    try:
        first = await _capture(runner)
        if first is None:
            raise RuntimeError("capture_bounds")
        boundaries.append(first)
    except Exception:
        status = "capture_failed"
        boundaries.clear()
    stop_reason: RunnerStopReasonCode | None = None
    while stop_reason is None:
        receipt = await runner.run_tick()
        if receipt.status is RunnerAttemptStatus.ABORTED:
            stop_reason = (
                receipt.stop_reason
                if receipt.stop_reason is not None
                else RunnerStopReasonCode.AUTHORITY_FAILURE
            )
            break
        stop_reason = receipt.stop_reason
        if (
            stop_reason is None
            and runner.ticks_committed >= config.stop_policy.max_ticks
        ):
            stop_reason = RunnerStopReasonCode.MAX_TICKS
        if status == "captured" and stop_reason is None:
            if runner.ticks_committed % 32 == 0:
                try:
                    boundary = await _capture(runner)
                    if boundary is None:
                        raise RuntimeError("capture_bounds")
                    boundaries.append(boundary)
                except Exception:
                    status = "capture_failed"
                    boundaries.clear()
    result = await runner.finish_run(stop_reason)
    if status == "captured":
        try:
            if (
                not boundaries
                or boundaries[-1].boundary.boundary_tick.value
                != result.ticks_committed
            ):
                boundary = await _capture(runner)
                if boundary is None:
                    raise RuntimeError("capture_bounds")
                boundaries.append(boundary)
        except Exception:
            status = "capture_failed"
            boundaries.clear()
    if status != "captured":
        _LOG.warning(
            "scientific_institutions_capture_failed run_id=%s",
            result.run_id.value,
        )
        return ScientificInstitutionCaptureResult(
            result=result,
            evidence=None,
            context=None,
            boundaries=(),
            baseline_events=baseline,
            status=status,
        )
    try:
        evidence = build_scientific_institution_windows(
            result,
            config,
            tuple(boundaries),
            baseline_events=baseline,
        )
        context = build_scientific_institution_context(
            evidence,
            tuple(boundaries),
            config,
            teaching_audits=tuple(result.teaching_audits),
        )
    except Exception:
        _LOG.warning(
            "scientific_institutions_analysis_unavailable run_id=%s",
            result.run_id.value,
        )
        return ScientificInstitutionCaptureResult(
            result=result,
            evidence=None,
            context=None,
            boundaries=tuple(boundaries),
            baseline_events=baseline,
            status="analysis_unavailable",
        )
    _LOG.info(
        "scientific_institutions_capture_complete run_id=%s boundaries=%s",
        result.run_id.value,
        len(boundaries),
    )
    return ScientificInstitutionCaptureResult(
        result=result,
        evidence=evidence,
        context=context,
        boundaries=tuple(boundaries),
        baseline_events=baseline,
        status="captured",
    )
