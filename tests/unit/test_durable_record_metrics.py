"""Durable-record lineage / fidelity / survival metric computors."""

from __future__ import annotations

import logging

import pytest

from analysis.durable_record_metrics import (
    DURABLE_RECORD_FIDELITY_METRIC_VERSION,
    DURABLE_RECORD_LINEAGE_METRIC_VERSION,
    DURABLE_RECORD_SURVIVAL_METRIC_VERSION,
    compute_durable_record_fidelity,
    compute_durable_record_lineage,
    compute_durable_record_survival,
    summarize_copy_fidelity,
    summarize_durable_record_lineage,
    summarize_record_survival,
)
from analysis.models import MetricAvailability

pytestmark = pytest.mark.unit


def test_lineage_empty_is_absent() -> None:
    document = compute_durable_record_lineage(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.metric_family == "durable_record_lineage"
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == DURABLE_RECORD_LINEAGE_METRIC_VERSION
    )
    assert document.values["censoring_policy"].startswith("analysis-only")


def test_lineage_nonempty_histogram_and_tombstone_share(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rows = (
        {
            "artifact_id": "a0",
            "copy_generation": 0,
            "source_artifact_id": "a0",
            "integrity": "intact",
        },
        {
            "artifact_id": "a1",
            "parent_artifact_id": "a0",
            "source_artifact_id": "a0",
            "copy_generation": 1,
            "integrity": "intact",
        },
        {
            "artifact_id": "a2",
            "parent_artifact_id": "a1",
            "source_artifact_id": "a0",
            "copy_generation": 2,
            "integrity": "destroyed",
            "tombstone": True,
        },
    )
    with caplog.at_level(logging.DEBUG, logger="analysis.durable_record_metrics"):
        document = compute_durable_record_lineage(
            rows, run_id="run-1", input_revision="rev-1"
        )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["record_count"] == 3
    assert document.values["max_copy_generation"] == 2
    assert document.values["tombstone_count"] == 1
    assert document.values["tombstone_share"] == pytest.approx(1 / 3)
    assert document.values["parent_coverage"] == pytest.approx(2 / 3)
    assert document.values["generation_0_count"] == 1
    assert document.values["generation_1_count"] == 1
    assert document.values["generation_2_count"] == 1
    assert document.values["generation_histogram_encoded"] == "0:1,1:1,2:1"
    assert "durable_record_lineage_computed" in caplog.text
    summary = summarize_durable_record_lineage(rows)
    assert summary.max_copy_generation == 2


def test_fidelity_empty_is_absent() -> None:
    document = compute_durable_record_fidelity(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.metric_family == "durable_record_fidelity"
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == DURABLE_RECORD_FIDELITY_METRIC_VERSION
    )


def test_fidelity_perfect_and_lossy_rates() -> None:
    events = (
        {
            "kind": "artifact_copied",
            "fidelity_mode": "perfect",
            "child_artifact_id": "c1",
            "parent_artifact_id": "p1",
        },
        {
            "kind": "artifact_copied",
            "fidelity_mode": "lossy",
            "child_artifact_id": "c2",
            "parent_artifact_id": "p1",
            "mark_edit_distance": 2,
            "relation_edit_distance": 1,
        },
        {
            "kind": "artifact_copied",
            "fidelity_mode": "deterministic_mutation",
            "child_artifact_id": "c3",
            "parent_artifact_id": "p1",
            "mark_edit_distance": 1,
            "relation_edit_distance": 0,
        },
    )
    document = compute_durable_record_fidelity(
        events, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["copy_event_count"] == 3
    assert document.values["perfect_rate"] == pytest.approx(1 / 3)
    assert document.values["lossy_rate"] == pytest.approx(1 / 3)
    assert document.values["deterministic_mutation_rate"] == pytest.approx(1 / 3)
    assert document.values["mean_mark_edit_distance"] == pytest.approx(1.5)
    summary = summarize_copy_fidelity(events)
    assert summary.copy_event_count == 3


def test_fidelity_uses_parent_child_mark_distance() -> None:
    events = (
        {
            "kind": "artifact_copied",
            "fidelity_mode": "deterministic_mutation",
            "child_artifact_id": "c1",
            "parent_artifact_id": "p1",
        },
    )
    records = (
        {"artifact_id": "p1", "marks": ("a", "b", "c")},
        {"artifact_id": "c1", "marks": ("a", "x")},
    )
    summary = summarize_copy_fidelity(events, record_rows=records)
    # dropped b,c (+2) and inserted x (+1) → 3
    assert summary.mean_mark_edit_distance == 3.0


def test_survival_empty_is_absent() -> None:
    document = compute_durable_record_survival(
        (),
        run_id="run-1",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.metric_family == "durable_record_survival"
    assert (
        f"{document.metric_family}@{document.algorithm_version}"
        == DURABLE_RECORD_SURVIVAL_METRIC_VERSION
    )


def test_survival_author_death_and_false_persist() -> None:
    rows = (
        {
            "artifact_id": "false-1",
            "author_id": "body-author",
            "created_tick": 1,
            "integrity": "intact",
            "marks": ("wrong", "claim"),
        },
        {
            "artifact_id": "damaged-1",
            "author_id": "body-author",
            "created_tick": 1,
            "integrity": "damaged",
            "marks": ("a",),
        },
        {
            "artifact_id": "gone-1",
            "author_id": "body-other",
            "created_tick": 2,
            "integrity": "destroyed",
            "marks": (),
        },
    )
    document = compute_durable_record_survival(
        rows,
        run_id="run-1",
        input_revision="rev-1",
        death_ticks_by_body={"body-author": 5},
        false_record_expectations=(
            {"artifact_id": "false-1", "expected_marks": ("wrong", "claim")},
        ),
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["intact_count"] == 1
    assert document.values["damaged_count"] == 1
    assert document.values["destroyed_count"] == 1
    assert document.values["intact_after_author_death_count"] == 1
    assert document.values["false_record_persistence_rate"] == 1.0
    summary = summarize_record_survival(
        rows,
        death_ticks_by_body={"body-author": 5},
        false_record_expectations=(
            {"artifact_id": "false-1", "expected_marks": ("wrong", "claim")},
        ),
    )
    assert summary.intact_after_author_death_count == 1


def test_module_avoids_cognition_and_private_world_imports() -> None:
    import analysis.durable_record_metrics as mod
    from pathlib import Path

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "import agents" not in source
    assert "from agents" not in source
    assert "import world._" not in source
    assert "from world._" not in source
    assert "import world.artifacts" not in source
    assert "from world.artifacts" not in source
