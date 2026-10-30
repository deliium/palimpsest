"""Unit tests for bounded and comparable V3 benchmark worlds."""

from __future__ import annotations

from dataclasses import replace

import pytest

from experiments import (
    V3_BENCHMARK_PROFILE_BUDGETS,
    V3_BENCHMARK_SCENARIO_IDS,
    V3BenchmarkContrastKind,
    V3BenchmarkError,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkProfileBudget,
    V3BenchmarkTreatmentScope,
    assert_v3_benchmark_build_comparable,
    build_v3_benchmark_base,
    build_v3_benchmark_scenario,
)
from experiments.civilization_benchmark_base import V3BenchmarkBase
from experiments.civilization_benchmark_suite import (
    FAST_COHORT_SCHEDULE_ID,
    RESEARCH_SCHEDULE_ID,
    RESEARCH_SEEDS,
    V3_BENCH_01_BLANK_SLATE,
    V3_BENCH_29_FOUNDER_CONTINGENCY,
    V3_BENCH_30_MULTIGENERATION_FORK,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V55,
    PopulationLifecycleSpec,
    SimulationRunnerConfig,
)
from simulation.runner_serialization import encode_runner_config
from world.lifecycle import LifecycleStageId


def _base(profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE) -> V3BenchmarkBase:
    return build_v3_benchmark_base(
        seed=None,
        profile=profile,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )


def test_smoke_profile_contract() -> None:
    base = _base()
    config = base.config
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V55
    assert base.seed == 23
    assert base.horizon_ticks == 96
    assert base.founder_ids == (
        "agent-origin",
        "agent-spring",
        "agent-grain",
        "agent-remote",
    )
    assert base.initializer_profile_id == "species_default_v1"
    lifecycle = config.population_lifecycle
    assert isinstance(lifecycle, PopulationLifecycleSpec)
    assert lifecycle.lifespan_ticks == 24
    assert lifecycle.max_population == 12
    assert lifecycle.natural_death_on_lifespan is True
    assert lifecycle.dependent_until_stage == LifecycleStageId("juvenile")
    assert dict(lifecycle.demographic_policy_params) == {
        "interval_ticks": 8,
        "entries_per_interval": 1,
        "generation_length_ticks": 16,
        "name_prefix": "entrant",
        "cohort_id_prefix": "cohort",
        "spawn_location_ids": (
            "loc-origin",
            "loc-spring",
            "loc-grain",
            "loc-remote",
        ),
    }
    assert config.stop_policy.max_ticks == 96
    assert config.stop_policy.stop_on_all_agents_terminal is False
    assert config.v3_capability_flags.generational_population is True
    assert config.v3_capability_flags.multi_polity_migration is True
    assert config.v3_capability_flags.cultural_historical_memory is True
    assert config.v3_capability_flags.kinship_inheritance is False
    assert config.v3_capability_flags.institutional_economy is False
    assert config.cultural_feature_provenance is not None
    assert config.generational_run is not None
    assert config.generational_run.max_generation_index is None
    assert config.generational_run.stop_on_extinction is False
    assert config.generational_run.population_threshold is None
    assert config.generational_run.experiment_criteria == ()
    assert config.generational_run.criterion_cadence_ticks == 1
    assert config.experiment is None
    assert config.derivation_version is not None


def test_profile_budgets_are_predeclared_and_closed() -> None:
    smoke = V3_BENCHMARK_PROFILE_BUDGETS[V3BenchmarkProfile.SMOKE]
    research = V3_BENCHMARK_PROFILE_BUDGETS[V3BenchmarkProfile.RESEARCH]
    visual = V3_BENCHMARK_PROFILE_BUDGETS[V3BenchmarkProfile.VISUAL]
    assert smoke.seeds == (23,)
    assert smoke.horizon_ticks == 96
    assert smoke.founder_count == 4
    assert research.seeds == RESEARCH_SEEDS == (11, 23, 37, 53, 71)
    assert research.horizon_ticks == 192
    assert research.founder_count == 4
    assert visual.seeds == (23,)
    assert visual.horizon_ticks == 160
    assert visual.founder_count == 6
    assert visual.max_population == 16
    for budget in V3_BENCHMARK_PROFILE_BUDGETS.values():
        assert type(budget) is V3BenchmarkProfileBudget
        assert budget.max_population >= budget.founder_count
        assert budget.generation_length_ticks % budget.entry_interval_ticks == 0
        assert budget.lifespan_ticks > budget.generation_length_ticks


def test_research_seeds_build_without_research_runs() -> None:
    for seed in RESEARCH_SEEDS:
        base = build_v3_benchmark_base(
            seed=seed,
            profile=V3BenchmarkProfile.RESEARCH,
            scenario_id=V3_BENCH_01_BLANK_SLATE,
        )
        assert base.seed == seed
        assert base.horizon_ticks == 192
    with pytest.raises(V3BenchmarkError) as excinfo:
        build_v3_benchmark_base(
            seed=99,
            profile=V3BenchmarkProfile.RESEARCH,
            scenario_id=V3_BENCH_01_BLANK_SLATE,
        )
    assert excinfo.value.code == "undeclared_seed"


def test_visual_profile_has_six_founders_and_capacity() -> None:
    base = _base(V3BenchmarkProfile.VISUAL)
    config = base.config
    assert len(base.founder_ids) == 6
    assert base.horizon_ticks == 160
    assert config.population_lifecycle is not None
    assert config.population_lifecycle.max_population == 16
    body_ids = {body.entity_id.value for body in config.scenario.bodies}
    assert {"body-extra-1", "body-extra-2"} <= body_ids
    assert "agent-extra-1" in base.founder_ids
    assert config.stop_policy.max_ticks == 160


def test_unknown_scenario_and_profile_are_rejected() -> None:
    with pytest.raises(V3BenchmarkError):
        build_v3_benchmark_base(
            seed=None,
            profile=V3BenchmarkProfile.SMOKE,
            scenario_id="v3-bench-99-unknown",
        )
    with pytest.raises(V3BenchmarkError) as excinfo:
        build_v3_benchmark_base(
            seed=None,
            profile="smoke",  # type: ignore[arg-type]
            scenario_id=V3_BENCH_01_BLANK_SLATE,
        )
    assert excinfo.value.code == "invalid_profile"


def test_profile_budget_validation_is_closed() -> None:
    with pytest.raises(V3BenchmarkError):
        V3BenchmarkProfileBudget(
            profile=V3BenchmarkProfile.SMOKE,
            horizon_ticks=0,
            seeds=(23,),
            founder_count=4,
            entry_interval_ticks=8,
            generation_length_ticks=16,
            lifespan_ticks=24,
            max_population=12,
        )
    with pytest.raises(V3BenchmarkError):
        V3BenchmarkProfileBudget(
            profile=V3BenchmarkProfile.SMOKE,
            horizon_ticks=96,
            seeds=(23,),
            founder_count=5,
            entry_interval_ticks=8,
            generation_length_ticks=16,
            lifespan_ticks=24,
            max_population=12,
        )
    with pytest.raises(V3BenchmarkError):
        V3BenchmarkProfileBudget(
            profile=V3BenchmarkProfile.SMOKE,
            horizon_ticks=96,
            seeds=(23,),
            founder_count=4,
            entry_interval_ticks=8,
            generation_length_ticks=17,
            lifespan_ticks=24,
            max_population=12,
        )
    with pytest.raises(V3BenchmarkError):
        V3BenchmarkProfileBudget(
            profile=V3BenchmarkProfile.SMOKE,
            horizon_ticks=96,
            seeds=(23,),
            founder_count=4,
            entry_interval_ticks=8,
            generation_length_ticks=16,
            lifespan_ticks=24,
            max_population=2,
        )


def test_every_scenario_builds_in_both_lanes() -> None:
    expected_horizon = V3_BENCHMARK_PROFILE_BUDGETS[
        V3BenchmarkProfile.SMOKE
    ].horizon_ticks
    for scenario_id in V3_BENCHMARK_SCENARIO_IDS:
        for lane in (V3BenchmarkLane.MECHANISM, V3BenchmarkLane.RESEARCH):
            build = build_v3_benchmark_scenario(
                scenario_id,
                profile=V3BenchmarkProfile.SMOKE,
                lane=lane,
            )
            assert build.spec.scenario_id == scenario_id
            assert build.lane is lane
            assert len(build.arms) == build.spec.recipe.arm_count
            for arm in build.arms:
                assert arm.config.schema_version == RUNNER_SCHEMA_VERSION_V55
                assert arm.config.stop_policy.max_ticks == expected_horizon
                assert arm.initializer_profile_id == "species_default_v1"
                assert arm.founder_ids == build.arms[0].founder_ids
    with pytest.raises(V3BenchmarkError):
        build_v3_benchmark_scenario(
            V3_BENCH_01_BLANK_SLATE,
            profile=V3BenchmarkProfile.SMOKE,
            lane="autonomous",  # type: ignore[arg-type]
        )


def test_grouped_cases_share_the_sealed_prefix_configuration() -> None:
    for scenario_id in (
        V3_BENCH_29_FOUNDER_CONTINGENCY,
        V3_BENCH_30_MULTIGENERATION_FORK,
    ):
        build = build_v3_benchmark_scenario(
            scenario_id,
            profile=V3BenchmarkProfile.SMOKE,
            lane=V3BenchmarkLane.RESEARCH,
        )
        assert len(build.arms) == 2
        assert [arm.arm_id for arm in build.arms] == [
            "parent-prefix",
            "fork-child",
        ]
        assert encode_runner_config(build.arms[0].config) == encode_runner_config(
            build.arms[1].config
        )
        for arm in build.arms:
            assert arm.treatment_scope is V3BenchmarkTreatmentScope.RUN_OPPORTUNITY
            assert arm.contrast_kind is V3BenchmarkContrastKind.SINGLE_FACTOR
            assert arm.manipulated_fields == ()
        assert build.spec.recipe.schedule_id == (
            FAST_COHORT_SCHEDULE_ID
            if scenario_id == V3_BENCH_30_MULTIGENERATION_FORK
            else RESEARCH_SCHEDULE_ID
        )


def test_independent_cases_have_one_untreated_arm() -> None:
    build = build_v3_benchmark_scenario(
        V3_BENCH_01_BLANK_SLATE,
        profile=V3BenchmarkProfile.SMOKE,
        lane=V3BenchmarkLane.MECHANISM,
    )
    assert len(build.arms) == 1
    arm = build.arms[0]
    assert arm.treatment_scope is V3BenchmarkTreatmentScope.NONE
    assert arm.contrast_kind is V3BenchmarkContrastKind.NONE


def test_codec_and_capture_independence_are_byte_stable() -> None:
    first = _base()
    second = _base()
    assert encode_runner_config(first.config) == encode_runner_config(second.config)
    # Capture is composition-only; no capture setting exists in the runner JSON.
    assert b"cultural_capture" not in encode_runner_config(first.config)
    assert b"capture" not in encode_runner_config(first.config)


def test_build_comparability_gate_rejects_varied_prefix() -> None:
    build = build_v3_benchmark_scenario(
        V3_BENCH_29_FOUNDER_CONTINGENCY,
        profile=V3BenchmarkProfile.SMOKE,
        lane=V3BenchmarkLane.RESEARCH,
    )
    varied = replace(
        build.arms[1],
        config=replace(
            build.arms[1].config,
            stop_policy=replace(
                build.arms[1].config.stop_policy,
                max_ticks=build.arms[1].config.stop_policy.max_ticks + 1,
            ),
        ),
    )
    broken = replace(build, arms=(build.arms[0], varied))
    with pytest.raises(V3BenchmarkError) as excinfo:
        assert_v3_benchmark_build_comparable(broken)
    assert excinfo.value.code == "comparison_mismatch"

    mismatched_scope = replace(
        build,
        arms=(
            build.arms[0],
            replace(
                build.arms[1],
                treatment_scope=V3BenchmarkTreatmentScope.NONE,
            ),
        ),
    )
    with pytest.raises(V3BenchmarkError) as excinfo:
        assert_v3_benchmark_build_comparable(mismatched_scope)
    assert excinfo.value.code == "comparison_scope_mismatch"


def test_arm_count_mismatch_is_rejected() -> None:
    build = build_v3_benchmark_scenario(
        V3_BENCH_29_FOUNDER_CONTINGENCY,
        profile=V3BenchmarkProfile.SMOKE,
        lane=V3BenchmarkLane.RESEARCH,
    )
    with pytest.raises(V3BenchmarkError) as excinfo:
        replace(build, arms=(build.arms[0],))
    assert excinfo.value.code == "arm_count_mismatch"


def test_schema_downgrade_is_rejected() -> None:
    base = _base()
    with pytest.raises(ValueError):
        replace(base, config=replace(base.config, schema_version="runner-config-v4"))


def test_simulation_config_type_is_preserved() -> None:
    base = _base()
    assert type(base.config) is SimulationRunnerConfig
    assert base.config.new_agent_initialization is not None
