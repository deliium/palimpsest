"""Pure bounded paging for ``supply-chains-snapshot-v1`` row families."""

from __future__ import annotations

from typing import Final

from simulation.supply_chain_models import (
    SupplyBottleneckRecord,
    SupplyChainRecord,
    SupplyDependencyRecord,
    SupplyLocationRecord,
    SupplyOrganizationRecord,
    SupplyStageRecord,
)

__all__ = [
    "MAX_PAGE_LIMIT",
    "page_bottlenecks",
    "page_chains",
    "page_dependencies",
    "page_locations",
    "page_organizations",
    "page_stages",
]

MAX_PAGE_LIMIT: Final[int] = 500


def _validate(limit: object, window_index: object) -> tuple[int, int | None]:
    if isinstance(limit, bool) or type(limit) is not int or limit < 1:
        raise ValueError("supply_chain_page_limit")
    if limit > MAX_PAGE_LIMIT:
        limit = MAX_PAGE_LIMIT
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or window_index < 0
    ):
        raise ValueError("supply_chain_window_index")
    return limit, window_index


def _row_key(row: object) -> str:
    window_value = getattr(row, "window_index", 0)
    window = window_value if isinstance(window_value, int) else 0
    token = (
        getattr(row, "stage_token", None)
        or getattr(row, "edge_token", None)
        or getattr(row, "chain_token", None)
        or getattr(row, "bottleneck_token", None)
        or getattr(row, "location_token", None)
        or getattr(row, "organization_token", None)
    )
    return f"{window:08d}:{token}"


def _page[Row](
    rows: tuple[Row, ...],
    *,
    after_key: str | None,
    limit: int,
    window_index: int | None,
) -> tuple[tuple[Row, ...], str | None]:
    filtered = tuple(
        row
        for row in rows
        if window_index is None or getattr(row, "window_index", None) == window_index
    )
    ordered = tuple(sorted(filtered, key=_row_key))
    if after_key is not None:
        ordered = tuple(row for row in ordered if _row_key(row) > after_key)
    selected = ordered[:limit]
    next_key = _row_key(selected[-1]) if len(ordered) > limit and selected else None
    return selected, next_key


def page_stages(
    rows: tuple[SupplyStageRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyStageRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)


def page_dependencies(
    rows: tuple[SupplyDependencyRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyDependencyRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)


def page_chains(
    rows: tuple[SupplyChainRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyChainRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)


def page_bottlenecks(
    rows: tuple[SupplyBottleneckRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyBottleneckRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)


def page_locations(
    rows: tuple[SupplyLocationRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyLocationRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)


def page_organizations(
    rows: tuple[SupplyOrganizationRecord, ...] = (),
    *,
    after_key: str | None = None,
    limit: int = 100,
    window_index: int | None = None,
) -> tuple[tuple[SupplyOrganizationRecord, ...], str | None]:
    limit, window_index = _validate(limit, window_index)
    return _page(rows, after_key=after_key, limit=limit, window_index=window_index)
