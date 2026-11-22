# mypy: ignore-errors
"""Registry, isolation, and pin invariants for V4-27 scientific hypotheses."""

from __future__ import annotations

import ast
from pathlib import Path

from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.runner_models import SUPPORTED_RUNNER_SCHEMA_VERSIONS
from simulation.v4_architecture import (
    V4_CAPABILITY_FLAGS,
    V4_CONTEXT_BY_ID,
    V4_CONTEXT_MAP_VERSION,
    V4_CONTEXTS,
    V4Authority,
    V4ContextId,
    validate_v4_contexts,
)
from simulation.versioning import (
    V4_EVENT_REUSING_CONTEXTS,
    V4_WRITE_PAIR_RESERVATIONS,
    validate_deepening_write_pairs,
    validate_write_pair_reservations,
)

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_MODULES = (
    ROOT / "src" / "analysis" / "scientific_hypotheses_contract.py",
    ROOT / "src" / "analysis" / "scientific_hypotheses_policy.py",
    ROOT / "src" / "analysis" / "scientific_hypotheses_rows.py",
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_science_is_owned_without_adding_a_context_or_flag() -> None:
    validate_v4_contexts()
    assert V4_CONTEXT_MAP_VERSION == "v4-context-map-v6"
    assert len(V4_CONTEXTS) == 17
    assert len(V4_CAPABILITY_FLAGS) == 12
    assert len(V4_OWNED_CAPABILITY_FLAGS) == 10
    assert "science" in V4_OWNED_CAPABILITY_FLAGS
    assert V4_CAPABILITY_FLAGS.count("science") == 1


def test_science_context_spec_is_unchanged() -> None:
    spec = V4_CONTEXT_BY_ID[V4ContextId.SCIENCE]
    assert spec.capability_flag == "science"
    assert spec.authority is V4Authority.OWNER_SCOPED
    assert spec.owner_packages == ("agents.cognition", "simulation")
    assert spec.required_config_seam == "v4_capability_flags.science"
    assert spec.uses_existing_events is False
    assert spec.prerequisite_contexts == (V4ContextId.FORMAL_RULES,)
    assert V4ContextId.SCIENCE not in V4_EVENT_REUSING_CONTEXTS


def test_no_new_write_pair_is_claimed() -> None:
    contexts = {reservation.context_id for reservation in V4_WRITE_PAIR_RESERVATIONS}
    assert V4ContextId.SCIENCE not in contexts
    validate_write_pair_reservations()
    validate_deepening_write_pairs()


def test_no_runner_schema_or_migration_is_added() -> None:
    assert "runner-config-v60" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
    for path in (ROOT / "src").rglob("*.py"):
        assert "runner-config-v60" not in path.read_text(encoding="utf-8"), path
    assert sorted((ROOT / "alembic" / "versions").glob("0018_*.py")) == []


def test_analysis_modules_never_import_owner_cognition_or_private_rules() -> None:
    for path in ANALYSIS_MODULES:
        modules = _imported_modules(path)
        assert not any(module == "agents" or module.startswith("agents.") for module in modules), path  # noqa: E501
        for module in modules:
            assert module != "world._experiment_laws", path
            assert module != "world._rules", path
            assert not module.startswith("world._experiment_laws."), path
            assert not module.startswith("world._rules."), path
