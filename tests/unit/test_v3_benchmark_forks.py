"""V3 grouped benchmark cases 29-30: sealed prefixes and fork lineage."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import pytest

from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
)
from experiments.civilization_benchmark_forks import (
    FORK_BENCHMARK_IDS,
    assert_fork_benchmark_design,
    build_fork_benchmark_spec,
    execute_grouped_benchmark,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkError,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_29_FOUNDER_CONTINGENCY,
    V3_BENCH_30_MULTIGENERATION_FORK,
)
from experiments.path_dependence_runner import (
    PathDependenceBatchRunner,
    PathDependenceExecutionContext,
)
from simulation.clock import Tick
from simulation.runner import RunnerDependencyFactories


def _materialize(checkpoint: object, child_run: object) -> Any:
    from experiments.civilization_benchmark_forks import _materialize_engine

    return _materialize_engine(checkpoint, child_run)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "profile,horizon",
    [
        (V3BenchmarkProfile.SMOKE, 96),
        (V3BenchmarkProfile.RESEARCH, 192),
    ],
)
def test_grouped_cases_declare_bounded_designs(
    profile: V3BenchmarkProfile, horizon: int
) -> None:
    for scenario_id in FORK_BENCHMARK_IDS:
        spec = build_fork_benchmark_spec(scenario_id, seed=23, profile=profile)
        assert spec.horizon_tick.value == horizon
        assert spec.base.stop_policy.max_ticks == horizon
        assert not spec.base.stop_policy.stop_on_all_agents_terminal
        run = spec.base.generational_run
        assert run is not None
        assert run.max_generation_index is None
        assert run.stop_on_extinction is False
        assert run.population_threshold is None
        assert run.experiment_criteria == ()
        expected_fork = 4 if scenario_id == V3_BENCH_29_FOUNDER_CONTINGENCY else 12
        assert spec.fork_ticks[0].value == expected_fork
        assert spec.windows[0].end_tick.value == horizon
        assert {(c.actor_id.value, c.tick.value) for c in spec.common_setup} >= {
            (actor, tick)
            for actor in ("agent-origin", "agent-spring")
            for tick in range(expected_fork)
        }
        assert_fork_benchmark_design(spec, scenario_id=scenario_id, profile=profile)


def test_case_30_declares_fast_cohort_schedule() -> None:
    spec = build_fork_benchmark_spec(
        V3_BENCH_30_MULTIGENERATION_FORK,
        seed=23,
        profile=V3BenchmarkProfile.SMOKE,
    )
    lifecycle = spec.base.population_lifecycle
    assert lifecycle is not None
    params = dict(lifecycle.demographic_policy_params)
    assert params["interval_ticks"] == 2
    assert params["generation_length_ticks"] == 4
    assert lifecycle.lifespan_ticks == 24


def test_design_rejects_inherited_stops_and_misaligned_windows() -> None:
    scenario_id = V3_BENCH_29_FOUNDER_CONTINGENCY
    spec = build_fork_benchmark_spec(
        scenario_id, seed=23, profile=V3BenchmarkProfile.SMOKE
    )
    assert spec.base.generational_run is not None
    stopped = replace(
        spec,
        base=replace(
            spec.base,
            generational_run=replace(
                spec.base.generational_run, max_generation_index=4
            ),
        ),
    )
    with pytest.raises(V3BenchmarkError):
        assert_fork_benchmark_design(
            stopped, scenario_id=scenario_id, profile=V3BenchmarkProfile.SMOKE
        )
    misaligned = replace(
        spec,
        windows=(
            replace(spec.windows[0], start_tick=Tick(spec.fork_ticks[0].value + 1)),
        ),
    )
    with pytest.raises(V3BenchmarkError):
        assert_fork_benchmark_design(
            misaligned, scenario_id=scenario_id, profile=V3BenchmarkProfile.SMOKE
        )


@pytest.mark.asyncio
async def test_grouped_execution_reaches_horizon_with_receipts() -> None:
    scenario_id = V3_BENCH_29_FOUNDER_CONTINGENCY
    spec = build_fork_benchmark_spec(
        scenario_id, seed=23, profile=V3BenchmarkProfile.SMOKE
    )
    summary = await PathDependenceBatchRunner().run(
        spec,
        PathDependenceExecutionContext(
            factories=RunnerDependencyFactories(),
            materialize_engine=_materialize,
            source_identity="unit-test",
        ),
    )
    assert summary.prefixes
    prefix = summary.prefixes[0]
    assert prefix.eligible is True
    assert prefix.parent_unchanged is True
    assert {child.arm_id for child in prefix.child_results} == {"share", "withhold"}
    assert all(child.ticks_committed == 96 for child in prefix.child_results)
    assert all(child.status == "completed" for child in prefix.child_results)
    assert all(
        any(entry.status.value == "committed" for entry in child.treatment_ledger)
        for child in prefix.child_results
    )
    assert len({child.child_run_id for child in prefix.child_results}) == 2


@pytest.mark.asyncio
async def test_hooks_are_isolated_from_scientific_execution() -> None:
    scenario_id = V3_BENCH_29_FOUNDER_CONTINGENCY
    spec = build_fork_benchmark_spec(
        scenario_id, seed=23, profile=V3BenchmarkProfile.SMOKE
    )
    installed: list[str] = []
    finalized: list[str] = []

    async def install(child: object, slot: object) -> None:
        installed.append(cast(Any, slot).child_run_id)

    async def finalize(child: object, slot: object) -> None:
        finalized.append(cast(Any, slot).child_run_id)
        raise RuntimeError("capture unavailable")

    summary = await PathDependenceBatchRunner().run(
        spec,
        PathDependenceExecutionContext(
            factories=RunnerDependencyFactories(),
            materialize_engine=_materialize,
            child_installer=install,
            child_finalizer=finalize,
            source_identity="unit-test",
        ),
    )
    prefix = summary.prefixes[0]
    assert len(installed) == 2
    assert len(finalized) == 2
    assert all(child.status == "completed" for child in prefix.child_results)
    assert all(child.ticks_committed == 96 for child in prefix.child_results)


@pytest.mark.asyncio
async def test_grouped_result_requires_the_grouped_protocol() -> None:
    scenario_id = V3_BENCH_30_MULTIGENERATION_FORK
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="parent-prefix",
        command_plan_id="v3-benchmark-grouped-v1",
        command_plan_version="1",
    )
    from experiments.civilization_benchmark_execution import (
        CivilizationBenchmarkExecutionError,
    )

    with pytest.raises(CivilizationBenchmarkExecutionError) as excinfo:
        await execute_civilization_benchmark(recipe, CivilizationBenchmarkContext())
    assert excinfo.value.code == "grouped_executor_required"

    result = await execute_grouped_benchmark(
        scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
    )
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.ticks_committed == 96
    assert result.evidence.value == "complete"
    checks = {check.selector_id: check for check in result.checks}
    assert checks["path_dependence_outcome_evidence"].status is (
        V3BenchmarkCheckStatus.PASS
    )
    assert checks["objective_event_journal"].status is V3BenchmarkCheckStatus.PASS
