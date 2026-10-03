"""Prediction calibration metric tests."""

from __future__ import annotations

from analysis.models import MetricAvailability
from analysis.prediction_calibration_metrics import (
    CalibrationRow,
    compute_prediction_calibration,
)


def test_empty_calibration_absent() -> None:
    doc = compute_prediction_calibration([], run_id="run-c", input_revision="rev-1")
    assert doc.availability is MetricAvailability.ABSENT


def test_perfect_calibration() -> None:
    rows = [
        CalibrationRow(predicted_confidence=0.1, empirical_outcome=0.1),
        CalibrationRow(predicted_confidence=0.9, empirical_outcome=0.9),
    ]
    doc = compute_prediction_calibration(rows, run_id="run-c", input_revision="rev-1")
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["brier_score"] == 0.0
    assert doc.values["mean_absolute_calibration_error"] == 0.0
    assert doc.values["evaluated_count"] == 2
    assert doc.values["bin_count_used"] == 2


def test_brier_squared_error_mean() -> None:
    rows = [
        CalibrationRow(predicted_confidence=1.0, empirical_outcome=0.0),
        CalibrationRow(predicted_confidence=0.0, empirical_outcome=0.0),
    ]
    doc = compute_prediction_calibration(rows, run_id="run-c", input_revision="rev-1")
    assert doc.values["brier_score"] == 0.5
