"""V3 benchmark coordination cases: physical work, benefits and nulls."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.civilization_benchmark_coordination import (
    COORDINATION_BENCHMARK_IDS,
    build_coordination_benchmark,
    coordination_benchmark_arbiter,
    evaluate_collective_projects,
    evaluate_public_goods,
    required_coordination_milestones,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_16_COLLECTIVE_PROJECT,
    V3_BENCH_17_PUBLIC_GOOD_PATTERNS,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from experiments.interventions import MilestoneInterventionArbiter
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import (
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.events import ProjectCompleted, ProjectContributed, PublicGoodBenefit
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold

_RUN_ID = RunId("v3bench-coordination")


def _short_config(
    config: SimulationRunnerConfig,
    *,
    max_ticks: int,
    lifespan: int = 8,
    interval: int = 8,
) -> SimulationRunnerConfig:
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        lifespan_ticks=lifespan,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), max(3, lifespan - 1)),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": interval,
            "generation_length_ticks": interval,
        },
        max_population=8,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _context(
    tmp_path: Path, probe: BenchmarkBoundaryProbe
) -> GenerationalExecutionContext:
    return GenerationalExecutionContext(
        artifact_root=tmp_path,
        source_identity={"code_revision": "deadbeef", "source_clean": True},
        recipe=GenerationalExecutionRecipe(
            recipe_id=PLAIN_RECIPE_ID, version="1", params={}
        ),
        factories=RunnerDependencyFactories(),
        attempt_id="attempt-1",
        boundary_observer=probe,
    )


def _assignment(config: SimulationRunnerConfig, run_id: RunId) -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id="v3-benchmark-coordination",
        condition_id="coordination-case",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=run_id,
        runner_config=config,
    )


async def _dispatch(
    tmp_path: Path,
    scenario_id: str,
    config: SimulationRunnerConfig,
    probe: BenchmarkBoundaryProbe,
    *,
    arbiter: MilestoneInterventionArbiter | None,
) -> V3BenchmarkRunResult:
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config, _RUN_ID),
        execution_context=_context(tmp_path, probe),
        probe=probe,
        arbiter=arbiter,
        required_milestone_ids=required_coordination_milestones(scenario_id),
    )
    return await execute_civilization_benchmark(recipe, context)


def test_coordination_cases_build_exact_channels() -> None:
    for scenario_id in COORDINATION_BENCHMARK_IDS:
        build = build_coordination_benchmark(scenario_id)
        config = build.arms[0].config
        assert config.collective_projects is not None
        names = {item.name for item in config.scenario.items}
        assert {"wood", "stone"} <= names
        assert decode_runner_config(encode_runner_config(config)) == config
        if scenario_id == V3_BENCH_16_COLLECTIVE_PROJECT:
            assert config.public_goods is None
        else:
            assert config.public_goods is not None


@pytest.mark.asyncio
async def test_collective_project_completes_with_two_owners(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_16_COLLECTIVE_PROJECT
    build = build_coordination_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=6)
    arbiter = coordination_benchmark_arbiter(scenario_id, config, run_id=_RUN_ID)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config, run_id=_RUN_ID) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        contributed = tuple(
            event.details
            for event in runner.engine.export_events().events
            if type(event.details) is ProjectContributed and event.details.accepted
        )
        completed = tuple(
            event.details
            for event in runner.engine.export_events().events
            if type(event.details) is ProjectCompleted
        )
    assert len(contributed) == 3
    assert len({row.actor_id.value for row in contributed}) == 2
    assert len(completed) == 1
    check = evaluate_collective_projects(
        probe,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "project_completed_observed"


@pytest.mark.asyncio
async def test_noncontributor_can_draw_a_public_good(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_17_PUBLIC_GOOD_PATTERNS
    build = build_coordination_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=7)
    arbiter = coordination_benchmark_arbiter(scenario_id, config, run_id=_RUN_ID)
    assert arbiter is not None
    async with await SimulationRunner.from_config(config, run_id=_RUN_ID) as runner:
        runner.set_intervention_arbiter(arbiter)
        probe = BenchmarkBoundaryProbe()
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
        events = runner.engine.export_events().events
    contributors = {
        event.details.actor_id.value
        for event in events
        if type(event.details) is ProjectContributed and event.details.accepted
    }
    benefits = tuple(
        event.details for event in events if type(event.details) is PublicGoodBenefit
    )
    assert "body-extra-2" not in contributors
    assert any(
        row.actor_id.value == "body-extra-2" and row.source == "command"
        for row in benefits
    )
    check = evaluate_public_goods(
        probe,
        boundary_end_tick=stepped.result.ticks_committed,
        mechanism_available=True,
    )
    assert check.status is V3BenchmarkCheckStatus.PASS
    assert check.reason_code == "public_good_benefit_observed"


@pytest.mark.asyncio
async def test_failed_or_absent_project_work_does_not_pass(tmp_path: Path) -> None:
    scenario_id = V3_BENCH_16_COLLECTIVE_PROJECT
    build = build_coordination_benchmark(scenario_id)
    config = _short_config(build.arms[0].config, max_ticks=3)
    probe = BenchmarkBoundaryProbe()
    result = await _dispatch(tmp_path, scenario_id, config, probe, arbiter=None)
    checks = {check.selector_id: check for check in result.checks}
    project = checks["collective_project_evidence"]
    assert project.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert project.reason_code == "no_project_contribution_observed"


def test_disabled_channels_stay_unexecuted() -> None:
    from types import SimpleNamespace

    class _Probe:
        observations = [SimpleNamespace(boundary_tick=1, owners=())]
        failures: tuple[str, ...] = ()

        def event_total(self, kind: str) -> int:
            return 0

    probe = _Probe()
    projects = evaluate_collective_projects(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=1,
        mechanism_available=False,
    )
    assert projects.status is V3BenchmarkCheckStatus.UNEXECUTED
    assert projects.evidence is V3BenchmarkEvidenceAvailability.UNAVAILABLE
    goods = evaluate_public_goods(
        probe,  # type: ignore[arg-type]
        boundary_end_tick=1,
        mechanism_available=False,
    )
    assert goods.reason_code == "public_goods_disabled"
