"""World authority must stay out of agent-facing packages."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import world
from tests.architecture.boundary_checker import check_tree, format_violations
from world._state import World, WorldState
from world._transitions import WorldTransition

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
FORBIDDEN_PACKAGES = (
    "agents",
    "memory",
    "social",
    "llm",
    "api",
    "analysis",
)
AUTHORITY_NAMES = frozenset(
    {
        "World",
        "WorldState",
        "WorldTransition",
        "apply_trusted",
        "apply_validated_operation",
        "validate_action_request",
        "OperationAccepted",
        "OperationRejected",
        "ValidatedWorldOperation",
        "project_observations",
        "evaluate_operation",
        "COMMAND_RULE_MATRIX",
    }
)
AUTHORITY_MODULES = frozenset(
    {
        "world._state",
        "world._transitions",
        "world._operations",
        "world._perception",
        "world._rules",
    }
)


def test_public_world_facade_omits_authority() -> None:
    assert "World" not in world.__all__
    assert "WorldState" not in world.__all__
    assert "WorldTransition" not in world.__all__
    assert "World" not in world.__dict__
    assert "WorldState" not in world.__dict__
    assert "WorldTransition" not in world.__dict__


def test_source_tree_still_satisfies_allowlist() -> None:
    violations = check_tree(SRC_ROOT)
    assert violations == [], format_violations(violations)


def test_forbidden_packages_do_not_reference_world_authority() -> None:
    hits: list[str] = []
    for package in FORBIDDEN_PACKAGES:
        root = SRC_ROOT / package.replace(".", "/")
        for path in root.rglob("*.py"):
            hits.extend(_authority_hits(path))
    assert hits == []


def _authority_hits(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in AUTHORITY_NAMES:
            found.append(f"{path}:{node.lineno}:{node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in AUTHORITY_NAMES:
            found.append(f"{path}:{node.lineno}:{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module in AUTHORITY_MODULES:
            found.append(f"{path}:{node.lineno}:{node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in AUTHORITY_MODULES:
                    found.append(f"{path}:{node.lineno}:{alias.name}")
    return found


def test_world_state_is_not_the_transition_protocol() -> None:
    assert World.__module__ == "world._state"
    assert WorldState.__module__ == "world._state"
    assert WorldTransition.__module__ == "world._transitions"
    assert WorldState.__qualname__ != WorldTransition.__qualname__
    assert World.__qualname__ != WorldState.__qualname__


def test_public_facades_hide_authority_and_expose_codec() -> None:
    import simulation
    import world

    assert "World" not in world.__all__
    assert "WorldState" not in world.__all__
    assert "encode_domain" in simulation.__all__
    assert "decode_domain" in simulation.__all__
    assert "DomainSerializationError" in simulation.__all__
