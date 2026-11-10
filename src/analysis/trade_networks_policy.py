"""Locked detached-analysis policy for trade networks.

The window, cap, media, major-location, lineage, and dependence thresholds are
fixed. Analysis never reads runner configuration, world state, wall-clock state,
or random state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.trade_networks_contract import (
    TradeFlowClass,
    TradeNetworksError,
)
from world.values import ItemKind

__all__ = [
    "DEFAULT_TRADE_WINDOW_TICKS",
    "TradeNetworksAnalysisPolicy",
    "default_trade_networks_analysis_policy",
    "flow_class_for_item",
    "is_media_candidate",
    "window_bounds",
    "window_index_for_tick",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.policy")

DEFAULT_TRADE_WINDOW_TICKS: Final[int] = 32

_MEDIA_MIN_TRANSFERS: Final[int] = 2
_MEDIA_MIN_DISTINCT_PARTIES: Final[int] = 2

_INT_RANGES: Final[dict[str, tuple[int, int]]] = {
    "window_ticks": (4, 256),
    "max_windows": (1, 2048),
    "max_transfer_rows": (1, 1_000_000),
    "max_corridors": (1, 16_384),
    "max_networks": (1, 4_096),
    "max_locations": (1, 16_384),
    "max_cross_society_pairs": (1, 8_192),
    "max_lineage_edges": (1, 65_536),
    "media_min_transfers": (2, 16),
    "media_min_distinct_parties": (2, 64),
    "major_min_corridors": (1, 16),
    "major_min_transfers": (1, 1_024),
    "lineage_overlap_milli": (1, 1_000),
    "high_dependence_milli": (1, 1_000),
}


@dataclass(frozen=True, slots=True)
class TradeNetworksAnalysisPolicy:
    """Validated detached trade-network analysis policy."""

    window_ticks: int = DEFAULT_TRADE_WINDOW_TICKS
    max_windows: int = 512
    max_transfer_rows: int = 200_000
    max_corridors: int = 4_096
    max_networks: int = 1_024
    max_locations: int = 4_096
    max_cross_society_pairs: int = 2_048
    max_lineage_edges: int = 16_384
    media_min_transfers: int = 2
    media_min_distinct_parties: int = 2
    major_min_corridors: int = 2
    major_min_transfers: int = 3
    lineage_overlap_milli: int = 500
    high_dependence_milli: int = 500

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in _INT_RANGES.items():
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int:
                raise ValueError(f"{name}: trade_networks_invalid_policy")
            if value < minimum or value > maximum:
                raise ValueError(f"{name}: trade_networks_invalid_policy")
        _LOG.debug(
            "trade_networks_policy_resolved window_ticks=%s max_corridors=%s",
            self.window_ticks,
            self.max_corridors,
        )


def default_trade_networks_analysis_policy() -> TradeNetworksAnalysisPolicy:
    """Return the one locked analysis policy value."""
    return TradeNetworksAnalysisPolicy()


def window_index_for_tick(
    tick: int, policy: TradeNetworksAnalysisPolicy | None = None
) -> int:
    """Return the locked policy window index for ``tick``."""
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise TradeNetworksError("trade_networks_window_out_of_range")
    window_ticks = (
        DEFAULT_TRADE_WINDOW_TICKS if policy is None else policy.window_ticks
    )
    index = tick // window_ticks
    if policy is not None and index >= policy.max_windows:
        raise TradeNetworksError("trade_networks_window_out_of_range")
    return index


def window_bounds(
    window_index: int, policy: TradeNetworksAnalysisPolicy
) -> tuple[int, int]:
    """Return the inclusive-exclusive tick bounds for one policy window."""
    if (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
        or window_index >= policy.max_windows
    ):
        raise TradeNetworksError("trade_networks_window_out_of_range")
    start = window_index * policy.window_ticks
    return start, start + policy.window_ticks


def _item_kind_value(kind: ItemKind | str) -> str:
    if isinstance(kind, ItemKind):
        return kind.value
    if isinstance(kind, str):
        return kind
    return ""


def flow_class_for_item(kind: ItemKind | str) -> TradeFlowClass:
    """Map one closed item kind to its fixed flow class."""
    value = _item_kind_value(kind)
    if value in {ItemKind.FOOD.value, ItemKind.WATER.value}:
        return TradeFlowClass.FOOD
    if value == ItemKind.MATERIAL.value:
        return TradeFlowClass.MATERIALS
    if value == ItemKind.TOOL.value:
        return TradeFlowClass.TOOLS
    return TradeFlowClass.OTHER


def is_media_candidate(
    kind: ItemKind | str,
    transfer_count: int,
    distinct_parties: int,
    consumed: bool,
) -> bool:
    """Generic item with repeated transfers across distinct parties, unconsumed."""
    if _item_kind_value(kind) != ItemKind.GENERIC.value:
        return False
    if consumed is True:
        return False
    return (
        transfer_count >= _MEDIA_MIN_TRANSFERS
        and distinct_parties >= _MEDIA_MIN_DISTINCT_PARTIES
    )


def flow_class_for_media_candidate(
    kind: ItemKind | str,
    transfer_count: int,
    distinct_parties: int,
    consumed: bool,
) -> TradeFlowClass:
    """Return durable-exchange media for eligible generic items, else OTHER."""
    if is_media_candidate(kind, transfer_count, distinct_parties, consumed):
        return TradeFlowClass.DURABLE_EXCHANGE_MEDIA
    return TradeFlowClass.OTHER


__all__.append("flow_class_for_media_candidate")
