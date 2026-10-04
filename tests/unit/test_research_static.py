"""Research UI static mount order and version flag."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import api.research_static as research_static
from api.app import DatabaseResourcesLike, DisposableEngine, create_app
from infrastructure.logging import reset_logging_for_tests
from infrastructure.settings import Settings, load_settings

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
    try:
        yield
    finally:
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


def _write_research_tree(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><title>research</title><div id='app'></div>",
        encoding="utf-8",
    )
    (root / "assets").mkdir()
    (root / "assets" / "app.js").write_text("console.log('research')", encoding="utf-8")


def _write_presentation_tree(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "index.html").write_text(
        "<!doctype html><title>observer</title>",
        encoding="utf-8",
    )


async def test_research_and_v1_win_over_presentation(
    logging_sandbox: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    research = tmp_path / "research"
    presentation = tmp_path / "presentation"
    _write_research_tree(research)
    _write_presentation_tree(presentation)
    with caplog.at_level(logging.INFO):
        app = _app(
            research_web_root=research,
            presentation_web_root=presentation,
        )
    assert "research_static_mounted" in caplog.text
    assert "path_suffix" in caplog.text
    async with running_client(app) as client:
        research_page = await client.get("/research/")
        spa_route = await client.get("/research/runs/demo")
        health = await client.get("/health")
        version = await client.get("/version")
        godot = await client.get("/")
        v1 = await client.get("/v1/simulations")
    assert research_page.status_code == 200
    assert "research" in research_page.text
    assert spa_route.status_code == 200
    assert "research" in spa_route.text
    assert health.status_code == 200
    assert version.json()["research_ui_configured"] is True
    assert godot.status_code == 200
    assert "observer" in godot.text
    # Control list may 401/403/200 depending on auth; must not be presentation HTML.
    assert v1.status_code != 404
    assert "observer" not in v1.text


async def test_missing_research_index_skips_mount(
    logging_sandbox: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with caplog.at_level(logging.ERROR):
        app = _app(research_web_root=empty)
    assert "research_static_skipped" in caplog.text
    assert "index_missing" in caplog.text
    async with running_client(app) as client:
        missing = await client.get("/research/")
        version = await client.get("/version")
    assert missing.status_code == 404
    assert version.json()["research_ui_configured"] is False


async def test_unset_research_root_leaves_api_unchanged(
    logging_sandbox: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        app = _app(log_level="DEBUG")
    assert "root_unset" in caplog.text
    async with running_client(app) as client:
        health = await client.get("/health")
        research = await client.get("/research/")
        version = await client.get("/version")
    assert health.json() == {"status": "ok"}
    assert research.status_code == 404
    assert version.json()["research_ui_configured"] is False
    assert research_static.research_ui_configured(_settings()) is False
