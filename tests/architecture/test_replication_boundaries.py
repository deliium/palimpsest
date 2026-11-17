"""V4-28 replication helpers stay outside private authority and outer layers."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

COGNITION = Path(__file__).resolve().parents[2] / "src" / "agents" / "cognition"
MODULES = (
    COGNITION / "replication.py",
    COGNITION / "replication_designs.py",
    COGNITION / "replication_codec.py",
    COGNITION / "replication_communication.py",
    COGNITION / "replication_interpretation.py",
)
FORBIDDEN_PACKAGES = frozenset(
    {
        "analysis",
        "api",
        "infrastructure",
        "observer",
        "persistence",
        "simulation",
    }
)


def _imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append(
                (node.module, tuple(alias.name for alias in node.names))
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, ()))
    return found


def test_replication_modules_never_import_private_authority_or_outer_layers() -> None:
    for path in MODULES:
        assert path.exists(), path
        for module, _names in _imports(path):
            top = module.split(".", 1)[0]
            assert top not in FORBIDDEN_PACKAGES, (path.name, module)
            assert not module.startswith("world._"), (path.name, module)
            assert module not in {
                "world._state",
                "world._perception",
                "world._operations",
            }, (path.name, module)


def test_replication_modules_never_construct_world_experiment_commands() -> None:
    for path in MODULES:
        for module, names in _imports(path):
            assert not (module == "world.actions" and "Experiment" in names), (
                path.name,
                module,
            )


def test_replication_state_models_forbid_truth_and_authority_fields() -> None:
    forbidden = {
        "truth",
        "proven",
        "verified",
        "consensus",
        "majority",
        "objective_probability",
        "world_state",
        "action_request",
        "authority_token",
    }
    for path in MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign):
                    continue
                target = statement.target
                if isinstance(target, ast.Name):
                    assert target.id not in forbidden, (path.name, node.name, target.id)


def test_world_communication_limits_are_not_widened() -> None:
    communications = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "world"
        / "communications.py"
    )
    text = communications.read_text(encoding="utf-8")
    assert "MAX_COMMUNICATION_RELATIONS: Final[int] = 32" in text
    assert "_MAX_CONCEPT_CHARS: Final[int] = 256" in text
