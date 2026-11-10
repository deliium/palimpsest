"""Read/publication ports for the trade-network snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.trade_networks_models import TradeNetworksSnapshot

__all__ = [
    "TRADE_NETWORKS_CURSOR_PURPOSES",
    "TradeNetworksCursor",
    "TradeNetworksPublication",
    "TradeNetworksPublisher",
    "TradeNetworksReader",
    "TradeNetworksSummary",
    "trade_networks_cursor_matches",
    "trade_networks_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.trade_networks.ports")

TRADE_NETWORKS_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "corridors",
    "flows",
    "locations",
    "dependence",
    "cross-society",
    "networks",
)
_PURPOSES: Final[frozenset[str]] = frozenset(TRADE_NETWORKS_CURSOR_PURPOSES)


@dataclass(frozen=True, slots=True)
class TradeNetworksSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    corridor_count: int = 0
    flow_count: int = 0
    location_count: int = 0
    network_count: int = 0
    cross_society_pair_count: int = 0
    coverage: str = "missing"


@dataclass(frozen=True, slots=True)
class TradeNetworksPublication:
    publication_id: str
    digest: str
    snapshot: TradeNetworksSnapshot


@dataclass(frozen=True, slots=True)
class TradeNetworksCursor:
    purpose: str
    after_key: str | None
    limit: int
    fingerprint: str
    window_index: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in _PURPOSES:
            raise ValueError("trade_networks_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("trade_networks_cursor_fingerprint")
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError("trade_networks_page_limit")
        if self.after_key is not None and (
            type(self.after_key) is not str or not self.after_key
        ):
            raise ValueError("trade_networks_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or self.window_index < 0
        ):
            raise ValueError("trade_networks_cursor_invalid")


def trade_networks_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
    after_key: str | None = None,
    limit: int,
) -> str:
    if purpose not in _PURPOSES:
        raise ValueError("trade_networks_cursor_purpose")
    payload = {
        "after_key": after_key,
        "digest": digest,
        "filters": {
            str(key): (filters or {})[key] for key in sorted(filters or {}, key=str)
        },
        "limit": limit,
        "publication_id": publication_id,
        "purpose": purpose,
        "run_id": run_id,
        "v": "palimpsest.trade_networks.cursor.v1",
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def trade_networks_cursor_matches(
    cursor: TradeNetworksCursor, fingerprint: str
) -> bool:
    if type(cursor) is not TradeNetworksCursor:
        return False
    matched = cursor.fingerprint == fingerprint
    if not matched:
        _LOG.warning("trade_networks_cursor_invalid")
    return matched


@runtime_checkable
class TradeNetworksReader(Protocol):
    def read_summary(self, run_id: str) -> TradeNetworksSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> TradeNetworksSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...


@runtime_checkable
class TradeNetworksPublisher(Protocol):
    def publish(self, snapshot: TradeNetworksSnapshot) -> None: ...

    def read_summary(self, run_id: str) -> TradeNetworksSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> TradeNetworksSnapshot | None: ...
