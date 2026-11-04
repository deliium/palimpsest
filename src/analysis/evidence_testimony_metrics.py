"""Three detached evidence metric documents.

The alignment family is researcher-facing only. It never feeds cognition,
prompts, memory, world state, observer semantics, or a verdict.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from analysis.evidence_testimony_alignment import (
    EvidenceAnalysis,
    EvidenceAnalysisSummary,
)
from analysis.evidence_testimony_layers import EvidenceLayerView
from analysis.evidence_testimony_rows import EvidenceHarvestRows
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
    "compute_evidence_objective_alignment",
    "compute_evidence_provenance_continuity",
    "compute_evidence_source_structure",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.evidence_testimony_metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _histogram(values: tuple[tuple[str, int], ...]) -> str:
    return json.dumps(dict(sorted(values)), separators=(",", ":"))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _availability(rows: EvidenceHarvestRows | None) -> MetricAvailability:
    if rows is None:
        return MetricAvailability.ABSENT
    if rows.coverage.value == "partial":
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(rows: EvidenceHarvestRows | None) -> MetricCoverage:
    if rows is None:
        return _ABSENT_COVERAGE
    observed = (
        len(rows.sources)
        + len(rows.testimony)
        + len(rows.items)
        + len(rows.evaluations)
    )
    expected = max(observed, 1)
    return MetricCoverage(
        observed=observed,
        expected=expected,
        ratio=quantize_float(observed / expected),
    )


def _document(
    family: MetricFamilyId,
    rows: EvidenceHarvestRows | None,
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
            source_kind="evidence_testimony_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )
    _LOG.info(
        "evidence_metric family=%s availability=%s",
        spec.family_id.value,
        availability.value,
    )
    return document


def compute_evidence_source_structure(
    rows: EvidenceHarvestRows | None,
    analysis: EvidenceAnalysis | None,
    summary: EvidenceAnalysisSummary | None,
    layers: EvidenceLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``evidence_source_structure@1``."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        values = {
            "candidate_count": len(analysis.candidates),
            "source_count": len(rows.sources),
            "source_kind_histogram": _histogram(summary.source_kind_counts),
            "testimony_count": len(rows.testimony),
            "item_count": len(rows.items),
            "interpretation_histogram": _histogram(summary.interpretation_counts),
            "confidence_band_histogram": _histogram(summary.confidence_band_counts),
            "multi_owner_candidate_ratio": _ratio(
                summary.multi_owner_candidate_count,
                summary.candidate_count,
            ),
            "uncorroborated_item_ratio": _ratio(
                summary.uncorroborated_item_count,
                summary.active_item_count,
            ),
        }
    return _document(
        MetricFamilyId.EVIDENCE_SOURCE_STRUCTURE,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="evidence_source_structure_v1",
    )


def compute_evidence_provenance_continuity(
    rows: EvidenceHarvestRows | None,
    analysis: EvidenceAnalysis | None,
    summary: EvidenceAnalysisSummary | None,
    layers: EvidenceLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``evidence_provenance_continuity@1``."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        values = {
            "provenance_channel_histogram": _histogram(
                summary.provenance_channel_counts
            ),
            "independent_root_ratio": _ratio(
                summary.independent_root_count, summary.rooted_testimony_count
            ),
            "communicated_testimony_ratio": _ratio(
                summary.communicated_testimony_count, summary.testimony_count
            ),
            "custody_link_count": summary.custody_link_count,
            "custody_complete_ratio": _ratio(
                summary.custody_complete_source_count,
                summary.custody_applicable_source_count,
            ),
            "custody_incomplete_count": summary.custody_incomplete_count,
            "custody_conflicting_count": summary.custody_conflicting_count,
            "missing_provenance_ratio": _ratio(
                summary.missing_provenance_source_count, summary.source_count
            ),
        }
    return _document(
        MetricFamilyId.EVIDENCE_PROVENANCE_CONTINUITY,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="evidence_provenance_continuity_v1",
    )


def compute_evidence_objective_alignment(
    rows: EvidenceHarvestRows | None,
    analysis: EvidenceAnalysis | None,
    summary: EvidenceAnalysisSummary | None,
    layers: EvidenceLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Append ``evidence_objective_alignment@1``. Researcher-only, never a verdict."""

    if rows is None or analysis is None or summary is None or layers is None:
        values: dict[str, object] = {}
    else:
        applicable = (
            summary.consistent_count
            + summary.unresolved_count
            + summary.inconsistent_count
        )
        values = {
            "aligned_item_count": summary.aligned_item_count,
            "consistent_count": summary.consistent_count,
            "unresolved_count": summary.unresolved_count,
            "inconsistent_count": summary.inconsistent_count,
            "not_applicable_count": summary.not_applicable_count,
            "consistency_ratio": _ratio(summary.consistent_count, applicable),
            "custody_match_count": summary.custody_match_count,
            "custody_mismatch_count": summary.custody_mismatch_count,
            "custody_unknown_count": summary.custody_unknown_count,
        }
    return _document(
        MetricFamilyId.EVIDENCE_OBJECTIVE_ALIGNMENT,
        rows,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="evidence_objective_alignment_v1",
    )
