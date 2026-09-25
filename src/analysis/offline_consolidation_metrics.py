"""Sleep-consolidation metric family from in-run audits (analysis-only).

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
    "OFFLINE_CONSOLIDATION_METRIC_VERSION",
    "OfflineConsolidationReport",
    "compute_offline_consolidation",
]

OFFLINE_CONSOLIDATION_METRIC_VERSION: Final[str] = "offline_consolidation@1"
_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.offline_consolidation_metrics"
)
_VALUE_KEYS: Final[tuple[str, ...]] = (
    "consolidation_invocations",
    "traces_strengthened",
    "traces_soft_forgotten",
    "patterns_merged",
    "belief_revisions",
    "relationship_revisions",
    "goal_transitions",
)


@dataclass(frozen=True, slots=True)
class OfflineConsolidationReport:
    """Neutral count aggregate. No belief text or memory content."""

    run_id: str
    consolidation_invocations: int = 0
    traces_strengthened: int = 0
    traces_soft_forgotten: int = 0
    patterns_merged: int = 0
    belief_revisions: int = 0
    relationship_revisions: int = 0
    goal_transitions: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "run_id",
            require_stable_id("OfflineConsolidationReport.run_id", self.run_id),
        )
        for name in (
            "consolidation_invocations",
            "traces_strengthened",
            "traces_soft_forgotten",
            "patterns_merged",
            "belief_revisions",
            "relationship_revisions",
            "goal_transitions",
        ):
            object.__setattr__(
                self,
                name,
                require_exact_nonneg_int(
                    f"OfflineConsolidationReport.{name}", getattr(self, name)
                ),
            )


def compute_offline_consolidation(
    report: OfflineConsolidationReport,
    *,
    input_revision: str,
) -> MetricDocument:
    """Summarize consolidation counts into a catalog MetricDocument."""
    started = time.perf_counter()
    if type(report) is not OfflineConsolidationReport:
        raise TypeError("compute_offline_consolidation: invalid_report")
    input_revision = require_stable_id("input_revision", input_revision)
    spec = metric_specification(MetricFamilyId.OFFLINE_CONSOLIDATION)
    if report.consolidation_invocations == 0:
        _LOG.debug(
            "offline_consolidation_metrics_assembled family_id=%s value_keys=%s",
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
                source_kind="offline_consolidation",
                source_ids=(),
                notes_code="no_audits",
            ),
        )
    values = {
        key: quantize_float(float(getattr(report, key))) for key in _VALUE_KEYS
    }
    duration_ms = int((time.perf_counter() - started) * 1000)
    _LOG.debug(
        "offline_consolidation_metrics_assembled family_id=%s value_keys=%s "
        "duration_ms=%s",
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
            observed=report.consolidation_invocations,
            expected=report.consolidation_invocations,
        ),
        availability=MetricAvailability.PRESENT,
        values=values,
        provenance=MetricProvenance(
            source_kind="offline_consolidation",
            source_ids=(report.run_id,),
            notes_code="ok",
        ),
    )
