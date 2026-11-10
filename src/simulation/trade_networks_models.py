"""Bounded canonical ``trade-networks-snapshot-v1`` document.

Independent of ``analysis``: experiments maps harvest outputs into these DTOs.
The snapshot carries observed counts and bounded ratios only; it has no
economic valuation, central routing, or aggregate ordering field.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "MAX_TRADE_SNAPSHOT_CORRIDORS",
    "MAX_TRADE_SNAPSHOT_CROSS_SOCIETY",
    "MAX_TRADE_SNAPSHOT_DEPENDENCE",
    "MAX_TRADE_SNAPSHOT_FLOWS",
    "MAX_TRADE_SNAPSHOT_LINEAGE_EDGES",
    "MAX_TRADE_SNAPSHOT_LOCATIONS",
    "MAX_TRADE_SNAPSHOT_NETWORKS",
    "MAX_TRADE_SNAPSHOT_WINDOWS",
    "TRADE_NETWORKS_SNAPSHOT_POLICY",
    "TRADE_NETWORKS_SNAPSHOT_VERSION",
    "TRADE_SNAPSHOT_COVERAGES",
    "TRADE_SNAPSHOT_FLOW_CLASSES",
    "TRADE_SNAPSHOT_NETWORK_STATUSES",
    "CrossSocietyTradeRecord",
    "TradeCorridorRecord",
    "TradeDependenceRecord",
    "TradeFlowCountRecord",
    "TradeFlowRecord",
    "TradeLocationRecord",
    "TradeNetworkRecord",
    "TradeNetworksArtifactError",
    "TradeNetworksSnapshot",
    "TradeNetworksSummaryRecord",
    "empty_trade_networks_snapshot",
]

TRADE_NETWORKS_SNAPSHOT_VERSION: Final[str] = "trade-networks-snapshot-v1"
TRADE_NETWORKS_SNAPSHOT_POLICY: Final[str] = "trade-networks.v1"
MAX_TRADE_SNAPSHOT_CORRIDORS: Final[int] = 4_096
MAX_TRADE_SNAPSHOT_FLOWS: Final[int] = 3_072
MAX_TRADE_SNAPSHOT_LOCATIONS: Final[int] = 4_096
MAX_TRADE_SNAPSHOT_DEPENDENCE: Final[int] = 8_192
MAX_TRADE_SNAPSHOT_CROSS_SOCIETY: Final[int] = 2_048
MAX_TRADE_SNAPSHOT_NETWORKS: Final[int] = 1_024
MAX_TRADE_SNAPSHOT_WINDOWS: Final[int] = 512
MAX_TRADE_SNAPSHOT_LINEAGE_EDGES: Final[int] = 16_384

TRADE_SNAPSHOT_FLOW_CLASSES: Final[tuple[str, ...]] = (
    "food",
    "materials",
    "tools",
    "records",
    "durable_exchange_media",
    "other",
)
TRADE_SNAPSHOT_COVERAGES: Final[tuple[str, ...]] = (
    "complete",
    "partial",
    "missing",
)
TRADE_SNAPSHOT_NETWORK_STATUSES: Final[tuple[str, ...]] = (
    "observed",
    "emerged",
    "continued",
    "transformed",
    "split",
    "merge",
    "dissolved",
)

_FLOW_SET: Final[frozenset[str]] = frozenset(TRADE_SNAPSHOT_FLOW_CLASSES)
_COVERAGE_SET: Final[frozenset[str]] = frozenset(TRADE_SNAPSHOT_COVERAGES)
_STATUS_SET: Final[frozenset[str]] = frozenset(TRADE_SNAPSHOT_NETWORK_STATUSES)
_CORRIDOR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^trd-cor-[0-9a-f]{16}$")
_NETWORK_PATTERN: Final[re.Pattern[str]] = re.compile(r"^trd-net-[0-9a-f]{16}$")
_PAIR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^trd-pair-[0-9a-f]{16}$")
_LOG: Final[logging.Logger] = logging.getLogger("simulation.trade_networks.models")


class TradeNetworksArtifactError(ValueError):
    """Fail-closed snapshot error with a stable reason code only."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = require_stable_id("reason_code", reason_code)
        _LOG.debug("trade_networks_artifact_invalid reason_code=%s", reason_code)
        super().__init__(reason_code)


def _stable(name: str, value: object) -> str:
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise TradeNetworksArtifactError(
            "trade_networks_artifact_invalid_value"
        ) from exc


def _count(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except ValueError as exc:
        raise TradeNetworksArtifactError(
            "trade_networks_artifact_invalid_value"
        ) from exc


def _window_index(value: object) -> int:
    window_index = _count("window_index", value)
    if window_index >= MAX_TRADE_SNAPSHOT_WINDOWS:
        raise TradeNetworksArtifactError(
            "trade_networks_artifact_invalid_window_index"
        )
    return window_index


def _coverage(value: object) -> str:
    if not isinstance(value, str) or value not in _COVERAGE_SET:
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_coverage")
    return value


def _bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
    return value


def _flow_counts(
    value: tuple[TradeFlowCountRecord, ...],
) -> tuple[TradeFlowCountRecord, ...]:
    if type(value) is not tuple or any(
        type(item) is not TradeFlowCountRecord for item in value
    ):
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_flow_counts")
    classes = tuple(item.flow_class for item in value)
    if classes != tuple(sorted(set(classes))):
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_flow_counts")
    return value


@dataclass(frozen=True, slots=True)
class TradeFlowCountRecord:
    flow_class: str
    count: int

    def __post_init__(self) -> None:
        if self.flow_class not in _FLOW_SET:
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_flow_class"
            )
        object.__setattr__(self, "count", _count("count", self.count))


@dataclass(frozen=True, slots=True)
class TradeCorridorRecord:
    corridor_id: str
    window_index: int
    from_location_id: str
    to_location_id: str
    flow_counts: tuple[TradeFlowCountRecord, ...]
    transfer_count: int
    coverage: str

    def __post_init__(self) -> None:
        if not isinstance(self.corridor_id, str) or not _CORRIDOR_PATTERN.match(
            self.corridor_id
        ):
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_corridor_id"
            )
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        _stable("from_location_id", self.from_location_id)
        _stable("to_location_id", self.to_location_id)
        object.__setattr__(self, "flow_counts", _flow_counts(self.flow_counts))
        object.__setattr__(
            self, "transfer_count", _count("transfer_count", self.transfer_count)
        )
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeFlowRecord:
    window_index: int
    flow_class: str
    transfer_count: int
    cross_location_count: int
    imported_count: int
    exported_count: int
    local_count: int
    coverage: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        if self.flow_class not in _FLOW_SET:
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_flow_class"
            )
        for name in (
            "transfer_count",
            "cross_location_count",
            "imported_count",
            "exported_count",
            "local_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeLocationRecord:
    location_id: str
    window_index: int
    inflow_count: int
    outflow_count: int
    local_count: int
    corridor_degree: int
    is_major: bool
    trade_post_present: bool
    flow_counts: tuple[TradeFlowCountRecord, ...]
    coverage: str

    def __post_init__(self) -> None:
        _stable("location_id", self.location_id)
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        for name in (
            "inflow_count",
            "outflow_count",
            "local_count",
            "corridor_degree",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        _bool("is_major", self.is_major)
        _bool("trade_post_present", self.trade_post_present)
        object.__setattr__(self, "flow_counts", _flow_counts(self.flow_counts))
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeDependenceRecord:
    location_id: str
    window_index: int
    flow_class: str
    imported_count: int
    locally_originated_count: int
    dependence_milli: int | None
    high_dependence: bool
    coverage: str

    def __post_init__(self) -> None:
        _stable("location_id", self.location_id)
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        if self.flow_class not in _FLOW_SET:
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_flow_class"
            )
        object.__setattr__(
            self, "imported_count", _count("imported_count", self.imported_count)
        )
        object.__setattr__(
            self,
            "locally_originated_count",
            _count("locally_originated_count", self.locally_originated_count),
        )
        if self.dependence_milli is not None:
            value = _count("dependence_milli", self.dependence_milli)
            if value > 1_000:
                raise TradeNetworksArtifactError(
                    "trade_networks_artifact_invalid_value"
                )
        _bool("high_dependence", self.high_dependence)
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class CrossSocietyTradeRecord:
    pair_id: str
    window_index: int
    society_a: str
    society_b: str
    society_a_location_id: str
    society_b_location_id: str
    overlap_member_count: int
    flow_counts: tuple[TradeFlowCountRecord, ...]
    transfer_count: int
    society_a_to_b_count: int
    society_b_to_a_count: int
    coverage: str

    def __post_init__(self) -> None:
        if not isinstance(self.pair_id, str) or not _PAIR_PATTERN.match(self.pair_id):
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_pair_id")
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        _stable("society_a", self.society_a)
        _stable("society_b", self.society_b)
        if self.society_a >= self.society_b:
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
        _stable("society_a_location_id", self.society_a_location_id)
        _stable("society_b_location_id", self.society_b_location_id)
        for name in (
            "overlap_member_count",
            "transfer_count",
            "society_a_to_b_count",
            "society_b_to_a_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(self, "flow_counts", _flow_counts(self.flow_counts))
        _coverage(self.coverage)


def _network_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    if type(values) is not tuple:
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
    for value in values:
        if not isinstance(value, str) or not _NETWORK_PATTERN.match(value):
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_network_id"
            )
    if values != tuple(sorted(set(values))):
        raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
    return values


@dataclass(frozen=True, slots=True)
class TradeNetworkRecord:
    network_id: str
    window_index: int
    corridor_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    flow_counts: tuple[TradeFlowCountRecord, ...]
    transfer_count: int
    status: str
    previous_network_ids: tuple[str, ...]
    next_network_ids: tuple[str, ...]
    rerouted: bool
    sustained: bool
    coverage: str

    def __post_init__(self) -> None:
        if not isinstance(self.network_id, str) or not _NETWORK_PATTERN.match(
            self.network_id
        ):
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_network_id"
            )
        object.__setattr__(
            self, "window_index", _window_index(self.window_index)
        )
        if (
            type(self.corridor_ids) is not tuple
            or not self.corridor_ids
            or self.corridor_ids != tuple(sorted(set(self.corridor_ids)))
        ):
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
        for corridor_id in self.corridor_ids:
            if not isinstance(corridor_id, str) or not _CORRIDOR_PATTERN.match(
                corridor_id
            ):
                raise TradeNetworksArtifactError(
                    "trade_networks_artifact_invalid_corridor_id"
                )
        if (
            type(self.location_ids) is not tuple
            or not self.location_ids
            or self.location_ids != tuple(sorted(set(self.location_ids)))
        ):
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_value")
        for location_id in self.location_ids:
            _stable("location_id", location_id)
        object.__setattr__(self, "flow_counts", _flow_counts(self.flow_counts))
        object.__setattr__(
            self, "transfer_count", _count("transfer_count", self.transfer_count)
        )
        if self.status not in _STATUS_SET:
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_status")
        object.__setattr__(
            self, "previous_network_ids", _network_ids(self.previous_network_ids)
        )
        object.__setattr__(
            self, "next_network_ids", _network_ids(self.next_network_ids)
        )
        _bool("rerouted", self.rerouted)
        _bool("sustained", self.sustained)
        _coverage(self.coverage)


@dataclass(frozen=True, slots=True)
class TradeNetworksSummaryRecord:
    window_tick: int
    corridor_count: int
    flow_count: int
    location_count: int
    major_location_count: int
    trade_post_location_count: int
    network_count: int
    cross_society_pair_count: int
    transfer_count: int
    emerged_count: int
    continued_count: int
    transformed_count: int
    split_count: int
    merge_count: int
    dissolved_count: int
    rerouted_count: int
    sustained_network_count: int
    lineage_edge_count: int
    coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in (
            "window_tick",
            "corridor_count",
            "flow_count",
            "location_count",
            "major_location_count",
            "trade_post_location_count",
            "network_count",
            "cross_society_pair_count",
            "transfer_count",
            "emerged_count",
            "continued_count",
            "transformed_count",
            "split_count",
            "merge_count",
            "dissolved_count",
            "rerouted_count",
            "sustained_network_count",
            "lineage_edge_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.lineage_edge_count > MAX_TRADE_SNAPSHOT_LINEAGE_EDGES:
            raise TradeNetworksArtifactError("trade_networks_artifact_cap_exceeded")
        _coverage(self.coverage)
        _bool("truncated", self.truncated)


@dataclass(frozen=True, slots=True)
class TradeNetworksSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: TradeNetworksSummaryRecord
    corridors: tuple[TradeCorridorRecord, ...] = ()
    flows: tuple[TradeFlowRecord, ...] = ()
    locations: tuple[TradeLocationRecord, ...] = ()
    dependence: tuple[TradeDependenceRecord, ...] = ()
    cross_society: tuple[CrossSocietyTradeRecord, ...] = ()
    networks: tuple[TradeNetworkRecord, ...] = ()
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        _stable("run_id", self.run_id)
        if self.schema_version != TRADE_NETWORKS_SNAPSHOT_VERSION:
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_schema")
        if self.policy_version != TRADE_NETWORKS_SNAPSHOT_POLICY:
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_policy")
        if type(self.summary) is not TradeNetworksSummaryRecord:
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_summary")
        for name, cap, row_type in (
            ("corridors", MAX_TRADE_SNAPSHOT_CORRIDORS, TradeCorridorRecord),
            ("flows", MAX_TRADE_SNAPSHOT_FLOWS, TradeFlowRecord),
            ("locations", MAX_TRADE_SNAPSHOT_LOCATIONS, TradeLocationRecord),
            ("dependence", MAX_TRADE_SNAPSHOT_DEPENDENCE, TradeDependenceRecord),
            (
                "cross_society",
                MAX_TRADE_SNAPSHOT_CROSS_SOCIETY,
                CrossSocietyTradeRecord,
            ),
            ("networks", MAX_TRADE_SNAPSHOT_NETWORKS, TradeNetworkRecord),
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple or any(
                type(item) is not row_type for item in rows
            ):
                raise TradeNetworksArtifactError("trade_networks_artifact_invalid_rows")
            if len(rows) > cap:
                raise TradeNetworksArtifactError("trade_networks_artifact_cap_exceeded")
        if type(self.digest) is not str or (self.digest and (len(self.digest) != 64)):
            raise TradeNetworksArtifactError("trade_networks_artifact_invalid_digest")
        if type(self.publication_id) is not str:
            raise TradeNetworksArtifactError(
                "trade_networks_artifact_invalid_publication_id"
            )


def empty_trade_networks_snapshot(
    run_id: str, *, digest: str = "", publication_id: str = ""
) -> TradeNetworksSnapshot:
    """Return a canonical empty snapshot."""
    return TradeNetworksSnapshot(
        run_id=_stable("run_id", run_id),
        schema_version=TRADE_NETWORKS_SNAPSHOT_VERSION,
        policy_version=TRADE_NETWORKS_SNAPSHOT_POLICY,
        summary=TradeNetworksSummaryRecord(
            window_tick=0,
            corridor_count=0,
            flow_count=0,
            location_count=0,
            major_location_count=0,
            trade_post_location_count=0,
            network_count=0,
            cross_society_pair_count=0,
            transfer_count=0,
            emerged_count=0,
            continued_count=0,
            transformed_count=0,
            split_count=0,
            merge_count=0,
            dissolved_count=0,
            rerouted_count=0,
            sustained_network_count=0,
            lineage_edge_count=0,
            coverage="missing",
            truncated=False,
        ),
        digest=digest,
        publication_id=publication_id,
    )
