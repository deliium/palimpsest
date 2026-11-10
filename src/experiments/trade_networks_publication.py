"""Compose and publish completed-run trade-network snapshots."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_analysis import TradeNetworksAnalysis
from analysis.trade_networks_policy import TradeNetworksAnalysisPolicy
from analysis.trade_networks_rows import TradeLineageRow, TradeNetworkRow
from simulation.trade_networks_codec import finalize_trade_networks_snapshot
from simulation.trade_networks_models import (
    TRADE_NETWORKS_SNAPSHOT_POLICY,
    TRADE_NETWORKS_SNAPSHOT_VERSION,
    CrossSocietyTradeRecord,
    TradeCorridorRecord,
    TradeDependenceRecord,
    TradeFlowCountRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksSnapshot,
    TradeNetworksSummaryRecord,
)
from world.values import ItemKind

__all__ = [
    "TradeNetworksHarvest",
    "TradeNetworksReceipt",
    "build_trade_networks_harvest_result",
    "compose_trade_networks_snapshot",
    "publish_trade_networks_snapshot",
    "trade_networks_publication_document",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.trade_networks_publication"
)


@dataclass(frozen=True, slots=True)
class TradeNetworksReceipt:
    publication_id: str
    digest: str
    run_id: str
    coverage: str
    corridor_count: int
    network_count: int
    stored: bool
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class TradeNetworksHarvest:
    run_id: str
    analysis: TradeNetworksAnalysis | None
    snapshot: TradeNetworksSnapshot | None
    coverage: str
    receipts: tuple[TradeNetworksReceipt, ...] = ()


def _flows(
    flow_counts: tuple[tuple[str, int], ...],
) -> tuple[TradeFlowCountRecord, ...]:
    return tuple(
        TradeFlowCountRecord(flow_class=key, count=count) for key, count in flow_counts
    )


def _network_lineage(
    analysis: TradeNetworksAnalysis,
) -> tuple[
    set[str],
    dict[str, list[TradeLineageRow]],
    dict[str, list[TradeLineageRow]],
]:
    dissolved = {
        edge.previous_token
        for edge in analysis.lineage
        if edge.relation == "dissolved" and edge.previous_token != "none"
    }
    incoming: dict[str, list[TradeLineageRow]] = {}
    outgoing: dict[str, list[TradeLineageRow]] = {}
    for edge in analysis.lineage:
        if edge.network_token != "none":
            incoming.setdefault(edge.network_token, []).append(edge)
        if edge.previous_token != "none":
            outgoing.setdefault(edge.previous_token, []).append(edge)
    return dissolved, incoming, outgoing


def _network_record(
    analysis: TradeNetworksAnalysis, row: TradeNetworkRow
) -> TradeNetworkRecord:
    dissolved, incoming, outgoing = _network_lineage(analysis)
    token = row.network_token
    parents = sorted(
        {
            edge.previous_token
            for edge in incoming.get(token, ())
            if edge.previous_token != "none"
        }
    )
    successors = sorted(
        {
            edge.network_token
            for edge in outgoing.get(token, ())
            if edge.network_token != "none"
        }
    )
    edges = incoming.get(token, [])
    if token in dissolved:
        status = "dissolved"
    elif len(successors) >= 2:
        status = "split"
    elif len(parents) >= 2:
        status = "merge"
    elif len(edges) == 1:
        status = str(edges[0].relation)
    elif successors:
        status = "emerged"
    else:
        status = "observed"
    rerouted = any(bool(getattr(edge, "rerouted", False)) for edge in edges)
    sustained = any(bool(getattr(edge, "sustained", False)) for edge in edges)
    return TradeNetworkRecord(
        network_id=token,
        window_index=row.window_index,
        corridor_ids=tuple(row.corridor_tokens),
        location_ids=tuple(row.location_tokens),
        flow_counts=_flows(row.flow_counts),
        transfer_count=row.transfer_count,
        status=status,
        previous_network_ids=tuple(parents),
        next_network_ids=tuple(successors),
        rerouted=rerouted,
        sustained=sustained,
        coverage=row.coverage.value,
    )


def compose_trade_networks_snapshot(
    analysis: TradeNetworksAnalysis, *, run_id: str
) -> TradeNetworksSnapshot:
    """Map one analysis harvest into the canonical snapshot and finalize it."""
    if type(analysis) is not TradeNetworksAnalysis:
        raise TypeError("analysis must be TradeNetworksAnalysis")
    relations = Counter(edge.relation for edge in analysis.lineage)
    networks = tuple(_network_record(analysis, row) for row in analysis.networks)
    status_counts = Counter(row.status for row in networks)
    sustained = {row.network_id for row in networks if row.sustained}
    notices = tuple(analysis.notices)
    truncated = any("truncated" in notice for notice in notices)
    summary = TradeNetworksSummaryRecord(
        window_tick=analysis.window_tick,
        corridor_count=len(analysis.corridors),
        flow_count=len(analysis.flows),
        location_count=len(analysis.locations),
        major_location_count=sum(1 for row in analysis.locations if row.is_major),
        trade_post_location_count=sum(
            1 for row in analysis.locations if row.trade_post_present
        ),
        network_count=len(networks),
        cross_society_pair_count=len(analysis.cross_society),
        transfer_count=analysis.transfer_count,
        emerged_count=status_counts.get("emerged", relations.get("emerged", 0)),
        continued_count=status_counts.get("continued", relations.get("continued", 0)),
        transformed_count=status_counts.get(
            "transformed", relations.get("transformed", 0)
        ),
        split_count=status_counts.get("split", relations.get("split", 0)),
        merge_count=status_counts.get("merge", relations.get("merge", 0)),
        dissolved_count=status_counts.get("dissolved", relations.get("dissolved", 0)),
        rerouted_count=sum(1 for row in networks if row.rerouted),
        sustained_network_count=len(sustained),
        lineage_edge_count=len(analysis.lineage),
        coverage=analysis.coverage.value,
        truncated=truncated,
    )
    snapshot = TradeNetworksSnapshot(
        run_id=run_id,
        schema_version=TRADE_NETWORKS_SNAPSHOT_VERSION,
        policy_version=TRADE_NETWORKS_SNAPSHOT_POLICY,
        summary=summary,
        corridors=tuple(
            TradeCorridorRecord(
                corridor_id=row.corridor_token,
                window_index=row.window_index,
                from_location_id=row.from_location_token,
                to_location_id=row.to_location_token,
                flow_counts=_flows(row.flow_counts),
                transfer_count=row.transfer_count,
                coverage=row.coverage.value,
            )
            for row in analysis.corridors
        ),
        flows=tuple(
            TradeFlowRecord(
                window_index=row.window_index,
                flow_class=row.flow_class.value,
                transfer_count=row.transfer_count,
                cross_location_count=row.cross_location_count,
                imported_count=row.imported_count,
                exported_count=row.exported_count,
                local_count=row.local_count,
                coverage=row.coverage.value,
            )
            for row in analysis.flows
        ),
        locations=tuple(
            TradeLocationRecord(
                location_id=row.location_token,
                window_index=row.window_index,
                inflow_count=row.inflow_count,
                outflow_count=row.outflow_count,
                local_count=row.local_count,
                corridor_degree=row.corridor_degree,
                is_major=row.is_major,
                trade_post_present=row.trade_post_present,
                flow_counts=_flows(row.flow_counts),
                coverage=row.coverage.value,
            )
            for row in analysis.locations
        ),
        dependence=tuple(
            TradeDependenceRecord(
                location_id=row.location_token,
                window_index=row.window_index,
                flow_class=row.flow_class.value,
                imported_count=row.imported_count,
                locally_originated_count=row.locally_originated_count,
                dependence_milli=row.dependence_milli,
                high_dependence=row.high_dependence,
                coverage=row.coverage.value,
            )
            for row in analysis.dependence
        ),
        cross_society=tuple(
            CrossSocietyTradeRecord(
                pair_id=row.pair_token,
                window_index=row.window_index,
                society_a=row.society_a,
                society_b=row.society_b,
                society_a_location_id=row.society_a_location_id,
                society_b_location_id=row.society_b_location_id,
                overlap_member_count=row.overlap_member_count,
                flow_counts=_flows(row.flow_counts),
                transfer_count=row.transfer_count,
                society_a_to_b_count=row.society_a_to_b_count,
                society_b_to_a_count=row.society_b_to_a_count,
                coverage=row.coverage.value,
            )
            for row in analysis.cross_society
        ),
        networks=networks,
    )
    return finalize_trade_networks_snapshot(snapshot)


def build_trade_networks_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    macro_candidates: Sequence[InterSocietyMacroCandidate] = (),
    policy: TradeNetworksAnalysisPolicy | None = None,
    recipe_item_kinds: Mapping[str, ItemKind] | None = None,
    item_kind_by_id: Mapping[str, ItemKind] | None = None,
    trade_post_locations: Sequence[str] = (),
    window_tick: int | None = None,
) -> TradeNetworksHarvest:
    from experiments.trade_networks_completed_run import (
        build_completed_run_trade_networks_analysis,
    )

    analysis = build_completed_run_trade_networks_analysis(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        macro_candidates=macro_candidates,
        policy=policy,
        window_tick=window_tick,
        recipe_item_kinds=recipe_item_kinds,
        item_kind_by_id=item_kind_by_id,
        trade_post_locations=trade_post_locations,
    )
    snapshot = compose_trade_networks_snapshot(analysis, run_id=run_id)
    _LOG.info(
        "trade_networks_publication run=%s corridors=%s networks=%s coverage=%s",
        run_id,
        len(snapshot.corridors),
        len(snapshot.networks),
        snapshot.summary.coverage,
    )
    return TradeNetworksHarvest(
        run_id=run_id,
        analysis=analysis,
        snapshot=snapshot,
        coverage=analysis.coverage.value,
    )


def publish_trade_networks_snapshot(
    harvest: TradeNetworksHarvest, publisher: Any
) -> TradeNetworksReceipt:
    if type(harvest) is not TradeNetworksHarvest:
        raise TypeError("harvest must be TradeNetworksHarvest")
    snapshot = harvest.snapshot
    if snapshot is None:
        return TradeNetworksReceipt(
            publication_id="",
            digest="",
            run_id=harvest.run_id,
            coverage=harvest.coverage,
            corridor_count=0,
            network_count=0,
            stored=False,
            reason_code="trade_networks_publication_missing",
        )
    if (
        not (
            snapshot.corridors
            or snapshot.flows
            or snapshot.locations
            or snapshot.dependence
            or snapshot.cross_society
            or snapshot.networks
        )
        and harvest.coverage == "missing"
    ):
        _LOG.warning(
            "trade_networks_publication_skipped run=%s reason_code=missing",
            harvest.run_id,
        )
        return TradeNetworksReceipt(
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            run_id=harvest.run_id,
            coverage=harvest.coverage,
            corridor_count=0,
            network_count=0,
            stored=False,
            reason_code="trade_networks_publication_missing",
        )
    publisher.publish(snapshot)
    return TradeNetworksReceipt(
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        run_id=harvest.run_id,
        coverage=harvest.coverage,
        corridor_count=len(snapshot.corridors),
        network_count=len(snapshot.networks),
        stored=True,
        reason_code="published",
    )


def trade_networks_publication_document(
    harvest: TradeNetworksHarvest,
) -> dict[str, object]:
    if type(harvest) is not TradeNetworksHarvest:
        raise TypeError("harvest must be TradeNetworksHarvest")
    snapshot = harvest.snapshot
    return {
        "run_id": harvest.run_id,
        "coverage": harvest.coverage,
        "corridor_count": 0 if snapshot is None else len(snapshot.corridors),
        "network_count": 0 if snapshot is None else len(snapshot.networks),
        "publication_id": "" if snapshot is None else snapshot.publication_id,
        "digest": "" if snapshot is None else snapshot.digest,
        "stored": bool(harvest.receipts)
        and any(receipt.stored for receipt in harvest.receipts),
    }
