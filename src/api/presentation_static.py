"""Serve an already-exported presentation tree from the API origin.

The tree is a directory of static files. This module does not build it.
"""

from __future__ import annotations

import json
import os
import stat
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from infrastructure.logging import get_logger
from infrastructure.settings import Settings
from observer.version import OBSERVER_PROTOCOL_VERSION

_LOGGER = get_logger("api.presentation")
_FORCED_MEDIA_TYPES: Final[dict[str, str]] = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".wasm": "application/wasm",
    ".pck": "application/octet-stream",
}
_logged_protocol_mismatches: set[str] = set()


class PresentationFiles(StaticFiles):
    """Static files with forced media types and no directory listing."""

    def file_response(
        self,
        full_path: str | os.PathLike[str],
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        if isinstance(response, FileResponse):
            suffix = Path(str(full_path)).suffix.lower()
            media_type = _FORCED_MEDIA_TYPES.get(suffix)
            if media_type is not None:
                response.media_type = media_type
                response.headers["content-type"] = media_type
        return response

    async def get_response(self, path: str, scope: Scope) -> Response:
        if path in {"", "."}:
            full_path, stat_result = self.lookup_path("index.html")
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                return self.file_response(full_path, stat_result, scope)
            _log_missing("index.html")
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404:
                _log_missing(path)
            raise


def _log_missing(path: str) -> None:
    name = Path(path).name
    suffix = name if name not in {"", ".", ".."} else "unknown"
    _LOGGER.warning("presentation_static_missing", path_suffix=suffix)


def presentation_root(settings: Settings) -> Path | None:
    root = settings.presentation_web_root
    if root is None:
        return None
    return Path(root)


def note_protocol_mismatch(baked: str) -> None:
    if baked == OBSERVER_PROTOCOL_VERSION or baked in _logged_protocol_mismatches:
        return
    _logged_protocol_mismatches.add(baked)
    _LOGGER.error(
        "presentation_protocol_mismatch",
        expected=OBSERVER_PROTOCOL_VERSION,
        baked=baked,
    )


def read_build_info(root: Path | None) -> dict[str, object]:
    if root is None or not root.is_dir():
        return {}
    path = root / "build-info.json"
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _LOGGER.error(
            "presentation_static_skipped",
            reason_code="build_info_invalid",
        )
        return {}
    if not isinstance(loaded, dict):
        _LOGGER.error(
            "presentation_static_skipped",
            reason_code="build_info_invalid",
        )
        return {}
    baked = loaded.get("protocol_version")
    if isinstance(baked, str):
        note_protocol_mismatch(baked)
    return loaded


def _optional_text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def version_payload(settings: Settings) -> dict[str, str | bool | None]:
    from api.research_static import research_ui_configured

    try:
        application_version = version("palimpsest")
    except PackageNotFoundError:
        application_version = "unknown"
        _LOGGER.error(
            "presentation_static_skipped",
            reason_code="distribution_version_missing",
        )
    info = read_build_info(presentation_root(settings))
    revision = settings.revision or _optional_text(info.get("revision"))
    research_configured = research_ui_configured(settings)
    _LOGGER.debug(
        "version_payload_built",
        has_export_engine=_optional_text(info.get("export_engine")) is not None,
        has_revision=revision is not None,
        research_ui_configured=research_configured,
    )
    return {
        "application_version": application_version,
        "protocol_version": OBSERVER_PROTOCOL_VERSION,
        "export_engine": _optional_text(info.get("export_engine")),
        "export_renderer": _optional_text(info.get("export_renderer")),
        "revision": revision,
        "research_ui_configured": research_configured,
    }


def mount_presentation(app: FastAPI, settings: Settings) -> None:
    """Mount the export directory at ``/`` after API routes, or skip it."""
    root = presentation_root(settings)
    if root is None:
        _LOGGER.debug("presentation_static_skipped", reason_code="root_unset")
        return
    if not root.is_dir() or not (root / "index.html").is_file():
        _LOGGER.error("presentation_static_skipped", reason_code="index_missing")
        return
    read_build_info(root)
    file_count = sum(1 for item in root.rglob("*") if item.is_file())
    app.mount(
        "/",
        PresentationFiles(directory=root, html=False),
        name="presentation",
    )
    _LOGGER.info("presentation_static_mounted", file_count=file_count)
