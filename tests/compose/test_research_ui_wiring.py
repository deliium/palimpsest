"""Opt-in Research UI compose wiring checks (not in default pytest)."""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.compose

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_DEV = ROOT / "compose.dev.yaml"
DIST = ROOT / "clients" / "research-ui" / "dist"
BENCHMARK_MATRIX_FIXTURE = (
    ROOT / "tests" / "fixtures" / "matrices" / "v2-benchmark-suite.json"
)


def test_compose_dev_documents_research_ui_env() -> None:
    text = COMPOSE_DEV.read_text(encoding="utf-8")
    assert "PALIMPSEST_RESEARCH_WEB_ROOT" in text
    assert "PALIMPSEST_RESEARCH_MATRIX_ROOT" in text
    assert "/research/" in text


def test_benchmark_matrix_fixture_exists_for_research_ui() -> None:
    """Static gate: V2 benchmark matrix fixture is present for matrix FS mounts."""
    assert BENCHMARK_MATRIX_FIXTURE.is_file()
    text = BENCHMARK_MATRIX_FIXTURE.read_text(encoding="utf-8")
    assert "v2-benchmark-suite" in text
    assert "experiment-matrix-v1" in text
    assert "matrix-metric-summary-v1" not in text  # summary is a runtime sidecar


def test_research_ui_index_when_dist_served() -> None:
    """Smoke: when a local API already serves RESEARCH_WEB_ROOT, /research/ is HTML.

    Skips unless ``PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL`` is set (e.g.
    ``http://127.0.0.1:8080``) and ``clients/research-ui/dist/index.html`` exists.
    """
    base = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL", "").strip()
    if not base:
        pytest.skip("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL unset")
    if not (DIST / "index.html").is_file():
        pytest.skip("research-ui dist/index.html missing")
    response = httpx.get(f"{base.rstrip('/')}/research/", timeout=5.0)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "html" in response.text.lower()


def test_research_ui_matrix_metric_summary_when_mounted() -> None:
    """Smoke: allowlisted metric-summary for v2-benchmark-suite when MATRIX_ROOT is live.

    Skips unless ``PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL`` is set and the running
    stack has ``PALIMPSEST_RESEARCH_MATRIX_ROOT`` populated with that matrix id.
    """
    base = os.environ.get("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL", "").strip()
    if not base:
        pytest.skip("PALIMPSEST_COMPOSE_RESEARCH_SMOKE_URL unset")
    url = (
        f"{base.rstrip('/')}/v1/research/matrices/v2-benchmark-suite/metric-summary"
    )
    response = httpx.get(url, timeout=5.0)
    if response.status_code == 404:
        pytest.skip("v2-benchmark-suite metric-summary not mounted in this stack")
    assert response.status_code == 200
    assert response.json().get("schema_version") == "matrix-metric-summary-v1"
