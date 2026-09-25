"""Reflection metric family from in-run audits (analysis-only).

Never feeds values into cognition or memory formation. Inputs are counts only.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Final

from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "REFLECTION_METRIC_VERSION",
    "ReflectionReport",
    "compute_reflection",
]

REFLECTION_METRIC_VERSION: Final[str] = "reflection@1"
_LOG: Final[logging.Logger] = logging.getLogger("analysis.reflection_metrics")
_VALUE_KEYS: Final[tuple[str, ...]] = (
    "reflection_invocations",
    "belief_revisions",
    "hypotheses",
    "goals_adopted",
    "goals_abandoned",
    "relationship_reassessments",
    "patterns_detected",
)
_KIND_FIELDS: Final[dict[str, str]] = {
    "revised_belief": "belief_revisions",
    "updated_self_belief": "belief_revisions",
    "new_hypothesis": "hypotheses",
    "new_long_term_goal": "goals_adopted",
    "abandoned_goal": "goals_abandoned",
    "relationship_reassessment": "relationship_reassessments",
}


@dataclass(frozen=True, slots=True)
class ReflectionReport:
    """Neutral count aggregate. No belief text or memory content."""

    run_id: str
    reflection_invocations: int = 0
    belief_revisions: int = 0
    hypotheses: int = 0
    goals_adopted: int = 0
    goals_abandoned: int = 0
    relationship_reassessments: int = 0
    patterns_detected: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("ReflectionReport.run_id", self.run_id),
        )
        for name in _VALUE_KEYS:
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"ReflectionReport.{name}", getattr(self, name)
                ),
            )


def compute_reflection(
    report: ReflectionReport,
    *,
    input_revision: str,
) -> MetricDocument:
    """Summarize reflection counts into a catalog MetricDocument."""
    started = time.perf_counter()
    if type(report) is not ReflectionReport:
        raise TypeError("compute_reflection: invalid_report")
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.REFLECTION)
    if report.reflection_invocations == 0:
        _LOG.debug(
            "reflection_metrics_assembled family_id=%s value_keys=%s",
            spec.family_id.value,
            (),
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
                source_kind="reflection",
                source_ids=(),
                notes_code="no_audits",
            ),
        )
    values = {key: quantize_float(float(getattr(report, key))) for key in _VALUE_KEYS}
    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "reflection_metrics_assembled family_id=%s value_keys=%s duration_ms=%s",
        spec.family_id.value,
        tuple(values),
        duration_ms,
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
        coverage=MetricCoverage(
            observed=report.reflection_invocations,
            expected=report.reflection_invocations,
        ),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="reflection",
            source_ids=(report.run_id,),
            notes_code="ok",
        ),
    )
