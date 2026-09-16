"""Architecture checks against the real source tree."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.architecture.boundary_checker import (
    ALLOWED_IMPORTS,
    check_tree,
    format_violations,
)

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
PACKAGES = (
    "world",
    "agents",
    "agents.cognition",
    "memory",
    "social",
    "llm",
    "simulation",
    "api",
    "analysis",
    "infrastructure",
    "persistence",
)


def test_source_tree_satisfies_ast_allowlist() -> None:
    violations = check_tree(SRC_ROOT)
    assert violations == [], format_violations(violations)


def test_import_linter_contracts_hold() -> None:
    lint_imports = Path(sys.executable).parent / "lint-imports"
    completed = subprocess.run(
        [
            str(lint_imports),
            "--config",
            str(ROOT / "pyproject.toml"),
            "--no-cache",
            "--no-logo",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        pytest.fail(completed.stdout + completed.stderr)


def test_packages_import_without_logs_or_side_effects() -> None:
    names = ", ".join(repr(name) for name in PACKAGES)
    script = f"""
import importlib
import logging
import sys
for name in [{names}]:
    module = importlib.import_module(name)
    logger = logging.getLogger(name)
    if logger.handlers:
        raise SystemExit(f"logger handlers for {{name}}: {{logger.handlers!r}}")
    if not hasattr(module, "__all__"):
        raise SystemExit(f"{{name}} missing __all__")
print("ok")
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=Path("/"),
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "ok"
    assert completed.stderr == ""


def test_persistence_facade_is_side_effect_free_and_exports_factories() -> None:
    import persistence

    assert "PersistenceAdapterError" in persistence.__all__
    assert "create_tick_journal_repository" in persistence.__all__
    assert persistence.create_run_repository.__module__ == "persistence"
    with pytest.raises(persistence.PersistenceAdapterError) as err:
        persistence.create_tick_journal_repository()
    assert err.value.code == "missing_session_factory"


def test_world_public_facade_does_not_reexport_authority() -> None:
    import world

    assert "_state" not in world.__all__
    assert "_transitions" not in world.__all__
    assert "_operations" not in world.__all__
    assert "_perception" not in world.__all__
    assert "_rules" not in world.__all__
    assert "_replay" not in world.__all__
    assert "WorldState" not in world.__all__
    assert "WorldTransition" not in world.__all__
    assert "WorldGateway" not in world.__all__
    assert "accept_action_request" not in world.__all__
    assert "admit_agent_command" not in __import__("simulation").__all__
    assert "WorldEngine" in __import__("simulation").__all__


def test_allowlist_covers_every_bounded_layer() -> None:
    assert set(ALLOWED_IMPORTS) == set(PACKAGES)
