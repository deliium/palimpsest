"""Operational infrastructure travel, capacity, production, and exposure effects."""

from __future__ import annotations

import pytest

from world._infrastructure import (
    effective_body_capacity,
    effective_exposure_scale,
    effective_item_capacity,
    effective_resource_regen_delta,
    effective_store_capacity,
    effective_travel_duration,
    effective_travel_fatigue,
)
from world.identifiers import EntityId
from world.infrastructure import (
    BASE_STORE_CAPACITY,
    MAX_INFRA_BODY_BONUS,
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    catalog_row,
    mint_infrastructure_id,
)

pytestmark = pytest.mark.unit


def _asset(
    kind: InfrastructureKind,
    *,
    location: str = "loc-a",
    endpoint: str | None = None,
    project: str = "proj-1",
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    integrity: float = 1.0,
    linked_structure: str | None = "struct-1",
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
    topology = (
        InfrastructureTopology.EDGE
        if kind is InfrastructureKind.ROAD
        else InfrastructureTopology.NODE
    )
    return InfrastructureAsset(
        asset_id=asset_id,
        kind=kind,
        topology=topology,
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=endpoint_id,
        linked_structure_id=(
            None if linked_structure is None else EntityId(linked_structure)
        ),
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )


def test_travel_road_shortens_duration_and_fatigue() -> None:
    road = _asset(
        InfrastructureKind.ROAD,
        location="loc-a",
        endpoint="loc-b",
        project="road-1",
    )
    assets = {road.asset_id: road}
    assert effective_travel_duration(
        assets,
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_duration=3,
    ) == 2
    assert effective_travel_fatigue(
        assets,
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_fatigue=4.0,
    ) == 3.0


def test_travel_destroyed_road_ignored_and_duration_floor() -> None:
    road = _asset(
        InfrastructureKind.ROAD,
        location="loc-a",
        endpoint="loc-b",
        project="road-1",
        status=InfrastructureStatus.DESTROYED,
        integrity=0.0,
    )
    assets = {road.asset_id: road}
    assert effective_travel_duration(
        assets,
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_duration=1,
    ) == 1
    live = _asset(
        InfrastructureKind.ROAD,
        location="loc-a",
        endpoint="loc-b",
        project="road-2",
    )
    assert effective_travel_duration(
        {live.asset_id: live},
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_duration=1,
    ) == 1


def test_travel_bridge_fatigue_from_origin() -> None:
    bridge = _asset(InfrastructureKind.BRIDGE, location="loc-a", project="bridge-1")
    assets = {bridge.asset_id: bridge}
    assert effective_travel_fatigue(
        assets,
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        base_fatigue=5.0,
    ) == 3.0


def test_travel_channel_off_legacy() -> None:
    assert (
        effective_travel_duration(
            None,
            origin_id=EntityId("loc-a"),
            destination_id=EntityId("loc-b"),
            base_duration=4,
        )
        == 4
    )
    assert (
        effective_travel_fatigue(
            None,
            origin_id=EntityId("loc-a"),
            destination_id=EntityId("loc-b"),
            base_fatigue=2.5,
        )
        == 2.5
    )


def test_capacity_shelter_body_bonus_and_destroyed_inert() -> None:
    shelter = _asset(
        InfrastructureKind.LARGE_SHELTER, location="loc-a", project="shelter-1"
    )
    assert effective_body_capacity(
        {shelter.asset_id: shelter},
        location_id=EntityId("loc-a"),
        base_capacity=4,
    ) == 6
    destroyed = _asset(
        InfrastructureKind.LARGE_SHELTER,
        location="loc-a",
        project="shelter-2",
        status=InfrastructureStatus.DESTROYED,
        integrity=0.0,
    )
    assert effective_body_capacity(
        {destroyed.asset_id: destroyed},
        location_id=EntityId("loc-a"),
        base_capacity=4,
    ) == 4


def test_capacity_item_bonus_and_body_clamp() -> None:
    trade = _asset(InfrastructureKind.TRADE_POST, location="loc-a", project="trade-1")
    assert effective_item_capacity(
        {trade.asset_id: trade},
        location_id=EntityId("loc-a"),
        base_capacity=3,
    ) == 5
    extras = []
    for index in range(6):
        extras.append(
            _asset(
                InfrastructureKind.LARGE_SHELTER,
                location="loc-a",
                project=f"shelter-{index}",
                linked_structure=f"struct-{index}",
            )
        )
    assets = {asset.asset_id: asset for asset in extras}
    assert (
        effective_body_capacity(
            assets, location_id=EntityId("loc-a"), base_capacity=1
        )
        == 1 + MAX_INFRA_BODY_BONUS
    )


def test_production_irrigation_regen_delta() -> None:
    irrigation = _asset(
        InfrastructureKind.IRRIGATION, location="loc-a", project="irr-1"
    )
    row = catalog_row(InfrastructureKind.IRRIGATION)
    assert effective_resource_regen_delta(
        {irrigation.asset_id: irrigation},
        location_id=EntityId("loc-a"),
    ) == pytest.approx(row.resource_regen_delta)
    destroyed = _asset(
        InfrastructureKind.IRRIGATION,
        location="loc-a",
        project="irr-2",
        status=InfrastructureStatus.DESTROYED,
        integrity=0.0,
    )
    assert (
        effective_resource_regen_delta(
            {destroyed.asset_id: destroyed},
            location_id=EntityId("loc-a"),
        )
        == 0.0
    )


def test_production_storage_max_ceiling() -> None:
    storage = _asset(
        InfrastructureKind.STORAGE,
        location="loc-a",
        project="store-1",
        linked_structure="struct-store",
    )
    capacity = effective_store_capacity(
        {storage.asset_id: storage},
        location_id=EntityId("loc-a"),
        linked_structure_id=EntityId("struct-store"),
    )
    assert capacity == BASE_STORE_CAPACITY + 3
    assert (
        effective_store_capacity(
            {storage.asset_id: storage},
            location_id=EntityId("loc-a"),
            linked_structure_id=None,
        )
        is None
    )


def test_exposure_marker_and_stacking() -> None:
    marker = _asset(
        InfrastructureKind.COMMUNICATION_MARKER,
        location="loc-a",
        project="marker-1",
    )
    scale = effective_exposure_scale(
        {marker.asset_id: marker},
        location_id=EntityId("loc-a"),
    )
    assert scale == pytest.approx(0.5)
    shelter = _asset(
        InfrastructureKind.LARGE_SHELTER,
        location="loc-a",
        project="shelter-1",
        linked_structure="struct-shelter",
    )
    stacked = effective_exposure_scale(
        {marker.asset_id: marker, shelter.asset_id: shelter},
        location_id=EntityId("loc-a"),
    )
    assert stacked == pytest.approx(0.5 * 0.75)
    destroyed = _asset(
        InfrastructureKind.COMMUNICATION_MARKER,
        location="loc-a",
        project="marker-2",
        status=InfrastructureStatus.DESTROYED,
        integrity=0.0,
    )
    assert (
        effective_exposure_scale(
            {destroyed.asset_id: destroyed},
            location_id=EntityId("loc-a"),
        )
        == 1.0
    )
