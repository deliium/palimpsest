"""Repeated behavior and private norm belief stay different readings."""

from __future__ import annotations

import logging

import pytest

from analysis.models import MetricAvailability
from analysis.social_norm_metrics import (
    EMERGENT_SOCIAL_NORMS_METRIC_VERSION,
    compute_emergent_social_norms,
    compute_norm_persistence,
)
from analysis.specifications import metric_specification


def test_metric_tag_and_divergence(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="analysis.social_norm_metrics")
    spec = metric_specification("emergent_social_norms")
    assert spec.version_identifier == EMERGENT_SOCIAL_NORMS_METRIC_VERSION
    assert EMERGENT_SOCIAL_NORMS_METRIC_VERSION == "emergent_social_norms@1"
    empty = compute_emergent_social_norms(
        {"behavior_rows": (), "belief_rows": ()},
        run_id="run-norms",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert any(
        record.levelno == logging.WARNING
        and "social_norms_metric_empty" in record.getMessage()
        and "reason=no_rows" in record.getMessage()
        for record in caplog.records
    )
    document = compute_emergent_social_norms(
        {
            "behavior_rows": (
                {
                    "tick": 1,
                    "actor_id": "ada",
                    "kind": "give",
                    "other_id": "ben",
                    "success": True,
                    "location_id": "clearing",
                    "food_quantity": 1.0,
                },
                {
                    "tick": 2,
                    "actor_id": "ben",
                    "kind": "give",
                    "other_id": "ada",
                    "success": True,
                    "location_id": "clearing",
                    "food_quantity": 1.0,
                },
            ),
            "belief_rows": (),
        },
        run_id="run-norms",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["return_transfer_rate"] == 1.0
    assert "return_transfer" in str(document.values["repetition_without_belief"])
    believed = compute_emergent_social_norms(
        {
            "behavior_rows": (),
            "belief_rows": (
                {
                    "tick": 1,
                    "owner_id": "ada",
                    "pattern": "spare_after_sleep",
                    "status": "active",
                    "confidence": 0.4,
                    "supporter_count": 1,
                    "consequences": (),
                    "response": "follow",
                },
            ),
        },
        run_id="run-norms",
        input_revision="rev-1",
    )
    assert believed.values["mean_confidence"] == 0.4
    assert "spare_after_sleep" in str(believed.values["belief_without_repetition"])
    assert believed.values["spare_after_sleep_rate"] == "absent"


def test_persistence_splits_behavior_from_belief(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="analysis.social_norm_metrics")
    empty = compute_norm_persistence(
        (),
        run_id="run-norms",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert any(
        record.levelno == logging.WARNING
        and "social_norms_metric_empty" in record.getMessage()
        and "reason=no_history" in record.getMessage()
        for record in caplog.records
    )
    history = (
        {
            "rates": {"spare_after_sleep": 0.8},
            "beliefs": (),
        },
        {
            "rates": {"spare_after_sleep": 0.6},
            "beliefs": (),
        },
    )
    persisted = compute_norm_persistence(
        history,
        run_id="run-norms",
        input_revision="rev-1",
    )
    assert persisted.values["behavior_persistence"] == 1.0
    assert persisted.values["belief_persistence"] == 0.0
