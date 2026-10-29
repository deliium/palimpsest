"""Authenticated image-owned Research UI wiring checks (not default pytest)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.compose.conftest import GenerationalStack

pytestmark = pytest.mark.compose

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_DEV = ROOT / "compose.dev.yaml"
BENCHMARK_MATRIX_FIXTURE = (
    ROOT / "tests" / "fixtures" / "matrices" / "v2-benchmark-suite.json"
)
_REQUIRED = os.environ.get("PALIMPSEST_V3_ACCEPTANCE_REQUIRED", "") == "1"


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


def test_shipped_image_serves_research_spa_without_host_dist(
    benchmark_stack: tuple[GenerationalStack, dict[str, Any]],
) -> None:
    stack, _manifest = benchmark_stack
    response = httpx.get(f"{stack.base_url}/research/", timeout=30.0)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<html" in response.text.lower()
    deep = httpx.get(
        f"{stack.base_url}/research/runs/demo/technology", timeout=30.0
    )
    assert deep.status_code == 200
    asset = httpx.get(
        f"{stack.base_url}/research/assets/missing.js", timeout=30.0
    )
    assert asset.status_code == 404


def test_shipped_image_serves_real_v2_matrix_summary(
    benchmark_stack: tuple[GenerationalStack, dict[str, Any]],
) -> None:
    stack, _manifest = benchmark_stack
    response = httpx.get(
        f"{stack.base_url}/v1/research/matrices/v2-benchmark-suite/metric-summary",
        headers={"x-palimpsest-token": stack.inspection_token},
        timeout=30.0,
    )
    if response.status_code in {404, 401, 403} and _REQUIRED:
        pytest.fail(
            f"required matrix summary unavailable status={response.status_code}"
        )
    assert response.status_code == 200
    assert response.json().get("schema_version") == "matrix-metric-summary-v1"
