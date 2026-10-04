"""Read-only experiment-matrix filesystem API (objective_inspection).

Serves allowlisted JSON under ``PALIMPSEST_RESEARCH_MATRIX_ROOT`` without
importing ``analysis`` or starting matrix batches.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.dependencies import get_settings
from api.errors import bad_request, not_found, service_unavailable
from api.schemas import AvailabilityOut, StrictModel
from api.security import ApiCapability, require_http_capability
from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from pydantic import Field

router = APIRouter(prefix="/v1/research", tags=["research-matrix"])
_LOGGER = get_logger("api.routes.research_matrix")

_MATRIX_SCHEMA: Final[str] = "experiment-matrix-v1"
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
        if schema != _MATRIX_SCHEMA:
            _LOGGER.warning(
                "matrix_fs_rejected",
                reason_code="unsupported_matrix_schema",
            )
            continue
        items.append(
            MatrixListItemOut(
                matrix_id=child.name,
                schema_version=schema,
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
    schema = _manifest_schema(payload)
    if schema != _MATRIX_SCHEMA:
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
    if cells_dir.is_dir():
        for path in sorted(cells_dir.iterdir(), key=lambda p: p.name):
            if not path.is_file():
                continue
            name = path.name
            if name.endswith(".metrics.json"):
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
