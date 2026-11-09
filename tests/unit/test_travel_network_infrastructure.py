"""V4-17 infrastructure quality/capacity helpers and no double counting."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._infrastructure import (
    edge_road_quality,
    node_bridge_quality,
    operational_bridge_capacity_bonus,
    operational_road_capacity_bonus,
    route_capacity_bonus,
    route_quality,
)
from world._state import WorldState
from world.environment import Season
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
)
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import derive_route_condition

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")
C = EntityId("loc-c")


def _asset(
    asset_id: str,
    kind: InfrastructureKind,
    *,
    integrity: float,
    location_id: EntityId = A,
    endpoint: EntityId | None = B,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
) -> InfrastructureAsset:
    return InfrastructureAsset(
        asset_id=EntityId(asset_id),
        kind=kind,
        topology=InfrastructureTopology.EDGE
        if kind is InfrastructureKind.ROAD
        else InfrastructureTopology.NODE,
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=endpoint if kind is InfrastructureKind.ROAD else None,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-1"),
        created_tick=0,
        last_maintained_tick=0,
    )


def _state(assets: tuple[InfrastructureAsset, ...]) -> WorldState:
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(A, "west"),
            LocationRegion(B, "east"),
            LocationRegion(C, "east"),
        ),
        routes=(RouteSpec(A, B, 2, 3.0), RouteSpec(B, C, 2, 3.0)),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    locations = (
        make_location("loc-a", adjacent=("loc-b",)),
        make_location("loc-b", adjacent=("loc-a", "loc-c")),
        make_location("loc-c", adjacent=("loc-b",)),
    )
    indexed = {asset.asset_id: asset for asset in assets}
    return WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=(alive_body("body-1", location_id="loc-a"),),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        infrastructure=indexed,
        regions_migration=spec,
    )


def test_road_bridge_quality_and_capacity() -> None:
    assets = {
        EntityId("infra-road"): _asset(
            "infra-road", InfrastructureKind.ROAD, integrity=0.8
        ),
        EntityId("infra-bridge"): _asset(
            "infra-bridge",
            InfrastructureKind.BRIDGE,
            integrity=0.4,
            location_id=B,
            endpoint=None,
        ),
    }
    assert edge_road_quality(assets, A, B) == pytest.approx(0.8)
    assert node_bridge_quality(assets, B) == pytest.approx(0.4)
    assert route_quality(assets, A, B) == pytest.approx(0.6)
    assert operational_road_capacity_bonus(assets, A, B) == 2
    assert operational_bridge_capacity_bonus(assets, B) == 1
    assert route_capacity_bonus(assets, A, B) == 3


def test_damaged_and_destroyed_assets_are_excluded() -> None:
    assets = {
        EntityId("infra-road"): _asset(
            "infra-road",
            InfrastructureKind.ROAD,
            integrity=0.2,
            status=InfrastructureStatus.DAMAGED,
        ),
        EntityId("infra-bridge"): _asset(
            "infra-bridge",
            InfrastructureKind.BRIDGE,
            integrity=0.0,
            location_id=A,
            endpoint=None,
            status=InfrastructureStatus.DESTROYED,
        ),
    }
    assert edge_road_quality(assets, A, B) == 0.0
    assert node_bridge_quality(assets, A) == 0.0
    assert route_quality(assets, A, B) == 0.0
    assert route_capacity_bonus(assets, A, B) == 0


def test_edge_isolation_for_bridge_incidence() -> None:
    bridge = _asset(
        "infra-bridge",
        InfrastructureKind.BRIDGE,
        integrity=0.7,
        location_id=C,
        endpoint=None,
    )
    assets = {bridge.asset_id: bridge}
    assert route_quality(assets, A, B) == 0.0
    assert route_quality(assets, B, C) == pytest.approx(0.7)


def test_non_mapping_asset_container_is_rejected() -> None:
    with pytest.raises(TypeError, match="assets must be a mapping"):
        route_quality((), A, B)  # type: ignore[arg-type]


def test_derivation_applies_infrastructure_once() -> None:
    road = _asset("infra-road", InfrastructureKind.ROAD, integrity=0.8)
    state = _state((road,))
    route = derive_route_condition(state, A, B, season=Season.WINTER, tick=0)
    # Base 2 -> road -1 -> 1; winter +2 -> 3. Not 2 or 4.
    assert route.duration_ticks == 3
    assert route.infrastructure_quality == pytest.approx(0.8)
    assert route.capacity == 10 - 2
