"""Deterministic trade identities and forward-only network lineage.

Corridor and network tokens are content-addressed over observed structure only.
Lineage never rewrites previous rows: previous windows are inputs, current rows
are outputs, and gaps are represented by explicit empty windows.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.trade_networks_contract import (
    NONE_TOKEN,
    TradeNetworksError,
    analysis_trade_candidate_id,
    canonical_trade_pair,
)
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
    window_bounds,
)
from analysis.trade_networks_rows import TradeLineageRow, TradeNetworkRow

__all__ = [
    "group_networks_by_window",
    "link_trade_network_lineage",
    "mint_corridor_token",
    "mint_cross_society_pair_token",
    "mint_network_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.identity")


def mint_corridor_token(from_location: str, to_location: str) -> str:
    """Stable directed corridor token over the exact ordered location pair."""
    if (
        not isinstance(from_location, str)
        or not from_location
        or not isinstance(to_location, str)
        or not to_location
    ):
        raise TradeNetworksError("trade_networks_invalid_identity")
    return analysis_trade_candidate_id("corridor", f"{from_location}\x1f{to_location}")


def mint_network_token(corridor_tokens: Sequence[str]) -> str:
    """Stable network token over sorted, de-duplicated corridor tokens."""
    tokens = sorted(set(corridor_tokens))
    if not tokens or any(not isinstance(token, str) or not token for token in tokens):
        raise TradeNetworksError("trade_networks_invalid_identity")
    return analysis_trade_candidate_id("network", "\x1e".join(tokens))


def mint_cross_society_pair_token(society_a: str, society_b: str) -> str:
    """Stable token over a canonically ordered pair of existing societies."""
    left, right = canonical_trade_pair(society_a, society_b)
    return analysis_trade_candidate_id("pair", f"{left}\x1e{right}")


def group_networks_by_window(
    networks: Sequence[TradeNetworkRow],
    *,
    first_window: int = 0,
    last_window: int | None = None,
) -> tuple[tuple[int, tuple[TradeNetworkRow, ...]], ...]:
    """Group networks by window, optionally materializing empty gap windows."""
    grouped: dict[int, list[TradeNetworkRow]] = {}
    for row in networks:
        if type(row) is not TradeNetworkRow:
            raise TradeNetworksError("trade_networks_invalid_lineage")
        grouped.setdefault(row.window_index, []).append(row)
    if last_window is None:
        return tuple(
            (window, tuple(sorted(rows, key=lambda item: item.network_token)))
            for window, rows in sorted(grouped.items())
        )
    if (
        isinstance(first_window, bool)
        or type(first_window) is not int
        or first_window < 0
        or isinstance(last_window, bool)
        or type(last_window) is not int
        or last_window < first_window
    ):
        raise TradeNetworksError("trade_networks_invalid_lineage")
    return tuple(
        (
            window,
            tuple(sorted(grouped.get(window, ()), key=lambda item: item.network_token)),
        )
        for window in range(first_window, last_window + 1)
    )


def _corridor_set(row: TradeNetworkRow) -> frozenset[str]:
    return frozenset(row.corridor_tokens)


def _overlap_milli(left: frozenset[str], right: frozenset[str]) -> int:
    if not left and not right:
        return 1_000
    if not left or not right:
        return 0
    intersection = len(left & right)
    return intersection * 1_000 // min(len(left), len(right))


def _require_single_window(
    rows: Sequence[TradeNetworkRow],
) -> int | None:
    windows: set[int] = set()
    for row in rows:
        if type(row) is not TradeNetworkRow:
            raise TradeNetworksError("trade_networks_invalid_lineage")
        windows.add(row.window_index)
    if len(windows) > 1:
        raise TradeNetworksError("trade_networks_invalid_lineage")
    if not windows:
        return None
    return next(iter(windows))


def link_trade_network_lineage(
    previous: Sequence[TradeNetworkRow],
    current: Sequence[TradeNetworkRow],
    policy: TradeNetworksAnalysisPolicy,
) -> tuple[TradeLineageRow, ...]:
    """Link consecutive policy windows forward-only by corridor-set overlap."""
    previous_window = _require_single_window(previous)
    current_window = _require_single_window(current)
    if (
        previous_window is not None
        and current_window is not None
        and previous_window > current_window
    ):
        raise TradeNetworksError("trade_networks_invalid_lineage")

    unique_previous: dict[str, TradeNetworkRow] = {}
    for row in previous:
        if row.network_token in unique_previous:
            raise TradeNetworksError("trade_networks_invalid_lineage")
        unique_previous[row.network_token] = row
    unique_current: dict[str, TradeNetworkRow] = {}
    for row in current:
        if row.network_token in unique_current:
            raise TradeNetworksError("trade_networks_invalid_lineage")
        unique_current[row.network_token] = row

    links: list[tuple[str, str, int]] = []
    for previous_token, previous_row in unique_previous.items():
        previous_corridors = _corridor_set(previous_row)
        for current_token, current_row in unique_current.items():
            overlap = _overlap_milli(previous_corridors, _corridor_set(current_row))
            if overlap >= policy.lineage_overlap_milli:
                links.append((previous_token, current_token, overlap))

    successor_count: dict[str, int] = {}
    predecessor_count: dict[str, int] = {}
    for previous_token, current_token, _ in links:
        successor_count[previous_token] = successor_count.get(previous_token, 0) + 1
        predecessor_count[current_token] = predecessor_count.get(current_token, 0) + 1

    def _edge(
        previous_token: str,
        network_token: str,
        relation: str,
        *,
        start_window: int,
        end_window: int,
    ) -> TradeLineageRow:
        start_tick, _ = window_bounds(start_window, policy)
        _, end_tick = window_bounds(end_window, policy)
        return TradeLineageRow(
            network_token=network_token,
            previous_token=previous_token,
            relation=relation,
            first_tick=start_tick,
            last_tick=end_tick - 1,
            rerouted=relation == "transformed",
            sustained=relation in {"continued", "transformed"},
        )

    edges: list[TradeLineageRow] = []
    linked_previous: set[str] = set()
    linked_current: set[str] = set()
    for previous_token, current_token, _ in links:
        linked_previous.add(previous_token)
        linked_current.add(current_token)
        previous_row = unique_previous[previous_token]
        current_row = unique_current[current_token]
        if successor_count[previous_token] >= 2:
            relation = "split"
        elif predecessor_count[current_token] >= 2:
            relation = "merge"
        elif _corridor_set(previous_row) == _corridor_set(current_row):
            relation = "continued"
        else:
            relation = "transformed"
        start_window = previous_row.window_index
        end_window = current_row.window_index
        edges.append(
            _edge(
                previous_token,
                current_token,
                relation,
                start_window=start_window,
                end_window=end_window,
            )
        )
    for previous_token, previous_row in unique_previous.items():
        if previous_token in linked_previous:
            continue
        edges.append(
            _edge(
                previous_token,
                NONE_TOKEN,
                "dissolved",
                start_window=previous_row.window_index,
                end_window=previous_row.window_index,
            )
        )
    for current_token, current_row in unique_current.items():
        if current_token in linked_current:
            continue
        edges.append(
            _edge(
                NONE_TOKEN,
                current_token,
                "emerged",
                start_window=current_row.window_index,
                end_window=current_row.window_index,
            )
        )
    edges.sort(key=lambda row: (row.first_tick, row.network_token, row.previous_token))
    _LOG.debug(
        "trade_networks_lineage previous=%s current=%s edges=%s",
        len(previous),
        len(current),
        len(edges),
    )
    return tuple(edges)
