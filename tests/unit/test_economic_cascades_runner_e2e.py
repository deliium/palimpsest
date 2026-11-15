# mypy: ignore-errors
"""Real runner-config-v56 run through the collector and cascade builder."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from experiments.collectors import assemble_arm_metric_bundle
from experiments.coordinator import ExperimentArmResult, materialize_assignments
from experiments.economic_cascades_scenario import economic_cascades_scenario
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    WorldScenarioSpec,
)
from simulation.runner_serialization import runner_config_fingerprint
from tests.physical_helpers import two_location_fixture
from tests.simulation_helpers import make_resource
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import ResourceKind

pytestmark = pytest.mark.unit

_CASCADE_FAMILIES = {
    "resource_loss_cascade",
    "route_closure_cascade",
    "infrastructure_destruction_cascade",
    "population_loss_cascade",
    "tool_shortage_cascade",
    "cascade_dependency_structure",
    "cascade_propagation",
    "cascade_coverage",
}


def _base_config():
    fixture = two_location_fixture(item_on_ground=False)
    boot = fixture.as_bootstrap()
    body = boot.bodies[0]
    agent_id = AgentId("agent-1")
    grain = make_resource(
        "res-grain",
        name="grain",
        kind=ResourceKind.FOOD,
        location_id="loc-1",
        quantity=3.0,
        maximum_quantity=5.0,
        regeneration_per_tick=0.0,
    )
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-economic-cascades-runner",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-economic-cascades-runner"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=boot.locations,
            bodies=(body,),
            items=boot.items,
            resources=(*boot.resources, grain),
            weather=boot.weather,
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=96,
    )


@pytest.mark.asyncio
async def test_runner_to_collector_emits_cascade_families() -> None:
    definition = economic_cascades_scenario(_base_config(), max_ticks=96)
    assignment = next(
        item
        for item in materialize_assignments(definition)
        if item.condition_id == "cascade-production"
    )
    async with await SimulationRunner.from_config(
        assignment.runner_config, run_id=assignment.run_id
    ) as runner:
        result = await runner.run()
        events = tuple(runner.engine.export_events().events)

    arm = ExperimentArmResult(
        assignment=assignment,
        runner_result=result,
        config_fingerprint=runner_config_fingerprint(assignment.runner_config),
        committed_events=events,
    )
    bundle = assemble_arm_metric_bundle(arm)
    families = {document.metric_family for document in bundle.documents}

    assert result.ticks_committed == 96
    assert _CASCADE_FAMILIES <= families
