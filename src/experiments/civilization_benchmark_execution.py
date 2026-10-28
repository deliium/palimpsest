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
    evaluate_cultural_mutation,
    evaluate_dependency_care,
    evaluate_developmental_teaching,
    evaluate_durable_records,
    evaluate_historical_memory,
    evaluate_population_lifecycle,
    evaluate_required_actions,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionKind,
    V3BenchmarkExecutionStatus,
    V3BenchmarkInterventionReceipt,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_09_TECHNOLOGY_DIFFUSION,
    V3_BENCH_20_RECONTACT_EXCHANGE,
    get_v3_benchmark_scenario,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RunnerAttemptReceipt,
    RunnerAttemptStatus,
    RunnerStopReasonCode,
    SimulationRunnerConfig,
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
            "benchmark_boundary_probe_unavailable run_id=%s boundary=%s reason_code=%s",
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
    final_receipt: RunnerAttemptReceipt | None = None
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
        if stop_reason is None:
            # The tick is fully finalized; observe before the next tick.
            await _notify(runner, receipt, boundary_observer, failures)
        else:
            # Terminal boundaries are inspectable only after finish_run.
            final_receipt = receipt
    assert stop_reason is not None
    result = await runner.finish_run(stop_reason)
    if final_receipt is not None:
        await _notify(runner, final_receipt, boundary_observer, failures)
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
        elif self.command_plan_id is not None or self.command_plan_version is not None:
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
    arbiter: object | None = None
    required_milestone_ids: tuple[str, ...] = ()
    grouped_runner: (
        Callable[
            [CivilizationBenchmarkRecipe, CivilizationBenchmarkContext],
            Awaitable[V3BenchmarkRunResult],
        ]
        | None
    ) = None
    publication_receipts: tuple[object, ...] = ()
    comparison_id: str | None = None


def _learner_profile_available(
    config: SimulationRunnerConfig,
) -> bool:
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
        SPECIES_DEFAULT_DEVELOPMENTAL_V1,
    )

    initialization = config.new_agent_initialization
    return initialization is not None and initialization.species_defaults_id in {
        SPECIES_DEFAULT_DEVELOPMENTAL_V1,
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    }


def _required_checks(
    recipe: CivilizationBenchmarkRecipe,
    probe: BenchmarkBoundaryProbe,
    *,
    config: SimulationRunnerConfig,
    result: SimulationRunnerResult,
    boundary_end_tick: int,
) -> tuple[V3BenchmarkCheck, ...]:
    spec = get_v3_benchmark_scenario(recipe.scenario_id)
    checks: list[V3BenchmarkCheck] = []
    for selector in spec.evidence_selectors:
        if not selector.required:
            continue
        if selector.selector_id == "new_agent_initialization_evidence":
            checks.append(blank_slate_check(probe, boundary_end_tick=boundary_end_tick))
        elif selector.selector_id == "objective_event_journal":
            from experiments.civilization_benchmark_evidence import (
                evaluate_event_journal,
            )

            checks.append(evaluate_event_journal(probe))
        elif selector.selector_id == "population_lifecycle_evidence":
            checks.append(
                evaluate_population_lifecycle(
                    probe, boundary_end_tick=boundary_end_tick
                )
            )
        elif selector.selector_id == "dependency_care_evidence":
            checks.append(
                evaluate_dependency_care(probe, boundary_end_tick=boundary_end_tick)
            )
        elif selector.selector_id in {
            "mentorship_evidence",
            "developmental_learning_evidence",
        }:
            checks.append(
                evaluate_developmental_teaching(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    selector_id=selector.selector_id,
                    mechanism_available=_learner_profile_available(config),
                )
            )
        elif selector.selector_id == "historical_memory_evidence":
            checks.append(
                evaluate_historical_memory(probe, boundary_end_tick=boundary_end_tick)
            )
        elif selector.selector_id == "durable_record_evidence":
            checks.append(
                evaluate_durable_records(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.durable_records is not None,
                )
            )
        elif selector.selector_id == "cultural_feature_evidence":
            checks.append(
                evaluate_cultural_mutation(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=(
                        config.cultural_feature_provenance is not None
                    ),
                )
            )
        elif selector.selector_id == "knowledge_genealogy_evidence":
            from experiments.civilization_benchmark_technology import (
                evaluate_knowledge_genealogy,
            )

            checks.append(
                evaluate_knowledge_genealogy(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.knowledge_genealogy is not None,
                    require_transmission=recipe.scenario_id
                    in {
                        V3_BENCH_09_TECHNOLOGY_DIFFUSION,
                        V3_BENCH_20_RECONTACT_EXCHANGE,
                    },
                )
            )
        elif selector.selector_id == "technique_lifecycle_evidence":
            from experiments.civilization_benchmark_technology import (
                evaluate_technique_lifecycle,
            )

            checks.append(
                evaluate_technique_lifecycle(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    spec=config.technique_lifecycle,
                )
            )
        elif selector.selector_id == "possession_succession_evidence":
            from experiments.civilization_benchmark_exchange import (
                evaluate_possession_succession,
            )

            checks.append(
                evaluate_possession_succession(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.possession_succession is not None,
                )
            )
        elif selector.selector_id == "commitment_evidence":
            from experiments.civilization_benchmark_exchange import (
                evaluate_commitments,
            )

            checks.append(
                evaluate_commitments(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.structured_commitments is not None,
                )
            )
        elif selector.selector_id == "subjective_exchange_evidence":
            from experiments.civilization_benchmark_exchange import (
                evaluate_subjective_exchange,
            )

            checks.append(
                evaluate_subjective_exchange(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.subjective_valuation is not None,
                )
            )
        elif selector.selector_id == "symbolic_language_evidence":
            from experiments.civilization_benchmark_language import (
                evaluate_symbolic_language,
            )

            checks.append(
                evaluate_symbolic_language(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.symbolic_language_mode.value == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "semantic_drift_evidence":
            from experiments.civilization_benchmark_language import (
                evaluate_semantic_drift,
            )

            checks.append(
                evaluate_semantic_drift(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.semantic_naming_mode.value == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "translation_evidence":
            from experiments.civilization_benchmark_language import (
                evaluate_translation,
            )

            checks.append(
                evaluate_translation(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.translation_mode.value == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "collective_project_evidence":
            from experiments.civilization_benchmark_coordination import (
                evaluate_collective_projects,
            )

            checks.append(
                evaluate_collective_projects(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.collective_projects is not None,
                )
            )
        elif selector.selector_id == "public_goods_evidence":
            from experiments.civilization_benchmark_coordination import (
                evaluate_public_goods,
            )

            checks.append(
                evaluate_public_goods(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.public_goods is not None,
                )
            )
        elif selector.selector_id == "migration_evidence":
            from experiments.civilization_benchmark_regions import (
                evaluate_migration,
            )

            checks.append(
                evaluate_migration(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.regions_migration is not None,
                )
            )
        elif selector.selector_id == "cultural_contact_evidence":
            from experiments.civilization_benchmark_regions import (
                evaluate_cultural_contact,
            )

            checks.append(
                evaluate_cultural_contact(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.cultural_contact is not None,
                )
            )
        elif selector.selector_id == "exchange_function_evidence":
            from experiments.civilization_benchmark_exchange import (
                evaluate_exchange_functions,
            )

            checks.append(
                evaluate_exchange_functions(
                    probe,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=(config.resource_exchange_profile is not None),
                )
            )
        elif selector.selector_id == "generational_narrative_evidence":
            from experiments.civilization_benchmark_institutions import (
                evaluate_generational_narratives,
            )

            checks.append(
                evaluate_generational_narratives(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=config.generational_narratives is not None,
                )
            )
        elif selector.selector_id == "institution_concept_evidence":
            from experiments.civilization_benchmark_institutions import (
                evaluate_institution_concepts,
            )

            checks.append(
                evaluate_institution_concepts(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.institution_concept_mode.value
                        == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "office_succession_evidence":
            from experiments.civilization_benchmark_institutions import (
                evaluate_office_succession,
            )

            checks.append(
                evaluate_office_succession(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.office_succession_mode.value == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "institutional_memory_evidence":
            from experiments.civilization_benchmark_institutions import (
                evaluate_institutional_memory,
            )

            checks.append(
                evaluate_institutional_memory(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.institutional_memory_mode.value
                        == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
        elif selector.selector_id == "institutional_decay_evidence":
            from experiments.civilization_benchmark_institutions import (
                evaluate_institutional_decay,
            )

            checks.append(
                evaluate_institutional_decay(
                    probe,
                    result,
                    boundary_end_tick=boundary_end_tick,
                    mechanism_available=any(
                        agent.cognition.institutional_decay_mode.value
                        == "deterministic"
                        for agent in config.agents
                    ),
                )
            )
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


def _collect_intervention_receipts(
    arbiter: object | None,
) -> tuple[V3BenchmarkInterventionReceipt, ...]:
    if arbiter is None:
        return ()
    records = {
        record.milestone_id: record
        for record in getattr(arbiter, "proposed_versus_effective", ())
    }
    receipts: list[V3BenchmarkInterventionReceipt] = []
    status_lookup = getattr(arbiter, "milestone_status", None)
    for milestone in getattr(arbiter, "milestones", ()):
        milestone_id = milestone.milestone_id
        if status_lookup is None:
            continue
        status = status_lookup(milestone_id)
        record = records.get(milestone_id)
        receipts.append(
            V3BenchmarkInterventionReceipt(
                milestone_id=milestone_id,
                status=getattr(status, "value", str(status)),
                proposed_command_kind=(
                    "none"
                    if record is None
                    else getattr(record, "proposed_command_kind", "none")
                ),
                effective_command_kind=(
                    "none"
                    if record is None
                    else getattr(record, "effective_command_kind", "none")
                ),
                resolution_status=(
                    None
                    if record is None
                    else getattr(record, "resolution_status", None)
                ),
            )
        )
    return tuple(receipts)


async def execute_civilization_benchmark(
    recipe: CivilizationBenchmarkRecipe,
    context: CivilizationBenchmarkContext,
) -> V3BenchmarkRunResult:
    """Execute one independent or grouped benchmark attempt."""
    spec = get_v3_benchmark_scenario(recipe.scenario_id)
    grouped = spec.execution_kind is V3BenchmarkExecutionKind.GROUPED
    if grouped:
        if context.grouped_runner is None:
            raise CivilizationBenchmarkExecutionError("grouped_executor_required")
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
    if context.arbiter is not None:
        base_configurator = execution_context.configurator
        arbiter = context.arbiter

        def _configure(runner: SimulationRunner) -> None:
            runner.set_intervention_arbiter(arbiter)
            if base_configurator is not None:
                base_configurator(runner)

        execution_context = replace(execution_context, configurator=_configure)
    arm = await execute_generational_assignment(context.assignment, execution_context)
    runner_result = arm.runner_result
    horizon = context.assignment.runner_config.stop_policy.max_ticks
    assert horizon is not None
    receipts = _collect_intervention_receipts(context.arbiter)
    checks = _required_checks(
        recipe,
        context.probe,
        config=context.assignment.runner_config,
        result=runner_result,
        boundary_end_tick=runner_result.ticks_committed,
    )
    if context.required_milestone_ids:
        checks = (
            *checks,
            evaluate_required_actions(receipts, context.required_milestone_ids),
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
        intervention_receipts=receipts,
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
