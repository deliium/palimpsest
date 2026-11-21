"""Explicit bounded capture driver for scientific-knowledge diffusion evidence."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.science_diffusion_contract import (
    MAX_DIFFUSION_EVENTS,
    MAX_DIFFUSION_OWNERS,
    MAX_DIFFUSION_TICKS,
    DiffusionAccumulator,
    DiffusionError,
    DiffusionInputs,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionReason,
    LaneCoverage,
    LaneCoverageState,
    StagedDiffusionBoundary,
)
from experiments.science_diffusion_carriers import project_carrier_occurrences
from experiments.science_diffusion_projection import (
    CanonicalEventPrefix,
    ScienceBoundarySample,
    canonical_event_prefix,
    project_science_versions,
    validate_boundary_identity,
    verify_prefix_extension,
)
from simulation import (
    ObjectiveFacts,
    SimulationRunnerConfig,
    SimulationRunnerResult,
)
from simulation.fork_checkpoint import FinalizedResearchBoundary
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerAttemptStatus,
    RunnerStopReasonCode,
)

__all__ = [
    "ScienceDiffusionCaptureResult",
    "capture_supported",
    "run_with_science_diffusion_capture",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_capture"
)


@dataclass(frozen=True, slots=True)
class ScienceDiffusionCaptureResult:
    """Typed result plus detached, non-authoritative diffusion material."""

    result: SimulationRunnerResult
    inputs: DiffusionInputs | None
    samples: tuple[ScienceBoundarySample, ...]
    prefix: CanonicalEventPrefix | None
    status: str


def capture_supported(config: SimulationRunnerConfig) -> bool:
    """Core capture needs the owned science gate and bounded run controls."""

    if type(config) is not SimulationRunnerConfig:
        return False
    if not config.v4_capability_flags.science:
        return False
    if not config.capability_flags.predictive_world_model:
        return False
    if config.bounded_experimentation is None:
        return False
    if config.stop_policy.max_ticks > MAX_DIFFUSION_TICKS:
        return False
    return True


def _bounds_ok(runner: SimulationRunner, inventory: ObjectiveFacts) -> bool:
    if len(inventory.registrations) > MAX_DIFFUSION_OWNERS:
        return False
    if len(runner.engine.export_events().events) > MAX_DIFFUSION_EVENTS:
        return False
    return True


def _lane_state(states: tuple[str, ...]) -> LaneCoverageState:
    if not states or all(value == "unavailable" for value in states):
        return LaneCoverageState.UNAVAILABLE
    if any(value != "complete" for value in states):
        return LaneCoverageState.PARTIAL
    return LaneCoverageState.COMPLETE


def _coverage(
    samples: tuple[ScienceBoundarySample, ...],
    carrier_states: tuple[tuple[str, str, str], ...],
    end_tick: int,
) -> tuple[LaneCoverage, ...]:
    end = end_tick if end_tick > 0 else 1
    if not samples:
        state = LaneCoverageState.UNAVAILABLE
        reason: DiffusionReason | None = DiffusionReason.COVERAGE_GAP
    elif all(
        row.science_state is LaneCoverageState.UNAVAILABLE for row in samples
    ):
        state = LaneCoverageState.UNAVAILABLE
        reason = DiffusionReason.COVERAGE_GAP
    elif any(
        row.science_state is not LaneCoverageState.COMPLETE for row in samples
    ):
        state = LaneCoverageState.PARTIAL
        reason = DiffusionReason.COVERAGE_GAP
    else:
        state = LaneCoverageState.COMPLETE
        reason = None
    observed = sum(len(row.versions) for row in samples)
    rows: list[LaneCoverage] = [
        LaneCoverage(
            lane=DiffusionLane.SCIENCE,
            start_tick=0,
            end_tick_exclusive=end,
            state=state,
            observed=observed,
            reason=reason,
        )
    ]
    channel_states = {
        DiffusionLane.SPEECH: tuple(item[0] for item in carrier_states),
        DiffusionLane.TEACHING: tuple(item[1] for item in carrier_states),
        DiffusionLane.RECORDS: tuple(item[2] for item in carrier_states),
    }
    for lane in DiffusionLane:
        if lane is DiffusionLane.SCIENCE:
            continue
        if lane in channel_states:
            lane_state = _lane_state(channel_states[lane])
        else:
            lane_state = LaneCoverageState.UNAVAILABLE
        rows.append(
            LaneCoverage(
                lane=lane,
                start_tick=0,
                end_tick_exclusive=end,
                state=lane_state,
                reason=(
                    None
                    if lane_state is LaneCoverageState.COMPLETE
                    else DiffusionReason.COVERAGE_GAP
                ),
            )
        )
    return tuple(rows)


async def _sample(
    runner: SimulationRunner,
    *,
    observed_boundary: int,
    prior_prefix: CanonicalEventPrefix | None,
    known_versions: tuple[object, ...],
    prior_occurrences: tuple[DiffusionOccurrence, ...] = (),
) -> tuple[
    ScienceBoundarySample,
    CanonicalEventPrefix,
    tuple[DiffusionOccurrence, ...],
    tuple[str, str, str],
]:
    inventory = runner.engine.detached_objective_facts()
    if not _bounds_ok(runner, inventory):
        raise DiffusionError(DiffusionReason.LIMIT_REACHED.value)
    boundary = await runner.export_finalized_research_boundary()
    if type(boundary) is not FinalizedResearchBoundary:
        raise DiffusionError(DiffusionReason.UNSUPPORTED_SCHEMA.value)
    validate_boundary_identity(boundary, inventory, runner.config)
    events = boundary.events
    run_id = boundary.run_id.value
    fingerprint = boundary.config_fingerprint
    if prior_prefix is None:
        prefix = canonical_event_prefix(
            events,
            run_id=run_id,
            config_fingerprint=fingerprint,
            boundary_tick=boundary.boundary_tick.value,
        )
    else:
        prefix = verify_prefix_extension(
            prior_prefix,
            events,
            run_id=run_id,
            config_fingerprint=fingerprint,
            boundary_tick=boundary.boundary_tick.value,
        )
    projection = project_science_versions(
        boundary,
        inventory,
        runner.config,
        known=known_versions,  # type: ignore[arg-type]
        observed_boundary=observed_boundary,
        events=events,
    )
    carriers = project_carrier_occurrences(
        boundary,
        inventory,
        versions=projection.versions,
        observed_boundary=observed_boundary,
        prior_occurrences=prior_occurrences,
    )
    sample = ScienceBoundarySample(
        boundary_tick=boundary.boundary_tick.value,
        boundary_revision=boundary.boundary_revision.value,
        config_fingerprint=fingerprint,
        owner_ids=projection.owner_ids,
        versions=projection.versions,
        artifacts=projection.artifacts,
        science_state=projection.coverage.state,
        science_reason=projection.coverage.reason,
    )
    return (
        sample,
        prefix,
        carriers.occurrences,
        (carriers.speech_state, carriers.teaching_state, carriers.records_state),
    )


async def run_with_science_diffusion_capture(
    runner: SimulationRunner,
    *,
    capture: bool = False,
) -> ScienceDiffusionCaptureResult:
    """Run with explicit finalized-boundary capture; never installs a sink."""

    config = runner.config
    if not capture or not capture_supported(config):
        result = await runner.run()
        _LOG.info(
            "science_diffusion_capture_disabled run_id=%s",
            result.run_id.value,
        )
        return ScienceDiffusionCaptureResult(
            result=result,
            inputs=None,
            samples=(),
            prefix=None,
            status="unavailable",
        )
    if runner.ticks_committed != 0 or runner.engine.tick.value != 0:
        result = await runner.run()
        _LOG.info(
            "science_diffusion_capture_unavailable_stage run_id=%s ticks=%s",
            result.run_id.value,
            result.ticks_committed,
        )
        return ScienceDiffusionCaptureResult(
            result=result,
            inputs=None,
            samples=(),
            prefix=None,
            status="unavailable",
        )
    if len(runner.engine.ordered_registrations) > MAX_DIFFUSION_OWNERS:
        result = await runner.run()
        _LOG.info(
            "science_diffusion_capture_unavailable_owners run_id=%s",
            result.run_id.value,
        )
        return ScienceDiffusionCaptureResult(
            result=result,
            inputs=None,
            samples=(),
            prefix=None,
            status="unavailable",
        )

    await runner.initialize_finalized_boundary()
    accumulator = DiffusionAccumulator(runner.run_id.value)
    known: tuple[object, ...] = ()
    prior_occurrences: tuple[DiffusionOccurrence, ...] = ()
    samples: list[ScienceBoundarySample] = []
    carrier_states: list[tuple[str, str, str]] = []
    prefix: CanonicalEventPrefix | None = None
    status = "captured"
    aborted = False

    try:
        sample, prefix, occurrences, states = await _sample(
            runner,
            observed_boundary=0,
            prior_prefix=None,
            known_versions=known,
        )
        if accumulator.stage(
            StagedDiffusionBoundary(
                boundary_tick=0,
                versions=sample.versions,
                occurrences=occurrences,
            )
        ):
            samples.append(sample)
            carrier_states.append(states)
            known = tuple(item for item in sample.versions)
            prior_occurrences = occurrences
        else:
            status = "captured_sealed"
    except Exception:
        status = "capture_failed"
        _LOG.warning(
            "science_diffusion_capture_failed run_id=%s stage=baseline",
            runner.run_id.value,
        )

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
            and runner.ticks_committed >= config.stop_policy.max_ticks
        ):
            stop_reason = RunnerStopReasonCode.MAX_TICKS
        if status in {"capture_failed", "captured_sealed"} or stop_reason is not None:
            continue
        try:
            sample, prefix, occurrences, states = await _sample(
                runner,
                observed_boundary=runner.ticks_committed,
                prior_prefix=prefix,
                known_versions=known,
                prior_occurrences=prior_occurrences,
            )
            if accumulator.stage(
                StagedDiffusionBoundary(
                    boundary_tick=sample.boundary_tick,
                    versions=sample.versions,
                    occurrences=occurrences,
                )
            ):
                samples.append(sample)
                carrier_states.append(states)
                known = tuple(accumulator.results()[0])
                prior_occurrences = tuple(accumulator.results()[1])
            else:
                status = "captured_sealed"
        except Exception:
            status = "capture_failed"
            _LOG.warning(
                "science_diffusion_capture_failed run_id=%s stage=tick",
                runner.run_id.value,
            )

    result = await runner.finish_run(stop_reason)
    if aborted:
        return ScienceDiffusionCaptureResult(
            result=result,
            inputs=None,
            samples=tuple(samples),
            prefix=prefix,
            status="aborted",
        )
    if status == "captured":
        try:
            if not samples or samples[-1].boundary_tick != result.ticks_committed:
                sample, prefix, occurrences, states = await _sample(
                    runner,
                    observed_boundary=result.ticks_committed,
                    prior_prefix=prefix,
                    known_versions=known,
                    prior_occurrences=prior_occurrences,
                )
                if accumulator.stage(
                    StagedDiffusionBoundary(
                        boundary_tick=sample.boundary_tick,
                        versions=sample.versions,
                        occurrences=occurrences,
                    )
                ):
                    samples.append(sample)
                    carrier_states.append(states)
                else:
                    status = "captured_sealed"
        except Exception:
            status = "capture_failed"
            _LOG.warning(
                "science_diffusion_capture_failed run_id=%s stage=terminal",
                result.run_id.value,
            )
    if status == "capture_failed":
        return ScienceDiffusionCaptureResult(
            result=result,
            inputs=None,
            samples=tuple(samples),
            prefix=prefix,
            status=status,
        )
    accumulator.add_coverage(
        _coverage(
            tuple(samples), tuple(carrier_states), result.ticks_committed
        )
    )
    versions, occurrences, coverage = accumulator.results()
    inputs = DiffusionInputs(
        run_id=runner.run_id.value,
        versions=versions,
        occurrences=occurrences,
        coverage=coverage,
    )
    if accumulator.sealed is not None:
        status = "captured_sealed"
    _LOG.info(
        "science_diffusion_capture_complete run_id=%s boundaries=%s versions=%s",
        result.run_id.value,
        len(samples),
        len(versions),
    )
    return ScienceDiffusionCaptureResult(
        result=result,
        inputs=inputs,
        samples=tuple(samples),
        prefix=prefix,
        status=status,
    )
