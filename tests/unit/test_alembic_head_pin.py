"""Pin Alembic head at 0012 for V2 scaffolding (no 0013 / no flag columns)."""

from __future__ import annotations

from pathlib import Path

from persistence.orm import AUTHORITATIVE_TABLES
from simulation.compatibility import ALEMBIC_HEAD_REVISION, compatibility_entry

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = ROOT / "alembic" / "versions"


def test_alembic_head_remains_0012() -> None:
    assert ALEMBIC_HEAD_REVISION == "0012"
    entry = compatibility_entry("alembic_head")
    assert entry.write_version == "0012"
    assert (VERSIONS / "0012_v1_scientific_evidence.py").is_file()
    assert sorted(VERSIONS.glob("0013_*.py")) == []


def test_authoritative_tables_unchanged_by_capability_flags() -> None:
    """Flags must not invent new authoritative tables or SQL columns."""
    names = set(AUTHORITATIVE_TABLES)
    assert "world_events" in names
    assert "tick_commits" in names
    # Capability flags are runner JSON only — never authoritative tables.
    for forbidden in (
        "v2_capability_flags",
        "capability_flags",
        "runner_capability_flags",
    ):
        assert forbidden not in names
