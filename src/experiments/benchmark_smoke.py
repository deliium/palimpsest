"""Network-free smoke helper for V2 benchmark scenarios.

Framework-only until Task 11b: requires an implemented builder, runs a short
tick budget with deterministic fakes, and reports measurable-output availability
without asserting emergence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import Final

from experiments.benchmark_scenarios import (
    BenchmarkBuilderError,
    BenchmarkBuildResult,
    build_benchmark_scenario,
    is_benchmark_builder_implemented,
)
from experiments.benchmark_suite import get_benchmark_scenario
from experiments.collectors import assemble_arm_metric_bundle, collect_for_experiment
from experiments.coordinator import ExperimentArmResult, ExperimentCoordinator
from experiments.models import ExperimentDefinition, ExperimentSeedMatrix
from simulation.runner_models import RunnerStopPolicy, SimulationRunnerConfig
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_smoke")

DEFAULT_SMOKE_TICK_BUDGET: Final[int] = 4
_METRIC_FAMILY_RE: Final[re.Pattern[str]] = re.compile(r"\b([a-z][a-z0-9_]*@\d+)\b")


class BenchmarkSmokeError(ValueError):
    """Fail-closed smoke helper errors with a stable reason code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        detail = message or code
        super().__init__(detail)
        _LOG.error("benchmark_smoke_failed reason_code=%s", code)


@dataclass(frozen=True, slots=True)
class SmokeOutputAvailability:
    """Availability probe for one declared measurable output."""

    measurable_output: str
    status: str
    detail_code: str = ""


@dataclass(frozen=True, slots=True)
class BenchmarkSmokeResult:
    """Structured smoke result — mechanism/availability only, no emergence."""

    scenario_id: str
    ticks: int
    condition_ids: tuple[str, ...]
    metrics_available: tuple[SmokeOutputAvailability, ...]
    arm_count: int
    ran: bool


def smoke_tick_budget(
    scenario_id: str,
    *,
    tick_budget: int = DEFAULT_SMOKE_TICK_BUDGET,
) -> int:
    """Return the effective smoke tick budget for a registered scenario."""
    require_stable_id("scenario_id", scenario_id)
    if type(tick_budget) is not int or isinstance(tick_budget, bool) or tick_budget < 1:
        raise BenchmarkSmokeError("invalid_tick_budget", "tick_budget must be >= 1")
    spec = get_benchmark_scenario(scenario_id)
    return min(tick_budget, spec.max_ticks, DEFAULT_SMOKE_TICK_BUDGET)


def _cap_definition(
    definition: ExperimentDefinition,
    *,
    ticks: int,
) -> ExperimentDefinition:
    capped_conditions = []
    for condition in definition.conditions:
        config = replace(
            condition.runner_config,
            stop_policy=RunnerStopPolicy(max_ticks=ticks),
        )
        capped_conditions.append(replace(condition, runner_config=config))
    first_seed = definition.seed_matrix.seeds[0]
    return replace(
        definition,
        conditions=tuple(capped_conditions),
        seed_matrix=ExperimentSeedMatrix(seeds=(first_seed,), replicates_per_seed=1),
    )


def _probe_outputs(
    *,
    measurable_outputs: tuple[str, ...],
    arms: tuple[ExperimentArmResult, ...],
) -> tuple[SmokeOutputAvailability, ...]:
    family_availability: dict[str, str] = {}
    collector_families: set[str] = set()
    for arm in arms:
        for doc in collect_for_experiment(arm):
            collector_families.add(doc.family)
        bundle = assemble_arm_metric_bundle(arm)
        for metric_doc in bundle.documents:
            family = metric_doc.metric_family
            algo = str(metric_doc.algorithm_version or "")
            keys = {family, f"{family}@1"}
            if "@" in algo:
                keys.add(algo)
            availability = metric_doc.availability.value
            for key in keys:
                prior = family_availability.get(key)
                if prior is None or prior == "absent":
                    family_availability[key] = availability
                elif availability == "present":
                    family_availability[key] = availability

    reports: list[SmokeOutputAvailability] = []
    for output in measurable_outputs:
        families = _METRIC_FAMILY_RE.findall(output)
        if not families:
            reports.append(
                SmokeOutputAvailability(
                    measurable_output=output,
                    status="declared",
                    detail_code="non_metric_token",
                )
            )
            continue
        statuses: list[str] = []
        for family in families:
            bare = family.split("@", 1)[0]
            if family in family_availability:
                statuses.append(family_availability[family])
            elif bare in family_availability:
                statuses.append(family_availability[bare])
            elif bare in collector_families:
                statuses.append("assemblable")
            else:
                statuses.append("absent")
        # Prefer the strongest observed status across tokens.
        if "present" in statuses:
            status = "present"
        elif "partial" in statuses or "assemblable" in statuses:
            status = "assemblable"
        elif "unknown" in statuses:
            status = "unknown"
        else:
            status = "absent"
        reports.append(
            SmokeOutputAvailability(
                measurable_output=output,
                status=status,
                detail_code=",".join(families),
            )
        )
    return tuple(reports)


async def run_benchmark_smoke(
    scenario_id: str,
    base: SimulationRunnerConfig,
    *,
    tick_budget: int = DEFAULT_SMOKE_TICK_BUDGET,
    run_ticks: bool = True,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkSmokeResult:
    """Build and optionally run a short smoke for one implemented scenario."""
    require_stable_id("scenario_id", scenario_id)
    if not is_benchmark_builder_implemented(scenario_id):
        raise BenchmarkSmokeError("builder_not_implemented", scenario_id)
    ticks = smoke_tick_budget(scenario_id, tick_budget=tick_budget)
    try:
        built: BenchmarkBuildResult = build_benchmark_scenario(
            scenario_id,
            base,
            seed_matrix=seed_matrix,
        )
    except BenchmarkBuilderError as exc:
        raise BenchmarkSmokeError(exc.code, str(exc)) from exc

    definition = _cap_definition(built.definition, ticks=ticks)
    condition_ids = tuple(item.condition_id for item in definition.conditions)
    spec = get_benchmark_scenario(scenario_id)

    if not run_ticks:
        reports = tuple(
            SmokeOutputAvailability(
                measurable_output=item,
                status="declared",
                detail_code="run_ticks_false",
            )
            for item in spec.measurable_outputs
        )
        _LOG.info(
            "benchmark_smoke_finished scenario_id=%s ticks=%s metrics_available=%s",
            scenario_id,
            0,
            ",".join(item.status for item in reports),
        )
        return BenchmarkSmokeResult(
            scenario_id=scenario_id,
            ticks=0,
            condition_ids=condition_ids,
            metrics_available=reports,
            arm_count=0,
            ran=False,
        )

    arms = await ExperimentCoordinator(definition).run_all()
    committed = max((arm.runner_result.ticks_committed for arm in arms), default=0)
    reports = _probe_outputs(
        measurable_outputs=spec.measurable_outputs,
        arms=arms,
    )
    available_codes = ",".join(
        f"{item.status}" for item in reports
    )
    _LOG.info(
        "benchmark_smoke_finished scenario_id=%s ticks=%s metrics_available=%s",
        scenario_id,
        committed,
        available_codes,
    )
    return BenchmarkSmokeResult(
        scenario_id=scenario_id,
        ticks=committed,
        condition_ids=condition_ids,
        metrics_available=reports,
        arm_count=len(arms),
        ran=True,
    )
