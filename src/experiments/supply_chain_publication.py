"""Completed-run supply-chain snapshot composition and publication bridge."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.supply_chain_analysis import SupplyChainAnalysis
from simulation.supply_chain_codec import finalize_supply_chain_snapshot
from simulation.supply_chain_models import (
    SUPPLY_CHAIN_SNAPSHOT_POLICY,
    SUPPLY_CHAIN_SNAPSHOT_VERSION,
    SupplyBottleneckRecord,
    SupplyChainLineageRecord,
    SupplyChainRecord,
    SupplyChainSnapshot,
    SupplyChainSummaryRecord,
    SupplyDependencyRecord,
    SupplyLocationRecord,
    SupplyOrganizationRecord,
    SupplyStageRecord,
)

__all__ = [
    "SupplyChainHarvest",
    "SupplyChainReceipt",
    "build_supply_chain_harvest_result",
    "compose_supply_chain_snapshot",
    "publish_supply_chain_snapshot",
    "supply_chain_publication_document",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.supply_chain_publication")


@dataclass(frozen=True, slots=True)
class SupplyChainReceipt:
    publication_id: str
    digest: str
    run_id: str
    coverage: str
    stored: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SupplyChainHarvest:
    run_id: str
    analysis: SupplyChainAnalysis
    snapshot: SupplyChainSnapshot
    coverage: str


def compose_supply_chain_snapshot(
    analysis: SupplyChainAnalysis, *, run_id: str
) -> SupplyChainSnapshot:
    if type(analysis) is not SupplyChainAnalysis:
        raise TypeError("analysis must be SupplyChainAnalysis")
    notices = tuple(analysis.notices)
    summary = SupplyChainSummaryRecord(
        window_tick=analysis.window_tick,
        stage_count=analysis.stage_count,
        edge_count=analysis.edge_count,
        chain_count=analysis.chain_count,
        lineage_count=len(analysis.lineage),
        bottleneck_count=analysis.bottleneck_count,
        location_count=analysis.location_count,
        organization_count=analysis.organization_count,
        sustained_chain_count=analysis.sustained_chain_count,
        max_depth=analysis.max_depth,
        coverage=analysis.coverage.value,
        truncated=any("truncated" in notice for notice in notices),
    )
    snapshot = SupplyChainSnapshot(
        run_id=run_id,
        schema_version=SUPPLY_CHAIN_SNAPSHOT_VERSION,
        policy_version=SUPPLY_CHAIN_SNAPSHOT_POLICY,
        summary=summary,
        stages=tuple(
            SupplyStageRecord(
                stage_token=row.recipe_id,
                window_index=row.window_index,
                recipe_id=row.recipe_id,
                action=row.action,
                location_token=row.location_token,
                actor_token=row.actor_token,
                item_names=row.item_names,
                completed=row.completed,
                attempt=row.attempt,
                duration_ticks=row.duration_ticks,
                created_item_token=row.created_item_token,
                cause=row.cause,
                coverage=(
                    "complete" if row.completed and not row.item_names else "partial"
                ),
            )
            for row in analysis.stages
        ),
        edges=tuple(
            SupplyDependencyRecord(
                edge_token=row.edge_token,
                window_index=row.window_index,
                from_kind=row.from_kind.value,
                from_token=row.from_token,
                to_kind=row.to_kind.value,
                to_token=row.to_token,
                edge_kind=row.edge_kind.value,
                recipe_id=row.recipe_id,
                observed_count=row.observed_count,
                completed_count=row.completed_count,
                share_milli=row.share_milli,
                created_elsewhere_count=row.created_elsewhere_count,
                coverage=row.coverage.value,
            )
            for row in analysis.edges
        ),
        chains=tuple(
            SupplyChainRecord(
                chain_token=row.chain_token,
                window_index=row.window_index,
                stage_tokens=row.stage_tokens,
                edge_tokens=row.edge_tokens,
                depth=row.depth,
                completed_count=row.completed_count,
                coverage=row.coverage.value,
            )
            for row in analysis.chains
        ),
        lineage=tuple(
            SupplyChainLineageRecord(
                chain_token=row.chain_token,
                window_index=row.window_index,
                status=row.status,
                predecessor_tokens=row.predecessor_tokens,
                successor_tokens=row.successor_tokens,
                shared_edge_count=row.shared_edge_count,
                overlap_milli=row.overlap_milli,
                coverage=row.coverage.value,
            )
            for row in analysis.lineage
        ),
        bottlenecks=tuple(
            SupplyBottleneckRecord(
                bottleneck_token=row.bottleneck_token,
                window_index=row.window_index,
                kind=row.kind.value,
                stage_token=row.stage_token,
                edge_token=row.edge_token,
                observed_count=row.observed_count,
                demand_count=row.demand_count,
                supply_count=row.supply_count,
                ratio_milli=row.ratio_milli,
                location_token=row.location_token,
                organization_token=row.organization_token,
                skill_domain=row.skill_domain,
                coverage=row.coverage.value,
            )
            for row in analysis.bottlenecks
        ),
        locations=tuple(
            SupplyLocationRecord(
                location_token=row.location_token,
                window_index=row.window_index,
                observed_count=row.observed_count,
                completed_count=row.completed_count,
                coverage=row.coverage.value,
            )
            for row in analysis.locations
        ),
        organizations=tuple(
            SupplyOrganizationRecord(
                organization_token=row.organization_token,
                window_index=row.window_index,
                actor_count=row.actor_count,
                claim_count=row.claim_count,
                completed_count=row.completed_count,
                coverage=row.coverage.value,
            )
            for row in analysis.organizations
        ),
    )
    return finalize_supply_chain_snapshot(snapshot)


def build_supply_chain_harvest_result(
    runner_result: object = None,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    **kwargs: Any,
) -> SupplyChainHarvest:
    from experiments.supply_chain_completed_run import (
        build_completed_run_supply_chain_analysis,
    )

    analysis = build_completed_run_supply_chain_analysis(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        **kwargs,
    )
    snapshot = compose_supply_chain_snapshot(analysis, run_id=run_id)
    return SupplyChainHarvest(
        run_id=run_id,
        analysis=analysis,
        snapshot=snapshot,
        coverage=analysis.coverage.value,
    )


def publish_supply_chain_snapshot(
    harvest: SupplyChainHarvest | None, publisher: Any
) -> SupplyChainReceipt:
    if harvest is None:
        _LOG.warning(
            "supply_chain_publication_missing reason=%s",
            "supply_chain_publication_missing",
        )
        return SupplyChainReceipt(
            publication_id="",
            digest="",
            run_id="",
            coverage="missing",
            stored=False,
            reason="supply_chain_publication_missing",
        )
    if type(harvest) is not SupplyChainHarvest:
        raise TypeError("harvest must be SupplyChainHarvest")
    snapshot = harvest.snapshot
    if snapshot is None or (
        not (
            snapshot.stages
            or snapshot.edges
            or snapshot.chains
            or snapshot.bottlenecks
            or snapshot.locations
            or snapshot.organizations
        )
        and harvest.coverage == "missing"
    ):
        _LOG.warning(
            "supply_chain_publication_missing reason=%s",
            "supply_chain_publication_missing",
        )
        return SupplyChainReceipt(
            publication_id=snapshot.publication_id if snapshot else "",
            digest=snapshot.digest if snapshot else "",
            run_id=harvest.run_id,
            coverage=harvest.coverage,
            stored=False,
            reason="supply_chain_publication_missing",
        )
    publisher.publish(snapshot)
    return SupplyChainReceipt(
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        run_id=harvest.run_id,
        coverage=harvest.coverage,
        stored=True,
        reason="published",
    )


def supply_chain_publication_document(
    harvest: SupplyChainHarvest,
) -> dict[str, object]:
    if type(harvest) is not SupplyChainHarvest:
        raise TypeError("harvest must be SupplyChainHarvest")
    snapshot = harvest.snapshot
    return {
        "run_id": harvest.run_id,
        "coverage": harvest.coverage,
        "stage_count": len(snapshot.stages),
        "edge_count": len(snapshot.edges),
        "chain_count": len(snapshot.chains),
        "bottleneck_count": len(snapshot.bottlenecks),
        "publication_id": snapshot.publication_id,
        "digest": snapshot.digest,
    }
