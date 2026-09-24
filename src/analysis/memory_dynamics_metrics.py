"""Memory-dynamics metric family from in-run V2 recall audits (analysis-only).

Never feeds values into cognition or memory formation. Inputs are IDs, counts,
and distortion codes only — never narratives or concept text.
"""

from __future__ import annotations

import logging
import time
from typing import Final

from analysis.models import (
    MEMORY_DYNAMICS_METRIC_VERSION,
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MemoryDynamicsReport,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float, require_finite
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_stable_id

__all__ = [
    "MEMORY_DYNAMICS_METRIC_VERSION",
    "compute_memory_dynamics",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.memory_dynamics_metrics")

_SOURCE_CONFUSION: Final[str] = "source_confusion"
_INTERFERENCE: Final[str] = "interference"


def compute_memory_dynamics(
    report: MemoryDynamicsReport,
    *,
    input_revision: str,
) -> MetricDocument:
    """Summarize a MemoryDynamicsReport into a catalog MetricDocument."""
    started = time.perf_counter()
    if type(report) is not MemoryDynamicsReport:
        raise TypeError("compute_memory_dynamics: invalid_report")
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.MEMORY_DYNAMICS)
    audit_count = len(report.audits)

    if audit_count == 0:
        _LOG.debug(
            "memory_dynamics_metric_absent",
            extra={
                "operation": "compute_memory_dynamics",
                "run_id": report.run_id,
                "condition_id": report.condition_id,
                "audit_count": 0,
                "metric_family": spec.family_id.value,
            },
        )
        return MetricDocument(
            schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
            metric_family=spec.family_id.value,
            algorithm_version=spec.algorithm_version,
            library_versions=library_versions(),
            run_id=report.run_id,
            input_revision=input_revision,
            evidence_stages=frozenset(spec.evidence_inputs),
            population=spec.population,
            denominator=spec.denominator,
            coverage=None,
            availability=MetricAvailability.ABSENT,
            values={},
            provenance=MetricProvenance(
                source_kind="memory_dynamics",
                source_ids=(),
                notes_code="no_audits",
            ),
        )

    accuracy_scores: list[float] = []
    survival_scores: list[float] = []
    calibration_scores: list[float] = []
    confusion_hits = 0
    interference_hits = 0

    for row in report.audits:
        true_ids = frozenset(row.source_memory_ids)
        selected = frozenset(row.selected_ids)
        if true_ids or selected:
            union = true_ids | selected
            accuracy = (
                0.0
                if not union
                else float(len(true_ids & selected)) / float(len(union))
            )
        else:
            source_n = max(row.source_count, 1)
            accuracy = min(1.0, float(row.selected_count) / float(source_n))
        accuracy_scores.append(accuracy)

        pool = max(row.source_count + row.competitor_count, 1)
        survival_scores.append(float(row.selected_count) / float(pool))

        before = require_finite(float(row.confidence_before))
        after = require_finite(float(row.confidence_after))
        if before <= 0.0:
            calibration_scores.append(1.0 if after <= 0.0 else 0.0)
        else:
            calibration_scores.append(max(0.0, min(1.0, after / before)))

        codes = frozenset(row.distortion_codes)
        if _SOURCE_CONFUSION in codes:
            confusion_hits += 1
        if _INTERFERENCE in codes:
            interference_hits += 1

    n = float(audit_count)
    values = {
        "recall_accuracy": quantize_float(sum(accuracy_scores) / n),
        "source_confusion": quantize_float(confusion_hits / n),
        "memory_survival": quantize_float(sum(survival_scores) / n),
        "interference": quantize_float(interference_hits / n),
        "confidence_calibration": quantize_float(sum(calibration_scores) / n),
    }
    coverage = MetricCoverage(observed=audit_count, expected=audit_count)
    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "memory_dynamics_metric_complete",
        extra={
            "operation": "compute_memory_dynamics",
            "run_id": report.run_id,
            "condition_id": report.condition_id,
            "audit_count": audit_count,
            "metric_family": spec.family_id.value,
            "value_keys": tuple(values.keys()),
            "duration_ms": duration_ms,
        },
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=report.run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="memory_dynamics",
            source_ids=tuple(row.reconstruction_id for row in report.audits),
            notes_code="ok",
        ),
    )
