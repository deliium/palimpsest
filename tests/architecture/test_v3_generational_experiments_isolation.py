"""Import boundaries for the generational experiment modules."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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


def test_generational_cohort_metric_is_analysis_only() -> None:
    module = SRC / "analysis" / "generational_cohort.py"
    forbidden = (
        "experiments",
        "api",
        "persistence",
        "infrastructure",
        "agents.cognition",
        "simulation.engine",
        "simulation.runner",
    )
    hits = [
        imported
        for imported in _imports(module)
        if _matches(imported, forbidden)
    ]
    assert hits == []


def test_generational_experiment_modules_avoid_outer_adapters() -> None:
    forbidden = ("analysis", "api", "persistence", "infrastructure")
    for name in (
        "generational_comparison_models.py",
        "generational_axes.py",
        "generational_comparison_base.py",
        "generational_comparison.py",
        "generational_comparison_scenario.py",
    ):
        module = SRC / "experiments" / name
        hits = [
            imported
            for imported in _imports(module)
            if _matches(imported, forbidden)
        ]
        assert hits == [], f"{name}: {hits}"


def test_simulation_does_not_import_generational_experiment_composition() -> None:
    forbidden = ("experiments.generational_comparison",)
    hits: list[str] = []
    for module in (SRC / "simulation").rglob("*.py"):
        for imported in _imports(module):
            if _matches(imported, forbidden):
                hits.append(f"{module.relative_to(SRC)}:{imported}")
    assert hits == []
