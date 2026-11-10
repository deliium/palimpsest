"""Bounded ``TradeNetworksAnalysis`` harvest composition.

One call turns committed events plus detached inputs into objective transfer
evidence, analytical corridors/flows/locations/networks, forward-only lineage,
and cross-society comparison rows. No metric, snapshot, API, or persistence
module is imported here.
"""

from __future__ import annotations

import itertools
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_contract import (
    TradeCoverage,
    TradeNetworksError,
)
from analysis.trade_networks_cross_society import detect_cross_society_trade
from analysis.trade_networks_detection import (
    detect_corridors,
    detect_dependence,
    detect_flows,
    detect_locations,
    detect_networks,
)
from analysis.trade_networks_events import (
    TradeEvidenceHarvest,
    TradeLocalSupplyRow,
    TradeTransferRow,
    trade_transfer_rows_from_events,
)
from analysis.trade_networks_identity import (
    group_networks_by_window,
    link_trade_network_lineage,
)
from analysis.trade_networks_layers import (
    TradeLayerView,
    assert_trade_layer_separation,
    project_trade_layers,
)
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
    default_trade_networks_analysis_policy,
    window_index_for_tick,
)
from analysis.trade_networks_rows import (
    CrossSocietyTradeRow,
    TradeCorridorRow,
    TradeDependenceRow,
    TradeFlowRow,
    TradeLineageRow,
    TradeLocationRow,
    TradeNetworkRow,
)
from world.events import WorldEvent
from world.identifiers import require_exact_nonneg_int
from world.values import ItemKind

__all__ = [
    "TradeNetworksAnalysis",
    "empty_trade_networks_analysis",
    "harvest_trade_networks_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.analysis")


@dataclass(frozen=True, slots=True)
class TradeNetworksAnalysis:
    """Stable bounded analysis object for metrics, snapshots, and tests."""

    window_tick: int
    transfers: tuple[TradeTransferRow, ...] = ()
    supplies: tuple[TradeLocalSupplyRow, ...] = ()
    corridors: tuple[TradeCorridorRow, ...] = ()
    flows: tuple[TradeFlowRow, ...] = ()
    locations: tuple[TradeLocationRow, ...] = ()
    dependence: tuple[TradeDependenceRow, ...] = ()
    networks: tuple[TradeNetworkRow, ...] = ()
    lineage: tuple[TradeLineageRow, ...] = ()
    cross_society: tuple[CrossSocietyTradeRow, ...] = ()
    layers: TradeLayerView = field(default_factory=TradeLayerView)
    evidence_coverage: TradeCoverage = TradeCoverage.MISSING
    cross_society_coverage: TradeCoverage = TradeCoverage.MISSING
    lineage_coverage: TradeCoverage = TradeCoverage.MISSING
    coverage: TradeCoverage = TradeCoverage.MISSING
    notices: tuple[str, ...] = ()
    transfer_count: int = 0
    corridor_count: int = 0
    network_count: int = 0
    cross_society_pair_count: int = 0
    trade_post_location_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "window_tick",
            require_exact_nonneg_int("window_tick", self.window_tick),
        )
        for name in (
            "transfer_count",
            "corridor_count",
            "network_count",
            "cross_society_pair_count",
            "trade_post_location_count",
        ):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if self.transfer_count != len(self.transfers):
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.corridor_count != len(self.corridors):
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.network_count != len(self.networks):
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.cross_society_pair_count != len(self.cross_society):
            raise TradeNetworksError("trade_networks_invalid_input")


def _observed_windows(
    transfers: Sequence[TradeTransferRow],
    supplies: Sequence[TradeLocalSupplyRow],
    policy: TradeNetworksAnalysisPolicy,
) -> list[int]:
    windows = {window_index_for_tick(row.tick, policy) for row in transfers}
    windows.update(window_index_for_tick(row.tick, policy) for row in supplies)
    return sorted(windows)


def _aggregate_coverage(
    evidence: TradeCoverage,
    cross_society: TradeCoverage,
    lineage: TradeCoverage,
    notices: Sequence[str],
) -> TradeCoverage:
    components = (evidence, cross_society, lineage)
    if all(item is TradeCoverage.MISSING for item in components):
        return TradeCoverage.MISSING
    if notices:
        return TradeCoverage.PARTIAL
    if any(
        item in {TradeCoverage.MISSING, TradeCoverage.PARTIAL} for item in components
    ):
        return TradeCoverage.PARTIAL
    return TradeCoverage.COMPLETE


def harvest_trade_networks_analysis(
    *,
    events: Sequence[WorldEvent] = (),
    macro_candidates: Sequence[InterSocietyMacroCandidate] = (),
    policy: TradeNetworksAnalysisPolicy | None = None,
    window_tick: int | None = None,
    recipe_item_kinds: Mapping[str, ItemKind] | None = None,
    item_kind_by_id: Mapping[str, ItemKind] | None = None,
    trade_post_locations: Sequence[str] = (),
) -> TradeNetworksAnalysis:
    """Compose the one bounded trade-network analysis object."""
    resolved = policy or default_trade_networks_analysis_policy()
    notices: set[str] = set()
    evidence: TradeEvidenceHarvest = trade_transfer_rows_from_events(
        events,
        policy=resolved,
        recipe_item_kinds=recipe_item_kinds,
        item_kind_by_id=item_kind_by_id,
    )
    notices.update(evidence.notices)

    corridors = detect_corridors(evidence.transfers, resolved, notices=notices)
    flows = detect_flows(evidence.transfers, resolved)
    locations = detect_locations(
        evidence.transfers,
        evidence.supplies,
        resolved,
        trade_post_locations,
        notices=notices,
    )
    dependence = detect_dependence(evidence.transfers, resolved)
    networks = detect_networks(corridors, resolved, notices=notices)

    windows = _observed_windows(evidence.transfers, evidence.supplies, resolved)
    lineage: list[TradeLineageRow] = []
    if windows:
        grouped = dict(
            group_networks_by_window(
                networks,
                first_window=windows[0],
                last_window=windows[-1],
            )
        )
        ordered_windows = list(range(windows[0], windows[-1] + 1))
        for left, right in itertools.pairwise(ordered_windows):
            lineage.extend(
                link_trade_network_lineage(
                    grouped.get(left, ()), grouped.get(right, ()), resolved
                )
            )
    lineage_truncated = False
    if len(lineage) > resolved.max_lineage_edges:
        lineage = lineage[: resolved.max_lineage_edges]
        lineage_truncated = True
        notices.add("trade_networks_lineage_truncated")
        _LOG.warning(
            "trade_networks_lineage_truncated retained=%s cap=%s",
            len(lineage),
            resolved.max_lineage_edges,
        )

    cross = detect_cross_society_trade(evidence.transfers, macro_candidates, resolved)
    notices.update(cross.notices)

    lineage_coverage = (
        TradeCoverage.MISSING
        if not networks
        else (TradeCoverage.PARTIAL if lineage_truncated else TradeCoverage.COMPLETE)
    )
    coverage = _aggregate_coverage(
        evidence.coverage,
        cross.coverage,
        lineage_coverage,
        sorted(notices),
    )
    if window_tick is None:
        resolved_window_tick = max((event.tick for event in events), default=0)
    else:
        resolved_window_tick = require_exact_nonneg_int("window_tick", window_tick)

    layers = project_trade_layers(
        evidence.transfers,
        corridors,
        networks,
        cross.rows,
    )
    assert_trade_layer_separation(layers)

    sorted_notices = tuple(sorted(set(notices)))
    _LOG.info(
        "trade_networks_harvest transfers=%s corridors=%s networks=%s pairs=%s "
        "evidence_coverage=%s cross_society_coverage=%s lineage_coverage=%s",
        len(evidence.transfers),
        len(corridors),
        len(networks),
        len(cross.rows),
        evidence.coverage.value,
        cross.coverage.value,
        lineage_coverage.value,
    )
    return TradeNetworksAnalysis(
        window_tick=resolved_window_tick,
        transfers=evidence.transfers,
        supplies=evidence.supplies,
        corridors=corridors,
        flows=flows,
        locations=locations,
        dependence=dependence,
        networks=networks,
        lineage=tuple(lineage),
        cross_society=cross.rows,
        layers=layers,
        evidence_coverage=evidence.coverage,
        cross_society_coverage=cross.coverage,
        lineage_coverage=lineage_coverage,
        coverage=coverage,
        notices=sorted_notices,
        transfer_count=len(evidence.transfers),
        corridor_count=len(corridors),
        network_count=len(networks),
        cross_society_pair_count=len(cross.rows),
        trade_post_location_count=sum(1 for row in locations if row.trade_post_present),
    )


def empty_trade_networks_analysis(window_tick: int = 0) -> TradeNetworksAnalysis:
    """Return the bounded empty analysis value."""
    return harvest_trade_networks_analysis(window_tick=window_tick)
