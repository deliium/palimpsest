"""Seven GET-only, dual-gated accounting ledger read routes."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Final

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from api.accounting_ledgers_cursor import (
    AccountingLedgersCursorCodec,
    AccountingLedgersCursorError,
)
from api.dependencies import get_settings
from api.errors import bad_request, gone, internal, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from simulation.accounting_ledgers_paging import page_accounting_ledgers
from simulation.accounting_ledgers_ports import (
    accounting_ledgers_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["accounting-ledgers"])
_LOGGER = get_logger("api.routes.accounting_ledgers")
ACCOUNTING_LEDGERS_ROUTE_COUNT: Final[int] = 7


def _reader(request: Request) -> Any:
    reader = getattr(request.app.state, "accounting_ledgers_reader", None)
    if reader is None:
        _LOGGER.info("accounting_ledgers_reader_disabled")
        raise service_unavailable(code="accounting_ledgers_disabled")
    return reader


def _codec(request: Request) -> AccountingLedgersCursorCodec:
    codec = getattr(request.app.state, "accounting_ledgers_cursor_codec", None)
    if not isinstance(codec, AccountingLedgersCursorCodec):
        _LOGGER.info("accounting_ledgers_reader_disabled")
        raise service_unavailable(code="accounting_ledgers_disabled")
    return codec


def _authorize(request: Request) -> None:
    require_http_capability(
        request,
        get_settings(request),
        capability=ApiCapability.SUBJECTIVE_DEBUG,
    )


def _snapshot(reader: Any, run_id: str) -> Any:
    try:
        snapshot = reader.read_snapshot(run_id)
    except ValueError as exc:
        if "corrupt" in str(exc):
            _LOGGER.error("accounting_ledgers_store_corrupt")
            raise internal(code="accounting_ledgers_store_corrupt") from exc
        raise not_found(code="accounting_ledgers_run_not_found") from exc
    except Exception as exc:
        raise not_found(code="accounting_ledgers_run_not_found") from exc
    if snapshot is None:
        raise not_found(code="accounting_ledgers_run_not_found")
    return snapshot


def _fingerprint(
    snapshot: Any, purpose: str, window_index: int | None, limit: int
) -> str:
    return accounting_ledgers_query_fingerprint(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        purpose=purpose,
        limit=limit,
        window_index=window_index,
    )


def _after_key(
    codec: AccountingLedgersCursorCodec,
    token: str | None,
    *,
    snapshot: Any,
    purpose: str,
    window_index: int | None,
    limit: int,
) -> str:
    if token is None:
        return ""
    try:
        payload = codec.decode(token, purpose=purpose)
    except AccountingLedgersCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code="accounting_ledgers_cursor_expired") from exc
        raise bad_request(code="accounting_ledgers_cursor_invalid") from exc
    if (
        payload.get("run_id") != snapshot.run_id
        or payload.get("publication_id") != snapshot.publication_id
        or payload.get("snapshot_digest") != snapshot.digest
        or payload.get("query_fingerprint")
        != _fingerprint(snapshot, purpose, window_index, limit)
    ):
        raise bad_request(code="accounting_ledgers_cursor_invalid")
    raw = payload.get("after_key")
    return "" if type(raw) is not str else raw


def _dict(row: Any) -> dict[str, object]:
    values: dict[str, object] = {}
    for item in fields(row):
        value = getattr(row, item.name)
        if hasattr(value, "value"):
            value = value.value
        values[item.name] = value
    return values


def _page(
    request: Request,
    run_id: str,
    *,
    purpose: str,
    limit: int,
    cursor: str | None,
    window_index: int | None,
) -> tuple[Any, tuple[object, ...], str | None]:
    reader = _reader(request)
    _authorize(request)
    snapshot = _snapshot(reader, run_id)
    codec = _codec(request)
    after = _after_key(
        codec,
        cursor,
        snapshot=snapshot,
        purpose=purpose,
        window_index=window_index,
        limit=limit,
    )
    rows = snapshot.alignments if purpose == "alignment" else getattr(
        snapshot, purpose
    )
    page, next_key = page_accounting_ledgers(
        rows,
        purpose=purpose,
        limit=limit,
        after_key=after,
        window_index=window_index,
    )
    next_cursor = None
    if next_key:
        next_cursor = codec.encode(
            purpose=purpose,
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            snapshot_digest=snapshot.digest,
            query_fingerprint=_fingerprint(
                snapshot, purpose, window_index, limit
            ),
            after_key=next_key,
        )
    _LOGGER.info("accounting_ledgers_route_served purpose=%s", purpose)
    return snapshot, page, next_cursor


def _page_body(
    snapshot: Any,
    page: tuple[object, ...],
    next_cursor: str | None,
    window_index: int | None,
    purpose: str,
) -> dict[str, object]:
    coverage_key = {
        "entries": "entry_coverage",
        "records": "record_coverage",
        "alignment": "alignment_coverage",
    }.get(purpose, "entry_coverage")
    return {
        "run_id": snapshot.run_id,
        "publication_id": snapshot.publication_id,
        "window_index": window_index,
        "rows": [_dict(row) for row in page],
        "next_cursor": next_cursor,
        "coverage": getattr(snapshot.summary, coverage_key),
    }


@router.get("/{run_id}/accounting-ledgers")
def get_accounting_ledgers_summary(
    run_id: str, request: Request
) -> JSONResponse:
    reader = _reader(request)
    _authorize(request)
    snapshot = _snapshot(reader, run_id)
    summary = snapshot.summary
    return JSONResponse(
        {
            "run_id": snapshot.run_id,
            "publication_id": snapshot.publication_id,
            "digest": snapshot.digest,
            "schema_version": snapshot.schema_version,
            "entry_count": summary.entry_count,
            "record_count": summary.record_count,
            "condition_count": summary.condition_count,
            "flow_count": summary.flow_count,
            "counterparty_count": summary.counterparty_count,
            "alignment_count": summary.alignment_count,
            "window_count": summary.window_count,
            "entry_coverage": summary.entry_coverage,
            "record_coverage": summary.record_coverage,
            "alignment_coverage": summary.alignment_coverage,
            "condition_coverage": summary.condition_coverage,
            "flow_coverage": summary.flow_coverage,
            "counterparty_coverage": summary.counterparty_coverage,
            "truncated": summary.truncated,
        }
    )


def _page_handler(
    purpose: str,
    run_id: str,
    request: Request,
    limit: int,
    cursor: str | None,
    window_index: int | None,
) -> JSONResponse:
    snapshot, page, next_cursor = _page(
        request,
        run_id,
        purpose=purpose,
        limit=limit,
        cursor=cursor,
        window_index=window_index,
    )
    return JSONResponse(
        _page_body(snapshot, page, next_cursor, window_index, purpose)
    )


@router.get("/{run_id}/accounting-ledgers/entries")
def get_accounting_ledgers_entries(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("entries", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/accounting-ledgers/records")
def get_accounting_ledgers_records(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("records", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/accounting-ledgers/conditions")
def get_accounting_ledgers_conditions(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "conditions", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/accounting-ledgers/flows")
def get_accounting_ledgers_flows(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("flows", run_id, request, limit, cursor, window_index)


@router.get("/{run_id}/accounting-ledgers/counterparties")
def get_accounting_ledgers_counterparties(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler(
        "counterparties", run_id, request, limit, cursor, window_index
    )


@router.get("/{run_id}/accounting-ledgers/alignment")
def get_accounting_ledgers_alignment(
    run_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = Query(default=None),
    window_index: int | None = Query(default=None, ge=0, le=511),
) -> JSONResponse:
    return _page_handler("alignment", run_id, request, limit, cursor, window_index)
