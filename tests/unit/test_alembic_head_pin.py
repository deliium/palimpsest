"""Pin Alembic head at 0013 for durable cognition traces."""

from __future__ import annotations

from pathlib import Path

from persistence.orm import (
    AUTHORITATIVE_TABLES,
    COGNITION_TRACE_TABLES,
)
from simulation.compatibility import ALEMBIC_HEAD_REVISION, compatibility_entry

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "alembic" / "versions"


def test_alembic_head_is_0013_with_cognition_trace() -> None:
    assert ALEMBIC_HEAD_REVISION == "0013"
    entry = compatibility_entry("alembic_head")
    assert entry.write_version == "0013"
    assert (VERSIONS / "0012_v1_scientific_evidence.py").is_file()
    assert (VERSIONS / "0013_v2_cognition_trace.py").is_file()
    assert sorted(VERSIONS.glob("0014_*.py")) == []


def test_cognition_trace_tables_outside_authoritative() -> None:
    names = set(AUTHORITATIVE_TABLES)
    for table in COGNITION_TRACE_TABLES:
        assert table not in names
    assert "cognition_trace_invocations" in COGNITION_TRACE_TABLES


def test_authoritative_tables_unchanged_by_capability_flags() -> None:
    """Flags must not invent new authoritative tables or SQL columns."""
    names = set(AUTHORITATIVE_TABLES)
    assert "world_events" in names
    assert "tick_commits" in names
    for forbidden in (
        "v2_capability_flags",
        "capability_flags",
        "runner_capability_flags",
    ):
        assert forbidden not in names
