"""Research UI FS acceptance for V2 benchmark matrix sidecars (network-free)."""

from __future__ import annotations

import json
import logging
import shutil
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

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "matrices" / "v2-benchmark-suite.json"


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


def _install_benchmark_matrix_tree(root: Path) -> Path:
    """Allowlisted runtime tree shaped like a completed matrix under RESEARCH_MATRIX_ROOT."""
    matrix = root / "v2-benchmark-suite"
    cells = matrix / "cells"
    cells.mkdir(parents=True)
    # Research routes require experiment-matrix-v1 schema on manifest.json.
    shutil.copyfile(FIXTURE, matrix / "manifest.json")
    (matrix / "aggregate.json").write_text(
        json.dumps(
            {
                "schema_version": "matrix-aggregate-v1",
                "matrix_id": "v2-benchmark-suite",
                "cell_count": 1,
            }
        ),
        encoding="utf-8",
    )
    (matrix / "metric-summary.json").write_text(
        json.dumps(
            {
                "schema_version": "matrix-metric-summary-v1",
                "key_summaries": [],
            }
        ),
        encoding="utf-8",
    )
    (cells / "cell-bench-01.json").write_text(
        json.dumps({"cell_id": "cell-bench-01", "status": "complete"}),
        encoding="utf-8",
    )
    (cells / "cell-bench-01.metrics.json").write_text(
        json.dumps({"documents": []}),
        encoding="utf-8",
    )
    return matrix


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_research_ui_resolves_benchmark_matrix_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "matrices"
    root.mkdir()
    _install_benchmark_matrix_tree(root)
    app = _app(research_matrix_root=root)
    async with running_client(app) as client:
        listed = await client.get("/v1/research/matrices")
        assert listed.status_code == 200
        body = listed.json()
        assert body["availability"] == "available"
        assert body["count"] == 1
        assert body["items"][0]["matrix_id"] == "v2-benchmark-suite"
        assert body["items"][0]["has_aggregate"] is True
        assert body["items"][0]["has_metric_summary"] is True

        manifest = await client.get("/v1/research/matrices/v2-benchmark-suite/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["matrix_id"] == "v2-benchmark-suite"
        assert manifest.json()["schema_version"] == "experiment-matrix-v1"

        summary = await client.get(
            "/v1/research/matrices/v2-benchmark-suite/metric-summary"
        )
        assert summary.status_code == 200
        assert summary.json()["schema_version"] == "matrix-metric-summary-v1"

        aggregate = await client.get(
            "/v1/research/matrices/v2-benchmark-suite/aggregate"
        )
        assert aggregate.status_code == 200
        assert aggregate.json()["schema_version"] == "matrix-aggregate-v1"

        cells = await client.get("/v1/research/matrices/v2-benchmark-suite/cells")
        assert cells.status_code == 200
        assert "cell-bench-01" in cells.json()["cell_ids"]


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_research_web_root_unset_skips_static_mount(
    tmp_path: Path,
) -> None:
    """When RESEARCH_WEB_ROOT is unset, matrix FS still works; /research/ is not required."""
    root = tmp_path / "matrices"
    root.mkdir()
    _install_benchmark_matrix_tree(root)
    app = _app(research_matrix_root=root, research_web_root=None)
    async with running_client(app) as client:
        listed = await client.get("/v1/research/matrices")
        assert listed.status_code == 200
        assert listed.json()["count"] == 1
        # Static SPA mount absent — no crash; 404 without HTML shell is fine.
        page = await client.get("/research/")
        assert page.status_code in {404, 307, 308}


@pytest.mark.usefixtures("logging_sandbox")
@pytest.mark.asyncio
async def test_research_web_root_serves_index_when_dist_present(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html></html>", encoding="utf-8")
    root = tmp_path / "matrices"
    root.mkdir()
    _install_benchmark_matrix_tree(root)
    app = _app(research_web_root=dist, research_matrix_root=root)
    async with running_client(app) as client:
        response = await client.get("/research/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "html" in response.text.lower()
