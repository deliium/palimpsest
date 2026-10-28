"""Stepped generational execution with isolated boundary observation.

The stepped helper mirrors ``SimulationRunner.run`` exactly (same stop selectors,
one ``finish_run``) and only adds read-only boundary callbacks. Observer failures
are isolated into benchmark receipts; they never change scientific execution.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

from experiments.civilization_benchmark_evidence import (
    BenchmarkBoundaryProbe,
    blank_slate_check,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionKind,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    get_v3_benchmark_scenario,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerAttemptReceipt,
    RunnerAttemptStatus,
    RunnerStopReasonCode,
    SimulationRunnerResult,
    runner_stop_is_failure,
)

if TYPE_CHECKING:
    from experiments.coordinator import ExperimentAssignment
    from experiments.generational_execution import GenerationalExecutionContext

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_execution"
)

BoundaryObserver = Callable[
    [SimulationRunner, RunnerAttemptReceipt | None], Awaitable[None]
]


class CivilizationBenchmarkExecutionError(RuntimeError):
    """Fail-closed benchmark execution error with a stable code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SteppedBenchmarkExecution:
    """Result plus per-boundary receipts and isolated probe failures."""

    result: SimulationRunnerResult
    attempt_receipts: tuple[RunnerAttemptReceipt, ...]
    probe_failures: tuple[str, ...]


async def _notify(
    runner: SimulationRunner,
    receipt: RunnerAttemptReceipt | None,
    observer: BoundaryObserver | None,
    failures: list[str],
) -> None:
    if observer is None:
        return
    label = "initialized" if receipt is None else f"tick:{receipt.tick}"
    try:
        await observer(runner, receipt)
    except Exception:
        failures.append(label)
        _LOG.warning(
            "benchmark_boundary_probe_unavailable run_id=%s boundary=%s "
            "reason_code=%s",
            runner.run_id.value,
            label,
            "probe_unavailable",
        )


async def execute_stepped_benchmark_runner(
    runner: SimulationRunner,
    *,
    boundary_observer: BoundaryObserver | None = None,
) -> SteppedBenchmarkExecution:
    """Run one initialized boundary through a stepped, stop-equivalent loop."""
    if type(runner) is not SimulationRunner:
        raise CivilizationBenchmarkExecutionError("runner_required")
    failures: list[str] = []
    await runner.initialize_finalized_boundary()
    await _notify(runner, None, boundary_observer, failures)
    receipts: list[RunnerAttemptReceipt] = []
    stop_reason: RunnerStopReasonCode | None = None
    while stop_reason is None:
        receipt = await runner.run_tick()
        receipts.append(receipt)
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
            and runner.ticks_committed >= runner.config.stop_policy.max_ticks
        ):
            stop_reason = RunnerStopReasonCode.MAX_TICKS
        # The tick is fully finalized; observe before the next tick or finish.
        await _notify(runner, receipt, boundary_observer, failures)
    assert stop_reason is not None
    result = await runner.finish_run(stop_reason)
    _LOG.info(
        "benchmark_stepped_run_finished run_id=%s ticks_committed=%s "
        "stop_reason=%s probe_failure_count=%s",
        runner.run_id.value,
        result.ticks_committed,
        result.stop_reason.value,
        len(failures),
    )
    return SteppedBenchmarkExecution(
        result=result,
        attempt_receipts=tuple(receipts),
        probe_failures=tuple(failures),
    )


@dataclass(frozen=True, slots=True)
class CivilizationBenchmarkRecipe:
    """Closed per-attempt benchmark descriptor (no arbitrary callbacks or JSON)."""

    scenario_id: str
    lane: V3BenchmarkLane
    profile: V3BenchmarkProfile
    seed: int
    arm_id: str
    command_plan_id: str | None = None
    command_plan_version: str | None = None

    def __post_init__(self) -> None:
        spec = get_v3_benchmark_scenario(self.scenario_id)
        if type(self.lane) is not V3BenchmarkLane:
            raise V3BenchmarkError("unsupported_lane", "lane must be known")
        if self.lane not in spec.lanes:
            raise V3BenchmarkError(
                "unsupported_lane", "lane is not declared by the scenario"
            )
        if type(self.profile) is not V3BenchmarkProfile:
            raise V3BenchmarkError("invalid_profile", "profile must be known")
        if type(self.seed) is not int or isinstance(self.seed, bool):
            raise V3BenchmarkError("invalid_seed", "seed must be an int")
        if type(self.arm_id) is not str or not self.arm_id:
            raise V3BenchmarkError("invalid_arm", "arm_id must be non-empty str")
        grouped = spec.recipe.arm_count > 1
        if grouped:
            if self.command_plan_id is None or self.command_plan_version is None:
                raise V3BenchmarkError(
                    "recipe_descriptor_mismatch",
                    "grouped cases require a declared command plan",
                )
        elif (
            self.command_plan_id is not None
            or self.command_plan_version is not None
        ):
            raise V3BenchmarkError(
                "recipe_descriptor_mismatch",
                "independent research lanes are unassisted",
            )


@dataclass(frozen=True, slots=True)
class CivilizationBenchmarkContext:
    """Injected outer context for one benchmark attempt."""

    assignment: ExperimentAssignment | None = None
    execution_context: GenerationalExecutionContext | None = None
    probe: BenchmarkBoundaryProbe | None = None
    grouped_runner: (
        Callable[
            [CivilizationBenchmarkRecipe, CivilizationBenchmarkContext],
            Awaitable[V3BenchmarkRunResult],
        ]
        | None
    ) = None
    publication_receipts: tuple[object, ...] = ()
    comparison_id: str | None = None


def _required_checks(
    recipe: CivilizationBenchmarkRecipe,
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
) -> tuple[V3BenchmarkCheck, ...]:
    spec = get_v3_benchmark_scenario(recipe.scenario_id)
    checks: list[V3BenchmarkCheck] = []
    for selector in spec.evidence_selectors:
        if not selector.required:
            continue
        if selector.selector_id == "new_agent_initialization_evidence":
            checks.append(
                blank_slate_check(probe, boundary_end_tick=boundary_end_tick)
            )
        elif selector.selector_id == "objective_event_journal":
            from experiments.civilization_benchmark_evidence import (
                evaluate_event_journal,
            )

            checks.append(evaluate_event_journal(probe))
        else:
            observations = probe.observations
            checks.append(
                V3BenchmarkCheck(
                    selector_id=selector.selector_id,
                    selector_version=selector.selector_version,
                    status=V3BenchmarkCheckStatus.UNEXECUTED,
                    reason_code="selector_evaluator_unavailable",
                    evidence=(
                        V3BenchmarkEvidenceAvailability.PARTIAL
                        if observations
                        else V3BenchmarkEvidenceAvailability.UNAVAILABLE
                    ),
                    coverage=(
                        V3BenchmarkCoverage.EXERCISED
                        if observations
                        else V3BenchmarkCoverage.NOT_EXERCISED
                    ),
                    source_references=(),
                    boundary_start_tick=0,
                    boundary_end_tick=boundary_end_tick,
                )
            )
    return tuple(checks)


def _execution_status(result: SimulationRunnerResult) -> V3BenchmarkExecutionStatus:
    if runner_stop_is_failure(result.stop_reason):
        return V3BenchmarkExecutionStatus.FAILED
    return V3BenchmarkExecutionStatus.COMPLETED


async def execute_civilization_benchmark(
    recipe: CivilizationBenchmarkRecipe,
    context: CivilizationBenchmarkContext,
) -> V3BenchmarkRunResult:
    """Execute one independent or grouped benchmark attempt."""
    spec = get_v3_benchmark_scenario(recipe.scenario_id)
    grouped = spec.execution_kind is V3BenchmarkExecutionKind.GROUPED
    if grouped:
        if context.grouped_runner is None:
            raise CivilizationBenchmarkExecutionError(
                "grouped_executor_required"
            )
        result = await context.grouped_runner(recipe, context)
        if type(result) is not V3BenchmarkRunResult:
            raise CivilizationBenchmarkExecutionError("grouped_result_invalid")
        if result.scenario_id != recipe.scenario_id:
            raise CivilizationBenchmarkExecutionError("grouped_result_mismatch")
        return result
    if recipe.command_plan_id is not None:
        raise CivilizationBenchmarkExecutionError(
            "independent_lane_forbids_command_plan"
        )
    if (
        context.assignment is None
        or context.execution_context is None
        or context.probe is None
    ):
        raise CivilizationBenchmarkExecutionError("execution_context_required")
    from experiments.generational_execution import execute_generational_assignment

    execution_context = replace(
        context.execution_context, boundary_observer=context.probe
    )
    arm = await execute_generational_assignment(context.assignment, execution_context)
    runner_result = arm.runner_result
    horizon = context.assignment.runner_config.stop_policy.max_ticks
    assert horizon is not None
    checks = _required_checks(
        recipe, context.probe, boundary_end_tick=runner_result.ticks_committed
    )
    status = _execution_status(runner_result)
    observations = context.probe.observations
    all_required_pass = bool(checks) and all(
        check.status is V3BenchmarkCheckStatus.PASS for check in checks
    )
    complete = (
        status is V3BenchmarkExecutionStatus.COMPLETED
        and runner_result.ticks_committed == horizon
        and all_required_pass
    )
    evidence = (
        V3BenchmarkEvidenceAvailability.COMPLETE
        if complete
        else (
            V3BenchmarkEvidenceAvailability.PARTIAL
            if observations
            else V3BenchmarkEvidenceAvailability.UNAVAILABLE
        )
    )
    run_result = V3BenchmarkRunResult(
        scenario_id=recipe.scenario_id,
        lane=recipe.lane,
        execution_status=status,
        declared_horizon=horizon,
        ticks_committed=runner_result.ticks_committed,
        coverage=(
            V3BenchmarkCoverage.EXERCISED
            if observations
            else V3BenchmarkCoverage.NOT_EXERCISED
        ),
        evidence=evidence,
        phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
        checks=checks,
        publication_status=(
            "published" if context.publication_receipts else "not_requested"
        ),
        comparison_id=context.comparison_id,
    )
    _LOG.info(
        "benchmark_attempt_executed scenario_id=%s lane=%s status=%s "
        "ticks_committed=%s declared_horizon=%s evidence=%s check_count=%s",
        run_result.scenario_id,
        run_result.lane.value,
        run_result.execution_status.value,
        run_result.ticks_committed,
        run_result.declared_horizon,
        run_result.evidence.value,
        len(checks),
    )
    return run_result


__all__ = [
    "BoundaryObserver",
    "CivilizationBenchmarkContext",
    "CivilizationBenchmarkExecutionError",
    "CivilizationBenchmarkRecipe",
    "SteppedBenchmarkExecution",
    "execute_civilization_benchmark",
    "execute_stepped_benchmark_runner",
]
