"""Paired disabled and deterministic arms for owner-scoped group formation.

Agents share a two-location world. Nothing in the scenario assigns a team.
"""

from __future__ import annotations

from agents.models import AgentId
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V16,
    AgentCognitionSpec,
    AgentRunnerSpec,
    GroupFormationMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    LifeStatus,
    Location,
    Weather,
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
    WeatherCondition,
)

_AGENTS: tuple[tuple[str, str, str], ...] = (
    ("north_a", "body-north-a", "north"),
    ("north_b", "body-north-b", "north"),
    ("south_a", "body-south-a", "south"),
    ("south_b", "body-south-b", "south"),
    ("lone", "body-lone", "north"),
)


def emergent_group_scenario(
    *,
    seed: int = 11,
    max_ticks: int = 4,
) -> ExperimentDefinition:
    """Disabled ``v4`` arm and deterministic ``v16`` arm on one shared world."""
    scenario = _scenario()
    identity = require_stochastic("cmp-emergent-groups")
    disabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=GroupFormationMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        max_ticks=max_ticks,
    )
    enabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=GroupFormationMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V16,
        max_ticks=max_ticks,
    )
    return ExperimentDefinition(
        experiment_id="experiment-w-emergent-groups",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=(
            ExperimentCondition(
                condition_id="w-disabled",
                label_code="group_formation_disabled",
                runner_config=disabled,
            ),
            ExperimentCondition(
                condition_id="w-enabled",
                label_code="group_formation_deterministic",
                runner_config=enabled,
            ),
        ),
        paired_world_group="experiment-w-emergent-groups-world",
    )


def _scenario() -> WorldScenarioSpec:
    north = EntityId("north")
    south = EntityId("south")
    return WorldScenarioSpec(
        world_id=WorldId("world-emergent-groups"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            _location(north, "North", south),
            _location(south, "South", north),
        ),
        bodies=tuple(
            _body(entity_id, location_id) for _agent, entity_id, location_id in _AGENTS
        ),
        weather=(
            Weather(location_id=north, condition=WeatherCondition.CLEAR),
            Weather(location_id=south, condition=WeatherCondition.CLEAR),
        ),
    )


def _config(
    *,
    seed: int,
    identity: str,
    scenario: WorldScenarioSpec,
    mode: GroupFormationMode,
    schema_version: str,
    max_ticks: int,
) -> SimulationRunnerConfig:
    return SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=identity,
        scenario=scenario,
        agents=tuple(
            AgentRunnerSpec(
                agent_id=AgentId(agent_id),
                entity_id=EntityId(entity_id),
                cognition=AgentCognitionSpec(
                    agent_id=AgentId(agent_id),
                    group_formation_mode=mode,
                ),
            )
            for agent_id, entity_id, _location_id in _AGENTS
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=schema_version,
    )


def _location(entity_id: EntityId, name: str, neighbor: EntityId) -> Location:
    return Location(
        entity_id=entity_id,
        name=name,
        adjacent=(neighbor,),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _body(entity_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
