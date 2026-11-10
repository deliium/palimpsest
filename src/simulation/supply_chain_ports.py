"""Read/publication ports for the supply-chain snapshot."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.supply_chain_models import SupplyChainSnapshot

__all__ = [
    "SUPPLY_CHAIN_CURSOR_PURPOSES",
    "SupplyChainCursor",
    "SupplyChainPublication",
    "SupplyChainPublisher",
    "SupplyChainReader",
    "SupplyChainSummary",
    "supply_chain_cursor_matches",
    "supply_chain_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.supply_chain.ports")

SUPPLY_CHAIN_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "stages",
    "dependencies",
    "chains",
    "bottlenecks",
    "locations",
    "organizations",
)
_PURPOSES: Final[frozenset[str]] = frozenset(SUPPLY_CHAIN_CURSOR_PURPOSES)


@dataclass(frozen=True, slots=True)
class SupplyChainSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    stage_count: int = 0
    edge_count: int = 0
    chain_count: int = 0
    bottleneck_count: int = 0
    location_count: int = 0
    organization_count: int = 0
    coverage: str = "missing"


@dataclass(frozen=True, slots=True)
class SupplyChainPublication:
    publication_id: str
    digest: str
    snapshot: SupplyChainSnapshot


@dataclass(frozen=True, slots=True)
class SupplyChainCursor:
    purpose: str
    after_key: str | None
    limit: int
    fingerprint: str
    window_index: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in _PURPOSES:
            raise ValueError("supply_chain_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("supply_chain_cursor_fingerprint")
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError("supply_chain_page_limit")
        if self.after_key is not None and (
            type(self.after_key) is not str or not self.after_key
        ):
            raise ValueError("supply_chain_cursor_invalid")
        if self.window_index is not None and (
            isinstance(self.window_index, bool)
            or type(self.window_index) is not int
            or self.window_index < 0
        ):
            raise ValueError("supply_chain_cursor_invalid")


def supply_chain_query_fingerprint(
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
        raise ValueError("supply_chain_cursor_purpose")
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
        "v": "palimpsest.supply_chain.cursor.v1",
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def supply_chain_cursor_matches(cursor: SupplyChainCursor, fingerprint: str) -> bool:
    if type(cursor) is not SupplyChainCursor:
        return False
    matched = cursor.fingerprint == fingerprint
    if not matched:
        _LOG.warning("supply_chain_cursor_invalid")
    return matched


@runtime_checkable
class SupplyChainReader(Protocol):
    def read_summary(self, run_id: str) -> SupplyChainSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> SupplyChainSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...


@runtime_checkable
class SupplyChainPublisher(Protocol):
    def publish(self, snapshot: SupplyChainSnapshot) -> None: ...

    def read_summary(self, run_id: str) -> SupplyChainSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> SupplyChainSnapshot | None: ...
