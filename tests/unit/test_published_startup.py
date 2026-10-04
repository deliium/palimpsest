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
        assert "export template" not in text.lower()
        assert "--export-release" not in text
        assert "compose up --build" not in text
        assert "up -d --build" not in text
        assert "up --build" not in text


def test_published_compose_documents_api_image_requirement() -> None:
    text = COMPOSE.read_text(encoding="utf-8")
    assert "PALIMPSEST_API_IMAGE" in text
    docs = _text("docs/development.md")
    assert "PALIMPSEST_API_IMAGE" in docs
    # Zero-install path: Docker + browser only; no host Godot install step.
    run_sh = _text("run.sh")
    assert "docker" in run_sh.lower()
    assert "godot" not in run_sh.lower()


def test_live_stack_pulls_the_database_before_never() -> None:
    text = _text("tests/compose/test_stack.py")
    fixture = text.split("def running_stack", 1)[1]
    pull_at = fixture.find('"pull"')
    never_at = fixture.find('"never"')
    assert pull_at != -1
    assert never_at != -1
    assert pull_at < never_at
    assert "database_image_pull" in fixture


def test_protocol_job_installs_export_stage_libraries() -> None:
    text = _text(".github/workflows/observer-image.yml")
    job = text.split("protocol:", 1)[1].split("\n  image:", 1)[0]
    for package in ("libdbus-1-3", "libegl1", "libxkbcommon0"):
        assert package in job
    assert ".tpz" not in job
    assert "observer_protocol_libs_ok" in job


def test_revision_is_documented() -> None:
    docs = _text("docs/development.md")
    example = _text(".env.example")
    assert "PALIMPSEST_REVISION" in docs
    assert "PALIMPSEST_REVISION" in example


def test_run_dev_is_the_local_build() -> None:
    text = _text("run-dev.sh")
    assert "compose.dev.yaml" in text
    assert "--build" in text
    dev = DEV_COMPOSE.read_text(encoding="utf-8")
    assert "network: host" in dev
    assert "PALIMPSEST_REVISION" in dev
    assert "compose.override.yaml" not in text
