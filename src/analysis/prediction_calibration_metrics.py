"""Prediction calibration from detached confidence / outcome pairs.

Analysis-only. Does not invent engine probabilities; confidence is the
subjective score already on the snapshot. Leaves ``causal_world_model@1``
value keys unchanged.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "CALIBRATION_BIN_EDGES",
    "PREDICTION_CALIBRATION_METRIC_VERSION",
    "CalibrationRow",
    "compute_prediction_calibration",
]

PREDICTION_CALIBRATION_METRIC_VERSION: Final[str] = "prediction_calibration@1"
# Fixed confidence bins: (0.0, 0.2], (0.2, 0.4], (0.4, 0.6], (0.6, 0.8], (0.8, 1.0].
# Confidence exactly 0.0 is placed in the first bin.
CALIBRATION_BIN_EDGES: Final[tuple[float, ...]] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.prediction_calibration_metrics"
)


@dataclass(frozen=True, slots=True)
class CalibrationRow:
    """One joined predicted confidence and empirical outcome in [0, 1]."""

    predicted_confidence: float
    empirical_outcome: float


def compute_prediction_calibration(
    rows: Sequence[object],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Brier score and mean absolute calibration error over fixed bins."""
    document_run = require_stable_id("run_id", run_id)
    revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.PREDICTION_CALIBRATION)
    parsed = _parse_rows(rows)
    _LOG.debug(
        "prediction_calibration_compute",
        extra={
            "operation": "compute_prediction_calibration",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "evaluated_count": len(parsed),
            "bin_edge_count": len(CALIBRATION_BIN_EDGES) - 1,
        },
    )
    if not parsed:
        return _document(
            spec,
            document_run,
            revision,
            MetricAvailability.ABSENT,
            {},
            notes_code="no_evaluable_rows",
        )

    squared = [
        (row.predicted_confidence - row.empirical_outcome) ** 2 for row in parsed
    ]
    brier = quantize_float(
        require_finite(float(sum(squared) / float(len(squared))))
    )
    bin_errors, bins_used = _bin_absolute_errors(parsed)
    mace: float | None
    if bins_used == 0:
        mace = None
    else:
        mace = quantize_float(
            require_finite(float(sum(bin_errors) / float(bins_used)))
        )
    values: dict[str, object] = {
        "brier_score": brier,
        "mean_absolute_calibration_error": mace,
        "evaluated_count": len(parsed),
        "bin_count_used": bins_used,
    }
    _LOG.debug(
        "prediction_calibration_done",
        extra={
            "operation": "compute_prediction_calibration",
            "family_id": spec.family_id.value,
            "run_id": document_run,
            "evaluated_count": len(parsed),
            "bin_count_used": bins_used,
            "availability": MetricAvailability.PRESENT.value,
        },
    )
    return _document(
        spec,
        document_run,
        revision,
        MetricAvailability.PRESENT,
        values,
        notes_code="ok",
        observed=len(parsed),
        expected=len(parsed),
    )


def _parse_rows(rows: Sequence[object]) -> tuple[CalibrationRow, ...]:
    if isinstance(rows, (str, bytes, set, frozenset, Mapping)) or not isinstance(
        rows, Sequence
    ):
        raise TypeError("rows: not_ordered")
    parsed: list[CalibrationRow] = []
    for index, row in enumerate(rows):
        if type(row) is CalibrationRow:
            pred = row.predicted_confidence
            outcome = row.empirical_outcome
        else:
            pred = getattr(row, "predicted_confidence", None)
            outcome = getattr(row, "empirical_outcome", None)
        if isinstance(pred, bool) or not isinstance(pred, (int, float)):
            raise TypeError(f"rows[{index}]: invalid_predicted_confidence")
        if isinstance(outcome, bool) or not isinstance(outcome, (int, float)):
            raise TypeError(f"rows[{index}]: invalid_empirical_outcome")
        pred_f = require_finite(float(pred))
        outcome_f = require_finite(float(outcome))
        if pred_f < 0.0 or pred_f > 1.0:
            raise ValueError(f"rows[{index}]: predicted_confidence_out_of_range")
        if outcome_f < 0.0 or outcome_f > 1.0:
            raise ValueError(f"rows[{index}]: empirical_outcome_out_of_range")
        parsed.append(
            CalibrationRow(
                predicted_confidence=pred_f,
                empirical_outcome=outcome_f,
            )
        )
    return tuple(parsed)


def _bin_index(confidence: float) -> int:
    edges = CALIBRATION_BIN_EDGES
    if confidence <= edges[0]:
        return 0
    for index in range(1, len(edges)):
        if confidence <= edges[index]:
            return index - 1
    return len(edges) - 2


def _bin_absolute_errors(
    rows: Sequence[CalibrationRow],
) -> tuple[list[float], int]:
    bin_count = len(CALIBRATION_BIN_EDGES) - 1
    preds: list[list[float]] = [[] for _ in range(bin_count)]
    outcomes: list[list[float]] = [[] for _ in range(bin_count)]
    for row in rows:
        index = _bin_index(row.predicted_confidence)
        preds[index].append(row.predicted_confidence)
        outcomes[index].append(row.empirical_outcome)
    errors: list[float] = []
    used = 0
    for index in range(bin_count):
        if not preds[index]:
            continue
        mean_pred = float(sum(preds[index]) / len(preds[index]))
        mean_outcome = float(sum(outcomes[index]) / len(outcomes[index]))
        errors.append(abs(mean_pred - mean_outcome))
        used += 1
    return errors, used


def _document(
    spec: object,
    run_id: str,
    revision: str,
    availability: MetricAvailability,
    values: Mapping[str, object],
    *,
    notes_code: str,
    observed: int = 0,
    expected: int = 0,
) -> MetricDocument:
    family = getattr(spec, "family_id")
    algorithm_version = getattr(spec, "algorithm_version")
    evidence_inputs = getattr(spec, "evidence_inputs")
    population = getattr(spec, "population")
    denominator = getattr(spec, "denominator")
    coverage = None
    if availability is MetricAvailability.PRESENT:
        coverage = MetricCoverage(observed=observed, expected=expected)
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=family.value,
        algorithm_version=algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=revision,
        evidence_stages=frozenset(evidence_inputs),
        population=population,
        denominator=denominator,
        coverage=coverage,
        availability=availability,
        values=dict(values),
        provenance=MetricProvenance(
            source_kind="prediction_calibration",
            source_ids=() if availability is MetricAvailability.ABSENT else (run_id,),
            notes_code=notes_code,
        ),
    )
