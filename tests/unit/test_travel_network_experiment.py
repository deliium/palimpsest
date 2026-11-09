"""V4-17 off-gate travel_network@1 registration and scenario shape."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    OFF_GATE_MATRIX_EXPERIMENT_IDS,
    base_runner_config_from_scenario,
    experiment_travel_network,
)
from experiments.travel_network_scenario import (
    TRAVEL_NETWORK_EXPERIMENT_ID,
    travel_network_scenario,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    regions = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "west"),
            LocationRegion(EntityId("loc-b"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    base = base_runner_config_from_scenario(
        seed=19,
        stochastic_identity="travel-network",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-travel-experiment"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(
                make_location("loc-a", adjacent=("loc-b",)),
                make_location("loc-b", adjacent=("loc-a",)),
            ),
            bodies=(body,),
            weather=(make_weather("loc-a"), make_weather("loc-b")),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=4,
    )
    return replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=V3CapabilityFlags(multi_polity_migration=True),
        regions_migration=regions,
    )


def test_experiment_is_registered_off_gate() -> None:
    assert TRAVEL_NETWORK_EXPERIMENT_ID == "travel_network@1"
    assert "travel_network@1" in OFF_GATE_MATRIX_EXPERIMENT_IDS
    definition = experiment_travel_network(_base())
    assert definition.experiment_id == "travel_network@1"
    assert len(definition.conditions) == 2
    control, treatment = definition.conditions
    assert control.runner_config.v4_capability_flags.infrastructure_networks is False
    assert treatment.runner_config.v4_capability_flags.infrastructure_networks is True
    assert control.runner_config.regions_migration is not None
    assert treatment.runner_config.regions_migration is not None


def test_scenario_is_deterministic_and_shares_environment() -> None:
    first = experiment_travel_network(_base())
    second = experiment_travel_network(_base())
    assert first == second
    control, treatment = first.conditions
    assert control.runner_config.environmental_dynamics == (
        treatment.runner_config.environmental_dynamics
    )
    assert control.runner_config.environmental_dynamics is not None
    assert control.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V56
    assert treatment.runner_config.schema_version == RUNNER_SCHEMA_VERSION_V56


def test_scenario_requires_regions() -> None:
    with pytest.raises(ValueError):
        travel_network_scenario(replace(_base(), regions_migration=None))
