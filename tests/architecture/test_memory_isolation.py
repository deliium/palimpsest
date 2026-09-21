"""Architecture gates for owner-scoped episodic memory isolation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.boundary_checker import ALLOWED_IMPORTS

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

_MEMORY_ADAPTER_FORBIDDEN_PREFIXES = (
    "world.events",
    "world._",
    "simulation.replay",
    "simulation.journal",
)


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


def test_persistence_may_depend_on_public_memory() -> None:
    assert "memory" in ALLOWED_IMPORTS["persistence"]


def test_memory_must_not_depend_on_persistence() -> None:
    assert "persistence" not in ALLOWED_IMPORTS["memory"]
    assert "infrastructure" not in ALLOWED_IMPORTS["memory"]


def test_memory_adapter_forbids_event_authority_imports() -> None:
    for relative in (
        "persistence/memory_sqlalchemy.py",
        "persistence/memory_orm.py",
    ):
        adapter = SRC / relative
        assert adapter.is_file()
        imported = _imported_modules(adapter)
        for name in imported:
            for prefix in _MEMORY_ADAPTER_FORBIDDEN_PREFIXES:
                assert not name.startswith(prefix), f"{adapter.name} imports {name}"
            assert name not in {
                "persistence.orm",
                "persistence.readers",
                "persistence.sqlalchemy",
            }, f"{adapter.name} imports event-store module {name}"


def test_memory_package_forbids_orm_and_sqlalchemy() -> None:
    memory_root = SRC / "memory"
    forbidden = {"sqlalchemy", "alembic", "asyncpg"}
    for path in memory_root.rglob("*.py"):
        imported = _imported_modules(path)
        overlap = imported & forbidden
        assert not overlap, f"{path.relative_to(SRC)} imports {sorted(overlap)}"


def test_create_memory_service_requires_scope_and_session() -> None:
    import persistence
    from agents.models import AgentId
    from memory.models import (
        MemoryRunId,
        MemoryScope,
        MemoryScoreWeights,
        MemoryScoringPolicy,
    )
    from persistence.memory_sqlalchemy import SqlAlchemyMemoryService

    assert "create_memory_service" in persistence.__all__
    scope = MemoryScope(run_id=MemoryRunId("run-1"), owner_id=AgentId("agent-1"))
    policy = MemoryScoringPolicy(
        policy_id="default",
        version="1",
        weights=MemoryScoreWeights(recency=1.0),
    )
    with pytest.raises(persistence.PersistenceAdapterError) as missing:
        persistence.create_memory_service(scope=scope, scoring_policy=policy)
    assert missing.value.code == "missing_session_factory"

    class _Factory:
        def __call__(self) -> object:
            raise RuntimeError("session_factory_not_for_unit_test")

    service = persistence.create_memory_service(
        scope=scope,
        session_factory=_Factory(),  # type: ignore[arg-type]
        scoring_policy=policy,
    )
    assert isinstance(service, SqlAlchemyMemoryService)
    assert service.scope == scope


_FORBIDDEN_NONDET = frozenset({"random", "secrets", "uuid", "time", "datetime"})


def test_memory_and_adapter_avoid_nondeterministic_clocks_and_randomness() -> None:
    roots = (
        SRC / "memory",
        SRC / "persistence" / "memory_sqlalchemy.py",
        SRC / "persistence" / "memory_orm.py",
        SRC / "agents" / "cognition" / "memory.py",
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


def test_memory_paths_do_not_import_objective_event_authority() -> None:
    forbidden = {
        "world.events",
        "world._state",
        "simulation.replay",
        "simulation.journal",
        "persistence.orm",
        "persistence.readers",
        "persistence.sqlalchemy",
        "analysis.contracts",
        "analysis.service",
    }
    paths = list((SRC / "memory").rglob("*.py"))
    paths.append(SRC / "persistence" / "memory_sqlalchemy.py")
    paths.append(SRC / "agents" / "cognition" / "memory.py")
    paths.append(SRC / "agents" / "cognition" / "reconstruction.py")
    for path in paths:
        imported = _imported_modules(path)
        overlap = imported & forbidden
        assert not overlap, f"{path.relative_to(SRC)} imports {sorted(overlap)}"


def test_memory_may_import_opaque_event_id_only() -> None:
    models = SRC / "memory" / "models.py"
    imported = _imported_modules(models)
    assert "world.identifiers" in imported or any(
        name.startswith("world.identifiers") for name in imported
    )
    assert "world.events" not in imported
    text = models.read_text(encoding="utf-8")
    assert "EventId" in text
    assert "from world.events" not in text
