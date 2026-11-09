"""Read-only inter-society-relations HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_inter_society_relations_reader, get_settings
from api.errors import (
    bad_request,
    gone,
    internal,
    not_found,
    service_unavailable,
)
from api.inter_society_relations_cursor import (
    InterSocietyRelationsCursorCodec,
    InterSocietyRelationsCursorError,
)
from api.inter_society_relations_schemas import (
    MAX_PAGE_LIMIT,
    InterSocietyComparisonOut,
    InterSocietyDomainDeltaOut,
    InterSocietyDomainPanelOut,
    InterSocietyPairOut,
    InterSocietyPairPageOut,
    InterSocietyRelationsSummaryOut,
    InterSocietySeriesPageOut,
    InterSocietySeriesPointOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.inter_society_relations_paging import (
    InterSocietyRelationsRowSelection,
    page_inter_society_relations_detail,
    page_inter_society_relations_rows,
)
from simulation.inter_society_relations_ports import (
    inter_society_relations_query_fingerprint,
)

router = APIRouter(
    prefix="/v1/simulations",
    tags=["inter-society-relations"],
)
_LOGGER = get_logger("api.routes.inter_society_relations")
INTER_SOCIETY_RELATIONS_ROUTE_COUNT: Final[int] = 6

_DOMAIN_ORDER: Final[tuple[str, ...]] = (
    "agreement",
    "conflict",
    "cooperation",
    "cultural_similarity",
    "exchange",
    "hostility",
    "migration",
    "trust_proxy",
)


def _reader(reader: object | None) -> Any:
    if reader is None:
        _LOGGER.info("inter_society_relations_api_disabled")
        raise service_unavailable(code="inter_society_relations_disabled")
    return reader


def _codec(request: Request) -> InterSocietyRelationsCursorCodec:
    codec = getattr(request.app.state, "inter_society_relations_cursor_codec", None)
    if not isinstance(codec, InterSocietyRelationsCursorCodec):
        _LOGGER.info("inter_society_relations_api_disabled")
        raise service_unavailable(code="inter_society_relations_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "inter_society_relations_store_corrupt":
            _LOGGER.error("inter_society_relations_store_corrupt")
            raise internal(code="inter_society_relations_store_corrupt") from exc
        raise not_found(code="inter_society_relations_not_found") from exc
    except Exception as exc:
        raise not_found(code="inter_society_relations_not_found") from exc
    if snapshot is None:
        raise not_found(code="inter_society_relations_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    *,
    limit: int,
) -> str:
    return inter_society_relations_query_fingerprint(
        run_id=snapshot.summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
        after_key=None,
        limit=limit,
    )


def _after_key(
    codec: InterSocietyRelationsCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    limit: int,
) -> str | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except InterSocietyRelationsCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            _LOGGER.warning("inter_society_relations_cursor_expired")
            raise gone(code="inter_society_relations_cursor_expired") from exc
        _LOGGER.warning("inter_society_relations_cursor_invalid")
        raise bad_request(code="inter_society_relations_cursor_invalid") from exc
    expected = _fingerprint(snapshot, purpose, filters, limit=limit)
    if (
        payload.get("run_id") != snapshot.summary.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != expected
    ):
        _LOGGER.warning("inter_society_relations_cursor_invalid")
        raise bad_request(code="inter_society_relations_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: InterSocietyRelationsCursorCodec,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    limit: int,
    next_key: str | None,
) -> str | None:
    if next_key is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=snapshot.summary.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose, filters, limit=limit),
        after_key=next_key,
    )


def _panel(row: Any) -> InterSocietyDomainPanelOut:
    return InterSocietyDomainPanelOut(
        domain=row.domain,
        event_count=row.event_count,
        availability=row.availability,
        coverage_observed=row.coverage_observed,
        coverage_expected=row.coverage_expected,
        values=dict(row.values),
    )


def _pair(row: Any) -> InterSocietyPairOut:
    return InterSocietyPairOut(
        pair_id=row.pair_id,
        society_a=row.society_a,
        society_b=row.society_b,
        window_tick=row.window_tick,
        status=row.status,
        overlap_member_count=row.overlap_member_count,
        panels=tuple(_panel(panel) for panel in row.panels),
    )


def _series_point(row: Any) -> InterSocietySeriesPointOut:
    return InterSocietySeriesPointOut(
        pair_id=row.pair_id,
        window_index=row.window_index,
        window_start_tick=row.window_start_tick,
        window_end_tick=row.window_end_tick,
        panels=tuple(_panel(panel) for panel in row.panels),
    )


def _panel_map(panels: tuple[Any, ...]) -> dict[str, Any]:
    return {panel.domain: panel for panel in panels}


def _domain_deltas(
    left_panels: tuple[Any, ...], right_panels: tuple[Any, ...]
) -> tuple[InterSocietyDomainDeltaOut, ...]:
    left = _panel_map(left_panels)
    right = _panel_map(right_panels)
    deltas: list[InterSocietyDomainDeltaOut] = []
    for domain in _DOMAIN_ORDER:
        left_panel = left.get(domain)
        right_panel = right.get(domain)
        left_count = 0 if left_panel is None else int(left_panel.event_count)
        right_count = 0 if right_panel is None else int(right_panel.event_count)
        left_av = "absent" if left_panel is None else str(left_panel.availability)
        right_av = "absent" if right_panel is None else str(right_panel.availability)
        deltas.append(
            InterSocietyDomainDeltaOut(
                domain=domain,
                count_delta=right_count - left_count,
                left_availability=left_av,
                right_availability=right_av,
            )
        )
    return tuple(deltas)


def _find_pair(snapshot: Any, pair_id: str) -> Any | None:
    for pair in snapshot.pairs:
        if pair.pair_id == pair_id:
            return pair
    return None


def _pair_societies(snapshot: Any, pair_id: str) -> tuple[str, str] | None:
    pair = _find_pair(snapshot, pair_id)
    if pair is not None:
        return pair.society_a, pair.society_b
    for point in snapshot.series_points:
        if point.pair_id != pair_id:
            continue
        for candidate in snapshot.pairs:
            if candidate.pair_id == point.pair_id:
                return candidate.society_a, candidate.society_b
        # Fall back to same-society series siblings via shared pair_id only.
        return None
    return None


def _series_points_for_pair(snapshot: Any, pair_id: str) -> tuple[Any, ...]:
    societies = _pair_societies(snapshot, pair_id)
    if societies is None:
        return tuple(
            point for point in snapshot.series_points if point.pair_id == pair_id
        )
    society_a, society_b = societies
    related_ids = {
        pair.pair_id
        for pair in snapshot.pairs
        if pair.society_a == society_a and pair.society_b == society_b
    }
    related_ids.add(pair_id)
    return tuple(
        point for point in snapshot.series_points if point.pair_id in related_ids
    )


def _find_series_point(snapshot: Any, pair_id: str, window_tick: int) -> Any | None:
    for point in _series_points_for_pair(snapshot, pair_id):
        if point.window_start_tick <= window_tick <= point.window_end_tick:
            return point
        if point.window_index == window_tick:
            return point
        if point.window_start_tick == window_tick:
            return point
    return None


@router.get(
    "/{run_id}/inter-society-relations",
    response_model=InterSocietyRelationsSummaryOut,
)
def get_inter_society_relations_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietyRelationsSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    _LOGGER.debug("inter_society_relations_api purpose=summary")
    return InterSocietyRelationsSummaryOut(
        run_id=summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        pair_count=summary.pair_count,
        window_count=summary.window_count,
        series_point_count=summary.series_point_count,
        comparison_count=summary.comparison_count,
        coverage=summary.coverage,
    )


@router.get(
    "/{run_id}/inter-society-relations/pairs",
    response_model=InterSocietyPairPageOut,
)
def get_inter_society_relations_pairs(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietyPairPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="pairs",
        filters=filters,
        limit=limit,
    )
    selection = page_inter_society_relations_rows(
        snapshot,
        InterSocietyRelationsRowSelection(
            purpose="pairs", after_key=after, limit=limit
        ),
    )
    _LOGGER.debug(
        "inter_society_relations_api purpose=pairs rows=%s", len(selection.rows)
    )
    return InterSocietyPairPageOut(
        items=tuple(_pair(row) for row in selection.rows),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="pairs",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/inter-society-relations/pairs/{pair_id}",
    response_model=InterSocietyPairOut,
)
def get_inter_society_relations_pair(
    run_id: str,
    pair_id: str,
    request: Request,
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietyPairOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    row = page_inter_society_relations_detail(snapshot, "pair", pair_id)
    if row is None:
        raise not_found(code="inter_society_relations_not_found")
    _LOGGER.debug("inter_society_relations_api purpose=pair")
    return _pair(row)


@router.get(
    "/{run_id}/inter-society-relations/pairs/{pair_id}/series",
    response_model=InterSocietySeriesPageOut,
)
def get_inter_society_relations_pair_series(
    run_id: str,
    pair_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietySeriesPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    related = _series_points_for_pair(snapshot, pair_id)
    if _find_pair(snapshot, pair_id) is None and not related:
        raise not_found(code="inter_society_relations_not_found")
    codec = _codec(request)
    filters: dict[str, object] = {"pair_id": pair_id}
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="series",
        filters=filters,
        limit=limit,
    )
    ordered = sorted(
        related,
        key=lambda row: (row.window_index, row.pair_id),
    )
    if after is not None:
        ordered = [
            row for row in ordered if f"{row.window_index:020d}|{row.pair_id}" > after
        ]
    page = tuple(ordered[: max(1, min(limit, MAX_PAGE_LIMIT))])
    next_key = (
        f"{page[-1].window_index:020d}|{page[-1].pair_id}"
        if len(ordered) > len(page) and page
        else None
    )
    _LOGGER.debug("inter_society_relations_api purpose=series rows=%s", len(page))
    return InterSocietySeriesPageOut(
        items=tuple(_series_point(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="series",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/inter-society-relations/comparison",
    response_model=InterSocietyComparisonOut,
)
def get_inter_society_relations_comparison(
    run_id: str,
    request: Request,
    pair_a: str | None = Query(default=None),
    pair_b: str | None = Query(default=None),
    pair_id: str | None = Query(default=None),
    window_a: int | None = Query(default=None),
    window_b: int | None = Query(default=None),
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietyComparisonOut:
    _authorize(request, settings)
    pair_mode = pair_a is not None or pair_b is not None
    window_mode = pair_id is not None or window_a is not None or window_b is not None
    if pair_mode and window_mode:
        raise bad_request(code="inter_society_relations_comparison_invalid")
    if pair_mode:
        if pair_a is None or pair_b is None:
            raise bad_request(code="inter_society_relations_comparison_invalid")
    elif window_mode:
        if pair_id is None or window_a is None or window_b is None:
            raise bad_request(code="inter_society_relations_comparison_invalid")
    else:
        raise bad_request(code="inter_society_relations_comparison_invalid")

    snapshot = _snapshot(_reader(reader), run_id)
    _LOGGER.debug("inter_society_relations_api purpose=comparison")
    if pair_mode:
        left = _find_pair(snapshot, pair_a)  # type: ignore[arg-type]
        right = _find_pair(snapshot, pair_b)  # type: ignore[arg-type]
        if left is None or right is None:
            raise not_found(code="inter_society_relations_not_found")
        return InterSocietyComparisonOut(
            left_pair_id=left.pair_id,
            right_pair_id=right.pair_id,
            left_window_tick=left.window_tick,
            right_window_tick=right.window_tick,
            domain_deltas=_domain_deltas(left.panels, right.panels),
        )

    left_point = _find_series_point(snapshot, pair_id, window_a)  # type: ignore[arg-type]
    right_point = _find_series_point(snapshot, pair_id, window_b)  # type: ignore[arg-type]
    if left_point is None or right_point is None:
        raise not_found(code="inter_society_relations_not_found")
    return InterSocietyComparisonOut(
        left_pair_id=left_point.pair_id,
        right_pair_id=right_point.pair_id,
        left_window_tick=left_point.window_start_tick,
        right_window_tick=right_point.window_start_tick,
        domain_deltas=_domain_deltas(left_point.panels, right_point.panels),
    )


@router.get(
    "/{run_id}/inter-society-relations/windows",
    response_model=InterSocietySeriesPageOut,
)
def get_inter_society_relations_windows(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_inter_society_relations_reader),
    settings: Settings = Depends(get_settings),
) -> InterSocietySeriesPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="windows",
        filters=filters,
        limit=limit,
    )
    selection = page_inter_society_relations_rows(
        snapshot,
        InterSocietyRelationsRowSelection(
            purpose="windows", after_key=after, limit=limit
        ),
    )
    _LOGGER.debug(
        "inter_society_relations_api purpose=windows rows=%s", len(selection.rows)
    )
    return InterSocietySeriesPageOut(
        items=tuple(_series_point(row) for row in selection.rows),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="windows",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )
