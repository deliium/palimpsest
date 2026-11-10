# mypy: ignore-errors
"""Closed trade-network vocabulary, identity, and media classification."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_contract import (
    NONE_TOKEN,
    TRADE_CORRIDOR_PREFIX,
    TRADE_FORBIDDEN_KEYS,
    TRADE_LAYER_FORBIDDEN_PREFIXES,
    TRADE_NETWORK_PREFIX,
    TRADE_NETWORKS_ANALYSIS_POLICY_VERSION,
    TRADE_PAIR_PREFIX,
    TradeCoverage,
    TradeFlowClass,
    TradeLayer,
    TradeNetworksError,
    analysis_trade_candidate_id,
    canonical_trade_pair,
)
from analysis.trade_networks_policy import (
    default_trade_networks_analysis_policy,
    flow_class_for_item,
    is_media_candidate,
    window_bounds,
    window_index_for_tick,
)
from world.values import ItemKind


def test_contract_is_closed_and_forbidden_keys_present() -> None:
    assert TRADE_NETWORKS_ANALYSIS_POLICY_VERSION == "trade-networks.v1"
    assert {item.value for item in TradeFlowClass} == {
        "food",
        "materials",
        "tools",
        "records",
        "durable_exchange_media",
        "other",
    }
    assert {item.value for item in TradeCoverage} == {
        "complete",
        "partial",
        "missing",
    }
    assert {item.value for item in TradeLayer} == {
        "objective_transfer",
        "analytical_corridor",
        "analytical_network",
        "comparison_view",
    }
    assert NONE_TOKEN == "none"
    assert {
        "price",
        "money",
        "currency",
        "central_planner",
        "route_plan",
        "allocation",
        "quota",
        "score",
        "ranking",
    }.issubset(TRADE_FORBIDDEN_KEYS)
    assert (
        TRADE_CORRIDOR_PREFIX
        in TRADE_LAYER_FORBIDDEN_PREFIXES[TradeLayer.OBJECTIVE_TRANSFER]
    )
    assert (
        TRADE_NETWORK_PREFIX
        in TRADE_LAYER_FORBIDDEN_PREFIXES[TradeLayer.ANALYTICAL_CORRIDOR]
    )
    assert (
        TRADE_PAIR_PREFIX
        in TRADE_LAYER_FORBIDDEN_PREFIXES[TradeLayer.ANALYTICAL_NETWORK]
    )
    assert "event_token" in TRADE_LAYER_FORBIDDEN_PREFIXES[TradeLayer.COMPARISON_VIEW]


def test_candidate_ids_are_deterministic_and_prefixed() -> None:
    corridor = analysis_trade_candidate_id("corridor", "loc-a->loc-b")
    network = analysis_trade_candidate_id("network", "corridor-token")
    pair = analysis_trade_candidate_id("pair", "society-a|society-b")
    assert corridor.startswith(TRADE_CORRIDOR_PREFIX)
    assert network.startswith(TRADE_NETWORK_PREFIX)
    assert pair.startswith(TRADE_PAIR_PREFIX)
    assert corridor == analysis_trade_candidate_id("CORRIDOR", "loc-a->loc-b")
    assert len(corridor) == len(TRADE_CORRIDOR_PREFIX) + 16
    with pytest.raises(TradeNetworksError):
        analysis_trade_candidate_id("corridor", "")


def test_canonical_pair_rejects_equal_and_empty() -> None:
    assert canonical_trade_pair("b", "a") == ("a", "b")
    assert canonical_trade_pair("a", "b") == ("a", "b")
    with pytest.raises(TradeNetworksError):
        canonical_trade_pair("a", "a")
    with pytest.raises(TradeNetworksError):
        canonical_trade_pair("", "a")


def test_window_bounds_and_out_of_range() -> None:
    policy = default_trade_networks_analysis_policy()
    assert window_index_for_tick(0) == 0
    assert window_index_for_tick(31) == 0
    assert window_index_for_tick(32) == 1
    assert window_index_for_tick(63) == 1
    assert window_bounds(0, policy) == (0, 32)
    assert window_bounds(511, policy) == (511 * 32, 512 * 32)
    with pytest.raises(TradeNetworksError):
        window_index_for_tick(-1)
    with pytest.raises(TradeNetworksError):
        window_index_for_tick(True)
    with pytest.raises(TradeNetworksError):
        window_bounds(512, policy)
    with pytest.raises(TradeNetworksError):
        window_bounds(-1, policy)


def test_item_kind_and_media_classification() -> None:
    assert flow_class_for_item(ItemKind.FOOD) is TradeFlowClass.FOOD
    assert flow_class_for_item(ItemKind.WATER) is TradeFlowClass.FOOD
    assert flow_class_for_item(ItemKind.MATERIAL) is TradeFlowClass.MATERIALS
    assert flow_class_for_item(ItemKind.TOOL) is TradeFlowClass.TOOLS
    assert flow_class_for_item(ItemKind.MEDICAL) is TradeFlowClass.OTHER
    assert flow_class_for_item(ItemKind.GENERIC) is TradeFlowClass.OTHER
    assert flow_class_for_item("unknown") is TradeFlowClass.OTHER
    assert not is_media_candidate(ItemKind.GENERIC, 1, 2, False)
    assert not is_media_candidate(ItemKind.GENERIC, 2, 1, False)
    assert not is_media_candidate(ItemKind.GENERIC, 2, 2, True)
    assert is_media_candidate(ItemKind.GENERIC, 2, 2, False)
    assert not is_media_candidate(ItemKind.MATERIAL, 4, 4, False)


def test_media_requires_distinct_parties() -> None:
    assert not is_media_candidate(ItemKind.GENERIC, 6, 1, False)
    assert is_media_candidate(ItemKind.GENERIC, 2, 2, False)


safe_text = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=64,
)


@given(kind=st.sampled_from(["corridor", "network", "pair"]), material=safe_text)
def test_candidate_id_is_stable_for_arbitrary_safe_material(
    kind: str, material: str
) -> None:
    first = analysis_trade_candidate_id(kind, material)
    second = analysis_trade_candidate_id(kind, material)
    assert first == second
    assert first.startswith("trd-")
