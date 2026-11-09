"""Map infrastructure analysis into ``infrastructure-networks-snapshot-v1``."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Final

from analysis.infrastructure_networks_analysis import (
    InfrastructureNetworksAnalysis,
    TravelRouteAnalysisRow,
    harvest_infrastructure_networks_analysis,
)
from simulation.infrastructure_codec import finalize_infrastructure_networks_snapshot
from simulation.infrastructure_models import (
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
    InfrastructureAssetRecord,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
    TravelRouteRecord,
    empty_infrastructure_networks_snapshot,
)
from world.identifiers import require_stable_id
from world.infrastructure import InfrastructureAsset
from world.travel_network import RouteCondition

__all__ = [
    "build_completed_run_infrastructure_networks_analysis",
    "compose_infrastructure_networks_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.infrastructure.completed_run"
)


def build_completed_run_infrastructure_networks_analysis(
    assets: Sequence[InfrastructureAsset] | None = None,
    *,
    routes: Sequence[RouteCondition] | None = None,
    belief_counts: Mapping[tuple[str, str], tuple[int, int, int]] | None = None,
    window_tick: int = 0,
) -> InfrastructureNetworksAnalysis:
    route_rows: list[TravelRouteAnalysisRow] = []
    counts = belief_counts or {}
    for route in routes or ():
        if type(route) is not RouteCondition:
            raise TypeError("routes entries must be RouteCondition")
        observed, closed, restricted = counts.get(route.edge_key, (0, 0, 0))
        route_rows.append(
            TravelRouteAnalysisRow(
                origin_id=route.origin_id.value,
                destination_id=route.destination_id.value,
                status=route.status.value,
                seasonal_availability=route.seasonal_availability.value,
                blockage_cause=route.blockage_cause.value,
                duration_ticks=route.duration_ticks,
                fatigue_cost=route.fatigue_cost,
                capacity=route.capacity,
                risk=route.risk,
                infrastructure_quality=route.infrastructure_quality,
                as_of_tick=route.as_of_tick,
                observed_belief_count=observed,
                believed_closed_count=closed,
                believed_restricted_count=restricted,
            )
        )
    return harvest_infrastructure_networks_analysis(
        tuple(assets or ()),
        routes=tuple(route_rows),
        route_coverage_expected=len(route_rows),
        window_tick=window_tick,
    )


def _coverage(analysis: InfrastructureNetworksAnalysis) -> str:
    if analysis.asset_count == 0:
        return "not_applicable"
    if all(row.status == "destroyed" for row in analysis.assets):
        return "partial"
    if any(row.status != "operational" for row in analysis.assets):
        return "partial"
    return "complete"


def compose_infrastructure_networks_snapshot(
    analysis: InfrastructureNetworksAnalysis,
    *,
    run_id: str,
    schema_version: str = INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
) -> InfrastructureNetworksSnapshot:
    require_stable_id("run_id", run_id)
    if schema_version not in {
        INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1,
        INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    }:
        raise ValueError("infrastructure_networks_snapshot_version")
    if analysis.asset_count == 0 and analysis.route_count == 0:
        empty = empty_infrastructure_networks_snapshot(run_id=run_id)
        if schema_version != empty.schema_version:
            empty = InfrastructureNetworksSnapshot(
                summary=replace(
                    empty.summary,
                    schema_version=schema_version,
                ),
                assets=(),
                schema_version=schema_version,
            )
        finalized = finalize_infrastructure_networks_snapshot(empty)
        _LOG.debug("infrastructure_networks_compose empty")
        return finalized
    assets = []
    for row in analysis.assets:
        assets.append(
            InfrastructureAssetRecord(
                asset_id=row.asset_id,
                kind=row.kind,
                topology=row.topology,
                status=row.status,
                integrity=row.integrity,
                location_id=row.location_id,
                endpoint_location_id=row.endpoint_location_id,
                effects_active=row.effects_active,
                created_tick=row.created_tick,
                last_maintained_tick=row.last_maintained_tick,
                ticks_since_maintained=row.ticks_since_maintained,
                linked_project_id=row.linked_project_id,
                linked_structure_id=row.linked_structure_id,
            )
        )
    summary = InfrastructureNetworksSummaryRecord(
        run_id=run_id,
        publication_id="",
        digest="",
        schema_version=schema_version,
        policy_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
        asset_count=0,
        node_count=0,
        edge_count=0,
        operational_count=0,
        damaged_count=0,
        destroyed_count=0,
        effects_active_count=0,
        coverage=_coverage(analysis),
    )
    routes = (
        ()
        if schema_version == INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION_V1
        else tuple(
            TravelRouteRecord(
                origin_location_id=row.origin_id,
                destination_location_id=row.destination_id,
                status=row.status,
                seasonal_availability=row.seasonal_availability,
                blockage_cause=row.blockage_cause,
                duration_ticks=row.duration_ticks,
                fatigue_cost=row.fatigue_cost,
                capacity=row.capacity,
                risk=row.risk,
                infrastructure_quality=row.infrastructure_quality,
                as_of_tick=row.as_of_tick,
            )
            for row in analysis.routes
        )
    )
    snapshot = InfrastructureNetworksSnapshot(
        summary=summary,
        assets=tuple(assets),
        routes=routes,
        schema_version=schema_version,
    )
    finalized = finalize_infrastructure_networks_snapshot(snapshot)
    _LOG.info(
        "infrastructure_networks_compose assets=%s coverage=%s",
        finalized.summary.asset_count,
        finalized.summary.coverage,
    )
    return finalized
