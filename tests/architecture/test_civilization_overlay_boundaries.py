"""Prove civilization presentation never widens authority or read/write scope."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def _civilization_modules() -> list[Path]:
    paths: list[Path] = []
    for root in (SRC / "simulation", SRC / "api", SRC / "persistence"):
        paths.extend(sorted(root.glob("*civilization*.py")))
    paths.extend(sorted((SRC / "api" / "routes").glob("*civilization*.py")))
    return paths


def _has_prefix(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def test_read_paths_never_import_analysis_experiments_or_adapters() -> None:
    for path in _civilization_modules():
        forbidden: tuple[str, ...] = (
            "analysis", "experiments", "infrastructure", "observer"
        )
        if path.parent.name == "persistence":
            forbidden = ("analysis", "experiments", "observer")
        if path.parent.name == "api" or path.parent.name == "routes":
            forbidden = ("analysis", "experiments")
        hits = [
            f"{path.relative_to(SRC)}:{imported}"
            for imported in _imports(path)
            for prefix in forbidden
            if _has_prefix(imported, prefix)
        ]
        assert hits == [], hits


def test_simulation_civilization_contracts_stay_framework_free() -> None:
    forbidden = (
        "fastapi",
        "starlette",
        "pydantic",
        "pydantic_core",
        "sqlalchemy",
        "alembic",
        "asyncpg",
        "api",
        "persistence",
    )
    for path in sorted((SRC / "simulation").glob("*civilization*.py")):
        hits = [
            f"{path.name}:{imported}"
            for imported in _imports(path)
            for prefix in forbidden
            if _has_prefix(imported, prefix)
        ]
        assert hits == [], hits


def test_only_trusted_composers_cross_capture_to_analysis() -> None:
    experiment = (SRC / "experiments" / "civilization_publication.py").read_text(
        encoding="utf-8"
    )
    assert "analysis.civilization_overlays" in experiment
    assert "api" not in {name.split(".")[0] for name in _imports(
        SRC / "experiments" / "civilization_publication.py"
    )}
    producer = (SRC / "research_runner" / "civilization_composition.py").read_text(
        encoding="utf-8"
    )
    assert "experiments.civilization_publication" in producer
    assert "api" not in {name.split(".")[0] for name in _imports(
        SRC / "research_runner" / "civilization_composition.py"
    )}


def test_reader_and_publisher_capabilities_are_distinct(tmp_path: Path) -> None:
    from persistence.civilization_filesystem import (
        create_civilization_publisher,
        create_civilization_reader,
    )

    publisher = create_civilization_publisher(tmp_path)
    reader = create_civilization_reader(tmp_path)
    assert type(publisher) is not type(reader)
    assert hasattr(publisher, "publish_boundary")
    assert hasattr(publisher, "seal_catalogue")
    assert not hasattr(reader, "publish_boundary")
    assert not hasattr(reader, "seal_catalogue")


def test_civilization_routes_are_get_only() -> None:
    from fastapi.routing import APIRoute

    from api.routes.civilization import router

    routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute) and "/observer/civilization/" in route.path
    ]
    assert routes
    assert all(route.methods == {"GET"} for route in routes)
    assert all(
        route.path.endswith(("/map", "/catalogue", "/overlays", "/markers"))
        for route in routes
    )


def test_python_never_imports_or_serves_the_godot_client_source() -> None:
    hits: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "clients.godot-observer" in text or "clients/godot-observer" in text:
            hits.append(str(path.relative_to(SRC)))
    assert hits == []
