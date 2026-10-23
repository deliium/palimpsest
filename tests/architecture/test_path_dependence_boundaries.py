"""Authority and compatibility boundaries for V3-38."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from observer.version import SEMANTIC_TYPE_BY_KIND
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.runner_models import RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V55

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _matches(module: str, roots: tuple[str, ...]) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in roots)


def test_path_dependence_experiments_avoid_outer_adapters() -> None:
    forbidden = ("api", "persistence", "infrastructure")
    for name in (
        "path_dependence_models.py",
        "path_dependence_identity.py",
        "path_dependence_interventions.py",
        "path_dependence_evidence.py",
        "path_dependence_artifacts.py",
        "path_dependence_resume.py",
        "path_dependence_runner.py",
    ):
        hits = [
            imported
            for imported in _imports(SRC / "experiments" / name)
            if _matches(imported, forbidden)
        ]
        assert hits == [], f"{name}: {hits}"


def test_simulation_and_analysis_do_not_import_path_dependence_experiments() -> None:
    hits: list[str] = []
    for directory in (SRC / "simulation", SRC / "analysis"):
        for module in directory.rglob("*.py"):
            for imported in _imports(module):
                if _matches(imported, ("experiments.path_dependence",)):
                    hits.append(f"{module.relative_to(SRC)}:{imported}")
    assert hits == []


def test_research_runner_path_dependence_never_imports_api_or_tests() -> None:
    for name in (
        "path_dependence_cli.py",
        "path_dependence_composition.py",
        "path_dependence_reconstruction.py",
    ):
        hits = [
            imported
            for imported in _imports(SRC / "research_runner" / name)
            if _matches(imported, ("api", "tests"))
        ]
        assert hits == [], f"{name}: {hits}"


def test_v3_38_preserves_current_contract_pins() -> None:
    assert METRIC_FAMILY_COUNT == 136
    assert len(SEMANTIC_TYPE_BY_KIND) == 73
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert RUNNER_SCHEMA_VERSION_V4 == "runner-config-v4"
    assert RUNNER_SCHEMA_VERSION_V55 == "runner-config-v55"


def test_no_new_runner_or_replay_schema_files() -> None:
    for path in (SRC / "simulation").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "runner-config-v56" not in source, path
