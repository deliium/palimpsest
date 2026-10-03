"""Phenomenon panel wiring through experiment collectors."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario, experiment_a_memory
from experiments.collectors import collect_for_experiment, collect_phenomenon_panel
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
        stochastic_identity="cmp-panel-wire",
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
async def test_collect_for_experiment_attaches_phenomenon_panel() -> None:
    definition = experiment_a_memory(
        _base(),
        seed_matrix=ExperimentSeedMatrix(seeds=(3,), replicates_per_seed=1),
    )
    results = await ExperimentCoordinator(definition).run_all()
    assert results
    for arm in results:
        docs = collect_for_experiment(arm)
        families = {doc.family for doc in docs}
        assert "phenomenon_indicators" in families
        panel = collect_phenomenon_panel(arm)
        assert panel is not None
        assert panel.family == "phenomenon_indicators"
        fields = dict(panel.fields)
        assert fields["phenomenon_count"] == 18
        assert "emerged" not in fields
        assert "culture_emerged" not in fields
        assert "detected" not in fields
