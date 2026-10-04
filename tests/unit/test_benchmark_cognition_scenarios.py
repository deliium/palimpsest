"""Unit tests for benchmark scenarios 1-3 (planning, memory, reflection)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId, GoalHorizon
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_smoke import run_benchmark_smoke
from experiments.benchmark_suite import (
    BENCH_01_SEASONAL_PLANNING,
    BENCH_02_MEMORY_INTERFERENCE,
    BENCH_03_REFLECTION_REVISION,
)
from experiments.catalog import base_runner_config_from_scenario
from experiments.collectors import collect_for_experiment
from experiments.coordinator import ExperimentCoordinator
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    MemoryMode,
    ReflectionMode,
    RunnerStopPolicy,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 8, seed: int = 11):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-cognition",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-cog"),
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


def test_bench_01_seasonal_planning_mechanism() -> None:
    result = build_benchmark_scenario(BENCH_01_SEASONAL_PLANNING, _base(max_ticks=16))
    assert [item.condition_id for item in result.definition.conditions] == [
        "u-learned",
        "u-naive",
    ]
    learned, naive = result.definition.conditions
    assert learned.runner_config.capability_flags.predictive_world_model is True
    assert naive.runner_config.capability_flags.predictive_world_model is False
    assert learned.runner_config.environmental_dynamics is not None
    goals = learned.runner_config.agents[0].initial_goals
    assert goals and goals[0].horizon is GoalHorizon.LONG_TERM
    assert learned.runner_config.seed == naive.runner_config.seed
    assert (
        learned.runner_config.stochastic_identity
        == naive.runner_config.stochastic_identity
    )


def test_bench_02_memory_interference_mechanism() -> None:
    result = build_benchmark_scenario(BENCH_02_MEMORY_INTERFERENCE, _base())
    assert [item.condition_id for item in result.definition.conditions] == [
        "a-reconstructive-v2",
        "a-reconstructive",
    ]
    modes = {
        item.runner_config.agents[0].cognition.memory_mode
        for item in result.definition.conditions
    }
    assert modes == {MemoryMode.RECONSTRUCTIVE_V2, MemoryMode.RECONSTRUCTIVE}
    seeds = {item.runner_config.seed for item in result.definition.conditions}
    assert len(seeds) == 1


@pytest.mark.asyncio
async def test_bench_03_reflection_revision_audits_and_analysis_only() -> None:
    result = build_benchmark_scenario(BENCH_03_REFLECTION_REVISION, _base(max_ticks=8))
    assert [item.condition_id for item in result.definition.conditions] == [
        "g-deterministic",
        "g-disabled",
    ]
    by_id = {item.condition_id: item for item in result.definition.conditions}
    assert (
        by_id["g-deterministic"].runner_config.agents[0].cognition.reflection_mode
        is ReflectionMode.DETERMINISTIC
    )
    assert (
        by_id["g-disabled"].runner_config.agents[0].cognition.reflection_mode
        is ReflectionMode.DISABLED
    )
    capped = result.definition
    conditions = tuple(
        replace(
            item,
            runner_config=replace(
                item.runner_config,
                stop_policy=RunnerStopPolicy(max_ticks=8),
            ),
        )
        for item in capped.conditions
    )
    definition = replace(
        capped,
        conditions=conditions,
        seed_matrix=ExperimentSeedMatrix(seeds=(capped.seed_matrix.seeds[0],)),
    )
    arms = await ExperimentCoordinator(definition).run_all()
    by_arm = {arm.assignment.condition_id: arm for arm in arms}
    assert by_arm["g-disabled"].runner_result.reflection_audits == ()
    deterministic_audits = by_arm["g-deterministic"].runner_result.reflection_audits
    # Mechanism engagement: deterministic arm emits reflection audits.
    assert len(deterministic_audits) >= 1
    for arm in arms:
        for doc in collect_for_experiment(arm):
            payload = dict(doc.fields)
            assert "is_false" not in payload
            assert "truth" not in payload


@pytest.mark.asyncio
async def test_bench_01_through_03_smoke_availability() -> None:
    for scenario_id in (
        BENCH_01_SEASONAL_PLANNING,
        BENCH_02_MEMORY_INTERFERENCE,
        BENCH_03_REFLECTION_REVISION,
    ):
        smoke = await run_benchmark_smoke(
            scenario_id, _base(max_ticks=8), tick_budget=4
        )
        assert smoke.ran is True
        assert smoke.ticks <= 4
        assert smoke.metrics_available
        # No emergence booleans in smoke statuses.
        assert all(
            item.status
            in {"present", "partial", "assemblable", "absent", "unknown", "declared"}
            for item in smoke.metrics_available
        )
