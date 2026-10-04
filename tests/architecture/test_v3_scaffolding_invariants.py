"""V3 scaffolding invariant gaps — fixed roster, presentation non-authority, no mandates.

Inventory (existing gates remain authoritative; this file adds only missing pins):
- test_world_authority, test_cognitive_loop_isolation, test_llm_provider_isolation
- test_social_isolation, test_experiment_instrumentation_isolation, test_analysis_isolation
- test_godot_client_isolation, test_observer_isolation, test_cognitive_architecture_boundaries
- import-linter (pyproject.toml), tests/unit/test_v2_scientific_invariants.py

Non-goal: rewrite WorldState / WorldEvent / LLM→command bans already covered elsewhere.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from simulation.engine import WorldEngine
from simulation.runner import SimulationRunner

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
RUNNER_PY = SRC / "simulation" / "runner.py"

# Mid-run roster mutation APIs must not exist on authority surfaces today.
_FORBIDDEN_ROSTER_METHODS = frozenset(
    {
        "register_agent",
        "unregister_agent",
        "unbind_agent",
        "spawn_agent",
        "add_agent",
        "remove_agent",
        "bind_agent",
    }
)

# Scripted-emergence mandate identifiers reserved against V3 scaffolding.
_FORBIDDEN_MANDATE_IDENTIFIERS = frozenset(
    {
        "civilization_emerged",
        "institution_formed",
        "kinship_must_form",
        "culture_emerged",
        "group_must_form",
        "society_formed",
        "norm_emerged",
    }
)

# Files that may name forbidden identifiers only inside deny-list comments/sets.
_DENYLIST_ALLOW_PATHS = frozenset(
    {
        "analysis/phenomenon_models.py",
    }
)


def test_inventory_pins_existing_architecture_gates() -> None:
    architecture = ROOT / "tests" / "architecture"
    required = (
        "test_world_authority.py",
        "test_cognitive_loop_isolation.py",
        "test_llm_provider_isolation.py",
        "test_social_isolation.py",
        "test_experiment_instrumentation_isolation.py",
        "test_analysis_isolation.py",
        "test_godot_client_isolation.py",
        "test_observer_isolation.py",
        "test_cognitive_architecture_boundaries.py",
        "test_import_boundaries.py",
    )
    for name in required:
        assert (architecture / name).is_file(), name
    assert (ROOT / "tests" / "unit" / "test_v2_scientific_invariants.py").is_file()


def test_world_engine_and_runner_have_no_mid_run_roster_api() -> None:
    for cls in (WorldEngine, SimulationRunner):
        public = {
            name
            for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith("_")
        }
        public |= {
            name
            for name, _ in inspect.getmembers(cls, predicate=inspect.ismethod)
            if not name.startswith("_")
        }
        # Also include unbound methods declared on the class body.
        public |= {
            name
            for name in dir(cls)
            if not name.startswith("_") and callable(getattr(cls, name, None))
        }
        overlap = public & _FORBIDDEN_ROSTER_METHODS
        assert overlap == set(), f"{cls.__name__} exposes roster mutators: {overlap}"


def test_prepare_parallel_remains_hardcoded_false() -> None:
    text = RUNNER_PY.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(RUNNER_PY))
    found_literal_false = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        format_strings = [
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        ]
        if not any("prepare_parallel" in value for value in format_strings):
            continue
        if any(
            isinstance(arg, ast.Constant) and arg.value is False for arg in node.args
        ):
            found_literal_false = True
    assert found_literal_false, "prepare_parallel must log literal False"


def test_no_scripted_civilization_mandate_helpers_in_src() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = str(path.relative_to(SRC))
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                names.add(node.value)
        hits = names & _FORBIDDEN_MANDATE_IDENTIFIERS
        if not hits:
            continue
        if rel in _DENYLIST_ALLOW_PATHS:
            # Deny-list modules may mention identifiers only as forbidden tokens.
            continue
        offenders.append(f"{rel}:{sorted(hits)}")
    assert offenders == [], f"scripted mandate identifiers present: {offenders}"


def test_analysis_and_experiments_still_forbidden_in_cognition() -> None:
    """Re-pin analysis/experiment → cognition feedback ban for V3 scaffolding."""
    cognition = SRC / "agents" / "cognition"
    forbidden_roots = ("analysis", "experiments")
    for path in cognition.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root not in forbidden_roots, f"{path}: import {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".")[0]
                assert root not in forbidden_roots, f"{path}: from {node.module}"


def test_godot_presentation_stays_non_authority_surface() -> None:
    """Godot client must not appear as a Python package or simulation authority."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "clients/godot-observer" not in pyproject
    for path in (SRC / "simulation").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "clients/godot-observer" not in text
        assert "clients.godot" not in text
