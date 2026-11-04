"""Three strictly separated detached evidence layers.

Objective counts, owner-scoped rows, and analytical candidates are different
types. Collapsing them is a hard failure, never a presentation choice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Final

from analysis.evidence_testimony_alignment import (
    EvidenceAnalysis,
    EvidenceAnalysisSummary,
)
from analysis.evidence_testimony_contract import (
    EVIDENCE_FORBIDDEN_RESULT_FIELDS,
    EVIDENCE_OWNER_LOCAL_PREFIXES,
    EvidenceAnalysisError,
    EvidenceCandidateStatus,
    require_candidate_id,
    require_owner_token,
)
from analysis.evidence_testimony_objective import (
    EvidenceObjectiveAnchorRow,
    EvidenceWindowEvidence,
)
from analysis.evidence_testimony_rows import EvidenceHarvestRows

__all__ = [
    "EvidenceAnalyticalRow",
    "EvidenceLayerView",
    "EvidenceObjectiveRow",
    "EvidenceSubjectiveRow",
    "assert_evidence_layer_separation",
    "project_evidence_layers",
]

_MAX_FORBIDDEN: Final[frozenset[str]] = EVIDENCE_FORBIDDEN_RESULT_FIELDS


@dataclass(frozen=True, slots=True)
class EvidenceObjectiveRow:
    """Aggregate objective counts only. No owner, candidate, or token field."""

    source_count: int = 0
    testimony_count: int = 0
    record_count: int = 0
    artifact_count: int = 0
    custody_link_count: int = 0
    contradiction_count: int = 0
    evaluation_count: int = 0
    window_count: int = 0

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            value = getattr(self, field.name)
            if type(value) is not int or value < 0:
                raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceSubjectiveRow:
    """One owner's safe aggregate. Never a candidate id and never an owner id."""

    owner_token: str
    source_count: int = 0
    testimony_count: int = 0
    item_count: int = 0
    contradiction_count: int = 0
    evaluation_count: int = 0
    complete_custody_count: int = 0
    incomplete_custody_count: int = 0
    conflicting_custody_count: int = 0

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        for field in fields(type(self)):
            if field.name == "owner_token":
                continue
            value = getattr(self, field.name)
            if type(value) is not int or value < 0:
                raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceAnalyticalRow:
    """One analytical candidate summary. No owner id or owner token field."""

    candidate_id: str
    subject_token: str
    status: EvidenceCandidateStatus
    owner_count: int
    item_count: int

    def __post_init__(self) -> None:
        require_candidate_id(self.candidate_id)
        if self.subject_token.startswith(EVIDENCE_OWNER_LOCAL_PREFIXES):
            raise EvidenceAnalysisError("evidence_testimony_layer_leak")
        if not isinstance(self.status, EvidenceCandidateStatus):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        if type(self.owner_count) is not int or self.owner_count < 0:
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        if type(self.item_count) is not int or self.item_count < 0:
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceLayerView:
    """The three separated layers of one detached evidence analysis."""

    objective: EvidenceObjectiveRow
    subjective: tuple[EvidenceSubjectiveRow, ...] = ()
    analytical: tuple[EvidenceAnalyticalRow, ...] = ()


def _subjective_rows(rows: EvidenceHarvestRows) -> tuple[EvidenceSubjectiveRow, ...]:
    by_owner: dict[str, dict[str, int]] = {}
    for source_row in rows.sources:
        bucket = by_owner.setdefault(source_row.owner_token, {})
        bucket["source_count"] = bucket.get("source_count", 0) + 1
        if source_row.custody_status == "complete_belief":
            bucket["complete_custody_count"] = (
                bucket.get("complete_custody_count", 0) + 1
            )
        elif source_row.custody_status == "incomplete_belief":
            bucket["incomplete_custody_count"] = (
                bucket.get("incomplete_custody_count", 0) + 1
            )
        elif source_row.custody_status == "conflicting_belief":
            bucket["conflicting_custody_count"] = (
                bucket.get("conflicting_custody_count", 0) + 1
            )
    for testimony_row in rows.testimony:
        bucket = by_owner.setdefault(testimony_row.owner_token, {})
        bucket["testimony_count"] = bucket.get("testimony_count", 0) + 1
    for item_row in rows.items:
        bucket = by_owner.setdefault(item_row.owner_token, {})
        bucket["item_count"] = bucket.get("item_count", 0) + 1
    for contradiction_row in rows.contradictions:
        bucket = by_owner.setdefault(contradiction_row.owner_token, {})
        bucket["contradiction_count"] = bucket.get("contradiction_count", 0) + 1
    for evaluation_row in rows.evaluations:
        bucket = by_owner.setdefault(evaluation_row.owner_token, {})
        bucket["evaluation_count"] = bucket.get("evaluation_count", 0) + 1
    return tuple(
        EvidenceSubjectiveRow(owner_token=owner, **by_owner[owner])
        for owner in sorted(by_owner)
    )


def project_evidence_layers(
    rows: EvidenceHarvestRows,
    analysis: EvidenceAnalysis,
    summary: EvidenceAnalysisSummary,
    windows: Sequence[EvidenceWindowEvidence] = (),
    objective_rows: Sequence[EvidenceObjectiveAnchorRow] = (),
) -> EvidenceLayerView:
    """Project the three detached layers without collapsing them."""

    if type(rows) is not EvidenceHarvestRows:
        raise TypeError("rows must be EvidenceHarvestRows")
    if type(analysis) is not EvidenceAnalysis:
        raise TypeError("analysis must be EvidenceAnalysis")
    if type(summary) is not EvidenceAnalysisSummary:
        raise TypeError("summary must be EvidenceAnalysisSummary")
    objective = EvidenceObjectiveRow(
        source_count=summary.source_count,
        testimony_count=summary.testimony_count,
        record_count=sum(
            1 for row in rows.sources if row.source_kind == "written_record"
        ),
        artifact_count=sum(1 for row in rows.sources if row.source_kind == "artifact"),
        custody_link_count=summary.custody_link_count,
        contradiction_count=len(rows.contradictions),
        evaluation_count=len(rows.evaluations),
        window_count=len(windows),
    )
    analytical = tuple(
        EvidenceAnalyticalRow(
            candidate_id=candidate.candidate_id,
            subject_token=candidate.subject_token,
            status=candidate.status,
            owner_count=len(candidate.owner_tokens),
            item_count=candidate.item_count,
        )
        for candidate in analysis.candidates
    )
    view = EvidenceLayerView(
        objective=objective,
        subjective=_subjective_rows(rows),
        analytical=analytical,
    )
    assert_evidence_layer_separation(view)
    return view


def assert_evidence_layer_separation(view: EvidenceLayerView) -> None:
    """Fail closed when a layer leaks an identity or a forbidden result field."""

    if type(view) is not EvidenceLayerView:
        raise TypeError("view must be EvidenceLayerView")
    objective_fields = {field.name for field in fields(EvidenceObjectiveRow)}
    if objective_fields & {"owner_token", "owner_id", "candidate_id", "subject_token"}:
        raise EvidenceAnalysisError("evidence_testimony_layer_leak")
    analytical_fields = {field.name for field in fields(EvidenceAnalyticalRow)}
    if analytical_fields & {"owner_token", "owner_id"}:
        raise EvidenceAnalysisError("evidence_testimony_layer_leak")
    for subjective_row in view.subjective:
        if subjective_row.owner_token.startswith("evid-"):
            raise EvidenceAnalysisError("evidence_testimony_layer_leak")
    for analytical_row in view.analytical:
        if analytical_row.subject_token.startswith(EVIDENCE_OWNER_LOCAL_PREFIXES):
            raise EvidenceAnalysisError("evidence_testimony_layer_leak")
    for model in (
        EvidenceObjectiveRow,
        EvidenceSubjectiveRow,
        EvidenceAnalyticalRow,
        EvidenceLayerView,
    ):
        if {field.name for field in fields(model)} & _MAX_FORBIDDEN:
            raise EvidenceAnalysisError("evidence_testimony_layer_leak")
