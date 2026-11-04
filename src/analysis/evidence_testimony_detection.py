"""Deterministic cross-owner evidence candidate detection.

A candidate groups owner rows about one subject and source family. It never
merges owners' beliefs into one truth and never owns another context's identity.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.evidence_testimony_contract import (
    EvidenceAnalysisError,
    EvidenceCandidateStatus,
    EvidenceCoverage,
    derive_evidence_candidate_id,
    evidence_candidate_key,
    require_candidate_id,
    require_owner_token,
)
from analysis.evidence_testimony_rows import EvidenceHarvestRows

__all__ = [
    "EvidenceCandidate",
    "EvidenceMemberItem",
    "detect_evidence_window_candidates",
    "source_kind_family",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.evidence_testimony_detection")

_SEPARATOR: Final[str] = "\x1f"

_FAMILY_BY_KIND: Final[dict[str, str]] = {
    "witness_testimony": "testimonial",
    "remembered_event": "testimonial",
    "written_record": "documentary",
    "artifact": "documentary",
    "prior_agreement": "agreement",
    "reputation": "reputational",
    "physical_state": "physical",
}


def source_kind_family(source_kind: str) -> str:
    """Return the closed candidate family for one source kind."""

    return _FAMILY_BY_KIND.get(source_kind, "unknown")


@dataclass(frozen=True, slots=True)
class EvidenceMemberItem:
    """One owner's contribution to a candidate. Holds no owner id."""

    owner_token: str
    local_ref: str
    source_kind: str
    interpretation: str
    confidence_band: str
    root_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_token", require_owner_token(self.owner_token))
        if type(self.local_ref) is not str or not self.local_ref:
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        if source_kind_family(self.source_kind) == "unknown" and (
            self.source_kind != "unknown"
        ):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    """One detached analytical evidence candidate. Never a registry entry."""

    candidate_id: str
    subject_token: str
    source_kind_family: str
    owner_tokens: tuple[str, ...]
    item_count: int
    source_count: int
    testimony_count: int
    contradiction_count: int
    status: EvidenceCandidateStatus
    coverage: EvidenceCoverage
    first_tick: int
    last_tick: int
    creation_digest: str

    def __post_init__(self) -> None:
        require_candidate_id(self.candidate_id)
        if not isinstance(self.status, EvidenceCandidateStatus):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        if not isinstance(self.coverage, EvidenceCoverage):
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        owners = tuple(
            sorted({require_owner_token(item) for item in self.owner_tokens})
        )
        if not owners:
            raise EvidenceAnalysisError("evidence_testimony_invalid_row")
        object.__setattr__(self, "owner_tokens", owners)
        for name in (
            "item_count",
            "source_count",
            "testimony_count",
            "contradiction_count",
            "first_tick",
            "last_tick",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise EvidenceAnalysisError("evidence_testimony_invalid_row")


def _creation_digest(members: Sequence[EvidenceMemberItem]) -> str:
    material = _SEPARATOR.join(
        sorted(
            f"{member.owner_token}{_SEPARATOR}{member.local_ref}" for member in members
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _candidate_status(
    members: Sequence[EvidenceMemberItem],
    *,
    contradiction_count: int,
) -> EvidenceCandidateStatus:
    owners = {member.owner_token for member in members}
    if contradiction_count:
        return EvidenceCandidateStatus.CONTESTED
    if len(owners) >= 2:
        roots = {member.root_ref for member in members}
        if roots == {None}:
            return EvidenceCandidateStatus.FRAGMENTED
        if len(roots) == 1 and None not in roots:
            return EvidenceCandidateStatus.FRAGMENTED
        return EvidenceCandidateStatus.CONVERGENT
    if len(owners) == 1:
        return EvidenceCandidateStatus.ISOLATED
    return EvidenceCandidateStatus.UNKNOWN


def detect_evidence_window_candidates(
    rows: EvidenceHarvestRows,
) -> tuple[EvidenceCandidate, ...]:
    """Group harvested rows into deterministic cross-owner candidates."""

    if type(rows) is not EvidenceHarvestRows:
        raise TypeError("rows must be EvidenceHarvestRows")
    groups: dict[str, list[EvidenceMemberItem]] = {}
    members_by_item: dict[str, EvidenceMemberItem] = {}
    for item in rows.items:
        member = EvidenceMemberItem(
            owner_token=item.owner_token,
            local_ref=item.local_id,
            source_kind=item.source_kind,
            interpretation=item.interpretation,
            confidence_band=item.confidence_band,
            root_ref=item.root_ref,
        )
        family = source_kind_family(item.source_kind)
        key = evidence_candidate_key(item.subject_token, family)
        groups.setdefault(key, []).append(member)
        members_by_item[item.local_id] = member

    candidates: list[EvidenceCandidate] = []
    for key in sorted(groups):
        members = groups[key]
        subject = _subject_for(rows, members)
        family = _family_for(members)
        contradictions = sum(
            1
            for row in rows.contradictions
            if row.status != "withdrawn"
            and (row.first_ref in members_by_item or row.second_ref in members_by_item)
        )
        ticks = [
            item.tick
            for item in rows.items
            if item.local_id in {member.local_ref for member in members}
        ]
        creation_digest = _creation_digest(members)
        candidate_id = derive_evidence_candidate_id(subject, family, creation_digest)
        owners = tuple(sorted({member.owner_token for member in members}))
        source_ids = {
            item.anchor_local_id
            for item in rows.items
            if item.local_id in {member.local_ref for member in members}
        }
        candidates.append(
            EvidenceCandidate(
                candidate_id=candidate_id,
                subject_token=subject,
                source_kind_family=family,
                owner_tokens=owners,
                item_count=len(members),
                source_count=len(
                    {item for item in source_ids if item.startswith("evs-")}
                ),
                testimony_count=len(
                    {item for item in source_ids if item.startswith("evw-")}
                ),
                contradiction_count=contradictions,
                status=_candidate_status(members, contradiction_count=contradictions),
                coverage=rows.coverage,
                first_tick=min(ticks) if ticks else 0,
                last_tick=max(ticks) if ticks else 0,
                creation_digest=creation_digest,
            )
        )
    candidates.sort(key=lambda candidate: candidate.candidate_id)
    contested = sum(
        1
        for candidate in candidates
        if candidate.status is EvidenceCandidateStatus.CONTESTED
    )
    _LOG.debug(
        "evidence_candidates_detected count=%s contested=%s",
        len(candidates),
        contested,
    )
    return tuple(candidates)


def _subject_for(
    rows: EvidenceHarvestRows, members: Sequence[EvidenceMemberItem]
) -> str:
    refs = {member.local_ref for member in members}
    for item in rows.items:
        if item.local_id in refs:
            return item.subject_token
    raise EvidenceAnalysisError("evidence_testimony_invalid_row")


def _family_for(members: Sequence[EvidenceMemberItem]) -> str:
    return source_kind_family(members[0].source_kind)
