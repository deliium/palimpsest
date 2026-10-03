"""Import and factory boundary guards for cognitive architectures."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition.architectures import (
    STAGE_FACTORY_TABLE,
    StageSlot,
)

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURES_PY = ROOT / "src" / "agents" / "cognition" / "architectures.py"

_FORBIDDEN_ROOTS = frozenset({"simulation", "experiments", "api", "persistence"})


def test_cognition_architectures_does_not_import_orchestration() -> None:
    tree = ast.parse(ARCHITECTURES_PY.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = imported & _FORBIDDEN_ROOTS
    assert forbidden == set(), f"forbidden imports: {sorted(forbidden)}"


def test_retrieval_reconstruction_factories_are_declaration_tokens() -> None:
    for slot in (StageSlot.RETRIEVAL, StageSlot.RECONSTRUCTION):
        for (bound_slot, key), factory in STAGE_FACTORY_TABLE.items():
            if bound_slot is not slot:
                continue
            value = factory()
            assert type(value) is str, (
                f"{slot.value}/{key} must be a declaration token, got {type(value)}"
            )
            assert value == key
