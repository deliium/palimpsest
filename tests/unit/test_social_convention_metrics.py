"""Objective repetition and private habit belief stay different readings."""

from __future__ import annotations

import logging

import pytest

from analysis.models import MetricAvailability
from analysis.social_convention_metrics import (
    PERSISTENT_SOCIAL_CONVENTIONS_METRIC_VERSION,
    compute_convention_persistence,
    compute_persistent_social_conventions,
)
from analysis.specifications import metric_specification


def test_metric_tag_and_divergence(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="analysis.social_convention_metrics")
    spec = metric_specification("persistent_social_conventions")
    assert spec.version_identifier == PERSISTENT_SOCIAL_CONVENTIONS_METRIC_VERSION
    assert (
        PERSISTENT_SOCIAL_CONVENTIONS_METRIC_VERSION
        == "persistent_social_conventions@1"
    )
    empty = compute_persistent_social_conventions(
        {"objective_rows": (), "habit_rows": ()},
        run_id="run-conventions",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert any(
        record.levelno == logging.WARNING
        and "social_conventions_metric_empty" in record.getMessage()
        and "reason=no_rows" in record.getMessage()
        for record in caplog.records
    )
    document = compute_persistent_social_conventions(
        {
            "objective_rows": (
                {
                    "tick": 1,
                    "actor_id": "ada",
                    "kind": "wait",
                    "other_id": None,
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
                {
                    "tick": 1,
                    "actor_id": "ben",
                    "kind": "wait",
                    "other_id": None,
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
                {
                    "tick": 2,
                    "actor_id": "ada",
                    "kind": "wait",
                    "other_id": None,
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
                {
                    "tick": 2,
                    "actor_id": "ben",
                    "kind": "talk",
                    "other_id": "ada",
                    "success": True,
                    "location_id": "clearing",
                    "day_phase": None,
                },
            ),
            "habit_rows": (),
        },
        run_id="run-conventions",
        input_revision="rev-1",
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["recurrent_meeting_rate"] == 1.0
    assert "colocated_meeting" in str(document.values["repetition_without_habit"])
    believed = compute_persistent_social_conventions(
        {
            "objective_rows": (),
            "habit_rows": (
                {
                    "tick": 1,
                    "owner_id": "ada",
                    "situation": "colocated_meeting",
                    "usual_action": "wait",
                    "status": "active",
                    "strength": 0.4,
                    "participant_count": 2,
                    "transmission": "observed",
                    "explanation": "forgotten",
                    "conceptualization": "none",
                    "duration_ticks": 10,
                    "variant_count": 0,
                },
            ),
        },
        run_id="run-conventions",
        input_revision="rev-1",
    )
    assert believed.values["mean_habit_strength"] == 0.4
    assert "colocated_meeting" in str(believed.values["habit_without_repetition"])
    assert believed.values["recurrent_meeting_rate"] == "absent"
    assert believed.values["reason_loss_persistence"] == 1.0
    assert believed.values["ritual_like_persistence"] == 1.0


def test_persistence_splits_behavior_from_habit(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="analysis.social_convention_metrics")
    empty = compute_convention_persistence(
        (),
        run_id="run-conventions",
        input_revision="rev-1",
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert any(
        record.levelno == logging.WARNING
        and "social_conventions_metric_empty" in record.getMessage()
        and "reason=no_history" in record.getMessage()
        for record in caplog.records
    )
    history = (
        {
            "rates": {"colocated_meeting": 0.8},
            "habits": (),
        },
        {
            "rates": {"colocated_meeting": 0.6},
            "habits": (),
        },
    )
    persisted = compute_convention_persistence(
        history,
        run_id="run-conventions",
        input_revision="rev-1",
    )
    assert persisted.values["behavior_persistence"] == 1.0
    assert persisted.values["habit_persistence"] == 0.0
