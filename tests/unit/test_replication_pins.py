# mypy: ignore-errors
"""V4-28 depth pins: catalog suffix, closed-world compatibility, no truth."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.cognition import ReplicationLedger
from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from api.routes.replication import SCIENTIFIC_REPLICATION_ROUTE_COUNT
from simulation.replication_models import REPLICATION_SNAPSHOT_VERSION

pytestmark = pytest.mark.unit


def test_catalog_appends_six_without_widening_truth() -> None:
    assert METRIC_FAMILY_COUNT == 262
    values = tuple(item.value for item in MetricFamilyId)
    assert values[244:250] == (
        "scientific_hypothesis_structure",
        "scientific_hypothesis_evidence",
        "scientific_hypothesis_test_activity",
        "scientific_hypothesis_revisions",
        "scientific_hypothesis_provenance",
        "scientific_hypothesis_prediction_outcomes",
    )
    assert values[250:256] == (
        "scientific_replication_design_lineage",
        "scientific_replication_conditions",
        "scientific_replication_results",
        "scientific_replication_uncertainty",
        "scientific_replication_relationships",
        "scientific_replication_social_interpretation",
    )
    assert not any("truth" in value or "consensus" in value for value in values)


def test_no_new_schema_migration_flag_or_wire_version() -> None:
    root = Path(__file__).resolve().parents[2]
    assert sorted((root / "alembic" / "versions").glob("0018_*.py")) == []
    assert SCIENTIFIC_REPLICATION_ROUTE_COUNT == 8
    assert REPLICATION_SNAPSHOT_VERSION == "scientific-replication-snapshot-v1"
    assert not hasattr(ReplicationLedger, "truth")
    assert not hasattr(ReplicationLedger, "proven")
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (root / "src").rglob("*.py")
        if "replication" in path.name
    )
    assert "runner-config-v58" not in sources
