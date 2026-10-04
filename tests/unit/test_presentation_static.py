"""Same-origin presentation files and the version route."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import api.presentation_static as presentation_static
from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings
from observer.version import OBSERVER_PROTOCOL_VERSION

pytestmark = pytest.mark.unit


class FakeEngine:
    async def dispose(self) -> None:
        return None


class FakeResources:
    def __init__(self, engine: DisposableEngine) -> None:
        self.engine = engine


@pytest.fixture
def logging_sandbox() -> Iterator[None]:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    presentation_static._logged_protocol_mismatches.clear()
    try:
        yield
    finally:
        presentation_static._logged_protocol_mismatches.clear()
        reset_logging_for_tests(original_handlers, original_level)


def _factory(_settings: Settings) -> DatabaseResourcesLike:
    return FakeResources(engine=FakeEngine())


def _settings(**overrides: object) -> Settings:
    return load_settings(env_file=False, **overrides)


def _app(**overrides: object) -> FastAPI:
    return create_app(settings=_settings(**overrides), database_factory=_factory)


@asynccontextmanager
async def running_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


def _write_tree(root: Path, *, protocol: str = OBSERVER_PROTOCOL_VERSION) -> None:
    root.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><title>observer</title>",
        encoding="utf-8",
    )
    (root / "index.js").write_text("console.log('ready')", encoding="utf-8")
    (root / "index.wasm").write_bytes(b"\0asm" + b"x" * 32)
    (root / "index.pck").write_bytes(b"GDPC")
    (root / "icon.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\0" * 16
    )
    (root / "nested").mkdir()
    (root / "build-info.json").write_text(
        (
            '{"application_version":"0.1.0",'
            f'"protocol_version":"{protocol}",'
            '"export_engine":"4.7.2-stable",'
            '"export_renderer":"gl_compatibility",'
            '"revision":"from-file"}'
        ),
        encoding="utf-8",
    )


async def test_static_mount_serves_index_and_typed_assets(
    logging_sandbox: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "web"
    _write_tree(root)
    with caplog.at_level(logging.INFO):
        app = _app(presentation_web_root=root)
    assert "presentation_static_mounted" in caplog.text
    async with running_client(app) as client:
        page = await client.get("/")
        script = await client.get("/index.js")
        wasm = await client.get("/index.wasm")
        pack = await client.get("/index.pck")
        icon = await client.get("/icon.png")
        health = await client.get("/health")
        missing = await client.get("/missing-texture.bin")
    assert page.status_code == 200
    assert page.headers["content-type"] == "text/html"
    assert "observer" in page.text
    assert script.headers["content-type"] == "text/javascript"
    assert wasm.headers["content-type"] == "application/wasm"
    assert wasm.content.startswith(b"\0asm")
    assert pack.headers["content-type"] == "application/octet-stream"
    assert icon.headers["content-type"].startswith("image/png")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert missing.status_code == 404
    for response in (page, script, wasm, pack, health):
        lowered = {name.lower() for name in response.headers}
        assert "cross-origin-opener-policy" not in lowered
        assert "cross-origin-embedder-policy" not in lowered


async def test_parent_segments_stay_inside_the_export_directory(
    logging_sandbox: None, tmp_path: Path
) -> None:
    root = tmp_path / "web"
    _write_tree(root)
    secret = tmp_path / "secret.txt"
    secret.write_text("token-should-stay-hidden", encoding="utf-8")
    (root / "escape").symlink_to(secret)
    app = _app(presentation_web_root=root)
    files = presentation_static.PresentationFiles(directory=root, html=False)
    assert files.lookup_path("../secret.txt") == ("", None)
    assert files.lookup_path("escape")[1] is None
    async with running_client(app) as client:
        response = await client.get("/escape")
        traversed = await client.get("/../secret.txt")
    assert response.status_code == 404
    assert traversed.status_code == 404
    assert secret.read_text(encoding="utf-8") not in response.text
    assert secret.read_text(encoding="utf-8") not in traversed.text


async def test_missing_static_path_logs_the_suffix_only(
    logging_sandbox: None,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "web"
    _write_tree(root)
    app = _app(presentation_web_root=root)
    with caplog.at_level(logging.WARNING):
        async with running_client(app) as client:
            response = await client.get("/sprites/missing.png?token=secret")
    assert response.status_code == 404
    assert "presentation_static_missing" in caplog.text
    assert "path_suffix" in caplog.text
    assert "missing.png" in caplog.text
    assert "token" not in caplog.text
    assert "secret" not in caplog.text


async def test_unset_or_missing_root_leaves_the_api_unchanged(
    logging_sandbox: None,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        unset = _app(log_level="DEBUG")
    assert "reason_code" in caplog.text
    assert "root_unset" in caplog.text
    caplog.clear()
    empty = tmp_path / "empty"
    empty.mkdir()
    with caplog.at_level(logging.ERROR):
        missing = _app(presentation_web_root=empty)
    assert "index_missing" in caplog.text
    async with running_client(unset) as client:
        health = await client.get("/health")
        page = await client.get("/")
    assert health.json() == {"status": "ok"}
    assert page.status_code == 404
    async with running_client(missing) as client:
        health = await client.get("/health")
    assert health.json() == {"status": "ok"}


async def test_version_uses_distribution_revision_and_build_info(
    logging_sandbox: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "web"
    _write_tree(root)
    app = _app(presentation_web_root=root, revision="abc123")
    with caplog.at_level(logging.INFO):
        async with running_client(app) as client:
            response = await client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol_version"] == OBSERVER_PROTOCOL_VERSION
    assert body["export_engine"] == "4.7.2-stable"
    assert body["export_renderer"] == "gl_compatibility"
    assert body["revision"] == "abc123"
    assert body["application_version"]
    assert set(body) == {
        "application_version",
        "protocol_version",
        "export_engine",
        "export_renderer",
        "revision",
        "research_ui_configured",
    }
    assert body["research_ui_configured"] is False
    assert "route_version" in caplog.text
    assert "status" in caplog.text
    assert "duration" in caplog.text
    assert "token" not in caplog.text


async def test_version_revision_falls_back_to_build_info(
    logging_sandbox: None, tmp_path: Path
) -> None:
    root = tmp_path / "web"
    _write_tree(root)
    app = _app(presentation_web_root=root)
    async with running_client(app) as client:
        response = await client.get("/version")
    assert response.json()["revision"] == "from-file"
    assert response.json()["export_engine"] == "4.7.2-stable"


async def test_protocol_mismatch_is_logged_and_files_still_serve(
    logging_sandbox: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    root = tmp_path / "web"
    _write_tree(root, protocol="observer-protocol-other")
    with caplog.at_level(logging.ERROR):
        app = _app(presentation_web_root=root)
    assert "presentation_protocol_mismatch" in caplog.text
    assert OBSERVER_PROTOCOL_VERSION in caplog.text
    assert "observer-protocol-other" in caplog.text
    async with running_client(app) as client:
        page = await client.get("/")
        version = await client.get("/version")
    assert page.status_code == 200
    assert version.json()["protocol_version"] == OBSERVER_PROTOCOL_VERSION
    assert version.json()["export_engine"] == "4.7.2-stable"
