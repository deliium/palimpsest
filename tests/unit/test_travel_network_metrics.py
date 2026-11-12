"""V4-17 four appended travel-network metric families."""

from __future__ import annotations

import pytest

from analysis.infrastructure_metrics import (
    compute_travel_route_belief_alignment,
    compute_travel_route_blockage,
    compute_travel_route_condition,
    compute_travel_route_structure,
)
from analysis.infrastructure_networks_analysis import (
    InfrastructureAssetAnalysisRow,
    InfrastructureNetworksAnalysis,
    TravelRouteAnalysisRow,
)
from analysis.specifications import METRIC_FAMILY_COUNT, metric_specification

pytestmark = pytest.mark.unit

A = "loc-a"
B = "loc-b"


def _row(**changes: object) -> TravelRouteAnalysisRow:
    values: dict[str, object] = {
        "origin_id": A,
        "destination_id": B,
        "status": "open",
        "seasonal_availability": "open",
        "blockage_cause": "none",
        "duration_ticks": 2,
        "fatigue_cost": 3.0,
        "capacity": 8,
        "risk": 0.1,
        "infrastructure_quality": 0.5,
        "as_of_tick": 1,
    }
    values.update(changes)
    return TravelRouteAnalysisRow(**values)  # type: ignore[arg-type]


def _analysis(*rows: TravelRouteAnalysisRow) -> InfrastructureNetworksAnalysis:
    return InfrastructureNetworksAnalysis(
        assets=(), routes=tuple(rows), route_coverage_expected=len(rows)
    )


def test_catalog_is_198_and_prior_families_stay_before() -> None:
    assert METRIC_FAMILY_COUNT == 220
    for family in (
        "travel_route_structure",
        "travel_route_condition",
        "travel_route_blockage",
        "travel_route_belief_alignment",
    ):
        assert metric_specification(family).family_id.value == family


def test_structure_condition_and_blockage_counts() -> None:
    analysis = _analysis(
        _row(),
        _row(
            destination_id="loc-c",
            status="closed",
            seasonal_availability="closed",
            blockage_cause="seasonal",
            capacity=4,
            risk=0.4,
        ),
    )
    structure = compute_travel_route_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert structure.values["route_count"] == 2
    assert structure.values["capacity_min"] == 4
    assert structure.values["capacity_max"] == 8
    condition = compute_travel_route_condition(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert condition.values["open_count"] == 1
    assert condition.values["closed_count"] == 1
    assert condition.values["availability_closed_count"] == 1
    blockage = compute_travel_route_blockage(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert blockage.values["none_count"] == 1
    assert blockage.values["seasonal_count"] == 1
    assert blockage.values["blocked_edge_count"] == 1


def test_structure_counts_operational_roads_and_bridges() -> None:
    road = InfrastructureAssetAnalysisRow(
        asset_id="infra-road",
        kind="road",
        topology="edge",
        status="operational",
        integrity=0.8,
        location_id=A,
        endpoint_location_id=B,
        effects_active=True,
        created_tick=0,
        last_maintained_tick=0,
        ticks_since_maintained=0,
        linked_project_id="proj-road",
    )
    bridge = InfrastructureAssetAnalysisRow(
        asset_id="infra-bridge",
        kind="bridge",
        topology="node",
        status="operational",
        integrity=0.7,
        location_id=A,
        endpoint_location_id=None,
        effects_active=True,
        created_tick=0,
        last_maintained_tick=0,
        ticks_since_maintained=0,
        linked_project_id="proj-bridge",
    )
    analysis = InfrastructureNetworksAnalysis(
        assets=(road, bridge),
        routes=(_row(infrastructure_quality=0.5),),
        route_coverage_expected=1,
    )
    document = compute_travel_route_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["road_edge_count"] == 1
    assert document.values["bridge_node_count"] == 1


def test_belief_alignment_is_researcher_only() -> None:
    analysis = _analysis(
        _row(observed_belief_count=2, believed_closed_count=1),
        _row(
            destination_id="loc-c",
            status="closed",
            observed_belief_count=1,
            believed_closed_count=1,
        ),
    )
    document = compute_travel_route_belief_alignment(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["belief_count"] == 3
    assert document.values["contradicted_count"] == 2
    assert document.values["consistent_count"] == 1
    assert "score" not in document.values


def test_belief_alignment_counts_stale_rows() -> None:
    analysis = InfrastructureNetworksAnalysis(
        assets=(),
        routes=(_row(observed_belief_count=2, believed_closed_count=1),),
        route_coverage_expected=1,
        window_tick=5,
    )
    document = compute_travel_route_belief_alignment(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert document.values["stale_count"] == 2


def test_empty_routes_are_unknown_not_fabricated_zero() -> None:
    document = compute_travel_route_structure(
        InfrastructureNetworksAnalysis(assets=()),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability.value == "unknown"


def test_production_analysis_builder_feeds_metric_service() -> None:
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )
    from experiments.infrastructure_completed_run import (
        build_completed_run_infrastructure_networks_analysis,
    )
    from world.identifiers import EntityId
    from world.travel_network import (
        RouteBlockageCause,
        RouteCondition,
        RouteStatus,
        SeasonalAvailability,
    )

    route = RouteCondition(
        origin_id=EntityId("loc-a"),
        destination_id=EntityId("loc-b"),
        status=RouteStatus.OPEN,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=RouteBlockageCause.NONE,
        duration_ticks=2,
        fatigue_cost=3.0,
        capacity=8,
        risk=0.1,
        infrastructure_quality=0.5,
        reason_codes=(),
        as_of_tick=1,
    )
    analysis = build_completed_run_infrastructure_networks_analysis(
        (),
        routes=(route,),
        belief_counts={("loc-a", "loc-b"): (2, 1, 0)},
    )
    documents = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=2,
            travel_network_analysis=analysis,
        )
    ).documents
    alignment = next(
        document
        for document in documents
        if document.metric_family == "travel_route_belief_alignment"
    )
    assert alignment.values["belief_count"] == 2
    assert alignment.values["contradicted_count"] == 2


def test_metric_service_emits_unknown_route_families_for_empty_input() -> None:
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )

    inputs = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=1,
        travel_network_analysis=InfrastructureNetworksAnalysis(assets=()),
    )
    documents = assemble_metric_documents(inputs).documents
    families = {document.metric_family for document in documents}
    for family in (
        "travel_route_structure",
        "travel_route_condition",
        "travel_route_blockage",
        "travel_route_belief_alignment",
    ):
        assert family in families
        assert next(
            document.availability.value
            for document in documents
            if document.metric_family == family
        ) == "unknown"
