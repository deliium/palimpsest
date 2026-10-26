"""Prove the generational research read surface stays read-only and bounded."""

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


def _has_prefix(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + ".")


def _api_modules() -> list[Path]:
    return [
        *(SRC / "api").glob("research_cultural_*.py"),
        *(SRC / "api").glob("semantic_history_*.py"),
        SRC / "api" / "routes" / "research_matrix.py",
        SRC / "api" / "routes" / "observer.py",
    ]


def test_api_read_surface_never_imports_analysis_or_experiments() -> None:
    for path in _api_modules():
        hits = [
            f"{path.relative_to(SRC)}:{name}"
            for name in _imports(path)
            if _has_prefix(name, "analysis") or _has_prefix(name, "experiments")
        ]
        assert hits == [], hits


def test_semantic_projection_is_detached_from_cognition_and_adapters() -> None:
    forbidden = (
        "agents",
        "analysis",
        "experiments",
        "api",
        "persistence",
        "infrastructure",
        "fastapi",
        "pydantic",
        "sqlalchemy",
    )
    path = SRC / "observer" / "semantic_history.py"
    hits = [
        f"{path.name}:{name}"
        for name in _imports(path)
        for prefix in forbidden
        if _has_prefix(name, prefix)
    ]
    assert hits == [], hits


def test_research_read_modules_contain_no_filesystem_writes() -> None:
    write_markers = (
        "write_text(",
        "write_bytes(",
        "os.replace(",
        "mkdir(",
        "unlink(",
        "tempfile.",
    )
    for path in [
        *(SRC / "api").glob("research_cultural_*.py"),
        SRC / "api" / "routes" / "research_matrix.py",
    ]:
        text = path.read_text(encoding="utf-8")
        hits = [marker for marker in write_markers if marker in text]
        assert hits == [], (path.name, hits)


def test_python_never_imports_client_trees() -> None:
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        hits = [
            f"{path.relative_to(SRC)}:{name}"
            for name in _imports(path)
            if _has_prefix(name, "clients")
        ]
        assert hits == [], hits
