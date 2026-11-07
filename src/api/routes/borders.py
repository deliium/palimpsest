"""Read-only border-snapshot HTTP routes."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Query, Request

from api.borders_cursor import BordersCursorCodec, BordersCursorError
from api.borders_schemas import (
    MAX_PAGE_LIMIT,
    BordersAgreementOut,
    BordersAgreementPageOut,
    BordersClaimOut,
    BordersClaimPageOut,
    BordersControlPageOut,
    BordersControlRowOut,
    BordersSummaryOut,
)
from api.dependencies import get_borders_reader, get_settings
from api.errors import (
    bad_request,
    gone,
    internal,
    not_found,
    service_unavailable,
)
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.borders_ports import borders_query_fingerprint

router = APIRouter(prefix="/v1/simulations", tags=["borders"])
_LOGGER = get_logger("api.routes.borders")
BORDERS_ROUTE_COUNT: Final[int] = 6


def _reader(reader: object | None) -> Any:
    if reader is None:
        raise service_unavailable(code="borders_disabled")
    return reader


def _codec(request: Request) -> BordersCursorCodec:
    codec = getattr(request.app.state, "borders_cursor_codec", None)
    if not isinstance(codec, BordersCursorCodec):
        raise service_unavailable(code="borders_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.snapshot(run_id)
    except ValueError as exc:
        if str(exc) == "borders_store_corrupt":
            raise internal(code="borders_store_corrupt") from exc
        raise not_found(code="borders_publication_not_found") from exc
    except Exception as exc:
        raise not_found(code="borders_publication_not_found") from exc
    if snapshot is None:
        raise not_found(code="borders_publication_not_found")
    return snapshot


def _fingerprint(snapshot: Any, purpose: str, filters: dict[str, object]) -> str:
    return borders_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        filters=filters,
    )


def _after_key(
    codec: BordersCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
) -> str | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except BordersCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="borders_cursor_expired") from exc
        raise bad_request(code="borders_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, filters)
    ):
        raise bad_request(code="borders_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: BordersCursorCodec,
    *,
    snapshot: Any,
    purpose: str,
    filters: dict[str, object],
    next_key: str | None,
) -> str | None:
    if next_key is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        query_fingerprint=_fingerprint(snapshot, purpose, filters),
        after_key=next_key,
    )


def _claim_key(row: Any) -> str:
    return f"{row.domain_token}|{row.owner_token}"


def _claim(row: Any) -> BordersClaimOut:
    return BordersClaimOut(
        claim_token=row.claim_token,
        owner_token=row.owner_token,
        domain_token=row.domain_token,
        location_tokens=tuple(row.location_tokens),
        boundary_edge_tokens=tuple(row.boundary_edge_tokens),
        status=row.status,
        strength=row.strength,
        anchor_token=row.anchor_token,
    )


def _agreement_key(row: Any) -> str:
    return f"{row.domain_token}|{row.agreement_token}"


def _agreement(row: Any) -> BordersAgreementOut:
    return BordersAgreementOut(
        agreement_token=row.agreement_token,
        domain_token=row.domain_token,
        counterparty_token=row.counterparty_token,
        provision_tokens=tuple(row.provision_tokens),
        status=row.status,
        recognition=row.recognition,
        effective_tick=row.effective_tick,
        expiry_tick=row.expiry_tick,
    )


def _control_key(item: tuple[str, Any]) -> str:
    layer, row = item
    if layer == "physical":
        return f"physical|{row.location_token}|{row.window_start:012d}"
    return f"analytical|{row.domain_token}|{row.pattern_token}"


def _control(layer: str, row: Any) -> BordersControlRowOut:
    if layer == "physical":
        return BordersControlRowOut(
            layer="physical",
            location_token=row.location_token,
            window_start=row.window_start,
            window_end=row.window_end,
            actor_count=row.actor_count,
            action_count=row.action_count,
            hostile_count=row.hostile_count,
            assistance_count=row.assistance_count,
            presence_ticks=row.presence_ticks,
            classification=row.classification,
        )
    return BordersControlRowOut(
        layer="analytical",
        pattern_token=row.pattern_token,
        domain_token=row.domain_token,
        location_tokens=tuple(row.location_tokens),
        pattern=row.pattern,
        physical_actions=row.physical_actions,
        claim_count=row.claim_count,
        agreement_count=row.agreement_count,
        dispute_count=row.dispute_count,
    )


@router.get("/{run_id}/borders", response_model=BordersSummaryOut)
def get_borders_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersSummaryOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    summary = snapshot.summary
    return BordersSummaryOut(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        schema_version=snapshot.schema_version,
        candidate_count=summary.candidate_count,
        claim_count=summary.claim_count,
        agreement_count=summary.agreement_count,
        dispute_count=summary.dispute_count,
        physical_row_count=summary.physical_row_count,
        pattern_count=summary.pattern_count,
        coverage=summary.coverage,
    )


@router.get("/{run_id}/borders/claims", response_model=BordersClaimPageOut)
def get_border_claims(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersClaimPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    after = _after_key(
        codec, cursor, snapshot=snapshot, purpose="claims", filters=filters
    )
    ordered = sorted(snapshot.claims, key=_claim_key)
    if after is not None:
        ordered = [row for row in ordered if _claim_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _claim_key(page[-1]) if len(ordered) > len(page) else None
    return BordersClaimPageOut(
        items=tuple(_claim(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="claims",
            filters=filters,
            next_key=next_key,
        ),
    )


@router.get("/{run_id}/borders/claims/{claim_id}", response_model=BordersClaimOut)
def get_border_claim(
    run_id: str,
    claim_id: str,
    request: Request,
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersClaimOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    for row in snapshot.claims:
        if row.claim_token == claim_id or row.domain_token == claim_id:
            return _claim(row)
    raise not_found(code="borders_record_not_found")


@router.get("/{run_id}/borders/agreements", response_model=BordersAgreementPageOut)
def get_border_agreements(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersAgreementPageOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {}
    after = _after_key(
        codec, cursor, snapshot=snapshot, purpose="agreements", filters=filters
    )
    ordered = sorted(snapshot.agreements, key=_agreement_key)
    if after is not None:
        ordered = [row for row in ordered if _agreement_key(row) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _agreement_key(page[-1]) if len(ordered) > len(page) else None
    return BordersAgreementPageOut(
        items=tuple(_agreement(row) for row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="agreements",
            filters=filters,
            next_key=next_key,
        ),
    )


@router.get(
    "/{run_id}/borders/agreements/{agreement_id}",
    response_model=BordersAgreementOut,
)
def get_border_agreement(
    run_id: str,
    agreement_id: str,
    request: Request,
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersAgreementOut:
    _authorize(request, settings)
    snapshot = _snapshot(_reader(reader), run_id)
    for row in snapshot.agreements:
        if row.agreement_token == agreement_id:
            return _agreement(row)
    raise not_found(code="borders_record_not_found")


@router.get("/{run_id}/borders/control", response_model=BordersControlPageOut)
def get_border_control(
    run_id: str,
    request: Request,
    layer: str = Query(default="all"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_borders_reader),
    settings: Settings = Depends(get_settings),
) -> BordersControlPageOut:
    _authorize(request, settings)
    if layer not in {"physical", "analytical", "all"}:
        raise bad_request(code="borders_control_layer")
    snapshot = _snapshot(_reader(reader), run_id)
    codec = _codec(request)
    filters: dict[str, object] = {"layer": layer}
    after = _after_key(
        codec, cursor, snapshot=snapshot, purpose="control", filters=filters
    )
    items: list[tuple[str, Any]] = []
    if layer in {"physical", "all"}:
        items.extend(("physical", row) for row in snapshot.physical)
    if layer in {"analytical", "all"}:
        items.extend(("analytical", row) for row in snapshot.patterns)
    ordered = sorted(items, key=_control_key)
    if after is not None:
        ordered = [item for item in ordered if _control_key(item) > after]
    page = ordered[: max(1, min(limit, MAX_PAGE_LIMIT))]
    next_key = _control_key(page[-1]) if len(ordered) > len(page) else None
    return BordersControlPageOut(
        items=tuple(_control(layer_name, row) for layer_name, row in page),
        next_cursor=_next_cursor(
            codec,
            snapshot=snapshot,
            purpose="control",
            filters=filters,
            next_key=next_key,
        ),
    )
