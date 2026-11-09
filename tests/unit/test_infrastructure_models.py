"""Infrastructure asset records, identity minting, and WorldState attachment."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import make_location, weather_for_locations
from world._infrastructure import (
    index_infrastructure,
    insert_infrastructure_asset,
    replace_infrastructure_asset,
)
from world._state import WorldState, rebuild_world_state
from world.identifiers import EntityId, WorldRevision
from world.infrastructure import (
    INFRASTRUCTURE_ID_PREFIX,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    mint_infrastructure_id,
    normalize_edge_endpoints,
)
from world.production import StructureKind

pytestmark = pytest.mark.unit


def _node_asset(
    *,
    kind: InfrastructureKind = InfrastructureKind.BRIDGE,
    location: str = "loc-a",
    project: str = "proj-1",
    tick: int = 3,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    integrity: float = 1.0,
) -> InfrastructureAsset:
    location_id = EntityId(location)
    project_id = EntityId(project)
    asset_id = mint_infrastructure_id(
        kind=kind,
        location_id=location_id,
        endpoint_location_id=None,
        created_tick=tick,
        project_id=project_id,
    )
    return InfrastructureAsset(
        asset_id=asset_id,
        kind=kind,
        topology=InfrastructureTopology.NODE,
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=None,
        linked_structure_id=None,
        linked_project_id=project_id,
        created_tick=tick,
        last_maintained_tick=tick,
    )


def _edge_asset(
    *,
    left: str = "loc-a",
    right: str = "loc-b",
    project: str = "proj-road",
    tick: int = 5,
) -> InfrastructureAsset:
    location_id = EntityId(left)
    endpoint = EntityId(right)
    project_id = EntityId(project)
    asset_id = mint_infrastructure_id(
        kind=InfrastructureKind.ROAD,
        location_id=location_id,
        endpoint_location_id=endpoint,
        created_tick=tick,
        project_id=project_id,
    )
    return InfrastructureAsset(
        asset_id=asset_id,
        kind=InfrastructureKind.ROAD,
        topology=InfrastructureTopology.EDGE,
        status=InfrastructureStatus.OPERATIONAL,
        integrity=1.0,
        location_id=location_id,
        endpoint_location_id=endpoint,
        linked_structure_id=EntityId("struct-road"),
        linked_project_id=project_id,
        created_tick=tick,
        last_maintained_tick=tick,
    )


def test_structure_kind_extensions_exist() -> None:
    assert StructureKind.ROAD.value == "road"
    assert StructureKind.IRRIGATION.value == "irrigation"
    assert StructureKind.TRADE_POST.value == "trade_post"


def test_node_and_edge_assets_validate() -> None:
    node = _node_asset()
    assert node.topology is InfrastructureTopology.NODE
    assert node.endpoint_location_id is None
    edge = _edge_asset(left="loc-b", right="loc-a")
    assert edge.location_id.value == "loc-a"
    assert edge.endpoint_location_id is not None
    assert edge.endpoint_location_id.value == "loc-b"


def test_destroyed_requires_zero_integrity() -> None:
    with pytest.raises(ValueError, match="infrastructure_destroyed_integrity"):
        _node_asset(status=InfrastructureStatus.DESTROYED, integrity=0.1)
    destroyed = _node_asset(status=InfrastructureStatus.DESTROYED, integrity=0.0)
    assert destroyed.integrity == 0.0


def test_edge_requires_distinct_endpoints() -> None:
    with pytest.raises(ValueError, match="infrastructure_edge_endpoints"):
        mint_infrastructure_id(
            kind=InfrastructureKind.ROAD,
            location_id=EntityId("loc-a"),
            endpoint_location_id=EntityId("loc-a"),
            created_tick=1,
            project_id=EntityId("proj-1"),
        )
    with pytest.raises(ValueError, match="infrastructure_invalid_topology"):
        InfrastructureAsset(
            asset_id=EntityId(f"{INFRASTRUCTURE_ID_PREFIX}{'0' * 32}"),
            kind=InfrastructureKind.BRIDGE,
            topology=InfrastructureTopology.EDGE,
            status=InfrastructureStatus.OPERATIONAL,
            integrity=1.0,
            location_id=EntityId("loc-a"),
            endpoint_location_id=EntityId("loc-b"),
            linked_structure_id=None,
            linked_project_id=EntityId("proj-1"),
            created_tick=1,
            last_maintained_tick=1,
        )


def test_mint_is_permutation_stable_and_prefixed() -> None:
    left = mint_infrastructure_id(
        kind=InfrastructureKind.ROAD,
        location_id=EntityId("loc-a"),
        endpoint_location_id=EntityId("loc-b"),
        created_tick=9,
        project_id=EntityId("proj-x"),
    )
    right = mint_infrastructure_id(
        kind=InfrastructureKind.ROAD,
        location_id=EntityId("loc-b"),
        endpoint_location_id=EntityId("loc-a"),
        created_tick=9,
        project_id=EntityId("proj-x"),
    )
    assert left == right
    assert left.value.startswith(INFRASTRUCTURE_ID_PREFIX)
    other = mint_infrastructure_id(
        kind=InfrastructureKind.BRIDGE,
        location_id=EntityId("loc-a"),
        endpoint_location_id=None,
        created_tick=9,
        project_id=EntityId("proj-x"),
    )
    assert other != left
    a, b = normalize_edge_endpoints(EntityId("loc-z"), EntityId("loc-a"))
    assert (a.value, b.value) == ("loc-a", "loc-z")


def test_insert_collision_and_rebuild() -> None:
    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    asset = _edge_asset()
    indexed = index_infrastructure(
        (asset,),
        location_ids={loc_a.entity_id: loc_a, loc_b.entity_id: loc_b},
    )
    assert indexed is not None
    with pytest.raises(ValueError, match="infrastructure_id_collision"):
        insert_infrastructure_asset(indexed, asset)
    state = WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        weather=weather_for_locations((loc_a, loc_b)),
        infrastructure=(asset,),
    )
    assert state.infrastructure is not None
    assert asset.asset_id in state.infrastructure
    rebuilt = rebuild_world_state(state)
    assert rebuilt.infrastructure is not None
    assert rebuilt.infrastructure[asset.asset_id] == asset
    off = WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        weather=weather_for_locations((loc_a, loc_b)),
    )
    assert off.infrastructure is None
    empty = WorldState(
        WorldRevision(0),
        locations=(loc_a, loc_b),
        weather=weather_for_locations((loc_a, loc_b)),
        infrastructure=(),
    )
    assert empty.infrastructure == {}
    damaged = InfrastructureAsset(
        asset_id=asset.asset_id,
        kind=asset.kind,
        topology=asset.topology,
        status=InfrastructureStatus.DAMAGED,
        integrity=0.5,
        location_id=asset.location_id,
        endpoint_location_id=asset.endpoint_location_id,
        linked_structure_id=asset.linked_structure_id,
        linked_project_id=asset.linked_project_id,
        created_tick=asset.created_tick,
        last_maintained_tick=asset.last_maintained_tick,
    )
    replaced = replace_infrastructure_asset(state.infrastructure, damaged)
    assert replaced[asset.asset_id].status is InfrastructureStatus.DAMAGED
