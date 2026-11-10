"""Bounded deterministic paging for trade-network snapshot rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Final

from simulation.trade_networks_models import (
    MAX_TRADE_SNAPSHOT_WINDOWS,
    CrossSocietyTradeRecord,
    TradeCorridorRecord,
    TradeDependenceRecord,
    TradeFlowRecord,
    TradeLocationRecord,
    TradeNetworkRecord,
    TradeNetworksSnapshot,
)

__all__ = [
    "MAX_PAGE_LIMIT",
    "CrossSocietyTradeRowSelection",
    "TradeCorridorRowSelection",
    "TradeDependenceRowSelection",
    "TradeFlowRowSelection",
    "TradeLocationRowSelection",
    "TradeNetworkRowSelection",
    "page_cross_society_trades",
    "page_trade_corridors",
    "page_trade_dependence",
    "page_trade_flows",
    "page_trade_locations",
    "page_trade_networks",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.trade_networks.paging")

MAX_PAGE_LIMIT: Final[int] = 500


@dataclass(frozen=True, slots=True)
class TradeCorridorRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[TradeCorridorRecord, ...] = ()
    next_key: str | None = None


@dataclass(frozen=True, slots=True)
class TradeFlowRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[TradeFlowRecord, ...] = ()
    next_key: str | None = None


@dataclass(frozen=True, slots=True)
class TradeLocationRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[TradeLocationRecord, ...] = ()
    next_key: str | None = None


@dataclass(frozen=True, slots=True)
class TradeDependenceRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[TradeDependenceRecord, ...] = ()
    next_key: str | None = None


@dataclass(frozen=True, slots=True)
class CrossSocietyTradeRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[CrossSocietyTradeRecord, ...] = ()
    next_key: str | None = None


@dataclass(frozen=True, slots=True)
class TradeNetworkRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    window_index: int | None = None
    rows: tuple[TradeNetworkRecord, ...] = ()
    next_key: str | None = None


def _clamp(limit: object) -> int:
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("trade_networks_page_limit")
    return limit


def _window(value: object) -> int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or type(value) is not int
        or value < 0
        or value >= MAX_TRADE_SNAPSHOT_WINDOWS
    ):
        raise ValueError("trade_networks_cursor_invalid")
    return value


def _row_key(row: Any) -> str:
    window = row.window_index
    token = (
        getattr(row, "corridor_id", None)
        or getattr(row, "network_id", None)
        or getattr(row, "pair_id", None)
        or getattr(row, "location_id", None)
        or ""
    )
    flow_class = getattr(row, "flow_class", None)
    if flow_class:
        token = f"{token}|{flow_class}"
    return f"{window:020d}|{token}"


def _page(
    rows: tuple[Any, ...],
    *,
    after_key: str | None,
    limit: int,
    window_index: int | None,
    purpose: str,
) -> tuple[tuple[Any, ...], str | None]:
    filtered = [
        row for row in rows if window_index is None or row.window_index == window_index
    ]
    ordered = sorted(filtered, key=_row_key)
    if after_key is not None:
        if type(after_key) is not str or not after_key:
            raise ValueError("trade_networks_cursor_invalid")
        ordered = [row for row in ordered if _row_key(row) > after_key]
    page = tuple(ordered[:limit])
    next_key = _row_key(page[-1]) if len(ordered) > len(page) and page else None
    _LOG.debug(
        "trade_networks_page purpose=%s rows=%s window_index=%s",
        purpose,
        len(page),
        window_index,
    )
    return page, next_key


def _require_snapshot(snapshot: object) -> TradeNetworksSnapshot:
    if type(snapshot) is not TradeNetworksSnapshot:
        raise TypeError("snapshot must be TradeNetworksSnapshot")
    return snapshot


def _check_purpose(selection: object, expected: str) -> None:
    if getattr(selection, "purpose", None) != expected:
        raise ValueError("trade_networks_cursor_purpose")


def page_trade_corridors(
    snapshot: TradeNetworksSnapshot, selection: TradeCorridorRowSelection
) -> TradeCorridorRowSelection:
    rows = _require_snapshot(snapshot).corridors
    _check_purpose(selection, "corridors")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="corridors",
    )
    return TradeCorridorRowSelection(
        purpose="corridors",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )


def page_trade_flows(
    snapshot: TradeNetworksSnapshot, selection: TradeFlowRowSelection
) -> TradeFlowRowSelection:
    rows = _require_snapshot(snapshot).flows
    _check_purpose(selection, "flows")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="flows",
    )
    return TradeFlowRowSelection(
        purpose="flows",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )


def page_trade_locations(
    snapshot: TradeNetworksSnapshot, selection: TradeLocationRowSelection
) -> TradeLocationRowSelection:
    rows = _require_snapshot(snapshot).locations
    _check_purpose(selection, "locations")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="locations",
    )
    return TradeLocationRowSelection(
        purpose="locations",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )


def page_trade_dependence(
    snapshot: TradeNetworksSnapshot, selection: TradeDependenceRowSelection
) -> TradeDependenceRowSelection:
    rows = _require_snapshot(snapshot).dependence
    _check_purpose(selection, "dependence")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="dependence",
    )
    return TradeDependenceRowSelection(
        purpose="dependence",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )


def page_cross_society_trades(
    snapshot: TradeNetworksSnapshot, selection: CrossSocietyTradeRowSelection
) -> CrossSocietyTradeRowSelection:
    rows = _require_snapshot(snapshot).cross_society
    _check_purpose(selection, "cross-society")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="cross-society",
    )
    return CrossSocietyTradeRowSelection(
        purpose="cross-society",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )


def page_trade_networks(
    snapshot: TradeNetworksSnapshot, selection: TradeNetworkRowSelection
) -> TradeNetworkRowSelection:
    rows = _require_snapshot(snapshot).networks
    _check_purpose(selection, "networks")
    page, next_key = _page(
        rows,
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=_window(selection.window_index),
        purpose="networks",
    )
    return TradeNetworkRowSelection(
        purpose="networks",
        after_key=selection.after_key,
        limit=_clamp(selection.limit),
        window_index=selection.window_index,
        rows=page,
        next_key=next_key,
    )
