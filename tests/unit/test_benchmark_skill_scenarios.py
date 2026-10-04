"""Unit tests for benchmark scenario 7 (skill learning + specialization)."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_smoke import run_benchmark_smoke
from experiments.benchmark_suite import BENCH_07_SKILL_SPECIALIZATION
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    SkillLearningMode,
    TeachingInteractionMode,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 4, seed: int = 19):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-skill",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-skill"),
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


def test_bench_07_skill_specialization_mechanism() -> None:
    result = build_benchmark_scenario(BENCH_07_SKILL_SPECIALIZATION, _base())
    assert [item.condition_id for item in result.definition.conditions] == [
        "r-enabled",
        "t-enabled",
        "r-disabled",
        "t-disabled",
    ]
    by_id = {item.condition_id: item for item in result.definition.conditions}
    assert (
        by_id["r-enabled"].runner_config.agents[0].cognition.skill_learning_mode
        is SkillLearningMode.DETERMINISTIC
    )
    assert (
        by_id["t-enabled"].runner_config.agents[0].cognition.teaching_interaction_mode
        is TeachingInteractionMode.DETERMINISTIC
    )
    assert (
        by_id["r-disabled"].runner_config.agents[0].cognition.skill_learning_mode
        is SkillLearningMode.DISABLED
    )
    seeds = {item.runner_config.seed for item in result.definition.conditions}
    assert len(seeds) == 1


@pytest.mark.asyncio
async def test_bench_07_smoke_availability() -> None:
    smoke = await run_benchmark_smoke(
        BENCH_07_SKILL_SPECIALIZATION, _base(), tick_budget=4
    )
    assert smoke.ran is True
    assert smoke.ticks <= 4
    assert smoke.arm_count == 4
    assert any("skill_learning@1" in item.measurable_output for item in smoke.metrics_available)
