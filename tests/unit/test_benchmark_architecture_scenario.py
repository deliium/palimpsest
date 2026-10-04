"""Unit tests for benchmark scenario 15 (architecture matrix)."""

from __future__ import annotations

from agents.models import AgentId
from experiments.benchmark_scenarios import build_benchmark_scenario
from experiments.benchmark_suite import BENCH_15_ARCHITECTURE_MATRIX
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from simulation.runner_serialization import scenario_fingerprint
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base(*, max_ticks: int = 4, seed: int = 31):
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=seed,
        stochastic_identity="cmp-bench-arch",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-bench-arch"),
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


def test_bench_15_architecture_matrix_shared_world() -> None:
    result = build_benchmark_scenario(BENCH_15_ARCHITECTURE_MATRIX, _base())
    assert all(item.condition_id.startswith("ac-") for item in result.definition.conditions)
    assert len(result.definition.conditions) >= 2
    fingerprints = {
        scenario_fingerprint(item.runner_config) for item in result.definition.conditions
    }
    assert len(fingerprints) == 1
    seeds = {item.runner_config.seed for item in result.definition.conditions}
    assert len(seeds) == 1
