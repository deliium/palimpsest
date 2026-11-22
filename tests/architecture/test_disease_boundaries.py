# mypy: ignore-errors

"""Private disease state must stay out of subjective and presentation layers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_PRIVATE = "world._disease"
_FORBIDDEN_LAYERS = (
    SRC / "agents",
    SRC / "memory",
    SRC / "llm",
    SRC / "observer",
    SRC / "clients",
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


@pytest.mark.parametrize("directory", _FORBIDDEN_LAYERS)
def test_subjective_and_presentation_layers_never_import_private_disease(
    directory: Path,
) -> None:
    if not directory.exists():
        pytest.skip(f"missing {directory}")
    for path in directory.rglob("*.py"):
        names = _imports(path)
        assert _PRIVATE not in names
        assert not any(name.startswith(f"{_PRIVATE}.") for name in names)
