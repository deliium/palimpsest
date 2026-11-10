"""Read-only trade-network HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_settings, get_trade_networks_reader
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from api.trade_networks_cursor import (
    TradeNetworksCursorCodec,
    TradeNetworksCursorError,
)
from api.trade_networks_schemas import (
    CrossSocietyPageOut,
    CrossSocietyTradeOut,
    DependencePageOut,
    TradeCorridorOut,
    TradeCorridorsPageOut,
    TradeDependenceOut,
    TradeFlowOut,
    TradeFlowsPageOut,
    TradeLocationOut,
    TradeLocationsPageOut,
    TradeNetworkOut,
    TradeNetworksPageOut,
    TradeNetworksSummaryOut,
)
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.trade_networks_paging import (
    MAX_PAGE_LIMIT,
    CrossSocietyTradeRowSelection,
    TradeCorridorRowSelection,
    TradeDependenceRowSelection,
    TradeFlowRowSelection,
    TradeLocationRowSelection,
    TradeNetworkRowSelection,
    page_cross_society_trades,
    page_trade_corridors,
    page_trade_dependence,
    page_trade_flows,
    page_trade_locations,
    page_trade_networks,
)
from simulation.trade_networks_ports import trade_networks_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["trade-networks"])
_LOGGER = get_logger("api.routes.trade_networks")
TRADE_NETWORKS_ROUTE_COUNT: Final[int] = 7


def _reader(reader: object | None) -> Any:
    if reader is None:
        _LOGGER.info("trade_networks_api_disabled")
        raise service_unavailable(code="trade_networks_disabled")
    return reader


def _codec(request: Request) -> TradeNetworksCursorCodec:
    codec = getattr(request.app.state, "trade_networks_cursor_codec", None)
    if not isinstance(codec, TradeNetworksCursorCodec):
        _LOGGER.info("trade_networks_api_disabled")
        raise service_unavailable(code="trade_networks_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "trade_networks_store_corrupt":
            _LOGGER.error("trade_networks_store_corrupt")
            raise internal(code="trade_networks_store_corrupt") from exc
        raise not_found(code="trade_networks_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="trade_networks_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="trade_networks_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    *,
    limit: int,
) -> str:
    return trade_networks_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
        after_key=None,
        limit=limit,
    )


def _after_key(
    codec: TradeNetworksCursorCodec,
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
    except TradeNetworksCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            _LOGGER.warning("trade_networks_cursor_expired")
            raise gone(code="trade_networks_cursor_expired") from exc
        _LOGGER.warning("trade_networks_cursor_invalid")
        raise bad_request(code="trade_networks_cursor_invalid") from exc
    expected = _fingerprint(snapshot, purpose, filters, limit=limit)
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != expected
    ):
        _LOGGER.warning("trade_networks_cursor_invalid")
        raise bad_request(code="trade_networks_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: TradeNetworksCursorCodec,
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
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose, filters, limit=limit),
        after_key=next_key,
    )


def _filters(window_index: int | None) -> dict[str, object]:
    return {} if window_index is None else {"window_index": window_index}


def _counts(row: Any) -> dict[str, int]:
    return {item.flow_class: item.count for item in row.flow_counts}


@router.get(
    "/{run_id}/trade-networks",
    response_model=TradeNetworksSummaryOut,
)
def get_trade_networks_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> TradeNetworksSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    _LOGGER.debug("trade_networks_api purpose=summary")
    return TradeNetworksSummaryOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        window_tick=summary.window_tick,
        corridor_count=summary.corridor_count,
        flow_count=summary.flow_count,
        location_count=summary.location_count,
        major_location_count=summary.major_location_count,
        trade_post_location_count=summary.trade_post_location_count,
        network_count=summary.network_count,
        cross_society_pair_count=summary.cross_society_pair_count,
        transfer_count=summary.transfer_count,
        emerged_count=summary.emerged_count,
        continued_count=summary.continued_count,
        transformed_count=summary.transformed_count,
        split_count=summary.split_count,
        merge_count=summary.merge_count,
        dissolved_count=summary.dissolved_count,
        rerouted_count=summary.rerouted_count,
        sustained_network_count=summary.sustained_network_count,
        lineage_edge_count=summary.lineage_edge_count,
        coverage=summary.coverage,
        truncated=summary.truncated,
    )


@router.get(
    "/{run_id}/trade-networks/corridors",
    response_model=TradeCorridorsPageOut,
)
def get_trade_networks_corridors(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> TradeCorridorsPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="corridors",
        filters=filters,
        limit=limit,
    )
    selection = page_trade_corridors(
        snapshot,
        TradeCorridorRowSelection(
            purpose="corridors",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return TradeCorridorsPageOut(
        items=[
            TradeCorridorOut(
                corridor_id=row.corridor_id,
                window_index=row.window_index,
                from_location_id=row.from_location_id,
                to_location_id=row.to_location_id,
                flow_counts=_counts(row),
                transfer_count=row.transfer_count,
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="corridors",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get("/{run_id}/trade-networks/flows", response_model=TradeFlowsPageOut)
def get_trade_networks_flows(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> TradeFlowsPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="flows",
        filters=filters,
        limit=limit,
    )
    selection = page_trade_flows(
        snapshot,
        TradeFlowRowSelection(
            purpose="flows",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return TradeFlowsPageOut(
        items=[
            TradeFlowOut(
                window_index=row.window_index,
                flow_class=row.flow_class,
                transfer_count=row.transfer_count,
                cross_location_count=row.cross_location_count,
                imported_count=row.imported_count,
                exported_count=row.exported_count,
                local_count=row.local_count,
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="flows",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/trade-networks/locations",
    response_model=TradeLocationsPageOut,
)
def get_trade_networks_locations(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> TradeLocationsPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="locations",
        filters=filters,
        limit=limit,
    )
    selection = page_trade_locations(
        snapshot,
        TradeLocationRowSelection(
            purpose="locations",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return TradeLocationsPageOut(
        items=[
            TradeLocationOut(
                location_id=row.location_id,
                window_index=row.window_index,
                inflow_count=row.inflow_count,
                outflow_count=row.outflow_count,
                local_count=row.local_count,
                corridor_degree=row.corridor_degree,
                is_major=row.is_major,
                trade_post_present=row.trade_post_present,
                flow_counts=_counts(row),
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="locations",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/trade-networks/dependence",
    response_model=DependencePageOut,
)
def get_trade_networks_dependence(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> DependencePageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="dependence",
        filters=filters,
        limit=limit,
    )
    selection = page_trade_dependence(
        snapshot,
        TradeDependenceRowSelection(
            purpose="dependence",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return DependencePageOut(
        items=[
            TradeDependenceOut(
                location_id=row.location_id,
                window_index=row.window_index,
                flow_class=row.flow_class,
                imported_count=row.imported_count,
                locally_originated_count=row.locally_originated_count,
                dependence_milli=row.dependence_milli,
                high_dependence=row.high_dependence,
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="dependence",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/trade-networks/cross-society",
    response_model=CrossSocietyPageOut,
)
def get_trade_networks_cross_society(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> CrossSocietyPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="cross-society",
        filters=filters,
        limit=limit,
    )
    selection = page_cross_society_trades(
        snapshot,
        CrossSocietyTradeRowSelection(
            purpose="cross-society",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return CrossSocietyPageOut(
        items=[
            CrossSocietyTradeOut(
                pair_id=row.pair_id,
                window_index=row.window_index,
                society_a=row.society_a,
                society_b=row.society_b,
                society_a_location_id=row.society_a_location_id,
                society_b_location_id=row.society_b_location_id,
                overlap_member_count=row.overlap_member_count,
                flow_counts=_counts(row),
                transfer_count=row.transfer_count,
                society_a_to_b_count=row.society_a_to_b_count,
                society_b_to_a_count=row.society_b_to_a_count,
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="cross-society",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/trade-networks/networks",
    response_model=TradeNetworksPageOut,
)
def get_trade_networks_networks(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_trade_networks_reader),
    settings: Settings = Depends(get_settings),
) -> TradeNetworksPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="networks",
        filters=filters,
        limit=limit,
    )
    selection = page_trade_networks(
        snapshot,
        TradeNetworkRowSelection(
            purpose="networks",
            after_key=after,
            limit=limit,
            window_index=window_index,
        ),
    )
    return TradeNetworksPageOut(
        items=[
            TradeNetworkOut(
                network_id=row.network_id,
                window_index=row.window_index,
                corridor_ids=list(row.corridor_ids),
                location_ids=list(row.location_ids),
                flow_counts=_counts(row),
                transfer_count=row.transfer_count,
                status=row.status,
                previous_network_ids=list(row.previous_network_ids),
                next_network_ids=list(row.next_network_ids),
                rerouted=row.rerouted,
                sustained=row.sustained,
                coverage=row.coverage,
            )
            for row in selection.rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="networks",
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )
