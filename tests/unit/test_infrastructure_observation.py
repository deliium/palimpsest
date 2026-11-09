"""Colocated infrastructure observation without score leakage."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import alive_body, make_location, weather_for_locations
from world._perception import PerceptionService
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.infrastructure import (
    INFRASTRUCTURE_FORBIDDEN_FIELDS,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    mint_infrastructure_id,
)
from world.observations import ObservationContext, ObservedInfrastructure
from world.production import Structure, StructureKind

pytestmark = pytest.mark.unit


def _asset(
    *,
    kind: InfrastructureKind,
    location: str,
    endpoint: str | None = None,
    project: str = "proj-1",
) -> InfrastructureAsset:
    location_id = EntityId(location)
    endpoint_id = None if endpoint is None else EntityId(endpoint)
    project_id = EntityId(project)
    asset_id = mint_infrastructure_id(
        kind=kind,
        location_id=location_id,
        endpoint_location_id=endpoint_id,
        created_tick=1,
        project_id=project_id,
    )
    return InfrastructureAsset(
        asset_id=asset_id,
        kind=kind,
        topology=(
            InfrastructureTopology.EDGE
            if endpoint is not None
            else InfrastructureTopology.NODE
        ),
        status=InfrastructureStatus.OPERATIONAL,
        integrity=1.0,
        location_id=location_id,
        endpoint_location_id=endpoint_id,
        linked_structure_id=EntityId("struct-1"),
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )


def test_observation_colocation_and_edge_visibility() -> None:
    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    bridge = _asset(kind=InfrastructureKind.BRIDGE, location="loc-a", project="b1")
    road = _asset(
        kind=InfrastructureKind.ROAD,
        location="loc-a",
        endpoint="loc-b",
        project="r1",
    )
    state = WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=weather_for_locations((loc_a, loc_b)),
        structures=(
            Structure(
                entity_id=EntityId("struct-1"),
                location_id=EntityId("loc-a"),
                kind=StructureKind.BRIDGE,
                integrity=1.0,
                stored_quantity=0,
            ),
        ),
        infrastructure=(bridge, road),
    )
    service = PerceptionService(infrastructure_networks_active=True)
    observations = service.project(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=1),
    )
    assert len(observations) == 1
    kinds = {row.kind for row in observations[0].infrastructure}
    assert kinds == {"bridge", "road"}
    road_obs = next(
        row for row in observations[0].infrastructure if row.kind == "road"
    )
    assert road_obs.endpoint_present is True
    assert road_obs.topology == "edge"


def test_observation_channel_off_empty() -> None:
    loc = make_location("loc-a")
    bridge = _asset(kind=InfrastructureKind.BRIDGE, location="loc-a")
    state = WorldState(
        WorldRevision(0),
        locations=(loc,),
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=weather_for_locations((loc,)),
        infrastructure=(bridge,),
    )
    service = PerceptionService(infrastructure_networks_active=False)
    observations = service.project(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
        context=ObservationContext(tick=1),
    )
    assert observations[0].infrastructure == ()


def test_observation_forbid_list() -> None:
    observed = ObservedInfrastructure(
        asset_id=EntityId("infra-a"),
        kind="bridge",
        status="operational",
        integrity=1.0,
        topology="node",
    )
    for field in INFRASTRUCTURE_FORBIDDEN_FIELDS:
        assert field not in observed.__slots__
