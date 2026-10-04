"""Serve the built Research UI SPA from the API origin at ``/research/``.

The tree is a directory of static files (Vite ``dist/``). This module does not
build it. Mount before the Godot presentation catch-all at ``/``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Final

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from infrastructure.logging import get_logger
from infrastructure.settings import Settings

_LOGGER = get_logger("api.research_static")
_FORCED_MEDIA_TYPES: Final[dict[str, str]] = {
    ".html": "text/html",
    ".js": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".wasm": "application/wasm",
}


class ResearchUiFiles(StaticFiles):
    """Static SPA files with HTML5 history fallback and forced media types."""

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
            return self._index_response(scope)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            # SPA fallback: client routes under /research/* → index.html
            if "." not in Path(path).name:
                return self._index_response(scope)
            _log_missing(path)
            raise

    def _index_response(self, scope: Scope) -> Response:
        full_path, stat_result = self.lookup_path("index.html")
        if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
            return self.file_response(full_path, stat_result, scope)
        _LOGGER.error(
            "research_static_skipped",
            reason_code="index_missing",
        )
        raise HTTPException(status_code=404)


def _log_missing(path: str) -> None:
    name = Path(path).name
    suffix = name if name not in {"", ".", ".."} else "unknown"
    _LOGGER.warning("research_static_missing", path_suffix=suffix)


def research_ui_root(settings: Settings) -> Path | None:
    root = settings.research_web_root
    if root is None:
        return None
    return Path(root)


def research_ui_configured(settings: Settings) -> bool:
    root = research_ui_root(settings)
    if root is None:
        return False
    return root.is_dir() and (root / "index.html").is_file()


def mount_research_ui(app: FastAPI, settings: Settings) -> None:
    """Mount the Research UI at ``/research`` before presentation ``/``."""
    root = research_ui_root(settings)
    if root is None:
        _LOGGER.debug("research_static_skipped", reason_code="root_unset")
        return
    if not root.is_dir() or not (root / "index.html").is_file():
        _LOGGER.error("research_static_skipped", reason_code="index_missing")
        return
    file_count = sum(1 for item in root.rglob("*") if item.is_file())
    app.mount(
        "/research",
        ResearchUiFiles(directory=root, html=False),
        name="research_ui",
    )
    _LOGGER.info(
        "research_static_mounted",
        path_suffix="research",
        file_count=file_count,
    )
