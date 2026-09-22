"""Unit tests for experiment collector families."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.collectors import (
    collect_for_experiment,
    collect_memory_drift,
)
from experiments.coordinator import ExperimentCoordinator
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
        stochastic_identity="cmp-collect",
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


@pytest.mark.asyncio
async def test_collectors_dispatch_by_experiment_family() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(2,), replicates_per_seed=1),
    )
    results = await ExperimentCoordinator(definition).run_all()
    assert len(results) == 2
    for arm in results:
        docs = collect_for_experiment(arm)
        families = {doc.family for doc in docs}
        assert "summary" in families
        assert "trajectory" in families
        assert "memory_drift" in families
        drift = collect_memory_drift(arm)
        assert drift.family == "memory_drift"
        assert "memory_mode" in dict(drift.fields)
        for doc in docs:
            assert doc.schema_version == "experiment-collector-v1"
            assert "is_false" not in dict(doc.fields)
            assert not any("truth" in key for key, _ in doc.fields)


@pytest.mark.asyncio
async def test_coordinator_attaches_metrics() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(4,), replicates_per_seed=1),
    )
    results = await ExperimentCoordinator(definition).run_all()
    assert all(len(item.metrics) >= 2 for item in results)
