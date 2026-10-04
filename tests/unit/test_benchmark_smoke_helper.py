"""Unit tests for the V2 benchmark smoke helper (framework only)."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import (
    BenchmarkBuilderError,
    build_benchmark_scenario,
)
from experiments.benchmark_smoke import (
    DEFAULT_SMOKE_TICK_BUDGET,
    BenchmarkSmokeError,
    run_benchmark_smoke,
    smoke_tick_budget,
)
from experiments.benchmark_suite import (
    BENCH_02_MEMORY_INTERFERENCE,
    BENCH_08_TERRITORIAL,
)
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 8):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=3,
        stochastic_identity="cmp-bench-smoke",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-smoke"),
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


def test_smoke_tick_budget_caps_at_four() -> None:
    assert DEFAULT_SMOKE_TICK_BUDGET == 4
    assert smoke_tick_budget(BENCH_02_MEMORY_INTERFERENCE, tick_budget=64) == 4
    assert smoke_tick_budget(BENCH_02_MEMORY_INTERFERENCE, tick_budget=2) == 2


def test_smoke_requires_implemented_builder() -> None:
    import asyncio

    with pytest.raises(BenchmarkSmokeError) as exc:
        asyncio.run(run_benchmark_smoke(BENCH_08_TERRITORIAL, _base()))
    assert exc.value.code == "builder_not_implemented"


@pytest.mark.asyncio
async def test_smoke_helper_runs_first_implemented_arm() -> None:
    result = await run_benchmark_smoke(
        BENCH_02_MEMORY_INTERFERENCE,
        _base(),
        tick_budget=4,
    )
    assert result.scenario_id == BENCH_02_MEMORY_INTERFERENCE
    assert result.ran is True
    assert result.ticks <= 4
    assert result.arm_count >= 2
    assert set(result.condition_ids) == {
        "a-reconstructive",
        "a-reconstructive-v2",
    }
    assert result.metrics_available
    for item in result.metrics_available:
        assert item.status in {
            "present",
            "partial",
            "assemblable",
            "absent",
            "unknown",
            "declared",
        }
        assert "must emerge" not in item.measurable_output.lower()
        assert "must form" not in item.measurable_output.lower()
    assert any("memory_dynamics@1" in item.measurable_output for item in result.metrics_available)


@pytest.mark.asyncio
async def test_smoke_helper_run_ticks_false_stays_declared_only() -> None:
    result = await run_benchmark_smoke(
        BENCH_02_MEMORY_INTERFERENCE,
        _base(),
        run_ticks=False,
    )
    assert result.ran is False
    assert result.ticks == 0
    assert result.arm_count == 0
    assert all(item.status == "declared" for item in result.metrics_available)


def test_bench_02_builder_is_live() -> None:
    result = build_benchmark_scenario(BENCH_02_MEMORY_INTERFERENCE, _base())
    assert result.scenario_id == BENCH_02_MEMORY_INTERFERENCE
    # Ensure protocol surface still raises for unknown ids via builder layer.
    with pytest.raises(BenchmarkBuilderError):
        build_benchmark_scenario("bench-99-missing", _base())
