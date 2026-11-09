"""Bounded deterministic paging for infrastructure-networks snapshot rows."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from simulation.infrastructure_models import (
    InfrastructureAssetRecord,
    InfrastructureNetworksSnapshot,
    TravelRouteRecord,
)

__all__ = [
    "MAX_PAGE_LIMIT",
    "InfrastructureNetworksRowSelection",
    "TravelRouteRowSelection",
    "page_infrastructure_networks_rows",
    "page_travel_routes",
]

_LOG: Final[logging.Logger] = logging.getLogger("simulation.infrastructure.paging")

MAX_PAGE_LIMIT: Final[int] = 500
_LIST_PURPOSES: Final[frozenset[str]] = frozenset(
    {"assets", "edges", "condition", "effects", "maintenance"}
)


@dataclass(frozen=True, slots=True)
class InfrastructureNetworksRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    rows: tuple[InfrastructureAssetRecord, ...] = ()
    next_key: str | None = None


def _clamp_limit(limit: object) -> int:
    if type(limit) is not int or limit < 1 or limit > MAX_PAGE_LIMIT:
        raise ValueError("infrastructure_networks_page_limit")
    return limit


def _row_key(row: InfrastructureAssetRecord) -> str:
    return str(row.asset_id)


def _ordered_rows(
    snapshot: InfrastructureNetworksSnapshot, purpose: str
) -> tuple[InfrastructureAssetRecord, ...]:
    assets = tuple(sorted(snapshot.assets, key=lambda row: row.asset_id))
    if purpose == "assets":
        return assets
    if purpose == "edges":
        return tuple(row for row in assets if row.topology == "edge")
    if purpose == "condition":
        return assets
    if purpose == "effects":
        return assets
    if purpose == "maintenance":
        return assets
    raise ValueError("infrastructure_networks_cursor_purpose")


@dataclass(frozen=True, slots=True)
class TravelRouteRowSelection:
    purpose: str
    after_key: str | None
    limit: int
    rows: tuple[TravelRouteRecord, ...] = ()
    next_key: str | None = None


def _route_key(row: TravelRouteRecord) -> str:
    return f"{row.origin_location_id}:{row.destination_location_id}"


def page_travel_routes(
    snapshot: InfrastructureNetworksSnapshot,
    *,
    after_key: str | None = None,
    limit: int | None = None,
) -> TravelRouteRowSelection:
    if type(snapshot) is not InfrastructureNetworksSnapshot:
        raise TypeError("snapshot must be InfrastructureNetworksSnapshot")
    clamped = _clamp_limit(100 if limit is None else limit)
    ordered = list(sorted(snapshot.routes, key=_route_key))
    if after_key is not None:
        if type(after_key) is not str or not after_key:
            raise ValueError("infrastructure_networks_cursor_invalid")
        ordered = [row for row in ordered if _route_key(row) > after_key]
    page = tuple(ordered[:clamped])
    next_key = _route_key(page[-1]) if len(ordered) > len(page) and page else None
    result = TravelRouteRowSelection(
        purpose="routes",
        after_key=after_key,
        limit=clamped,
        rows=page,
        next_key=next_key,
    )
    _LOG.debug("infrastructure_networks_page purpose=routes rows=%s", len(page))
    return result


def page_infrastructure_networks_rows(
    snapshot: InfrastructureNetworksSnapshot,
    selection: InfrastructureNetworksRowSelection | None = None,
    *,
    purpose: str | None = None,
    after_key: str | None = None,
    limit: int | None = None,
) -> InfrastructureNetworksRowSelection:
    if type(snapshot) is not InfrastructureNetworksSnapshot:
        raise TypeError("snapshot must be InfrastructureNetworksSnapshot")
    if selection is not None:
        if type(selection) is not InfrastructureNetworksRowSelection:
            raise TypeError("selection must be InfrastructureNetworksRowSelection")
        purpose = selection.purpose
        after_key = selection.after_key
        limit = selection.limit
    if purpose is None or purpose not in _LIST_PURPOSES:
        raise ValueError("infrastructure_networks_cursor_purpose")
    clamped = _clamp_limit(1 if limit is None else limit)
    ordered = list(_ordered_rows(snapshot, purpose))
    if after_key is not None:
        if type(after_key) is not str or not after_key:
            raise ValueError("infrastructure_networks_cursor_invalid")
        ordered = [row for row in ordered if _row_key(row) > after_key]
    page = tuple(ordered[:clamped])
    next_key = _row_key(page[-1]) if len(ordered) > len(page) and page else None
    result = InfrastructureNetworksRowSelection(
        purpose=purpose,
        after_key=after_key,
        limit=clamped,
        rows=page,
        next_key=next_key,
    )
    _LOG.debug(
        "infrastructure_networks_page purpose=%s rows=%s",
        purpose,
        len(result.rows),
    )
    return result
