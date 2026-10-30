"""Read-only macro-society HTTP routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from api.dependencies import get_macro_society_reader, get_settings
from api.errors import bad_request, gone, not_found, service_unavailable
from api.macro_society_cursor import MacroSocietyCursorCodec, MacroSocietyCursorError
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.macro_society_models import MacroSocietyArtifactError
from simulation.macro_society_ports import (
    MacroSocietyReadPort,
    macro_society_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["macro-societies"])
_LOGGER = get_logger("api.routes.macro_society")
_PURPOSE_CANDIDATES = "candidates"
_PURPOSE_LINEAGE = "lineage"


def _cursor_codec(request: Request) -> MacroSocietyCursorCodec:
    codec = getattr(request.app.state, "macro_society_cursor_codec", None)
    if codec is None:
        raise service_unavailable(code="macro_society_disabled")
    return codec


def _reader(reader: MacroSocietyReadPort | None) -> MacroSocietyReadPort:
    if reader is None:
        raise service_unavailable(code="macro_society_disabled")
    return reader


def _decode_cursor(
    codec: MacroSocietyCursorCodec, token: str, *, purpose: str
):
    try:
        cursor, _ = codec.decode(token, purpose=purpose)
    except MacroSocietyCursorError as exc:
        if exc.reason_code == "macro_society_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    return cursor


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


@router.get("/{run_id}/macro-societies")
async def macro_society_summary(
    run_id: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    reader: MacroSocietyReadPort | None = Depends(get_macro_society_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    summary = _reader(reader).read_summary(run_id)
    _LOGGER.debug("macro_society_read route=summary run=%s", run_id)
    return {
        "publication_id": summary.publication_id,
        "snapshot_digest": summary.snapshot_digest,
        "schema_version": summary.schema_version,
        "policy_version": summary.policy_version,
        "run_id": summary.run_id,
        "input_revision": summary.input_revision,
        "generated_tick": summary.generated_tick,
        "window_count": summary.window_count,
        "candidate_count": summary.candidate_count,
        "edge_count": summary.edge_count,
        "coverage": {
            "observed": summary.coverage.observed,
            "expected": summary.coverage.expected,
            "ratio": summary.coverage.ratio,
        },
        "provenance_code": summary.provenance_code,
    }


@router.get("/{run_id}/macro-societies/candidates")
async def macro_society_candidates(
    run_id: str,
    request: Request,
    response: Response,
    status: Literal["supported", "fragmented", "contested"] | None = Query(
        default=None
    ),
    limit: int = Query(default=100, ge=1),
    cursor: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    reader: MacroSocietyReadPort | None = Depends(get_macro_society_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    port = _reader(reader)
    codec = _cursor_codec(request)
    summary = port.read_summary(run_id)
    offset = 0
    if cursor is not None:
        decoded = _decode_cursor(codec, cursor, purpose=_PURPOSE_CANDIDATES)
        expected = macro_society_query_fingerprint(
            run_id=run_id,
            publication_id=summary.publication_id,
            purpose=_PURPOSE_CANDIDATES,
            filters={"status": status},
        )
        if decoded.query_fingerprint != expected:
            raise bad_request(code="macro_society_cursor_invalid")
        offset = decoded.offset
    rows, next_offset = port.read_candidates(
        run_id,
        publication_id=summary.publication_id,
        offset=offset,
        limit=limit,
    )
    items = [
        {
            "macro_society_id": row.macro_society_id,
            "creation_tick": row.creation_tick,
            "first_tick": row.first_tick,
            "last_tick": row.last_tick,
            "status": row.status,
            "member_count": len(row.member_ids),
            "lane_signature": list(row.lane_signature),
            "overlap_person_count": len(row.overlap_person_ids),
        }
        for row in rows
        if status is None or row.status == status
    ]
    token = None
    if next_offset is not None:
        token = codec.encode(
            purpose=_PURPOSE_CANDIDATES,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            offset=next_offset,
            query_fingerprint=macro_society_query_fingerprint(
                run_id=run_id,
                publication_id=summary.publication_id,
                purpose=_PURPOSE_CANDIDATES,
                filters={"status": status},
            ),
        )
    _LOGGER.debug(
        "macro_society_read route=candidates run=%s rows=%s", run_id, len(items)
    )
    return {"items": items, "next_cursor": token}


@router.get("/{run_id}/macro-societies/candidates/{macro_society_id}")
async def macro_society_candidate(
    run_id: str,
    macro_society_id: str,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
    reader: MacroSocietyReadPort | None = Depends(get_macro_society_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    try:
        record = _reader(reader).read_candidate(
            run_id, macro_society_id, publication_id=None
        )
    except MacroSocietyArtifactError as exc:
        raise not_found(code=exc.reason_code) from exc
    return {
        "macro_society_id": record.macro_society_id,
        "creation_tick": record.creation_tick,
        "first_tick": record.first_tick,
        "last_tick": record.last_tick,
        "status": record.status,
        "member_ids": list(record.member_ids),
        "lane_signature": list(record.lane_signature),
        "overlap_person_ids": list(record.overlap_person_ids),
    }


@router.get("/{run_id}/macro-societies/lineage")
async def macro_society_lineage(
    run_id: str,
    request: Request,
    response: Response,
    kind: Literal[
        "continued", "transformed", "split", "merge", "dissolved", "emerged"
    ]
    | None = Query(default=None),
    limit: int = Query(default=100, ge=1),
    cursor: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
    reader: MacroSocietyReadPort | None = Depends(get_macro_society_reader),
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    _authorize(request, settings)
    port = _reader(reader)
    codec = _cursor_codec(request)
    summary = port.read_summary(run_id)
    offset = 0
    if cursor is not None:
        decoded = _decode_cursor(codec, cursor, purpose=_PURPOSE_LINEAGE)
        expected = macro_society_query_fingerprint(
            run_id=run_id,
            publication_id=summary.publication_id,
            purpose=_PURPOSE_LINEAGE,
            filters={"kind": kind},
        )
        if decoded.query_fingerprint != expected:
            raise bad_request(code="macro_society_cursor_invalid")
        offset = decoded.offset
    rows, next_offset = port.read_lineage(
        run_id,
        publication_id=summary.publication_id,
        offset=offset,
        limit=limit,
    )
    items = [
        {
            "from_id": row.from_id,
            "to_id": row.to_id,
            "kind": row.kind,
            "from_tick": row.from_tick,
            "to_tick": row.to_tick,
            "jaccard": row.jaccard,
        }
        for row in rows
        if kind is None or row.kind == kind
    ]
    token = None
    if next_offset is not None:
        token = codec.encode(
            purpose=_PURPOSE_LINEAGE,
            run_id=run_id,
            publication_id=summary.publication_id,
            snapshot_digest=summary.snapshot_digest,
            offset=next_offset,
            query_fingerprint=macro_society_query_fingerprint(
                run_id=run_id,
                publication_id=summary.publication_id,
                purpose=_PURPOSE_LINEAGE,
                filters={"kind": kind},
            ),
        )
    return {"items": items, "next_cursor": token}
