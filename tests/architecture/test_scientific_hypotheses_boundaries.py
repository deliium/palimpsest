# mypy: ignore-errors
"""Import and wire-surface boundaries for V4-27 scientific hypotheses."""

from __future__ import annotations

import ast
from pathlib import Path

from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_analysis_feature_modules_import_no_outer_or_owner_layer() -> None:
    for path in SRC.glob("analysis/scientific_hypotheses_*.py"):
        modules = _imports(path)
        for module in modules:
            root = module.split(".", 1)[0]
            assert root not in {
                "agents",
                "api",
                "persistence",
                "experiments",
                "infrastructure",
                "observer",
            }, (path, module)
            assert module not in {"world._experiment_laws", "world._rules"}, path


def test_simulation_feature_modules_import_no_analysis_or_outer_layer() -> None:
    for path in SRC.glob("simulation/scientific_hypotheses_*.py"):
        for module in _imports(path):
            root = module.split(".", 1)[0]
            assert root not in {"analysis", "api", "persistence", "experiments"}, (
                path,
                module,
            )
            assert module != "world._experiment_laws", path


def test_experiments_feature_modules_import_no_api_or_concrete_store() -> None:
    for path in SRC.glob("experiments/scientific_hypotheses_*.py"):
        for module in _imports(path):
            root = module.split(".", 1)[0]
            assert root not in {"api", "persistence"}, (path, module)


def test_no_v57_no_0018_no_v2_and_no_godot_change() -> None:
    assert "runner-config-v60" in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "runner-config-v63" not in text, path
        assert '"/v2' not in text, path
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []
