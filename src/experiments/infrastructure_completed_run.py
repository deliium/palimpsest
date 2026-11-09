"""Map infrastructure analysis into ``infrastructure-networks-snapshot-v1``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.infrastructure_networks_analysis import (
    InfrastructureNetworksAnalysis,
    harvest_infrastructure_networks_analysis,
)
from simulation.infrastructure_codec import finalize_infrastructure_networks_snapshot
from simulation.infrastructure_models import (
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_POLICY,
    INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
    InfrastructureAssetRecord,
    InfrastructureNetworksSnapshot,
    InfrastructureNetworksSummaryRecord,
    empty_infrastructure_networks_snapshot,
)
from world.identifiers import require_stable_id
from world.infrastructure import InfrastructureAsset

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
    window_tick: int = 0,
) -> InfrastructureNetworksAnalysis:
    return harvest_infrastructure_networks_analysis(
        tuple(assets or ()), window_tick=window_tick
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
) -> InfrastructureNetworksSnapshot:
    require_stable_id("run_id", run_id)
    if analysis.asset_count == 0:
        empty = empty_infrastructure_networks_snapshot(run_id=run_id)
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
        schema_version=INFRASTRUCTURE_NETWORKS_SNAPSHOT_VERSION,
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
    snapshot = InfrastructureNetworksSnapshot(
        summary=summary,
        assets=tuple(assets),
    )
    finalized = finalize_infrastructure_networks_snapshot(snapshot)
    _LOG.info(
        "infrastructure_networks_compose assets=%s coverage=%s",
        finalized.summary.asset_count,
        finalized.summary.coverage,
    )
    return finalized
