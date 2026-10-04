"""Unit tests for benchmark scenarios 8-14 (culture/social processes)."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_smoke import run_benchmark_smoke
from experiments.benchmark_suite import (
    BENCH_08_TERRITORIAL,
    BENCH_09_SOCIAL_CLUSTERS,
    BENCH_10_NORMS,
    BENCH_11_CONVENTIONS,
    BENCH_12_ARTIFACTS,
    BENCH_13_NAMING_DRIFT,
    BENCH_14_RUMOR_NARRATIVE,
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

_SCENARIOS = (
    (BENCH_08_TERRITORIAL, ("v-scarce", "v-abundant")),
    (BENCH_09_SOCIAL_CLUSTERS, ("w-enabled", "w-disabled")),
    (BENCH_10_NORMS, ("x-enabled", "x-disabled")),
    (BENCH_11_CONVENTIONS, ("y-enabled", "y-disabled")),
    (BENCH_12_ARTIFACTS, ("artifact_channel", "memory_only")),
    (BENCH_13_NAMING_DRIFT, ("aa-enabled", "aa-disabled")),
    (BENCH_14_RUMOR_NARRATIVE, ("ab-enabled", "ab-disabled")),
)


def _base(*, max_ticks: int = 4, seed: int = 29):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-culture",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-culture"),
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


@pytest.mark.parametrize(("scenario_id", "condition_ids"), _SCENARIOS)
def test_culture_scenario_locked_condition_ids(
    scenario_id: str, condition_ids: tuple[str, ...]
) -> None:
    result = build_benchmark_scenario(scenario_id, _base())
    assert tuple(item.condition_id for item in result.definition.conditions) == (
        condition_ids
    )
    # No boolean emergence fields on runner configs / conditions.
    for condition in result.definition.conditions:
        encoded = str(condition.label_code)
        assert "group_must_form" not in encoded
        assert "norm_emerged" not in encoded
        assert "society_formed" not in encoded


@pytest.mark.asyncio
async def test_culture_scenarios_smoke_availability() -> None:
    for scenario_id, _ids in _SCENARIOS:
        smoke = await run_benchmark_smoke(scenario_id, _base(), tick_budget=4)
        assert smoke.ran is True
        assert smoke.ticks <= 4
        assert smoke.metrics_available
