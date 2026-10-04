"""Unit tests for V2 benchmark builder protocol and fail-closed slots."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import (
    BenchmarkBuildResult,
    BenchmarkBuilderError,
    build_benchmark_scenario,
    is_benchmark_builder_implemented,
    register_benchmark_builder,
    registered_benchmark_builders,
    uninstall_benchmark_builder,
)
from experiments.benchmark_suite import (
    BENCHMARK_SCENARIO_IDS,
    BENCH_01_SEASONAL_PLANNING,
    BENCH_02_MEMORY_INTERFERENCE,
)
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 4):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=7,
        stochastic_identity="cmp-bench-protocol",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=max_ticks,
    )


def test_all_sixteen_slots_registered_fail_closed() -> None:
    builders = registered_benchmark_builders()
    assert set(builders) == set(BENCHMARK_SCENARIO_IDS)
    assert len(builders) == 16
    base = _base()
    for scenario_id in BENCHMARK_SCENARIO_IDS:
        assert is_benchmark_builder_implemented(scenario_id) is False
        with pytest.raises(BenchmarkBuilderError) as exc:
            build_benchmark_scenario(scenario_id, base)
        assert exc.value.code == "builder_not_implemented"


def test_implemented_stub_builds_known_experiment_a_arm() -> None:
    def _stub(
        base,
        *,
        seed_matrix: ExperimentSeedMatrix | None = None,
    ) -> BenchmarkBuildResult:
        definition = experiment_a_memory(base, seed_matrix=seed_matrix)
        # Keep only the locked reconstructive pair for this scenario.
        conditions = tuple(
            item
            for item in definition.conditions
            if item.condition_id in {"a-reconstructive", "a-reconstructive-v2"}
        )
        from experiments.models import ExperimentDefinition

        paired = ExperimentDefinition(
            experiment_id="bench-02-memory-interference",
            schema_version=definition.schema_version,
            seed_matrix=definition.seed_matrix,
            conditions=conditions,
            paired_world_group="bench-02-memory-interference-world",
        )
        return BenchmarkBuildResult(
            scenario_id=BENCH_02_MEMORY_INTERFERENCE,
            definition=paired,
            matrix_factors=("memory_type",),
        )

    register_benchmark_builder(BENCH_02_MEMORY_INTERFERENCE, _stub)
    try:
        assert is_benchmark_builder_implemented(BENCH_02_MEMORY_INTERFERENCE) is True
        result = build_benchmark_scenario(BENCH_02_MEMORY_INTERFERENCE, _base())
        assert result.scenario_id == BENCH_02_MEMORY_INTERFERENCE
        assert {item.condition_id for item in result.definition.conditions} == {
            "a-reconstructive",
            "a-reconstructive-v2",
        }
        assert result.matrix_factors == ("memory_type",)
    finally:
        uninstall_benchmark_builder(BENCH_02_MEMORY_INTERFERENCE)
        assert is_benchmark_builder_implemented(BENCH_02_MEMORY_INTERFERENCE) is False


def test_unknown_builder_registration_fails_closed() -> None:
    with pytest.raises(BenchmarkBuilderError) as exc:
        register_benchmark_builder("bench-99-missing", lambda base, *, seed_matrix=None: None)  # type: ignore[arg-type,return-value]
    assert exc.value.code == "unknown_scenario_id"


def test_package_docstring_lists_locked_condition_mapping() -> None:
    import experiments.benchmark_scenarios as pkg

    doc = pkg.__doc__ or ""
    assert "bench-01-seasonal-planning" in doc
    assert "u-learned" in doc
    assert "COMMUNICATION_REMOVE" in doc
    assert BENCH_01_SEASONAL_PLANNING in doc
