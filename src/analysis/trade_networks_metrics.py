"""Six detached trade-network metric families (catalog 192 -> 198).

Counts, availability, and integer ratios only; no economic valuation,
aggregate ordering, or routing model.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from analysis.trade_networks_analysis import (
    TradeNetworksAnalysis,
)
from analysis.trade_networks_contract import (
    TRADE_FORBIDDEN_KEYS,
    TRADE_NETWORKS_ANALYSIS_POLICY_VERSION,
    TradeCoverage,
    TradeFlowClass,
    TradeNetworksError,
)
from analysis.trade_networks_events import TradeTransferRow
from world.identifiers import require_stable_id

__all__ = [
    "assemble_trade_network_metrics",
    "compute_cross_society_trade_flows",
    "compute_trade_corridor_structure",
    "compute_trade_dependence",
    "compute_trade_flow_composition",
    "compute_trade_location_centrality",
    "compute_trade_network_lineage",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _require(analysis: object) -> TradeNetworksAnalysis:
    if type(analysis) is not TradeNetworksAnalysis:
        raise TradeNetworksError("trade_networks_metrics_invalid_analysis")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _milli(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return numerator * 1_000 // denominator


def _state(coverage: TradeCoverage) -> str:
    if coverage is TradeCoverage.MISSING:
        return "unknown"
    if coverage is TradeCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden_fields(values: Mapping[str, object]) -> None:
    for key in values:
        lowered = str(key).lower()
        if lowered in TRADE_FORBIDDEN_KEYS:
            _LOG.warning(
                "trade_networks_metrics_forbidden_key reason_code=%s",
                "trade_networks_forbidden_metric_key",
            )
            raise TradeNetworksError("trade_networks_forbidden_metric_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
) -> MetricDocument:
    spec = metric_specification(family)
    if state == "unknown":
        availability = MetricAvailability.UNKNOWN
        coverage = _ABSENT_COVERAGE
        payload: dict[str, object] = {}
    else:
        availability = (
            MetricAvailability.PRESENT
            if state == "present"
            else MetricAvailability.PARTIAL
        )
        coverage = MetricCoverage(
            observed=observed, expected=expected, ratio=_ratio(observed, expected)
        )
        _reject_forbidden_fields(values)
        payload = dict(values)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values=payload,
        provenance=MetricProvenance(
            source_kind="trade_networks_analysis",
            source_ids=(
                run_id,
                input_revision,
                TRADE_NETWORKS_ANALYSIS_POLICY_VERSION,
                "trade-networks",
            ),
            notes_code="detached_trade_networks_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def _flow_values(rows: Sequence[TradeTransferRow]) -> dict[str, int]:
    counts = Counter(row.flow_class.value for row in rows)
    return {
        "food_count": counts.get(TradeFlowClass.FOOD.value, 0),
        "materials_count": counts.get(TradeFlowClass.MATERIALS.value, 0),
        "tools_count": counts.get(TradeFlowClass.TOOLS.value, 0),
        "records_count": counts.get(TradeFlowClass.RECORDS.value, 0),
        "durable_exchange_media_count": counts.get(
            TradeFlowClass.DURABLE_EXCHANGE_MEDIA.value, 0
        ),
        "other_count": counts.get(TradeFlowClass.OTHER.value, 0),
    }


def compute_trade_corridor_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Directed corridor structure, major locations, and degree bounds."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.evidence_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRADE_CORRIDOR_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    major_locations = {
        row.location_token for row in rows.locations if row.is_major
    }
    active_locations = {row.location_token for row in rows.locations}
    isolated = {
        row.location_token
        for row in rows.locations
        if row.corridor_degree == 0
    }
    complete_corridors = sum(
        1 for row in rows.corridors if row.coverage is TradeCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "corridor_count": rows.corridor_count,
        "active_location_count": len(active_locations),
        "major_location_count": len(major_locations),
        "max_corridor_degree": max(
            (row.corridor_degree for row in rows.locations), default=0
        ),
        "max_corridor_transfers": max(
            (row.transfer_count for row in rows.corridors), default=0
        ),
        "isolated_location_count": len(isolated),
        "corridor_coverage_ratio_milli": _milli(
            complete_corridors, len(rows.corridors)
        ),
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=corridor_structure corridors=%s",
        len(rows.corridors),
    )
    return _document(
        MetricFamilyId.TRADE_CORRIDOR_STRUCTURE,
        state=state,
        observed=complete_corridors,
        expected=len(rows.corridors),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_trade_flow_composition(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Closed flow-class composition with non-disjoint import/export roles."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.evidence_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRADE_FLOW_COMPOSITION,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    cross = sum(
        1
        for row in rows.transfers
        if row.previous_location_token != row.location_token
    )
    local = len(rows.transfers) - cross
    complete_flows = sum(
        1 for row in rows.flows if row.coverage is TradeCoverage.COMPLETE
    )
    values = {
        "window_tick": rows.window_tick,
        "transfer_count": rows.transfer_count,
        "cross_location_count": cross,
        **_flow_values(rows.transfers),
        "imported_count": cross,
        "exported_count": cross,
        "local_count": local,
        "unknown_class_count": sum(
            1
            for row in rows.transfers
            if row.flow_class is TradeFlowClass.OTHER
        ),
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=flow_composition transfers=%s",
        rows.transfer_count,
    )
    return _document(
        MetricFamilyId.TRADE_FLOW_COMPOSITION,
        state=state,
        observed=complete_flows,
        expected=len(rows.flows),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_trade_location_centrality(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Major exchange locations, venue anchors, and activity bounds."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.evidence_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRADE_LOCATION_CENTRALITY,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    locations = {row.location_token for row in rows.locations}
    major = {row.location_token for row in rows.locations if row.is_major}
    trade_posts = {
        row.location_token for row in rows.locations if row.trade_post_present
    }
    major_trade_posts = major & trade_posts
    degree_sum = sum(row.corridor_degree for row in rows.locations)
    values = {
        "window_tick": rows.window_tick,
        "location_count": len(locations),
        "major_location_count": len(major),
        "trade_post_location_count": len(trade_posts),
        "major_trade_post_location_count": len(major_trade_posts),
        "max_inflow_count": max(
            (row.inflow_count for row in rows.locations), default=0
        ),
        "max_outflow_count": max(
            (row.outflow_count for row in rows.locations), default=0
        ),
        "max_local_count": max(
            (row.local_count for row in rows.locations), default=0
        ),
        "max_corridor_degree": max(
            (row.corridor_degree for row in rows.locations), default=0
        ),
        "mean_corridor_degree_milli": _milli(degree_sum, len(rows.locations)),
        "major_share_milli": _milli(len(major), len(locations)),
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=location_centrality locations=%s",
        len(locations),
    )
    return _document(
        MetricFamilyId.TRADE_LOCATION_CENTRALITY,
        state=state,
        observed=sum(
            1 for row in rows.locations if row.coverage is TradeCoverage.COMPLETE
        ),
        expected=len(rows.locations),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_trade_dependence(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Observed exchange dependence statistics, never a welfare claim."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.evidence_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRADE_DEPENDENCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    resolved = [
        row for row in rows.dependence if row.dependence_milli is not None
    ]
    dependence_values = [
        row.dependence_milli for row in resolved if row.dependence_milli is not None
    ]
    values = {
        "window_tick": rows.window_tick,
        "location_count": len({row.location_token for row in rows.dependence}),
        "class_count": len(
            {(row.location_token, row.flow_class.value) for row in rows.dependence}
        ),
        "mean_dependence_milli": (
            sum(dependence_values) // len(dependence_values)
            if dependence_values
            else 0
        ),
        "max_dependence_milli": max(dependence_values, default=0),
        "high_dependence_count": sum(
            1 for row in rows.dependence if row.high_dependence
        ),
        "unresolved_count": sum(
            1 for row in rows.dependence if row.dependence_milli is None
        ),
        "complete_coverage_count": sum(
            1
            for row in rows.dependence
            if row.coverage is TradeCoverage.COMPLETE
        ),
        "partial_coverage_count": sum(
            1
            for row in rows.dependence
            if row.coverage is TradeCoverage.PARTIAL
        ),
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=dependence rows=%s",
        len(rows.dependence),
    )
    return _document(
        MetricFamilyId.TRADE_DEPENDENCE,
        state=state,
        observed=len(resolved),
        expected=len(rows.dependence),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_cross_society_trade_flows(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Analytical cross-society exchange counts with explicit anchor coverage."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.cross_society_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.CROSS_SOCIETY_TRADE_FLOWS,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    pairs = rows.cross_society
    societies = {row.society_a for row in pairs} | {
        row.society_b for row in pairs
    }
    class_counts: Counter[str] = Counter()
    for row in pairs:
        for key, count in row.flow_counts:
            class_counts[key] += count
    resolved_anchors = sum(
        1
        for row in pairs
        if row.society_a_location_id != "none"
        and row.society_b_location_id != "none"
    )
    values = {
        "window_tick": rows.window_tick,
        "pair_count": len(pairs),
        "society_count": len(societies),
        "transfer_count": sum(row.transfer_count for row in pairs),
        "food_count": class_counts.get(TradeFlowClass.FOOD.value, 0),
        "materials_count": class_counts.get(TradeFlowClass.MATERIALS.value, 0),
        "tools_count": class_counts.get(TradeFlowClass.TOOLS.value, 0),
        "records_count": class_counts.get(TradeFlowClass.RECORDS.value, 0),
        "durable_exchange_media_count": class_counts.get(
            TradeFlowClass.DURABLE_EXCHANGE_MEDIA.value, 0
        ),
        "other_count": class_counts.get(TradeFlowClass.OTHER.value, 0),
        "overlap_pair_count": sum(
            1 for row in pairs if row.overlap_member_count > 0
        ),
        "anchor_resolved_pair_count": resolved_anchors,
        "anchor_unresolved_pair_count": len(pairs) - resolved_anchors,
        "coverage": rows.cross_society_coverage.value,
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=cross_society pairs=%s", len(pairs)
    )
    return _document(
        MetricFamilyId.CROSS_SOCIETY_TRADE_FLOWS,
        state=state,
        observed=sum(
            1 for row in pairs if row.coverage is TradeCoverage.COMPLETE
        ),
        expected=len(pairs),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_trade_network_lineage(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Forward-only lineage status counts and sustained-transition counts."""
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.lineage_coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRADE_NETWORK_LINEAGE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    relations = Counter(row.relation for row in rows.lineage)
    sustained_current = {
        row.network_token for row in rows.lineage if row.sustained
    }
    values = {
        "window_tick": rows.window_tick,
        "network_count": rows.network_count,
        "active_network_count": len(
            {row.network_token for row in rows.networks}
        ),
        "emerged_count": relations.get("emerged", 0),
        "continued_count": relations.get("continued", 0),
        "transformed_count": relations.get("transformed", 0),
        "split_count": relations.get("split", 0),
        "merge_count": relations.get("merge", 0),
        "dissolved_count": relations.get("dissolved", 0),
        "rerouted_count": sum(1 for row in rows.lineage if row.rerouted),
        "sustained_transition_count": sum(
            1 for row in rows.lineage if row.sustained
        ),
        "sustained_network_count": len(sustained_current),
        "coverage": rows.lineage_coverage.value,
    }
    _LOG.debug(
        "trade_networks_metrics_emitted family=network_lineage edges=%s",
        len(rows.lineage),
    )
    return _document(
        MetricFamilyId.TRADE_NETWORK_LINEAGE,
        state=state,
        observed=len(rows.networks),
        expected=len(rows.networks),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def assemble_trade_network_metrics(
    analysis: TradeNetworksAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> tuple[MetricDocument, ...]:
    """Return the six documents in catalog order."""
    _require(analysis)
    return (
        compute_trade_corridor_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_trade_flow_composition(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_trade_location_centrality(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_trade_dependence(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_cross_society_trade_flows(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_trade_network_lineage(
            analysis, run_id=run_id, input_revision=input_revision
        ),
    )
