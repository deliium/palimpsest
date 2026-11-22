"""Off-gate experiment ``disease_mechanics@1`` (paired transmission arms)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from experiments.reference_scenario import _alive_body
from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V58,
    AgentCognitionSpec,
    AgentRunnerSpec,
    ImaginationMode,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_collective_projects_spec,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import Location, Weather, default_physical_rules
from world.production import example_production_catalog
from world.values import (
    BodyCapacity,
    ItemCapacity,
    TemperatureCelsius,
    UnitInterval,
    WeatherCondition,
)

__all__ = [
    "DISEASE_MECHANICS_EXPERIMENT_ID",
    "disease_mechanics_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.disease_scenario")

DISEASE_MECHANICS_EXPERIMENT_ID: Final[str] = "disease_mechanics@1"
_SETTLED = "loc-settled"
_REMOTE = "loc-remote"
_BODY_A = "body-a"
_BODY_B = "body-b"
_BODY_C = "body-c"


def _location(entity_id: str, name: str, *, adjacent: tuple[str, ...]) -> Location:
    return Location(
        entity_id=EntityId(entity_id),
        name=name,
        adjacent=tuple(EntityId(item) for item in adjacent),
        body_capacity=BodyCapacity(8),
        item_capacity=ItemCapacity(16),
        base_temperature=TemperatureCelsius(20.0),
        shelter_factor=UnitInterval(0.0),
        visibility_factor=UnitInterval(1.0),
    )


def _weather(location_id: str) -> Weather:
    return Weather(
        location_id=EntityId(location_id),
        condition=WeatherCondition.CLEAR,
    )


def _agents_for(scenario: WorldScenarioSpec) -> tuple[AgentRunnerSpec, ...]:
    catalog = example_production_catalog()
    agents: list[AgentRunnerSpec] = []
    for index, body in enumerate(scenario.bodies):
        agent_id = AgentId(f"agent-{index + 1}")
        agents.append(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(
                    agent_id=agent_id,
                    production_catalog=catalog,
                    imagination_mode=ImaginationMode.DISABLED,
                ),
            )
        )
    return tuple(agents)


def _disease_spec(*, transmission_milli: int) -> DiseaseMechanicsSpec:
    # Lexically first colocated founder starts latent; roster is shared.
    return DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=(EntityId(_BODY_A),),
        exposure_chance_milli=1000,
        transmission_chance_milli=transmission_milli,
        symptom_chance_milli=1000,
        mortality_chance_milli=0,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )


def _arm(
    base: SimulationRunnerConfig,
    *,
    max_ticks: int,
    transmission_milli: int,
) -> SimulationRunnerConfig:
    scenario = WorldScenarioSpec(
        world_id=base.scenario.world_id,
        revision=WorldRevision(0),
        physical_rules=default_physical_rules(),
        locations=(
            _location(_SETTLED, "Settled", adjacent=(_REMOTE,)),
            _location(_REMOTE, "Remote", adjacent=(_SETTLED,)),
        ),
        bodies=(
            _alive_body(_BODY_A, location_id=_SETTLED, hunger=0.0, thirst=0.0),
            _alive_body(_BODY_B, location_id=_SETTLED, hunger=0.0, thirst=0.0),
            _alive_body(_BODY_C, location_id=_REMOTE, hunger=0.0, thirst=0.0),
        ),
        weather=(_weather(_SETTLED), _weather(_REMOTE)),
        items=(),
        resources=(),
        artifacts=(),
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V58,
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        scenario=scenario,
        agents=_agents_for(scenario),
        v3_capability_flags=V3CapabilityFlags(),
        v4_capability_flags=V4CapabilityFlags(
            infrastructure_networks=True,
            epidemics=True,
        ),
        collective_projects=example_collective_projects_spec(),
        regions_migration=None,
        measurement_instruments=None,
        disease_mechanics=_disease_spec(transmission_milli=transmission_milli),
        public_goods=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        population_lifecycle=None,
        bounded_experimentation=None,
    )


def disease_mechanics_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 8,
) -> ExperimentDefinition:
    """Paired no-transmission vs contact-enabled disease arms."""
    if type(base) is not SimulationRunnerConfig:
        _LOG.warning(
            "disease_scenario_invalid reason_code=base_type experiment_id=%s",
            DISEASE_MECHANICS_EXPERIMENT_ID,
        )
        raise TypeError("disease_scenario_base_invalid")
    if isinstance(max_ticks, bool) or type(max_ticks) is not int or max_ticks < 8:
        _LOG.warning(
            "disease_scenario_invalid reason_code=min_ticks experiment_id=%s",
            DISEASE_MECHANICS_EXPERIMENT_ID,
        )
        raise ValueError("disease_scenario_min_ticks")
    if type(base.scenario.world_id) is not WorldId:
        _LOG.warning(
            "disease_scenario_invalid reason_code=world_id experiment_id=%s",
            DISEASE_MECHANICS_EXPERIMENT_ID,
        )
        raise ValueError("disease_scenario_base_invalid")

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    no_transmission = _arm(base, max_ticks=max_ticks, transmission_milli=0)
    contact_enabled = _arm(base, max_ticks=max_ticks, transmission_milli=1000)
    conditions = (
        ExperimentCondition(
            condition_id="no-transmission",
            label_code="disease_mechanics_no_transmission",
            runner_config=no_transmission,
        ),
        ExperimentCondition(
            condition_id="contact-enabled",
            label_code="disease_mechanics_contact_enabled",
            runner_config=contact_enabled,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        DISEASE_MECHANICS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=DISEASE_MECHANICS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{DISEASE_MECHANICS_EXPERIMENT_ID}-world",
    )
