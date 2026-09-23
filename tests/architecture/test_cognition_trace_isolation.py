"""Architecture gates: cognition traces cannot influence WorldEngine."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from persistence.orm import AUTHORITATIVE_TABLES, COGNITION_TRACE_TABLES

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _package_modules(package_dir: Path) -> set[str]:
    modules: set[str] = set()
    for path in package_dir.rglob("*.py"):
        modules |= _imported_modules(path)
    return modules


def test_cognition_trace_tables_disjoint_from_authoritative() -> None:
    assert set(COGNITION_TRACE_TABLES).isdisjoint(AUTHORITATIVE_TABLES)
    assert "cognition_trace_invocations" in COGNITION_TRACE_TABLES


def test_world_does_not_import_cognition_trace() -> None:
    forbidden_prefixes = (
        "simulation.cognition_trace",
        "persistence.cognition_trace",
    )
    imports = _package_modules(SRC / "world")
    for imported in imports:
        assert not imported.startswith(forbidden_prefixes)


def test_persistence_adapter_does_not_import_agents_cognition() -> None:
    path = SRC / "persistence" / "cognition_trace_sqlalchemy.py"
    imports = _imported_modules(path)
    assert "agents.cognition" not in imports
    assert not any(item.startswith("agents.cognition.") for item in imports)


def test_cognition_does_not_import_analysis_or_simulation_trace() -> None:
    imports = _package_modules(SRC / "agents" / "cognition")
    assert "analysis" not in imports
    assert "simulation.cognition_trace" not in imports
    assert "persistence" not in imports
    assert not any(item.startswith("analysis.") for item in imports)


def test_world_engine_does_not_reference_cognition_trace() -> None:
    text = (SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    assert "CognitionTraceInvocation" not in text
    assert "cognition_trace" not in text


def test_action_submission_and_loop_input_do_not_reference_traces() -> None:
    for rel in (
        "simulation/lifecycle.py",
        "agents/cognition/models.py",
    ):
        text = (SRC / rel).read_text(encoding="utf-8")
        assert "CognitionTraceInvocation" not in text
        assert "CognitionTraceRepository" not in text
