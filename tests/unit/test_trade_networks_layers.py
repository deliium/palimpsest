# mypy: ignore-errors
"""Strict separation of objective and analytical trade layers."""

from __future__ import annotations

import pytest

from analysis.trade_networks_contract import TradeFlowClass, TradeNetworksError
from analysis.trade_networks_events import TradeTransferRow
from analysis.trade_networks_layers import (
    assert_trade_layer_separation,
    project_trade_layers,
)
from analysis.trade_networks_rows import (
    CrossSocietyTradeRow,
    TradeCorridorRow,
    TradeNetworkRow,
)


def _transfer(*, entity: str = "item-1", event: str = "evt-1"):
    return TradeTransferRow(
        entity_kind="item",
        entity_token=entity,
        flow_class=TradeFlowClass.FOOD,
        tick=0,
        event_token=event,
        location_token="loc-a",
        previous_location_token="loc-b",
        origin_location_token="loc-b",
        actor_token="body-a",
        counterparty_token="body-b",
        direction="give",
        source_kind="gift",
        consumed=False,
    )


def _corridor(token: str = "trd-cor-0000000000000000"):
    return TradeCorridorRow(
        corridor_token=token,
        window_index=0,
        from_location_token="loc-b",
        to_location_token="loc-a",
        flow_counts=(("food", 1),),
        transfer_count=1,
    )


def _network():
    return TradeNetworkRow(
        network_token="trd-net-0000000000000000",
        window_index=0,
        corridor_tokens=("trd-cor-0000000000000000",),
        location_tokens=("loc-a", "loc-b"),
        flow_counts=(("food", 1),),
        transfer_count=1,
    )


def _cross(society_a: str = "msoc-aaaaaaaaaaaaaaaa"):
    return CrossSocietyTradeRow(
        pair_token="trd-pair-0000000000000000",
        window_index=0,
        society_a=society_a,
        society_b="msoc-bbbbbbbbbbbbbbbb",
        society_a_location_id="loc-a",
        society_b_location_id="loc-b",
        overlap_member_count=0,
        flow_counts=(("food", 1),),
        transfer_count=1,
        society_a_to_b_count=1,
        society_b_to_a_count=0,
    )


def test_layers_keep_objective_and_analytical_rows_separate() -> None:
    view = project_trade_layers(
        (_transfer(),), (_corridor(),), (_network(),), (_cross(),)
    )
    assert view.objective_transfers and view.analytical_corridors
    assert view.analytical_networks and view.comparison_view
    assert_trade_layer_separation(view)


def test_network_token_leak_in_objective_layer_is_rejected() -> None:
    view = project_trade_layers(
        (_transfer(entity="trd-net-0000000000000000"),), (), (), ()
    )
    with pytest.raises(TradeNetworksError, match="trade_networks_layer_leak"):
        assert_trade_layer_separation(view)


def test_pair_token_leak_in_corridor_layer_is_rejected() -> None:
    view = project_trade_layers((), (_corridor("trd-pair-0000000000000000"),), (), ())
    with pytest.raises(TradeNetworksError, match="trade_networks_layer_leak"):
        assert_trade_layer_separation(view)


def test_raw_event_token_leak_in_network_layer_is_rejected() -> None:
    network = TradeNetworkRow(
        network_token="trd-net-0000000000000000",
        window_index=0,
        corridor_tokens=("trd-cor-0000000000000000",),
        location_tokens=("evt-1", "loc-b"),
        flow_counts=(("food", 1),),
        transfer_count=1,
    )
    view = project_trade_layers((_transfer(),), (), (network,), ())
    with pytest.raises(TradeNetworksError, match="trade_networks_layer_leak"):
        assert_trade_layer_separation(view)


def test_item_token_leak_in_comparison_layer_is_rejected() -> None:
    view = project_trade_layers(
        (_transfer(entity="item-1"),), (), (), (_cross("item-1"),)
    )
    with pytest.raises(TradeNetworksError, match="trade_networks_layer_leak"):
        assert_trade_layer_separation(view)
