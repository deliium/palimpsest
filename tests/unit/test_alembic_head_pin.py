"""Pin Alembic head at 0015 for research branch lineage."""

from __future__ import annotations

from pathlib import Path

from persistence.orm import (
    AUTHORITATIVE_TABLES,
    BRANCH_LINEAGE_TABLES,
    COGNITION_TRACE_TABLES,
)
from simulation.compatibility import ALEMBIC_HEAD_REVISION, compatibility_entry

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "alembic" / "versions"


def test_alembic_head_is_0015_with_simulation_branches() -> None:
    assert ALEMBIC_HEAD_REVISION == "0015"
    entry = compatibility_entry("alembic_head")
    assert entry.write_version == "0015"
    assert (VERSIONS / "0014_stochastic_identity.py").is_file()
    assert (VERSIONS / "0015_simulation_branches.py").is_file()
    assert sorted(VERSIONS.glob("0016_*.py")) == []


def test_cognition_trace_tables_outside_authoritative() -> None:
    names = set(AUTHORITATIVE_TABLES)
    for table in COGNITION_TRACE_TABLES:
        assert table not in names
    assert "cognition_trace_invocations" in COGNITION_TRACE_TABLES


def test_branch_lineage_tables_outside_authoritative() -> None:
    names = set(AUTHORITATIVE_TABLES)
    for table in BRANCH_LINEAGE_TABLES:
        assert table not in names
    assert "simulation_branches" in BRANCH_LINEAGE_TABLES


def test_authoritative_tables_unchanged_by_capability_flags() -> None:
    """Flags must not invent new authoritative tables or SQL columns."""
    names = set(AUTHORITATIVE_TABLES)
    assert "world_events" in names
    assert "tick_commits" in names
    for forbidden in (
        "v2_capability_flags",
        "capability_flags",
        "runner_capability_flags",
        "simulation_branches",
    ):
        assert forbidden not in names
