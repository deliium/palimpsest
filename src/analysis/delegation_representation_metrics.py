"""Three detached representation metric documents.

The alignment family is researcher-facing only. It never feeds cognition,
prompts, memory, world state, observer semantics, or a legitimacy finding.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from analysis.delegation_representation_alignment import (
    RepresentationAnalysisSummary,
)
from analysis.delegation_representation_identity import RepresentationAnalysis
from analysis.delegation_representation_layers import RepresentationLayerView
from analysis.delegation_representation_rows import RepresentationHarvestRows
from analysis.models import (
    METRIC_DOCUMENT_SCHEMA_VERSION,
    MetricAvailability,
    MetricCoverage,
    MetricDocument,
    MetricProvenance,
)
from analysis.numerical import library_versions, quantize_float
from analysis.specifications import MetricFamilyId, metric_specification

__all__ = [
    "compute_representation_mandate_structure",
    "compute_representation_recognition_support",
    "compute_representation_scope_alignment",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.delegation_representation_metrics"
)

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _histogram(values: tuple[tuple[str, int], ...]) -> str:
    return json.dumps(dict(sorted(values)), separators=(",", ":"))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _availability(rows: RepresentationHarvestRows | None) -> MetricAvailability:
    if rows is None:
        return MetricAvailability.ABSENT
    if rows.coverage.value == "partial":
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(rows: RepresentationHarvestRows | None) -> MetricCoverage:
    if rows is None:
        return _ABSENT_COVERAGE
    observed = (
        len(rows.mandates)
        + len(rows.positions)
        + len(rows.revocations)
        + len(rows.conflicts)
    )
    expected = max(observed, 1)
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=quantize_float(observed / expected),
    )


def _document(
    family: MetricFamilyId,
    rows: RepresentationHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability = _availability(rows)
    document = MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=_coverage(rows),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="delegation_representation_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )
    _LOG.info(
        "representation_metric family=%s availability=%s",
        spec.family_id.value,
        availability.value,
    )
    return document


def compute_representation_mandate_structure(
    rows: RepresentationHarvestRows | None,
    analysis: RepresentationAnalysis | None,
    summary: RepresentationAnalysisSummary | None,
    layers: RepresentationLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``representation_mandate_structure@1``."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        values = {
            "mandate_count": summary.mandate_count,
            "candidate_count": summary.candidate_count,
            "principal_kind_histogram": _histogram(summary.principal_kind_counts),
            "scope_kind_histogram": _histogram(summary.scope_kind_counts),
            "duration_kind_histogram": _histogram(summary.duration_kind_counts),
            "provenance_histogram": _histogram(summary.provenance_counts),
            "status_histogram": _histogram(summary.status_counts),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.REPRESENTATION_MANDATE_STRUCTURE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="representation_mandate_structure_v1",
    )


def compute_representation_recognition_support(
    rows: RepresentationHarvestRows | None,
    analysis: RepresentationAnalysis | None,
    summary: RepresentationAnalysisSummary | None,
    layers: RepresentationLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``representation_recognition_support@1``."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        denominator = summary.positioned_mandate_count
        values = {
            "recognized_count": summary.recognized_count,
            "contested_count": summary.contested_count,
            "rejected_count": summary.rejected_count,
            "support_root_total": summary.support_root_total,
            "opposition_root_total": summary.opposition_root_total,
            "positioned_mandate_count": denominator,
            "recognition_ratio": _ratio(summary.recognized_count, denominator),
            "contestation_ratio": _ratio(summary.contested_count, denominator),
            "rejection_ratio": _ratio(summary.rejected_count, denominator),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.REPRESENTATION_RECOGNITION_SUPPORT,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="representation_recognition_support_v1",
    )


def compute_representation_scope_alignment(
    rows: RepresentationHarvestRows | None,
    analysis: RepresentationAnalysis | None,
    summary: RepresentationAnalysisSummary | None,
    layers: RepresentationLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``representation_scope_alignment@1``. Researcher-only."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        applicable = summary.aligned_mandate_count
        values = {
            "consistent_count": summary.consistent_count,
            "unresolved_count": summary.unresolved_alignment_count,
            "inconsistent_count": summary.inconsistent_count,
            "not_applicable_count": summary.not_applicable_count,
            "aligned_mandate_count": applicable,
            "consistency_ratio": _ratio(summary.consistent_count, applicable),
            "inconsistency_ratio": _ratio(summary.inconsistent_count, applicable),
            "coverage": summary.coverage.value,
        }
    return _document(
        MetricFamilyId.REPRESENTATION_SCOPE_ALIGNMENT,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="representation_scope_alignment_v1",
    )
