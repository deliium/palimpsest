"""Read-only experiment-matrix filesystem API (objective_inspection).

Serves allowlisted JSON under ``PALIMPSEST_RESEARCH_MATRIX_ROOT`` without
importing ``analysis`` or starting matrix batches.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final, cast

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field

from api.dependencies import get_settings
from api.errors import (
    bad_request,
    conflict,
    not_found,
    service_unavailable,
    too_large,
)
from api.research_cultural_cursor import CulturalCursorCodec, CulturalCursorError
from api.research_cultural_service import (
    ArtifactDocument,
    CulturalEvidencePair,
    ResearchCulturalService,
    manifest_kind,
)
from api.schemas import AvailabilityOut, StrictModel
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings

router = APIRouter(prefix="/v1/research", tags=["research-matrix"])
_LOGGER = get_logger("api.routes.research_matrix")

_MATRIX_SCHEMA: Final[str] = "experiment-matrix-v1"
_RUNTIME_MANIFEST_SCHEMA: Final[str] = "matrix-manifest-v1"
_LEGACY_ARTIFACT_SUFFIXES: Final[tuple[str, ...]] = (
    ".completion.json",
    ".metrics.json",
    ".cultural-evidence.json",
    ".cultural-metrics.json",
)
_MATRIX_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CELL_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class MatrixListItemOut(StrictModel):
    matrix_id: str
    schema_version: str
    has_aggregate: bool = False
    has_metric_summary: bool = False


class MatrixListOut(StrictModel):
    items: tuple[MatrixListItemOut, ...]
    count: int = Field(ge=0)
    availability: AvailabilityOut


class MatrixCellListOut(StrictModel):
    matrix_id: str
    cell_ids: tuple[str, ...]
    count: int = Field(ge=0)


class CulturalEvidenceWindowOut(StrictModel):
    from_tick: int | None = None
    to_tick: int | None = None


class CulturalEvidencePageOut(StrictModel):
    schema_version: str = "research-cultural-evidence-page-v1"
    run_id: str
    matrix_id: str
    cell_id: str
    section: str
    artifact_digest: str
    source_revision: str
    binding_state: str
    requested_window: CulturalEvidenceWindowOut
    capture_status: dict[str, object]
    gaps: tuple[object, ...]
    rows: tuple[dict[str, object], ...]
    next_cursor: str | None = None
    truncated: bool = False
    coverage: float | None = None


def _inspect(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.OBJECTIVE_INSPECTION
    )


def _root_or_none(settings: Settings) -> Path | None:
    root = settings.research_matrix_root
    if root is None:
        return None
    resolved = root.resolve()
    if not resolved.is_dir():
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="matrix_root_missing",
        )
        return None
    return resolved


def _require_root(settings: Settings) -> Path:
    root = _root_or_none(settings)
    if root is None:
        if settings.research_matrix_root is None:
            raise service_unavailable(code="matrix_root_unset")
        raise service_unavailable(code="matrix_root_missing")
    return root


def _validate_matrix_id(matrix_id: str) -> str:
    if _MATRIX_ID_RE.fullmatch(matrix_id) is None:
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="invalid_matrix_id",
        )
        raise bad_request(code="invalid_matrix_id")
    return matrix_id


def _validate_cell_id(cell_id: str) -> str:
    if _CELL_ID_RE.fullmatch(cell_id) is None:
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="invalid_cell_id",
        )
        raise bad_request(code="invalid_cell_id")
    return cell_id


def _resolve_under(base: Path, *parts: str) -> Path:
    candidate = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if candidate != base_resolved and not str(candidate).startswith(
        str(base_resolved) + "/"
    ):
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="path_traversal",
        )
        raise bad_request(code="path_traversal")
    return candidate


def _read_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        raise not_found(code="matrix_file_missing") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="invalid_json",
        )
        raise bad_request(code="invalid_json") from None


def _manifest_schema(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    schema = payload.get("schema_version")
    if isinstance(schema, str) and schema.strip():
        return schema.strip()
    return None


def _supported_manifest(payload: Any) -> bool:
    try:
        return manifest_kind(payload) in {"runtime", "legacy"}
    except Exception:
        return False


def _cultural_service(request: Request) -> ResearchCulturalService:
    service = getattr(request.app.state, "research_cultural_service", None)
    if not isinstance(service, ResearchCulturalService):
        raise service_unavailable(code="research_cultural_unavailable")
    return service


def _cursor_codec(request: Request) -> CulturalCursorCodec:
    codec = getattr(request.app.state, "research_cultural_cursor_codec", None)
    if not isinstance(codec, CulturalCursorCodec):
        raise service_unavailable(code="research_cultural_unavailable")
    return codec


def _debug(request: Request, settings: Settings = Depends(get_settings)) -> None:
    require_http_capability(
        request, settings, capability=ApiCapability.SUBJECTIVE_DEBUG
    )


_SECTION_ROW_KEYS: Final[dict[str, str]] = {
    "boundaries": "boundaries",
    "traits": "trait_rows",
    "transmission": "transmission_edges",
    "groups": "group_memberships",
    "archives": "archive_states",
}
_SECTION_TICK_KEYS: Final[dict[str, str]] = {
    "boundaries": "boundary_tick",
    "traits": "boundary_tick",
    "transmission": "acquisition_boundary",
    "groups": "boundary_tick",
    "archives": "boundary_tick",
}


def _row_owner_matches(section: str, row: dict[str, object], owner_id: str) -> bool:
    if section == "transmission":
        return owner_id in {
            row.get("source_owner_id"),
            row.get("receiver_owner_id"),
        }
    if section == "archives":
        holders = row.get("holder_owner_ids")
        return isinstance(holders, list) and owner_id in holders
    if section == "boundaries":
        owners = row.get("living_owner_ids")
        return isinstance(owners, list) and owner_id in owners
    return row.get("owner_id") == owner_id


def _filtered_rows(
    section: str,
    rows: list[dict[str, object]],
    *,
    from_tick: int | None,
    to_tick: int | None,
    owner_id: str | None,
    dimension: str | None,
) -> list[dict[str, object]]:
    tick_key = _SECTION_TICK_KEYS[section]
    result: list[dict[str, object]] = []
    for row in rows:
        tick = row.get(tick_key)
        if not isinstance(tick, int):
            continue
        if from_tick is not None and tick < from_tick:
            continue
        if to_tick is not None and tick >= to_tick:
            continue
        if owner_id is not None and not _row_owner_matches(section, row, owner_id):
            continue
        if dimension is not None and row.get("dimension") != dimension:
            continue
        result.append(row)
    if section == "traits":
        result.sort(
            key=lambda row: (
                row.get("boundary_tick", 0),
                row.get("owner_id", ""),
                row.get("dimension", ""),
                row.get("local_entry_id", ""),
            )
        )
    elif section == "transmission":
        result.sort(
            key=lambda row: (
                row.get("acquisition_boundary", 0),
                row.get("edge_id", ""),
            )
        )
    elif section == "groups":
        result.sort(
            key=lambda row: (
                row.get("boundary_tick", 0),
                row.get("group_id", ""),
                row.get("owner_id", ""),
            )
        )
    elif section == "archives":
        result.sort(
            key=lambda row: (
                row.get("boundary_tick", 0),
                row.get("subject_id", ""),
            )
        )
    else:
        result.sort(key=lambda row: _int_tick(row))
    return result


def _int_tick(row: dict[str, object]) -> int:
    value = row.get("boundary_tick", 0)
    return value if isinstance(value, int) else 0


def _coverage(
    pair: CulturalEvidencePair,
    *,
    dimension: str | None,
    from_tick: int | None,
    to_tick: int | None,
) -> float | None:
    if dimension is None:
        return None
    observed = 0
    total = 0
    boundaries = pair.evidence.get("boundaries")
    if not isinstance(boundaries, list):
        return None
    for row in boundaries:
        if not isinstance(row, dict):
            continue
        tick = row.get("boundary_tick")
        if not isinstance(tick, int):
            continue
        if from_tick is not None and tick < from_tick:
            continue
        if to_tick is not None and tick >= to_tick:
            continue
        coverage = row.get("owner_dimension_coverage")
        if not isinstance(coverage, list):
            continue
        for item in coverage:
            if isinstance(item, list) and len(item) == 3 and item[1] == dimension:
                total += 1
                if item[2] == "complete":
                    observed += 1
    if total == 0:
        return None
    return observed / total


def _artifact_response(document: ArtifactDocument) -> Response:
    raw = document.raw
    binding = document.binding
    return Response(
        content=raw,
        media_type="application/json",
        headers={
            "Cache-Control": "no-store",
            "X-Palimpsest-Artifact-Binding": binding,
        },
    )


def _matrix_dir(root: Path, matrix_id: str) -> Path:
    mid = _validate_matrix_id(matrix_id)
    path = _resolve_under(root, mid)
    if not path.is_dir():
        raise not_found(code="matrix_not_found")
    return path


@router.get("/matrices", response_model=MatrixListOut)
async def list_matrices(
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> MatrixListOut:
    del request
    root = _root_or_none(settings)
    if root is None:
        _LOGGER.info("route_matrix_list", count=0)
        return MatrixListOut(
            items=(),
            count=0,
            availability=AvailabilityOut.UNAVAILABLE,
        )
    items: list[MatrixListItemOut] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        if _MATRIX_ID_RE.fullmatch(child.name) is None:
            continue
        manifest_path = child / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            payload = _read_json(manifest_path)
        except Exception:
            continue
        schema = _manifest_schema(payload)
        if not _supported_manifest(payload):
            _LOGGER.warning(
                "matrix_fs_rejected",
                reason_code="unsupported_matrix_schema",
            )
            continue
        items.append(
            MatrixListItemOut(
                matrix_id=child.name,
                schema_version=schema or "unknown",
                has_aggregate=(child / "aggregate.json").is_file(),
                has_metric_summary=(child / "metric-summary.json").is_file(),
            )
        )
    _LOGGER.info("route_matrix_list", count=len(items))
    return MatrixListOut(
        items=tuple(items),
        count=len(items),
        availability=AvailabilityOut.AVAILABLE,
    )


@router.get("/matrices/{matrix_id}/manifest")
async def get_matrix_manifest(
    matrix_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    del request
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    path = _resolve_under(matrix_dir, "manifest.json")
    if not path.is_file():
        raise not_found(code="matrix_file_missing")
    payload = _read_json(path)
    if not _supported_manifest(payload):
        _LOGGER.warning(
            "matrix_fs_rejected",
            reason_code="unsupported_matrix_schema",
        )
        raise bad_request(code="unsupported_matrix_schema")
    _LOGGER.info("route_matrix_manifest", matrix_id=matrix_id)
    return JSONResponse(payload)


@router.get("/matrices/{matrix_id}/aggregate")
async def get_matrix_aggregate(
    matrix_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    del request
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    path = _resolve_under(matrix_dir, "aggregate.json")
    if not path.is_file():
        raise not_found(code="matrix_file_missing")
    payload = _read_json(path)
    _LOGGER.info("route_matrix_aggregate", matrix_id=matrix_id)
    return JSONResponse(payload)


@router.get("/matrices/{matrix_id}/metric-summary")
async def get_matrix_metric_summary(
    matrix_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    del request
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    path = _resolve_under(matrix_dir, "metric-summary.json")
    if not path.is_file():
        raise not_found(code="matrix_file_missing")
    payload = _read_json(path)
    _LOGGER.info("route_matrix_metric_summary", matrix_id=matrix_id)
    return JSONResponse(payload)


@router.get("/matrices/{matrix_id}/cells", response_model=MatrixCellListOut)
async def list_matrix_cells(
    matrix_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> MatrixCellListOut:
    del request
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    cells_dir = matrix_dir / "cells"
    cell_ids: list[str] = []
    manifest_path = matrix_dir / "manifest.json"
    manifest = _read_json(manifest_path) if manifest_path.is_file() else None
    try:
        kind = manifest_kind(manifest) if manifest is not None else "legacy"
    except Exception:
        raise bad_request(code="unsupported_matrix_schema") from None
    if kind == "runtime" and isinstance(manifest, dict):
        declared = manifest.get("cell_ids")
        if not isinstance(declared, list):
            raise bad_request(code="invalid_manifest")
        for raw in declared:
            if not isinstance(raw, str) or _CELL_ID_RE.fullmatch(raw) is None:
                continue
            if (cells_dir / f"{raw}.json").is_file():
                cell_ids.append(raw)
    elif cells_dir.is_dir():
        for path in sorted(cells_dir.iterdir(), key=lambda p: p.name):
            if not path.is_file():
                continue
            name = path.name
            if any(name.endswith(suffix) for suffix in _LEGACY_ARTIFACT_SUFFIXES):
                continue
            if not name.endswith(".json"):
                continue
            cell_id = name[: -len(".json")]
            if _CELL_ID_RE.fullmatch(cell_id) is None:
                continue
            cell_ids.append(cell_id)
    _LOGGER.info(
        "route_matrix_cells",
        matrix_id=matrix_id,
        count=len(cell_ids),
    )
    return MatrixCellListOut(
        matrix_id=matrix_id,
        cell_ids=tuple(cell_ids),
        count=len(cell_ids),
    )


@router.get("/matrices/{matrix_id}/cultural-comparison")
async def get_matrix_cultural_comparison(
    matrix_id: str,
    request: Request,
    _: None = Depends(_inspect),
) -> Response:
    service = _cultural_service(request)
    document = await service.read_comparison(_validate_matrix_id(matrix_id))
    _LOGGER.info("route_matrix_cultural_comparison", matrix_id=matrix_id)
    return _artifact_response(document)


@router.get(
    "/matrices/{matrix_id}/cells/{cell_id}/cultural-evidence",
    response_model=CulturalEvidencePageOut,
)
async def get_matrix_cultural_evidence(
    matrix_id: str,
    cell_id: str,
    request: Request,
    section: str = Query(...),
    from_tick: int | None = Query(None, ge=0),
    to_tick: int | None = Query(None, ge=0),
    owner_id: str | None = Query(None),
    dimension: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    cursor: str | None = Query(None),
    _: None = Depends(_debug),
) -> CulturalEvidencePageOut:
    if section not in _SECTION_ROW_KEYS:
        raise bad_request(code="invalid_section")
    if from_tick is not None and to_tick is not None and from_tick > to_tick:
        raise bad_request(code="invalid_tick_window")
    if dimension is not None and section not in {"boundaries", "traits"}:
        raise bad_request(code="unsupported_dimension_filter")
    if owner_id is not None:
        owner_id = owner_id.strip() or None
    if dimension is not None:
        dimension = dimension.strip() or None
    mid = _validate_matrix_id(matrix_id)
    cid = _validate_cell_id(cell_id)
    service = _cultural_service(request)
    pair = await service.read_evidence_pair(mid, cid)
    filters = {
        "from_tick": from_tick,
        "to_tick": to_tick,
        "owner_id": owner_id,
        "dimension": dimension,
    }
    offset = 0
    if cursor is not None:
        codec = _cursor_codec(request)
        try:
            payload = codec.decode(cursor)
        except CulturalCursorError as exc:
            raise bad_request(code=exc.code) from None
        if (
            payload.get("matrix_id") != mid
            or payload.get("cell_id") != cid
            or payload.get("section") != section
            or payload.get("filters") != filters
        ):
            raise bad_request(code="invalid_research_cursor")
        if (
            payload.get("evidence_digest") != pair.evidence_identity["digest"]
            or payload.get("metrics_digest") != pair.metrics_identity["digest"]
        ):
            raise conflict(code="research_snapshot_changed")
        raw_offset = payload.get("offset")
        if not isinstance(raw_offset, int) or raw_offset < 0:
            raise bad_request(code="invalid_research_cursor")
        offset = raw_offset

    raw_rows = pair.evidence.get(_SECTION_ROW_KEYS[section])
    source_rows = (
        [row for row in raw_rows if isinstance(row, dict)]
        if isinstance(raw_rows, list)
        else []
    )
    filtered = _filtered_rows(
        section,
        source_rows,
        from_tick=from_tick,
        to_tick=to_tick,
        owner_id=owner_id,
        dimension=dimension,
    )
    total = len(filtered)
    page_rows = filtered[offset : offset + limit]
    if not page_rows and offset < total:
        page_rows = filtered[offset : offset + 1]
    truncated = offset + len(page_rows) < total
    next_cursor = None
    requested_window = CulturalEvidenceWindowOut(from_tick=from_tick, to_tick=to_tick)
    while True:
        page = CulturalEvidencePageOut(
            run_id=str(pair.evidence_identity["run_id"]),
            matrix_id=mid,
            cell_id=cid,
            section=section,
            artifact_digest=str(pair.evidence_identity["digest"]),
            source_revision=str(pair.evidence_identity["source_revision"]),
            binding_state=pair.binding,
            requested_window=requested_window,
            capture_status=cast(
                dict[str, object], pair.evidence_identity["capture_status"]
            ),
            gaps=tuple(cast(list[object], pair.evidence_identity["gaps"])),
            rows=tuple(page_rows),
            next_cursor=next_cursor,
            truncated=truncated,
            coverage=_coverage(
                pair,
                dimension=dimension,
                from_tick=from_tick,
                to_tick=to_tick,
            ),
        )
        encoded = page.model_dump_json().encode("utf-8")
        if len(encoded) <= 2 * 1024 * 1024:
            break
        if len(page_rows) <= 1:
            raise too_large(code="research_artifact_too_large")
        page_rows = page_rows[: max(1, len(page_rows) // 2)]
        truncated = True
        next_cursor = None
    if truncated:
        next_cursor = _cursor_codec(request).encode(
            {
                "matrix_id": mid,
                "cell_id": cid,
                "section": section,
                "evidence_digest": pair.evidence_identity["digest"],
                "metrics_digest": pair.metrics_identity["digest"],
                "filters": filters,
                "offset": offset + len(page_rows),
            }
        )
        page = page.model_copy(update={"next_cursor": next_cursor})
        if len(page.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
            raise too_large(code="research_artifact_too_large")
    _LOGGER.info(
        "route_matrix_cultural_evidence",
        matrix_id=mid,
        section=section,
        returned=len(page_rows),
        scanned=total,
    )
    return page


@router.get("/matrices/{matrix_id}/cells/{cell_id}/cultural-metrics")
async def get_matrix_cultural_metrics(
    matrix_id: str,
    cell_id: str,
    request: Request,
    _: None = Depends(_inspect),
) -> Response:
    service = _cultural_service(request)
    document = await service.read_cell_metrics(
        _validate_matrix_id(matrix_id), _validate_cell_id(cell_id)
    )
    _LOGGER.info("route_matrix_cultural_metrics", matrix_id=matrix_id)
    return _artifact_response(document)


@router.get("/matrices/{matrix_id}/cells/{cell_id}")
async def get_matrix_cell(
    matrix_id: str,
    cell_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    del request
    cid = _validate_cell_id(cell_id)
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    path = _resolve_under(matrix_dir, "cells", f"{cid}.json")
    if not path.is_file():
        raise not_found(code="matrix_file_missing")
    payload = _read_json(path)
    _LOGGER.info("route_matrix_cell", matrix_id=matrix_id)
    return JSONResponse(payload)


@router.get("/matrices/{matrix_id}/cells/{cell_id}/metrics")
async def get_matrix_cell_metrics(
    matrix_id: str,
    cell_id: str,
    request: Request,
    _: None = Depends(_inspect),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    del request
    cid = _validate_cell_id(cell_id)
    matrix_dir = _matrix_dir(_require_root(settings), matrix_id)
    path = _resolve_under(matrix_dir, "cells", f"{cid}.metrics.json")
    if not path.is_file():
        raise not_found(code="matrix_file_missing")
    payload = _read_json(path)
    _LOGGER.info("route_matrix_cell_metrics", matrix_id=matrix_id)
    return JSONResponse(payload)
