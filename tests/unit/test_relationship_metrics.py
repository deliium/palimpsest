"""Relationship stability metric tests."""

from __future__ import annotations

from analysis.models import MetricAvailability, RelationshipEdgeRow
from analysis.relationship_metrics import compute_relationship_stability
from analysis.serialization import metric_document_fingerprint


def test_relationship_stability_known_answer_and_missing_dimension() -> None:
    rows = [
        RelationshipEdgeRow(
            source_id="a",
            target_id="b",
            logical_tick=0,
            activation_state="active",
            trust=0.5,
            fear=None,
            ordinal=0,
        ),
        RelationshipEdgeRow(
            source_id="a",
            target_id="b",
            logical_tick=5,
            activation_state="active",
            trust=-0.5,
            fear=0.2,
            ordinal=1,
        ),
        RelationshipEdgeRow(
            source_id="a",
            target_id="c",
            logical_tick=1,
            activation_state="retired",
            trust=0.1,
            ordinal=0,
        ),
    ]
    doc = compute_relationship_stability(
        rows, run_id="run-r", input_revision="rev-1", window_end=10
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["active_edge_count"] == 1
    assert doc.values["retired_edge_count"] == 1
    assert doc.values["mean_abs_delta"] == 1.0
    assert doc.values["sign_change_rate"] == 1.0


def test_relationship_stability_empty_absent() -> None:
    doc = compute_relationship_stability(
        [], run_id="run-r", input_revision="rev-1", window_end=5
    )
    assert doc.availability is MetricAvailability.ABSENT


def test_relationship_stability_permutation() -> None:
    rows = [
        RelationshipEdgeRow(
            source_id="a", target_id="b", logical_tick=0, activation_state="active", trust=0.2
        ),
        RelationshipEdgeRow(
            source_id="a", target_id="b", logical_tick=3, activation_state="active", trust=0.8
        ),
        RelationshipEdgeRow(
            source_id="b", target_id="a", logical_tick=1, activation_state="active", trust=-0.1
        ),
    ]
    first = compute_relationship_stability(
        rows, run_id="run-r", input_revision="rev-1", window_end=8
    )
    second = compute_relationship_stability(
        list(reversed(rows)), run_id="run-r", input_revision="rev-1", window_end=8
    )
    assert metric_document_fingerprint(first) == metric_document_fingerprint(second)
