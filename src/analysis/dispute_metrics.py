"""Three detached metric documents over dispute analysis.

The objective-alignment ratios are researcher-facing only. They never feed
cognition, prompts, memory, world state, observer semantics, or a verdict.
"""

from __future__ import annotations

import json
import logging
from typing import Final

from analysis.dispute_layers import DisputeLayerView
from analysis.dispute_lineage import DisputeAnalysis, DisputeAnalysisSummary
from analysis.disputes import DisputeHarvestRows
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
    "compute_dispute_claim_structure",
    "compute_dispute_resolution_alignment",
    "compute_dispute_testimony_independence",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _histogram(values: dict[str, int]) -> str:
    return json.dumps(dict(sorted(values.items())), separators=(",", ":"))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _availability(summary: DisputeAnalysisSummary | None) -> MetricAvailability:
    if summary is None:
        return MetricAvailability.ABSENT
    if summary.coverage.partial:
        return MetricAvailability.PARTIAL
    return MetricAvailability.PRESENT


def _coverage(summary: DisputeAnalysisSummary | None) -> MetricCoverage:
    if summary is None:
        return _ABSENT_COVERAGE
    return MetricCoverage(
        observed=summary.coverage.observed,
        expected=summary.coverage.expected,
        ratio=summary.coverage.coverage_fraction,
    )


def _document(
    family: MetricFamilyId,
    summary: DisputeAnalysisSummary | None,
    *,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
    notes_code: str,
) -> MetricDocument:
    spec = metric_specification(family)
    availability = _availability(summary)
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
        coverage=_coverage(summary),
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="dispute_analysis",
            source_ids=(run_id,),
            notes_code=notes_code,
        ),
    )
    _LOG.info(
        "dispute_metric family=%s availability=%s",
        spec.family_id.value,
        availability.value,
    )
    return document


def compute_dispute_claim_structure(
    summary: DisputeAnalysisSummary | None,
    layers: DisputeLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Claim/counterclaim structure, kind and polarity histograms, and ratios."""

    if summary is None or layers is None:
        return _document(
            MetricFamilyId.DISPUTE_CLAIM_STRUCTURE,
            None,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="dispute_claim_structure_absent",
        )
    values: dict[str, object] = {
        "candidate_count": summary.candidate_count,
        "case_count": summary.case_count,
        "claim_count": summary.claim_count,
        "counterclaim_count": summary.counterclaim_count,
        "counterclaim_ratio": _ratio(summary.counterclaim_count, summary.claim_count),
        "claim_kind_histogram": _histogram(dict(summary.claim_kind_histogram)),
        "polarity_histogram": _histogram(dict(summary.polarity_histogram)),
        "rule_referenced_case_ratio": _ratio(
            summary.rule_referenced_case_count,
            summary.cases_with_claims_count,
        ),
        "evidence_backed_claim_ratio": _ratio(
            summary.evidence_backed_claim_count, summary.claim_count
        ),
        "multi_party_case_ratio": _ratio(
            summary.multi_party_case_count,
            summary.cases_with_claims_count,
        ),
        "unresolved_case_ratio": _ratio(
            summary.unresolved_case_count,
            summary.cases_with_claims_count,
        ),
    }
    return _document(
        MetricFamilyId.DISPUTE_CLAIM_STRUCTURE,
        summary,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="dispute_claim_structure_detached",
    )


def compute_dispute_testimony_independence(
    summary: DisputeAnalysisSummary | None,
    rows: DisputeHarvestRows | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Testimony channel, root independence, and contradiction ratios."""

    if summary is None or rows is None:
        return _document(
            MetricFamilyId.DISPUTE_TESTIMONY_INDEPENDENCE,
            None,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="dispute_testimony_independence_absent",
        )
    values: dict[str, object] = {
        "testimony_count": summary.testimony_count,
        "direct_testimony_ratio": _ratio(
            summary.direct_testimony_count, summary.testimony_count
        ),
        "communicated_testimony_ratio": _ratio(
            summary.communicated_testimony_count, summary.testimony_count
        ),
        "distinct_root_count": summary.distinct_testimony_root_count,
        "shared_root_duplicate_ratio": _ratio(
            summary.shared_root_duplicate_count, summary.testimony_count
        ),
        "independently_evidenced_ratio": _ratio(
            summary.independently_evidenced_count, summary.testimony_count
        ),
        "contradictory_testimony_ratio": _ratio(
            summary.contradictory_testimony_count, summary.testimony_count
        ),
        "claim_without_testimony_ratio": _ratio(
            summary.claim_count - summary.claim_with_testimony_count,
            summary.claim_count,
        ),
    }
    return _document(
        MetricFamilyId.DISPUTE_TESTIMONY_INDEPENDENCE,
        summary,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="dispute_testimony_independence_detached",
    )


def compute_dispute_resolution_alignment(
    summary: DisputeAnalysisSummary | None,
    analysis: DisputeAnalysis | None,
    layers: DisputeLayerView | None,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    """Resolution status, per-party declarations, and objective alignment."""

    if summary is None or analysis is None or layers is None:
        return _document(
            MetricFamilyId.DISPUTE_RESOLUTION_ALIGNMENT,
            None,
            run_id=run_id,
            input_revision=input_revision,
            values={},
            notes_code="dispute_resolution_alignment_absent",
        )
    values: dict[str, object] = {
        "resolution_count": summary.resolution_count,
        "proposed_resolution_count": summary.proposed_resolution_count,
        "apparently_accepted_resolution_count": (
            summary.apparently_accepted_resolution_count
        ),
        "contested_resolution_count": summary.contested_resolution_count,
        "accepted_party_ratio": _ratio(summary.accepted_count, summary.response_count),
        "rejected_party_ratio": _ratio(summary.rejected_count, summary.response_count),
        "mediation_linked_resolution_ratio": _ratio(
            summary.mediation_linked_resolution_count,
            summary.resolution_count,
        ),
        "objective_supported_claim_ratio": _ratio(
            summary.supported_claim_count,
            summary.objective_anchored_claim_count,
        ),
        "objective_unresolved_claim_ratio": _ratio(
            summary.unresolved_claim_count,
            summary.objective_anchored_claim_count,
        ),
        "objective_inconsistent_claim_ratio": _ratio(
            summary.inconsistent_claim_count,
            summary.objective_anchored_claim_count,
        ),
        "agreement_alignment_ratio": _ratio(
            summary.aligned_resolution_pair_count,
            summary.resolution_pair_count,
        ),
    }
    return _document(
        MetricFamilyId.DISPUTE_RESOLUTION_ALIGNMENT,
        summary,
        run_id=run_id,
        input_revision=input_revision,
        values=values,
        notes_code="dispute_resolution_alignment_detached",
    )
