"""Unit tests for benchmark population and cultural-mutation recipes."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments.civilization_benchmark_base import build_v3_benchmark_base
from experiments.civilization_benchmark_evidence import (
    BenchmarkBoundaryProbe,
    blank_slate_check,
)
from experiments.civilization_benchmark_execution import (
    CivilizationBenchmarkContext,
    CivilizationBenchmarkRecipe,
    execute_civilization_benchmark,
    execute_stepped_benchmark_runner,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheckStatus,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_population import (
    POPULATION_BENCHMARK_IDS,
    build_population_benchmark,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_02_DEPENDENT_CARE,
    V3_BENCH_03_INTERGENERATIONAL_TEACHING,
    V3_BENCH_04_CULTURAL_MUTATION,
)
from experiments.coordinator import ExperimentAssignment
from experiments.generational_archive import GenerationalExecutionRecipe
from experiments.generational_execution import (
    PLAIN_RECIPE_ID,
    GenerationalExecutionContext,
)
from simulation.models import RunId
from simulation.new_agent_initialization import SPECIES_DEFAULT_DEVELOPMENTAL_V1
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import PopulationLifecycleSpec
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from world.lifecycle import LifecycleStageId, LifecycleStageThreshold


def _short_config(config, *, max_ticks: int = 3):
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    short = replace(
        lifecycle,
        lifespan_ticks=6,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 1),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 2),
            LifecycleStageThreshold(LifecycleStageId("adult"), 5),
        ),
        demographic_policy_params={
            **dict(lifecycle.demographic_policy_params),
            "interval_ticks": 1,
            "generation_length_ticks": 1,
        },
        max_population=8,
    )
    return replace(
        config,
        population_lifecycle=short,
        stop_policy=replace(config.stop_policy, max_ticks=max_ticks),
    )


def _assignment(config, run_id: str) -> ExperimentAssignment:
    return ExperimentAssignment(
        experiment_id="v3-benchmark-population",
        condition_id="population-case",
        condition_ordinal=0,
        seed=config.seed,
        seed_ordinal=0,
        replicate_index=0,
        run_id=RunId(run_id),
        runner_config=config,
    )


def _context(tmp_path, probe: BenchmarkBoundaryProbe) -> GenerationalExecutionContext:
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


def test_all_population_cases_build_exact_owned_specs() -> None:
    for scenario_id in POPULATION_BENCHMARK_IDS:
        for lane in (V3BenchmarkLane.MECHANISM, V3BenchmarkLane.RESEARCH):
            build = build_population_benchmark(scenario_id, lane=lane)
            assert build.lane is lane
            assert len(build.arms) == 1
            config = build.arms[0].config
            assert config.schema_version == "runner-config-v55"
            assert config.generational_run is not None
            if scenario_id == V3_BENCH_02_DEPENDENT_CARE:
                assert config.dependency_care is not None
            else:
                assert config.dependency_care is None
            if scenario_id != V3_BENCH_03_INTERGENERATIONAL_TEACHING:
                assert config.mentorship is None
            if scenario_id == V3_BENCH_03_INTERGENERATIONAL_TEACHING:
                assert config.developmental_learning is not None
                assert config.mentorship is not None
                assert (
                    config.new_agent_initialization.species_defaults_id
                    == SPECIES_DEFAULT_DEVELOPMENTAL_V1
                )
            if scenario_id == V3_BENCH_04_CULTURAL_MUTATION:
                assert config.cultural_feature_provenance is not None
                assert (
                    config.new_agent_initialization.species_defaults_id
                    == SPECIES_DEFAULT_DEVELOPMENTAL_V1
                )
            assert build.arms[0].manipulated_fields == ()
            assert (
                decode_runner_config(encode_runner_config(config)) == config
            )


def test_unknown_population_case_is_rejected() -> None:
    with pytest.raises(Exception) as excinfo:
        build_population_benchmark("v3-bench-05-memory-layers")
    assert "unknown_scenario" in str(excinfo.value) or getattr(
        excinfo.value, "code", None
    ) == "unknown_scenario"


@pytest.mark.asyncio
async def test_dependent_care_case_measures_real_entrants(tmp_path) -> None:
    build = build_population_benchmark(V3_BENCH_02_DEPENDENT_CARE)
    config = _short_config(build.arms[0].config, max_ticks=3)
    probe = BenchmarkBoundaryProbe()
    async with await SimulationRunner.from_config(config) as runner:
        stepped = await execute_stepped_benchmark_runner(
            runner, boundary_observer=probe
        )
    assert stepped.result.ticks_committed == 3
    assert probe.new_owners()
    assert any(
        owner.owner_id.startswith("entrant") for owner in probe.new_owners()
    )
    check = blank_slate_check(probe, boundary_end_tick=3)
    assert check.status is V3BenchmarkCheckStatus.PASS


@pytest.mark.asyncio
async def test_teaching_case_keeps_unmeasured_selectors_unexecuted(
    tmp_path,
) -> None:
    build = build_population_benchmark(V3_BENCH_03_INTERGENERATIONAL_TEACHING)
    config = _short_config(build.arms[0].config, max_ticks=2)
    probe = BenchmarkBoundaryProbe()
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=V3_BENCH_03_INTERGENERATIONAL_TEACHING,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config, "run-teaching-short"),
        execution_context=_context(tmp_path, probe),
        probe=probe,
    )
    result = await execute_civilization_benchmark(recipe, context)
    assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
    assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE
    statuses = {check.selector_id: check for check in result.checks}
    for selector_id in (
        "mentorship_evidence",
        "developmental_learning_evidence",
    ):
        check = statuses[selector_id]
        assert check.status is V3BenchmarkCheckStatus.PASS
        assert check.reason_code == "teaching_window_complete"
        assert check.denominator >= 1
        assert 0 <= (check.numerator or 0) <= check.denominator


@pytest.mark.asyncio
async def test_blank_slate_case_remains_the_only_complete_mechanism(
    tmp_path,
) -> None:
    build = build_population_benchmark(V3_BENCH_01_BLANK_SLATE)
    config = _short_config(build.arms[0].config, max_ticks=2)
    probe = BenchmarkBoundaryProbe()
    async with await SimulationRunner.from_config(config) as runner:
        await execute_stepped_benchmark_runner(runner, boundary_observer=probe)
    check = blank_slate_check(probe, boundary_end_tick=2)
    assert check.numerator == len(probe.new_owners())
    assert check.denominator == len(probe.new_owners())


def test_base_case_has_no_extra_optional_specs() -> None:
    base = build_v3_benchmark_base(
        seed=None,
        profile=V3BenchmarkProfile.SMOKE,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )
    assert base.config.dependency_care is None
    assert base.config.mentorship is None
    assert base.config.developmental_learning is None
    assert base.config.cultural_feature_provenance is not None


@pytest.mark.asyncio
async def test_all_four_cases_reach_complete_evidence(tmp_path) -> None:
    for index, scenario_id in enumerate(POPULATION_BENCHMARK_IDS):
        build = build_population_benchmark(scenario_id)
        config = _short_config(build.arms[0].config, max_ticks=3)
        probe = BenchmarkBoundaryProbe()
        recipe = CivilizationBenchmarkRecipe(
            scenario_id=scenario_id,
            lane=V3BenchmarkLane.RESEARCH,
            profile=V3BenchmarkProfile.SMOKE,
            seed=23,
            arm_id="observation",
        )
        context = CivilizationBenchmarkContext(
            assignment=_assignment(config, f"run-all-{index}"),
            execution_context=_context(tmp_path / scenario_id, probe),
            probe=probe,
        )
        result = await execute_civilization_benchmark(recipe, context)
        assert result.execution_status is V3BenchmarkExecutionStatus.COMPLETED
        assert result.ticks_committed == 3
        assert result.evidence is V3BenchmarkEvidenceAvailability.COMPLETE, (
            scenario_id,
            [(check.selector_id, check.status.value) for check in result.checks],
        )
        for check in result.checks:
            assert check.status is V3BenchmarkCheckStatus.PASS


@pytest.mark.asyncio
async def test_teaching_requires_the_recipient_learner_profile(tmp_path) -> None:
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_V1,
        default_new_agent_initialization_spec,
    )

    build = build_population_benchmark(V3_BENCH_03_INTERGENERATIONAL_TEACHING)
    config = _short_config(build.arms[0].config, max_ticks=3)
    config = replace(
        config,
        new_agent_initialization=replace(
            default_new_agent_initialization_spec(),
            species_defaults_id=SPECIES_DEFAULT_V1,
        ),
    )
    probe = BenchmarkBoundaryProbe()
    recipe = CivilizationBenchmarkRecipe(
        scenario_id=V3_BENCH_03_INTERGENERATIONAL_TEACHING,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        seed=23,
        arm_id="observation",
    )
    context = CivilizationBenchmarkContext(
        assignment=_assignment(config, "run-teaching-mode-off"),
        execution_context=_context(tmp_path / "mode-off", probe),
        probe=probe,
    )
    result = await execute_civilization_benchmark(recipe, context)
    assert result.evidence is V3BenchmarkEvidenceAvailability.PARTIAL
    statuses = {check.selector_id: check for check in result.checks}
    for selector_id in (
        "mentorship_evidence",
        "developmental_learning_evidence",
    ):
        check = statuses[selector_id]
        assert check.status is V3BenchmarkCheckStatus.UNEXECUTED
        assert check.reason_code == "recipient_mode_disabled"
