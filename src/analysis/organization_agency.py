"""Detached collective-agency rows and analytical summary.

This module reads exported owner ledgers and existing analytical candidates. It
never imports cognition, world authority, event stores, persistence, API, or
observer packages, and it never creates, splits, merges, dissolves, or
re-identifies an ``org-`` candidate.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.numerical import quantize_float
from analysis.organization_contract import (
    OrganizationAnalysisError,
    OrganizationCoverage,
)

__all__ = [
    "OrganizationAgencyHarvestRows",
    "OrganizationAgencyOwnerRow",
    "OrganizationAgencySummary",
    "OrganizationAmendmentRow",
    "OrganizationCandidateAgency",
    "OrganizationCollectiveDecisionRow",
    "OrganizationImplementationRow",
    "OrganizationPositionRow",
    "OrganizationProposalRow",
    "harvest_organization_agency_rows",
    "harvest_organization_agency_snapshot",
    "organization_agency_concept_counts",
    "organization_agency_decision_ticks",
    "summarize_organization_agency",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_agency")

_ROW_ERROR: Final[str] = "organization_agency_row_invalid"
_SUMMARY_ERROR: Final[str] = "organization_agency_summary_invalid"

PROVENANCE_OK: Final[str] = "ok"
PROVENANCE_TRUNCATED: Final[str] = "collective_agency_truncated"
PROVENANCE_ORPHANED: Final[str] = "orphaned_concept"
PROVENANCE_UNKNOWN: Final[str] = "unknown_evidence"


def _text(name: str, value: object) -> str:
    token = getattr(value, "value", value)
    if type(token) is not str or not token:
        raise OrganizationAnalysisError(_ROW_ERROR)
    return token


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    token = getattr(value, "value", value)
    if type(token) is not str or not token:
        return None
    return token


def _optional_count(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _optional_tick(value: object) -> int | None:
    if type(value) is int and value >= 0:
        return value
    return None


def _records(source: object, name: str) -> Sequence[object]:
    values = getattr(source, name, ())
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise OrganizationAnalysisError(_ROW_ERROR)
    return values


def _owner_token(value: object) -> str:
    token = getattr(value, "value", value)
    if type(token) is not str or not token:
        raise OrganizationAnalysisError(_ROW_ERROR)
    return token


@dataclass(frozen=True, slots=True)
class OrganizationAgencyOwnerRow:
    owner_id: str
    concept_count: int
    proposal_count: int
    position_count: int
    amendment_count: int
    decision_count: int
    implementation_count: int
    notices: tuple[str, ...] = ()
    policy_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text("owner_id", self.owner_id))
        for name in (
            "concept_count",
            "proposal_count",
            "position_count",
            "amendment_count",
            "decision_count",
            "implementation_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise OrganizationAnalysisError(_ROW_ERROR)
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))
        object.__setattr__(
            self, "policy_version", _text("policy_version", self.policy_version)
        )


@dataclass(frozen=True, slots=True)
class OrganizationProposalRow:
    organization_id: str
    proposal_id: str
    proposal_ref: str | None = None
    topic: str | None = None
    domain: str | None = None
    effect: str | None = None
    implementation_mode: str | None = None
    target_kind: str | None = None
    target_ref: str | None = None
    procedure_ref: str | None = None
    revision: int = 1
    status: str | None = None
    opened_tick: int | None = None
    deadline_tick: int | None = None
    support_count: int | None = None
    oppose_count: int | None = None
    abstain_count: int | None = None
    contest_count: int | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(self, "proposal_id", _text("proposal_id", self.proposal_id))


@dataclass(frozen=True, slots=True)
class OrganizationPositionRow:
    organization_id: str
    proposal_id: str
    revision: int
    actor_id: str
    stance: str
    authority_basis: str
    disputed: bool
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(self, "proposal_id", _text("proposal_id", self.proposal_id))
        object.__setattr__(self, "actor_id", _text("actor_id", self.actor_id))


@dataclass(frozen=True, slots=True)
class OrganizationAmendmentRow:
    organization_id: str
    proposal_id: str
    amendment_id: str
    from_revision: int
    to_revision: int
    domain: str | None = None
    effect: str | None = None
    target_kind: str | None = None
    target_ref: str | None = None
    procedure_ref: str | None = None
    amended_tick: int | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(self, "proposal_id", _text("proposal_id", self.proposal_id))
        object.__setattr__(
            self, "amendment_id", _text("amendment_id", self.amendment_id)
        )


@dataclass(frozen=True, slots=True)
class OrganizationCollectiveDecisionRow:
    organization_id: str
    decision_id: str
    proposal_id: str
    revision: int
    procedure_ref: str | None = None
    recognition: str | None = None
    authority_basis: str | None = None
    support_count: int | None = None
    oppose_count: int | None = None
    abstain_count: int | None = None
    contest_count: int | None = None
    implementation_mode: str | None = None
    effect: str | None = None
    target_kind: str | None = None
    target_ref: str | None = None
    decided_tick: int | None = None
    window_end_tick: int | None = None
    implementation_status: str | None = None
    provenance_code: str | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(self, "decision_id", _text("decision_id", self.decision_id))
        object.__setattr__(self, "proposal_id", _text("proposal_id", self.proposal_id))


@dataclass(frozen=True, slots=True)
class OrganizationImplementationRow:
    organization_id: str
    implementation_id: str
    decision_id: str
    actor_id: str
    status: str
    effect: str | None = None
    observed_tick: int | None = None
    provenance_code: str | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", _text("organization_id", self.organization_id)
        )
        object.__setattr__(
            self,
            "implementation_id",
            _text("implementation_id", self.implementation_id),
        )
        object.__setattr__(self, "decision_id", _text("decision_id", self.decision_id))
        object.__setattr__(self, "actor_id", _text("actor_id", self.actor_id))


@dataclass(frozen=True, slots=True)
class OrganizationAgencyHarvestRows:
    owner: OrganizationAgencyOwnerRow
    proposals: tuple[OrganizationProposalRow, ...] = ()
    positions: tuple[OrganizationPositionRow, ...] = ()
    amendments: tuple[OrganizationAmendmentRow, ...] = ()
    decisions: tuple[OrganizationCollectiveDecisionRow, ...] = ()
    implementations: tuple[OrganizationImplementationRow, ...] = ()
    concept_ticks: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner) is not OrganizationAgencyOwnerRow:
            raise OrganizationAnalysisError(_ROW_ERROR)
        for name in (
            "proposals",
            "positions",
            "amendments",
            "decisions",
            "implementations",
        ):
            values = getattr(self, name)
            if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
                raise OrganizationAnalysisError(_ROW_ERROR)
            object.__setattr__(self, name, tuple(values))
        ticks = tuple(self.concept_ticks)
        for organization_id, tick in ticks:
            _text("organization_id", organization_id)
            if type(tick) is not int or tick < 0:
                raise OrganizationAnalysisError(_ROW_ERROR)
        object.__setattr__(self, "concept_ticks", tuple(sorted(ticks)))


def _ledger_rows(ledger: object) -> OrganizationAgencyHarvestRows:
    owner_id = _text("owner_id", _owner_token(getattr(ledger, "owner_id", None)))
    policy_version = getattr(ledger, "policy_version", None)
    if type(policy_version) is not str or not policy_version:
        raise OrganizationAnalysisError(_ROW_ERROR)
    concepts = _records(ledger, "concepts")
    proposals: list[OrganizationProposalRow] = []
    positions: list[OrganizationPositionRow] = []
    amendments: list[OrganizationAmendmentRow] = []
    decisions: list[OrganizationCollectiveDecisionRow] = []
    implementations: list[OrganizationImplementationRow] = []
    concept_ticks: list[tuple[str, int]] = []
    seen: set[str] = set()
    for concept in concepts:
        concept_owner = getattr(concept, "owner_id", None)
        if concept_owner is not None and _owner_token(concept_owner) != owner_id:
            raise OrganizationAnalysisError(_ROW_ERROR)
        organization_id = _text(
            "organization_id", getattr(concept, "organization_id", None)
        )
        if organization_id in seen:
            raise OrganizationAnalysisError(_ROW_ERROR)
        seen.add(organization_id)
        first_tick = _optional_tick(getattr(concept, "first_tick", None))
        last_tick = _optional_tick(getattr(concept, "last_tick", None))
        if first_tick is not None and last_tick is not None and last_tick < first_tick:
            raise OrganizationAnalysisError(_ROW_ERROR)
        if last_tick is not None:
            concept_ticks.append((organization_id, last_tick))
        for record in _records(concept, "proposals"):
            proposals.append(
                OrganizationProposalRow(
                    organization_id=organization_id,
                    proposal_id=_text(
                        "proposal_id", getattr(record, "proposal_id", None)
                    ),
                    proposal_ref=_optional_text(getattr(record, "proposal_ref", None)),
                    topic=_optional_text(getattr(record, "topic", None)),
                    domain=_optional_text(getattr(record, "domain", None)),
                    effect=_optional_text(getattr(record, "effect", None)),
                    implementation_mode=_optional_text(
                        getattr(record, "implementation_mode", None)
                    ),
                    target_kind=_optional_text(getattr(record, "target_kind", None)),
                    target_ref=_optional_text(getattr(record, "target_ref", None)),
                    procedure_ref=_optional_text(
                        getattr(record, "procedure_ref", None)
                    ),
                    revision=_optional_count(getattr(record, "revision", None)) or 1,
                    status=_optional_text(getattr(record, "status", None)),
                    opened_tick=_optional_tick(getattr(record, "opened_tick", None)),
                    deadline_tick=_optional_tick(
                        getattr(record, "deadline_tick", None)
                    ),
                    support_count=_optional_count(
                        getattr(record, "support_count", None)
                    ),
                    oppose_count=_optional_count(getattr(record, "oppose_count", None)),
                    abstain_count=_optional_count(
                        getattr(record, "abstain_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                    resolved=(
                        getattr(record, "target_kind", None) not in ("none", "unknown")
                    ),
                )
            )
        for record in _records(concept, "positions"):
            positions.append(
                OrganizationPositionRow(
                    organization_id=organization_id,
                    proposal_id=_text(
                        "proposal_id", getattr(record, "proposal_id", None)
                    ),
                    revision=_optional_count(getattr(record, "revision", None)) or 1,
                    actor_id=_text(
                        "actor_id", _owner_token(getattr(record, "actor_id", None))
                    ),
                    stance=_text("stance", getattr(record, "stance", None)),
                    authority_basis=_text(
                        "authority_basis", getattr(record, "authority_basis", None)
                    ),
                    disputed=bool(getattr(record, "disputed", False)),
                    tick=_optional_tick(getattr(record, "tick", None)) or 0,
                )
            )
        for record in _records(concept, "amendments"):
            amendments.append(
                OrganizationAmendmentRow(
                    organization_id=organization_id,
                    proposal_id=_text(
                        "proposal_id", getattr(record, "proposal_id", None)
                    ),
                    amendment_id=_text(
                        "amendment_id", getattr(record, "amendment_id", None)
                    ),
                    from_revision=(
                        _optional_count(getattr(record, "from_revision", None)) or 1
                    ),
                    to_revision=(
                        _optional_count(getattr(record, "to_revision", None)) or 2
                    ),
                    domain=_optional_text(getattr(record, "domain", None)),
                    effect=_optional_text(getattr(record, "effect", None)),
                    target_kind=_optional_text(getattr(record, "target_kind", None)),
                    target_ref=_optional_text(getattr(record, "target_ref", None)),
                    procedure_ref=_optional_text(
                        getattr(record, "procedure_ref", None)
                    ),
                    amended_tick=_optional_tick(getattr(record, "amended_tick", None)),
                )
            )
        for record in _records(concept, "decisions"):
            decisions.append(
                OrganizationCollectiveDecisionRow(
                    organization_id=organization_id,
                    decision_id=_text(
                        "decision_id", getattr(record, "decision_id", None)
                    ),
                    proposal_id=_text(
                        "proposal_id", getattr(record, "proposal_id", None)
                    ),
                    revision=_optional_count(getattr(record, "revision", None)) or 1,
                    procedure_ref=_optional_text(
                        getattr(record, "procedure_ref", None)
                    ),
                    recognition=_optional_text(getattr(record, "recognition", None)),
                    authority_basis=_optional_text(
                        getattr(record, "authority_basis", None)
                    ),
                    support_count=_optional_count(
                        getattr(record, "support_count", None)
                    ),
                    oppose_count=_optional_count(getattr(record, "oppose_count", None)),
                    abstain_count=_optional_count(
                        getattr(record, "abstain_count", None)
                    ),
                    contest_count=_optional_count(
                        getattr(record, "contest_count", None)
                    ),
                    implementation_mode=_optional_text(
                        getattr(record, "implementation_mode", None)
                    ),
                    effect=_optional_text(getattr(record, "effect", None)),
                    target_kind=_optional_text(getattr(record, "target_kind", None)),
                    target_ref=_optional_text(getattr(record, "target_ref", None)),
                    decided_tick=_optional_tick(getattr(record, "decided_tick", None)),
                    window_end_tick=_optional_tick(
                        getattr(record, "window_end_tick", None)
                    ),
                    implementation_status=_optional_text(
                        getattr(record, "implementation_status", None)
                    ),
                    provenance_code=_optional_text(
                        getattr(record, "provenance_code", None)
                    ),
                )
            )
        for record in _records(concept, "implementations"):
            implementations.append(
                OrganizationImplementationRow(
                    organization_id=organization_id,
                    implementation_id=_text(
                        "implementation_id", getattr(record, "implementation_id", None)
                    ),
                    decision_id=_text(
                        "decision_id", getattr(record, "decision_id", None)
                    ),
                    actor_id=_text(
                        "actor_id", _owner_token(getattr(record, "actor_id", None))
                    ),
                    status=_text("status", getattr(record, "status", None)),
                    effect=_optional_text(getattr(record, "effect", None)),
                    observed_tick=_optional_tick(
                        getattr(record, "observed_tick", None)
                    ),
                    provenance_code=_optional_text(
                        getattr(record, "provenance_code", None)
                    ),
                )
            )

    proposals.sort(
        key=lambda item: (item.organization_id, item.opened_tick or 0, item.proposal_id)
    )
    positions.sort(
        key=lambda item: (
            item.organization_id,
            item.proposal_id,
            item.revision,
            item.actor_id,
            item.tick,
        )
    )
    amendments.sort(
        key=lambda item: (
            item.organization_id,
            item.proposal_id,
            item.to_revision,
        )
    )
    decisions.sort(
        key=lambda item: (
            item.organization_id,
            item.decided_tick or 0,
            item.decision_id,
        )
    )
    implementations.sort(
        key=lambda item: (
            item.organization_id,
            item.decision_id,
            item.actor_id,
            item.observed_tick or 0,
        )
    )
    notices = tuple(sorted(set(getattr(ledger, "notices", ()))))
    owner = OrganizationAgencyOwnerRow(
        owner_id=owner_id,
        concept_count=len(seen),
        proposal_count=len(proposals),
        position_count=len(positions),
        amendment_count=len(amendments),
        decision_count=len(decisions),
        implementation_count=len(implementations),
        notices=notices,
        policy_version=policy_version,
    )
    return OrganizationAgencyHarvestRows(
        owner=owner,
        proposals=tuple(proposals),
        positions=tuple(positions),
        amendments=tuple(amendments),
        decisions=tuple(decisions),
        implementations=tuple(implementations),
        concept_ticks=tuple(concept_ticks),
    )


def harvest_organization_agency_rows(
    ledgers: Sequence[object] | None,
) -> tuple[OrganizationAgencyHarvestRows, ...]:
    """Harvest exported owner agency ledgers into detached rows."""

    if ledgers is None:
        return ()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise OrganizationAnalysisError(_ROW_ERROR)
    items = tuple(ledgers)
    rows: tuple[OrganizationAgencyHarvestRows, ...]
    if items and all(type(ledger) is OrganizationAgencyHarvestRows for ledger in items):
        rows = tuple(
            ledger
            for ledger in items
            if isinstance(ledger, OrganizationAgencyHarvestRows)
        )
    else:
        rows = tuple(_ledger_rows(ledger) for ledger in items)
    owners = [row.owner.owner_id for row in rows]
    if len(set(owners)) != len(owners):
        raise OrganizationAnalysisError(_ROW_ERROR)
    ordered = tuple(sorted(rows, key=lambda row: row.owner.owner_id))
    _LOG.info(
        "organization_agency_harvest owners=%s concepts=%s proposals=%s "
        "decisions=%s implementations=%s",
        len(ordered),
        sum(row.owner.concept_count for row in ordered),
        sum(len(row.proposals) for row in ordered),
        sum(len(row.decisions) for row in ordered),
        sum(len(row.implementations) for row in ordered),
    )
    return ordered


def harvest_organization_agency_snapshot(
    runner_result: object,
) -> tuple[OrganizationAgencyHarvestRows, ...]:
    """Read agency ledgers from a completed runner result defensively."""

    ledgers = getattr(runner_result, "organization_agency_ledgers", ())
    if not ledgers:
        return ()
    return harvest_organization_agency_rows(ledgers)


def organization_agency_concept_counts(
    rows: Sequence[OrganizationAgencyHarvestRows] | None,
) -> tuple[tuple[str, str, int, int, int, int], ...]:
    """Return ``(owner, concept, proposals, decisions, implementations, open)``."""

    if not rows:
        return ()
    grouped: dict[tuple[str, str], list[int]] = {}
    for owner_row in rows:
        for proposal in owner_row.proposals:
            key = (owner_row.owner.owner_id, proposal.organization_id)
            grouped.setdefault(key, [0, 0, 0, 0])[0] += 1
        for decision in owner_row.decisions:
            key = (owner_row.owner.owner_id, decision.organization_id)
            grouped.setdefault(key, [0, 0, 0, 0])[1] += 1
        for implementation in owner_row.implementations:
            key = (owner_row.owner.owner_id, implementation.organization_id)
            bucket = grouped.setdefault(key, [0, 0, 0, 0])
            bucket[2] += 1
            if implementation.status == "unimplemented":
                bucket[3] += 1
    return tuple(
        (
            owner_id,
            organization_id,
            counts[0],
            counts[1],
            counts[2],
            counts[3],
        )
        for (owner_id, organization_id), counts in sorted(grouped.items())
    )


def organization_agency_decision_ticks(
    rows: Sequence[OrganizationAgencyHarvestRows] | None,
) -> tuple[int, ...]:
    if not rows:
        return ()
    ticks: set[int] = set()
    for owner_row in rows:
        for decision in owner_row.decisions:
            if decision.decided_tick is not None:
                ticks.add(decision.decided_tick)
    return tuple(sorted(ticks))


@dataclass(frozen=True, slots=True)
class OrganizationCandidateAgency:
    organization_id: str
    proposal_count: int = 0
    amendment_count: int = 0
    support_count: int = 0
    oppose_count: int = 0
    abstain_count: int = 0
    recognized_decision_count: int = 0
    contested_decision_count: int = 0
    unrecognized_decision_count: int = 0
    expired_proposal_count: int = 0
    implemented_decision_count: int = 0
    partial_decision_count: int = 0
    unimplemented_decision_count: int = 0
    obstructed_decision_count: int = 0
    unknown_decision_count: int = 0
    compliance_count: int = 0
    refusal_count: int = 0
    sabotage_count: int = 0
    contrary_count: int = 0
    orphaned_count: int = 0
    coverage_ratio: float | None = None

    def __post_init__(self) -> None:
        if not self.organization_id.startswith("org-"):
            raise OrganizationAnalysisError(_SUMMARY_ERROR)


@dataclass(frozen=True, slots=True)
class OrganizationAgencySummary:
    candidates: tuple[OrganizationCandidateAgency, ...] = ()
    candidate_count: int = 0
    candidates_with_agency: int = 0
    proposal_count: int = 0
    amendment_count: int = 0
    support_count: int = 0
    oppose_count: int = 0
    abstain_count: int = 0
    decision_count: int = 0
    implementation_count: int = 0
    orphaned_count: int = 0
    history_truncated: bool = False
    coverage_ratio: float | None = None
    coverage: OrganizationCoverage | None = None
    provenance_code: str = PROVENANCE_OK
    candidate_map: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.candidates, key=lambda item: item.organization_id))
        seen: set[str] = set()
        for candidate in ordered:
            if type(candidate) is not OrganizationCandidateAgency:
                raise OrganizationAnalysisError(_SUMMARY_ERROR)
            if candidate.organization_id in seen:
                raise OrganizationAnalysisError(_SUMMARY_ERROR)
            seen.add(candidate.organization_id)
        object.__setattr__(self, "candidates", ordered)
        if self.provenance_code not in (
            PROVENANCE_OK,
            PROVENANCE_TRUNCATED,
            PROVENANCE_ORPHANED,
            PROVENANCE_UNKNOWN,
        ):
            raise OrganizationAnalysisError(_SUMMARY_ERROR)


@dataclass
class _Accumulator:
    organization_id: str
    proposal_count: int = 0
    amendment_count: int = 0
    support_count: int = 0
    oppose_count: int = 0
    abstain_count: int = 0
    recognized_decision_count: int = 0
    contested_decision_count: int = 0
    unrecognized_decision_count: int = 0
    expired_proposal_count: int = 0
    implemented_decision_count: int = 0
    partial_decision_count: int = 0
    unimplemented_decision_count: int = 0
    obstructed_decision_count: int = 0
    unknown_decision_count: int = 0
    compliance_count: int = 0
    refusal_count: int = 0
    sabotage_count: int = 0
    contrary_count: int = 0
    orphaned_count: int = 0
    decisions_with_implementation: int = 0
    decision_ids: set[str] = field(default_factory=set)

    def add_positions(
        self,
        positions: Sequence[OrganizationPositionRow],
        proposals: Sequence[OrganizationProposalRow],
    ) -> None:
        latest_revision = {
            proposal.proposal_id: proposal.revision for proposal in proposals
        }
        seen: set[tuple[str, str]] = set()
        for position in positions:
            if position.revision != latest_revision.get(position.proposal_id):
                continue
            key = (position.proposal_id, position.actor_id)
            if key in seen:
                continue
            seen.add(key)
            if position.stance == "support":
                self.support_count += 1
            elif position.stance == "oppose":
                self.oppose_count += 1
            elif position.stance == "abstain":
                self.abstain_count += 1


def summarize_organization_agency(
    rows: Sequence[OrganizationAgencyHarvestRows] | None,
    assignment: object | None,
    *,
    member_rows: Sequence[object] = (),
) -> OrganizationAgencySummary | None:
    """Join owner agency rows to existing final-window analytical candidates."""

    if rows is None or not rows:
        return None
    if assignment is None:
        return None
    windows = getattr(assignment, "windows", ())
    if not windows:
        return None
    final_window = windows[-1]
    candidates = tuple(
        sorted(final_window.candidates, key=lambda item: item.candidate_key)
    )
    candidate_ids: dict[str, str] = {}
    for key, organization_id in getattr(assignment, "candidate_ids", ()):
        candidate_ids[key] = organization_id
    accumulators: dict[str, _Accumulator] = {}
    for candidate in candidates:
        organization_id = candidate_ids.get(candidate.candidate_key)
        if organization_id is None:
            continue
        accumulators[organization_id] = _Accumulator(organization_id=organization_id)

    member_map: dict[tuple[str, str], set[str]] = {}
    for owner in member_rows:
        owner_id = getattr(getattr(owner, "owner", None), "owner_id", None)
        for member in getattr(owner, "members", ()):
            organization_id = getattr(member, "organization_id", None)
            if owner_id is None or organization_id is None:
                continue
            member_map.setdefault((owner_id, organization_id), set()).add(
                getattr(member, "member_id", "")
            )
    candidate_members = {
        candidate.candidate_key: set(candidate.member_ids) for candidate in candidates
    }
    candidate_owner_ids = {
        candidate.candidate_key: set(candidate.owner_ids) for candidate in candidates
    }

    candidate_map: list[tuple[str, str, str]] = []
    orphaned = 0
    for owner_row in rows:
        owner_id = owner_row.owner.owner_id
        by_concept: dict[str, list[object]] = {}
        for family in (
            owner_row.proposals,
            owner_row.positions,
            owner_row.amendments,
            owner_row.decisions,
            owner_row.implementations,
        ):
            for record in family:
                by_concept.setdefault(record.organization_id, []).append(record)
        for organization_id in sorted(by_concept):
            members = member_map.get((owner_id, organization_id), set())
            best_key: str | None = None
            best_score = 0.0
            for candidate in candidates:
                if owner_id not in candidate_owner_ids[candidate.candidate_key]:
                    continue
                other = candidate_members[candidate.candidate_key]
                if not members or not other:
                    continue
                score = len(members & other) / len(members | other)
                if score > best_score or (
                    score == best_score
                    and best_key is not None
                    and candidate.candidate_key < best_key
                ):
                    best_score = score
                    best_key = candidate.candidate_key
            if best_key is None or best_score < 0.5:
                orphaned += 1
                continue
            accumulator = accumulators.get(candidate_ids[best_key])
            if accumulator is None:
                orphaned += 1
                continue
            candidate_map.append(
                (owner_id, organization_id, candidate_ids[best_key])
            )
            proposals = [
                record
                for record in owner_row.proposals
                if record.organization_id == organization_id
            ]
            positions = [
                record
                for record in owner_row.positions
                if record.organization_id == organization_id
            ]
            accumulator.proposal_count += len(proposals)
            accumulator.amendment_count += sum(
                1
                for record in owner_row.amendments
                if record.organization_id == organization_id
            )
            accumulator.expired_proposal_count += sum(
                1 for record in proposals if record.status == "expired"
            )
            accumulator.add_positions(positions, proposals)
            for decision in owner_row.decisions:
                if decision.organization_id != organization_id:
                    continue
                accumulator.decision_ids.add(decision.decision_id)
                if decision.recognition == "recognized":
                    accumulator.recognized_decision_count += 1
                elif decision.recognition == "contested":
                    accumulator.contested_decision_count += 1
                elif decision.recognition == "unrecognized":
                    accumulator.unrecognized_decision_count += 1
                status = decision.implementation_status
                if status == "implemented":
                    accumulator.implemented_decision_count += 1
                elif status == "partial":
                    accumulator.partial_decision_count += 1
                elif status == "unimplemented":
                    accumulator.unimplemented_decision_count += 1
                elif status == "obstructed":
                    accumulator.obstructed_decision_count += 1
                elif status == "unknown":
                    accumulator.unknown_decision_count += 1
            for implementation in owner_row.implementations:
                if implementation.organization_id != organization_id:
                    continue
                if implementation.status == "implemented":
                    accumulator.compliance_count += 1
                elif implementation.status == "refused":
                    accumulator.refusal_count += 1
                elif implementation.status == "sabotaged":
                    accumulator.sabotage_count += 1
                elif implementation.status == "contrary":
                    accumulator.contrary_count += 1
            accumulator.decisions_with_implementation += len(
                {
                    implementation.decision_id
                    for implementation in owner_row.implementations
                    if implementation.organization_id == organization_id
                }
                & accumulator.decision_ids
            )

    summaries: list[OrganizationCandidateAgency] = []
    for organization_id in sorted(accumulators):
        accumulator = accumulators[organization_id]
        decision_count = len(accumulator.decision_ids)
        coverage = (
            quantize_float(
                min(1.0, accumulator.decisions_with_implementation / decision_count)
            )
            if decision_count
            else None
        )
        summaries.append(
            OrganizationCandidateAgency(
                organization_id=organization_id,
                proposal_count=accumulator.proposal_count,
                amendment_count=accumulator.amendment_count,
                support_count=accumulator.support_count,
                oppose_count=accumulator.oppose_count,
                abstain_count=accumulator.abstain_count,
                recognized_decision_count=accumulator.recognized_decision_count,
                contested_decision_count=accumulator.contested_decision_count,
                unrecognized_decision_count=accumulator.unrecognized_decision_count,
                expired_proposal_count=accumulator.expired_proposal_count,
                implemented_decision_count=accumulator.implemented_decision_count,
                partial_decision_count=accumulator.partial_decision_count,
                unimplemented_decision_count=accumulator.unimplemented_decision_count,
                obstructed_decision_count=accumulator.obstructed_decision_count,
                unknown_decision_count=accumulator.unknown_decision_count,
                compliance_count=accumulator.compliance_count,
                refusal_count=accumulator.refusal_count,
                sabotage_count=accumulator.sabotage_count,
                contrary_count=accumulator.contrary_count,
                orphaned_count=accumulator.orphaned_count,
                coverage_ratio=coverage,
            )
        )

    candidates_with_agency = sum(
        1
        for candidate in summaries
        if candidate.proposal_count
        or candidate.recognized_decision_count
        or candidate.contested_decision_count
        or candidate.unrecognized_decision_count
    )
    candidate_count = len(accumulators)
    history_truncated = any(
        "agency_truncated" in owner_row.owner.notices
        or "implementation_truncated" in owner_row.owner.notices
        for owner_row in rows
    )
    unknown = any(candidate.unknown_decision_count > 0 for candidate in summaries)
    if history_truncated:
        provenance = PROVENANCE_TRUNCATED
    elif orphaned:
        provenance = PROVENANCE_ORPHANED
    elif unknown:
        provenance = PROVENANCE_UNKNOWN
    else:
        provenance = PROVENANCE_OK
    coverage_ratio = (
        quantize_float(candidates_with_agency / candidate_count)
        if candidate_count
        else None
    )
    return OrganizationAgencySummary(
        candidates=tuple(summaries),
        candidate_count=candidate_count,
        candidates_with_agency=candidates_with_agency,
        proposal_count=sum(item.proposal_count for item in summaries),
        amendment_count=sum(item.amendment_count for item in summaries),
        support_count=sum(item.support_count for item in summaries),
        oppose_count=sum(item.oppose_count for item in summaries),
        abstain_count=sum(item.abstain_count for item in summaries),
        decision_count=sum(
            item.recognized_decision_count
            + item.contested_decision_count
            + item.unrecognized_decision_count
            for item in summaries
        ),
        implementation_count=sum(
            item.compliance_count
            + item.refusal_count
            + item.sabotage_count
            + item.contrary_count
            for item in summaries
        ),
        orphaned_count=orphaned,
        history_truncated=history_truncated,
        coverage_ratio=coverage_ratio,
        coverage=OrganizationCoverage.of(candidates_with_agency, candidate_count),
        provenance_code=provenance,
        candidate_map=tuple(sorted(candidate_map)),
    )
