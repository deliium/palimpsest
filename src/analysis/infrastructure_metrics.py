"""Four detached infrastructure-networks metric families (catalog 184 -> 188).

Counts, availability, and quantized ratios only — never a civilization
infrastructure score. Emit only when
``MetricComputationInputs.infrastructure_networks_analysis`` is supplied.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping
from typing import Final

from analysis.infrastructure_networks_analysis import (
    INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION,
    InfrastructureNetworksAnalysis,
    TravelRouteAnalysisRow,
    harvest_infrastructure_networks_analysis,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import (
    INFRASTRUCTURE_KIND_KEYS,
    MetricFamilyId,
    metric_specification,
)
from world.infrastructure import (
    INFRASTRUCTURE_CATALOG,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
)

__all__ = [
    "InfrastructureNetworksAnalysis",
    "compute_infrastructure_condition_lifecycle",
    "compute_infrastructure_effect_coverage",
    "compute_infrastructure_maintenance_burden",
    "compute_infrastructure_network_structure",
    "compute_travel_route_belief_alignment",
    "compute_travel_route_blockage",
    "compute_travel_route_condition",
    "compute_travel_route_structure",
    "harvest_infrastructure_networks_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.infrastructure.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)

_TRAVEL_KINDS: Final[frozenset[str]] = frozenset({"road", "bridge"})
_CAPACITY_KINDS: Final[frozenset[str]] = frozenset(
    {"storage", "trade_post", "large_shelter"}
)
_RESOURCE_KINDS: Final[frozenset[str]] = frozenset({"well", "irrigation"})
_EXPOSURE_KINDS: Final[frozenset[str]] = frozenset(
    {"communication_marker", "large_shelter"}
)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
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
        payload = values
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
            source_kind="infrastructure_networks_analysis",
            source_ids=(
                run_id,
                input_revision,
                INFRASTRUCTURE_NETWORKS_ANALYSIS_POLICY_VERSION,
            ),
            notes_code="detached_infrastructure_networks_analysis",
        ),
    )


def _require(analysis: object) -> InfrastructureNetworksAnalysis:
    if type(analysis) is not InfrastructureNetworksAnalysis:
        raise ValueError("infrastructure_networks_metrics: invalid_analysis")
    return analysis


def _state(analysis: InfrastructureNetworksAnalysis) -> str:
    if analysis.asset_count == 0:
        return "unknown"
    if all(
        row.status == InfrastructureStatus.DESTROYED.value for row in analysis.assets
    ):
        return "partial"
    return "present"


def _reject_score_fields(values: Mapping[str, object]) -> None:
    for key in values:
        if key in {"score", "infrastructure_score", "civilization_score"} or str(
            key
        ).endswith("_score"):
            raise ValueError("infrastructure_networks_metrics: forbidden_score_field")


def compute_infrastructure_network_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Asset inventory structure counts without a composite infrastructure score."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("infrastructure_metric_empty family=network_structure")
        return _document(
            MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    kind_counts = Counter(row.kind for row in rows.assets)
    topology_counts = Counter(row.topology for row in rows.assets)
    locations = {
        location
        for row in rows.assets
        for location in (
            (row.location_id, row.endpoint_location_id)
            if row.endpoint_location_id is not None
            else (row.location_id,)
        )
    }
    values: dict[str, object] = {
        "asset_count": rows.asset_count,
        "node_count": topology_counts.get(InfrastructureTopology.NODE.value, 0),
        "edge_count": topology_counts.get(InfrastructureTopology.EDGE.value, 0),
        "distinct_location_count": len(locations),
        "window_tick": rows.window_tick,
    }
    for kind in INFRASTRUCTURE_KIND_KEYS:
        values[f"kind_count_{kind}"] = kind_counts.get(kind, 0)
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE,
        state=state,
        observed=rows.asset_count,
        expected=rows.asset_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_infrastructure_condition_lifecycle(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Status / integrity lifecycle counts; never a health score."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("infrastructure_metric_empty family=condition_lifecycle")
        return _document(
            MetricFamilyId.INFRASTRUCTURE_CONDITION_LIFECYCLE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    status_counts = Counter(row.status for row in rows.assets)
    below_floor = 0
    integrity_sum = 0.0
    for row in rows.assets:
        integrity_sum += row.integrity
        try:
            kind = InfrastructureKind(row.kind)
            floor = INFRASTRUCTURE_CATALOG[kind].operational_integrity_min
        except (KeyError, ValueError):
            _LOG.warning("infrastructure_metric_partial_coverage reason=unknown_kind")
            continue
        if row.integrity < floor:
            below_floor += 1
    values: dict[str, object] = {
        "asset_count": rows.asset_count,
        "operational_count": status_counts.get(
            InfrastructureStatus.OPERATIONAL.value, 0
        ),
        "damaged_count": status_counts.get(InfrastructureStatus.DAMAGED.value, 0),
        "destroyed_count": status_counts.get(InfrastructureStatus.DESTROYED.value, 0),
        "mean_integrity": quantize_float(integrity_sum / rows.asset_count),
        "integrity_below_operational_floor_count": below_floor,
        "repair_eligible_count": status_counts.get(
            InfrastructureStatus.DAMAGED.value, 0
        ),
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.INFRASTRUCTURE_CONDITION_LIFECYCLE,
        state=state,
        observed=rows.asset_count,
        expected=rows.asset_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_infrastructure_effect_coverage(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Active-effect coverage counts and quantized ratios."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("infrastructure_metric_empty family=effect_coverage")
        return _document(
            MetricFamilyId.INFRASTRUCTURE_EFFECT_COVERAGE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    active = sum(1 for row in rows.assets if row.effects_active)
    inactive = rows.asset_count - active
    values: dict[str, object] = {
        "asset_count": rows.asset_count,
        "effects_active_count": active,
        "effects_inactive_count": inactive,
        "effects_active_ratio": _ratio(active, rows.asset_count),
        "travel_effect_asset_count": sum(
            1 for row in rows.assets if row.effects_active and row.kind in _TRAVEL_KINDS
        ),
        "capacity_effect_asset_count": sum(
            1
            for row in rows.assets
            if row.effects_active and row.kind in _CAPACITY_KINDS
        ),
        "resource_effect_asset_count": sum(
            1
            for row in rows.assets
            if row.effects_active and row.kind in _RESOURCE_KINDS
        ),
        "exposure_effect_asset_count": sum(
            1
            for row in rows.assets
            if row.effects_active and row.kind in _EXPOSURE_KINDS
        ),
    }
    _reject_score_fields(values)
    if inactive > 0:
        _LOG.warning(
            "infrastructure_metric_partial_coverage reason=inactive_effects count=%s",
            inactive,
        )
    return _document(
        MetricFamilyId.INFRASTRUCTURE_EFFECT_COVERAGE,
        state=state,
        observed=active,
        expected=rows.asset_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_infrastructure_maintenance_burden(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Maintenance lag and unrepaired counts; never a burden score."""
    rows = _require(analysis)
    state = _state(rows)
    if state == "unknown":
        _LOG.debug("infrastructure_metric_empty family=maintenance_burden")
        return _document(
            MetricFamilyId.INFRASTRUCTURE_MAINTENANCE_BURDEN,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    lags = [row.ticks_since_maintained for row in rows.assets]
    never_maintained = sum(
        1 for row in rows.assets if row.last_maintained_tick == row.created_tick
    )
    damaged_unrepaired = sum(
        1 for row in rows.assets if row.status == InfrastructureStatus.DAMAGED.value
    )
    lag_sum = sum(lags)
    values: dict[str, object] = {
        "asset_count": rows.asset_count,
        "mean_maintenance_lag_ticks": quantize_float(lag_sum / rows.asset_count),
        "max_maintenance_lag_ticks": max(lags),
        "assets_never_maintained_count": never_maintained,
        "damaged_unrepaired_count": damaged_unrepaired,
        "maintenance_opportunity_count": rows.asset_count - never_maintained,
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.INFRASTRUCTURE_MAINTENANCE_BURDEN,
        state=state,
        observed=rows.asset_count,
        expected=rows.asset_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def _route_rows(
    analysis: InfrastructureNetworksAnalysis,
) -> tuple[TravelRouteAnalysisRow, ...]:
    return analysis.routes


def _route_state(analysis: InfrastructureNetworksAnalysis) -> str:
    if analysis.route_count == 0:
        return "unknown"
    return "present"


def compute_travel_route_structure(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Route structure counts and capacity distribution; never a route score."""
    rows = _require(analysis)
    state = _route_state(rows)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRAVEL_ROUTE_STRUCTURE,
            state=state,
            observed=0,
            expected=rows.route_coverage_expected,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    route_rows = _route_rows(rows)
    capacity = [row.capacity for row in route_rows]
    values: dict[str, object] = {
        "route_count": len(route_rows),
        "adjacency_coverage_ratio": _ratio(
            len(route_rows),
            max(rows.route_coverage_expected, len(route_rows)),
        ),
        "road_edge_count": sum(
            1
            for asset in rows.assets
            if asset.kind == "road"
            and asset.topology == "edge"
            and asset.effects_active
        ),
        "bridge_node_count": sum(
            1
            for asset in rows.assets
            if asset.kind == "bridge"
            and asset.topology == "node"
            and asset.effects_active
        ),
        "capacity_min": min(capacity),
        "capacity_max": max(capacity),
        "capacity_mean_milli": round(sum(capacity) * 1000 / len(capacity)),
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.TRAVEL_ROUTE_STRUCTURE,
        state=state,
        observed=len(route_rows),
        expected=max(rows.route_coverage_expected, len(route_rows)),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_travel_route_condition(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Status and availability histograms; never a composite condition score."""
    rows = _require(analysis)
    state = _route_state(rows)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRAVEL_ROUTE_CONDITION,
            state=state,
            observed=0,
            expected=rows.route_coverage_expected,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    route_rows = _route_rows(rows)
    status = Counter(row.status for row in route_rows)
    availability = Counter(row.seasonal_availability for row in route_rows)
    values: dict[str, object] = {
        "open_count": status.get("open", 0),
        "restricted_count": status.get("restricted", 0),
        "closed_count": status.get("closed", 0),
        "availability_open_count": availability.get("open", 0),
        "availability_restricted_count": availability.get("restricted", 0),
        "availability_closed_count": availability.get("closed", 0),
        "risk_mean_milli": round(
            sum(row.risk for row in route_rows) * 1000 / len(route_rows)
        ),
        "quality_mean_milli": round(
            sum(row.infrastructure_quality for row in route_rows)
            * 1000
            / len(route_rows)
        ),
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.TRAVEL_ROUTE_CONDITION,
        state=state,
        observed=len(route_rows),
        expected=max(rows.route_coverage_expected, len(route_rows)),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_travel_route_blockage(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Blockage cause counts and blocked-edge coverage; never a severity score."""
    rows = _require(analysis)
    state = _route_state(rows)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRAVEL_ROUTE_BLOCKAGE,
            state=state,
            observed=0,
            expected=rows.route_coverage_expected,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    route_rows = _route_rows(rows)
    causes = Counter(row.blockage_cause for row in route_rows)
    blocked = sum(1 for row in route_rows if row.status == "closed")
    values: dict[str, object] = {
        "none_count": causes.get("none", 0),
        "weather_count": causes.get("weather", 0),
        "seasonal_count": causes.get("seasonal", 0),
        "hazard_count": causes.get("hazard", 0),
        "blocked_edge_count": blocked,
        "blockage_coverage_ratio": _ratio(blocked, len(route_rows)),
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.TRAVEL_ROUTE_BLOCKAGE,
        state=state,
        observed=blocked,
        expected=len(route_rows),
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_travel_route_belief_alignment(
    analysis: object, *, run_id: str, input_revision: str
) -> MetricDocument:
    """Researcher-only belief alignment counts; beliefs are never truth."""
    rows = _require(analysis)
    state = _route_state(rows)
    if state == "unknown":
        return _document(
            MetricFamilyId.TRAVEL_ROUTE_BELIEF_ALIGNMENT,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    route_rows = _route_rows(rows)
    window_tick = getattr(rows, "window_tick", 0)
    belief_count = sum(row.observed_belief_count for row in route_rows)
    unknown = stale = contradicted = consistent = unresolved = inconsistent = 0
    for row in route_rows:
        if row.observed_belief_count == 0:
            unknown += 1
            continue
        if row.as_of_tick < window_tick:
            stale += row.observed_belief_count
        if row.believed_closed_count:
            if row.status == "closed":
                consistent += row.observed_belief_count
            else:
                contradicted += row.observed_belief_count
                inconsistent += row.observed_belief_count
        elif row.believed_restricted_count:
            if row.status in {"restricted", "closed"}:
                consistent += row.observed_belief_count
            else:
                contradicted += row.observed_belief_count
                inconsistent += row.observed_belief_count
        else:
            unresolved += row.observed_belief_count
    values: dict[str, object] = {
        "belief_count": belief_count,
        "unknown_count": unknown,
        "stale_count": stale,
        "contradicted_count": contradicted,
        "consistent_count": consistent,
        "unresolved_count": unresolved,
        "inconsistent_count": inconsistent,
        "not_applicable_count": 0 if belief_count else len(route_rows),
    }
    _reject_score_fields(values)
    return _document(
        MetricFamilyId.TRAVEL_ROUTE_BELIEF_ALIGNMENT,
        state=state,
        observed=belief_count,
        expected=belief_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )
