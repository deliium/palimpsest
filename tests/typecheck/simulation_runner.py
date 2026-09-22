"""Positive typing fixtures for simulation runner configuration."""

from __future__ import annotations

from simulation.models import StochasticIdentity
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    MemoryMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    default_physical_rules,
)
from world.values import (
    BodyCapacity,
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemCapacity,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
)


def _sample_config() -> SimulationRunnerConfig:
    from agents.models import AgentId

    agent_id = AgentId("agent-1")
    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    return SimulationRunnerConfig(
        seed=1,
        stochastic_identity=StochasticIdentity("cmp-typecheck"),
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                Location(
                    entity_id=EntityId("loc-1"),
                    name="Camp",
                    adjacent=(),
                    body_capacity=BodyCapacity(8),
                    item_capacity=ItemCapacity(16),
                    base_temperature=TemperatureCelsius(20.0),
                    shelter_factor=UnitInterval(0.0),
                    visibility_factor=UnitInterval(1.0),
                ),
            ),
            bodies=(body,),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent_id, memory_mode=MemoryMode.REFERENCE
                ),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=1),
    )


def _round_trip_fingerprint() -> str:
    config = _sample_config()
    decoded = decode_runner_config(encode_runner_config(config))
    return runner_config_fingerprint(decoded)
