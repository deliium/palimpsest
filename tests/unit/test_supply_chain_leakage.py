# mypy: ignore-errors
"""Supply-chain analysis and client surfaces cannot leak authority or ranking."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT
from analysis.supply_chain_contract import SupplyEdgeKind
from api.routes.supply_chains import SUPPLY_CHAIN_ROUTE_COUNT
from observer.version import SEMANTIC_EVENT_TYPES
from simulation.compatibility import ALEMBIC_HEAD_REVISION
from world.actions import _COMMAND_TYPES
from world.events import EVENT_SCHEMA_REPLAY_V27

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_FORBIDDEN_KEYS = (
    "price",
    "cost",
    "currency",
    "money",
    "quota",
    "allocation",
    "optimizer",
    "plan_score",
    "priority_score",
    "recommendation",
    "rank",
    "severity",
)
_FORBIDDEN_AUTHORITY = {
    "WorldState",
    "WorldEngine",
    "ActionSubmission",
    "ProductionCatalog",
}
_FORBIDDEN_ANALYSIS_IMPORTS = {
    "world._state",
    "world._production",
    "simulation",
    "experiments",
    "api",
    "persistence",
    "observer",
    "agents.cognition",
}


def _analysis_modules() -> list[Path]:
    return sorted((SRC / "analysis").glob("supply_chain_*.py"))


def test_analysis_modules_are_detached() -> None:
    for path in _analysis_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        names |= {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not names & _FORBIDDEN_ANALYSIS_IMPORTS, path
        assert not any(name.startswith("world._") for name in names), path


def test_no_forbidden_authority_types() -> None:
    for pattern in ("analysis/supply_chain_*.py", "simulation/supply_chain_*.py"):
        for path in sorted(SRC.glob(pattern)):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            }
            assert not names & _FORBIDDEN_AUTHORITY, path


def _code_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            names.add(node.arg)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


def test_no_optimizer_or_score_keys_in_new_surfaces() -> None:
    paths = list(_analysis_modules())
    paths += sorted((SRC / "simulation").glob("supply_chain_*.py"))
    for path in paths:
        if path.name in {"supply_chain_contract.py", "supply_chain_models.py"}:
            continue
        names = _code_names(path)
        for key in _FORBIDDEN_KEYS:
            assert key not in names, (path, key)
    client = (
        ROOT / "clients" / "research-ui" / "src" / "api" / "supplyChains.ts"
    ).read_text(encoding="utf-8")
    for key in _FORBIDDEN_KEYS:
        assert re.search(rf"\b{key}\b", client, re.IGNORECASE) is None, key


def test_snapshot_models_have_no_forbidden_fields() -> None:
    import dataclasses

    from simulation import supply_chain_models

    for value in vars(supply_chain_models).values():
        if not dataclasses.is_dataclass(value):
            continue
        names = {field.name for field in dataclasses.fields(value)}
        for key in _FORBIDDEN_KEYS:
            assert key not in names, (value.__name__, key)


def test_client_has_no_mutating_method() -> None:
    text = (
        ROOT / "clients" / "research-ui" / "src" / "api" / "supplyChains.ts"
    ).read_text(encoding="utf-8")
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert re.search(rf"\b{method}\b", text) is None


def test_pins_are_unchanged() -> None:
    assert len(_COMMAND_TYPES) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert METRIC_FAMILY_COUNT == 216
    assert EVENT_SCHEMA_REPLAY_V27 == 27
    assert ALEMBIC_HEAD_REVISION == "0017"
    assert SUPPLY_CHAIN_ROUTE_COUNT == 7
    assert len(SupplyEdgeKind) == 10
