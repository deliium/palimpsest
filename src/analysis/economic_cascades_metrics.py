"""Eight detached economic-cascade metric families (catalog 236 -> 244)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Final

from analysis.economic_cascades_analysis import EconomicCascadesAnalysis
from analysis.economic_cascades_contract import (
    CASCADE_FORBIDDEN_KEYS,
    ECONOMIC_CASCADES_POLICY_VERSION,
    CascadeAvailability,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
    EconomicCascadesError,
)
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_cascade_coverage",
    "compute_cascade_dependency_structure",
    "compute_cascade_propagation",
    "compute_infrastructure_destruction_cascade",
    "compute_population_loss_cascade",
    "compute_resource_loss_cascade",
    "compute_route_closure_cascade",
    "compute_tool_shortage_cascade",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)
_POLICY_TOKEN: Final[str] = "economic-cascades"


def _require(analysis: object) -> EconomicCascadesAnalysis:
    if type(analysis) is not EconomicCascadesAnalysis:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return analysis


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _reject_forbidden(values: Mapping[str, object]) -> None:
    for key in values:
        if str(key).lower() in CASCADE_FORBIDDEN_KEYS:
            raise EconomicCascadesError("economic_cascades_forbidden_key")


def _document(
    family: MetricFamilyId,
    *,
    state: str,
    observed: int,
    expected: int,
    run_id: str,
    input_revision: str,
    values: Mapping[str, object],
    notes_code: str,
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
            observed=observed,
            expected=expected,
            ratio=_ratio(observed, expected),
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
            source_kind="economic_cascades_analysis",
            source_ids=(
                run_id,
                input_revision,
                ECONOMIC_CASCADES_POLICY_VERSION,
                _POLICY_TOKEN,
                notes_code,
            ),
        ),
    )


def _latest_window(analysis: EconomicCascadesAnalysis) -> int:
    return analysis.coverage_row.window_index


def _kind_document(
    family: MetricFamilyId,
    *,
    kind: CascadeDisruptionKind,
    analysis: EconomicCascadesAnalysis,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    episode = next(
        (
            row
            for row in reversed(analysis.episodes)
            if row.kind is kind
            and row.window_index == _latest_window(analysis)
        ),
        None,
    )
    if episode is None or analysis.coverage is CascadeCoverage.MISSING:
        return _document(
            family,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="no_disruption_episode",
        )
    propagation = next(
        (
            row
            for row in analysis.propagation_rows
            if row.disruption_kind is kind
            and row.window_index == episode.window_index
        ),
        None,
    )
    chain_count = propagation.chain_count if propagation else 0
    linked = propagation.linked_chain_count if propagation else 0
    shortfall_count = sum(
        1
        for row in analysis.stages
        if row.window_index == episode.window_index and row.demand_count > 0
    )
    values: dict[str, object] = {
        "cascade_window_tick": episode.window_tick,
        "disruption_count": episode.disruption_count,
        "stage_shortfall_count": shortfall_count,
        "linked_chain_count": linked,
        "unlinked_chain_count": (
            propagation.unlinked_chain_count if propagation else 0
        ),
        "unresolved_chain_count": (
            propagation.unresolved_chain_count if propagation else 0
        ),
        "mean_chain_depth_milli": (
            propagation.mean_depth_milli if propagation else 0
        ),
        "mean_lag_milli": propagation.mean_lag_milli if propagation else 0,
        "propagation_share_milli": (
            (1_000 * linked) // chain_count if chain_count else 0
        ),
        "coverage": (propagation.coverage if propagation else episode.coverage).value,
        "availability": (
            propagation.availability
            if propagation
            else CascadeAvailability.UNAVAILABLE
        ).value,
    }
    state = (
        "present"
        if values["availability"] == CascadeAvailability.AVAILABLE.value
        else "partial"
    )
    return _document(
        family,
        state=state,
        observed=linked,
        expected=chain_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code=kind.value,
    )


def compute_resource_loss_cascade(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _kind_document(
        MetricFamilyId.RESOURCE_LOSS_CASCADE,
        kind=CascadeDisruptionKind.RESOURCE_LOSS,
        analysis=_require(analysis),
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_route_closure_cascade(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _kind_document(
        MetricFamilyId.ROUTE_CLOSURE_CASCADE,
        kind=CascadeDisruptionKind.ROUTE_CLOSURE,
        analysis=_require(analysis),
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_infrastructure_destruction_cascade(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _kind_document(
        MetricFamilyId.INFRASTRUCTURE_DESTRUCTION_CASCADE,
        kind=CascadeDisruptionKind.INFRASTRUCTURE_DESTRUCTION,
        analysis=_require(analysis),
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_population_loss_cascade(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _kind_document(
        MetricFamilyId.POPULATION_LOSS_CASCADE,
        kind=CascadeDisruptionKind.POPULATION_LOSS,
        analysis=_require(analysis),
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_tool_shortage_cascade(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    return _kind_document(
        MetricFamilyId.TOOL_SHORTAGE_CASCADE,
        kind=CascadeDisruptionKind.TOOL_SHORTAGE,
        analysis=_require(analysis),
        run_id=run_id,
        input_revision=input_revision,
    )


def compute_cascade_dependency_structure(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    if value.coverage is CascadeCoverage.MISSING or not value.stages:
        return _document(
            MetricFamilyId.CASCADE_DEPENDENCY_STRUCTURE,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="no_stage_evidence",
        )
    counts = {kind: 0 for kind in CascadeDependencyKind}
    for edge in value.edges:
        counts[edge.kind] += 1
    values: dict[str, object] = {
        "cascade_window_tick": value.window_tick,
        "stage_count": value.stage_count,
        "dependency_edge_count": value.dependency_edge_count,
        "resource_edge_count": counts[CascadeDependencyKind.RESOURCE_INPUT],
        "item_edge_count": counts[CascadeDependencyKind.ITEM_INPUT],
        "tool_edge_count": counts[CascadeDependencyKind.TOOL_DEPENDENCY],
        "infrastructure_edge_count": counts[
            CascadeDependencyKind.INFRASTRUCTURE_DEPENDENCY
        ],
        "transport_edge_count": counts[CascadeDependencyKind.TRANSPORT_DEPENDENCY],
        "labor_join_count": value.labor_join_count,
        "max_depth": value.max_depth,
        "coverage": value.coverage.value,
        "availability": (
            CascadeAvailability.AVAILABLE
            if value.dependency_edge_count
            else CascadeAvailability.UNAVAILABLE
        ).value,
    }
    return _document(
        MetricFamilyId.CASCADE_DEPENDENCY_STRUCTURE,
        state="present",
        observed=value.stage_count,
        expected=value.stage_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="dependency_structure",
    )


def compute_cascade_propagation(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    if value.coverage is CascadeCoverage.MISSING or not value.propagation_rows:
        return _document(
            MetricFamilyId.CASCADE_PROPAGATION,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="no_propagation_rows",
        )
    chain_count = sum(row.chain_count for row in value.propagation_rows)
    linked = sum(row.linked_chain_count for row in value.propagation_rows)
    unlinked = sum(row.unlinked_chain_count for row in value.propagation_rows)
    unresolved = sum(row.unresolved_chain_count for row in value.propagation_rows)
    total_depth = sum(
        row.mean_depth_milli * row.chain_count for row in value.propagation_rows
    )
    total_lag = sum(
        row.mean_lag_milli * row.chain_count for row in value.propagation_rows
    )
    values: dict[str, object] = {
        "cascade_window_tick": value.window_tick,
        "disruption_kind_count": len(
            {row.disruption_kind for row in value.propagation_rows}
        ),
        "chain_count": chain_count,
        "linked_chain_count": linked,
        "unlinked_chain_count": unlinked,
        "unresolved_chain_count": unresolved,
        "mean_depth_milli": (
            total_depth // chain_count if chain_count else 0
        ),
        "mean_lag_milli": total_lag // chain_count if chain_count else 0,
        "downstream_stage_count": len(
            {row.downstream_recipe_id for row in value.chains}
        ),
        "coverage": value.chain_coverage.value,
        "availability": (
            CascadeAvailability.AVAILABLE
            if linked >= 3
            else (
                CascadeAvailability.INSUFFICIENT_SAMPLES
                if linked
                else CascadeAvailability.UNAVAILABLE
            )
        ).value,
    }
    state = (
        "present"
        if values["availability"] == CascadeAvailability.AVAILABLE.value
        else "partial"
    )
    return _document(
        MetricFamilyId.CASCADE_PROPAGATION,
        state=state,
        observed=linked,
        expected=chain_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="propagation",
    )


def compute_cascade_coverage(
    analysis: EconomicCascadesAnalysis, *, run_id: str, input_revision: str
) -> MetricDocument:
    value = _require(analysis)
    if value.coverage is CascadeCoverage.MISSING:
        return _document(
            MetricFamilyId.CASCADE_COVERAGE,
            state="unknown",
            observed=0,
            expected=0,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="no_evidence",
        )
    row = value.coverage_row
    values: dict[str, object] = {
        "cascade_window_tick": row.window_tick,
        "window_count": row.window_count,
        "event_count": row.event_count,
        "disruption_count": row.disruption_count,
        "stage_count": row.stage_count,
        "dependency_edge_count": row.dependency_edge_count,
        "chain_count": row.chain_count,
        "linked_chain_count": row.linked_chain_count,
        "truncated": row.truncated,
        "coverage": row.coverage.value,
        "availability": row.availability.value,
    }
    return _document(
        MetricFamilyId.CASCADE_COVERAGE,
        state=(
            "present"
            if row.availability is CascadeAvailability.AVAILABLE
            else "partial"
        ),
        observed=row.linked_chain_count,
        expected=row.chain_count,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="coverage",
    )
