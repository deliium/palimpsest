"""Detached cross-owner organization candidate detection.

Candidates are analytical research labels. Owner beliefs are never collapsed
into one roster, membership is never a partition, and a person may appear in
more than one candidate.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.organization_contract import (
    MAX_WINDOW_CANDIDATES,
    OrganizationAnalysisError,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationMembershipStatus,
    OrganizationTemporalScope,
)
from analysis.organization_evidence import (
    ANCHOR_FAMILIES,
    OrganizationWindowEvidence,
)
from analysis.organizations import OrganizationConceptRow

__all__ = [
    "OrganizationCandidate",
    "OrganizationDetectionResult",
    "OrganizationMemberClaim",
    "OrganizationWindowResult",
    "detect_organization_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_detection")

_STATUS_PRECEDENCE: Final[dict[OrganizationMembershipStatus, int]] = {
    OrganizationMembershipStatus.UNKNOWN: 1,
    OrganizationMembershipStatus.PERCEIVED: 2,
    OrganizationMembershipStatus.FORMER: 3,
    OrganizationMembershipStatus.EXPLICIT: 4,
    OrganizationMembershipStatus.DISPUTED: 5,
}


@dataclass(frozen=True, slots=True)
class OrganizationMemberClaim:
    member_id: str
    status: OrganizationMembershipStatus
    basis: str
    temporal_scope: OrganizationTemporalScope
    owner_ids: tuple[str, ...]
    channels: tuple[str, ...] = ()
    dispute_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrganizationCandidate:
    candidate_key: str
    window_index: int
    member_ids: tuple[str, ...]
    member_claims: tuple[OrganizationMemberClaim, ...]
    role_anchor_ids: tuple[str, ...]
    goal_anchor_ids: tuple[str, ...]
    resource_anchor_ids: tuple[str, ...]
    procedure_anchor_ids: tuple[str, ...]
    record_anchor_ids: tuple[str, ...]
    commitment_ids: tuple[str, ...]
    identity_tokens: tuple[str, ...]
    status: OrganizationCandidateStatus
    temporal_scope: OrganizationTemporalScope
    self_identified: bool
    owner_ids: tuple[str, ...]
    first_tick: int
    last_tick: int
    overlap_member_ids: tuple[str, ...] = ()

    @property
    def anchor_signature(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    *(f"role:{item}" for item in self.role_anchor_ids),
                    *(f"goal:{item}" for item in self.goal_anchor_ids),
                    *(f"resource:{item}" for item in self.resource_anchor_ids),
                    *(f"procedure:{item}" for item in self.procedure_anchor_ids),
                    *(f"record:{item}" for item in self.record_anchor_ids),
                    *(f"commitment:{item}" for item in self.commitment_ids),
                }
            )
        )


@dataclass(frozen=True, slots=True)
class OrganizationWindowResult:
    window_index: int
    start_tick: int
    end_tick: int
    candidate_keys: tuple[str, ...]
    lane_presence: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class OrganizationDetectionResult:
    windows: tuple[OrganizationWindowResult, ...] = ()
    candidates: tuple[OrganizationCandidate, ...] = ()
    overlap_person_ids: tuple[str, ...] = ()
    lane_presence: tuple[tuple[str, bool], ...] = ()
    coverage: OrganizationCoverage = field(
        default_factory=lambda: OrganizationCoverage.of(0, 0)
    )


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left != root_right:
            self._parent[max(root_left, root_right)] = min(root_left, root_right)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _candidate_key(
    window_index: int, member_ids: Iterable[str], anchors: Iterable[str]
) -> str:
    payload = "|".join(
        (
            "organization-candidate.v1",
            str(window_index),
            ",".join(sorted(member_ids)),
            ",".join(sorted(anchors)),
        )
    )
    return f"cand-{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _contributions(
    window: OrganizationWindowEvidence,
) -> list[tuple[str, OrganizationConceptRow, set[str], set[str]]]:
    items: list[tuple[str, OrganizationConceptRow, set[str], set[str]]] = []
    for owner in window.owner_rows:
        for concept in owner.concepts:
            if not (
                concept.first_tick <= window.end_tick
                and concept.last_tick >= window.start_tick
            ):
                continue
            members = {
                member.member_id
                for member in owner.members
                if member.organization_id == concept.organization_id
            }
            anchors = {
                *(
                    f"role:{role.office_id}"
                    for role in owner.roles
                    if role.organization_id == concept.organization_id
                ),
                *(
                    f"goal:{goal.anchor_id}"
                    for goal in owner.goals
                    if goal.organization_id == concept.organization_id
                ),
                *(
                    f"resource:{item.anchor_id}"
                    for item in owner.resources
                    if item.organization_id == concept.organization_id
                ),
                *(
                    f"procedure:{item.anchor_id}"
                    for item in owner.procedures
                    if item.organization_id == concept.organization_id
                ),
                *(
                    f"record:{item.anchor_id}"
                    for item in owner.records
                    if item.organization_id == concept.organization_id
                ),
                *(
                    f"commitment:{item.commitment_id}"
                    for item in owner.commitments
                    if item.organization_id == concept.organization_id
                ),
            }
            items.append((owner.owner.owner_id, concept, members, anchors))
    return items


def _member_claims(
    window: OrganizationWindowEvidence,
    member_ids: set[str],
) -> tuple[OrganizationMemberClaim, ...]:
    claims: list[OrganizationMemberClaim] = []
    for member_id in sorted(member_ids):
        statuses: list[OrganizationMembershipStatus] = []
        scopes: list[OrganizationTemporalScope] = []
        owners: set[str] = set()
        channels: set[str] = set()
        basis = "inference"
        for owner in window.owner_rows:
            for member in owner.members:
                if member.member_id != member_id:
                    continue
                statuses.append(OrganizationMembershipStatus(member.status))
                scopes.append(OrganizationTemporalScope(member.temporal_scope))
                owners.add(owner.owner.owner_id)
                channels.update(member.channels)
                basis = member.basis
        if not statuses:
            claims.append(
                OrganizationMemberClaim(
                    member_id=member_id,
                    status=OrganizationMembershipStatus.UNKNOWN,
                    basis="record_reference",
                    temporal_scope=OrganizationTemporalScope.UNKNOWN,
                    owner_ids=tuple(sorted(owners)),
                )
            )
            continue
        disputed = OrganizationMembershipStatus.DISPUTED in statuses or (
            OrganizationMembershipStatus.EXPLICIT in statuses
            and OrganizationMembershipStatus.FORMER in statuses
        )
        status = max(statuses, key=lambda item: _STATUS_PRECEDENCE[item])
        if disputed:
            status = OrganizationMembershipStatus.DISPUTED
        scope = (
            OrganizationTemporalScope.TEMPORARY
            if OrganizationTemporalScope.TEMPORARY in scopes
            else (
                OrganizationTemporalScope.ONGOING
                if OrganizationTemporalScope.ONGOING in scopes
                else OrganizationTemporalScope.UNKNOWN
            )
        )
        claims.append(
            OrganizationMemberClaim(
                member_id=member_id,
                status=status,
                basis=basis,
                temporal_scope=scope,
                owner_ids=tuple(sorted(owners)),
                channels=tuple(sorted(channels)),
                dispute_reasons=("contradictory_owner_status",) if disputed else (),
            )
        )
    return tuple(claims)


def _candidate_from_group(
    window: OrganizationWindowEvidence,
    indices: Sequence[int],
    contributions: Sequence[tuple[str, OrganizationConceptRow, set[str], set[str]]],
) -> OrganizationCandidate:
    members: set[str] = set()
    anchors: set[str] = set()
    owners: set[str] = set()
    statuses: list[str] = []
    first_tick = window.end_tick
    last_tick = window.start_tick
    roles: set[str] = set()
    goals: set[str] = set()
    resources: set[str] = set()
    procedures: set[str] = set()
    records: set[str] = set()
    commitments: set[str] = set()
    identity_tokens: set[str] = set()
    for index in indices:
        owner_id, concept, concept_members, concept_anchors = contributions[index]
        owners.add(owner_id)
        members |= concept_members
        anchors |= concept_anchors
        statuses.append(concept.status)
        first_tick = min(first_tick, concept.first_tick)
        last_tick = max(last_tick, concept.last_tick)
        for anchor in concept_anchors:
            kind, _, value = anchor.partition(":")
            if kind == "role":
                roles.add(value)
            elif kind == "goal":
                goals.add(value)
            elif kind == "resource":
                resources.add(value)
            elif kind == "procedure":
                procedures.add(value)
            elif kind == "record":
                records.add(value)
            elif kind == "commitment":
                commitments.add(value)
        for owner in window.owner_rows:
            if owner.owner.owner_id != owner_id:
                continue
            for identity in owner.identities:
                if identity.organization_id == concept.organization_id:
                    if identity.label_token:
                        identity_tokens.add(identity.label_token)
    known_members = set(members)
    for owner in window.owner_rows:
        for role in owner.roles:
            for occupant in role.occupant_ids:
                if occupant not in known_members:
                    members.add(occupant)
    claims = _member_claims(window, members)
    disputed = any(
        claim.status is OrganizationMembershipStatus.DISPUTED for claim in claims
    )
    temporary = any(
        claim.temporal_scope is OrganizationTemporalScope.TEMPORARY for claim in claims
    )
    all_dissolved = statuses and all(
        status in {"dissolved", "retired"} for status in statuses
    )
    self_identified = any(token for token in identity_tokens) or any(
        claim.status is OrganizationMembershipStatus.EXPLICIT for claim in claims
    )
    if all_dissolved:
        status = OrganizationCandidateStatus.DISSOLVED
    elif disputed:
        status = OrganizationCandidateStatus.DISPUTED
    elif temporary:
        status = OrganizationCandidateStatus.TEMPORARY
    elif not self_identified and not anchors:
        status = OrganizationCandidateStatus.FRAGMENTED
    elif "recognized" in statuses:
        status = OrganizationCandidateStatus.RECOGNIZED
    else:
        status = OrganizationCandidateStatus.PARTIAL
    scope = (
        OrganizationTemporalScope.TEMPORARY
        if temporary
        else (
            OrganizationTemporalScope.ONGOING
            if any(
                claim.temporal_scope is OrganizationTemporalScope.ONGOING
                for claim in claims
            )
            else OrganizationTemporalScope.UNKNOWN
        )
    )
    return OrganizationCandidate(
        candidate_key=_candidate_key(window.window_index, members, anchors),
        window_index=window.window_index,
        member_ids=tuple(sorted(members)),
        member_claims=claims,
        role_anchor_ids=tuple(sorted(roles)),
        goal_anchor_ids=tuple(sorted(goals)),
        resource_anchor_ids=tuple(sorted(resources)),
        procedure_anchor_ids=tuple(sorted(procedures)),
        record_anchor_ids=tuple(sorted(records)),
        commitment_ids=tuple(sorted(commitments)),
        identity_tokens=tuple(sorted(identity_tokens)),
        status=status,
        temporal_scope=scope,
        self_identified=self_identified,
        owner_ids=tuple(sorted(owners)),
        first_tick=first_tick,
        last_tick=last_tick,
    )


def detect_organization_candidates(
    windows: Sequence[OrganizationWindowEvidence],
    *,
    known_person_ids: Sequence[str] = (),
) -> OrganizationDetectionResult:
    """Compose overlapping cross-owner candidates from windowed evidence."""

    known = set(known_person_ids)
    candidates: list[OrganizationCandidate] = []
    window_results: list[OrganizationWindowResult] = []
    lane_presence: dict[str, bool] = dict.fromkeys(ANCHOR_FAMILIES, False)
    observed_lanes = 0
    for window in windows:
        contributions = _contributions(window)
        if known:
            unknown = {
                member
                for _, _, members, _ in contributions
                for member in members
                if member not in known
            }
            if unknown:
                raise OrganizationAnalysisError("organization_unknown_person")
        union = _UnionFind(len(contributions))
        for left in range(len(contributions)):
            for right in range(left + 1, len(contributions)):
                left_members = contributions[left][2]
                right_members = contributions[right][2]
                shared_anchor = bool(contributions[left][3] & contributions[right][3])
                if _jaccard(left_members, right_members) >= 0.5 or shared_anchor:
                    union.union(left, right)
        groups: dict[int, list[int]] = {}
        for index in range(len(contributions)):
            groups.setdefault(union.find(index), []).append(index)
        keys: list[str] = []
        for indices in sorted(groups.values()):
            candidate = _candidate_from_group(window, indices, contributions)
            candidates.append(candidate)
            keys.append(candidate.candidate_key)
        if len(keys) > MAX_WINDOW_CANDIDATES:
            raise OrganizationAnalysisError("organization_detection_empty")
        for family, present in window.lane_presence:
            if present:
                lane_presence[family] = True
        observed_lanes = sum(1 for value in lane_presence.values() if value)
        window_results.append(
            OrganizationWindowResult(
                window_index=window.window_index,
                start_tick=window.start_tick,
                end_tick=window.end_tick,
                candidate_keys=tuple(sorted(keys)),
                lane_presence=window.lane_presence,
            )
        )
    counts: dict[str, int] = {}
    for candidate in candidates:
        for member in candidate.member_ids:
            counts[member] = counts.get(member, 0) + 1
    overlap = tuple(sorted(member for member, count in counts.items() if count > 1))
    enriched: list[OrganizationCandidate] = []
    for candidate in candidates:
        overlap_ids = tuple(
            sorted(member for member in candidate.member_ids if member in overlap)
        )
        enriched.append(
            OrganizationCandidate(
                candidate_key=candidate.candidate_key,
                window_index=candidate.window_index,
                member_ids=candidate.member_ids,
                member_claims=candidate.member_claims,
                role_anchor_ids=candidate.role_anchor_ids,
                goal_anchor_ids=candidate.goal_anchor_ids,
                resource_anchor_ids=candidate.resource_anchor_ids,
                procedure_anchor_ids=candidate.procedure_anchor_ids,
                record_anchor_ids=candidate.record_anchor_ids,
                commitment_ids=candidate.commitment_ids,
                identity_tokens=candidate.identity_tokens,
                status=candidate.status,
                temporal_scope=candidate.temporal_scope,
                self_identified=candidate.self_identified,
                owner_ids=candidate.owner_ids,
                first_tick=candidate.first_tick,
                last_tick=candidate.last_tick,
                overlap_member_ids=overlap_ids,
            )
        )
    enriched.sort(
        key=lambda item: (
            item.window_index,
            item.first_tick,
            item.member_ids,
            item.anchor_signature,
        )
    )
    _LOG.debug(
        "organization_detection windows=%s candidates=%s overlap=%s",
        len(window_results),
        len(enriched),
        len(overlap),
    )
    return OrganizationDetectionResult(
        windows=tuple(window_results),
        candidates=tuple(enriched),
        overlap_person_ids=overlap,
        lane_presence=tuple(sorted(lane_presence.items())),
        coverage=OrganizationCoverage.of(observed_lanes, len(ANCHOR_FAMILIES)),
    )
