# mypy: ignore-errors
"""Import and version boundaries for the social-mobility feature."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

ANALYSIS_MODULES = tuple(
    f"src/analysis/social_mobility_{name}.py"
    for name in (
        "contract",
        "policy",
        "rows",
        "genealogy",
        "outcomes",
        "detection",
        "generations",
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


def test_analysis_modules_never_import_world_state_or_kinship_graph() -> None:
    for relative in ANALYSIS_MODULES:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert "world._state" not in modules, relative
        assert "world.kinship" not in modules, relative
        assert "simulation" not in {module.split(".", 1)[0] for module in modules}, (
            relative
        )


def test_simulation_never_imports_social_mobility_analysis() -> None:
    for path in (SRC / "simulation").glob("social_mobility_*.py"):
        roots = _imports(path)
        assert "analysis" not in roots, path


def test_no_v2_route_is_added() -> None:
    pattern = re.compile(r"(prefix|@router\.get)\(\s*[\"']/v2")
    for path in list((SRC / "api").rglob("*.py")):
        assert pattern.search(path.read_text(encoding="utf-8")) is None, path


def test_no_0018_migration_exists() -> None:
    assert not list((ROOT / "alembic" / "versions").glob("0018*"))


def test_analysis_module_allowlist_matches_created_files() -> None:
    created = {path.name for path in (SRC / "analysis").glob("social_mobility_*.py")}
    expected = {Path(relative).name for relative in ANALYSIS_MODULES}
    assert created == expected


def test_no_godot_source_change_is_attributed_to_social_mobility() -> None:
    for path in (ROOT / "clients" / "godot-observer").rglob("*"):
        if path.is_file() and path.suffix in {".gd", ".tscn", ".godot"}:
            assert "social_mobility" not in path.read_text(
                encoding="utf-8", errors="ignore"
            ), path
