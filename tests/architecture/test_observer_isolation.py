"""Observer stays a read-only presentation package."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.boundary_checker import ALLOWED_IMPORTS

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
OBSERVER = SRC / "observer"

_FORBIDDEN_IMPORT_PREFIXES = (
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic",
    "pydantic_core",
    "sqlalchemy",
    "alembic",
    "asyncpg",
    "persistence",
    "api",
    "infrastructure",
    "simulation.engine",
    "simulation.randomness",
    "world._state",
    "world._operations",
    "world._rules",
    "world._replay",
    "world._perception",
    "world._physical",
)

_CONTRACT_IDS = (
    "observer_is_presentation_only",
    "world_does_not_import_bounded_modules",
    "simulation_does_not_import_api_or_analysis",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def test_observer_sources_avoid_forbidden_modules() -> None:
    offenders: list[str] = []
    for path in sorted(OBSERVER.rglob("*.py")):
        for imported in _imports(path):
            for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                if imported == prefix or imported.startswith(prefix + "."):
                    offenders.append(f"{path.name}:{imported}")
    assert offenders == []


def test_observer_contract_ids_exist() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for contract_id in _CONTRACT_IDS:
        assert f'id = "{contract_id}"' in text


def test_observer_contracts_do_not_import_randomness() -> None:
    imported = _imports(OBSERVER / "contracts.py")
    assert "simulation.randomness" not in imported


def test_persistence_allowlist_includes_subjective_packages_only() -> None:
    assert ALLOWED_IMPORTS["persistence"] == frozenset(
        {"simulation", "infrastructure", "memory", "social", "experiments"}
    )
    assert "observer" not in ALLOWED_IMPORTS["persistence"]
    assert "observer" in ALLOWED_IMPORTS["api"]
    assert "observer" not in ALLOWED_IMPORTS["simulation"]
