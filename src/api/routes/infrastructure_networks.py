"""Read-only infrastructure-networks HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_infrastructure_networks_reader, get_settings
from api.errors import (
    bad_request,
    gone,
    internal,
    not_found,
    service_unavailable,
)
from api.infrastructure_networks_cursor import (
    InfrastructureNetworksCursorCodec,
    InfrastructureNetworksCursorError,
)
from api.infrastructure_networks_schemas import (
    MAX_PAGE_LIMIT,
    InfrastructureAssetOut,
    InfrastructureAssetPageOut,
    InfrastructureNetworksSummaryOut,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.infrastructure_paging import (
    InfrastructureNetworksRowSelection,
    page_infrastructure_networks_rows,
)
from simulation.infrastructure_ports import infrastructure_networks_query_fingerprint

router = APIRouter(
    prefix="/v1/simulations",
    tags=["infrastructure-networks"],
)
_LOGGER = get_logger("api.routes.infrastructure_networks")
INFRASTRUCTURE_NETWORKS_ROUTE_COUNT: Final[int] = 6


def _reader(reader: object | None) -> Any:
    if reader is None:
        _LOGGER.info("infrastructure_networks_api_disabled")
        raise service_unavailable(code="infrastructure_networks_disabled")
    return reader


def _codec(request: Request) -> InfrastructureNetworksCursorCodec:
    codec = getattr(request.app.state, "infrastructure_networks_cursor_codec", None)
    if not isinstance(codec, InfrastructureNetworksCursorCodec):
        _LOGGER.info("infrastructure_networks_api_disabled")
        raise service_unavailable(code="infrastructure_networks_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "infrastructure_networks_store_corrupt":
            _LOGGER.error("infrastructure_networks_store_corrupt")
            raise internal(code="infrastructure_networks_store_corrupt") from exc
        raise not_found(code="infrastructure_networks_not_found") from exc
    except Exception as exc:
        raise not_found(code="infrastructure_networks_not_found") from exc
    if snapshot is None:
        raise not_found(code="infrastructure_networks_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    *,
    limit: int,
) -> str:
    return infrastructure_networks_query_fingerprint(
        run_id=snapshot.summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
        after_key=None,
        limit=limit,
    )


def _after_key(
    codec: InfrastructureNetworksCursorCodec,
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
    except InfrastructureNetworksCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            _LOGGER.warning("infrastructure_networks_cursor_expired")
            raise gone(code="infrastructure_networks_cursor_expired") from exc
        _LOGGER.warning("infrastructure_networks_cursor_invalid")
        raise bad_request(code="infrastructure_networks_cursor_invalid") from exc
    expected = _fingerprint(snapshot, purpose, filters, limit=limit)
    if (
        payload.get("run_id") != snapshot.summary.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != expected
    ):
        _LOGGER.warning("infrastructure_networks_cursor_invalid")
        raise bad_request(code="infrastructure_networks_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: InfrastructureNetworksCursorCodec,
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


def _asset(row: Any) -> InfrastructureAssetOut:
    return InfrastructureAssetOut(
        asset_id=row.asset_id,
        kind=row.kind,
        topology=row.topology,
        status=row.status,
        integrity=row.integrity,
        location_id=row.location_id,
        endpoint_location_id=row.endpoint_location_id,
        effects_active=row.effects_active,
        created_tick=row.created_tick,
        last_maintained_tick=row.last_maintained_tick,
        ticks_since_maintained=row.ticks_since_maintained,
        linked_project_id=row.linked_project_id,
        linked_structure_id=row.linked_structure_id,
    )


def _page(
    *,
    request: Request,
    run_id: str,
    purpose: str,
    cursor: str | None,
    limit: int,
    reader: object | None,
    settings: Settings,
) -> InfrastructureAssetPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose=purpose,
        filters=filters,
        limit=limit,
    )
    selection = page_infrastructure_networks_rows(
        snapshot,
        InfrastructureNetworksRowSelection(
            purpose=purpose, after_key=after, limit=limit
        ),
    )
    _LOGGER.debug(
        "infrastructure_networks_api purpose=%s rows=%s", purpose, len(selection.rows)
    )
    return InfrastructureAssetPageOut(
        items=tuple(_asset(row) for row in selection.rows),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose=purpose,
            filters=filters,
            limit=limit,
            next_key=selection.next_key,
        ),
    )


@router.get(
    "/{run_id}/infrastructure-networks",
    response_model=InfrastructureNetworksSummaryOut,
)
def get_infrastructure_networks_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureNetworksSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    _LOGGER.debug("infrastructure_networks_api purpose=summary")
    return InfrastructureNetworksSummaryOut(
        run_id=summary.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        asset_count=summary.asset_count,
        node_count=summary.node_count,
        edge_count=summary.edge_count,
        operational_count=summary.operational_count,
        damaged_count=summary.damaged_count,
        destroyed_count=summary.destroyed_count,
        effects_active_count=summary.effects_active_count,
        coverage=summary.coverage,
    )


@router.get(
    "/{run_id}/infrastructure-networks/assets",
    response_model=InfrastructureAssetPageOut,
)
def get_infrastructure_networks_assets(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureAssetPageOut:
    return _page(
        request=request,
        run_id=run_id,
        purpose="assets",
        cursor=cursor,
        limit=limit,
        reader=reader,
        settings=settings,
    )


@router.get(
    "/{run_id}/infrastructure-networks/edges",
    response_model=InfrastructureAssetPageOut,
)
def get_infrastructure_networks_edges(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureAssetPageOut:
    return _page(
        request=request,
        run_id=run_id,
        purpose="edges",
        cursor=cursor,
        limit=limit,
        reader=reader,
        settings=settings,
    )


@router.get(
    "/{run_id}/infrastructure-networks/condition",
    response_model=InfrastructureAssetPageOut,
)
def get_infrastructure_networks_condition(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureAssetPageOut:
    return _page(
        request=request,
        run_id=run_id,
        purpose="condition",
        cursor=cursor,
        limit=limit,
        reader=reader,
        settings=settings,
    )


@router.get(
    "/{run_id}/infrastructure-networks/effects",
    response_model=InfrastructureAssetPageOut,
)
def get_infrastructure_networks_effects(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureAssetPageOut:
    return _page(
        request=request,
        run_id=run_id,
        purpose="effects",
        cursor=cursor,
        limit=limit,
        reader=reader,
        settings=settings,
    )


@router.get(
    "/{run_id}/infrastructure-networks/maintenance",
    response_model=InfrastructureAssetPageOut,
)
def get_infrastructure_networks_maintenance(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_infrastructure_networks_reader),
    settings: Settings = Depends(get_settings),
) -> InfrastructureAssetPageOut:
    return _page(
        request=request,
        run_id=run_id,
        purpose="maintenance",
        cursor=cursor,
        limit=limit,
        reader=reader,
        settings=settings,
    )
