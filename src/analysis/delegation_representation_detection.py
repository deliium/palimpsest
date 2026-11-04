"""Deterministic detached representation candidate detection."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.delegation_representation_contract import (
    REPRESENTATION_STATUSES,
    RepresentationAnalysisError,
    RepresentationCandidateStatus,
    RepresentationCoverage,
    derive_representation_candidate_id,
    representation_candidate_key,
    require_candidate_id,
    require_owner_token,
)
from analysis.delegation_representation_rows import RepresentationHarvestRows

__all__ = [
    "RepresentationCandidate",
    "RepresentationMemberItem",
    "detect_representation_window_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.delegation_representation_detection"
)
_SEPARATOR: Final[str] = "\x1f"


@dataclass(frozen=True, slots=True)
class RepresentationMemberItem:
    owner_token: str
    mandate_id: str
    representative_token: str
    status: str
    support_roots: int
    opposition_roots: int
    start_tick: int

    def __post_init__(self) -> None:
        require_owner_token(self.owner_token)
        if self.status not in REPRESENTATION_STATUSES:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.support_roots) is not int or self.support_roots < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.opposition_roots) is not int or self.opposition_roots < 0:
            raise RepresentationAnalysisError("representation_invalid_row")
        if type(self.start_tick) is not int or self.start_tick < 0:
            raise RepresentationAnalysisError("representation_invalid_row")


@dataclass(frozen=True, slots=True)
class RepresentationCandidate:
    candidate_id: str
    principal_kind: str
    principal_token: str | None
    scope_kind: str
    scope_subject_token: str | None
    owner_tokens: tuple[str, ...]
    representative_tokens: tuple[str, ...]
    mandate_count: int
    status: RepresentationCandidateStatus
    coverage: RepresentationCoverage
    first_tick: int
    last_tick: int
    creation_digest: str

    def __post_init__(self) -> None:
        require_candidate_id(self.candidate_id)
        if not isinstance(self.status, RepresentationCandidateStatus):
            raise RepresentationAnalysisError("representation_invalid_row")
        if not isinstance(self.coverage, RepresentationCoverage):
            raise RepresentationAnalysisError("representation_invalid_row")
        owners = tuple(
            sorted({require_owner_token(item) for item in self.owner_tokens})
        )
        if not owners:
            raise RepresentationAnalysisError("representation_invalid_row")
        object.__setattr__(self, "owner_tokens", owners)
        if type(self.mandate_count) is not int or self.mandate_count < 0:
            raise RepresentationAnalysisError("representation_invalid_row")


def _creation_digest(members: Sequence[RepresentationMemberItem]) -> str:
    material = _SEPARATOR.join(
        sorted(
            f"{member.owner_token}{_SEPARATOR}{member.mandate_id}" for member in members
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _status(
    members: Sequence[RepresentationMemberItem],
) -> RepresentationCandidateStatus:
    statuses = {member.status for member in members}
    if statuses <= {"revoked", "expired", "superseded"}:
        return RepresentationCandidateStatus.DISSOLVED
    if "recognized" in statuses and "contested" in statuses:
        return RepresentationCandidateStatus.CONTESTED
    representatives = {member.representative_token for member in members}
    if len(representatives) >= 2:
        counts = {
            representative: sum(
                1 for member in members if member.representative_token == representative
            )
            for representative in representatives
        }
        if max(counts.values()) * 2 <= len(members):
            return RepresentationCandidateStatus.FRAGMENTED
    if "recognized" in statuses:
        return RepresentationCandidateStatus.RECOGNIZED
    if "claimed" in statuses:
        return RepresentationCandidateStatus.CLAIMED
    return RepresentationCandidateStatus.UNKNOWN


def detect_representation_window_candidates(
    rows: RepresentationHarvestRows,
) -> tuple[RepresentationCandidate, ...]:
    """Group mandate rows into deterministic principal/scope candidates."""

    if type(rows) is not RepresentationHarvestRows:
        raise TypeError("rows must be RepresentationHarvestRows")
    groups: dict[str, list[RepresentationMemberItem]] = {}
    metadata: dict[str, tuple[str, str | None, str, str | None]] = {}
    for row in rows.mandates:
        key = representation_candidate_key(
            row.principal_kind,
            row.principal_token,
            row.scope_kind,
            row.scope_subject_token,
        )
        groups.setdefault(key, []).append(
            RepresentationMemberItem(
                owner_token=row.owner_token,
                mandate_id=row.mandate_id,
                representative_token=row.representative_token,
                status=row.status,
                support_roots=row.support_roots,
                opposition_roots=row.opposition_roots,
                start_tick=row.start_tick,
            )
        )
        metadata[key] = (
            row.principal_kind,
            row.principal_token,
            row.scope_kind,
            row.scope_subject_token,
        )
    candidates: list[RepresentationCandidate] = []
    for key in sorted(groups):
        members = groups[key]
        principal_kind, principal_token, scope_kind, scope_subject = metadata[key]
        creation_digest = _creation_digest(members)
        first_tick = min(member.start_tick for member in members)
        first_owner = sorted(member.owner_token for member in members)[0]
        candidates.append(
            RepresentationCandidate(
                candidate_id=derive_representation_candidate_id(
                    principal_kind,
                    principal_token,
                    scope_kind,
                    scope_subject,
                    first_tick,
                    first_owner,
                ),
                principal_kind=principal_kind,
                principal_token=principal_token,
                scope_kind=scope_kind,
                scope_subject_token=scope_subject,
                owner_tokens=tuple(sorted({member.owner_token for member in members})),
                representative_tokens=tuple(
                    sorted({member.representative_token for member in members})
                ),
                mandate_count=len(members),
                status=_status(members),
                coverage=rows.coverage,
                first_tick=first_tick,
                last_tick=max(
                    row.start_tick
                    for row in rows.mandates
                    if row.mandate_id in {member.mandate_id for member in members}
                ),
                creation_digest=creation_digest,
            )
        )
    candidates.sort(key=lambda candidate: candidate.candidate_id)
    _LOG.debug("representation_candidates_detected count=%s", len(candidates))
    return tuple(candidates)
