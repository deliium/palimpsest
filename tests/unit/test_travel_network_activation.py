"""V4-17 travel-network activation combinations and checkpoint priority."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine, select_checkpoint_schema
from simulation.models import SimulationRunConfig
from simulation.persistence import checkpoint_schema_for_production
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)

pytestmark = pytest.mark.unit


def _spec() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), "east"),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 3),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _engine(
    *, with_regions: bool, travel: bool, infrastructure: bool = True
) -> WorldEngine:
    bodies = (alive_body("body-1", location_id="loc-1"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-travel-activation"),
        revision=WorldRevision(0),
        locations=(
            make_location("loc-1", adjacent=("loc-2",)),
            make_location("loc-2", adjacent=("loc-1",)),
        ),
        bodies=bodies,
        weather=(make_weather("loc-1"), make_weather("loc-2")),
        registrations=(
            AgentRegistration(AgentId("agent-body-1"), bodies[0].entity_id),
        ),
        regions_migration=_spec() if with_regions else None,
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=17, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        collective_projects_active=infrastructure,
        infrastructure_networks_active=infrastructure,
        travel_network_active=travel,
    )


def test_activation_matrix() -> None:
    inactive = _engine(with_regions=False, travel=False, infrastructure=False)
    assert inactive.travel_network_active is False
    regions_only = _engine(with_regions=True, travel=False, infrastructure=False)
    assert regions_only.travel_network_active is False
    infrastructure_only = _engine(with_regions=False, travel=False, infrastructure=True)
    assert infrastructure_only.travel_network_active is False
    active = _engine(with_regions=True, travel=True, infrastructure=True)
    assert active.travel_network_active is True


def test_activation_requires_prerequisites() -> None:
    with pytest.raises(ValueError, match="travel_network_requires_infrastructure"):
        _engine(with_regions=True, travel=True, infrastructure=False)
    with pytest.raises(ValueError, match="travel_network_requires_regions"):
        _engine(with_regions=False, travel=True, infrastructure=True)


def test_activation_flag_is_exact_bool_and_immutable() -> None:
    with pytest.raises(TypeError, match="travel_network_active must be bool"):
        _engine(with_regions=True, travel=1)  # type: ignore[arg-type]
    engine = _engine(with_regions=True, travel=True)
    with pytest.raises(AttributeError):
        engine.travel_network_active = False  # type: ignore[misc]


def test_checkpoint_selection_prefers_travel_network() -> None:
    assert checkpoint_schema_for_production(
        production_active=False, travel_network_active=True
    ) == (27, "v25")
    assert checkpoint_schema_for_production(
        production_active=False,
        travel_network_active=True,
        infrastructure_networks_active=True,
    ) == (27, "v25")
    assert checkpoint_schema_for_production(
        production_active=False, infrastructure_networks_active=True
    ) == (23, "v21")
    assert checkpoint_schema_for_production(
        production_active=False, regions_migration_active=True
    ) == (21, "v19")
    assert select_checkpoint_schema(
        production_active=False,
        dynamics_active=False,
        travel_network_active=True,
    ) == (27, "v25")


def test_no_runner_schema_v57_is_accepted() -> None:
    assert "runner-config-v57" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
