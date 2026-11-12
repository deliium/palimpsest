"""Infrastructure metric families and MetricComputationInputs emit gate."""

from __future__ import annotations

import pytest

from analysis.infrastructure_metrics import (
    compute_infrastructure_condition_lifecycle,
    compute_infrastructure_effect_coverage,
    compute_infrastructure_maintenance_burden,
    compute_infrastructure_network_structure,
    harvest_infrastructure_networks_analysis,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    validate_metric_catalog,
)
from world.identifiers import EntityId
from world.infrastructure import (
    InfrastructureAsset,
    InfrastructureKind,
    InfrastructureStatus,
    InfrastructureTopology,
    mint_infrastructure_id,
)

pytestmark = pytest.mark.unit


def _asset(
    kind: InfrastructureKind,
    *,
    project: str,
    status: InfrastructureStatus = InfrastructureStatus.OPERATIONAL,
    integrity: float = 1.0,
    endpoint: str | None = None,
) -> InfrastructureAsset:
    location_id = EntityId("loc-a")
    endpoint_id = None if endpoint is None else EntityId(endpoint)
    project_id = EntityId(project)
    return InfrastructureAsset(
        asset_id=mint_infrastructure_id(
            kind=kind,
            location_id=location_id,
            endpoint_location_id=endpoint_id,
            created_tick=1,
            project_id=project_id,
        ),
        kind=kind,
        topology=(
            InfrastructureTopology.EDGE
            if endpoint is not None
            else InfrastructureTopology.NODE
        ),
        status=status,
        integrity=integrity,
        location_id=location_id,
        endpoint_location_id=endpoint_id,
        linked_structure_id=EntityId(f"struct-{project}"),
        linked_project_id=project_id,
        created_tick=1,
        last_maintained_tick=1,
    )


def test_catalog_count_188() -> None:
    assert METRIC_FAMILY_COUNT == 220
    catalog = validate_metric_catalog()
    assert len(catalog) == 220


def test_empty_analysis_unknown() -> None:
    empty = harvest_infrastructure_networks_analysis((), window_tick=0)
    structure = compute_infrastructure_network_structure(
        empty, run_id="run", input_revision="rev"
    )
    assert structure.availability.value == "unknown"
    assert structure.values == {}


def test_structure_and_condition_metrics() -> None:
    analysis = harvest_infrastructure_networks_analysis(
        (
            _asset(InfrastructureKind.BRIDGE, project="b1"),
            _asset(
                InfrastructureKind.ROAD,
                project="r1",
                endpoint="loc-b",
            ),
        ),
        window_tick=10,
    )
    structure = compute_infrastructure_network_structure(
        analysis, run_id="run", input_revision="rev"
    )
    assert (
        structure.metric_family
        == MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE.value
    )
    assert structure.values["asset_count"] == 2
    assert structure.values["edge_count"] == 1
    assert structure.values["kind_count_bridge"] == 1
    assert "score" not in structure.values
    condition = compute_infrastructure_condition_lifecycle(
        analysis, run_id="run", input_revision="rev"
    )
    assert condition.values["operational_count"] == 2


def test_effect_and_maintenance_metrics() -> None:
    analysis = harvest_infrastructure_networks_analysis(
        (
            _asset(InfrastructureKind.BRIDGE, project="b1"),
            _asset(
                InfrastructureKind.BRIDGE,
                project="b2",
                status=InfrastructureStatus.DAMAGED,
                integrity=0.2,
            ),
        ),
        window_tick=20,
    )
    coverage = compute_infrastructure_effect_coverage(
        analysis, run_id="run", input_revision="rev"
    )
    assert coverage.values["effects_active_count"] == 1
    burden = compute_infrastructure_maintenance_burden(
        analysis, run_id="run", input_revision="rev"
    )
    assert burden.values["damaged_unrepaired_count"] == 1
    assert "infrastructure_score" not in burden.values


def test_metric_service_emit_gate() -> None:
    analysis = harvest_infrastructure_networks_analysis(
        (_asset(InfrastructureKind.STORAGE, project="s1"),),
        window_tick=5,
    )
    with_gate = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=64,
            infrastructure_networks_analysis=analysis,
        )
    )
    families = {doc.metric_family for doc in with_gate.documents}
    assert MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE.value in families
    assert MetricFamilyId.INFRASTRUCTURE_MAINTENANCE_BURDEN.value in families
    without = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-2",
            input_revision="rev-2",
            window_end=64,
        )
    )
    absent = {doc.metric_family for doc in without.documents}
    assert MetricFamilyId.INFRASTRUCTURE_NETWORK_STRUCTURE.value not in absent
