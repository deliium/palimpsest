"""Normalized detached trade-network rows.

Every row is frozen, bounded, and content-addressed. Rows are analytical views
over committed evidence; they are never objective world state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from analysis.trade_networks_contract import (
    TradeCoverage,
    TradeFlowClass,
    TradeNetworksError,
)
from analysis.trade_networks_events import (
    TradeLocalSupplyRow,
    TradeTransferRow,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "CrossSocietyTradeRow",
    "TradeCorridorRow",
    "TradeDependenceRow",
    "TradeFlowRow",
    "TradeLineageRow",
    "TradeLocationRow",
    "TradeNetworkRow",
    "TradeNetworksHarvestRows",
]

_FLOW_VALUES: Final[frozenset[str]] = frozenset(item.value for item in TradeFlowClass)
_COVERAGE_VALUES: Final[frozenset[str]] = frozenset(
    item.value for item in TradeCoverage
)
_LINEAGE_RELATIONS: Final[frozenset[str]] = frozenset(
    {"emerged", "continued", "transformed", "split", "merge", "dissolved"}
)


def _require_token(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TradeNetworksError("trade_networks_invalid_input")
    return require_stable_id(name, value)


def _require_tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise TradeNetworksError("trade_networks_invalid_input") from exc


def _require_flow_counts(
    value: tuple[tuple[str, int], ...],
) -> tuple[tuple[str, int], ...]:
    seen: set[str] = set()
    normalized: list[tuple[str, int]] = []
    for key, count in value:
        if key not in _FLOW_VALUES or key in seen:
            raise TradeNetworksError("trade_networks_invalid_input")
        seen.add(key)
        normalized.append((key, _require_tick("flow_count", count)))
    return tuple(sorted(normalized))


def _require_coverage(value: object) -> TradeCoverage:
    if not isinstance(value, TradeCoverage) or value.value not in _COVERAGE_VALUES:
        raise TradeNetworksError("trade_networks_invalid_input")
    return value


@dataclass(frozen=True, slots=True)
class TradeCorridorRow:
    """One directed observed edge between consecutive entity locations."""

    corridor_token: str
    window_index: int
    from_location_token: str
    to_location_token: str
    flow_counts: tuple[tuple[str, int], ...]
    transfer_count: int
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        _require_token("corridor_token", self.corridor_token)
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        _require_token("from_location_token", self.from_location_token)
        _require_token("to_location_token", self.to_location_token)
        object.__setattr__(self, "flow_counts", _require_flow_counts(self.flow_counts))
        object.__setattr__(
            self,
            "transfer_count",
            _require_tick("transfer_count", self.transfer_count),
        )
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeFlowRow:
    """Per-window flow-class totals with non-disjoint role counts."""

    window_index: int
    flow_class: TradeFlowClass
    transfer_count: int
    cross_location_count: int
    imported_count: int
    exported_count: int
    local_count: int
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        if self.flow_class.value not in _FLOW_VALUES:
            raise TradeNetworksError("trade_networks_invalid_input")
        for name in (
            "transfer_count",
            "cross_location_count",
            "imported_count",
            "exported_count",
            "local_count",
        ):
            object.__setattr__(self, name, _require_tick(name, getattr(self, name)))
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeLocationRow:
    """Exchange activity at one location in one window."""

    location_token: str
    window_index: int
    inflow_count: int
    outflow_count: int
    local_count: int
    corridor_degree: int
    is_major: bool
    trade_post_present: bool
    flow_counts: tuple[tuple[str, int], ...]
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        _require_token("location_token", self.location_token)
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        for name in (
            "inflow_count",
            "outflow_count",
            "local_count",
            "corridor_degree",
        ):
            object.__setattr__(self, name, _require_tick(name, getattr(self, name)))
        if type(self.is_major) is not bool or type(self.trade_post_present) is not bool:
            raise TradeNetworksError("trade_networks_invalid_input")
        object.__setattr__(self, "flow_counts", _require_flow_counts(self.flow_counts))
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeDependenceRow:
    """Observed exchange dependence for one location/window/class."""

    location_token: str
    window_index: int
    flow_class: TradeFlowClass
    imported_count: int
    locally_originated_count: int
    dependence_milli: int | None
    high_dependence: bool
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        _require_token("location_token", self.location_token)
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        if self.flow_class.value not in _FLOW_VALUES:
            raise TradeNetworksError("trade_networks_invalid_input")
        for name in ("imported_count", "locally_originated_count"):
            object.__setattr__(self, name, _require_tick(name, getattr(self, name)))
        if self.dependence_milli is not None:
            if (
                isinstance(self.dependence_milli, bool)
                or type(self.dependence_milli) is not int
                or self.dependence_milli < 0
                or self.dependence_milli > 1_000
            ):
                raise TradeNetworksError("trade_networks_invalid_input")
        if type(self.high_dependence) is not bool:
            raise TradeNetworksError("trade_networks_invalid_input")
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeNetworkRow:
    """One connected component of the undirected corridor union."""

    network_token: str
    window_index: int
    corridor_tokens: tuple[str, ...]
    location_tokens: tuple[str, ...]
    flow_counts: tuple[tuple[str, int], ...]
    transfer_count: int
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        _require_token("network_token", self.network_token)
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        if not self.corridor_tokens:
            raise TradeNetworksError("trade_networks_invalid_input")
        for token in self.corridor_tokens:
            _require_token("corridor_token", token)
        if tuple(sorted(set(self.corridor_tokens))) != self.corridor_tokens:
            raise TradeNetworksError("trade_networks_invalid_input")
        if not self.location_tokens:
            raise TradeNetworksError("trade_networks_invalid_input")
        for token in self.location_tokens:
            _require_token("location_token", token)
        if tuple(sorted(set(self.location_tokens))) != self.location_tokens:
            raise TradeNetworksError("trade_networks_invalid_input")
        object.__setattr__(self, "flow_counts", _require_flow_counts(self.flow_counts))
        object.__setattr__(
            self,
            "transfer_count",
            _require_tick("transfer_count", self.transfer_count),
        )
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeLineageRow:
    """One forward-only network lineage transition."""

    network_token: str
    previous_token: str
    relation: str
    first_tick: int
    last_tick: int
    rerouted: bool
    sustained: bool

    def __post_init__(self) -> None:
        _require_token("network_token", self.network_token)
        _require_token("previous_token", self.previous_token)
        if self.relation not in _LINEAGE_RELATIONS:
            raise TradeNetworksError("trade_networks_invalid_input")
        object.__setattr__(
            self, "first_tick", _require_tick("first_tick", self.first_tick)
        )
        object.__setattr__(
            self, "last_tick", _require_tick("last_tick", self.last_tick)
        )
        if self.last_tick < self.first_tick:
            raise TradeNetworksError("trade_networks_invalid_input")
        if type(self.rerouted) is not bool or type(self.sustained) is not bool:
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.rerouted != (self.relation == "transformed"):
            raise TradeNetworksError("trade_networks_invalid_input")
        if self.sustained and self.relation not in {"continued", "transformed"}:
            raise TradeNetworksError("trade_networks_invalid_input")


@dataclass(frozen=True, slots=True)
class CrossSocietyTradeRow:
    """Analytical exchange view over one contemporaneous society pair."""

    pair_token: str
    window_index: int
    society_a: str
    society_b: str
    society_a_location_id: str
    society_b_location_id: str
    overlap_member_count: int
    flow_counts: tuple[tuple[str, int], ...]
    transfer_count: int
    society_a_to_b_count: int
    society_b_to_a_count: int
    coverage: TradeCoverage = TradeCoverage.COMPLETE

    def __post_init__(self) -> None:
        _require_token("pair_token", self.pair_token)
        object.__setattr__(
            self, "window_index", _require_tick("window_index", self.window_index)
        )
        _require_token("society_a", self.society_a)
        _require_token("society_b", self.society_b)
        if self.society_a >= self.society_b:
            raise TradeNetworksError("trade_networks_invalid_input")
        _require_token("society_a_location_id", self.society_a_location_id)
        _require_token("society_b_location_id", self.society_b_location_id)
        for name in (
            "overlap_member_count",
            "transfer_count",
            "society_a_to_b_count",
            "society_b_to_a_count",
        ):
            object.__setattr__(self, name, _require_tick(name, getattr(self, name)))
        object.__setattr__(self, "flow_counts", _require_flow_counts(self.flow_counts))
        _require_coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeNetworksHarvestRows:
    """Combined bounded detection output before metrics or snapshots."""

    transfers: tuple[TradeTransferRow, ...] = ()
    supplies: tuple[TradeLocalSupplyRow, ...] = ()
    corridors: tuple[TradeCorridorRow, ...] = ()
    flows: tuple[TradeFlowRow, ...] = ()
    locations: tuple[TradeLocationRow, ...] = ()
    dependence: tuple[TradeDependenceRow, ...] = ()
    networks: tuple[TradeNetworkRow, ...] = ()
    lineage: tuple[TradeLineageRow, ...] = ()
    cross_society: tuple[CrossSocietyTradeRow, ...] = ()
    coverage: TradeCoverage = TradeCoverage.MISSING
    notices: tuple[str, ...] = ()
    transfer_count: int = 0
    corridor_count: int = 0
    network_count: int = 0
    cross_society_pair_count: int = 0

    def __post_init__(self) -> None:
        _require_coverage(self.coverage)
        for name in (
            "transfer_count",
            "corridor_count",
            "network_count",
            "cross_society_pair_count",
        ):
            object.__setattr__(self, name, _require_tick(name, getattr(self, name)))
