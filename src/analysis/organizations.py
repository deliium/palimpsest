"""Detached organization rows harvested from exported owner ledgers.

Rows are post-run research artifacts. Owner-local ``orgc-`` ids stay owner-local;
missing or pruned evidence is absent/partial, never zero. Nothing here feeds
cognition, prompts, admission, or world state, and this module never imports
``agents.cognition``; it reads the documented ledger attributes defensively.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from analysis.organization_contract import (
    OrganizationAnalysisError,
)
from analysis.organization_operations import (
    OrganizationActionRow,
    OrganizationAdmissionRow,
    OrganizationAssignmentRow,
    OrganizationCommitmentOperationRow,
    OrganizationControlRow,
    OrganizationDecisionRow,
    OrganizationDepartureRow,
    OrganizationOperationHarvestRows,
    OrganizationOperationOwnerRow,
    OrganizationProcedureActionRow,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

if TYPE_CHECKING:
    pass

__all__ = [
    "MAX_HARVEST_CONCEPTS",
    "OrganizationActionRow",
    "OrganizationAdmissionRow",
    "OrganizationAnalysisError",
    "OrganizationAssignmentRow",
    "OrganizationCommitmentOperationRow",
    "OrganizationCommitmentRow",
    "OrganizationConceptRow",
    "OrganizationControlRow",
    "OrganizationDecisionRow",
    "OrganizationDepartureRow",
    "OrganizationGoalRow",
    "OrganizationHarvestRows",
    "OrganizationIdentityRow",
    "OrganizationLineageRow",
    "OrganizationMemberRow",
    "OrganizationOperationHarvestRows",
    "OrganizationOperationOwnerRow",
    "OrganizationOwnerRow",
    "OrganizationProcedureActionRow",
    "OrganizationProcedureRow",
    "OrganizationRecordRow",
    "OrganizationResourceRow",
    "OrganizationRoleRow",
    "OrganizationWindowRow",
    "harvest_organization_rows",
    "harvest_organization_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organizations")

MAX_HARVEST_CONCEPTS: Final[int] = 4096


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise OrganizationAnalysisError("organization_row_invalid_order")
    try:
        return require_stable_id(name, value)
    except ValueError as exc:
        raise OrganizationAnalysisError("organization_row_invalid_order") from exc


def _tick(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise OrganizationAnalysisError("organization_row_invalid_tick") from exc


def _sorted_ids(name: str, values: object) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise OrganizationAnalysisError("organization_row_invalid_order")
    items: list[str] = []
    for value in values:
        items.append(_text(name, value))
    if len(set(items)) != len(items):
        raise OrganizationAnalysisError("organization_row_duplicate")
    if items != sorted(items):
        raise OrganizationAnalysisError("organization_row_invalid_order")
    return tuple(items)


def _number(name: str, value: object) -> float:
    if type(value) is not float:
        raise OrganizationAnalysisError("organization_row_invalid_order")
    return value


@dataclass(frozen=True, slots=True)
class OrganizationOwnerRow:
    owner_id: str
    concept_count: int
    lineage_count: int
    notices: tuple[str, ...]
    policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text("owner_id", self.owner_id))
        object.__setattr__(
            self,
            "concept_count",
            require_exact_nonneg_int("concept_count", self.concept_count),
        )
        object.__setattr__(
            self,
            "lineage_count",
            require_exact_nonneg_int("lineage_count", self.lineage_count),
        )
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))
        object.__setattr__(
            self, "policy_version", _text("policy_version", self.policy_version)
        )


@dataclass(frozen=True, slots=True)
class OrganizationConceptRow:
    owner_id: str
    organization_id: str
    creation_tick: int
    status: str
    temporal_scope: str
    strength: float
    member_evidence_count: int
    structural_channel_count: int
    first_tick: int
    last_tick: int
    predecessor_ids: tuple[str, ...]
    structural_signature: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text("owner_id", self.owner_id))
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(
            self, "creation_tick", _tick("creation_tick", self.creation_tick)
        )
        object.__setattr__(self, "status", _text("status", self.status))
        object.__setattr__(
            self, "temporal_scope", _text("temporal_scope", self.temporal_scope)
        )
        object.__setattr__(self, "strength", _number("strength", self.strength))
        object.__setattr__(
            self,
            "member_evidence_count",
            require_exact_nonneg_int(
                "member_evidence_count", self.member_evidence_count
            ),
        )
        object.__setattr__(
            self,
            "structural_channel_count",
            require_exact_nonneg_int(
                "structural_channel_count", self.structural_channel_count
            ),
        )
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            raise OrganizationAnalysisError("organization_row_invalid_tick")
        object.__setattr__(
            self,
            "predecessor_ids",
            _sorted_ids("predecessor_ids", self.predecessor_ids),
        )
        object.__setattr__(
            self,
            "structural_signature",
            _text("structural_signature", self.structural_signature),
        )


@dataclass(frozen=True, slots=True)
class OrganizationMemberRow:
    owner_id: str
    organization_id: str
    member_id: str
    status: str
    basis: str
    temporal_scope: str
    first_tick: int
    last_tick: int
    expires_tick: int | None
    strength: float
    channels: tuple[str, ...]
    independently_evidenced: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text("owner_id", self.owner_id))
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(self, "member_id", _text("member_id", self.member_id))
        object.__setattr__(self, "status", _text("status", self.status))
        object.__setattr__(self, "basis", _text("basis", self.basis))
        object.__setattr__(
            self, "temporal_scope", _text("temporal_scope", self.temporal_scope)
        )
        first = _tick("first_tick", self.first_tick)
        last = _tick("last_tick", self.last_tick)
        if last < first:
            raise OrganizationAnalysisError("organization_row_invalid_tick")
        if self.expires_tick is not None:
            object.__setattr__(
                self, "expires_tick", _tick("expires_tick", self.expires_tick)
            )
        object.__setattr__(self, "strength", _number("strength", self.strength))
        object.__setattr__(self, "channels", _sorted_ids("channels", self.channels))
        if type(self.independently_evidenced) is not bool:
            raise OrganizationAnalysisError("organization_row_invalid_order")


@dataclass(frozen=True, slots=True)
class OrganizationRoleRow:
    owner_id: str
    organization_id: str
    office_id: str
    function: str
    context_key: str
    occupant_ids: tuple[str, ...]
    status: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationGoalRow:
    owner_id: str
    organization_id: str
    anchor_kind: str
    anchor_id: str
    status: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationResourceRow:
    owner_id: str
    organization_id: str
    resource_kind: str
    anchor_id: str
    access_belief: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationProcedureRow:
    owner_id: str
    organization_id: str
    procedure_kind: str
    anchor_id: str
    recurrence: int
    status: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationRecordRow:
    owner_id: str
    organization_id: str
    record_kind: str
    anchor_id: str
    integrity: float
    custody_belief: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationCommitmentRow:
    owner_id: str
    organization_id: str
    commitment_id: str
    role: str
    counterpart_id: str
    commitment_kind: str
    status: str
    first_tick: int
    last_tick: int
    due_tick: int | None


@dataclass(frozen=True, slots=True)
class OrganizationIdentityRow:
    owner_id: str
    organization_id: str
    label_token: str | None
    conceptualization: str
    stance: str
    first_tick: int
    last_tick: int


@dataclass(frozen=True, slots=True)
class OrganizationWindowRow:
    owner_id: str
    organization_id: str
    window_index: int
    tick: int
    status: str
    temporal_scope: str
    member_ids: tuple[str, ...]
    role_anchor_ids: tuple[str, ...]
    goal_anchor_ids: tuple[str, ...]
    resource_anchor_ids: tuple[str, ...]
    procedure_anchor_ids: tuple[str, ...]
    record_anchor_ids: tuple[str, ...]
    commitment_ids: tuple[str, ...]
    structural_signature: str
    evidence_count: int
    identity_token: str | None


@dataclass(frozen=True, slots=True)
class OrganizationLineageRow:
    owner_id: str
    lineage_id: str
    kind: str
    tick: int
    from_ids: tuple[str, ...]
    to_ids: tuple[str, ...]
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class OrganizationHarvestRows:
    owner: OrganizationOwnerRow
    concepts: tuple[OrganizationConceptRow, ...] = ()
    members: tuple[OrganizationMemberRow, ...] = ()
    roles: tuple[OrganizationRoleRow, ...] = ()
    goals: tuple[OrganizationGoalRow, ...] = ()
    resources: tuple[OrganizationResourceRow, ...] = ()
    procedures: tuple[OrganizationProcedureRow, ...] = ()
    records: tuple[OrganizationRecordRow, ...] = ()
    commitments: tuple[OrganizationCommitmentRow, ...] = ()
    identities: tuple[OrganizationIdentityRow, ...] = ()
    windows: tuple[OrganizationWindowRow, ...] = ()
    lineage: tuple[OrganizationLineageRow, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        concepts = tuple(self.concepts)
        if len(concepts) > MAX_HARVEST_CONCEPTS:
            raise OrganizationAnalysisError("organization_row_cap")
        object.__setattr__(self, "concepts", concepts)


def _owner_token(value: object) -> str:
    token = getattr(value, "value", value)
    if not isinstance(token, str) or not token:
        raise OrganizationAnalysisError("organization_row_owner_mismatch")
    return token


def _ledger_rows(ledger: object) -> OrganizationHarvestRows:
    owner_id = _owner_token(getattr(ledger, "owner_id", None))
    policy_version = getattr(ledger, "policy_version", None)
    if not isinstance(policy_version, str) or not policy_version:
        raise OrganizationAnalysisError("organization_row_invalid_order")
    concepts = tuple(getattr(ledger, "concepts", ()))
    if len(concepts) > MAX_HARVEST_CONCEPTS:
        raise OrganizationAnalysisError("organization_row_cap")
    concept_rows: list[OrganizationConceptRow] = []
    member_rows: list[OrganizationMemberRow] = []
    role_rows: list[OrganizationRoleRow] = []
    goal_rows: list[OrganizationGoalRow] = []
    resource_rows: list[OrganizationResourceRow] = []
    procedure_rows: list[OrganizationProcedureRow] = []
    record_rows: list[OrganizationRecordRow] = []
    commitment_rows: list[OrganizationCommitmentRow] = []
    identity_rows: list[OrganizationIdentityRow] = []
    window_rows: list[OrganizationWindowRow] = []
    seen: set[str] = set()
    for concept in concepts:
        concept_owner = getattr(concept, "owner_id", None)
        if concept_owner is not None and _owner_token(concept_owner) != owner_id:
            raise OrganizationAnalysisError("organization_row_owner_mismatch")
        organization_id = getattr(concept, "organization_id", None)
        if not isinstance(organization_id, str):
            raise OrganizationAnalysisError("organization_row_invalid_order")
        if organization_id in seen:
            raise OrganizationAnalysisError("organization_row_duplicate")
        seen.add(organization_id)
        concept_rows.append(
            OrganizationConceptRow(
                owner_id=owner_id,
                organization_id=organization_id,
                creation_tick=getattr(concept, "creation_tick", 0),
                status=getattr(getattr(concept, "status", None), "value", ""),
                temporal_scope=getattr(
                    getattr(concept, "temporal_scope", None), "value", ""
                ),
                strength=getattr(concept, "strength", 0.0),
                member_evidence_count=getattr(concept, "member_evidence_count", 0),
                structural_channel_count=getattr(
                    concept, "structural_channel_count", 0
                ),
                first_tick=getattr(concept, "first_tick", 0),
                last_tick=getattr(concept, "last_tick", 0),
                predecessor_ids=tuple(sorted(getattr(concept, "predecessor_ids", ()))),
                structural_signature=_text(
                    "structural_signature",
                    getattr(concept, "structural_signature", None)
                    or getattr(concept, "inception_digest", ""),
                ),
            )
        )
        for member in getattr(concept, "members", ()):
            member_rows.append(
                OrganizationMemberRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    member_id=getattr(member, "member_id", ""),
                    status=getattr(getattr(member, "status", None), "value", ""),
                    basis=getattr(getattr(member, "basis", None), "value", ""),
                    temporal_scope=getattr(
                        getattr(member, "temporal_scope", None), "value", ""
                    ),
                    first_tick=getattr(member, "first_tick", 0),
                    last_tick=getattr(member, "last_tick", 0),
                    expires_tick=getattr(member, "expires_tick", None),
                    strength=getattr(member, "strength", 0.0),
                    channels=tuple(
                        sorted(
                            getattr(channel, "value", channel)
                            for channel in getattr(member, "channels", ())
                        )
                    ),
                    independently_evidenced=getattr(
                        member, "independently_evidenced", False
                    ),
                )
            )
        for role in getattr(concept, "roles", ()):
            role_rows.append(
                OrganizationRoleRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    office_id=getattr(role, "office_id", ""),
                    function=getattr(role, "function", ""),
                    context_key=getattr(role, "context_key", ""),
                    occupant_ids=tuple(sorted(getattr(role, "occupant_ids", ()))),
                    status=getattr(getattr(role, "status", None), "value", ""),
                    first_tick=getattr(role, "first_tick", 0),
                    last_tick=getattr(role, "last_tick", 0),
                )
            )
        for goal in getattr(concept, "goals", ()):
            goal_rows.append(
                OrganizationGoalRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    anchor_kind=getattr(
                        getattr(goal, "anchor_kind", None), "value", ""
                    ),
                    anchor_id=getattr(goal, "anchor_id", ""),
                    status=getattr(getattr(goal, "status", None), "value", ""),
                    first_tick=getattr(goal, "first_tick", 0),
                    last_tick=getattr(goal, "last_tick", 0),
                )
            )
        for resource in getattr(concept, "resources", ()):
            resource_rows.append(
                OrganizationResourceRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    resource_kind=getattr(
                        getattr(resource, "resource_kind", None), "value", ""
                    ),
                    anchor_id=getattr(resource, "anchor_id", ""),
                    access_belief=getattr(resource, "access_belief", ""),
                    first_tick=getattr(resource, "first_tick", 0),
                    last_tick=getattr(resource, "last_tick", 0),
                )
            )
        for procedure in getattr(concept, "procedures", ()):
            procedure_rows.append(
                OrganizationProcedureRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    procedure_kind=getattr(
                        getattr(procedure, "procedure_kind", None), "value", ""
                    ),
                    anchor_id=getattr(procedure, "anchor_id", ""),
                    recurrence=getattr(procedure, "recurrence", 0),
                    status=getattr(getattr(procedure, "status", None), "value", ""),
                    first_tick=getattr(procedure, "first_tick", 0),
                    last_tick=getattr(procedure, "last_tick", 0),
                )
            )
        for record in getattr(concept, "records", ()):
            record_rows.append(
                OrganizationRecordRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    record_kind=getattr(
                        getattr(record, "record_kind", None), "value", ""
                    ),
                    anchor_id=getattr(record, "anchor_id", ""),
                    integrity=getattr(record, "integrity", 0.0),
                    custody_belief=getattr(record, "custody_belief", ""),
                    first_tick=getattr(record, "first_tick", 0),
                    last_tick=getattr(record, "last_tick", 0),
                )
            )
        for commitment in getattr(concept, "commitments", ()):
            commitment_rows.append(
                OrganizationCommitmentRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    commitment_id=getattr(commitment, "commitment_id", ""),
                    role=getattr(getattr(commitment, "role", None), "value", ""),
                    counterpart_id=getattr(commitment, "counterpart_id", ""),
                    commitment_kind=getattr(commitment, "commitment_kind", ""),
                    status=getattr(getattr(commitment, "status", None), "value", ""),
                    first_tick=getattr(commitment, "first_tick", 0),
                    last_tick=getattr(commitment, "last_tick", 0),
                    due_tick=getattr(commitment, "due_tick", None),
                )
            )
        for identity in getattr(concept, "identities", ()):
            identity_rows.append(
                OrganizationIdentityRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    label_token=getattr(identity, "label_token", None),
                    conceptualization=getattr(
                        getattr(identity, "conceptualization", None), "value", ""
                    ),
                    stance=getattr(getattr(identity, "stance", None), "value", ""),
                    first_tick=getattr(identity, "first_tick", 0),
                    last_tick=getattr(identity, "last_tick", 0),
                )
            )
        for window in getattr(concept, "snapshots", ()):
            window_rows.append(
                OrganizationWindowRow(
                    owner_id=owner_id,
                    organization_id=organization_id,
                    window_index=getattr(window, "window_index", 0),
                    tick=getattr(window, "tick", 0),
                    status=getattr(getattr(window, "status", None), "value", ""),
                    temporal_scope=getattr(
                        getattr(window, "temporal_scope", None), "value", ""
                    ),
                    member_ids=tuple(sorted(getattr(window, "member_ids", ()))),
                    role_anchor_ids=tuple(
                        sorted(getattr(window, "role_anchor_ids", ()))
                    ),
                    goal_anchor_ids=tuple(
                        sorted(getattr(window, "goal_anchor_ids", ()))
                    ),
                    resource_anchor_ids=tuple(
                        sorted(getattr(window, "resource_anchor_ids", ()))
                    ),
                    procedure_anchor_ids=tuple(
                        sorted(getattr(window, "procedure_anchor_ids", ()))
                    ),
                    record_anchor_ids=tuple(
                        sorted(getattr(window, "record_anchor_ids", ()))
                    ),
                    commitment_ids=tuple(sorted(getattr(window, "commitment_ids", ()))),
                    structural_signature=getattr(window, "structural_signature", ""),
                    evidence_count=getattr(window, "evidence_count", 0),
                    identity_token=getattr(window, "identity_token", None),
                )
            )
    lineage_rows: list[OrganizationLineageRow] = []
    for record in getattr(ledger, "lineage", ()):
        lineage_rows.append(
            OrganizationLineageRow(
                owner_id=owner_id,
                lineage_id=getattr(record, "lineage_id", ""),
                kind=getattr(getattr(record, "kind", None), "value", ""),
                tick=getattr(record, "tick", 0),
                from_ids=tuple(sorted(getattr(record, "from_ids", ()))),
                to_ids=tuple(sorted(getattr(record, "to_ids", ()))),
                evidence_digest=getattr(record, "evidence_digest", ""),
            )
        )
    owner_row = OrganizationOwnerRow(
        owner_id=owner_id,
        concept_count=len(concept_rows),
        lineage_count=len(lineage_rows),
        notices=tuple(sorted(getattr(ledger, "notices", ()))),
        policy_version=policy_version,
    )
    return OrganizationHarvestRows(
        owner=owner_row,
        concepts=tuple(
            sorted(concept_rows, key=lambda row: (row.organization_id, row.first_tick))
        ),
        members=tuple(
            sorted(
                member_rows,
                key=lambda row: (
                    row.organization_id,
                    row.first_tick,
                    row.member_id,
                ),
            )
        ),
        roles=tuple(
            sorted(role_rows, key=lambda row: (row.organization_id, row.office_id))
        ),
        goals=tuple(
            sorted(goal_rows, key=lambda row: (row.organization_id, row.anchor_id))
        ),
        resources=tuple(
            sorted(resource_rows, key=lambda row: (row.organization_id, row.anchor_id))
        ),
        procedures=tuple(
            sorted(procedure_rows, key=lambda row: (row.organization_id, row.anchor_id))
        ),
        records=tuple(
            sorted(record_rows, key=lambda row: (row.organization_id, row.anchor_id))
        ),
        commitments=tuple(
            sorted(
                commitment_rows,
                key=lambda row: (row.organization_id, row.commitment_id),
            )
        ),
        identities=tuple(
            sorted(
                identity_rows,
                key=lambda row: (
                    row.organization_id,
                    row.first_tick,
                    row.label_token or "",
                ),
            )
        ),
        windows=tuple(
            sorted(window_rows, key=lambda row: (row.organization_id, row.window_index))
        ),
        lineage=tuple(sorted(lineage_rows, key=lambda row: (row.tick, row.lineage_id))),
    )


def harvest_organization_rows(
    ledgers: Sequence[object] | None,
) -> tuple[OrganizationHarvestRows, ...]:
    """Harvest exported owner ledgers into detached rows."""

    if ledgers is None:
        return ()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise OrganizationAnalysisError("organization_row_invalid_order")
    items = tuple(ledgers)
    rows: tuple[OrganizationHarvestRows, ...]
    if items and all(isinstance(row, OrganizationHarvestRows) for row in items):
        rows = tuple(
            row for row in items if isinstance(row, OrganizationHarvestRows)
        )
    else:
        rows = tuple(_ledger_rows(ledger) for ledger in items)
    owners = [row.owner.owner_id for row in rows]
    if len(set(owners)) != len(owners):
        raise OrganizationAnalysisError("organization_row_duplicate")
    ordered = tuple(sorted(rows, key=lambda row: row.owner.owner_id))
    concept_count = sum(len(row.concepts) for row in ordered)
    member_count = sum(len(row.members) for row in ordered)
    _LOG.info(
        "organization_harvest owners=%s concepts=%s members=%s",
        len(ordered),
        concept_count,
        member_count,
    )
    return ordered


def harvest_organization_snapshot(
    runner_result: object,
) -> tuple[OrganizationHarvestRows, ...]:
    """Read organization ledgers from a completed runner result defensively."""

    ledgers = getattr(runner_result, "organization_concept_ledgers", ())
    if not ledgers:
        return ()
    return harvest_organization_rows(ledgers)
