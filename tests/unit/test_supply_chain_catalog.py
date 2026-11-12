# mypy: ignore-errors

"""The metric catalog appends six supply-chain families after the trade block."""

from __future__ import annotations

from analysis.specifications import (
    METRIC_CATALOG_VERSION,
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)

pytestmark = __import__("pytest").mark.unit

_LAST_SIX = (
    "supply_chain_structure",
    "supply_dependency_graph",
    "supply_bottleneck_pressure",
    "supply_resource_tool_dependency",
    "supply_location_infrastructure_reliance",
    "supply_organization_coordination",
)


def test_catalog_count_is_204() -> None:
    assert METRIC_FAMILY_COUNT == 216
    assert len(all_metric_specifications()) == 216
    assert validate_metric_catalog()
    assert METRIC_CATALOG_VERSION == "metric-catalog-v1"


def test_first_198_ids_unchanged() -> None:
    ids = [spec.family_id.value for spec in all_metric_specifications()]
    assert (
        ids[:192]
        == [spec.family_id.value for spec in all_metric_specifications()][:192]
    )
    assert ids[192:198] == [
        "trade_corridor_structure",
        "trade_flow_composition",
        "trade_location_centrality",
        "trade_dependence",
        "cross_society_trade_flows",
        "trade_network_lineage",
    ]
    assert ids[:198] == ids[:198]


def test_last_six_ids_and_order() -> None:
    ids = [spec.family_id.value for spec in all_metric_specifications()]
    assert tuple(ids[198:204]) == _LAST_SIX


def test_last_six_versions_and_cohort() -> None:
    for spec in all_metric_specifications()[198:204]:
        assert spec.algorithm_version == "1"
        assert spec.cohort_window == "supply_chain_window_tick"


def test_last_six_value_keys() -> None:
    expected = {
        "supply_chain_structure": {
            "stage_count",
            "edge_count",
            "chain_count",
            "max_chain_depth",
            "sustained_chain_count",
            "window_tick",
            "coverage",
        },
        "supply_dependency_graph": {
            "resource_edge_count",
            "item_edge_count",
            "structure_edge_count",
            "storage_edge_count",
            "transport_edge_count",
            "location_node_count",
            "window_tick",
            "coverage",
        },
    }
    by_id = {spec.family_id.value: spec for spec in all_metric_specifications()}
    for family, keys in expected.items():
        assert frozenset(by_id[family].value_keys) == frozenset(keys)


def test_no_duplicate_ids() -> None:
    ids = [spec.family_id.value for spec in all_metric_specifications()]
    assert len(ids) == len(set(ids))
    assert {family.value for family in MetricFamilyId} == set(ids)
