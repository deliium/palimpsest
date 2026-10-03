"""Paired disabled and deterministic arms for owner-scoped semantic naming.

Two locations with researcher-canonical names, three agents, a depleting
forest resource. The builder accepts no language, lexicon, glossary, dialect,
or shared-name argument. Location names are not label seeds.
"""

from __future__ import annotations

import logging
from typing import Final

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
    RUNNER_SCHEMA_VERSION_V20,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SemanticNamingMode,
    SimulationRunnerConfig,
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

_LOG: Final[logging.Logger] = logging.getLogger("experiments.catalog")

_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    ("alice", "body-alice"),
    ("bob", "body-bob"),
    ("cy", "body-cy"),
)


def emergent_naming_scenario(
    *,
    seed: int = 29,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Disabled ``v4`` arm and deterministic ``v20`` arm on one shared world."""
    scenario = _scenario()
    identity = require_stochastic("cmp-emergent-naming")
    disabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=SemanticNamingMode.DISABLED,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        max_ticks=max_ticks,
    )
    enabled = _config(
        seed=seed,
        identity=identity,
        scenario=scenario,
        mode=SemanticNamingMode.DETERMINISTIC,
        schema_version=RUNNER_SCHEMA_VERSION_V20,
        max_ticks=max_ticks,
    )
    definition = ExperimentDefinition(
        experiment_id="experiment-aa-emergent-naming",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=(
            ExperimentCondition(
                condition_id="aa-disabled",
                label_code="semantic_naming_disabled",
                runner_config=disabled,
            ),
            ExperimentCondition(
                condition_id="aa-enabled",
                label_code="semantic_naming_deterministic",
                runner_config=enabled,
            ),
        ),
        paired_world_group="experiment-aa-emergent-naming-world",
    )
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.debug(
        "experiment_aa_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def _scenario() -> WorldScenarioSpec:
    forest = EntityId("loc-forest")
    clearing = EntityId("loc-clearing")
    return WorldScenarioSpec(
        world_id=WorldId("world-emergent-naming"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            _location(
                forest,
                name="Northern Forest",
                adjacent=(clearing,),
            ),
            _location(
                clearing,
                name="Clearing",
                adjacent=(forest,),
            ),
        ),
        bodies=tuple(
            _body(entity_id, location_id=forest) for _agent, entity_id in _AGENTS
        ),
        items=tuple(_food(entity_id) for _agent, entity_id in _AGENTS),
        resources=(
            Resource(
                entity_id=EntityId("food-forest"),
                name="forage",
                kind=ResourceKind.FOOD,
                location_id=forest,
                quantity=1.0,
                maximum_quantity=1.0,
                regeneration_per_tick=0.0,
            ),
        ),
        weather=(
            Weather(location_id=forest, condition=WeatherCondition.CLEAR),
            Weather(location_id=clearing, condition=WeatherCondition.CLEAR),
        ),
    )


def _config(
    *,
    seed: int,
    identity: str,
    scenario: WorldScenarioSpec,
    mode: SemanticNamingMode,
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
                    semantic_naming_mode=mode,
                ),
            )
            for agent_id, entity_id in _AGENTS
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=schema_version,
    )


def _location(
    entity_id: EntityId,
    *,
    name: str,
    adjacent: tuple[EntityId, ...],
) -> Location:
    return Location(
        entity_id=entity_id,
        name=name,
        adjacent=adjacent,
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _body(entity_id: str, *, location_id: EntityId) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=location_id,
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
