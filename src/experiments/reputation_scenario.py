"""Split east and west starts for owner-scoped reputation.

The two locations share one symmetric edge and both have weather. Agents
start apart so they are not colocated at tick 0. Body ids and agent ids
stay distinct. This module does not run the reputation metric.
"""

from __future__ import annotations

from agents.models import AgentId
from experiments.reference_scenario import _alive_body, _reference_physical_rules
from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    MemoryMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import Location, Weather
from world.values import (
    BodyCapacity,
    ItemCapacity,
    TemperatureCelsius,
    UnitInterval,
    WeatherCondition,
)

DISTRIBUTED_REPUTATION_SCENARIO_ID = "distributed-reputation-east-west"


def distributed_reputation_scenario(
    *,
    seed: int = 251,
    stochastic_identity: str = "distributed-reputation",
) -> SimulationRunnerConfig:
    """Five agents, two start locations, one connecting edge."""
    east = _location("east", "East", "west")
    west = _location("west", "West", "east")
    starts = (
        ("east_a", "body-east-a", "east"),
        ("east_b", "body-east-b", "east"),
        ("focal", "body-focal", "east"),
        ("west_a", "body-west-a", "west"),
        ("west_b", "body-west-b", "west"),
    )
    agents = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            name=agent_id,
            cognition=AgentCognitionSpec(
                agent_id=AgentId(agent_id),
                memory_mode=MemoryMode.RECONSTRUCTIVE,
            ),
        )
        for agent_id, body_id, _location_id in starts
    )
    scenario = WorldScenarioSpec(
        world_id=WorldId(DISTRIBUTED_REPUTATION_SCENARIO_ID),
        revision=WorldRevision(0),
        physical_rules=_reference_physical_rules(),
        locations=(east, west),
        bodies=tuple(
            _alive_body(body_id, location_id=location_id)
            for _agent_id, body_id, location_id in starts
        ),
        weather=(
            Weather(location_id=EntityId("east"), condition=WeatherCondition.CLEAR),
            Weather(location_id=EntityId("west"), condition=WeatherCondition.CLEAR),
        ),
    )
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=StochasticIdentity(stochastic_identity),
        scenario=scenario,
        agents=agents,
        stop_policy=RunnerStopPolicy(max_ticks=4),
    )


def _location(entity_id: str, name: str, neighbor: str) -> Location:
    return Location(
        entity_id=EntityId(entity_id),
        name=name,
        adjacent=(EntityId(neighbor),),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )
