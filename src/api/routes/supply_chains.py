"""Read-only supply-chain HTTP routes (seven GET endpoints)."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_settings, get_supply_chain_reader
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from api.supply_chain_cursor import (
    SupplyChainCursorCodec,
    SupplyChainCursorError,
)
from api.supply_chain_schemas import (
    SupplyBottleneckOut,
    SupplyBottlenecksPageOut,
    SupplyChainOut,
    SupplyChainsPageOut,
    SupplyChainSummaryOut,
    SupplyDependenciesPageOut,
    SupplyDependencyOut,
    SupplyLocationOut,
    SupplyLocationsPageOut,
    SupplyOrganizationOut,
    SupplyOrganizationsPageOut,
    SupplyStageOut,
    SupplyStagesPageOut,
)
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.supply_chain_paging import (
    MAX_PAGE_LIMIT,
    page_bottlenecks,
    page_chains,
    page_dependencies,
    page_locations,
    page_organizations,
    page_stages,
)
from simulation.supply_chain_ports import supply_chain_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["supply-chains"])
_LOGGER = get_logger("api.routes.supply_chains")
SUPPLY_CHAIN_ROUTE_COUNT: Final[int] = 7


def _reader(reader: object | None) -> Any:
    if reader is None:
        _LOGGER.warning("supply_chains_disabled")
        raise service_unavailable(code="supply_chains_disabled")
    return reader


def _codec(request: Request) -> SupplyChainCursorCodec:
    codec = getattr(request.app.state, "supply_chain_cursor_codec", None)
    if not isinstance(codec, SupplyChainCursorCodec):
        _LOGGER.warning("supply_chains_disabled")
        raise service_unavailable(code="supply_chains_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if "corrupt" in str(exc):
            _LOGGER.error("supply_chains_store_corrupt")
            raise internal(code="supply_chains_store_corrupt") from exc
        raise not_found(code="supply_chains_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="supply_chains_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="supply_chains_run_not_found")
    return snapshot


def _filters(window_index: int | None) -> dict[str, object]:
    return {} if window_index is None else {"window_index": window_index}


def _fingerprint(
    snapshot: Any, purpose: str, filters: dict[str, object], *, limit: int
) -> str:
    return supply_chain_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
        after_key=None,
        limit=limit,
    )


def _after_key(
    codec: SupplyChainCursorCodec,
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
    except SupplyChainCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="supply_chains_cursor_expired") from exc
        raise bad_request(code="supply_chains_cursor_invalid") from exc
    expected = _fingerprint(snapshot, purpose, filters, limit=limit)
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint") != expected
    ):
        raise bad_request(code="supply_chains_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: SupplyChainCursorCodec,
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


@router.get("/{run_id}/supply-chains", response_model=SupplyChainSummaryOut)
def get_supply_chain_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyChainSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    _LOGGER.debug("supply_chain_api_route route=summary window_index=-")
    return SupplyChainSummaryOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        window_tick=summary.window_tick,
        stage_count=summary.stage_count,
        edge_count=summary.edge_count,
        chain_count=summary.chain_count,
        lineage_count=summary.lineage_count,
        bottleneck_count=summary.bottleneck_count,
        location_count=summary.location_count,
        organization_count=summary.organization_count,
        sustained_chain_count=summary.sustained_chain_count,
        max_depth=summary.max_depth,
        coverage=summary.coverage,
        truncated=summary.truncated,
    )


@router.get("/{run_id}/supply-chains/stages", response_model=SupplyStagesPageOut)
def get_supply_chain_stages(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyStagesPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="stages",
        filters=filters,
        limit=limit,
    )
    rows, next_key = page_stages(
        snapshot.stages,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyStagesPageOut(
        items=[
            SupplyStageOut(
                stage_token=row.stage_token,
                window_index=row.window_index,
                recipe_id=row.recipe_id,
                action=row.action,
                location_token=row.location_token,
                actor_token=row.actor_token,
                item_names=list(row.item_names),
                completed=row.completed,
                attempt=row.attempt,
                duration_ticks=row.duration_ticks,
                created_item_token=row.created_item_token,
                cause=row.cause,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="stages",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/supply-chains/dependencies",
    response_model=SupplyDependenciesPageOut,
)
def get_supply_chain_dependencies(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyDependenciesPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="dependencies",
        filters=filters,
        limit=limit,
    )
    rows, next_key = page_dependencies(
        snapshot.edges,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyDependenciesPageOut(
        items=[
            SupplyDependencyOut(
                edge_token=row.edge_token,
                window_index=row.window_index,
                from_kind=row.from_kind,
                from_token=row.from_token,
                to_kind=row.to_kind,
                to_token=row.to_token,
                edge_kind=row.edge_kind,
                recipe_id=row.recipe_id,
                observed_count=row.observed_count,
                completed_count=row.completed_count,
                share_milli=row.share_milli,
                created_elsewhere_count=row.created_elsewhere_count,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="dependencies",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get("/{run_id}/supply-chains/chains", response_model=SupplyChainsPageOut)
def get_supply_chain_chains(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyChainsPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="chains",
        filters=filters,
        limit=limit,
    )
    rows, next_key = page_chains(
        snapshot.chains,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyChainsPageOut(
        items=[
            SupplyChainOut(
                chain_token=row.chain_token,
                window_index=row.window_index,
                stage_tokens=list(row.stage_tokens),
                edge_tokens=list(row.edge_tokens),
                depth=row.depth,
                completed_count=row.completed_count,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="chains",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/supply-chains/bottlenecks",
    response_model=SupplyBottlenecksPageOut,
)
def get_supply_chain_bottlenecks(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyBottlenecksPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="bottlenecks",
        filters=filters,
        limit=limit,
    )
    rows, next_key = page_bottlenecks(
        snapshot.bottlenecks,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyBottlenecksPageOut(
        items=[
            SupplyBottleneckOut(
                bottleneck_token=row.bottleneck_token,
                window_index=row.window_index,
                kind=row.kind,
                stage_token=row.stage_token,
                edge_token=row.edge_token,
                observed_count=row.observed_count,
                demand_count=row.demand_count,
                supply_count=row.supply_count,
                ratio_milli=row.ratio_milli,
                location_token=row.location_token,
                organization_token=row.organization_token,
                skill_domain=row.skill_domain,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="bottlenecks",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/supply-chains/locations",
    response_model=SupplyLocationsPageOut,
)
def get_supply_chain_locations(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyLocationsPageOut:
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
    rows, next_key = page_locations(
        snapshot.locations,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyLocationsPageOut(
        items=[
            SupplyLocationOut(
                location_token=row.location_token,
                window_index=row.window_index,
                observed_count=row.observed_count,
                completed_count=row.completed_count,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="locations",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/supply-chains/organizations",
    response_model=SupplyOrganizationsPageOut,
)
def get_supply_chain_organizations(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    window_index: int | None = Query(default=None, ge=0, le=511),
    reader: object | None = Depends(get_supply_chain_reader),
    settings: Settings = Depends(get_settings),
) -> SupplyOrganizationsPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters = _filters(window_index)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose="organizations",
        filters=filters,
        limit=limit,
    )
    rows, next_key = page_organizations(
        snapshot.organizations,
        after_key=after,
        limit=limit,
        window_index=window_index,
    )
    return SupplyOrganizationsPageOut(
        items=[
            SupplyOrganizationOut(
                organization_token=row.organization_token,
                window_index=row.window_index,
                actor_count=row.actor_count,
                claim_count=row.claim_count,
                completed_count=row.completed_count,
                coverage=row.coverage,
            )
            for row in rows
        ],
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="organizations",
            filters=filters,
            limit=limit,
            next_key=next_key,
        ),
    )
