"""Seasonal scarcity scenario and an analysis-only dynamics count."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from agents.models import (
    AgentId,
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
    require_stochastic,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V14,
    AgentCognitionSpec,
    AgentRunnerSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    WorldScenarioSpec,
)
from world.environment import scarcity_scenario_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import (
    AgentBody,
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
    ResourceKind,
    TemperatureCelsius,
    Thirst,
    UnitInterval,
    WeatherCondition,
)

_LOG: Final[logging.Logger] = logging.getLogger("experiments.catalog")
ENVIRONMENTAL_DYNAMICS_METRIC_VERSION: Final[str] = "environmental_dynamics@1"


def count_environmental_dynamics(events: Sequence[object]) -> dict[str, int]:
    """Count season changes and depletions from the objective log only."""
    season_changes = 0
    depletions = 0
    for event in events:
        kind = getattr(getattr(event, "details", None), "kind", None)
        if kind == "season_changed":
            season_changes += 1
        elif kind == "resource_node_depleted":
            depletions += 1
    return {
        "season_change_count": season_changes,
        "depletion_count": depletions,
    }


def seasonal_scarcity_scenario(
    *,
    seed: int = 11,
    max_ticks: int = 16,
) -> ExperimentDefinition:
    """One location, one food node, and two arms that share the seed."""
    spec = scarcity_scenario_dynamics()
    owner = AgentId("agent-1")
    location_id = EntityId("loc-1")
    body = AgentBody(
        entity_id=EntityId("body-1"),
        location_id=location_id,
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )
    scenario = WorldScenarioSpec(
        world_id=WorldId("world-scarcity"),
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            Location(
                entity_id=location_id,
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
        resources=(
            Resource(
                entity_id=EntityId("res-food"),
                name="Cache",
                kind=ResourceKind.FOOD,
                location_id=location_id,
                quantity=1.0,
                maximum_quantity=1.0,
                regeneration_per_tick=1.0,
                unit="portions",
            ),
        ),
        weather=(Weather(location_id=location_id, condition=WeatherCondition.CLEAR),),
    )
    goal = Goal(
        goal_id=GoalId("goal-preserve"),
        owner_id=owner,
        description="preserve life through the scarce season",
        priority=0.8,
        status=GoalStatus.ACTIVE,
        horizon=GoalHorizon.LONG_TERM,
        outcome=GoalOutcome(kind=GoalOutcomeKind.PRESERVE_LIFE),
    )
    shared = SimulationRunnerConfig(
        seed=seed,
        stochastic_identity=require_stochastic("cmp-scarcity"),
        scenario=scenario,
        agents=(
            AgentRunnerSpec(
                agent_id=owner,
                entity_id=EntityId("body-1"),
                cognition=AgentCognitionSpec(agent_id=owner),
                initial_goals=(goal,),
            ),
        ),
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        schema_version=RUNNER_SCHEMA_VERSION_V14,
        environmental_dynamics=spec,
    )
    learned = SimulationRunnerConfig(
        seed=shared.seed,
        stochastic_identity=shared.stochastic_identity,
        scenario=shared.scenario,
        agents=shared.agents,
        stop_policy=shared.stop_policy,
        schema_version=shared.schema_version,
        environmental_dynamics=spec,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
    )
    for arm in ("learned", "naive"):
        _LOG.info(
            "environment_scenario arm=%s season_length=%s",
            arm,
            spec.season_length_ticks,
        )
    return ExperimentDefinition(
        experiment_id="experiment-u-seasonal-scarcity",
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=ExperimentSeedMatrix(seeds=(seed,)),
        conditions=(
            ExperimentCondition(
                condition_id="u-learned",
                label_code="predictive_world_model",
                runner_config=learned,
            ),
            ExperimentCondition(
                condition_id="u-naive",
                label_code="world_model_disabled",
                runner_config=shared,
            ),
        ),
        paired_world_group="experiment-u-seasonal-scarcity-world",
    )
