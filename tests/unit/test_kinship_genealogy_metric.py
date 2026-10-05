"""Kinship genealogy analysis metric tests."""

from __future__ import annotations

from analysis.kinship_genealogy_metrics import (
    KINSHIP_GENEALOGY_METRIC_VERSION,
    KinshipEdgeRow,
    compute_kinship_genealogy,
)
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId, metric_specification


def test_metric_family_registered() -> None:
    spec = metric_specification(MetricFamilyId.KINSHIP_GENEALOGY)
    assert spec.version_identifier == KINSHIP_GENEALOGY_METRIC_VERSION


def test_compute_kinship_genealogy_stats() -> None:
    document = compute_kinship_genealogy(
        (
            KinshipEdgeRow("agent-a", "agent-b", 0),
            KinshipEdgeRow("agent-a", "agent-c", 0),
        ),
        run_id="run-kinship-metric",
        input_revision="rev-1",
        known_agent_ids=("agent-a", "agent-b", "agent-c", "agent-orphan"),
        max_depth=4,
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["edge_count"] == 2
    assert document.values["orphan_count"] == 1
    assert document.values["component_sizes"] == "3,1"


def test_empty_rows_absent() -> None:
    document = compute_kinship_genealogy(
        (),
        run_id="run-kinship-empty",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
