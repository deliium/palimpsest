"""Architecture boundary: simulation branching never imports experiments."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SRC = Path(__file__).resolve().parents[2] / "src" / "simulation"


@pytest.mark.parametrize(
    "filename",
    ("branching.py", "branch_service.py", "branch_compare.py"),
)
def test_branch_modules_forbid_experiments_imports(filename: str) -> None:
    path = _SRC / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("experiments"), alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("experiments"), node.module
