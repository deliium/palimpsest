"""Architecture gates for subjective social / relationship isolation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.boundary_checker import ALLOWED_IMPORTS

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_PROHIBITED_SOCIAL_LABELS = frozenset(
    {
        "friend",
        "enemy",
        "leader",
        "leadership",
        "morality",
        "moral",
        "culture",
        "group_membership",
        "Friend",
        "Enemy",
        "Leader",
    }
)

_SUBJECTIVE_ADAPTER_FORBIDDEN_PREFIXES = (
    "world.events",
    "world._",
    "simulation.replay",
    "simulation.journal",
)

_FORBIDDEN_NONDET = frozenset({"random", "secrets", "uuid", "time", "datetime"})


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.add(node.module)
    return names


def _defined_identifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_persistence_may_depend_on_public_social() -> None:
    assert "social" in ALLOWED_IMPORTS["persistence"]


def test_social_must_not_depend_on_persistence_or_memory() -> None:
    assert "persistence" not in ALLOWED_IMPORTS["social"]
    assert "memory" not in ALLOWED_IMPORTS["social"]
    assert "infrastructure" not in ALLOWED_IMPORTS["social"]


def test_memory_and_social_remain_independent_in_allowlist() -> None:
    assert "social" not in ALLOWED_IMPORTS["memory"]
    assert "memory" not in ALLOWED_IMPORTS["social"]


def test_social_package_forbids_orm_and_sqlalchemy() -> None:
    social_root = SRC / "social"
    forbidden = {"sqlalchemy", "alembic", "asyncpg"}
    for path in social_root.rglob("*.py"):
        imported = _imported_modules(path)
        overlap = imported & forbidden
        assert not overlap, f"{path.relative_to(SRC)} imports {sorted(overlap)}"


def test_social_package_forbids_memory_imports() -> None:
    for path in (SRC / "social").rglob("*.py"):
        imported = _imported_modules(path)
        assert "memory" not in imported
        assert not any(name.startswith("memory.") for name in imported), (
            f"{path.relative_to(SRC)} imports memory"
        )


def test_subjective_adapter_forbids_event_authority_imports() -> None:
    for relative in (
        "persistence/subjective_sqlalchemy.py",
        "persistence/subjective_orm.py",
    ):
        adapter = SRC / relative
        assert adapter.is_file()
        imported = _imported_modules(adapter)
        for name in imported:
            for prefix in _SUBJECTIVE_ADAPTER_FORBIDDEN_PREFIXES:
                assert not name.startswith(prefix), f"{adapter.name} imports {name}"
            assert name not in {
                "persistence.orm",
                "persistence.readers",
                "persistence.sqlalchemy",
            }, f"{adapter.name} imports event-store module {name}"


def test_social_avoids_nondeterministic_clocks_and_randomness() -> None:
    roots = (
        SRC / "social",
        SRC / "persistence" / "subjective_sqlalchemy.py",
        SRC / "persistence" / "subjective_orm.py",
    )
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*.py"))
        for path in paths:
            imported = _imported_modules(path)
            overlap = {
                name.split(".", 1)[0]
                for name in imported
                if name.split(".", 1)[0] in _FORBIDDEN_NONDET
            }
            assert not overlap, f"{path.relative_to(SRC)} imports {sorted(overlap)}"


def test_social_models_forbid_high_level_category_symbols() -> None:
    for relative in (
        "social/models.py",
        "social/relationships.py",
        "social/contracts.py",
        "social/service.py",
        "social/__init__.py",
    ):
        path = SRC / relative
        names = _defined_identifiers(path)
        banned = names & _PROHIBITED_SOCIAL_LABELS
        assert not banned, f"{relative} defines prohibited symbols {sorted(banned)}"
        # Reject string literals that would encode high-level category enums/fields.
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                for label in ("friend", "enemy", "leader", "morality", "culture"):
                    assert label not in lowered, (
                        f"{relative} contains prohibited label literal {node.value!r}"
                    )


def test_create_subjective_state_service_is_public() -> None:
    import persistence

    assert "create_subjective_state_service" in persistence.__all__


def test_subjective_agent_tables_disjoint_from_authoritative() -> None:
    from persistence.orm import AUTHORITATIVE_TABLES
    from persistence.subjective_orm import SUBJECTIVE_AGENT_TABLES

    assert set(SUBJECTIVE_AGENT_TABLES).isdisjoint(AUTHORITATIVE_TABLES)
    assert "semantic_beliefs" in SUBJECTIVE_AGENT_TABLES
    assert "directed_relationships" in SUBJECTIVE_AGENT_TABLES
