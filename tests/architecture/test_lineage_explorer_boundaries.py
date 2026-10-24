"""Architecture gates for the read-only lineage explorer."""

from __future__ import annotations

import ast
from pathlib import Path

_FORBIDDEN_SIMULATION = {
    "api",
    "analysis",
    "experiments",
    "persistence",
    "observer",
    "infrastructure",
}
_FORBIDDEN_API = {"analysis", "experiments"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_simulation_lineage_modules_do_not_import_outer_layers() -> None:
    for path in sorted(Path("src/simulation").glob("lineage_*.py")):
        assert not (_imports(path) & _FORBIDDEN_SIMULATION), path


def test_api_lineage_modules_do_not_import_analysis_or_experiments() -> None:
    for path in (
        Path("src/api/lineage_service.py"),
        Path("src/api/lineage_cursor.py"),
        Path("src/api/lineage_schemas.py"),
        Path("src/api/routes/lineage.py"),
    ):
        assert not (_imports(path) & _FORBIDDEN_API), path


def test_persistence_lineage_does_not_import_analysis_or_private_world() -> None:
    path = Path("src/persistence/lineage_filesystem.py")
    imports = _imports(path)
    assert "analysis" not in imports
    assert not any(name.startswith("world._") for name in imports)


def test_lineage_routes_are_get_only() -> None:
    tree = ast.parse(Path("src/api/routes/lineage.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and isinstance(
                    decorator.func, ast.Attribute
                ):
                    assert decorator.func.attr == "get", node.name
