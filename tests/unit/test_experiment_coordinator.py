"""Unit tests for experiment coordinator ordering."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.coordinator import ExperimentCoordinator, materialize_assignments
from experiments.models import ExperimentSeedMatrix
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=1,
        stochastic_identity="cmp-coord",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
        max_ticks=1,
    )


def test_materialize_assignments_order() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(1, 2), replicates_per_seed=2),
    )
    assignments = materialize_assignments(definition)
    assert len(assignments) == 8  # 2 conditions × 2 seeds × 2 replicates
    keys = [
        (a.condition_ordinal, a.seed_ordinal, a.replicate_index) for a in assignments
    ]
    assert keys == sorted(keys)


@pytest.mark.asyncio
async def test_coordinator_runs_all_arms() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(3,), replicates_per_seed=1),
    )
    coordinator = ExperimentCoordinator(definition)
    results = await coordinator.run_all()
    assert len(results) == 2
    assert {item.assignment.condition_id for item in results} == {
        "a-reference",
        "a-reconstructive",
    }
    assert all(item.runner_result.ticks_committed == 1 for item in results)
