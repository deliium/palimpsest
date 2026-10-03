"""Paired disabled and deterministic arms for owner-scoped social conventions.

One clearing, three agents, day/night weather, modest food. Nothing in the
scenario names a tradition, ritual, or convention field.
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
    RUNNER_SCHEMA_VERSION_V18,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SocialConventionMode,
    WorldScenarioSpec,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
    Item,
    LifeStatus,
    Location,
    Resource,
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
    ItemKind,
    ItemLoad,
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

_AGENTS: tuple[tuple[str, str], ...] = (
    ("ada", "body-ada"),
    ("ben", "body-ben"),
    ("cy", "body-cy"),
)


def social_conventions_scenario(
    *,
    seed: int = 19,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Disabled ``v4`` arm and deterministic ``v18`` arm on one shared world."""
    scenario = _scenario()
    identity = require_stochastic("cmp-social-conventions")
    disabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=SocialConventionMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        max_ticks=max_ticks,
    )
    enabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=SocialConventionMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V18,
        max_ticks=max_ticks,
    )
    return ExperimentDefinition(
        experiment_id="experiment-y-social-conventions",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=(
            ExperimentCondition(
                condition_id="y-disabled",
                label_code="social_conventions_disabled",
                runner_config=disabled,
            ),
            ExperimentCondition(
                condition_id="y-enabled",
                label_code="social_conventions_deterministic",
                runner_config=enabled,
            ),
        ),
        paired_world_group="experiment-y-social-conventions-world",
    )


def _scenario() -> WorldScenarioSpec:
    clearing = EntityId("clearing")
    return WorldScenarioSpec(
        world_id=WorldId("world-social-conventions"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(_location(clearing),),
        bodies=tuple(_body(entity_id) for _agent, entity_id in _AGENTS),
        items=tuple(_food(entity_id) for _agent, entity_id in _AGENTS),
        resources=(
            Resource(
                entity_id=EntityId("food-clearing"),
                name="berries",
                kind=ResourceKind.FOOD,
                location_id=clearing,
                quantity=2.0,
                maximum_quantity=2.0,
                regeneration_per_tick=0.0,
            ),
        ),
        weather=(Weather(location_id=clearing, condition=WeatherCondition.CLEAR),),
    )


def _config(
    *,
    seed: int,
    identity: str,
    scenario: WorldScenarioSpec,
    mode: SocialConventionMode,
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
                    social_convention_mode=mode,
                ),
            )
            for agent_id, entity_id in _AGENTS
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=schema_version,
    )


def _location(entity_id: EntityId) -> Location:
    return Location(
        entity_id=entity_id,
        name="Clearing",
        adjacent=(),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _body(entity_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId("clearing"),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(EntityId(f"food-{entity_id}"),),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _food(holder_id: str) -> Item:
    return Item(
        entity_id=EntityId(f"food-{holder_id}"),
        name="ration",
        kind=ItemKind.FOOD,
        load=ItemLoad(1),
        holder_id=EntityId(holder_id),
    )
