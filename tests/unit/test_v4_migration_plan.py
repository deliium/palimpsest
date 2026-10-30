"""Ordered V4 migration intent: no revision applied, head pinned at 0017."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from simulation.compatibility import ALEMBIC_HEAD_REVISION, V4_CAPABILITY_FLAG_NAMES
from simulation.migration_plan import (
    V4_MIGRATION_SEQUENCE,
    MigrationStage,
    future_migration_files,
    next_revision,
    unapplied_stages,
    validate_migration_sequence,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "simulation" / "migration_plan.py"

pytestmark = pytest.mark.unit


def _mutated(index: int, **changes: Any) -> tuple[MigrationStage, ...]:
    return tuple(
        replace(stage, **changes) if position == index else stage
        for position, stage in enumerate(V4_MIGRATION_SEQUENCE)
    )


def test_sequence_validates_and_starts_at_the_next_revision() -> None:
    validate_migration_sequence()
    assert next_revision() == "0018"
    assert len(V4_MIGRATION_SEQUENCE) == 6
    assert V4_MIGRATION_SEQUENCE[0].requires_migration is False
    assert all(stage.requires_migration for stage in V4_MIGRATION_SEQUENCE[1:])


def test_no_future_migration_file_exists() -> None:
    assert future_migration_files(ROOT / "alembic" / "versions") == ()
    assert ALEMBIC_HEAD_REVISION == "0017"


def test_unapplied_stages_are_the_migrating_tail() -> None:
    stages = unapplied_stages()
    assert [stage.order for stage in stages] == [2, 3, 4, 5, 6]
    assert all(stage.requires_migration for stage in stages)
    assert unapplied_stages("0018") == ()


def test_only_known_flags_and_no_resilience_flag() -> None:
    known = set(V4_CAPABILITY_FLAG_NAMES)
    for stage in V4_MIGRATION_SEQUENCE[1:5]:
        assert stage.prerequisite_flags
        assert set(stage.prerequisite_flags) <= known
    assert V4_MIGRATION_SEQUENCE[5].prerequisite_flags == ()


def test_order_and_identity_mutations_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_migration_order"):
        validate_migration_sequence(stages=_mutated(1, order=3))
    with pytest.raises(ValueError, match="v4_migration_duplicate_stage"):
        validate_migration_sequence(
            stages=_mutated(1, stage_id=V4_MIGRATION_SEQUENCE[0].stage_id)
        )
    with pytest.raises(ValueError, match="v4_migration_stage_prefix"):
        validate_migration_sequence(stages=_mutated(1, stage_id="m02-wrong-prefix"))


def test_unknown_flag_and_post_migration_false_are_rejected() -> None:
    with pytest.raises(ValueError, match="v4_migration_unknown_flag"):
        validate_migration_sequence(
            stages=_mutated(1, prerequisite_flags=("not_a_flag",))
        )
    with pytest.raises(ValueError, match="v4_migration_gap_after_migration"):
        validate_migration_sequence(stages=_mutated(2, requires_migration=False))


def test_head_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="v4_migration_head_mismatch"):
        validate_migration_sequence("0018")


def test_future_migration_files_detects_only_later_revisions(
    tmp_path: Path,
) -> None:
    (tmp_path / "0017_memory_embedding_hnsw.py").write_text("revision = '0017'\n")
    (tmp_path / "0018_example.py").write_text("revision = '0018'\n")
    (tmp_path / "not_a_revision.py").write_text("x = 1\n")
    assert [path.name for path in future_migration_files(tmp_path)] == [
        "0018_example.py"
    ]


def test_module_imports_no_forbidden_stack() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    assert roots & {"sqlalchemy", "alembic", "persistence", "infrastructure"} == set()
