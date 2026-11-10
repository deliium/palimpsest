# mypy: ignore-errors
"""Six detached trade-network metric calculators."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.models import MetricAvailability
from analysis.trade_networks_analysis import (
    empty_trade_networks_analysis,
    harvest_trade_networks_analysis,
)
from analysis.trade_networks_contract import TradeCoverage
from analysis.trade_networks_metrics import (
    _reject_forbidden_fields,
    assemble_trade_network_metrics,
    compute_cross_society_trade_flows,
    compute_trade_corridor_structure,
    compute_trade_dependence,
    compute_trade_flow_composition,
    compute_trade_location_centrality,
    compute_trade_network_lineage,
)
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId

SOC_A = "msoc-aaaaaaaaaaaaaaaa"
SOC_B = "msoc-bbbbbbbbbbbbbbbb"


def _event(token: str, details: object, *, tick: int = 0, origin: str = "loc-a"):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(origin_location_id=EntityId(origin)),
    )


def _pair(
    ordinal: int, *, tick: int, origin: str = "loc-a", destination: str = "loc-b"
):
    return (
        _event(
            f"evt-c-{ordinal}",
            ItemCrafted(
                recipe_id=RecipeId("cook_food"),
                created_item_id=EntityId(f"item-{ordinal}"),
                resulting_holder_id=EntityId("body-a"),
                duration_ticks=1,
            ),
            tick=tick,
            origin=origin,
        ),
        _event(
            f"evt-g-{ordinal}",
            Given(
                recipient_id=EntityId("body-b"),
                item_id=EntityId(f"item-{ordinal}"),
            ),
            tick=tick + 1,
            origin=destination,
        ),
    )


def _candidates(tick: int = 0):
    return (
        InterSocietyMacroCandidate(
            society_id=SOC_A, member_ids=("body-a",), window_tick=tick
        ),
        InterSocietyMacroCandidate(
            society_id=SOC_B, member_ids=("body-b",), window_tick=tick
        ),
    )


def _analysis(*, candidates=(), trade_posts=()):
    return harvest_trade_networks_analysis(
        events=(*_pair(0, tick=0), *_pair(1, tick=32)),
        macro_candidates=candidates,
        recipe_item_kinds={"cook_food": "food"},
        trade_post_locations=trade_posts,
    )


def test_corridor_structure_values() -> None:
    document = compute_trade_corridor_structure(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["corridor_count"] == 2
    assert document.values["active_location_count"] == 2
    assert document.values["major_location_count"] == 0
    assert document.values["max_corridor_degree"] == 1
    assert document.values["max_corridor_transfers"] == 1


def test_flow_composition_counts_all_six_classes() -> None:
    document = compute_trade_flow_composition(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    values = document.values
    assert values["transfer_count"] == 2
    assert values["cross_location_count"] == 2
    assert values["food_count"] == 2
    assert values["materials_count"] == 0
    assert values["tools_count"] == 0
    assert values["records_count"] == 0
    assert values["durable_exchange_media_count"] == 0
    assert values["other_count"] == 0
    assert values["imported_count"] == values["exported_count"] == 2
    assert values["local_count"] == 0


def test_location_centrality_uses_major_threshold() -> None:
    document = compute_trade_location_centrality(
        _analysis(trade_posts=("loc-b",)), run_id="run-1", input_revision="rev-1"
    )
    values = document.values
    assert values["location_count"] == 2
    assert values["major_location_count"] == 0
    assert values["trade_post_location_count"] == 1
    assert values["major_trade_post_location_count"] == 0
    assert values["max_inflow_count"] == 1
    assert values["mean_corridor_degree_milli"] == 1_000


def test_dependence_mean_and_high_count() -> None:
    document = compute_trade_dependence(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    values = document.values
    assert values["location_count"] == 1
    assert values["mean_dependence_milli"] == 1_000
    assert values["max_dependence_milli"] == 1_000
    assert values["high_dependence_count"] == 2
    assert values["unresolved_count"] == 0


def test_cross_society_counts_and_coverage() -> None:
    document = compute_cross_society_trade_flows(
        _analysis(candidates=(*_candidates(0), *_candidates(32))),
        run_id="run-1",
        input_revision="rev-1",
    )
    values = document.values
    assert values["pair_count"] == 2
    assert values["society_count"] == 2
    assert values["transfer_count"] == 2
    assert values["food_count"] == 2
    assert values["anchor_resolved_pair_count"] == 2
    assert values["coverage"] == "complete"


def test_network_lineage_status_counts() -> None:
    document = compute_trade_network_lineage(
        _analysis(), run_id="run-1", input_revision="rev-1"
    )
    values = document.values
    assert values["network_count"] == 2
    assert values["continued_count"] == 1
    assert values["sustained_transition_count"] == 1
    assert values["sustained_network_count"] == 1
    assert values["rerouted_count"] == 0
    assert values["coverage"] == "complete"


def test_missing_analysis_is_unknown_for_all_six() -> None:
    analysis = empty_trade_networks_analysis()
    documents = assemble_trade_network_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert len(documents) == 6
    assert all(
        document.availability is MetricAvailability.UNKNOWN
        and dict(document.values) == {}
        for document in documents
    )


def test_missing_macro_candidates_only_cross_society_is_unknown() -> None:
    analysis = _analysis()
    documents = assemble_trade_network_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert documents[0].availability is MetricAvailability.PRESENT
    assert documents[4].availability is MetricAvailability.UNKNOWN


def test_missing_evidence_does_not_unknown_cross_society_when_candidates_exist() -> (
    None
):
    analysis = harvest_trade_networks_analysis(macro_candidates=_candidates(0))
    documents = assemble_trade_network_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert documents[0].availability is MetricAvailability.UNKNOWN
    assert documents[4].availability is MetricAvailability.PRESENT
    assert documents[4].values["pair_count"] == 0


def test_sustained_and_trade_post_keys() -> None:
    analysis = _analysis(trade_posts=("loc-a",))
    corridor = compute_trade_corridor_structure(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    lineage = compute_trade_network_lineage(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    assert corridor.values["corridor_coverage_ratio_milli"] == 1_000
    assert lineage.values["sustained_transition_count"] == 1
    assert lineage.values["sustained_network_count"] == 1


def test_coverage_ratios_reflect_partial_rows() -> None:
    analysis = _analysis()
    patched = replace(
        analysis,
        corridors=tuple(
            replace(row, coverage=TradeCoverage.PARTIAL) if index == 0 else row
            for index, row in enumerate(analysis.corridors)
        ),
        flows=tuple(
            replace(row, coverage=TradeCoverage.PARTIAL) if index == 0 else row
            for index, row in enumerate(analysis.flows)
        ),
        locations=tuple(
            replace(row, coverage=TradeCoverage.PARTIAL) if index == 0 else row
            for index, row in enumerate(analysis.locations)
        ),
    )
    corridor = compute_trade_corridor_structure(
        patched, run_id="run-1", input_revision="rev-1"
    )
    flow = compute_trade_flow_composition(
        patched, run_id="run-1", input_revision="rev-1"
    )
    location = compute_trade_location_centrality(
        patched, run_id="run-1", input_revision="rev-1"
    )
    assert corridor.values["corridor_coverage_ratio_milli"] == 500
    assert corridor.coverage.observed == 1
    assert corridor.coverage.expected == 2
    assert flow.coverage.observed == 1
    assert flow.coverage.expected == 2
    assert location.coverage.observed < location.coverage.expected


def test_forbidden_score_key_is_rejected() -> None:
    with pytest.raises(ValueError):
        _reject_forbidden_fields({"score": 1})
    with pytest.raises(ValueError):
        _reject_forbidden_fields({"ranking": 1})


@given(
    tick=st.integers(min_value=0, max_value=96),
)
def test_metric_values_are_non_negative_exact_ints(tick) -> None:
    analysis = harvest_trade_networks_analysis(
        events=_pair(0, tick=tick),
        macro_candidates=_candidates(tick - (tick % 32)),
        recipe_item_kinds={"cook_food": "food"},
    )
    documents = assemble_trade_network_metrics(
        analysis, run_id="run-1", input_revision="rev-1"
    )
    for document in documents:
        for key, value in document.values.items():
            assert not isinstance(value, float), key
            if isinstance(value, int):
                assert not isinstance(value, bool)
                assert value >= 0
