# mypy: ignore-errors
"""Import and authority boundaries for the economic-cascade feature."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

ANALYSIS_MODULES = tuple(
    f"src/analysis/economic_cascades_{name}.py"
    for name in (
        "contract",
        "policy",
        "rows",
        "events",
        "dependencies",
        "detection",
        "chains",
        "analysis",
        "metrics",
    )
)
FORBIDDEN_ANALYSIS_ROOTS = {
    "api",
    "persistence",
    "experiments",
    "infrastructure",
    "observer",
    "simulation",
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
        assert (ROOT / relative).exists(), relative
        roots = _imports(ROOT / relative)
        assert roots & FORBIDDEN_ANALYSIS_ROOTS == set(), relative


def test_analysis_modules_never_import_private_world_state() -> None:
    for relative in ANALYSIS_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "world._state" not in modules, relative
        assert "world.kinship" not in modules, relative


def test_simulation_modules_import_no_analysis_or_outer_layer() -> None:
    for path in (SRC / "simulation").glob("economic_cascades_*.py"):
        roots = _imports(path)
        assert "analysis" not in roots, path
        assert not (roots & {"api", "experiments", "persistence", "infrastructure"})


def test_experiments_modules_import_no_api_or_concrete_persistence() -> None:
    for path in (SRC / "experiments").glob("economic_cascades_*.py"):
        roots = _imports(path)
        assert "api" not in roots, path
        assert "persistence" not in roots, path


def test_no_module_returns_or_submits_an_agent_command() -> None:
    for relative in ANALYSIS_MODULES:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "AgentCommand" not in source, relative
        assert not re.search(r"class\s+\w+Command\b", source), relative


def test_no_v2_route_is_added() -> None:
    pattern = re.compile(r"(prefix|@router\.get)\(\s*[\"']/v2")
    for path in list((SRC / "api").rglob("*.py")):
        assert pattern.search(path.read_text(encoding="utf-8")) is None, path


def test_no_0018_migration_exists() -> None:
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))
