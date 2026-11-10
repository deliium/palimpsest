"""Strict layer separation for trade evidence and analytical views."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.trade_networks_contract import (
    TRADE_CORRIDOR_PREFIX,
    TRADE_NETWORK_PREFIX,
    TRADE_PAIR_PREFIX,
    TradeNetworksError,
)
from analysis.trade_networks_events import TradeTransferRow
from analysis.trade_networks_rows import (
    CrossSocietyTradeRow,
    TradeCorridorRow,
    TradeNetworkRow,
)

__all__ = [
    "TradeLayerView",
    "assert_trade_layer_separation",
    "project_trade_layers",
]


@dataclass(frozen=True, slots=True)
class TradeLayerView:
    """Separated objective evidence and analytical trade representations."""

    objective_transfers: tuple[TradeTransferRow, ...] = ()
    analytical_corridors: tuple[TradeCorridorRow, ...] = ()
    analytical_networks: tuple[TradeNetworkRow, ...] = ()
    comparison_view: tuple[CrossSocietyTradeRow, ...] = ()


def project_trade_layers(
    transfers: tuple[TradeTransferRow, ...],
    corridors: tuple[TradeCorridorRow, ...],
    networks: tuple[TradeNetworkRow, ...],
    cross_society: tuple[CrossSocietyTradeRow, ...],
) -> TradeLayerView:
    """Project the four layers without merging their identifiers."""
    return TradeLayerView(
        objective_transfers=tuple(transfers),
        analytical_corridors=tuple(corridors),
        analytical_networks=tuple(networks),
        comparison_view=tuple(cross_society),
    )


def _strings(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list, set, frozenset)):
        collected: list[str] = []
        for item in value:
            collected.extend(_strings(item))
        return tuple(collected)
    if hasattr(value, "__dataclass_fields__"):
        collected = []
        for name in value.__dataclass_fields__:
            collected.extend(_strings(getattr(value, name)))
        return tuple(collected)
    return ()


def _contains_prefix(values: tuple[str, ...], prefix: str) -> bool:
    return any(value.startswith(prefix) for value in values)


def assert_trade_layer_separation(view: TradeLayerView) -> None:
    """Fail closed when one layer carries another layer's identity family."""
    if type(view) is not TradeLayerView:
        raise TradeNetworksError("trade_networks_invalid_input")
    objective = _strings(view.objective_transfers)
    corridor = _strings(view.analytical_corridors)
    network = _strings(view.analytical_networks)
    comparison = _strings(view.comparison_view)

    for prefix in (TRADE_CORRIDOR_PREFIX, TRADE_NETWORK_PREFIX, TRADE_PAIR_PREFIX):
        if _contains_prefix(objective, prefix):
            raise TradeNetworksError("trade_networks_layer_leak")
    for prefix in (TRADE_NETWORK_PREFIX, TRADE_PAIR_PREFIX):
        if _contains_prefix(corridor, prefix):
            raise TradeNetworksError("trade_networks_layer_leak")
    if _contains_prefix(network, TRADE_PAIR_PREFIX):
        raise TradeNetworksError("trade_networks_layer_leak")
    event_tokens = {row.event_token for row in view.objective_transfers}
    if event_tokens.intersection(network):
        raise TradeNetworksError("trade_networks_layer_leak")
    entity_tokens = {row.entity_token for row in view.objective_transfers}
    if entity_tokens.intersection(comparison):
        raise TradeNetworksError("trade_networks_layer_leak")
