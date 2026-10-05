"""Channel-active wiring for dependency_care (no behavior change yet)."""

from __future__ import annotations

from dataclasses import replace

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V28,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_dependency_care_spec,
    example_population_lifecycle_spec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _config():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    base = base_runner_config_from_scenario(
        seed=2803,
        stochastic_identity="cmp-v28-channel",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v28-channel"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=1,
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
    )


def test_dependency_care_channel_active_on_construction() -> None:
    import asyncio

    async def _run() -> None:
        runner = await SimulationRunner.from_config(_config())
        assert runner.engine.dependency_care_channel_active is True
        assert runner.engine.dependency_care_spec is not None

    asyncio.run(_run())


def test_dependency_care_channel_off_without_spec() -> None:
    import asyncio

    async def _run() -> None:
        body_a = alive_body("body-a")
        agent_a = AgentId("agent-a")
        base = base_runner_config_from_scenario(
            seed=1,
            stochastic_identity="cmp-channel-off",
            scenario=WorldScenarioSpec(
                world_id=WorldId("world-off"),
                revision=WorldRevision(0),
                physical_rules=default_physical_rules(),
                locations=(make_location(),),
                bodies=(body_a,),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=agent_a,
                    entity_id=body_a.entity_id,
                    cognition=AgentCognitionSpec(agent_id=agent_a),
                ),
            ),
            max_ticks=1,
        )
        runner = await SimulationRunner.from_config(base)
        assert runner.engine.dependency_care_channel_active is False
        assert runner.engine.dependency_care_spec is None

    asyncio.run(_run())
