"""V3-40 client projections stay read-only and pinned to Godot 4.7.2."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.routes.lineage import router as lineage_router
from api.routes.observer import router as observer_router

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
GODOT = ROOT / "clients" / "godot-observer"
PINS = GODOT / "export" / "pins.env"
PROJECT = GODOT / "project.godot"
EXPORT = GODOT / "export_presets.cfg"


def test_routes_remain_get_only() -> None:
    for router in (observer_router, lineage_router):
        for route in router.routes:
            methods = getattr(route, "methods", set()) or set()
            assert methods <= {"GET"}, (route.path, methods)


def test_pins_renderer_and_threads_are_unchanged() -> None:
    pins = PINS.read_text(encoding="utf-8")
    assert "GODOT_VERSION=4.7.2-stable" in pins
    assert "GODOT_LINUX_SHA512=" in pins
    assert "GODOT_TEMPLATES_SHA512=" in pins
    project = PROJECT.read_text(encoding="utf-8")
    assert "gl_compatibility" in project
    export = EXPORT.read_text(encoding="utf-8")
    assert "thread_support=false" in export


def test_client_has_no_python_or_analysis_imports() -> None:
    forbidden = (
        "res://src/",
        "WorldEngine",
        "lineage_subjective",
        "import simulation",
        "res://api/",
    )
    for path in sorted((GODOT / "scripts").rglob("*.gd")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains {token}"


def test_client_does_not_derive_generation_or_pedigree_locally() -> None:
    generational = (GODOT / "scripts" / "net" / "generational_source.gd").read_text(
        encoding="utf-8"
    )
    lineage = (GODOT / "scripts" / "net" / "lineage_source.gd").read_text(
        encoding="utf-8"
    )
    assert "generation_index" in generational
    assert "world.revision" in generational or "revision" in generational
    assert "parent_of" in lineage
    for forbidden in ("chronological_age(", "entry_tick +", "generation + 1"):
        assert forbidden not in generational + lineage


def test_credentials_are_not_persisted_or_encoded_in_urls() -> None:
    session = (GODOT / "scripts" / "net" / "session.gd").read_text(encoding="utf-8")
    assert "configure_credentials" in session
    assert "forget_credentials" in session
    configured = session.split("func configure_credentials", 1)[1]
    assert "ProjectSettings.set_setting" not in configured
    urls = (GODOT / "scripts" / "protocol" / "urls.gd").read_text(encoding="utf-8")
    assert '"token"' not in urls.split("var allowed :=", 1)[1].split("]", 1)[0]
