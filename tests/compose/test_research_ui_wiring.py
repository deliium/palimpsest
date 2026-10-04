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


def test_compose_dev_documents_research_ui_env() -> None:
    text = COMPOSE_DEV.read_text(encoding="utf-8")
    assert "PALIMPSEST_RESEARCH_WEB_ROOT" in text
    assert "PALIMPSEST_RESEARCH_MATRIX_ROOT" in text
    assert "/research/" in text


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
