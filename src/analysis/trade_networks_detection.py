"""Deterministic corridor, flow, location, dependence, and network detection.

No graph search, shortest path, or automatic distribution is performed.
Corridors are directed observations; networks are connected components of the
undirected corridor union.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Final

from analysis.trade_networks_contract import (
    NONE_TOKEN,
    TradeCoverage,
    TradeFlowClass,
)
from analysis.trade_networks_events import (
    TradeLocalSupplyRow,
    TradeTransferRow,
)
from analysis.trade_networks_identity import (
    mint_corridor_token,
    mint_network_token,
)
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
    window_index_for_tick,
)
from analysis.trade_networks_rows import (
    TradeCorridorRow,
    TradeDependenceRow,
    TradeFlowRow,
    TradeLocationRow,
    TradeNetworkRow,
)

__all__ = [
    "detect_corridors",
    "detect_dependence",
    "detect_flows",
    "detect_locations",
    "detect_networks",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.detection")


def _window(tick: int) -> int:
    return window_index_for_tick(tick)


def _flow_totals(
    rows: Sequence[TradeTransferRow],
) -> tuple[tuple[str, int], ...]:
    counts = Counter(row.flow_class.value for row in rows)
    return tuple(sorted((key, int(value)) for key, value in counts.items()))


def _resolved(row: TradeTransferRow) -> bool:
    return (
        row.location_token != NONE_TOKEN and row.previous_location_token != NONE_TOKEN
    )


def _find(parent: dict[str, str], node: str) -> str:
    parent.setdefault(node, node)
    while parent[node] != node:
        parent[node] = parent[parent[node]]
        node = parent[node]
    return node


def _union(parent: dict[str, str], left: str, right: str) -> None:
    left_root = _find(parent, left)
    right_root = _find(parent, right)
    if left_root != right_root:
        parent[right_root] = left_root


def detect_corridors(
    transfers: Sequence[TradeTransferRow],
    policy: TradeNetworksAnalysisPolicy,
    *,
    notices: set[str] | None = None,
) -> tuple[TradeCorridorRow, ...]:
    """Aggregate observed consecutive-location transfers into directed corridors."""
    grouped: dict[tuple[int, str, str], list[TradeTransferRow]] = defaultdict(list)
    for row in transfers:
        if not _resolved(row) or row.previous_location_token == row.location_token:
            continue
        grouped[
            (_window(row.tick), row.previous_location_token, row.location_token)
        ].append(row)
    corridors: list[TradeCorridorRow] = []
    for (window_index, from_token, to_token), rows in grouped.items():
        corridors.append(
            TradeCorridorRow(
                corridor_token=mint_corridor_token(from_token, to_token),
                window_index=window_index,
                from_location_token=from_token,
                to_location_token=to_token,
                flow_counts=_flow_totals(rows),
                transfer_count=len(rows),
            )
        )
    corridors.sort(key=lambda row: (row.window_index, row.corridor_token))
    if len(corridors) > policy.max_corridors:
        corridors = corridors[: policy.max_corridors]
        if notices is not None:
            notices.add("trade_networks_corridor_truncated")
        _LOG.warning(
            "trade_networks_corridor_truncated retained=%s cap=%s",
            len(corridors),
            policy.max_corridors,
        )
        corridors = [
            TradeCorridorRow(
                corridor_token=row.corridor_token,
                window_index=row.window_index,
                from_location_token=row.from_location_token,
                to_location_token=row.to_location_token,
                flow_counts=row.flow_counts,
                transfer_count=row.transfer_count,
                coverage=TradeCoverage.PARTIAL,
            )
            for row in corridors
        ]
    return tuple(corridors)


def detect_flows(
    transfers: Sequence[TradeTransferRow],
    policy: TradeNetworksAnalysisPolicy,
) -> tuple[TradeFlowRow, ...]:
    """Aggregate per-window flow-class totals with non-disjoint role counts."""
    grouped: dict[tuple[int, str], list[TradeTransferRow]] = defaultdict(list)
    for row in transfers:
        grouped[(_window(row.tick), row.flow_class.value)].append(row)
    flows: list[TradeFlowRow] = []
    for (window_index, flow_class), rows in grouped.items():
        resolved = [row for row in rows if _resolved(row)]
        cross = sum(
            1
            for row in resolved
            if row.previous_location_token != row.location_token
        )
        local = len(resolved) - cross
        coverage = (
            TradeCoverage.PARTIAL
            if len(resolved) != len(rows)
            else TradeCoverage.COMPLETE
        )
        flows.append(
            TradeFlowRow(
                window_index=window_index,
                flow_class=TradeFlowClass(flow_class),
                transfer_count=len(resolved),
                cross_location_count=cross,
                imported_count=cross,
                exported_count=cross,
                local_count=local,
                coverage=coverage,
            )
        )
    flows.sort(key=lambda row: (row.window_index, row.flow_class.value))
    return tuple(flows)


def detect_locations(
    transfers: Sequence[TradeTransferRow],
    supplies: Sequence[TradeLocalSupplyRow],
    policy: TradeNetworksAnalysisPolicy,
    trade_post_locations: Sequence[str] = (),
    *,
    notices: set[str] | None = None,
) -> tuple[TradeLocationRow, ...]:
    """Summarize exchange activity, degree, and major-location status."""
    trade_posts = frozenset(trade_post_locations)
    corridors, _ = _corridors_without_notices(transfers, policy)
    degree: Counter[tuple[int, str]] = Counter()
    for corridor in corridors:
        degree[(corridor.window_index, corridor.from_location_token)] += 1
        degree[(corridor.window_index, corridor.to_location_token)] += 1

    activity: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"inflow": 0, "outflow": 0, "local": 0}
    )
    flow_counts: dict[tuple[int, str], Counter[str]] = defaultdict(Counter)
    for row in transfers:
        if not _resolved(row):
            continue
        window_index = _window(row.tick)
        current = row.location_token
        previous = row.previous_location_token
        if current == previous:
            activity[(window_index, current)]["local"] += 1
        else:
            activity[(window_index, current)]["inflow"] += 1
            activity[(window_index, previous)]["outflow"] += 1
            flow_counts[(window_index, previous)][row.flow_class.value] += 1
        flow_counts[(window_index, current)][row.flow_class.value] += 1
    for supply in supplies:
        if supply.location_token == NONE_TOKEN:
            continue
        window_index = _window(supply.tick)
        activity[(window_index, supply.location_token)]
        flow_counts[(window_index, supply.location_token)][
            supply.flow_class.value
        ] += 0

    locations: list[TradeLocationRow] = []
    for (window_index, location_token), counts in activity.items():
        total = counts["inflow"] + counts["outflow"] + counts["local"]
        corridor_degree = degree.get((window_index, location_token), 0)
        locations.append(
            TradeLocationRow(
                location_token=location_token,
                window_index=window_index,
                inflow_count=counts["inflow"],
                outflow_count=counts["outflow"],
                local_count=counts["local"],
                corridor_degree=corridor_degree,
                is_major=(
                    corridor_degree >= policy.major_min_corridors
                    and total >= policy.major_min_transfers
                ),
                trade_post_present=location_token in trade_posts,
                flow_counts=tuple(
                    sorted(
                        (key, int(value))
                        for key, value in flow_counts[
                            (window_index, location_token)
                        ].items()
                    )
                ),
            )
        )
    locations.sort(key=lambda row: (row.window_index, row.location_token))
    if len(locations) > policy.max_locations:
        locations = locations[: policy.max_locations]
        if notices is not None:
            notices.add("trade_networks_location_truncated")
        _LOG.warning(
            "trade_networks_location_truncated retained=%s cap=%s",
            len(locations),
            policy.max_locations,
        )
        locations = [
            TradeLocationRow(
                location_token=row.location_token,
                window_index=row.window_index,
                inflow_count=row.inflow_count,
                outflow_count=row.outflow_count,
                local_count=row.local_count,
                corridor_degree=row.corridor_degree,
                is_major=row.is_major,
                trade_post_present=row.trade_post_present,
                flow_counts=row.flow_counts,
                coverage=TradeCoverage.PARTIAL,
            )
            for row in locations
        ]
    return tuple(locations)


def detect_dependence(
    transfers: Sequence[TradeTransferRow],
    policy: TradeNetworksAnalysisPolicy,
) -> tuple[TradeDependenceRow, ...]:
    """Compute observed exchange dependence per location/window/class."""
    counts: dict[tuple[int, str, str], dict[str, int]] = defaultdict(
        lambda: {"imported": 0, "local": 0}
    )
    for row in transfers:
        if not _resolved(row):
            continue
        window_index = _window(row.tick)
        key = (window_index, row.location_token, row.flow_class.value)
        if row.previous_location_token != row.location_token:
            counts[key]["imported"] += 1
        elif row.origin_location_token == row.location_token:
            counts[key]["local"] += 1
    rows: list[TradeDependenceRow] = []
    for (window_index, location_token, flow_class), values in counts.items():
        imported = values["imported"]
        local = values["local"]
        denominator = imported + local
        if denominator == 0:
            dependence: int | None = None
            coverage = TradeCoverage.PARTIAL
        else:
            dependence = imported * 1_000 // denominator
            coverage = TradeCoverage.COMPLETE
        rows.append(
            TradeDependenceRow(
                location_token=location_token,
                window_index=window_index,
                flow_class=TradeFlowClass(flow_class),
                imported_count=imported,
                locally_originated_count=local,
                dependence_milli=dependence,
                high_dependence=(
                    dependence is not None
                    and dependence >= policy.high_dependence_milli
                ),
                coverage=coverage,
            )
        )
    rows.sort(
        key=lambda row: (
            row.window_index,
            row.location_token,
            row.flow_class.value,
        )
    )
    return tuple(rows)


def _corridors_without_notices(
    transfers: Sequence[TradeTransferRow],
    policy: TradeNetworksAnalysisPolicy,
) -> tuple[tuple[TradeCorridorRow, ...], set[str]]:
    return detect_corridors(transfers, policy), set()


def detect_networks(
    corridors: Sequence[TradeCorridorRow],
    policy: TradeNetworksAnalysisPolicy,
    *,
    notices: set[str] | None = None,
) -> tuple[TradeNetworkRow, ...]:
    """Build connected components of the undirected corridor union per window."""
    by_window: dict[int, list[TradeCorridorRow]] = defaultdict(list)
    for row in corridors:
        by_window[row.window_index].append(row)
    networks: list[TradeNetworkRow] = []
    for window_index, rows in by_window.items():
        parent: dict[str, str] = {}
        for row in rows:
            _union(parent, row.from_location_token, row.to_location_token)
        components: dict[str, list[TradeCorridorRow]] = defaultdict(list)
        for row in rows:
            components[_find(parent, row.from_location_token)].append(row)
        for members in components.values():
            tokens = sorted({row.corridor_token for row in members})
            locations = sorted(
                {row.from_location_token for row in members}
                | {row.to_location_token for row in members}
            )
            totals: Counter[str] = Counter()
            for row in members:
                for key, count in row.flow_counts:
                    totals[key] += count
            networks.append(
                TradeNetworkRow(
                    network_token=mint_network_token(tokens),
                    window_index=window_index,
                    corridor_tokens=tuple(tokens),
                    location_tokens=tuple(locations),
                    flow_counts=tuple(sorted(totals.items())),
                    transfer_count=sum(row.transfer_count for row in members),
                )
            )
    networks.sort(key=lambda row: (row.window_index, row.network_token))
    if len(networks) > policy.max_networks:
        networks = networks[: policy.max_networks]
        if notices is not None:
            notices.add("trade_networks_network_truncated")
        _LOG.warning(
            "trade_networks_network_truncated retained=%s cap=%s",
            len(networks),
            policy.max_networks,
        )
        networks = [
            TradeNetworkRow(
                network_token=row.network_token,
                window_index=row.window_index,
                corridor_tokens=row.corridor_tokens,
                location_tokens=row.location_tokens,
                flow_counts=row.flow_counts,
                transfer_count=row.transfer_count,
                coverage=TradeCoverage.PARTIAL,
            )
            for row in networks
        ]
    _LOG.debug(
        "trade_networks_detected corridors=%s networks=%s locations=unknown "
        "coverage=%s",
        len(corridors),
        len(networks),
        "complete" if not notices else "partial",
    )
    return tuple(networks)
