"""Six detached supply-chain metric families (catalog 198 -> 204)."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Mapping
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
from analysis.supply_chain_analysis import SupplyChainAnalysis
from analysis.supply_chain_contract import (
    SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION,
    SUPPLY_FORBIDDEN_KEYS,
    SupplyBottleneckKind,
    SupplyChainError,
    SupplyCoverage,
    SupplyEdgeKind,
)
from world.identifiers import require_stable_id

__all__ = [
    "assemble_supply_chain_metrics",
    "compute_supply_bottleneck_pressure",
    "compute_supply_chain_structure",
    "compute_supply_dependency_graph",
    "compute_supply_location_infrastructure_reliance",
    "compute_supply_organization_coordination",
    "compute_supply_resource_tool_dependency",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _require(analysis: object) -> SupplyChainAnalysis:
    if type(analysis) is not SupplyChainAnalysis:
        raise SupplyChainError("supply_chain_metrics_invalid_analysis")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _state(coverage: SupplyCoverage) -> str:
    if coverage is SupplyCoverage.MISSING:
        return "unknown"
    if coverage is SupplyCoverage.PARTIAL:
        return "partial"
    return "present"


def _reject_forbidden(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in SUPPLY_FORBIDDEN_KEYS:
            raise SupplyChainError("supply_chain_forbidden_metric_key")


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
        _reject_forbidden(values)
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
            source_kind="supply_chain_analysis",
            source_ids=(
                run_id,
                input_revision,
                SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION,
                "supply-chain",
            ),
            notes_code="detached_supply_chain_analysis",
        ),
    )


def _ids(run_id: str, input_revision: str) -> tuple[str, str]:
    return (
        require_stable_id("run_id", run_id),
        require_stable_id("input_revision", input_revision),
    )


def _coverage_value(analysis: SupplyChainAnalysis) -> str:
    return analysis.coverage.value


def compute_supply_chain_structure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_CHAIN_STRUCTURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    values = {
        "stage_count": rows.stage_count,
        "edge_count": rows.edge_count,
        "chain_count": rows.chain_count,
        "max_chain_depth": rows.max_depth,
        "sustained_chain_count": rows.sustained_chain_count,
        "window_tick": rows.window_tick,
        "coverage": _coverage_value(rows),
    }
    return _document(
        MetricFamilyId.SUPPLY_CHAIN_STRUCTURE,
        state=state,
        observed=rows.stage_count,
        expected=rows.stage_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_supply_dependency_graph(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_DEPENDENCY_GRAPH,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    counts = Counter(edge.edge_kind for edge in rows.edges)
    values = {
        "resource_edge_count": counts.get(SupplyEdgeKind.RESOURCE_TO_ITEM, 0),
        "item_edge_count": counts.get(SupplyEdgeKind.ITEM_TO_ITEM, 0),
        "structure_edge_count": counts.get(SupplyEdgeKind.ITEM_TO_STRUCTURE, 0),
        "storage_edge_count": counts.get(SupplyEdgeKind.ITEM_TO_STORAGE, 0),
        "transport_edge_count": counts.get(SupplyEdgeKind.TRANSPORT, 0),
        "location_node_count": rows.location_count,
        "window_tick": rows.window_tick,
        "coverage": _coverage_value(rows),
    }
    return _document(
        MetricFamilyId.SUPPLY_DEPENDENCY_GRAPH,
        state=state,
        observed=rows.edge_count,
        expected=rows.edge_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_supply_bottleneck_pressure(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_BOTTLENECK_PRESSURE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    counts = Counter(row.kind for row in rows.bottlenecks)
    values: dict[str, object] = {
        f"{kind.value}_count": counts.get(kind, 0) for kind in SupplyBottleneckKind
    }
    values["max_ratio_milli"] = max(
        (row.ratio_milli for row in rows.bottlenecks), default=0
    )
    values["window_tick"] = rows.window_tick
    values["coverage"] = _coverage_value(rows)
    return _document(
        MetricFamilyId.SUPPLY_BOTTLENECK_PRESSURE,
        state=state,
        observed=rows.bottleneck_count,
        expected=rows.bottleneck_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_supply_resource_tool_dependency(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_RESOURCE_TOOL_DEPENDENCY,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    harvest = sum(1 for row in rows.stages if row.action == "harvest")
    craft = sum(1 for row in rows.stages if row.action == "craft")
    tool_edges = [
        edge for edge in rows.edges if edge.edge_kind is SupplyEdgeKind.TOOL_TO_STAGE
    ]
    values = {
        "harvest_stage_count": harvest,
        "craft_stage_count": craft,
        "tool_stage_count": len(tool_edges),
        "tool_downstream_stage_count": len({edge.to_token for edge in tool_edges}),
        "resource_edge_count": sum(
            1
            for edge in rows.edges
            if edge.edge_kind is SupplyEdgeKind.RESOURCE_TO_ITEM
        ),
        "window_tick": rows.window_tick,
        "coverage": _coverage_value(rows),
    }
    return _document(
        MetricFamilyId.SUPPLY_RESOURCE_TOOL_DEPENDENCY,
        state=state,
        observed=rows.stage_count,
        expected=rows.stage_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_supply_location_infrastructure_reliance(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_LOCATION_INFRASTRUCTURE_RELIANCE,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    infra_edges = [
        edge
        for edge in rows.edges
        if edge.edge_kind is SupplyEdgeKind.INFRASTRUCTURE_TO_STAGE
    ]
    values = {
        "location_count": rows.location_count,
        "infrastructure_backed_stage_count": len(
            {edge.to_token for edge in infra_edges}
        ),
        "infrastructure_location_count": len({edge.from_token for edge in infra_edges}),
        "single_location_stage_count": sum(
            1
            for row in rows.bottlenecks
            if row.kind is SupplyBottleneckKind.SINGLE_LOCATION_CONCENTRATION
        ),
        "window_tick": rows.window_tick,
        "coverage": _coverage_value(rows),
    }
    return _document(
        MetricFamilyId.SUPPLY_LOCATION_INFRASTRUCTURE_RELIANCE,
        state=state,
        observed=rows.location_count,
        expected=rows.location_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_supply_organization_coordination(
    analysis: object,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    rows = _require(analysis)
    run_id, input_revision = _ids(run_id, input_revision)
    state = _state(rows.coverage)
    if state == "unknown":
        return _document(
            MetricFamilyId.SUPPLY_ORGANIZATION_COORDINATION,
            state=state,
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
        )
    org_edges = [
        edge
        for edge in rows.edges
        if edge.edge_kind is SupplyEdgeKind.ORGANIZATION_TO_STAGE
    ]
    values = {
        "organization_count": rows.organization_count,
        "organization_stage_count": len({edge.to_token for edge in org_edges}),
        "organization_claim_count": sum(row.claim_count for row in rows.organizations),
        "organization_dependency_count": sum(
            1
            for row in rows.bottlenecks
            if row.kind is SupplyBottleneckKind.ORGANIZATION_DEPENDENCY
        ),
        "window_tick": rows.window_tick,
        "coverage": _coverage_value(rows),
    }
    return _document(
        MetricFamilyId.SUPPLY_ORGANIZATION_COORDINATION,
        state=state,
        observed=rows.organization_count,
        expected=rows.organization_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def assemble_supply_chain_metrics(
    analysis: SupplyChainAnalysis,
    *,
    run_id: str,
    input_revision: str,
) -> tuple[MetricDocument, ...]:
    """Return the six documents in catalog order."""
    _require(analysis)
    return (
        compute_supply_chain_structure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_supply_dependency_graph(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_supply_bottleneck_pressure(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_supply_resource_tool_dependency(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_supply_location_infrastructure_reliance(
            analysis, run_id=run_id, input_revision=input_revision
        ),
        compute_supply_organization_coordination(
            analysis, run_id=run_id, input_revision=input_revision
        ),
    )
