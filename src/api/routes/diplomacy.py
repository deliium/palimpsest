"""Read-only diplomacy HTTP routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_diplomacy_reader, get_settings
from api.diplomacy_cursor import DiplomacyCursorCodec, DiplomacyCursorError
from api.diplomacy_schemas import (
    MAX_PAGE_LIMIT,
    DiplomacyConflictOut,
    DiplomacyContactOut,
    DiplomacyDeclarationOut,
    DiplomacyEnvoyOut,
    DiplomacyInstrumentDetailOut,
    DiplomacyInstrumentOut,
    DiplomacyInstrumentPageOut,
    DiplomacyLineageOut,
    DiplomacyLineagePageOut,
    DiplomacyMisrepresentationOut,
    DiplomacyNegotiationOut,
    DiplomacyPartyOut,
    DiplomacyRelationDetailOut,
    DiplomacyRelationOut,
    DiplomacyRelationPageOut,
    DiplomacySummaryOut,
    DiplomacyTerminationOut,
)
from api.errors import bad_request, gone, not_found, service_unavailable
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from simulation.diplomacy_models import DiplomacyArtifactError
from simulation.diplomacy_ports import (
    DiplomacyPortError,
    DiplomacyReadPort,
    diplomacy_query_fingerprint,
)

router = APIRouter(prefix="/v1/simulations", tags=["diplomacy"])
_LOGGER = get_logger("api.routes.diplomacy")


def _reader(reader: DiplomacyReadPort | None) -> DiplomacyReadPort:
    if reader is None:
        raise service_unavailable(code="diplomacy_disabled")
    return reader


def _codec(request: Request) -> DiplomacyCursorCodec:
    codec = getattr(request.app.state, "diplomacy_cursor_codec", None)
    if not isinstance(codec, DiplomacyCursorCodec):
        raise service_unavailable(code="diplomacy_disabled")
    return codec


def _authorize(request: Request, settings: Settings) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


def _read(func: Any, *args: object, **kwargs: object) -> Any:
    try:
        return func(*args, **kwargs)
    except DiplomacyPortError as exc:
        if exc.code in {"diplomacy_not_found", "diplomacy_unknown_relation"}:
            raise not_found(code="diplomacy_unknown_relation") from exc
        if exc.code == "diplomacy_unknown_instrument":
            raise not_found(code=exc.code) from exc
        if exc.code == "diplomacy_cursor_expired":
            raise gone(code=exc.code) from exc
        raise bad_request(code=exc.code) from exc
    except DiplomacyArtifactError as exc:
        raise not_found(code="diplomacy_not_found") from exc


def _fingerprint(summary: Any, purpose: str) -> str:
    return diplomacy_query_fingerprint(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        purpose=purpose,
        filters={},
    )


def _cursor_key(
    codec: DiplomacyCursorCodec,
    token: str | None,
    *,
    summary: Any,
    purpose: str,
) -> str | None:
    if token is None:
        return None
    try:
        payload = codec.decode(token, purpose=purpose)
    except DiplomacyCursorError as exc:
        if exc.reason_code == "diplomacy_cursor_expired":
            raise gone(code=exc.reason_code) from exc
        raise bad_request(code=exc.reason_code) from exc
    if (
        payload.get("run_id") != summary.run_id
        or payload.get("publication_id") != summary.publication_id
        or payload.get("snapshot_digest") != summary.snapshot_digest
        or payload.get("query_fingerprint") != _fingerprint(summary, purpose)
    ):
        raise bad_request(code="diplomacy_cursor_invalid")
    after = payload.get("after_key")
    return after if type(after) is str else None


def _next_cursor(
    codec: DiplomacyCursorCodec,
    *,
    summary: Any,
    purpose: str,
    next_key: str | None,
) -> str | None:
    if next_key is None:
        return None
    return codec.encode(
        purpose=purpose,
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        query_fingerprint=_fingerprint(summary, purpose),
        after_key=next_key,
    )


def _summary_out(summary: Any) -> DiplomacySummaryOut:
    row = summary.summary
    return DiplomacySummaryOut(
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=summary.snapshot_digest,
        relation_count=row.relation_count,
        party_count=row.party_count,
        contact_count=row.contact_count,
        envoy_count=row.envoy_count,
        negotiation_count=row.negotiation_count,
        instrument_count=row.instrument_count,
        declaration_count=row.declaration_count,
        misrepresentation_count=row.misrepresentation_count,
        termination_count=row.termination_count,
        conflict_count=row.conflict_count,
        candidate_count=row.candidate_count,
        lineage_edge_count=row.lineage_edge_count,
        coverage=summary.coverage,
    )


def _row_out(row: object) -> object:
    name = type(row).__name__
    mapping = {
        "DiplomacySnapshotRelationRow": DiplomacyRelationOut,
        "DiplomacySnapshotPartyRow": DiplomacyPartyOut,
        "DiplomacySnapshotContactRow": DiplomacyContactOut,
        "DiplomacySnapshotEnvoyRow": DiplomacyEnvoyOut,
        "DiplomacySnapshotNegotiationRow": DiplomacyNegotiationOut,
        "DiplomacySnapshotInstrumentRow": DiplomacyInstrumentOut,
        "DiplomacySnapshotDeclarationRow": DiplomacyDeclarationOut,
        "DiplomacySnapshotMisrepresentationRow": DiplomacyMisrepresentationOut,
        "DiplomacySnapshotTerminationRow": DiplomacyTerminationOut,
        "DiplomacySnapshotConflictRow": DiplomacyConflictOut,
        "DiplomacySnapshotLineageRow": DiplomacyLineageOut,
    }
    model = mapping.get(name)
    if model is None:
        raise bad_request(code="diplomacy_snapshot_invalid")
    return model(**{field: getattr(row, field) for field in model.model_fields})


@router.get("/{run_id}/diplomacy", response_model=DiplomacySummaryOut)
def get_diplomacy_summary(
    run_id: str,
    request: Request,
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacySummaryOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    return _summary_out(_read(active.read_summary, run_id))


@router.get("/{run_id}/diplomacy/relations", response_model=DiplomacyRelationPageOut)
def get_diplomacy_relations(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacyRelationPageOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    summary = _read(active.read_summary, run_id)
    codec = _codec(request)
    after = _cursor_key(codec, cursor, summary=summary, purpose="relations")
    selection = _read(
        active.relations_page,
        run_id,
        after_key=after,
        limit=limit,
    )
    return DiplomacyRelationPageOut(
        items=tuple(_row_out(row) for row in selection.rows),  # type: ignore[misc]
        next_cursor=_next_cursor(
            codec, summary=summary, purpose="relations", next_key=selection.next_key
        ),
    )


@router.get(
    "/{run_id}/diplomacy/relations/{relation_id}",
    response_model=DiplomacyRelationDetailOut,
)
def get_diplomacy_relation(
    run_id: str,
    relation_id: str,
    request: Request,
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacyRelationDetailOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    detail = _read(active.read_relation, run_id, relation_id)
    rows = [_row_out(row) for row in detail.rows]
    return DiplomacyRelationDetailOut(
        relation=rows[0],  # type: ignore[arg-type]
        parties=tuple(row for row in rows if isinstance(row, DiplomacyPartyOut)),
        contacts=tuple(row for row in rows if isinstance(row, DiplomacyContactOut)),
        envoys=tuple(row for row in rows if isinstance(row, DiplomacyEnvoyOut)),
        negotiations=tuple(
            row for row in rows if isinstance(row, DiplomacyNegotiationOut)
        ),
        instruments=tuple(
            row for row in rows if isinstance(row, DiplomacyInstrumentOut)
        ),
        declarations=tuple(
            row for row in rows if isinstance(row, DiplomacyDeclarationOut)
        ),
        misrepresentations=tuple(
            row for row in rows if isinstance(row, DiplomacyMisrepresentationOut)
        ),
        terminations=tuple(
            row for row in rows if isinstance(row, DiplomacyTerminationOut)
        ),
        truncated=detail.truncated,
    )


@router.get(
    "/{run_id}/diplomacy/instruments", response_model=DiplomacyInstrumentPageOut
)
def get_diplomacy_instruments(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacyInstrumentPageOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    summary = _read(active.read_summary, run_id)
    codec = _codec(request)
    after = _cursor_key(codec, cursor, summary=summary, purpose="instruments")
    selection = _read(
        active.instruments_page,
        run_id,
        after_key=after,
        limit=limit,
    )
    return DiplomacyInstrumentPageOut(
        items=tuple(_row_out(row) for row in selection.rows),  # type: ignore[misc]
        next_cursor=_next_cursor(
            codec, summary=summary, purpose="instruments", next_key=selection.next_key
        ),
    )


@router.get(
    "/{run_id}/diplomacy/instruments/{instrument_id}",
    response_model=DiplomacyInstrumentDetailOut,
)
def get_diplomacy_instrument(
    run_id: str,
    instrument_id: str,
    request: Request,
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacyInstrumentDetailOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    detail = _read(active.read_instrument, run_id, instrument_id)
    rows = [_row_out(row) for row in detail.rows]
    return DiplomacyInstrumentDetailOut(
        instrument=rows[0],  # type: ignore[arg-type]
        declarations=tuple(
            row for row in rows if isinstance(row, DiplomacyDeclarationOut)
        ),
        misrepresentations=tuple(
            row for row in rows if isinstance(row, DiplomacyMisrepresentationOut)
        ),
        terminations=tuple(
            row for row in rows if isinstance(row, DiplomacyTerminationOut)
        ),
        truncated=detail.truncated,
    )


@router.get("/{run_id}/diplomacy/lineage", response_model=DiplomacyLineagePageOut)
def get_diplomacy_lineage(
    run_id: str,
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=MAX_PAGE_LIMIT),
    reader: object | None = Depends(get_diplomacy_reader),
    settings: Settings = Depends(get_settings),
) -> DiplomacyLineagePageOut:
    _authorize(request, settings)
    active = _reader(reader)  # type: ignore[arg-type]
    summary = _read(active.read_summary, run_id)
    codec = _codec(request)
    after = _cursor_key(codec, cursor, summary=summary, purpose="lineage")
    selection = _read(
        active.lineage_page,
        run_id,
        after_key=after,
        limit=limit,
    )
    return DiplomacyLineagePageOut(
        items=tuple(_row_out(row) for row in selection.rows),  # type: ignore[misc]
        next_cursor=_next_cursor(
            codec, summary=summary, purpose="lineage", next_key=selection.next_key
        ),
    )
