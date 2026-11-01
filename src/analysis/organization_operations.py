"""Detached organization operation rows harvested from exported owner ledgers.

Rows are post-run research evidence. An operation row records what one owner
believed about legitimate control, storage, records, admission, departure, role
assignment, procedure acts, or internal commitments. It is never objective
custody, never a permission, and never a command source.

This module is read-only and detached: it never imports ``agents.cognition``,
world state, persistence, API, infrastructure, or observer packages, and nothing
here feeds cognition, prompts, admission, or world state. Owner-local ``orgc-``,
``orgd-``, and ``orga-`` ids stay inside detached analysis and are never
published by the snapshot layer.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from analysis.numerical import quantize_float
from analysis.organization_contract import (
    OrganizationAnalysisError,
    require_organization_id,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

if TYPE_CHECKING:
    from analysis.organization_detection import OrganizationCandidate
    from analysis.organization_identity import OrganizationIdentityAssignment

__all__ = [
    "DISPUTED_OPERATION_STANCE",
    "OrganizationActionRow",
    "OrganizationAdmissionRow",
    "OrganizationAssignmentRow",
    "OrganizationCandidateOperations",
    "OrganizationCommitmentOperationRow",
    "OrganizationControlRow",
    "OrganizationDecisionRow",
    "OrganizationDepartureRow",
    "OrganizationOperationHarvestRows",
    "OrganizationOperationOwnerRow",
    "OrganizationOperationSummary",
    "OrganizationProcedureActionRow",
    "harvest_organization_operation_rows",
    "harvest_organization_operation_snapshot",
    "operation_action_ticks",
    "operation_concept_counts",
    "organization_operation_sources",
    "summarize_organization_operations",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_operations")

_ROW_ERROR: Final[str] = "organization_operation_row_invalid"
DISPUTED_OPERATION_STANCE: Final[str] = "disputed"

_RECORD_FAMILIES: Final[tuple[str, ...]] = (
    "controls",
    "admissions",
    "departures",
    "assignments",
    "procedures",
    "commitments",
    "decisions",
    "actions",
)

_STANCE_FAMILIES: Final[tuple[str, ...]] = (
    "controls",
    "admissions",
    "departures",
    "assignments",
    "procedures",
    "commitments",
)


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise OrganizationAnalysisError(_ROW_ERROR)
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise OrganizationAnalysisError(_ROW_ERROR) from exc


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        return value or None
    token = getattr(value, "value", None)
    if isinstance(token, str):
        return token or None
    return None


def _optional_tick(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        return None
    return value


def _optional_count(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is not int or value < 0:
        return None
    return value


def _span_ok(first_tick: int | None, last_tick: int | None) -> None:
    if first_tick is not None and last_tick is not None and last_tick < first_tick:
        raise OrganizationAnalysisError(_ROW_ERROR)


def _span(first_tick: int | None, last_tick: int | None) -> int | None:
    if first_tick is None or last_tick is None:
        return None
    return last_tick - first_tick


@dataclass(frozen=True, slots=True)
class OrganizationOperationOwnerRow:
    """One owner's operation ledger header counts; no anchors or labels."""

    owner_id: str
    concept_count: int
    notices: tuple[str, ...]
    policy_version: str
    control_count: int = 0
    admission_count: int = 0
    departure_count: int = 0
    assignment_count: int = 0
    procedure_count: int = 0
    commitment_count: int = 0
    decision_count: int = 0
    action_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _required_text("owner_id", self.owner_id))
        object.__setattr__(
            self,
            "concept_count",
            require_exact_nonneg_int("concept_count", self.concept_count),
        )
        object.__setattr__(
            self,
            "policy_version",
            _required_text("policy_version", self.policy_version),
        )
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))
        for name in (
            "control_count",
            "admission_count",
            "departure_count",
            "assignment_count",
            "procedure_count",
            "commitment_count",
            "decision_count",
            "action_count",
        ):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )

    @property
    def record_count(self) -> int:
        return sum(
            (
                self.control_count,
                self.admission_count,
                self.departure_count,
                self.assignment_count,
                self.procedure_count,
                self.commitment_count,
                self.decision_count,
                self.action_count,
            )
        )


@dataclass(frozen=True, slots=True)
class OrganizationControlRow:
    """One believed legitimate control relation; never objective custody."""

    organization_id: str
    domain: str | None = None
    anchor_kind: str | None = None
    anchor_id: str | None = None
    stance: str | None = None
    authority_basis: str | None = None
    legitimacy_doctrine: str | None = None
    decision_ref: str | None = None
    role_ref: str | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationAdmissionRow:
    """One believed admission claim; never a permission or world rule."""

    organization_id: str
    member_id: str | None = None
    stance: str | None = None
    authority_basis: str | None = None
    role_ref: str | None = None
    decision_ref: str | None = None
    temporal_scope: str | None = None
    expires_tick: int | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationDepartureRow:
    """One believed departure claim; departure is not expulsion law."""

    organization_id: str
    member_id: str | None = None
    stance: str | None = None
    authority_basis: str | None = None
    decision_ref: str | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationAssignmentRow:
    """One believed role assignment; never an authority grant."""

    organization_id: str
    office_id: str | None = None
    occupant_id: str | None = None
    stance: str | None = None
    authority_basis: str | None = None
    decision_ref: str | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationProcedureActionRow:
    """One believed recognized procedure act and its observed outcome."""

    organization_id: str
    procedure_ref: str | None = None
    command_kind: str | None = None
    actor_id: str | None = None
    outcome: str | None = None
    authority_basis: str | None = None
    decision_ref: str | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationCommitmentOperationRow:
    """One believed internal commitment state; never enforced debt."""

    organization_id: str
    commitment_id: str | None = None
    role: str | None = None
    counterpart_id: str | None = None
    stance: str | None = None
    authority_basis: str | None = None
    decision_ref: str | None = None
    due_tick: int | None = None
    first_tick: int | None = None
    last_tick: int | None = None
    owner_support_count: int | None = None
    contest_count: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )
        _span_ok(self.first_tick, self.last_tick)

    @property
    def span(self) -> int | None:
        return _span(self.first_tick, self.last_tick)


@dataclass(frozen=True, slots=True)
class OrganizationDecisionRow:
    """One owner-local believed decision with provenance."""

    organization_id: str
    decision_id: str | None = None
    domain: str | None = None
    act: str | None = None
    actor_id: str | None = None
    target_id: str | None = None
    anchor_kind: str | None = None
    anchor_id: str | None = None
    authority_basis: str | None = None
    stance: str | None = None
    support_count: int | None = None
    oppose_count: int | None = None
    provenance_code: str | None = None
    tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )


@dataclass(frozen=True, slots=True)
class OrganizationActionRow:
    """One owner-local believed action effect with provenance."""

    organization_id: str
    action_id: str | None = None
    decision_id: str | None = None
    domain: str | None = None
    act: str | None = None
    actor_id: str | None = None
    command_kind: str | None = None
    anchor_kind: str | None = None
    anchor_id: str | None = None
    outcome: str | None = None
    provenance_code: str | None = None
    tick: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            _required_text("organization_id", self.organization_id),
        )


@dataclass(frozen=True, slots=True)
class OrganizationOperationHarvestRows:
    """All detached operation rows for one owner."""

    owner: OrganizationOperationOwnerRow
    controls: tuple[OrganizationControlRow, ...] = ()
    admissions: tuple[OrganizationAdmissionRow, ...] = ()
    departures: tuple[OrganizationDepartureRow, ...] = ()
    assignments: tuple[OrganizationAssignmentRow, ...] = ()
    procedures: tuple[OrganizationProcedureActionRow, ...] = ()
    commitments: tuple[OrganizationCommitmentOperationRow, ...] = ()
    decisions: tuple[OrganizationDecisionRow, ...] = ()
    actions: tuple[OrganizationActionRow, ...] = ()
    concept_ticks: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner) is not OrganizationOperationOwnerRow:
            raise OrganizationAnalysisError(_ROW_ERROR)
        for name in _RECORD_FAMILIES:
            values = getattr(self, name)
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise OrganizationAnalysisError(_ROW_ERROR)
            object.__setattr__(self, name, tuple(values))
        ticks = tuple(self.concept_ticks)
        for organization_id, tick in ticks:
            _required_text("organization_id", organization_id)
            require_exact_nonneg_int("concept_tick", tick)
        object.__setattr__(self, "concept_ticks", tuple(sorted(ticks)))

    @property
    def has_operations(self) -> bool:
        return any(getattr(self, name) for name in _RECORD_FAMILIES)

    @property
    def has_contest(self) -> bool:
        return any(
            record.stance == DISPUTED_OPERATION_STANCE
            or (record.contest_count or 0) > 0
            for name in _STANCE_FAMILIES
            for record in getattr(self, name)
        )


def _owner_token(value: object) -> str:
    token = getattr(value, "value", value)
    if not isinstance(token, str) or not token:
        raise OrganizationAnalysisError(_ROW_ERROR)
    return token


def _records(source: object, name: str) -> Sequence[object]:
    values = getattr(source, name, ())
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise OrganizationAnalysisError(_ROW_ERROR)
    return values


def _ledger_rows(ledger: object) -> OrganizationOperationHarvestRows:
    owner_id = _required_text(
        "owner_id", _owner_token(getattr(ledger, "owner_id", None))
    )
    policy_version = getattr(ledger, "policy_version", None)
    if not isinstance(policy_version, str) or not policy_version:
        raise OrganizationAnalysisError(_ROW_ERROR)
    concepts = _records(ledger, "concepts")

    control_rows: list[OrganizationControlRow] = []
    admission_rows: list[OrganizationAdmissionRow] = []
    departure_rows: list[OrganizationDepartureRow] = []
    assignment_rows: list[OrganizationAssignmentRow] = []
    procedure_rows: list[OrganizationProcedureActionRow] = []
    commitment_rows: list[OrganizationCommitmentOperationRow] = []
    decision_rows: list[OrganizationDecisionRow] = []
    action_rows: list[OrganizationActionRow] = []
    seen: set[str] = set()
    concept_ticks: list[tuple[str, int]] = []

    for concept in concepts:
        concept_owner = getattr(concept, "owner_id", None)
        if concept_owner is not None and _owner_token(concept_owner) != owner_id:
            raise OrganizationAnalysisError(_ROW_ERROR)
        organization_id = _required_text(
            "organization_id", getattr(concept, "organization_id", None)
        )
        if organization_id in seen:
            raise OrganizationAnalysisError(_ROW_ERROR)
        seen.add(organization_id)
        concept_last_tick = _optional_tick(getattr(concept, "last_tick", None))
        if concept_last_tick is not None:
            concept_ticks.append((organization_id, concept_last_tick))

        for record in _records(concept, "controls"):
            control_rows.append(
                OrganizationControlRow(
                    organization_id=organization_id,
                    domain=_optional_text(getattr(record, "domain", None)),
                    anchor_kind=_optional_text(getattr(record, "anchor_kind", None)),
                    anchor_id=_optional_text(getattr(record, "anchor_id", None)),
                    stance=_optional_text(getattr(record, "stance", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    legitimacy_doctrine=_optional_text(
                        getattr(record, "legitimacy_doctrine", None)
                    ),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    role_ref=_optional_text(getattr(record, "role_ref", None)),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "admissions"):
            admission_rows.append(
                OrganizationAdmissionRow(
                    organization_id=organization_id,
                    member_id=_optional_text(getattr(record, "member_id", None)),
                    stance=_optional_text(getattr(record, "stance", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    role_ref=_optional_text(getattr(record, "role_ref", None)),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    temporal_scope=_optional_text(
                        getattr(record, "temporal_scope", None)
                    ),
                    expires_tick=_optional_tick(getattr(record, "expires_tick", None)),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "departures"):
            departure_rows.append(
                OrganizationDepartureRow(
                    organization_id=organization_id,
                    member_id=_optional_text(getattr(record, "member_id", None)),
                    stance=_optional_text(getattr(record, "stance", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "assignments"):
            assignment_rows.append(
                OrganizationAssignmentRow(
                    organization_id=organization_id,
                    office_id=_optional_text(getattr(record, "office_id", None)),
                    occupant_id=_optional_text(getattr(record, "occupant_id", None)),
                    stance=_optional_text(getattr(record, "stance", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "procedures"):
            procedure_rows.append(
                OrganizationProcedureActionRow(
                    organization_id=organization_id,
                    procedure_ref=_optional_text(
                        getattr(record, "procedure_ref", None)
                    ),
                    command_kind=_optional_text(getattr(record, "command_kind", None)),
                    actor_id=_optional_text(getattr(record, "actor_id", None)),
                    outcome=_optional_text(getattr(record, "outcome", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "commitments"):
            commitment_rows.append(
                OrganizationCommitmentOperationRow(
                    organization_id=organization_id,
                    commitment_id=_optional_text(
                        getattr(record, "commitment_id", None)
                    ),
                    role=_optional_text(getattr(record, "role", None)),
                    counterpart_id=_optional_text(
                        getattr(record, "counterpart_id", None)
                    ),
                    stance=_optional_text(getattr(record, "stance", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    decision_ref=_optional_text(
                        getattr(record, "decision_ref", None)
                    ),
                    due_tick=_optional_tick(getattr(record, "due_tick", None)),
                    first_tick=_optional_tick(getattr(record, "first_tick", None)),
                    last_tick=_optional_tick(getattr(record, "last_tick", None)),
                    owner_support_count=_optional_count(
                        getattr(record, "owner_support_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                )
            )
        for record in _records(concept, "decisions"):
            decision_rows.append(
                OrganizationDecisionRow(
                    organization_id=organization_id,
                    decision_id=_optional_text(getattr(record, "decision_id", None)),
                    domain=_optional_text(getattr(record, "domain", None)),
                    act=_optional_text(getattr(record, "act", None)),
                    actor_id=_optional_text(getattr(record, "actor_id", None)),
                    target_id=_optional_text(getattr(record, "target_id", None)),
                    anchor_kind=_optional_text(getattr(record, "anchor_kind", None)),
                    anchor_id=_optional_text(getattr(record, "anchor_id", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    stance=_optional_text(getattr(record, "stance", None)),
                    support_count=_optional_count(
                        getattr(record, "support_count", None)
                    ),
                    oppose_count=_optional_count(
                        getattr(record, "oppose_count", None)
                    ),
                    provenance_code=_optional_text(
                        getattr(record, "provenance_code", None)
                    ),
                    tick=_optional_tick(getattr(record, "tick", None)),
                )
            )
        for record in _records(concept, "actions"):
            action_rows.append(
                OrganizationActionRow(
                    organization_id=organization_id,
                    action_id=_optional_text(getattr(record, "action_id", None)),
                    decision_id=_optional_text(getattr(record, "decision_id", None)),
                    domain=_optional_text(getattr(record, "domain", None)),
                    act=_optional_text(getattr(record, "act", None)),
                    actor_id=_optional_text(getattr(record, "actor_id", None)),
                    command_kind=_optional_text(getattr(record, "command_kind", None)),
                    anchor_kind=_optional_text(getattr(record, "anchor_kind", None)),
                    anchor_id=_optional_text(getattr(record, "anchor_id", None)),
                    outcome=_optional_text(getattr(record, "outcome", None)),
                    provenance_code=_optional_text(
                        getattr(record, "provenance_code", None)
                    ),
                    tick=_optional_tick(getattr(record, "tick", None)),
                )
            )

    owner_row = OrganizationOperationOwnerRow(
        owner_id=owner_id,
        concept_count=len(seen),
        notices=tuple(sorted(getattr(ledger, "notices", ()))),
        policy_version=policy_version,
        control_count=len(control_rows),
        admission_count=len(admission_rows),
        departure_count=len(departure_rows),
        assignment_count=len(assignment_rows),
        procedure_count=len(procedure_rows),
        commitment_count=len(commitment_rows),
        decision_count=len(decision_rows),
        action_count=len(action_rows),
    )
    return OrganizationOperationHarvestRows(
        owner=owner_row,
        controls=tuple(
            sorted(
                control_rows,
                key=lambda row: (
                    row.organization_id,
                    row.domain or "",
                    row.anchor_kind or "",
                    row.anchor_id or "",
                    row.first_tick if row.first_tick is not None else -1,
                ),
            )
        ),
        admissions=tuple(
            sorted(
                admission_rows,
                key=lambda row: (
                    row.organization_id,
                    row.member_id or "",
                    row.first_tick if row.first_tick is not None else -1,
                    row.stance or "",
                ),
            )
        ),
        departures=tuple(
            sorted(
                departure_rows,
                key=lambda row: (
                    row.organization_id,
                    row.member_id or "",
                    row.first_tick if row.first_tick is not None else -1,
                ),
            )
        ),
        assignments=tuple(
            sorted(
                assignment_rows,
                key=lambda row: (
                    row.organization_id,
                    row.office_id or "",
                    row.occupant_id or "",
                    row.first_tick if row.first_tick is not None else -1,
                ),
            )
        ),
        procedures=tuple(
            sorted(
                procedure_rows,
                key=lambda row: (
                    row.organization_id,
                    row.procedure_ref or "",
                    row.actor_id or "",
                    row.first_tick if row.first_tick is not None else -1,
                ),
            )
        ),
        commitments=tuple(
            sorted(
                commitment_rows,
                key=lambda row: (
                    row.organization_id,
                    row.commitment_id or "",
                    row.role or "",
                    row.first_tick if row.first_tick is not None else -1,
                ),
            )
        ),
        concept_ticks=tuple(concept_ticks),
        decisions=tuple(
            sorted(
                decision_rows,
                key=lambda row: (
                    row.organization_id,
                    row.tick if row.tick is not None else -1,
                    row.decision_id or "",
                ),
            )
        ),
        actions=tuple(
            sorted(
                action_rows,
                key=lambda row: (
                    row.organization_id,
                    row.tick if row.tick is not None else -1,
                    row.action_id or "",
                ),
            )
        ),
    )


def harvest_organization_operation_rows(
    ledgers: Sequence[object] | None,
) -> tuple[OrganizationOperationHarvestRows, ...]:
    """Harvest exported owner operation ledgers into detached rows."""

    if ledgers is None:
        _LOG.debug("organization_operation_harvest mode=empty")
        return ()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise OrganizationAnalysisError(_ROW_ERROR)
    items = tuple(ledgers)
    if items and all(
        isinstance(ledger, OrganizationOperationHarvestRows) for ledger in items
    ):
        rows = tuple(
            ledger
            for ledger in items
            if isinstance(ledger, OrganizationOperationHarvestRows)
        )
        owners = [row.owner.owner_id for row in rows]
        if len(set(owners)) != len(owners):
            raise OrganizationAnalysisError(_ROW_ERROR)
        ordered_rows = tuple(sorted(rows, key=lambda row: row.owner.owner_id))
        _LOG.info(
            "organization_operation_harvest owners=%s concepts=%s decisions=%s "
            "actions=%s",
            len(ordered_rows),
            sum(row.owner.concept_count for row in ordered_rows),
            sum(len(row.decisions) for row in ordered_rows),
            sum(len(row.actions) for row in ordered_rows),
        )
        return ordered_rows
    rows = tuple(_ledger_rows(ledger) for ledger in items)
    owners = [row.owner.owner_id for row in rows]
    if len(set(owners)) != len(owners):
        raise OrganizationAnalysisError(_ROW_ERROR)
    ordered = tuple(sorted(rows, key=lambda row: row.owner.owner_id))
    _LOG.info(
        "organization_operation_harvest owners=%s concepts=%s decisions=%s actions=%s",
        len(ordered),
        sum(row.owner.concept_count for row in ordered),
        sum(len(row.decisions) for row in ordered),
        sum(len(row.actions) for row in ordered),
    )
    return ordered


def harvest_organization_operation_snapshot(
    runner_result: object,
) -> tuple[OrganizationOperationHarvestRows, ...]:
    """Read operation ledgers from a completed runner result defensively."""

    ledgers = getattr(runner_result, "organization_operation_ledgers", ())
    if not ledgers:
        return ()
    return harvest_organization_operation_rows(ledgers)

CONTESTED_OPERATION_STANCE: Final[str] = "contested"
UNKNOWN_PROVENANCE_CODE: Final[str] = "unknown_authority"
ORPHANED_PROVENANCE_CODE: Final[str] = "orphaned"
OPERATION_SUMMARY_ERROR: Final[str] = "organization_operation_summary_invalid"
UNKNOWN_TOKEN: Final[str] = "unknown"

OPERATION_DOMAINS: Final[tuple[str, ...]] = (
    "resource_control",
    "storage",
    "record_keeping",
    "membership_admission",
    "membership_departure",
    "role_assignment",
    "procedure_action",
    "internal_commitment",
)

_FAMILY_DOMAINS: Final[dict[str, str]] = {
    "admissions": "membership_admission",
    "departures": "membership_departure",
    "assignments": "role_assignment",
    "procedures": "procedure_action",
    "commitments": "internal_commitment",
}


@dataclass(slots=True)
class _CandidateAccumulator:
    organization_id: str
    control_counts: dict[str, int] = field(default_factory=dict)
    admission_count: int = 0
    departure_count: int = 0
    assignment_count: int = 0
    procedure_action_count: int = 0
    commitment_count: int = 0
    decision_count: int = 0
    action_count: int = 0
    contested_domains: set[str] = field(default_factory=set)
    authority_counts: dict[str, int] = field(default_factory=dict)
    provenance_counts: dict[str, int] = field(default_factory=dict)
    orphaned_count: int = 0
    support_values: list[float] = field(default_factory=list)
    domains: set[str] = field(default_factory=set)


def _bump(counts: dict[str, int], key: str | None) -> None:
    token = key or UNKNOWN_TOKEN
    counts[token] = counts.get(token, 0) + 1


def _pairs(counts: dict[str, int]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counts.items()))


def _is_contested(
    stance: str | None,
    contest_count: int | None = None,
    *,
    extra: bool = False,
) -> bool:
    return (
        stance in (DISPUTED_OPERATION_STANCE, CONTESTED_OPERATION_STANCE)
        or (contest_count or 0) > 0
        or extra
    )


def _record_contested(family: str, record: object) -> bool:
    if family == "actions":
        return False
    if family == "decisions":
        return _is_contested(
            getattr(record, "stance", None),
            extra=(getattr(record, "oppose_count", None) or 0) > 0,
        )
    return _is_contested(
        getattr(record, "stance", None),
        getattr(record, "contest_count", None),
    )


def _record_domain(family: str, record: object) -> str | None:
    if family == "controls":
        domain = getattr(record, "domain", None)
        if isinstance(domain, str) and domain in OPERATION_DOMAINS:
            return domain
        return None
    if family == "decisions":
        domain = getattr(record, "domain", None)
        if isinstance(domain, str) and domain in OPERATION_DOMAINS:
            return domain
        return None
    return _FAMILY_DOMAINS.get(family)


def _record_last_tick(family: str, record: object) -> int | None:
    if family in ("decisions", "actions"):
        return getattr(record, "tick", None)
    return getattr(record, "last_tick", None)


def _group_records(
    rows: Sequence[OrganizationOperationHarvestRows],
) -> dict[tuple[str, str], list[tuple[str, object]]]:
    groups: dict[tuple[str, str], list[tuple[str, object]]] = {}
    for owner in rows:
        owner_id = owner.owner.owner_id
        for family in _RECORD_FAMILIES:
            for record in getattr(owner, family):
                groups.setdefault((owner_id, record.organization_id), []).append(
                    (family, record)
                )
    return groups


def _operation_members(entries: Sequence[tuple[str, object]]) -> set[str]:
    members: set[str] = set()
    for family, record in entries:
        if family in ("admissions", "departures"):
            member_id = getattr(record, "member_id", None)
            if isinstance(member_id, str) and member_id:
                members.add(member_id)
    return members


def _operation_anchors(entries: Sequence[tuple[str, object]]) -> set[str]:
    anchors: set[str] = set()
    for family, record in entries:
        if family not in ("controls", "decisions", "actions"):
            continue
        anchor_kind = getattr(record, "anchor_kind", None)
        anchor_id = getattr(record, "anchor_id", None)
        if (
            isinstance(anchor_kind, str)
            and anchor_kind
            and isinstance(anchor_id, str)
            and anchor_id
        ):
            anchors.add(f"{anchor_kind}:{anchor_id}")
    return anchors


def _match_candidate(
    candidates: Sequence[OrganizationCandidate],
    member_ids: set[str],
    anchors: set[str],
) -> OrganizationCandidate | None:
    best: OrganizationCandidate | None = None
    best_score = 0
    for candidate in candidates:
        score = len(set(candidate.member_ids) & member_ids) + len(
            set(candidate.anchor_signature) & anchors
        )
        if score <= 0:
            continue
        if best is None or score > best_score:
            best = candidate
            best_score = score
        elif score == best_score and candidate.candidate_key < best.candidate_key:
            best = candidate
    return best


def _candidate_id(
    assignment: OrganizationIdentityAssignment, candidate_key: str
) -> str:
    for key, organization_id in assignment.candidate_ids:
        if key == candidate_key:
            return organization_id
    raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)


@dataclass(frozen=True, slots=True)
class OrganizationCandidateOperations:
    """Owner operation evidence attached to one analytical ``org-`` candidate."""

    organization_id: str
    control_counts: tuple[tuple[str, int], ...] = ()
    admission_count: int = 0
    departure_count: int = 0
    assignment_count: int = 0
    procedure_action_count: int = 0
    commitment_count: int = 0
    decision_count: int = 0
    action_count: int = 0
    contested_domains: tuple[str, ...] = ()
    authority_counts: tuple[tuple[str, int], ...] = ()
    provenance_counts: tuple[tuple[str, int], ...] = ()
    orphaned_count: int = 0
    mean_owner_support: float | None = None
    coverage_ratio: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "organization_id",
            require_organization_id(self.organization_id),
        )
        object.__setattr__(self, "control_counts", _pairs(dict(self.control_counts)))
        for name in (
            "admission_count",
            "departure_count",
            "assignment_count",
            "procedure_action_count",
            "commitment_count",
            "decision_count",
            "action_count",
            "orphaned_count",
        ):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        object.__setattr__(
            self, "contested_domains", tuple(sorted(self.contested_domains))
        )
        object.__setattr__(
            self, "authority_counts", _pairs(dict(self.authority_counts))
        )
        object.__setattr__(
            self, "provenance_counts", _pairs(dict(self.provenance_counts))
        )

    @property
    def operation_count(self) -> int:
        return (
            sum(count for _, count in self.control_counts)
            + self.admission_count
            + self.departure_count
            + self.assignment_count
            + self.procedure_action_count
            + self.commitment_count
            + self.decision_count
            + self.action_count
        )

    @property
    def has_contest(self) -> bool:
        return bool(self.contested_domains)


@dataclass(frozen=True, slots=True)
class OrganizationOperationSummary:
    """Detached operation summary keyed by analytical ``org-`` ids only."""

    candidates: tuple[OrganizationCandidateOperations, ...]
    as_of_tick: int
    control_counts: tuple[tuple[str, int], ...] = ()
    admission_count: int = 0
    departure_count: int = 0
    assignment_count: int = 0
    procedure_action_count: int = 0
    commitment_count: int = 0
    decision_count: int = 0
    action_count: int = 0
    contested_domain_counts: tuple[tuple[str, int], ...] = ()
    contested_operation_count: int = 0
    authority_contest_count: int = 0
    authority_counts: tuple[tuple[str, int], ...] = ()
    provenance_counts: tuple[tuple[str, int], ...] = ()
    provenance_known_count: int = 0
    orphaned_count: int = 0
    mean_owner_support: float | None = None
    coverage_ratio: float | None = None
    history_truncated: bool = False

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.candidates, key=lambda item: item.organization_id))
        seen: set[str] = set()
        for candidate in ordered:
            if type(candidate) is not OrganizationCandidateOperations:
                raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)
            if candidate.organization_id in seen:
                raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)
            seen.add(candidate.organization_id)
        object.__setattr__(self, "candidates", ordered)
        object.__setattr__(
            self, "as_of_tick", require_exact_nonneg_int("as_of_tick", self.as_of_tick)
        )
        object.__setattr__(self, "control_counts", _pairs(dict(self.control_counts)))
        object.__setattr__(
            self, "contested_domain_counts", _pairs(dict(self.contested_domain_counts))
        )
        object.__setattr__(
            self, "authority_counts", _pairs(dict(self.authority_counts))
        )
        object.__setattr__(
            self, "provenance_counts", _pairs(dict(self.provenance_counts))
        )
        for name in (
            "admission_count",
            "departure_count",
            "assignment_count",
            "procedure_action_count",
            "commitment_count",
            "decision_count",
            "action_count",
            "contested_operation_count",
            "authority_contest_count",
            "provenance_known_count",
            "orphaned_count",
        ):
            object.__setattr__(
                self, name, require_exact_nonneg_int(name, getattr(self, name))
            )
        if type(self.history_truncated) is not bool:
            raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def candidates_with_operations(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.operation_count > 0)

    @property
    def operation_count(self) -> int:
        return (
            sum(count for _, count in self.control_counts)
            + self.admission_count
            + self.departure_count
            + self.assignment_count
            + self.procedure_action_count
            + self.commitment_count
            + self.decision_count
            + self.action_count
        )

    @property
    def has_operations(self) -> bool:
        return self.operation_count > 0

    @property
    def contested_domains(self) -> tuple[str, ...]:
        return tuple(domain for domain, _ in self.contested_domain_counts)

    def control_count(self, domain: str) -> int:
        for key, value in self.control_counts:
            if key == domain:
                return value
        return 0

    def authority_count(self, basis: str) -> int:
        for key, value in self.authority_counts:
            if key == basis:
                return value
        return 0

    def contested_count(self, domain: str) -> int:
        for key, value in self.contested_domain_counts:
            if key == domain:
                return value
        return 0

    def provenance_count(self, code: str) -> int:
        for key, value in self.provenance_counts:
            if key == code:
                return value
        return 0


@dataclass(frozen=True, slots=True)
class _Totals:
    control_counts: tuple[tuple[str, int], ...] = ()
    admission_count: int = 0
    departure_count: int = 0
    assignment_count: int = 0
    procedure_action_count: int = 0
    commitment_count: int = 0
    decision_count: int = 0
    action_count: int = 0
    candidates_with_operations: int = 0


def operation_concept_counts(
    rows: Sequence[OrganizationOperationHarvestRows],
) -> tuple[tuple[str, str, int, int], ...]:
    """Return ``(owner_id, organization_id, count, contested)`` per concept."""

    counts: dict[tuple[str, str], list[int]] = {}
    for owner in rows:
        owner_id = owner.owner.owner_id
        for family in _RECORD_FAMILIES:
            for record in getattr(owner, family):
                key = (owner_id, record.organization_id)
                entry = counts.setdefault(key, [0, 0])
                entry[0] += 1
                if _record_contested(family, record):
                    entry[1] += 1
    return tuple(
        (owner_id, organization_id, entry[0], entry[1])
        for (owner_id, organization_id), entry in sorted(counts.items())
    )


def operation_action_ticks(
    rows: Sequence[OrganizationOperationHarvestRows],
) -> tuple[int, ...]:
    """Return observed action ticks in deterministic order; never action ids."""

    ticks: list[int] = []
    for owner in rows:
        for record in owner.actions:
            tick = getattr(record, "tick", None)
            if tick is not None:
                ticks.append(tick)
    return tuple(sorted(ticks))


def _totals(
    candidates: tuple[OrganizationCandidateOperations, ...],
) -> _Totals:
    control_counts: dict[str, int] = {}
    admission_count = 0
    departure_count = 0
    assignment_count = 0
    procedure_action_count = 0
    commitment_count = 0
    decision_count = 0
    action_count = 0
    with_operations = 0
    for candidate in candidates:
        for key, value in candidate.control_counts:
            control_counts[key] = control_counts.get(key, 0) + value
        admission_count += candidate.admission_count
        departure_count += candidate.departure_count
        assignment_count += candidate.assignment_count
        procedure_action_count += candidate.procedure_action_count
        commitment_count += candidate.commitment_count
        decision_count += candidate.decision_count
        action_count += candidate.action_count
        if candidate.operation_count > 0:
            with_operations += 1
    return _Totals(
        control_counts=_pairs(control_counts),
        admission_count=admission_count,
        departure_count=departure_count,
        assignment_count=assignment_count,
        procedure_action_count=procedure_action_count,
        commitment_count=commitment_count,
        decision_count=decision_count,
        action_count=action_count,
        candidates_with_operations=with_operations,
    )


def _matched_groups(
    rows: Sequence[OrganizationOperationHarvestRows],
    assignment: OrganizationIdentityAssignment,
    *,
    include_stale: bool,
) -> list[tuple[list[tuple[str, object]], str | None]]:
    """Match owner operation groups to candidates deterministically."""

    concept_ticks: dict[tuple[str, str], int] = {}
    for owner in rows:
        for organization_id, tick in owner.concept_ticks:
            concept_ticks[(owner.owner.owner_id, organization_id)] = tick
    matches: list[tuple[list[tuple[str, object]], str | None]] = []
    for (owner_id, organization_id), entries in sorted(
        _group_records(rows).items()
    ):
        last_tick = concept_ticks.get((owner_id, organization_id))
        if last_tick is None:
            last_tick = max(
                (
                    tick
                    for family, record in entries
                    for tick in (_record_last_tick(family, record),)
                    if tick is not None
                ),
                default=None,
            )
        if include_stale:
            window = assignment.windows[-1]
            for candidate_window in assignment.windows:
                if last_tick is None or candidate_window.start_tick <= last_tick:
                    window = candidate_window
        else:
            window = assignment.windows[-1]
            if last_tick is not None and last_tick < window.start_tick:
                continue
        owner_candidates = tuple(
            candidate
            for candidate in sorted(
                window.candidates, key=lambda item: item.candidate_key
            )
            if owner_id in candidate.owner_ids
        )
        matched = _match_candidate(
            owner_candidates,
            _operation_members(entries),
            _operation_anchors(entries),
        )
        matches.append(
            (entries, None if matched is None else matched.candidate_key)
        )
    return matches


def summarize_organization_operations(
    rows: Sequence[OrganizationOperationHarvestRows] | None,
    assignment: OrganizationIdentityAssignment | None,
) -> OrganizationOperationSummary | None:
    """Join owner operation records to final-window analytical candidates."""

    from analysis.organization_identity import OrganizationIdentityAssignment

    if rows is None or not rows:
        return None
    if assignment is None:
        return None
    if type(assignment) is not OrganizationIdentityAssignment:
        raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)
    if not assignment.windows:
        return None

    final_window = assignment.windows[-1]
    candidates = tuple(
        sorted(final_window.candidates, key=lambda item: item.candidate_key)
    )
    candidate_ids = {
        candidate.candidate_key: _candidate_id(assignment, candidate.candidate_key)
        for candidate in candidates
    }
    accumulators: dict[str, _CandidateAccumulator] = {
        organization_id: _CandidateAccumulator(organization_id=organization_id)
        for organization_id in sorted(set(candidate_ids.values()))
    }
    authority_counts: dict[str, int] = {}
    provenance_counts: dict[str, int] = {}
    contested_domains: dict[str, int] = {}
    support_values: list[float] = []
    contested_operations = 0
    authority_contest = 0
    provenance_known = 0
    orphaned = 0

    for entries, matched_key in _matched_groups(
        rows, assignment, include_stale=False
    ):
        if matched_key is None:
            orphaned += 1
            continue
        accumulator = accumulators[candidate_ids[matched_key]]
        for family, record in entries:
            domain = _record_domain(family, record)
            if domain is not None:
                accumulator.domains.add(domain)
            if _record_contested(family, record):
                contested_operations += 1
                if domain is not None:
                    contested_domains[domain] = contested_domains.get(domain, 0) + 1
                    accumulator.contested_domains.add(domain)
            if family == "controls":
                key = domain or UNKNOWN_TOKEN
                accumulator.control_counts[key] = (
                    accumulator.control_counts.get(key, 0) + 1
                )
            elif family == "admissions":
                accumulator.admission_count += 1
            elif family == "departures":
                accumulator.departure_count += 1
            elif family == "assignments":
                accumulator.assignment_count += 1
            elif family == "procedures":
                accumulator.procedure_action_count += 1
            elif family == "commitments":
                accumulator.commitment_count += 1
            elif family == "decisions":
                accumulator.decision_count += 1
            elif family == "actions":
                accumulator.action_count += 1
            if family != "actions":
                authority_basis = getattr(record, "authority_basis", None)
                _bump(authority_counts, authority_basis)
                _bump(accumulator.authority_counts, authority_basis)
            if family == "decisions" and (
                getattr(record, "authority_basis", None) in (None, UNKNOWN_TOKEN)
                or getattr(record, "stance", None)
                in (DISPUTED_OPERATION_STANCE, CONTESTED_OPERATION_STANCE)
            ):
                authority_contest += 1
            if family in ("decisions", "actions"):
                provenance_code = getattr(record, "provenance_code", None)
                _bump(provenance_counts, provenance_code)
                _bump(accumulator.provenance_counts, provenance_code)
                if provenance_code is not None and (
                    provenance_code != UNKNOWN_PROVENANCE_CODE
                ):
                    provenance_known += 1
                if provenance_code == ORPHANED_PROVENANCE_CODE:
                    accumulator.orphaned_count += 1
            support = getattr(record, "owner_support_count", None)
            if support is not None:
                support_values.append(float(support))
                accumulator.support_values.append(float(support))

    summaries = tuple(
        OrganizationCandidateOperations(
            organization_id=accumulator.organization_id,
            control_counts=_pairs(accumulator.control_counts),
            admission_count=accumulator.admission_count,
            departure_count=accumulator.departure_count,
            assignment_count=accumulator.assignment_count,
            procedure_action_count=accumulator.procedure_action_count,
            commitment_count=accumulator.commitment_count,
            decision_count=accumulator.decision_count,
            action_count=accumulator.action_count,
            contested_domains=tuple(sorted(accumulator.contested_domains)),
            authority_counts=_pairs(accumulator.authority_counts),
            provenance_counts=_pairs(accumulator.provenance_counts),
            orphaned_count=accumulator.orphaned_count,
            mean_owner_support=(
                quantize_float(
                    sum(accumulator.support_values)
                    / len(accumulator.support_values)
                )
                if accumulator.support_values
                else None
            ),
            coverage_ratio=(
                quantize_float(len(accumulator.domains) / len(OPERATION_DOMAINS))
                if accumulator.domains
                else None
            ),
        )
        for accumulator in sorted(
            accumulators.values(), key=lambda item: item.organization_id
        )
    )
    totals = _totals(summaries)
    coverage_ratio = (
        quantize_float(totals.candidates_with_operations / len(candidates))
        if candidates
        else None
    )
    summary = OrganizationOperationSummary(
        candidates=summaries,
        as_of_tick=final_window.end_tick,
        control_counts=totals.control_counts,
        admission_count=totals.admission_count,
        departure_count=totals.departure_count,
        assignment_count=totals.assignment_count,
        procedure_action_count=totals.procedure_action_count,
        commitment_count=totals.commitment_count,
        decision_count=totals.decision_count,
        action_count=totals.action_count,
        contested_domain_counts=_pairs(contested_domains),
        contested_operation_count=contested_operations,
        authority_contest_count=authority_contest,
        authority_counts=_pairs(authority_counts),
        provenance_counts=_pairs(provenance_counts),
        provenance_known_count=provenance_known,
        orphaned_count=orphaned,
        mean_owner_support=(
            quantize_float(sum(support_values) / len(support_values))
            if support_values
            else None
        ),
        coverage_ratio=coverage_ratio,
        history_truncated=any(
            "operations_truncated" in row.owner.notices for row in rows
        ),
    )
    _LOG.info(
        "organization_operation_summary candidates=%s contested=%s orphaned=%s",
        summary.candidate_count,
        summary.contested_operation_count,
        summary.orphaned_count,
    )
    return summary


def organization_operation_sources(
    rows: Sequence[OrganizationOperationHarvestRows] | None,
    assignment: OrganizationIdentityAssignment | None,
) -> tuple[tuple[str, tuple[tuple[str, object], ...]], ...]:
    """Return operation source rows grouped by analytical ``org-`` candidate."""

    from analysis.organization_identity import OrganizationIdentityAssignment

    if rows is None or not rows:
        return ()
    if assignment is None:
        return ()
    if type(assignment) is not OrganizationIdentityAssignment:
        raise OrganizationAnalysisError(OPERATION_SUMMARY_ERROR)
    if not assignment.windows:
        return ()
    candidate_ids = dict(assignment.candidate_ids)
    grouped: dict[str, list[tuple[str, object]]] = {}
    for entries, matched_key in _matched_groups(
        rows, assignment, include_stale=True
    ):
        if matched_key is None:
            continue
        organization_id = candidate_ids.get(matched_key)
        if organization_id is None:
            continue
        grouped.setdefault(organization_id, []).extend(entries)
    return tuple(
        (organization_id, tuple(entries))
        for organization_id, entries in sorted(grouped.items())
    )
