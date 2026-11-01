"""Three strictly separated organization layers and leakage checks."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organization_contract import (
    OrganizationAnalysisError,
    OrganizationCoverage,
)
from analysis.organization_detection import (
    OrganizationCandidate,
    OrganizationDetectionResult,
)
from analysis.organization_identity import OrganizationIdentityAssignment
from analysis.organization_operations import (
    OrganizationOperationSummary,
    operation_action_ticks,
    operation_concept_counts,
)
from analysis.organizations import OrganizationHarvestRows
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "OrganizationLayerView",
    "OrganizationObjectiveRow",
    "OrganizationSubjectiveRow",
    "assert_organization_layer_separation",
    "project_organization_layers",
]

_CONCEPT_PREFIX: Final[str] = "orgc-"
_ANALYTICAL_PREFIX: Final[str] = "org-"


@dataclass(frozen=True, slots=True)
class OrganizationObjectiveRow:
    """Objective structure counts for one window; never any ids."""

    window_index: int
    tick: int
    member_count: int
    role_count: int
    goal_count: int
    resource_count: int
    procedure_count: int
    record_count: int
    commitment_count: int
    identity_count: int
    resolved_anchor_count: int
    unresolved_anchor_count: int
    operation_action_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "window_index",
            "tick",
            "member_count",
            "role_count",
            "goal_count",
            "resource_count",
            "procedure_count",
            "record_count",
            "commitment_count",
            "identity_count",
            "resolved_anchor_count",
            "unresolved_anchor_count",
            "operation_action_count",
        ):
            require_exact_nonneg_int(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class OrganizationSubjectiveRow:
    """One owner's claim about one owner-local ``orgc-`` concept."""

    owner_id: str
    organization_id: str
    member_count: int
    status: str
    temporal_scope: str
    self_identified: bool
    operation_count: int = 0
    contested_operation_count: int = 0

    def __post_init__(self) -> None:
        if not self.organization_id.startswith(_CONCEPT_PREFIX):
            raise OrganizationAnalysisError("organization_layer_leak")
        require_exact_nonneg_int("member_count", self.member_count)
        require_exact_nonneg_int("operation_count", self.operation_count)
        require_exact_nonneg_int(
            "contested_operation_count", self.contested_operation_count
        )


@dataclass(frozen=True, slots=True)
class OrganizationLayerView:
    objective: tuple[OrganizationObjectiveRow, ...]
    subjective: tuple[OrganizationSubjectiveRow, ...]
    analytical: tuple[OrganizationCandidate, ...]
    coverage: OrganizationCoverage
    operations: OrganizationOperationSummary | None = None


def project_organization_layers(
    detection: OrganizationDetectionResult | OrganizationIdentityAssignment,
    owner_rows: Sequence[OrganizationHarvestRows],
    operation_rows: Sequence[object] | None = None,
    operation_summary: OrganizationOperationSummary | None = None,
) -> OrganizationLayerView:
    """Project objective counts, owner claims, and analytical candidates."""

    windows: Sequence[object]
    if type(detection) is OrganizationIdentityAssignment:
        windows = detection.windows
        candidates = tuple(
            candidate for window in detection.windows for candidate in window.candidates
        )
        coverage = detection.coverage
    elif type(detection) is OrganizationDetectionResult:
        windows = detection.windows
        candidates = detection.candidates
        coverage = detection.coverage
    else:
        raise OrganizationAnalysisError("organization_layer_leak")

    action_ticks = (
        operation_action_ticks(operation_rows)  # type: ignore[arg-type]
        if operation_rows
        else ()
    )
    concept_counts = {
        (owner_id, organization_id): (count, contested)
        for owner_id, organization_id, count, contested in (
            operation_concept_counts(operation_rows)  # type: ignore[arg-type]
            if operation_rows
            else ()
        )
    }
    objective: list[OrganizationObjectiveRow] = []
    for window in windows:
        role_count = 0
        goal_count = 0
        resource_count = 0
        procedure_count = 0
        record_count = 0
        commitment_count = 0
        identity_count = 0
        member_count = 0
        resolved = 0
        for owner in owner_rows:
            for concept in owner.concepts:
                if not (
                    concept.first_tick <= window.end_tick
                    and concept.last_tick >= window.start_tick
                ):
                    continue
                member_count += sum(
                    1
                    for member in owner.members
                    if member.organization_id == concept.organization_id
                )
                role_count += sum(
                    1
                    for item in owner.roles
                    if item.organization_id == concept.organization_id
                )
                goal_count += sum(
                    1
                    for item in owner.goals
                    if item.organization_id == concept.organization_id
                )
                resource_count += sum(
                    1
                    for item in owner.resources
                    if item.organization_id == concept.organization_id
                )
                procedure_count += sum(
                    1
                    for item in owner.procedures
                    if item.organization_id == concept.organization_id
                )
                record_count += sum(
                    1
                    for item in owner.records
                    if item.organization_id == concept.organization_id
                )
                commitment_count += sum(
                    1
                    for item in owner.commitments
                    if item.organization_id == concept.organization_id
                )
                identity_count += sum(
                    1
                    for item in owner.identities
                    if item.organization_id == concept.organization_id
                )
        for candidate in candidates:
            if candidate.window_index != window.window_index:
                continue
            resolved += len(candidate.anchor_signature)
        objective.append(
            OrganizationObjectiveRow(
                window_index=window.window_index,
                tick=window.start_tick,
                member_count=member_count,
                role_count=role_count,
                goal_count=goal_count,
                resource_count=resource_count,
                procedure_count=procedure_count,
                record_count=record_count,
                commitment_count=commitment_count,
                identity_count=identity_count,
                resolved_anchor_count=resolved,
                unresolved_anchor_count=0,
                operation_action_count=sum(
                    1
                    for tick in action_ticks
                    if window.start_tick <= tick <= window.end_tick
                ),
            )
        )

    subjective: list[OrganizationSubjectiveRow] = []
    for owner in owner_rows:
        for concept in owner.concepts:
            self_identified = any(
                identity.organization_id == concept.organization_id
                and identity.stance in {"member", "affiliated"}
                for identity in owner.identities
            )
            operation_count, contested_count = concept_counts.get(
                (owner.owner.owner_id, concept.organization_id), (0, 0)
            )
            subjective.append(
                OrganizationSubjectiveRow(
                    owner_id=owner.owner.owner_id,
                    organization_id=concept.organization_id,
                    member_count=sum(
                        1
                        for member in owner.members
                        if member.organization_id == concept.organization_id
                    ),
                    status=concept.status,
                    temporal_scope=concept.temporal_scope,
                    self_identified=self_identified,
                    operation_count=operation_count,
                    contested_operation_count=contested_count,
                )
            )
    view = OrganizationLayerView(
        objective=tuple(objective),
        subjective=tuple(
            sorted(subjective, key=lambda row: (row.owner_id, row.organization_id))
        ),
        analytical=tuple(sorted(candidates, key=lambda item: item.candidate_key)),
        coverage=coverage,
        operations=operation_summary,
    )
    assert_organization_layer_separation(view)
    return view


def assert_organization_layer_separation(view: OrganizationLayerView) -> None:
    """Fail closed when an authority layer leaks another layer's identity."""

    if type(view) is not OrganizationLayerView:
        raise OrganizationAnalysisError("organization_layer_leak")
    for row in view.objective:
        for name in row.__dataclass_fields__:
            value = getattr(row, name)
            if isinstance(value, str) and (
                value.startswith(_CONCEPT_PREFIX)
                or value.startswith(_ANALYTICAL_PREFIX)
            ):
                raise OrganizationAnalysisError("organization_layer_leak")
    for subjective in view.subjective:
        if not subjective.organization_id.startswith(_CONCEPT_PREFIX):
            raise OrganizationAnalysisError("organization_layer_leak")
        if subjective.organization_id.startswith(_ANALYTICAL_PREFIX):
            raise OrganizationAnalysisError("organization_layer_leak")
    for candidate in view.analytical:
        if candidate.candidate_key.startswith(_CONCEPT_PREFIX):
            raise OrganizationAnalysisError("organization_layer_leak")
        if candidate.candidate_key.startswith(_ANALYTICAL_PREFIX):
            raise OrganizationAnalysisError("organization_layer_leak")
    summary = view.operations
    if summary is not None:
        if type(summary) is not OrganizationOperationSummary:
            raise OrganizationAnalysisError("organization_layer_leak")
        for operation_candidate in summary.candidates:
            if not operation_candidate.organization_id.startswith(_ANALYTICAL_PREFIX):
                raise OrganizationAnalysisError("organization_layer_leak")
            for name in operation_candidate.__dataclass_fields__:
                value = getattr(operation_candidate, name)
                if isinstance(value, str) and (
                    value.startswith(_CONCEPT_PREFIX)
                    or value.startswith("orgd-")
                    or value.startswith("orga-")
                ):
                    raise OrganizationAnalysisError("organization_layer_leak")
