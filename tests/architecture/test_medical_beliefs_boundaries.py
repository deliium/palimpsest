# mypy: ignore-errors

"""Medical beliefs stay owner-scoped and outside objective disease authority."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from simulation.compatibility import ALEMBIC_HEAD_REVISION
from simulation.runner_models import (
    RESULT_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION,
    RUNNER_SCHEMA_VERSION_V4,
)

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
_COGNITION_FILES = (
    SRC / "agents" / "cognition" / "medical_beliefs.py",
    SRC / "agents" / "cognition" / "medical_beliefs_actions.py",
    SRC / "agents" / "cognition" / "medical_beliefs_communication.py",
)
_FORBIDDEN_PREFIXES = (
    "world._disease",
    "world.events",
    "analysis",
    "simulation.persistence",
    "simulation.observer",
    "observer",
    "api",
    "persistence",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_cognition_never_imports_objective_or_detached_authority() -> None:
    for path in _COGNITION_FILES:
        names = _imports(path)
        for forbidden in _FORBIDDEN_PREFIXES:
            assert not any(
                name == forbidden or name.startswith(f"{forbidden}.")
                for name in names
            ), (path, forbidden)


def test_no_objective_version_or_schema_change() -> None:
    assert RUNNER_SCHEMA_VERSION == RUNNER_SCHEMA_VERSION_V4
    assert RESULT_SCHEMA_VERSION == "runner-result-v2"
    assert ALEMBIC_HEAD_REVISION == "0017"


def _field_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    fields: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(
                    item.target, ast.Name
                ):
                    fields.add(item.target.id)
    return fields


def test_medical_module_has_no_truth_or_diagnosis_field() -> None:
    forbidden = {"truth", "diagnosis", "confirmed_cause", "objective_phase"}
    for path in _COGNITION_FILES:
        assert not (_field_names(path) & forbidden)


def test_capture_does_not_import_api_or_persistence_adapters() -> None:
    path = SRC / "experiments" / "medical_beliefs_capture.py"
    names = _imports(path)
    assert not any(
        name == "api" or name.startswith("api.") for name in names
    )
    assert not any(
        name == "persistence" or name.startswith("persistence.")
        for name in names
    )
