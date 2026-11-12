"""AST import boundaries for the V4-22 credit relationship seam."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def _modules(pattern: str, package: str) -> Iterator[Path]:
    """Yield credit modules whose parent package matches ``package``."""
    for path in SRC.rglob(pattern):
        if path.parts[-2] == package:
            yield path


def _assert_no(path: Path, forbidden: tuple[str, ...]) -> None:
    for module in _imports(path):
        assert not module.startswith(forbidden), f"{path.name}: {module}"


def test_world_credit_codec_imports_only_world_communications() -> None:
    path = SRC / "world" / "credit_relationships.py"
    for module in _imports(path):
        assert module == "world.communications" or module.split(".")[0] in {
            "__future__",
            "collections",
            "dataclasses",
            "enum",
            "logging",
            "re",
            "types",
            "typing",
        } or module.startswith("world.communications"), f"{path.name}: {module}"


def test_cognition_credit_modules_stay_inward() -> None:
    for path in _modules("*credit_relationship*.py", "cognition"):
        _assert_no(
            path,
            ("simulation", "analysis", "experiments", "persistence", "api", "observer"),
        )


def test_analysis_credit_modules_have_no_live_authority() -> None:
    for path in _modules("credit_relationships_*.py", "analysis"):
        _assert_no(
            path,
            (
                "agents.cognition",
                "simulation",
                "experiments",
                "persistence",
                "api",
                "observer",
            ),
        )


def test_simulation_credit_modules_do_not_import_outer_layers() -> None:
    for path in _modules("credit_relationships_*.py", "simulation"):
        _assert_no(
            path, ("analysis", "experiments", "persistence", "api", "observer")
        )


def test_experiments_credit_modules_avoid_api_and_concrete_persistence() -> None:
    for path in _modules("credit_relationship*.py", "experiments"):
        _assert_no(path, ("api", "infrastructure", "persistence"))


def test_persistence_store_avoids_analysis_api_and_experiments() -> None:
    path = SRC / "persistence" / "credit_relationships_filesystem.py"
    _assert_no(path, ("analysis", "api", "experiments"))


def test_api_routes_do_not_import_analysis_or_publishers() -> None:
    path = SRC / "api" / "routes" / "credit_relationships.py"
    _assert_no(path, ("analysis", "experiments"))
    text = path.read_text(encoding="utf-8")
    assert "publisher" not in text.lower()


def test_python_never_imports_either_client() -> None:
    for path in SRC.rglob("*.py"):
        for module in _imports(path):
            assert not module.startswith("clients"), (path.name, module)
            assert "godot_observer" not in module, (path.name, module)
