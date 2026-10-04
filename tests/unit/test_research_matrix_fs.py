"""Read-only research matrix filesystem API."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

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


def _write_matrix(root: Path, matrix_id: str = "demo-matrix") -> Path:
    matrix = root / matrix_id
    cells = matrix / "cells"
    cells.mkdir(parents=True)
    (matrix / "manifest.json").write_text(
        json.dumps({"schema_version": "experiment-matrix-v1", "matrix_id": matrix_id}),
        encoding="utf-8",
    )
    (matrix / "aggregate.json").write_text(
        json.dumps({"schema_version": "matrix-aggregate-v1", "cell_count": 1}),
        encoding="utf-8",
    )
    (matrix / "metric-summary.json").write_text(
        json.dumps({"schema_version": "matrix-metric-summary-v1"}),
        encoding="utf-8",
    )
    (cells / "cell-a.json").write_text(
        json.dumps({"cell_id": "cell-a", "status": "complete"}),
        encoding="utf-8",
    )
    (cells / "cell-a.metrics.json").write_text(
        json.dumps({"documents": []}),
        encoding="utf-8",
    )
    return matrix


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_matrix_list_and_allowlisted_files(tmp_path: Path) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_matrix(root)
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        listed = await client.get("/v1/research/matrices")
        assert listed.status_code == 200
        body = listed.json()
        assert body["count"] == 1
        assert body["items"][0]["matrix_id"] == "demo-matrix"
        assert body["items"][0]["has_aggregate"] is True

        manifest = await client.get("/v1/research/matrices/demo-matrix/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["schema_version"] == "experiment-matrix-v1"

        cells = await client.get("/v1/research/matrices/demo-matrix/cells")
        assert cells.status_code == 200
        assert cells.json()["cell_ids"] == ["cell-a"]

        cell = await client.get("/v1/research/matrices/demo-matrix/cells/cell-a")
        assert cell.status_code == 200
        assert cell.json()["cell_id"] == "cell-a"


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_matrix_path_traversal_rejected(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _write_matrix(root)
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        with caplog.at_level(logging.WARNING):
            # Invalid matrix id with traversal tokens.
            bad = await client.get("/v1/research/matrices/../secret/manifest")
        assert bad.status_code in {400, 404}
        assert "matrix_fs_rejected" in caplog.text or bad.status_code == 404


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_matrix_root_unset_lists_unavailable() -> None:
    app = _app(research_matrix_root=None)
    async with running_client(app) as client:
        listed = await client.get("/v1/research/matrices")
        assert listed.status_code == 200
        body = listed.json()
        assert body["availability"] == "unavailable"
        assert body["count"] == 0
