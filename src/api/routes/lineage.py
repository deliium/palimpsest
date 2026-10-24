"""Read-only historical lineage explorer HTTP routes."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse

from api.dependencies import get_lineage_service, get_settings
from api.errors import ApiError, bad_request, gone, not_found, service_unavailable
from api.lineage_cursor import LineageCursorCodec
from api.lineage_schemas import (
    LineageAvailabilityOut,
    LineageCoverageOut,
    LineageEdgeOut,
    LineageEvidenceRefOut,
    LineageFamilyOut,
    LineageGraphOut,
    LineageNodeListOut,
    LineageNodeOut,
    LineageNodeRefOut,
    LineageSnapshotListOut,
    LineageSnapshotOut,
)
from api.lineage_service import LineageApiService, node_filter_fingerprint
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageCoverage,
    LineageDirection,
    LineageEdge,
    LineageError,
    LineageNode,
    LineageQuery,
    LineageScope,
    LineageSnapshotRef,
)
from simulation.lineage_ports import MAX_RESPONSE_BYTES, lineage_query_fingerprint
from simulation.models import RunId

router = APIRouter(prefix="/v1/simulations", tags=["lineage"])
_LOGGER = get_logger("api.routes.lineage")

_OBJECTIVE_FAMILIES = {LineageFamily.GENEALOGY, LineageFamily.RECORD}


def _require_service(service: LineageApiService | None) -> LineageApiService:
    if service is None:
        raise service_unavailable(code="lineage_disabled")
    return service


def _scope(
    run_id: str, family: str, evidence_class: str, owner_id: str | None
) -> LineageScope:
    try:
        return LineageScope(
            run_id=RunId(run_id),
            family=LineageFamily(family),
            evidence_class=LineageEvidenceClass(evidence_class),
            owner_id=owner_id,
        )
    except (ValueError, LineageError) as exc:
        raise bad_request(code="invalid_lineage_scope") from exc


def _reject_unknown(request: Request, allowed: set[str]) -> None:
    unknown = set(request.query_params.keys()) - allowed
    if unknown:
        raise bad_request(code="invalid_lineage_query")
    seen: set[str] = set()
    for key, _value in request.query_params.multi_items():
        if key in seen:
            raise bad_request(code="invalid_lineage_query")
        seen.add(key)


def _enforce_response_bytes(model: object) -> None:
    dump = getattr(model, "model_dump_json", None)
    if dump is None:
        return
    if len(dump().encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise service_unavailable(code="lineage_response_too_large")


def _availability_response(
    scope: LineageScope, boundary_tick: int | None
) -> JSONResponse:
    payload = LineageAvailabilityOut(
        schema_version="lineage-availability-v1",
        availability="unavailable",
        reason_code="snapshot_unavailable",
        family=scope.family.value,
        evidence_class=scope.evidence_class.value,
        requested_boundary_tick=boundary_tick,
        captured_boundary_tick=None,
    )
    return JSONResponse(
        status_code=200,
        content=payload.model_dump(),
        headers={"Cache-Control": "no-store"},
    )


def _authorize(request: Request, settings: Settings, scope: LineageScope) -> None:
    capability = (
        ApiCapability.OBJECTIVE_INSPECTION
        if scope.family in _OBJECTIVE_FAMILIES
        and scope.evidence_class is LineageEvidenceClass.OBJECTIVE
        else ApiCapability.SUBJECTIVE_DEBUG
    )
    require_http_capability(request, settings, capability=capability)


def _map_error(exc: LineageError, *, run_id: str | None = None) -> ApiError:
    code = exc.code
    if code == "lineage_run_not_found":
        return not_found(code=code, run_id=run_id)
    if code == "lineage_root_not_found":
        return not_found(code=code, run_id=run_id)
    if code in {
        "lineage_cursor_expired",
        "lineage_snapshot_gone",
        "snapshot_unavailable",
    }:
        return gone(code=code, run_id=run_id)
    if code in {
        "lineage_snapshot_corrupt",
        "snapshot_corrupt",
        "lineage_digest_mismatch",
        "lineage_identity_conflict",
        "lineage_record_oversize",
        "lineage_storage_unavailable",
        "lineage_source_budget",
        "lineage_response_too_large",
    }:
        return service_unavailable(code=code)
    return bad_request(code=code, run_id=run_id)


def _snapshot_out(ref: LineageSnapshotRef) -> LineageSnapshotOut:
    return LineageSnapshotOut(
        publication_id=ref.publication_id,
        digest=ref.digest,
        boundary_tick=ref.boundary_tick,
        schema_version=ref.schema_version,
    )


def _coverage_out(coverage: LineageCoverage) -> LineageCoverageOut:
    return LineageCoverageOut(
        state=coverage.state.value,
        reason_codes=list(coverage.reason_codes),
        capture_start_tick=coverage.capture_start_tick,
        capture_end_tick=coverage.capture_end_tick,
        missing_prefix_tick=coverage.missing_prefix_tick,
        pruned_count=coverage.pruned_count,
        unresolved_count=coverage.unresolved_count,
        policy_version=coverage.policy_version,
    )


def _evidence_out(ref: LineageEvidenceRef) -> LineageEvidenceRefOut:
    return LineageEvidenceRefOut(
        evidence_class=ref.evidence_class.value,
        native_kind=ref.native_kind.value,
        native_id=ref.native_id,
        owner_id=ref.owner_id,
        observed_tick=ref.observed_tick,
    )


def _ref_out(ref: LineageNodeRef) -> LineageNodeRefOut:
    return LineageNodeRefOut(
        run_id=ref.run_id.value,
        family=ref.family.value,
        evidence_class=ref.evidence_class.value,
        native_kind=ref.native_kind.value,
        native_id=ref.native_id,
        identity_owner=ref.identity_owner,
        key=ref.key,
    )


def _node_out(node: LineageNode) -> LineageNodeOut:
    return LineageNodeOut(
        ref=_ref_out(node.ref),
        state=node.state.value,
        living=node.living,
        observed_tick=node.observed_tick,
        status_code=node.status_code,
        confidence_code=node.confidence_code,
        confidence_value=node.confidence_value,
        unresolved_reason=node.unresolved_reason,
        native_revision=node.native_revision,
        evidence_refs=[_evidence_out(item) for item in node.evidence_refs],
        counts=dict(node.counts),
        source_observed_boundary=node.source_observed_boundary,
    )


def _edge_out(edge: LineageEdge) -> LineageEdgeOut:
    return LineageEdgeOut(
        edge_key=edge.edge_key,
        source_key=edge.source_key,
        target_key=edge.target_key,
        relation=edge.relation,
        native_kind=edge.native_kind.value,
        native_id=edge.native_id,
        claim_owner_id=edge.claim_owner_id,
        observed_tick=edge.observed_tick,
        status_code=edge.status_code,
        confidence_code=edge.confidence_code,
        confidence_value=edge.confidence_value,
        source_presence=edge.source_presence,
        evidence_refs=[_evidence_out(item) for item in edge.evidence_refs],
        counts=dict(edge.counts),
    )


def _native_filter(
    native_kind: str | None, native_id: str | None
) -> tuple[LineageNativeKind | None, str | None]:
    if (native_kind is None) != (native_id is None):
        raise bad_request(code="invalid_native_filter")
    if native_kind is None:
        return None, None
    try:
        return LineageNativeKind(native_kind), native_id
    except ValueError as exc:
        raise bad_request(code="invalid_native_kind") from exc


@router.get("/{run_id}/lineage/families", response_model=list[LineageFamilyOut])
async def lineage_families(
    run_id: str,
    request: Request,
    response: Response,
    include_restricted: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    service: LineageApiService | None = Depends(get_lineage_service),
) -> list[LineageFamilyOut]:
    response.headers["Cache-Control"] = "no-store"
    _reject_unknown(request, {"include_restricted"})
    if include_restricted:
        require_http_capability(
            request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
        )
    else:
        require_http_capability(
            request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
        )
    descriptors = _require_service(service).families()
    if not include_restricted:
        descriptors = tuple(
            item
            for item in descriptors
            if item.available_classes == (LineageEvidenceClass.OBJECTIVE,)
        )
    return [
        LineageFamilyOut(
            family=item.family.value,
            available_classes=[value.value for value in item.available_classes],
            owner_required=item.owner_required,
            directions=[value.value for value in item.directions],
            max_depth=item.max_depth,
            max_nodes=item.max_nodes,
            max_edges=item.max_edges,
            max_page_size=item.max_page_size,
        )
        for item in descriptors
    ]


@router.get(
    "/{run_id}/lineage/{family}/snapshots", response_model=LineageSnapshotListOut
)
async def lineage_snapshots(
    run_id: str,
    family: str,
    request: Request,
    response: Response,
    evidence_class: str = Query(...),
    owner_id: str | None = Query(default=None),
    after: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    settings: Settings = Depends(get_settings),
    service: LineageApiService | None = Depends(get_lineage_service),
) -> LineageSnapshotListOut:
    response.headers["Cache-Control"] = "no-store"
    _reject_unknown(
        request,
        {"evidence_class", "owner_id", "after", "limit"},
    )
    scope = _scope(run_id, family, evidence_class, owner_id)
    _authorize(request, settings, scope)
    service = _require_service(service)
    codec: LineageCursorCodec = request.app.state.lineage_cursor_codec
    catalogue_ref = None
    boundary_after = after
    if after is not None:
        try:
            payload = codec.decode(after, purpose="snapshots", scope=scope)
        except LineageError as exc:
            raise _map_error(exc, run_id=run_id) from exc
        if payload.page_size != limit:
            raise bad_request(code="invalid_lineage_cursor", run_id=run_id)
        catalogue_ref = payload.run_commit_ref
        boundary_after = (
            f"{payload.last_boundary_key}:{payload.last_publication_id or ''}"
        )
    try:
        page, commit_ref = await service.snapshots(
            scope, after=boundary_after, limit=limit, catalogue_ref=catalogue_ref
        )
    except LineageError as exc:
        raise _map_error(exc, run_id=run_id) from exc
    next_cursor = None
    if page.continuation is not None and page.rows:
        last = page.rows[-1]
        next_cursor = codec.encode_snapshots(
            scope,
            run_commit_ref=commit_ref,
            catalogue_generation=commit_ref,
            last_boundary_key=last.boundary_tick,
            last_publication_id=last.publication_id,
            page_size=limit,
        )
    model = LineageSnapshotListOut(
        schema_version="lineage-snapshot-list-v1",
        items=[_snapshot_out(item) for item in page.rows],
        declared_count=page.declared_count,
        next_cursor=next_cursor,
    )
    _enforce_response_bytes(model)
    return model


@router.get("/{run_id}/lineage/{family}/nodes", response_model=LineageNodeListOut)
async def lineage_nodes(
    run_id: str,
    family: str,
    request: Request,
    response: Response,
    evidence_class: str = Query(...),
    owner_id: str | None = Query(default=None),
    boundary_tick: int | None = Query(default=None, ge=0),
    native_kind: str | None = Query(default=None),
    native_id: str | None = Query(default=None),
    after: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    settings: Settings = Depends(get_settings),
    service: LineageApiService | None = Depends(get_lineage_service),
) -> LineageNodeListOut | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    _reject_unknown(
        request,
        {
            "evidence_class",
            "owner_id",
            "boundary_tick",
            "native_kind",
            "native_id",
            "after",
            "limit",
        },
    )
    scope = _scope(run_id, family, evidence_class, owner_id)
    _authorize(request, settings, scope)
    service = _require_service(service)
    kind, identifier = _native_filter(native_kind, native_id)
    codec: LineageCursorCodec = request.app.state.lineage_cursor_codec
    snapshot = None
    catalogue_ref = None
    node_after = after
    filter_fp = node_filter_fingerprint(kind, identifier)
    if after is not None:
        try:
            payload = codec.decode(after, purpose="nodes", scope=scope)
        except LineageError as exc:
            raise _map_error(exc, run_id=run_id) from exc
        if payload.filter_fingerprint != filter_fp or payload.page_size != limit:
            raise bad_request(code="invalid_lineage_cursor", run_id=run_id)
        if (
            boundary_tick is not None
            and boundary_tick != payload.snapshot_boundary_tick
        ):
            raise bad_request(code="invalid_lineage_cursor", run_id=run_id)
        snapshot = LineageSnapshotRef(
            publication_id=payload.snapshot_id or "",
            digest=payload.snapshot_digest or "",
            boundary_tick=payload.snapshot_boundary_tick or 0,
        )
        node_after = payload.last_node_key
    try:
        page, resolved, _commit_ref = await service.nodes(
            scope,
            snapshot=snapshot,
            boundary_tick=boundary_tick,
            after=node_after,
            limit=limit,
            native_kind=kind,
            native_id=identifier,
            catalogue_ref=catalogue_ref,
        )
    except LineageError as exc:
        if (
            exc.code == "snapshot_unavailable"
            and after is None
            and boundary_tick is not None
        ):
            return _availability_response(scope, boundary_tick)
        raise _map_error(exc, run_id=run_id) from exc
    next_cursor = None
    if page.continuation is not None and page.rows:
        next_cursor = codec.encode_nodes(
            scope,
            snapshot_id=resolved.publication_id,
            snapshot_digest=resolved.digest,
            snapshot_boundary_tick=resolved.boundary_tick,
            filter_fingerprint=filter_fp,
            last_node_key=page.rows[-1].key,
            page_size=limit,
        )
    model = LineageNodeListOut(
        schema_version="lineage-node-list-v1",
        snapshot=_snapshot_out(resolved),
        items=[_node_out(item) for item in page.rows],
        matched_node_keys=[item.key for item in page.rows],
        context_only_node_keys=[],
        declared_count=page.declared_count,
        next_cursor=next_cursor,
        coverage=_coverage_out(
            page.coverage
            if page.coverage is not None
            else LineageCoverage(
                state=__import__(
                    "simulation.lineage_models", fromlist=["LineageCoverageState"]
                ).LineageCoverageState.COMPLETE,
                capture_end_tick=resolved.boundary_tick,
            )
        ),
        requested_boundary_tick=boundary_tick,
        captured_boundary_tick=resolved.boundary_tick,
        effective_page_size=limit,
    )
    _enforce_response_bytes(model)
    return model


@router.get("/{run_id}/lineage/{family}/traverse", response_model=LineageGraphOut)
async def lineage_traverse(
    run_id: str,
    family: str,
    request: Request,
    response: Response,
    evidence_class: str = Query(...),
    owner_id: str | None = Query(default=None),
    root_key: str = Query(...),
    direction: str = Query(default="both"),
    boundary_tick: int | None = Query(default=None, ge=0),
    max_depth: int = Query(default=4, ge=0, le=32),
    max_nodes: int = Query(default=200, ge=1, le=1000),
    max_edges: int = Query(default=500, ge=1, le=4000),
    living_only: bool = Query(default=False),
    after: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    settings: Settings = Depends(get_settings),
    service: LineageApiService | None = Depends(get_lineage_service),
) -> LineageGraphOut | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    _reject_unknown(
        request,
        {
            "evidence_class",
            "owner_id",
            "root_key",
            "direction",
            "boundary_tick",
            "max_depth",
            "max_nodes",
            "max_edges",
            "living_only",
            "after",
            "limit",
        },
    )
    started = time.perf_counter()
    scope = _scope(run_id, family, evidence_class, owner_id)
    _authorize(request, settings, scope)
    service = _require_service(service)
    codec: LineageCursorCodec = request.app.state.lineage_cursor_codec
    payload = None
    pinned_boundary = boundary_tick
    if after is not None:
        try:
            payload = codec.decode(after, purpose="traverse", scope=scope)
        except LineageError as exc:
            raise _map_error(exc, run_id=run_id) from exc
        pinned_boundary = payload.snapshot_boundary_tick
        if boundary_tick is not None and boundary_tick != pinned_boundary:
            raise bad_request(code="invalid_lineage_cursor", run_id=run_id)
    try:
        snapshot, root_node, page = await service.traverse_scope(
            scope,
            boundary_tick=pinned_boundary,
            root_key=root_key,
            direction=direction,
            max_depth=max_depth,
            max_nodes=max_nodes,
            max_edges=max_edges,
            living_only=living_only,
            page_size=limit,
            record_offset=payload.record_offset or 0 if payload is not None else 0,
        )
    except LineageError as exc:
        if (
            exc.code == "snapshot_unavailable"
            and after is None
            and boundary_tick is not None
        ):
            return _availability_response(scope, boundary_tick)
        raise _map_error(exc, run_id=run_id) from exc
    if root_node is None or page is None:
        raise not_found(code="lineage_root_not_found", run_id=run_id)
    query = LineageQuery(
        scope=scope,
        snapshot=snapshot,
        root=root_node.ref,
        direction=LineageDirection(direction),
        max_depth=max_depth,
        max_nodes=max_nodes,
        max_edges=max_edges,
        living_only=living_only,
        page_size=limit,
    )
    if payload is not None:
        if (
            payload.root_key != root_key
            or payload.query_fingerprint != lineage_query_fingerprint(query)
            or payload.snapshot_id != snapshot.publication_id
            or payload.snapshot_digest != snapshot.digest
        ):
            raise bad_request(code="invalid_lineage_cursor", run_id=run_id)
    next_cursor = None
    if page.continuation is not None:
        next_cursor = codec.encode_traverse(
            scope,
            snapshot_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            snapshot_boundary_tick=snapshot.boundary_tick,
            root_key=root_key,
            query_fingerprint=lineage_query_fingerprint(query),
            record_offset=int(page.continuation),
        )
    _LOGGER.info(
        "route_lineage_traverse",
        route_template="GET /v1/simulations/{run_id}/lineage/{family}/traverse",
        status=200,
        family=scope.family.value,
        evidence_class=scope.evidence_class.value,
        node_count=len(page.nodes),
        edge_count=len(page.edges),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
    )
    model = LineageGraphOut(
        schema_version="lineage-graph-page-v1",
        root=_ref_out(page.root),
        snapshot=_snapshot_out(page.snapshot),
        nodes=[_node_out(item) for item in page.nodes],
        edges=[_edge_out(item) for item in page.edges],
        matched_node_keys=list(page.matched_node_keys),
        context_only_node_keys=list(page.context_only_node_keys),
        visited_node_count=page.visited_node_count,
        visited_edge_count=page.visited_edge_count,
        stop_reasons=list(page.stop_reasons),
        coverage=_coverage_out(page.coverage),
        next_cursor=next_cursor,
        requested_boundary_tick=boundary_tick,
        captured_boundary_tick=page.snapshot.boundary_tick,
        effective_max_depth=max_depth,
        effective_max_nodes=max_nodes,
        effective_max_edges=max_edges,
        effective_page_size=limit,
    )
    _enforce_response_bytes(model)
    return model


def _native_kind_for_root(family: LineageFamily) -> LineageNativeKind:
    if family is LineageFamily.RECORD:
        return LineageNativeKind.ARTIFACT
    if family is LineageFamily.NARRATIVE:
        return LineageNativeKind.NARRATIVE_VARIANT
    if family is LineageFamily.INSTITUTION:
        return LineageNativeKind.INSTITUTION_EPISODE
    if family is LineageFamily.OFFICE_SUCCESSION:
        return LineageNativeKind.OFFICE
    return LineageNativeKind.AGENT
