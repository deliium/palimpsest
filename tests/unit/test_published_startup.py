"""Published startup stays a pull, not a local editor build."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "compose.yaml"
DEV_COMPOSE = ROOT / "compose.dev.yaml"
PUBLISHED_IMAGE = "${PALIMPSEST_API_IMAGE:-ghcr.io/deliium/palimpsest:0.1.0}"


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_published_compose_uses_the_pinned_image_without_a_build() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert text.count(f"image: {PUBLISHED_IMAGE}") == 2
    assert "build:" not in text
    assert ":latest" not in text
    assert "latest" not in text
    assert "pgvector/pgvector:0.8.6-pg17@sha256:" in text


def test_published_launchers_do_not_export_or_build() -> None:
    for name in ("run.sh", "run.ps1", "scripts/up.sh"):
        text = _text(name)
        assert "godot" not in text.lower()
        assert "--export-release" not in text
        assert "compose up --build" not in text
        assert "up -d --build" not in text
        assert "up --build" not in text


def test_run_dev_is_the_local_build() -> None:
    text = _text("run-dev.sh")
    assert "compose.dev.yaml" in text
    assert "--build" in text
    dev = DEV_COMPOSE.read_text(encoding="utf-8")
    assert "network: host" in dev
    assert "PALIMPSEST_REVISION" in dev
    assert "compose.override.yaml" not in text
