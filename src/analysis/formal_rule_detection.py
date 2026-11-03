"""Overlap-legal detached formal-rule candidate detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.formal_rule_contract import (
    FormalRuleCandidateStatus,
    FormalRuleCoverage,
    candidate_key,
)
from analysis.formal_rule_evidence import FormalRuleWindowEvidence
from analysis.formal_rules import FormalRuleHarvestRows, FormalRuleRow

__all__ = [
    "FormalRuleCandidate",
    "FormalRuleMemberClaim",
    "detect_formal_rule_candidates",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_detection")


@dataclass(frozen=True, slots=True)
class FormalRuleMemberClaim:
    owner_id: str
    rule_id: str
    system_id: str
    scope_kind: str
    scope_digest: str
    action_token: str
    constraint_kind: str
    authority_kind: str
    stage: str
    tick: int


@dataclass(frozen=True, slots=True)
class FormalRuleCandidate:
    candidate_key: str
    owner_ids: tuple[str, ...]
    scope_kind: str
    scope_digest: str
    action_token: str
    constraint_kind: str
    authority_kind: str
    rule_ids: tuple[str, ...]
    members: tuple[FormalRuleMemberClaim, ...]
    first_tick: int
    last_tick: int
    status: FormalRuleCandidateStatus
    coverage: FormalRuleCoverage


def _row_tick(row: FormalRuleRow, windows: tuple[FormalRuleWindowEvidence, ...]) -> int:
    ticks = [
        window.end_tick
        for window in windows
        if row.rule_id in window.rule_ids
    ]
    return max(ticks) if ticks else 0


def _status(rows: tuple[FormalRuleRow, ...]) -> FormalRuleCandidateStatus:
    if any(row.status == "retired" for row in rows):
        return FormalRuleCandidateStatus.DISSOLVED
    if any(row.status == "contested" or row.recognition == "contested" for row in rows):
        return FormalRuleCandidateStatus.CONTESTED
    if len({row.owner_id for row in rows}) > 1:
        return FormalRuleCandidateStatus.FRAGMENTED
    return FormalRuleCandidateStatus.RECOGNIZED


def detect_formal_rule_candidates(
    rows: FormalRuleHarvestRows,
    windows: tuple[FormalRuleWindowEvidence, ...],
) -> tuple[FormalRuleCandidate, ...]:
    """Detect candidates that may overlap and compete; never merge constraints.

    Grouping is exactly scope digest + action token + constraint + authority, so
    two systems that disagree about the same action remain separate candidates.
    """

    if type(rows) is not FormalRuleHarvestRows:
        raise TypeError("rows must be FormalRuleHarvestRows")
    groups: dict[tuple[str, ...], list[FormalRuleRow]] = {}
    for row in rows.rules:
        key = (
            row.scope_digest,
            row.action_token,
            row.constraint_kind,
            row.authority_kind,
        )
        groups.setdefault(key, []).append(row)
    candidates: list[FormalRuleCandidate] = []
    for group_key, members in sorted(groups.items()):
        ordered = tuple(sorted(members, key=lambda item: item.rule_id))
        first = ordered[0]
        member_claims = tuple(
            FormalRuleMemberClaim(
                owner_id=row.owner_id,
                rule_id=row.rule_id,
                system_id=row.system_id,
                scope_kind=row.scope_kind,
                scope_digest=row.scope_digest,
                action_token=row.action_token,
                constraint_kind=row.constraint_kind,
                authority_kind=row.authority_kind,
                stage=row.stage,
                tick=_row_tick(row, windows),
            )
            for row in ordered
        )
        observed = sum(
            1
            for window in windows
            if any(rule_id in window.rule_ids for rule_id in first_rule_ids(ordered))
        )
        coverage = FormalRuleCoverage(
            observed=observed,
            expected=len(windows),
            partial=observed < len(windows),
        )
        candidates.append(
            FormalRuleCandidate(
                candidate_key=candidate_key(group_key),
                owner_ids=tuple(sorted({row.owner_id for row in ordered})),
                scope_kind=first.scope_kind,
                scope_digest=first.scope_digest,
                action_token=first.action_token,
                constraint_kind=first.constraint_kind,
                authority_kind=first.authority_kind,
                rule_ids=tuple(row.rule_id for row in ordered),
                members=member_claims,
                first_tick=min(item.tick for item in member_claims),
                last_tick=max(item.tick for item in member_claims),
                status=_status(ordered),
                coverage=coverage,
            )
        )
    _LOG.info("formal_rule_candidates count=%s", len(candidates))
    return tuple(candidates)


def first_rule_ids(rows: tuple[FormalRuleRow, ...]) -> tuple[str, ...]:
    return tuple(row.rule_id for row in rows)
