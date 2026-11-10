# mypy: ignore-errors

"""Supply-chain boundaries: world contract stays public and analysis-free."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SUPPLY_CHAIN = ROOT / "src" / "world" / "supply_chain.py"

FORBIDDEN_PREFIXES = (
    "agents",
    "analysis",
    "api",
    "experiments",
    "persistence",
    "simulation",
)


def _tree() -> ast.Module:
    return ast.parse(SUPPLY_CHAIN.read_text(encoding="utf-8"))


def test_supply_chain_module_is_inside_world_package() -> None:
    assert SUPPLY_CHAIN.parent.name == "world"
    assert SUPPLY_CHAIN.is_file()


def test_supply_chain_has_no_runtime_private_state_import() -> None:
    tree = _tree()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("world._"):
                assert node.level == 0
                # Only a TYPE_CHECKING annotation import is allowed.
                parents = [
                    parent
                    for parent in ast.walk(tree)
                    if node in ast.iter_child_nodes(parent)
                ]
                assert parents, "unparented import"
    # A direct top-level import of private world state is rejected.
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "world._"
        ):
            pytest.fail("world.supply_chain imports private world state at runtime")


def test_supply_chain_does_not_import_outer_packages() -> None:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            assert not any(
                module == prefix or module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_PREFIXES
            ), module


def test_supply_chain_contract_has_no_planner_or_score_tokens() -> None:
    text = SUPPLY_CHAIN.read_text(encoding="utf-8").lower()
    for token in (
        "central planner",
        "optimizer",
        "quota",
        "allocation",
        "severity",
        "recommendation",
        "score",
    ):
        assert token not in text


def test_analysis_supply_modules_are_detached_and_private_free() -> None:
    analysis = ROOT / "src" / "analysis"
    modules = sorted(analysis.glob("supply_chain_*.py"))
    assert {module.name for module in modules} == {
        "supply_chain_analysis.py",
        "supply_chain_bottlenecks.py",
        "supply_chain_contract.py",
        "supply_chain_events.py",
        "supply_chain_graph.py",
        "supply_chain_identity.py",
        "supply_chain_layers.py",
        "supply_chain_metrics.py",
        "supply_chain_policy.py",
        "supply_chain_rows.py",
    }
    forbidden_modules = {
        "world._state",
        "world._production",
        "simulation",
        "experiments",
        "api",
        "persistence",
        "observer",
        "agents.cognition",
    }
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported = node.module or ""
                assert imported not in forbidden_modules, (module.name, imported)
                assert not imported.startswith("world._"), (module.name, imported)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_modules, (
                        module.name,
                        alias.name,
                    )
