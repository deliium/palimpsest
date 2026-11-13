# mypy: ignore-errors
"""Import and version boundaries for the economic-inequality feature."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

ANALYSIS_MODULES = (
    "src/analysis/economic_inequality_contract.py",
    "src/analysis/economic_inequality_policy.py",
    "src/analysis/economic_inequality_rows.py",
    "src/analysis/economic_inequality_events.py",
    "src/analysis/economic_inequality_claims.py",
    "src/analysis/inequality_indices.py",
    "src/analysis/economic_inequality_detection.py",
    "src/analysis/economic_inequality_comparisons.py",
    "src/analysis/economic_inequality_analysis.py",
    "src/analysis/economic_inequality_metrics.py",
)
FORBIDDEN_ANALYSIS_ROOTS = {
    "api",
    "persistence",
    "experiments",
    "infrastructure",
    "observer",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


def test_analysis_modules_import_no_outer_layer() -> None:
    for relative in ANALYSIS_MODULES:
        roots = _imports(ROOT / relative)
        assert roots & FORBIDDEN_ANALYSIS_ROOTS == set(), relative


def test_analysis_modules_never_import_world_state() -> None:
    for relative in ANALYSIS_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "world._state" not in modules, relative
        assert not any(module.endswith("_state") for module in modules), relative


def test_simulation_never_imports_economic_analysis() -> None:
    for path in (SRC / "simulation").glob("economic_inequality_*.py"):
        roots = _imports(path)
        assert "analysis" not in roots, path


def test_no_v2_route_is_added() -> None:
    import re

    pattern = re.compile(r"(prefix|@router\.get)\(\s*[\"']/v2")
    for path in list((SRC / "api").rglob("*.py")):
        assert pattern.search(path.read_text(encoding="utf-8")) is None, path


def test_no_0018_migration_exists() -> None:
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
