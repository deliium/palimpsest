"""Grouped benchmark adapters for cases 29-30 (sealed historical forks).

Both cases execute the genuine common-prefix protocol from Experiment BN: one
parent prefix is sealed, independent children continue through normal
admission, and no child may rewrite the parent. Positive divergence is not a
gate; the retained evidence only records what happened.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_base import V3_BENCHMARK_PROFILE_BUDGETS
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_29_FOUNDER_CONTINGENCY,
    V3_BENCH_30_MULTIGENERATION_FORK,
)
from experiments.path_dependence_models import (
    ArmRole,
    CommonSetupCommand,
    ForkTickSchedule,
    GiveInterventionAction,
    OutcomeDomain,
    OutcomeSelector,
    OutcomeWindow,
    PathDependenceArm,
    PathDependenceSpec,
    ProtocolContrast,
    ScheduledCommandIntervention,
    WaitInterventionAction,
)
from experiments.path_dependence_runner import (
    BranchExecutionResult,
    PathDependenceBatchRunner,
    PathDependenceExecutionContext,
    PathDependenceExecutionSummary,
)
from experiments.path_dependence_scenario import (
    RECIPIENT_BODY_ID,
    RESERVED_FOOD_ID,
    historical_contingency_scenario,
)
from simulation.branch_service import rematerialize_snapshot
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.fork_checkpoint import RunnerForkCheckpoint
from simulation.generational_models import GenerationalRunSpec
from simulation.models import RunId
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    default_new_agent_initialization_spec,
)
from simulation.persistence import SnapshotId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import (
    PopulationLifecycleSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    default_lifespan_distribution_spec,
)
from world.actions import Wait
from world.identifiers import EntityId
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_forks"
)

FORK_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_29_FOUNDER_CONTINGENCY,
    V3_BENCH_30_MULTIGENERATION_FORK,
)

_FORK_TICKS: Final[dict[str, int]] = {
    V3_BENCH_29_FOUNDER_CONTINGENCY: 4,
    V3_BENCH_30_MULTIGENERATION_FORK: 12,
}
_FAST_COHORT: Final[dict[str, int]] = {
    "entry_interval_ticks": 2,
    "generation_length_ticks": 4,
}
_SELECTOR_DOMAINS: Final[tuple[tuple[str, str], ...]] = (
    ("norms.active_beliefs", "norms"),
    ("norms.belief_persistence", "norms"),
    ("relationships.mean_abs_delta", "relationships"),
    ("institutions.persistent_candidates", "institutions"),
    ("technology.living_retention", "technology"),
    ("narratives.endpoint_persistence", "cultural_narratives"),
    ("inequality.resource_gini", "inequality"),
    ("inequality.resource_theil", "inequality"),
    ("cooperation.applied_rate", "cooperation"),
)

ChildHook = Callable[[object, object], Awaitable[None]]


def _learner_initializer() -> object:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    )


def _lifecycle(
    config: SimulationRunnerConfig, scenario_id: str
) -> PopulationLifecycleSpec:
    budget = V3_BENCHMARK_PROFILE_BUDGETS[V3BenchmarkProfile.SMOKE]
    fast = _FAST_COHORT if scenario_id == V3_BENCH_30_MULTIGENERATION_FORK else {}
    interval = fast.get("entry_interval_ticks", budget.entry_interval_ticks)
    generation = fast.get("generation_length_ticks", budget.generation_length_ticks)
    spawns = tuple(location.entity_id.value for location in config.scenario.locations)
    return PopulationLifecycleSpec(
        lifespan_ticks=budget.lifespan_ticks,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 6),
            LifecycleStageThreshold(
                LifecycleStageId("adult"), budget.lifespan_ticks - 1
            ),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": interval,
            "entries_per_interval": 1,
            "generation_length_ticks": generation,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "spawn_location_ids": list(spawns),
        },
        max_population=budget.max_population,
        natural_death_on_lifespan=True,
        lifespan_distribution=default_lifespan_distribution_spec(),
    )


def _arms(scenario_id: str, fork_tick: Tick) -> tuple[PathDependenceArm, ...]:
    founder = _founder_agent()
    food = _food_entity()
    recipient = _recipient_entity()
    return (
        PathDependenceArm(
            arm_id="share",
            label_code="SHARE",
            role=ArmRole.TREATMENT,
            schedule_by_fork_tick=(
                ForkTickSchedule(
                    fork_tick,
                    (
                        ScheduledCommandIntervention(
                            "share-food",
                            founder,
                            fork_tick,
                            GiveInterventionAction(food, recipient),
                        ),
                    ),
                ),
            ),
        ),
        PathDependenceArm(
            arm_id="withhold",
            label_code="WITHHOLD",
            role=ArmRole.CONTROL,
            schedule_by_fork_tick=(
                ForkTickSchedule(
                    fork_tick,
                    (
                        ScheduledCommandIntervention(
                            "withhold-food",
                            founder,
                            fork_tick,
                            WaitInterventionAction(),
                        ),
                    ),
                ),
            ),
        ),
    )


def _founder_agent() -> AgentId:
    return AgentId("agent-origin")


def _recipient_entity() -> EntityId:
    return EntityId(RECIPIENT_BODY_ID)


def _food_entity() -> EntityId:
    return EntityId(RESERVED_FOOD_ID)


def build_fork_benchmark_spec(
    scenario_id: str,
    *,
    seed: int,
    profile: V3BenchmarkProfile,
) -> PathDependenceSpec:
    """Materialize one predeclared grouped case without testing outcomes."""
    if scenario_id not in FORK_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a fork benchmark: {scenario_id!r}"
        )
    if type(seed) is not int or isinstance(seed, bool):
        raise V3BenchmarkError("invalid_seed", "seed must be an int")
    budget = V3_BENCHMARK_PROFILE_BUDGETS[profile]
    horizon = budget.horizon_ticks
    fork_tick = Tick(_FORK_TICKS[scenario_id])
    if fork_tick.value >= horizon:
        raise V3BenchmarkError("invalid_fork_window", "fork must precede the horizon")
    template = historical_contingency_scenario(seed=seed, profile="smoke")
    config = replace(
        template.base,
        stop_policy=RunnerStopPolicy(
            max_ticks=horizon, stop_on_all_agents_terminal=False
        ),
        population_lifecycle=_lifecycle(template.base, scenario_id),
        new_agent_initialization=_learner_initializer(),  # type: ignore[arg-type]
        generational_run=GenerationalRunSpec(
            max_generation_index=None,
            stop_on_extinction=False,
            population_threshold=None,
            experiment_criteria=(),
            criterion_cadence_ticks=1,
        ),
    )
    actors = (_founder_agent(), _spring_agent())
    setup = tuple(
        CommonSetupCommand(actor_id=actor, tick=Tick(tick), command=Wait())
        for actor in actors
        for tick in range(fork_tick.value)
    )
    spec = PathDependenceSpec(
        base=config,
        seeds=(seed,),
        replicates_per_seed=1,
        fork_ticks=(fork_tick,),
        horizon_tick=Tick(horizon),
        arms=_arms(scenario_id, fork_tick),
        contrasts=(ProtocolContrast("share-vs-withhold", "withhold", "share"),),
        windows=(OutcomeWindow("post-fork", fork_tick, fork_tick, Tick(horizon)),),
        selectors=tuple(
            OutcomeSelector(
                selector_id=selector_id,
                domain=OutcomeDomain(domain),
                window_id="post-fork",
            )
            for selector_id, domain in _SELECTOR_DOMAINS
        ),
        assignment_seed=seed + 1,
        common_setup=setup,
        max_interventions_per_arm=4,
    )
    assert_fork_benchmark_design(spec, scenario_id=scenario_id, profile=profile)
    _LOG.info(
        "fork_benchmark_spec_built scenario_id=%s seed=%s horizon=%s fork=%s",
        scenario_id,
        seed,
        horizon,
        fork_tick.value,
    )
    return spec


def _spring_agent() -> AgentId:
    return AgentId("agent-spring")


def assert_fork_benchmark_design(
    spec: PathDependenceSpec,
    *,
    scenario_id: str,
    profile: V3BenchmarkProfile,
) -> None:
    """Fail closed on inherited stops, misaligned windows or weak prefixes."""
    if type(spec) is not PathDependenceSpec:
        raise V3BenchmarkError("invalid_spec", "spec must be PathDependenceSpec")
    budget = V3_BENCHMARK_PROFILE_BUDGETS[profile]
    expected_horizon = budget.horizon_ticks
    expected_fork = _FORK_TICKS[scenario_id]
    if spec.horizon_tick.value != expected_horizon:
        raise V3BenchmarkError(
            "horizon_mismatch", "grouped horizon must equal the declared budget"
        )
    if spec.base.stop_policy.max_ticks != expected_horizon:
        raise V3BenchmarkError(
            "horizon_mismatch", "base stop policy must equal the grouped horizon"
        )
    if spec.base.stop_policy.stop_on_all_agents_terminal:
        raise V3BenchmarkError(
            "runtime_terminal_stop_enabled", "grouped bases disable terminal stops"
        )
    run = spec.base.generational_run
    if run is None:
        raise V3BenchmarkError("missing_generational_run", "grouped base needs v55")
    if (
        run.max_generation_index is not None
        or run.stop_on_extinction
        or run.population_threshold is not None
        or run.experiment_criteria
    ):
        raise V3BenchmarkError(
            "competing_stop_enabled", "grouped runs disable competing stop selectors"
        )
    if spec.base.new_agent_initialization is None or (
        spec.base.new_agent_initialization.species_defaults_id
        != SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1
    ):
        raise V3BenchmarkError(
            "learner_profile_required",
            "grouped runs use the content-empty learner pack",
        )
    if spec.fork_ticks != (Tick(expected_fork),):
        raise V3BenchmarkError("invalid_fork_window", "unexpected fork tick")
    for window in spec.windows:
        if (
            window.window_id != "post-fork"
            or window.start_tick.value != expected_fork
            or window.end_tick.value != expected_horizon
        ):
            raise V3BenchmarkError(
                "window_mismatch", "post-fork windows must align with F/H"
            )
    coverage = {
        (command.actor_id.value, command.tick.value) for command in spec.common_setup
    }
    for actor in ("agent-origin", "agent-spring"):
        for tick in range(expected_fork):
            if (actor, tick) not in coverage:
                raise V3BenchmarkError(
                    "prefix_control_gap", "every pre-fork tick needs a declared Wait"
                )
    if scenario_id == V3_BENCH_30_MULTIGENERATION_FORK:
        lifecycle = spec.base.population_lifecycle
        assert lifecycle is not None
        params = dict(lifecycle.demographic_policy_params)
        if (
            params.get("interval_ticks") != 2
            or params.get("generation_length_ticks") != 4
        ):
            raise V3BenchmarkError(
                "fast_cohort_mismatch", "case 30 declares faster cohort labels"
            )


async def _materialize_engine(
    checkpoint: RunnerForkCheckpoint, child_run: RunId
) -> WorldEngine:
    snapshot = rematerialize_snapshot(
        checkpoint.snapshot,
        child_run_id=child_run,
        snapshot_id=SnapshotId(f"child-{child_run.value}"),
        predecessor_commit_hash=None,
        next_tick=Tick(checkpoint.boundary_tick.value),
    )
    config = checkpoint.config
    return WorldEngine.restore_from_snapshot(
        snapshot,
        population_lifecycle=config.population_lifecycle,
        new_agent_initialization=config.new_agent_initialization,
        kinship_spec=config.kinship,
        environmental_dynamics=config.environmental_dynamics,
        artifacts_enabled=config.artifacts_enabled,
    )


def _source_ref(child: BranchExecutionResult) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
        reference_id=child.child_run_id,
        tick=child.ticks_committed,
    )


def _child_at_horizon(child: BranchExecutionResult, horizon: int) -> bool:
    return child.status == "completed" and child.ticks_committed == horizon


def _fork_checks(
    summary: PathDependenceExecutionSummary,
    *,
    horizon: int,
    selector_id: str,
) -> V3BenchmarkCheck:
    prefixes = summary.prefixes
    if not prefixes:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_grouped_prefix_observed",
            evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
        )
    children = tuple(child for prefix in prefixes for child in prefix.child_results)
    eligible = all(prefix.eligible for prefix in prefixes)
    parent_unchanged = all(prefix.parent_unchanged for prefix in prefixes)
    complete = bool(children) and all(
        _child_at_horizon(child, horizon) for child in children
    )
    sources = tuple(_source_ref(child) for child in children)
    if not eligible:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="prefix_ineligible",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=horizon,
            numerator=0,
            denominator=len(children),
        )
    if not parent_unchanged:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.FAIL,
            reason_code="parent_prefix_mutated",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=horizon,
            numerator=0,
            denominator=len(children),
        )
    if not complete:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="child_horizon_incomplete",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=horizon,
            numerator=sum(1 for child in children if _child_at_horizon(child, horizon)),
            denominator=max(len(children), 1),
        )
    ranked = sum(
        1
        for child in children
        if any(entry.status.value == "committed" for entry in child.treatment_ledger)
    )
    if ranked < 1:
        return V3BenchmarkCheck(
            selector_id=selector_id,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_treatment_receipt_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=sources,
            boundary_start_tick=0,
            boundary_end_tick=horizon,
            numerator=0,
            denominator=max(len(children), 1),
        )
    return V3BenchmarkCheck(
        selector_id=selector_id,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code="grouped_continuation_observed",
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=sources,
        boundary_start_tick=0,
        boundary_end_tick=horizon,
        numerator=len(children),
        denominator=len(children),
    )


async def execute_grouped_benchmark(
    scenario_id: str,
    *,
    lane: V3BenchmarkLane,
    profile: V3BenchmarkProfile,
    seed: int,
    child_installer: ChildHook | None = None,
    child_finalizer: ChildHook | None = None,
    factories: RunnerDependencyFactories | None = None,
    source_identity: str = "unspecified",
) -> V3BenchmarkRunResult:
    """Run the genuine shared-prefix protocol for one grouped case."""
    if scenario_id not in FORK_BENCHMARK_IDS:
        raise V3BenchmarkError("unknown_scenario", "not a grouped benchmark")
    spec = build_fork_benchmark_spec(scenario_id, seed=seed, profile=profile)
    context = PathDependenceExecutionContext(
        factories=factories or RunnerDependencyFactories(),
        materialize_engine=_materialize_engine,
        child_installer=child_installer,
        child_finalizer=child_finalizer,
        source_identity=source_identity,
    )
    summary = await PathDependenceBatchRunner().run(spec, context)
    horizon = spec.horizon_tick.value
    checks = (
        _fork_checks(
            summary, horizon=horizon, selector_id="path_dependence_outcome_evidence"
        ),
        _fork_checks(summary, horizon=horizon, selector_id="objective_event_journal"),
    )
    children = tuple(
        child for prefix in summary.prefixes for child in prefix.child_results
    )
    completed = bool(children) and all(
        _child_at_horizon(child, horizon) for child in children
    )
    status = (
        V3BenchmarkExecutionStatus.COMPLETED
        if completed
        else V3BenchmarkExecutionStatus.FAILED
    )
    evidence = (
        V3BenchmarkEvidenceAvailability.COMPLETE
        if completed
        and all(check.status is V3BenchmarkCheckStatus.PASS for check in checks)
        else V3BenchmarkEvidenceAvailability.PARTIAL
    )
    _LOG.info(
        "grouped_benchmark_executed scenario_id=%s lane=%s seeds=%s children=%s "
        "completed=%s evidence=%s",
        scenario_id,
        lane.value,
        len(spec.seeds),
        len(children),
        completed,
        evidence.value,
    )
    return V3BenchmarkRunResult(
        scenario_id=scenario_id,
        lane=lane,
        execution_status=status,
        declared_horizon=horizon,
        ticks_committed=horizon if completed else 0,
        coverage=(
            V3BenchmarkCoverage.EXERCISED
            if children
            else V3BenchmarkCoverage.NOT_EXERCISED
        ),
        evidence=evidence,
        phenomenon=V3BenchmarkPhenomenon.UNKNOWN,
        checks=checks,
    )


__all__ = [
    "FORK_BENCHMARK_IDS",
    "assert_fork_benchmark_design",
    "build_fork_benchmark_spec",
    "execute_grouped_benchmark",
]
