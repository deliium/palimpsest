"""V4-17 infrastructure snapshot v2 route rows and v1 compatibility."""

from __future__ import annotations

import pytest

from simulation.infrastructure_codec import (
    decode_infrastructure_networks_snapshot,
    encode_infrastructure_networks_snapshot,
    finalize_infrastructure_networks_snapshot,
)
from simulation.infrastructure_models import (
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
    InfrastructureNetworksArtifactError,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
    TravelRouteRecord,
)
from simulation.infrastructure_paging import page_travel_routes

pytestmark = pytest.mark.unit

ROUTE = TravelRouteRecord(
    origin_location_id="loc-a",
    destination_location_id="loc-b",
    status="restricted",
    seasonal_availability="restricted",
    blockage_cause="seasonal",
    duration_ticks=3,
    fatigue_cost=4.5,
    capacity=6,
    risk=0.3,
    infrastructure_quality=0.4,
    as_of_tick=1,
)


def _summary(
    version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
) -> InfrastructureNetworksSummaryRecord:
    return InfrastructureNetworksSummaryRecord(
        run_id="run-routes",
        publication_id="",
        digest="",
        schema_version=version,
        policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        asset_count=0,
        node_count=0,
        edge_count=0,
        operational_count=0,
        damaged_count=0,
        destroyed_count=0,
        effects_active_count=0,
        coverage="not_applicable",
    )


def test_v2_round_trip_and_summary() -> None:
    snapshot = finalize_infrastructure_networks_snapshot(
        InfrastructureNetworksSnapshot(summary=_summary(), assets=(), routes=(ROUTE,))
    )
    assert snapshot.schema_version == INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION
    assert snapshot.summary.route_count == 1
    assert snapshot.summary.route_restricted_count == 1
    assert snapshot.summary.route_seasonal_count == 1
    decoded = decode_infrastructure_networks_snapshot(
        encode_infrastructure_networks_snapshot(snapshot)
    )
    assert decoded == snapshot


def test_v1_snapshot_still_decodes() -> None:
    snapshot = finalize_infrastructure_networks_snapshot(
        InfrastructureNetworksSnapshot(
            summary=_summary(INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1),
            assets=(),
            schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
        )
    )
    decoded = decode_infrastructure_networks_snapshot(
        encode_infrastructure_networks_snapshot(snapshot)
    )
    assert decoded.schema_version == INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1
    assert decoded.routes == ()


def test_v1_rejects_route_rows() -> None:
    with pytest.raises(InfrastructureNetworksArtifactError):
        InfrastructureNetworksSnapshot(
            summary=_summary(INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1),
            assets=(),
            routes=(ROUTE,),
            schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
        )


def test_composition_keeps_routes_without_assets() -> None:
    from experiments.infrastructure_completed_run import (
        build_completed_run_infrastructure_networks_analysis,
        compose_infrastructure_networks_snapshot,
    )
    from world.identifiers import EntityId
    from world.travel_network import (
        RouteBlockageCause,
        RouteCondition,
        RouteStatus,
        SeasonalAvailability,
    )

    route = RouteCondition(
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        status=RouteStatus.RESTRICTED,
        seasonal_availability=SeasonalAvailability.RESTRICTED,
        blockage_cause=RouteBlockageCause.SEASONAL,
        duration_ticks=3,
        fatigue_cost=4.5,
        capacity=6,
        risk=0.3,
        infrastructure_quality=0.4,
        reason_codes=("season_autumn", "route_restricted"),
        as_of_tick=1,
    )
    analysis = build_completed_run_infrastructure_networks_analysis(
        (), routes=(route,)
    )
    snapshot = compose_infrastructure_networks_snapshot(analysis, run_id="run-routes")
    assert snapshot.routes == (ROUTE,)


def test_v1_composition_remains_available() -> None:
    from experiments.infrastructure_completed_run import (
        build_completed_run_infrastructure_networks_analysis,
        compose_infrastructure_networks_snapshot,
    )
    from simulation.infrastructure_models import (
        INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
    )
    from world.identifiers import EntityId
    from world.travel_network import (
        RouteBlockageCause,
        RouteCondition,
        RouteStatus,
        SeasonalAvailability,
    )

    route = RouteCondition(
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        status=RouteStatus.OPEN,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=RouteBlockageCause.NONE,
        duration_ticks=1,
        fatigue_cost=0.0,
        capacity=8,
        risk=0.0,
        infrastructure_quality=0.0,
        reason_codes=(),
        as_of_tick=0,
    )
    analysis = build_completed_run_infrastructure_networks_analysis(
        (), routes=(route,)
    )
    snapshot = compose_infrastructure_networks_snapshot(
        analysis,
        run_id="run-routes",
        schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
    )
    assert snapshot.schema_version == INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1
    assert snapshot.routes == ()


def test_route_paging_keyset_and_limit() -> None:
    other = TravelRouteRecord(
        origin_location_id="loc-b",
        destination_location_id="loc-c",
        status="open",
        seasonal_availability="open",
        blockage_cause="none",
        duration_ticks=1,
        fatigue_cost=1.0,
        capacity=8,
        risk=0.0,
        infrastructure_quality=0.0,
        as_of_tick=2,
    )
    snapshot = InfrastructureNetworksSnapshot(
        summary=_summary(), assets=(), routes=(other, ROUTE)
    )
    page = page_travel_routes(snapshot, limit=1)
    assert len(page.rows) == 1
    assert page.rows[0].origin_location_id == "loc-a"
    assert page.next_key is not None
    next_page = page_travel_routes(snapshot, after_key=page.next_key, limit=1)
    assert next_page.rows[0].origin_location_id == "loc-b"
    assert next_page.next_key is None
