# mypy: ignore-errors
"""V4-11 catalog append and stale-pin guard."""

from __future__ import annotations

from pathlib import Path

from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
)

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_is_168_and_treaty_families_are_last() -> None:
    specs = all_metric_specifications()
    assert METRIC_FAMILY_COUNT == 168
    assert len(specs) == 168
    assert [spec.family_id for spec in specs[-4:]] == [
        MetricFamilyId.TREATY_STRUCTURE,
        MetricFamilyId.TREATY_VERSION_LINEAGE,
        MetricFamilyId.TREATY_RECOLLECTION,
        MetricFamilyId.TREATY_ANCHOR_COVERAGE,
    ]


def test_first_164_families_keep_order_and_versions() -> None:
    specs = all_metric_specifications()
    assert len(specs[:164]) == 164
    assert len({spec.family_id for spec in specs[:164]}) == 164
    assert all(spec.algorithm_version for spec in specs[:164])


def test_no_current_pin_asserts_164() -> None:
    for path in (ROOT / "tests").rglob("*.py"):
        if path.name == "test_diplomacy_treaty_catalog.py":
            continue
        assert "== 164" not in path.read_text(encoding="utf-8"), path
    stale_current = (
        "Closed catalog cardinality: **164**",
        "catalog stays at **164**",
        "| Metric families | 164",
        "164 metric families",
        "164 families (`METRIC_FAMILY_COUNT`)",
    )
    for path in (
        *(ROOT / "docs").rglob("*.md"),
        *(ROOT / ".ai-factory").glob("*.md"),
        ROOT / "README.md",
    ):
        text = path.read_text(encoding="utf-8")
        for phrase in stale_current:
            assert phrase not in text, f"{path}: stale current pin {phrase!r}"


def test_historical_revision_statements_remain() -> None:
    description = (ROOT / ".ai-factory" / "DESCRIPTION.md").read_text(encoding="utf-8")
    assert "160 to **164**" in description or "160 -> 164" in description
