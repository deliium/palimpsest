# mypy: ignore-errors
"""Eight economic-cascade metric documents and their state mapping."""

from __future__ import annotations

import pytest

from analysis.economic_cascades_analysis import (
    empty_economic_cascades_analysis,
    harvest_economic_cascades_analysis,
)
from analysis.economic_cascades_contract import (
    CascadeAvailability,
    CascadeCoverage,
)
from analysis.economic_cascades_metrics import (
    compute_cascade_coverage,
    compute_cascade_dependency_structure,
    compute_cascade_propagation,
    compute_infrastructure_destruction_cascade,
    compute_population_loss_cascade,
    compute_resource_loss_cascade,
    compute_route_closure_cascade,
    compute_tool_shortage_cascade,
)
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId, metric_specification
from tests.unit.test_economic_cascades_analysis import (
    _harvest_events,
    _recipes,
    _stage,
)

pytestmark = pytest.mark.unit

_COMPUTE = {
    "resource_loss_cascade": compute_resource_loss_cascade,
    "route_closure_cascade": compute_route_closure_cascade,
    "infrastructure_destruction_cascade": (
        compute_infrastructure_destruction_cascade
    ),
    "population_loss_cascade": compute_population_loss_cascade,
    "tool_shortage_cascade": compute_tool_shortage_cascade,
    "cascade_dependency_structure": compute_cascade_dependency_structure,
    "cascade_propagation": compute_cascade_propagation,
    "cascade_coverage": compute_cascade_coverage,
}


def _analysis():
    return harvest_economic_cascades_analysis(
        events=_harvest_events(),
        recipe_specs=_recipes(),
        stages=[_stage(completions=1), _stage(completions=0, sequence=1)],
    )


def test_all_eight_families_are_present_and_wired() -> None:
    for name in _COMPUTE:
        spec = metric_specification(name)
        assert spec.family_id.value == name
        assert spec.value_keys


def test_documents_emit_with_an_analysis() -> None:
    analysis = _analysis()
    for name, compute in _COMPUTE.items():
        document = compute(analysis, run_id="run-1", input_revision="rev-1")
        assert document.metric_family == name
        assert document.coverage.observed >= 0
    resource = compute_resource_loss_cascade(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert resource.availability is not MetricAvailability.UNKNOWN


def test_documents_are_unknown_without_an_analysis() -> None:
    empty = empty_economic_cascades_analysis()
    for compute in _COMPUTE.values():
        document = compute(empty, run_id="run-1", input_revision="rev-1")
        assert document.availability is MetricAvailability.UNKNOWN
        assert document.values == {}


def test_kind_family_reports_only_its_own_kind() -> None:
    analysis = _analysis()
    document = compute_resource_loss_cascade(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["disruption_count"] >= 1
    assert document.values["linked_chain_count"] >= 1
    assert document.values["availability"] in {
        CascadeAvailability.AVAILABLE.value,
        CascadeAvailability.INSUFFICIENT_SAMPLES.value,
        CascadeAvailability.UNAVAILABLE.value,
    }
    route = compute_route_closure_cascade(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert route.metric_family == MetricFamilyId.ROUTE_CLOSURE_CASCADE.value


def test_dependency_document_counts_edge_kinds() -> None:
    analysis = _analysis()
    document = compute_cascade_dependency_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["stage_count"] >= 1
    assert document.values["dependency_edge_count"] >= 1
    assert (
        document.values["resource_edge_count"]
        + document.values["item_edge_count"]
        + document.values["tool_edge_count"]
        + document.values["infrastructure_edge_count"]
        + document.values["transport_edge_count"]
        >= 1
    )


def test_coverage_document_maps_the_coverage_row() -> None:
    analysis = _analysis()
    document = compute_cascade_coverage(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["window_count"] >= 1
    assert document.values["coverage"] in {
        CascadeCoverage.COMPLETE.value,
        CascadeCoverage.PARTIAL.value,
        CascadeCoverage.MISSING.value,
    }


def test_no_metric_family_aggregates_the_five_kinds() -> None:
    for family in (
        MetricFamilyId.RESOURCE_LOSS_CASCADE,
        MetricFamilyId.ROUTE_CLOSURE_CASCADE,
        MetricFamilyId.INFRASTRUCTURE_DESTRUCTION_CASCADE,
        MetricFamilyId.POPULATION_LOSS_CASCADE,
        MetricFamilyId.TOOL_SHORTAGE_CASCADE,
    ):
        spec = metric_specification(family)
        assert "cascade_score" not in spec.formulas
        assert "severity" not in spec.formulas


def test_insufficient_samples_maps_to_partial() -> None:
    analysis = _analysis()
    document = compute_cascade_propagation(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    if document.values["availability"] != CascadeAvailability.AVAILABLE.value:
        assert document.availability is MetricAvailability.PARTIAL


def test_population_loss_kind_is_declared() -> None:
    analysis = _analysis()
    document = compute_population_loss_cascade(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.metric_family == MetricFamilyId.POPULATION_LOSS_CASCADE.value
    assert document.availability is MetricAvailability.UNKNOWN
