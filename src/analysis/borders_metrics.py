# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Four detached border metric families.

Counts, ratios, and closed label distributions only. No border score, control
score, sovereignty finding, winner, or composite exists.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.borders_contract import (
    BorderAgreementRow,
    BorderAlignmentRow,
    BorderOverlapRow,
    BorderPatternRow,
    BorderRecognitionRow,
)
from analysis.borders_policy import BORDERS_ANALYSIS_POLICY_VERSION
from analysis.borders_rows import BorderHarvestRows
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
    "compute_border_agreement_recognition",
    "compute_border_claim_structure",
    "compute_border_control_alignment",
    "compute_border_overlap_contest",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.borders.metrics")

_ABSENT_COVERAGE: Final[MetricCoverage] = MetricCoverage(
    observed=0, expected=0, ratio=None
)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return quantize_float(numerator / denominator)


def _distribution(values: Sequence[str]) -> str:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return ";".join(f"{key}={counts[key]}" for key in sorted(counts))


def _document(
    family: MetricFamilyId,
    *,
    available: bool,
    run_id: str,
    input_revision: str,
    values: dict[str, object],
) -> MetricDocument:
    spec = metric_specification(family)
    availability = (
        MetricAvailability.PRESENT if available else MetricAvailability.ABSENT
    )
    coverage = (
        MetricCoverage(
            observed=1 if available else 0,
            expected=1,
            ratio=1.0 if available else None,
        )
        if available
        else _ABSENT_COVERAGE
    )
    return MetricDocument(
        schema_version=METRIC_DOCUMENT_SCHEMA_VERSION,
        metric_family=spec.family_id.value,
        algorithm_version=spec.algorithm_version,
        library_versions=library_versions(),
        run_id=run_id,
        input_revision=input_revision,
        evidence_stages=frozenset(spec.evidence_inputs),
        population=spec.population,
        denominator=spec.denominator,
        coverage=coverage,
        availability=availability,
        values={} if availability is MetricAvailability.ABSENT else values,
        provenance=MetricProvenance(
            source_kind="border_analysis",
            source_ids=(
                run_id,
                input_revision,
                BORDERS_ANALYSIS_POLICY_VERSION,
            ),
            notes_code="detached_border_analysis",
        ),
    )


def compute_border_claim_structure(
    rows: BorderHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    claims = rows.claims
    locations = {token for claim in claims for token in claim.location_tokens}
    edges = {edge for claim in claims for edge in claim.boundary_edge_tokens}
    statuses = [claim.status for claim in claims]
    resolved = sum(1 for claim in claims if claim.anchor_token)
    values = {
        "domain_count": len(claims),
        "location_count": len(locations),
        "boundary_edge_count": len(edges),
        "claimed_count": statuses.count("claimed"),
        "recognized_count": statuses.count("recognized"),
        "disputed_count": statuses.count("disputed"),
        "anchor_resolved_ratio": _ratio(resolved, len(claims)) or 0.0,
    }
    return _document(
        MetricFamilyId.BORDER_CLAIM_STRUCTURE,
        available=rows.coverage != "not_applicable",
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_border_overlap_contest(
    rows: BorderHarvestRows,
    overlaps: Sequence[BorderOverlapRow],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    values = {
        "overlap_pair_count": len(overlaps),
        "overlap_location_count": sum(item.overlap_count for item in overlaps),
        "dispute_count": sum(
            1 for item in overlaps if item.dispute_status == "disputed"
        ),
        "reciprocal_claim_count": sum(1 for item in overlaps if item.overlap_count > 0),
        "dispute_status_distribution": _distribution(
            [item.dispute_status for item in overlaps]
        ),
    }
    return _document(
        MetricFamilyId.BORDER_OVERLAP_CONTEST,
        available=rows.coverage != "not_applicable",
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_border_agreement_recognition(
    rows: BorderHarvestRows,
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    agreements: Sequence[BorderAgreementRow] = rows.agreements
    recognitions: Sequence[BorderRecognitionRow] = rows.recognitions
    recognized_edges = {
        edge
        for row in recognitions
        if row.status == "recognized"
        for edge in row.edge_tokens
    }
    all_edges = {edge for claim in rows.claims for edge in claim.boundary_edge_tokens}
    values = {
        "agreement_count": len(agreements),
        "agreement_status_distribution": _distribution(
            [item.status for item in agreements]
        ),
        "recognition_count": len(recognitions),
        "access_mode_distribution": _distribution(
            [item.mode for item in rows.access_expectations]
        ),
        "provision_distribution": _distribution(
            [provision for item in agreements for provision in item.provision_tokens]
        ),
        "recognized_edge_ratio": _ratio(len(recognized_edges), len(all_edges)) or 0.0,
    }
    return _document(
        MetricFamilyId.BORDER_AGREEMENT_RECOGNITION,
        available=rows.coverage != "not_applicable",
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )


def compute_border_control_alignment(
    rows: BorderHarvestRows,
    patterns: Sequence[BorderPatternRow],
    alignment: Sequence[BorderAlignmentRow],
    *,
    run_id: str,
    input_revision: str,
) -> MetricDocument:
    observed = [item for item in patterns if item.claim_count > 0]
    physical = [item for item in observed if item.physical_actions > 0]
    claim_aligned = [item for item in patterns if item.pattern == "claim_aligned"]
    agreement_aligned = [
        item for item in patterns if item.pattern == "agreement_aligned"
    ]
    values = {
        "pattern_distribution": _distribution([item.pattern for item in patterns]),
        "physical_use_ratio": _ratio(len(physical), len(observed)) or 0.0,
        "claim_alignment_ratio": _ratio(len(claim_aligned), len(observed)) or 0.0,
        "agreement_alignment_ratio": _ratio(len(agreement_aligned), len(observed))
        or 0.0,
        "alignment_distribution": _distribution([item.alignment for item in alignment]),
        "coverage_ratio": _ratio(len(observed), len(patterns)) or 0.0,
    }
    return _document(
        MetricFamilyId.BORDER_CONTROL_ALIGNMENT,
        available=rows.coverage != "not_applicable",
        run_id=run_id,
        input_revision=input_revision,
        values=values,
    )
