"""Vocabulary convergence and semantic drift stay analysis-only."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from analysis.models import MetricAvailability
from analysis.semantic_naming_metrics import (
    EMERGENT_SEMANTIC_NAMING_METRIC_VERSION,
    compute_emergent_semantic_naming,
    compute_naming_persistence,
)
from analysis.specifications import metric_specification


def test_metric_tag_and_convergence(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="analysis.semantic_naming_metrics")
    spec = metric_specification("emergent_semantic_naming")
    assert spec.version_identifier == EMERGENT_SEMANTIC_NAMING_METRIC_VERSION
    assert EMERGENT_SEMANTIC_NAMING_METRIC_VERSION == "emergent_semantic_naming@1"
    empty = compute_emergent_semantic_naming(
        (),
        run_id="run-naming",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert any(
        "semantic_naming_metric_empty" in record.getMessage()
        and "no_rows" in record.getMessage()
        for record in caplog.records
    )
    document = compute_emergent_semantic_naming(
        (
            {
                "tick": 3,
                "owner_id": "alice",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.5,
                "sense_revision": 0,
                "transmission": "observed",
                "competing_label_ids": (),
                "merged_into": None,
            },
            {
                "tick": 3,
                "owner_id": "bob",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.6,
                "sense_revision": 0,
                "transmission": "communicated",
                "competing_label_ids": (),
                "merged_into": None,
            },
            {
                "tick": 3,
                "owner_id": "cy",
                "label_token": "place_bbbb2222",
                "referent_kind": "location",
                "top_candidate_id": "loc-clearing",
                "status": "active",
                "strength": 0.45,
                "sense_revision": 0,
                "transmission": "observed",
                "competing_label_ids": (),
                "merged_into": None,
            },
        ),
        run_id="run-naming",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["shared_label_rate"] == 0.5
    assert document.values["preferred_label_agreement"] == 1.0
    assert document.values["empty_lexicon_owner_rate"] == 0.0
    assert "semantic_naming_metric_computed" in caplog.text


def test_drift_keys_on_separate_setup() -> None:
    document = compute_emergent_semantic_naming(
        (
            {
                "tick": 1,
                "owner_id": "alice",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.5,
                "sense_revision": 0,
                "transmission": "observed",
                "competing_label_ids": ("other",),
                "merged_into": None,
            },
            {
                "tick": 2,
                "owner_id": "alice",
                "label_token": "dead_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "active",
                "strength": 0.55,
                "sense_revision": 1,
                "transmission": "observed",
                "competing_label_ids": (),
                "merged_into": None,
            },
            {
                "tick": 2,
                "owner_id": "alice",
                "label_token": "place_aaaa1111",
                "referent_kind": "location",
                "top_candidate_id": "loc-forest",
                "status": "retired",
                "strength": 0.1,
                "sense_revision": 0,
                "transmission": "observed",
                "competing_label_ids": (),
                "merged_into": "deadbind",
            },
        ),
        run_id="run-naming",
        input_revision="rev-2",
    )
    assert document.values["meaning_shift_rate"] == 0.5
    assert document.values["label_turnover_rate"] == 1.0
    assert document.values["mean_sense_revision"] == 0.5
    assert document.values["merge_rate"] > 0.0


def test_persistence_empty_history_is_absent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="analysis.semantic_naming_metrics")
    empty = compute_naming_persistence(
        (),
        run_id="run-naming",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert empty.values["label_persistence"] == "absent"
    assert any("no_history" in record.getMessage() for record in caplog.records)
    history = (
        {
            "bindings": (
                {
                    "owner_id": "alice",
                    "label_token": "place_aaaa1111",
                    "top_candidate_id": "loc-forest",
                    "status": "active",
                    "strength": 0.5,
                    "sense_revision": 0,
                },
            )
        },
        {
            "bindings": (
                {
                    "owner_id": "alice",
                    "label_token": "place_aaaa1111",
                    "top_candidate_id": "loc-forest",
                    "status": "active",
                    "strength": 0.55,
                    "sense_revision": 0,
                },
            )
        },
    )
    present = compute_naming_persistence(
        history,
        run_id="run-naming",
        input_revision="rev-1",
    )
    assert present.values["label_persistence"] == 1.0
    assert present.values["sense_stability"] == 1.0


def test_metrics_module_stays_import_closed() -> None:
    source = Path("src/analysis/semantic_naming_metrics.py").read_text(encoding="utf-8")
    assert "agents" not in source
    assert "apply_naming_update" not in source
    assert "AgentRuntime" not in source
