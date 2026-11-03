"""Detached dispute candidate detection with disaggregation by party set.

Grouping is exactly ``subject_token`` plus the party-set digest. Opposing claims
increase a disagreement count but are never merged into one truth, and a
different party set is always a separate candidate even for one subject.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.dispute_contract import (
    DisputeAnalysisError,
    DisputeCandidateStatus,
    DisputeCoverage,
    dispute_candidate_key,
)
from analysis.dispute_evidence import DisputeWindowEvidence
from analysis.disputes import (
    DisputeCaseRow,
    DisputeClaimRow,
    DisputeHarvestRows,
)

__all__ = [
    "DisputeCandidate",
    "DisputeMemberClaim",
    "detect_dispute_candidates",
    "detect_dispute_window_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_detection")

_PARTY_SET_NAMESPACE: Final[str] = "dispute-party-set"
_DISAGREEING_POLARITIES: Final[frozenset[str]] = frozenset({"affirm", "deny"})
_DISSOLVED_STATUSES: Final[frozenset[str]] = frozenset(
    {"withdrawn", "expired", "abandoned"}
)


def _fail(code: str = "dispute_invalid_candidate") -> None:
    raise DisputeAnalysisError(code)


def party_set_digest(party_ids: Sequence[str]) -> str:
    """Return the deterministic grouping digest for one party set."""
    parties = sorted({str(party) for party in party_ids})
    material = "\x1f".join((_PARTY_SET_NAMESPACE, *parties))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DisputeMemberClaim:
    """One attributed claim attached to a detached candidate."""

    owner_id: str
    case_ref: str
    claim_ref: str
    claimant_id: str
    respondent_id: str
    role: str
    claim_kind: str
    polarity: str
    subject_token: str
    tick: int


@dataclass(frozen=True, slots=True)
class DisputeCandidate:
    """One analytical cross-owner dispute candidate; never a shared case file."""

    candidate_key: str
    kind: str
    subject_token: str
    party_ids: tuple[str, ...]
    owner_ids: tuple[str, ...]
    case_refs: tuple[str, ...]
    claim_refs: tuple[str, ...]
    status: DisputeCandidateStatus
    first_tick: int
    last_tick: int
    disagreement_count: int
    resolution_count: int
    coverage: DisputeCoverage
    party_digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_key, str) or not self.candidate_key:
            _fail()
        if not isinstance(self.kind, str) or not self.kind:
            _fail()
        if not isinstance(self.subject_token, str) or not self.subject_token:
            _fail()
        if type(self.status) is not DisputeCandidateStatus:
            _fail()
        object.__setattr__(self, "party_ids", tuple(sorted(set(self.party_ids))))
        object.__setattr__(self, "owner_ids", tuple(sorted(set(self.owner_ids))))
        object.__setattr__(self, "case_refs", tuple(sorted(set(self.case_refs))))
        object.__setattr__(self, "claim_refs", tuple(sorted(set(self.claim_refs))))
        if not self.party_digest:
            object.__setattr__(self, "party_digest", party_set_digest(self.party_ids))
        if type(self.coverage) is not DisputeCoverage:
            _fail()
        for name in (
            "first_tick",
            "last_tick",
            "disagreement_count",
            "resolution_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                _fail()
        if self.last_tick < self.first_tick:
            _fail()


def _candidate_kind(cases: Sequence[DisputeCaseRow]) -> str:
    kinds = sorted({row.kind for row in cases})
    narrowed = [kind for kind in kinds if kind != "other"]
    return narrowed[0] if narrowed else "other"


def _candidate_status(
    cases: Sequence[DisputeCaseRow],
    *,
    claim_count: int,
    resolution_count: int,
) -> DisputeCandidateStatus:
    statuses = {row.status for row in cases}
    if "contested" in statuses:
        return DisputeCandidateStatus.CONTESTED
    if statuses and statuses <= {"apparently_resolved"}:
        return DisputeCandidateStatus.APPARENTLY_RESOLVED
    if statuses and statuses <= _DISSOLVED_STATUSES:
        return DisputeCandidateStatus.DISSOLVED
    by_owner: dict[str, set[str]] = {}
    for row in cases:
        by_owner.setdefault(row.owner_id, set()).add(row.status)
    if len(by_owner) > 1 and len(statuses) > 1:
        return DisputeCandidateStatus.FRAGMENTED
    if claim_count or resolution_count:
        return DisputeCandidateStatus.ACTIVE
    return DisputeCandidateStatus.EMERGING


def _disagreement_count(claims: Sequence[DisputeClaimRow]) -> int:
    affirm: Counter[tuple[str, str]] = Counter()
    deny: Counter[tuple[str, str]] = Counter()
    for claim in claims:
        if claim.polarity not in _DISAGREEING_POLARITIES:
            continue
        key = (claim.claim_kind, claim.subject_token)
        if claim.polarity == "affirm":
            affirm[key] += 1
        else:
            deny[key] += 1
    return sum(
        min(affirm[key], deny[key]) for key in sorted(affirm.keys() & deny.keys())
    )


def _coverage_for(
    windows: Sequence[DisputeWindowEvidence],
    cases: Sequence[DisputeCaseRow],
    claims: Sequence[DisputeClaimRow],
) -> DisputeCoverage:
    if not windows:
        return DisputeCoverage(observed=0, expected=0)
    observed = 0
    for window in windows:
        if any(
            row.first_tick <= window.end_tick and row.last_tick >= window.start_tick
            for row in cases
        ) or any(
            row.first_tick <= window.end_tick and row.last_tick >= window.start_tick
            for row in claims
        ):
            observed += 1
    return DisputeCoverage(
        observed=observed,
        expected=len(windows),
        partial=observed < len(windows),
    )


def _build(
    rows: DisputeHarvestRows,
    *,
    cases: Sequence[DisputeCaseRow],
    claims: Sequence[DisputeClaimRow],
    windows: Sequence[DisputeWindowEvidence],
) -> tuple[DisputeCandidate, ...]:
    case_refs = {row.case_ref for row in cases}
    claims_by_case: dict[str, list[DisputeClaimRow]] = {}
    for claim in claims:
        if claim.case_ref not in case_refs:
            raise DisputeAnalysisError("dispute_invalid_candidate")
        claims_by_case.setdefault(claim.case_ref, []).append(claim)
    groups: dict[tuple[str, str], list[DisputeCaseRow]] = {}
    for row in cases:
        key = (row.subject_token, party_set_digest(row.party_ids))
        groups.setdefault(key, []).append(row)
    candidates: list[DisputeCandidate] = []
    seen: set[str] = set()
    for group_key, members in sorted(groups.items()):
        ordered = tuple(sorted(members, key=lambda row: row.case_ref))
        member_refs = tuple(row.case_ref for row in ordered)
        member_claims = tuple(
            sorted(
                (claim for ref in member_refs for claim in claims_by_case.get(ref, ())),
                key=lambda claim: claim.claim_ref,
            )
        )
        resolution_count = sum(
            1 for row in rows.resolutions if row.case_ref in set(member_refs)
        )
        subject_token, party_digest = group_key
        key_material = (
            subject_token,
            party_digest,
            *(f"{row.owner_id}:{row.case_ref}:{row.first_tick}" for row in ordered),
        )
        identifier = dispute_candidate_key(key_material)
        if identifier in seen:
            raise DisputeAnalysisError("dispute_duplicate_id")
        seen.add(identifier)
        first_tick = min(row.first_tick for row in ordered)
        last_tick = max(row.last_tick for row in ordered)
        candidates.append(
            DisputeCandidate(
                candidate_key=identifier,
                kind=_candidate_kind(ordered),
                subject_token=subject_token,
                party_ids=tuple(
                    sorted({party for row in ordered for party in row.party_ids})
                ),
                owner_ids=tuple(
                    sorted(
                        {row.owner_id for row in ordered}
                        | {claim.owner_id for claim in member_claims}
                    )
                ),
                case_refs=member_refs,
                claim_refs=tuple(claim.claim_ref for claim in member_claims),
                status=_candidate_status(
                    ordered,
                    claim_count=len(member_claims),
                    resolution_count=resolution_count,
                ),
                first_tick=first_tick,
                last_tick=last_tick,
                disagreement_count=_disagreement_count(member_claims),
                resolution_count=resolution_count,
                coverage=_coverage_for(windows, ordered, member_claims),
                party_digest=party_digest,
            )
        )
    _LOG.debug("dispute_candidates count=%s", len(candidates))
    return tuple(candidates)


def detect_dispute_candidates(
    rows: DisputeHarvestRows,
    windows: Sequence[DisputeWindowEvidence] = (),
) -> tuple[DisputeCandidate, ...]:
    """Detect candidates grouped by subject token and exact party set."""

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    return _build(
        rows,
        cases=rows.cases,
        claims=rows.claims,
        windows=tuple(windows),
    )


def detect_dispute_window_candidates(
    rows: DisputeHarvestRows,
    window: DisputeWindowEvidence,
) -> tuple[DisputeCandidate, ...]:
    """Detect the candidates present inside one deterministic tick window."""

    if type(rows) is not DisputeHarvestRows:
        raise TypeError("rows must be DisputeHarvestRows")
    if type(window) is not DisputeWindowEvidence:
        raise TypeError("window must be DisputeWindowEvidence")
    cases = tuple(
        row
        for row in rows.cases
        if row.first_tick <= window.end_tick and row.last_tick >= window.start_tick
    )
    claims = tuple(
        row
        for row in rows.claims
        if row.first_tick <= window.end_tick and row.last_tick >= window.start_tick
    )
    claim_case_refs = {claim.case_ref for claim in claims}
    known = {row.case_ref: row for row in cases}
    for row in rows.cases:
        if row.case_ref in claim_case_refs and row.case_ref not in known:
            known[row.case_ref] = row
    cases = tuple(known[ref] for ref in sorted(known))
    case_refs = set(known)
    if any(claim.case_ref not in case_refs for claim in claims):
        raise DisputeAnalysisError("dispute_invalid_candidate")
    built = _build(
        rows,
        cases=cases,
        claims=claims,
        windows=(window,),
    )
    return tuple(
        replace(
            candidate,
            first_tick=window.start_tick,
            last_tick=window.end_tick,
        )
        for candidate in built
    )
