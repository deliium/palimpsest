# mypy: ignore-errors
"""Catalog append pin for the six trade-network families."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

from analysis.specifications import (
    CROSS_SOCIETY_TRADE_FLOWS_KEYS,
    METRIC_FAMILY_COUNT,
    TRADE_CORRIDOR_STRUCTURE_KEYS,
    TRADE_DEPENDENCE_KEYS,
    TRADE_FLOW_COMPOSITION_KEYS,
    TRADE_LOCATION_CENTRALITY_KEYS,
    TRADE_NETWORK_LINEAGE_KEYS,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)
from analysis.trade_networks_analysis import harvest_trade_networks_analysis
from analysis.trade_networks_metrics import assemble_trade_network_metrics
from world.events import Given
from world.identifiers import EntityId, EventId

TRADE_FAMILIES = (
    MetricFamilyId.TRADE_CORRIDOR_STRUCTURE,
    MetricFamilyId.TRADE_FLOW_COMPOSITION,
    MetricFamilyId.TRADE_LOCATION_CENTRALITY,
    MetricFamilyId.TRADE_DEPENDENCE,
    MetricFamilyId.CROSS_SOCIETY_TRADE_FLOWS,
    MetricFamilyId.TRADE_NETWORK_LINEAGE,
)


def test_catalog_count_is_204() -> None:
    assert METRIC_FAMILY_COUNT == 220
    catalog = validate_metric_catalog()
    assert len(catalog) == 220
    assert len(all_metric_specifications()) == 220


def test_first_198_ids_order_versions_and_keys_are_unchanged() -> None:
    specs = all_metric_specifications()
    first = specs[:198]
    supply = specs[198:204]
    market = specs[204:208]
    trade_values = {family.value for family in TRADE_FAMILIES}
    assert not any(spec.family_id.value in trade_values for spec in first[:192])
    assert [spec.family_id for spec in first[192:]] == list(TRADE_FAMILIES)
    assert len(supply) == 6
    assert len(market) == 4
    assert len({spec.family_id for spec in specs}) == 220
    for spec in first:
        assert spec.algorithm_version == "1"
        assert spec.value_keys


def test_six_trade_families_are_the_preceding_block() -> None:
    specs = all_metric_specifications()
    assert [spec.family_id for spec in specs[192:198]] == list(TRADE_FAMILIES)
    for spec in specs[192:198]:
        assert spec.algorithm_version == "1"
        assert spec.cohort_window == "trade_networks_window_tick"


def test_trade_family_value_keys_match_documents() -> None:
    event = SimpleNamespace(
        event_id=EventId("evt-1"),
        tick=0,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=Given(
            recipient_id=EntityId("body-b"), item_id=EntityId("item-1")
        ),
        occurrence=SimpleNamespace(origin_location_id=EntityId("loc-a")),
    )
    analysis = harvest_trade_networks_analysis(events=(event,))
    documents = assemble_trade_network_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    expected = {
        "trade_corridor_structure": TRADE_CORRIDOR_STRUCTURE_KEYS,
        "trade_flow_composition": TRADE_FLOW_COMPOSITION_KEYS,
        "trade_location_centrality": TRADE_LOCATION_CENTRALITY_KEYS,
        "trade_dependence": TRADE_DEPENDENCE_KEYS,
        "cross_society_trade_flows": CROSS_SOCIETY_TRADE_FLOWS_KEYS,
        "trade_network_lineage": TRADE_NETWORK_LINEAGE_KEYS,
    }
    for document in documents:
        keys = expected[document.metric_family]
        if document.availability.value == "unknown":
            assert dict(document.values) == {}
        else:
            assert tuple(document.values) == tuple(sorted(keys))


def test_first_198_are_unchanged() -> None:
    specs = all_metric_specifications()[:198]
    payload = [
        {
            "id": spec.family_id.value,
            "version": spec.algorithm_version,
            "keys": list(spec.value_keys),
        }
        for spec in specs
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert digest == (
        "c3d280250a65747e90952a82d88fe545d7dd39ca7fae2d7bb29ad9d922302851"
    )
