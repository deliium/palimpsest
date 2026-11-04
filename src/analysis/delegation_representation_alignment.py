"""Researcher-only representation summaries and objective scope alignment."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from analysis.delegation_representation_contract import (
    RepresentationAnalysisError,
    RepresentationCoverage,
    representation_owner_token,
)
from analysis.delegation_representation_identity import RepresentationAnalysis
from analysis.delegation_representation_objective import (
    RepresentationObjectiveAnchorKind,
    RepresentationObjectiveAnchorRow,
    RepresentationWindowEvidence,
)
from analysis.delegation_representation_rows import (
    RepresentationHarvestRows,
    RepresentationMandateRow,
)

__all__ = [
    "RepresentationAlignmentStatus",
    "RepresentationAnalysisSummary",
    "classify_representation_scope_alignment",
    "representation_analysis_digest",
    "summarize_representation",
]

_SEPARATOR: Final[str] = "\x1f"
_OBJECTIVE_SCOPES: Final[frozenset[str]] = frozenset(
    {"speak_for", "negotiate", "carry_message"}
)
_NOT_APPLICABLE_SCOPES: Final[frozenset[str]] = frozenset(
    {"transact", "decide", "coordinate_project", "unknown"}
)


class RepresentationAlignmentStatus(StrEnum):
    """Researcher-only alignment classification. Never a verdict."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class RepresentationAnalysisSummary:
    mandate_count: int
    candidate_count: int
    coverage: RepresentationCoverage
    principal_kind_counts: tuple[tuple[str, int], ...]
    scope_kind_counts: tuple[tuple[str, int], ...]
    duration_kind_counts: tuple[tuple[str, int], ...]
    provenance_counts: tuple[tuple[str, int], ...]
    status_counts: tuple[tuple[str, int], ...]
    recognized_count: int
    contested_count: int
    rejected_count: int
    support_root_total: int
    opposition_root_total: int
    positioned_mandate_count: int
    consistent_count: int
    unresolved_alignment_count: int
    inconsistent_count: int
    not_applicable_count: int
    aligned_mandate_count: int


def _window_for(
    mandate: RepresentationMandateRow, windows: Sequence[RepresentationWindowEvidence]
) -> tuple[int, int] | None:
    if not windows:
        return None
    end = mandate.end_tick if mandate.end_tick is not None else windows[-1].end_tick
    return (mandate.start_tick, end)


def classify_representation_scope_alignment(
    mandate: RepresentationMandateRow,
    anchors: Sequence[RepresentationObjectiveAnchorRow],
) -> RepresentationAlignmentStatus:
    """Classify one mandate against committed speech anchors for researchers."""

    if type(mandate) is not RepresentationMandateRow:
        raise TypeError("mandate must be RepresentationMandateRow")
    if mandate.unresolved_principal:
        return RepresentationAlignmentStatus.NOT_APPLICABLE
    if mandate.scope_kind not in _OBJECTIVE_SCOPES:
        return RepresentationAlignmentStatus.NOT_APPLICABLE
    if mandate.end_tick is not None and mandate.end_tick <= mandate.start_tick:
        return RepresentationAlignmentStatus.NOT_APPLICABLE
    representative = mandate.representative_token
    communications = [
        anchor
        for anchor in anchors
        if anchor.kind is RepresentationObjectiveAnchorKind.COMMUNICATION
        and anchor.actor_token is not None
        and representation_owner_token(anchor.actor_token) == representative
    ]
    if not communications:
        return RepresentationAlignmentStatus.UNRESOLVED
    end = (
        mandate.end_tick
        if mandate.end_tick is not None
        else max(anchor.tick for anchor in communications) + 1
    )
    inside = [
        anchor for anchor in communications if mandate.start_tick <= anchor.tick < end
    ]
    if inside:
        return RepresentationAlignmentStatus.CONSISTENT
    return RepresentationAlignmentStatus.INCONSISTENT


def _histogram(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items()))


def summarize_representation(
    rows: RepresentationHarvestRows,
    analysis: RepresentationAnalysis,
    *,
    anchors: Sequence[RepresentationObjectiveAnchorRow] = (),
    windows: Sequence[RepresentationWindowEvidence] = (),
) -> RepresentationAnalysisSummary:
    """Summarize detached rows with explicit denominators and coverage."""

    if type(rows) is not RepresentationHarvestRows:
        raise TypeError("rows must be RepresentationHarvestRows")
    if type(analysis) is not RepresentationAnalysis:
        raise TypeError("analysis must be RepresentationAnalysis")
    status_counts = Counter(row.status for row in rows.mandates)
    positioned = {position.mandate_id for position in rows.positions if position.active}
    aligned = [
        classify_representation_scope_alignment(mandate, anchors)
        for mandate in rows.mandates
    ]
    coverage = rows.coverage
    if windows and any(window.partial for window in windows):
        coverage = RepresentationCoverage.PARTIAL
    return RepresentationAnalysisSummary(
        mandate_count=len(rows.mandates),
        candidate_count=len(analysis.candidates),
        coverage=coverage,
        principal_kind_counts=_histogram(
            Counter(row.principal_kind for row in rows.mandates)
        ),
        scope_kind_counts=_histogram(Counter(row.scope_kind for row in rows.mandates)),
        duration_kind_counts=_histogram(
            Counter(row.duration_kind for row in rows.mandates)
        ),
        provenance_counts=_histogram(Counter(row.provenance for row in rows.mandates)),
        status_counts=_histogram(status_counts),
        recognized_count=status_counts.get("recognized", 0),
        contested_count=status_counts.get("contested", 0),
        rejected_count=status_counts.get("rejected", 0),
        support_root_total=sum(row.support_roots for row in rows.mandates),
        opposition_root_total=sum(row.opposition_roots for row in rows.mandates),
        positioned_mandate_count=len(positioned),
        consistent_count=aligned.count(RepresentationAlignmentStatus.CONSISTENT),
        unresolved_alignment_count=aligned.count(
            RepresentationAlignmentStatus.UNRESOLVED
        ),
        inconsistent_count=aligned.count(RepresentationAlignmentStatus.INCONSISTENT),
        not_applicable_count=aligned.count(
            RepresentationAlignmentStatus.NOT_APPLICABLE
        ),
        aligned_mandate_count=sum(
            1
            for status in aligned
            if status
            in {
                RepresentationAlignmentStatus.CONSISTENT,
                RepresentationAlignmentStatus.UNRESOLVED,
                RepresentationAlignmentStatus.INCONSISTENT,
            }
        ),
    )


def _summary_payload(summary: RepresentationAnalysisSummary) -> dict[str, object]:
    return {
        "mandate_count": summary.mandate_count,
        "candidate_count": summary.candidate_count,
        "coverage": summary.coverage.value,
        "principal_kind_counts": list(summary.principal_kind_counts),
        "scope_kind_counts": list(summary.scope_kind_counts),
        "duration_kind_counts": list(summary.duration_kind_counts),
        "provenance_counts": list(summary.provenance_counts),
        "status_counts": list(summary.status_counts),
        "recognized_count": summary.recognized_count,
        "contested_count": summary.contested_count,
        "rejected_count": summary.rejected_count,
        "support_root_total": summary.support_root_total,
        "opposition_root_total": summary.opposition_root_total,
        "positioned_mandate_count": summary.positioned_mandate_count,
        "consistent_count": summary.consistent_count,
        "unresolved_alignment_count": summary.unresolved_alignment_count,
        "inconsistent_count": summary.inconsistent_count,
        "not_applicable_count": summary.not_applicable_count,
        "aligned_mandate_count": summary.aligned_mandate_count,
    }


def representation_analysis_digest(summary: RepresentationAnalysisSummary) -> str:
    """Return a canonical digest over one representation summary."""

    if type(summary) is not RepresentationAnalysisSummary:
        raise TypeError("summary must be RepresentationAnalysisSummary")
    payload = json.dumps(
        _summary_payload(summary),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_separator_free(values: Sequence[str]) -> None:
    for value in values:
        if _SEPARATOR in value:
            raise RepresentationAnalysisError("representation_invalid_row")
