"""Paired external-record arms: artifact channel versus memory-only.

One clearing, two agents, high visibility, low fatigue. Soft-forget uses the
existing sleep-consolidation path. No tradition, literacy, or culture fields.
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
    RUNNER_SCHEMA_VERSION_V19,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ArtifactInterpretationMode,
    ConsolidationMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    WorldScenarioSpec,
)
from world.artifacts import (
    ArtifactContent,
    ArtifactKind,
    ArtifactRelation,
    InformationArtifact,
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

_LOG: Final[logging.Logger] = logging.getLogger("experiments.external_artifacts")

SCARCE_RESOURCE_MARKS: Final[tuple[str, ...]] = ("food", "scarce")
SCARCE_RESOURCE_RELATIONS: Final[tuple[ArtifactRelation, ...]] = (
    ArtifactRelation(subject="food", predicate="at", object="clearing"),
)
SCENARIO_ARTIFACT_ID: Final[str] = "record-scarce-food"
OWNER_A_ID: Final[str] = "ada"
OWNER_B_ID: Final[str] = "ben"
_AGENTS: Final[tuple[tuple[str, str], ...]] = (
    (OWNER_A_ID, "body-ada"),
    (OWNER_B_ID, "body-ben"),
)


def external_artifacts_scenario(
    *,
    seed: int = 23,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """Artifact-channel and memory-only arms on one shared topology.

    Both arms set ``artifacts_enabled=true``, share seed/bodies/identity, keep
    visibility at ``1.0`` and fatigue at ``0.0``, and enable deterministic
    interpretation plus sleep consolidation for soft-forget.
    """
    identity = require_stochastic("cmp-external-artifacts")
    channel = _config(
        seed=seed,
        identity=identity,
        scenario=_scenario(seed_record=True),
        max_ticks=max_ticks,
        artifacts_enabled=True,
    )
    memory_only = _config(
        seed=seed,
        identity=identity,
        scenario=_scenario(seed_record=False),
        max_ticks=max_ticks,
        artifacts_enabled=True,
    )
    definition = ExperimentDefinition(
        experiment_id="experiment-z-external-artifacts",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=(
            ExperimentCondition(
                condition_id="artifact_channel",
                label_code="external_artifacts_channel",
                runner_config=channel,
            ),
            ExperimentCondition(
                condition_id="memory_only",
                label_code="external_artifacts_memory_only",
                runner_config=memory_only,
            ),
        ),
        paired_world_group="experiment-z-external-artifacts-world",
    )
    condition_ids = ",".join(
        condition.condition_id for condition in definition.conditions
    )
    _LOG.info(
        "experiment_z_built experiment_id=%s condition_ids=%s",
        definition.experiment_id,
        condition_ids,
    )
    return definition


def scarce_resource_record(*, author_id: str = "body-ada") -> InformationArtifact:
    """Locked scarce-resource cue record used by the artifact-channel arm."""
    return InformationArtifact(
        artifact_id=EntityId(SCENARIO_ARTIFACT_ID),
        kind=ArtifactKind.RECORD,
        author_id=EntityId(author_id),
        created_tick=0,
        content=ArtifactContent(
            marks=SCARCE_RESOURCE_MARKS,
            relations=SCARCE_RESOURCE_RELATIONS,
        ),
        content_revision=0,
        location_id=EntityId("clearing"),
    )


def _scenario(*, seed_record: bool) -> WorldScenarioSpec:
    clearing = EntityId("clearing")
    artifacts = (scarce_resource_record(),) if seed_record else ()
    return WorldScenarioSpec(
        world_id=WorldId("world-external-artifacts"),
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
                quantity=1.0,
                maximum_quantity=1.0,
                regeneration_per_tick=0.0,
            ),
        ),
        weather=(Weather(location_id=clearing, condition=WeatherCondition.CLEAR),),
        artifacts=artifacts,
    )


def _config(
    *,
    seed: int,
    identity: str,
    scenario: WorldScenarioSpec,
    max_ticks: int,
    artifacts_enabled: bool,
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
                    consolidation_mode=ConsolidationMode.DETERMINISTIC,
                    artifact_interpretation_mode=(
                        ArtifactInterpretationMode.DETERMINISTIC
                    ),
                ),
            )
            for agent_id, entity_id in _AGENTS
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=RUNNER_SCHEMA_VERSION_V19,
        artifacts_enabled=artifacts_enabled,
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
