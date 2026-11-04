"""Three strictly separated detached representation layers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Final

from analysis.delegation_representation_alignment import (
    RepresentationAnalysisSummary,
)
from analysis.delegation_representation_contract import (
    REPRESENTATION_FORBIDDEN_RESULT_FIELDS,
    REPRESENTATION_SCOPE_KINDS,
    RepresentationAnalysisError,
    RepresentationCandidateStatus,
    require_candidate_id,
    require_owner_token,
)
from analysis.delegation_representation_identity import (
    RepresentationAnalysis,
)
from analysis.delegation_representation_objective import (
    RepresentationObjectiveAnchorRow,
    RepresentationWindowEvidence,
)
from analysis.delegation_representation_rows import RepresentationHarvestRows

__all__ = [
    "RepresentationAnalyticalRow",
    "RepresentationLayerView",
    "RepresentationObjectiveRow",
    "RepresentationSubjectiveRow",
    "assert_representation_layer_separation",
    "project_representation_layers",
]

_MAX_FORBIDDEN: Final[frozenset[str]] = REPRESENTATION_FORBIDDEN_RESULT_FIELDS


@dataclass(frozen=True, slots=True)
class RepresentationObjectiveRow:
    """Aggregate objective counts only. No owner, candidate, or token field."""

    communication_count: int = 0
    transfer_count: int = 0
    harm_count: int = 0
    commitment_count: int = 0
    window_count: int = 0

    def __post_init__(self) -> None:
        for field in fields(type(self)):
            value = getattr(self, field.name)
            if type(value) is not int or value < 0:
                raise RepresentationAnalysisError("representation_invalid_row")


@dataclass(frozen=True, slots=True)
class RepresentationSubjectiveRow:
    """One owner's safe aggregate. Never a candidate id and never an owner id."""

    owner_token: str
    mandate_count: int = 0
    recognized_count: int = 0
    contested_count: int = 0
    rejected_count: int = 0
    revoked_count: int = 0
    position_count: int = 0
    revocation_count: int = 0
    conflict_count: int = 0

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        for field in fields(type(self)):
            if field.name == "owner_token":
                continue
            value = getattr(self, field.name)
            if type(value) is not int or value < 0:
                raise RepresentationAnalysisError("representation_invalid_row")


@dataclass(frozen=True, slots=True)
class RepresentationAnalyticalRow:
    """One analytical candidate summary. No owner id or owner token field."""

    candidate_id: str
    principal_kind: str
    scope_kind: str
    status: RepresentationCandidateStatus
    mandate_count: int
    representative_count: int
    lineage_kind: str

    def __post_init__(self) -> None:
        require_candidate_id(self.candidate_id)
        if self.scope_kind not in REPRESENTATION_SCOPE_KINDS:
            raise RepresentationAnalysisError("representation_invalid_row")
        if not isinstance(self.status, RepresentationCandidateStatus):
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.mandate_count) is not int or self.mandate_count < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.representative_count) is not int or self.representative_count < 0:
            raise RepresentationAnalysisError("representation_invalid_row")


@dataclass(frozen=True, slots=True)
class RepresentationLayerView:
    """The three separated layers of one detached representation analysis."""

    objective: RepresentationObjectiveRow
    subjective: tuple[RepresentationSubjectiveRow, ...] = ()
    analytical: tuple[RepresentationAnalyticalRow, ...] = ()


def _subjective_rows(
    rows: RepresentationHarvestRows,
) -> tuple[RepresentationSubjectiveRow, ...]:
    by_owner: dict[str, dict[str, int]] = {}
    for mandate in rows.mandates:
        bucket = by_owner.setdefault(mandate.owner_token, {})
        bucket["mandate_count"] = bucket.get("mandate_count", 0) + 1
        if mandate.status == "recognized":
            bucket["recognized_count"] = bucket.get("recognized_count", 0) + 1
        elif mandate.status == "contested":
            bucket["contested_count"] = bucket.get("contested_count", 0) + 1
        elif mandate.status == "rejected":
            bucket["rejected_count"] = bucket.get("rejected_count", 0) + 1
        elif mandate.status == "revoked":
            bucket["revoked_count"] = bucket.get("revoked_count", 0) + 1
    for position in rows.positions:
        bucket = by_owner.setdefault(position.owner_token, {})
        bucket["position_count"] = bucket.get("position_count", 0) + 1
    for revocation in rows.revocations:
        bucket = by_owner.setdefault(revocation.owner_token, {})
        bucket["revocation_count"] = bucket.get("revocation_count", 0) + 1
    for conflict in rows.conflicts:
        bucket = by_owner.setdefault(conflict.owner_token, {})
        bucket["conflict_count"] = bucket.get("conflict_count", 0) + 1
    return tuple(
        RepresentationSubjectiveRow(owner_token=owner, **by_owner[owner])
        for owner in sorted(by_owner)
    )


def project_representation_layers(
    rows: RepresentationHarvestRows,
    analysis: RepresentationAnalysis,
    summary: RepresentationAnalysisSummary,
    windows: Sequence[RepresentationWindowEvidence] = (),
    objective_rows: Sequence[RepresentationObjectiveAnchorRow] = (),
) -> RepresentationLayerView:
    """Project the three detached layers without collapsing them."""

    if type(rows) is not RepresentationHarvestRows:
        raise TypeError("rows must be RepresentationHarvestRows")
    if type(analysis) is not RepresentationAnalysis:
        raise TypeError("analysis must be RepresentationAnalysis")
    if type(summary) is not RepresentationAnalysisSummary:
        raise TypeError("summary must be RepresentationAnalysisSummary")
    kinds = Counter(row.kind.value for row in objective_rows)
    lineage_by_target: dict[str, str] = {}
    for transition in analysis.transitions:
        lineage_by_target.setdefault(transition.to_candidate_id, transition.kind.value)
    objective = RepresentationObjectiveRow(
        communication_count=kinds.get("communication", 0),
        transfer_count=kinds.get("transfer", 0),
        harm_count=kinds.get("harm", 0),
        commitment_count=kinds.get("commitment_declared", 0),
        window_count=len(windows),
    )
    analytical = tuple(
        RepresentationAnalyticalRow(
            candidate_id=candidate.candidate_id,
            principal_kind=candidate.principal_kind,
            scope_kind=candidate.scope_kind,
            status=candidate.status,
            mandate_count=candidate.mandate_count,
            representative_count=len(candidate.representative_tokens),
            lineage_kind=lineage_by_target.get(candidate.candidate_id, "emerged"),
        )
        for candidate in analysis.candidates
    )
    view = RepresentationLayerView(
        objective=objective,
        subjective=_subjective_rows(rows),
        analytical=analytical,
    )
    assert_representation_layer_separation(view)
    return view


def assert_representation_layer_separation(view: RepresentationLayerView) -> None:
    """Fail closed when a layer leaks an identity or a forbidden result field."""

    if type(view) is not RepresentationLayerView:
        raise TypeError("view must be RepresentationLayerView")
    objective_fields = {field.name for field in fields(RepresentationObjectiveRow)}
    if objective_fields & {"owner_token", "owner_id", "candidate_id", "subject_token"}:
        raise RepresentationAnalysisError("representation_layer_leak")
    analytical_fields = {field.name for field in fields(RepresentationAnalyticalRow)}
    if analytical_fields & {"owner_token", "owner_id", "actor_token"}:
        raise RepresentationAnalysisError("representation_layer_leak")
    for subjective_row in view.subjective:
        if subjective_row.owner_token.startswith("rep-"):
            raise RepresentationAnalysisError("representation_layer_leak")
    for analytical_row in view.analytical:
        if analytical_row.principal_kind in {
            "agent",
        } and analytical_row.candidate_id.startswith("rmd-"):
            raise RepresentationAnalysisError("representation_layer_leak")
    for model in (
        RepresentationObjectiveRow,
        RepresentationSubjectiveRow,
        RepresentationAnalyticalRow,
        RepresentationLayerView,
    ):
        if {field.name for field in fields(model)} & _MAX_FORBIDDEN:
            raise RepresentationAnalysisError("representation_layer_leak")
