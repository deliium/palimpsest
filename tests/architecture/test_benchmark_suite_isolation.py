"""Architecture isolation for the V2 benchmark suite."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
_V1_GATE = _ROOT / "tests" / "unit" / "test_v1_regression_gate.py"
_EXPERIMENTS = _SRC / "experiments"


def test_v1_gate_excludes_benchmark_and_graphical_ids() -> None:
    source = _V1_GATE.read_text(encoding="utf-8")
    for needle in (
        "benchmark_suite",
        "benchmark_scenarios",
        "benchmark_smoke",
        "bench-",
        "observer-graphical-v2",
        "observer_graphical_scenario",
    ):
        assert needle not in source


def test_experiments_package_forbids_api_imports() -> None:
    hits: list[str] = []
    for path in sorted(_EXPERIMENTS.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "api" or alias.name.startswith("api."):
                        hits.append(f"{path.relative_to(_ROOT)}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "api" or node.module.startswith("api."):
                    hits.append(f"{path.relative_to(_ROOT)}:{node.module}")
    assert hits == []


def test_src_does_not_import_godot_or_research_ui_clients() -> None:
    hits: list[str] = []
    for path in sorted(_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "clients/godot-observer" in text or "clients/research-ui" in text:
            hits.append(str(path.relative_to(_ROOT)))
        if "import godot" in text or "from godot" in text:
            hits.append(str(path.relative_to(_ROOT)))
    assert hits == []
