"""Typed read and publication ports for infrastructure-networks snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol, runtime_checkable

from simulation.infrastructure_models import InfrastructureNetworksSnapshot
from simulation.infrastructure_paging import (
    MAX_PAGE_LIMIT,
    InfrastructureNetworksRowSelection,
    page_infrastructure_networks_rows,
)

__all__ = [
    "INFRASTRUCTURE_NETWORKS_CURSOR_PURPOSES",
    "MAX_PAGE_LIMIT",
    "InfrastructureNetworksCursor",
    "InfrastructureNetworksPublication",
    "InfrastructureNetworksPublisherPort",
    "InfrastructureNetworksReadPort",
    "InfrastructureNetworksSummary",
    "infrastructure_networks_cursor_matches",
    "infrastructure_networks_query_fingerprint",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.infrastructure.ports")

INFRASTRUCTURE_NETWORKS_CURSOR_PURPOSES: Final[tuple[str, ...]] = (
    "summary",
    "assets",
    "edges",
    "condition",
    "effects",
    "maintenance",
)
_PURPOSE_SET: Final[frozenset[str]] = frozenset(INFRASTRUCTURE_NETWORKS_CURSOR_PURPOSES)


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksSummary:
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    asset_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    operational_count: int = 0
    damaged_count: int = 0
    destroyed_count: int = 0
    effects_active_count: int = 0
    coverage: str = "not_applicable"


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksPublication:
    publication_id: str
    digest: str
    snapshot: InfrastructureNetworksSnapshot


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksCursor:
    purpose: str
    after_key: str | None
    limit: int
    fingerprint: str
    expires_at_tick: int | None = None

    def __post_init__(self) -> None:
        if self.purpose not in _PURPOSE_SET:
            raise ValueError("infrastructure_networks_cursor_purpose")
        if type(self.fingerprint) is not str or not self.fingerprint:
            raise ValueError("infrastructure_networks_cursor_fingerprint")
        if type(self.limit) is not int or self.limit < 1 or self.limit > MAX_PAGE_LIMIT:
            raise ValueError("infrastructure_networks_page_limit")
        if self.after_key is not None and (
            type(self.after_key) is not str or not self.after_key
        ):
            raise ValueError("infrastructure_networks_cursor_after_key")
        if self.expires_at_tick is not None and (
            type(self.expires_at_tick) is not int or self.expires_at_tick < 0
        ):
            raise ValueError("infrastructure_networks_cursor_expiry")


def infrastructure_networks_query_fingerprint(
    *,
    run_id: str,
    publication_id: str,
    digest: str,
    purpose: str,
    filters: Mapping[str, object] | None = None,
    after_key: str | None = None,
    limit: int,
) -> str:
    if purpose not in _PURPOSE_SET:
        raise ValueError("infrastructure_networks_cursor_purpose")
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("infrastructure_networks_page_limit")
    payload = {
        "after_key": after_key,
        "digest": digest,
        "filters": {
            str(key): (filters or {})[key]
            for key in sorted((filters or {}), key=str)
        },
        "limit": limit,
        "publication_id": publication_id,
        "purpose": purpose,
        "run_id": run_id,
        "v": "palimpsest.infrastructure_networks.cursor.v1",
    }
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def infrastructure_networks_cursor_matches(
    cursor: InfrastructureNetworksCursor, fingerprint: str
) -> bool:
    if type(cursor) is not InfrastructureNetworksCursor:
        return False
    matched = cursor.fingerprint == fingerprint
    if not matched:
        _LOG.warning("infrastructure_networks_cursor_invalid")
    return matched


def bounded_infrastructure_networks_rows(
    snapshot: InfrastructureNetworksSnapshot,
    purpose: str,
    after_key: str | None,
    limit: int,
) -> InfrastructureNetworksRowSelection:
    if purpose not in _PURPOSE_SET or purpose == "summary":
        raise ValueError("infrastructure_networks_cursor_purpose")
    selection = page_infrastructure_networks_rows(
        snapshot,
        InfrastructureNetworksRowSelection(
            purpose=purpose,
            after_key=after_key,
            limit=limit,
        ),
    )
    _LOG.debug(
        "infrastructure_networks_page purpose=%s rows=%s",
        purpose,
        len(selection.rows),
    )
    return selection


@runtime_checkable
class InfrastructureNetworksReadPort(Protocol):
    def summary(self, run_id: str) -> InfrastructureNetworksSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InfrastructureNetworksSnapshot | None: ...

    def list_publications(self, run_id: str) -> tuple[str, ...]: ...


@runtime_checkable
class InfrastructureNetworksPublisherPort(Protocol):
    def publish(self, snapshot: InfrastructureNetworksSnapshot) -> None: ...

    def read_summary(self, run_id: str) -> InfrastructureNetworksSummary | None: ...

    def read_snapshot(
        self, run_id: str, publication_id: str | None = None
    ) -> InfrastructureNetworksSnapshot | None: ...
