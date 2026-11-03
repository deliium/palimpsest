"""Deterministic detached formal-rule identity assignment."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Final

from analysis.formal_rule_contract import (
    FORMAL_RULE_IDENTITY_POLICY_VERSION,
    FormalRuleCandidateStatus,
    FormalRuleCoverage,
    FormalRuleLineageKind,
    candidate_key,
    derive_formal_rule_id,
)
from analysis.formal_rule_detection import FormalRuleCandidate
from analysis.formal_rule_evidence import FormalRuleWindowEvidence
from analysis.formal_rules import FormalRuleRow

__all__ = [
    "FormalRuleIdentityAssignment",
    "FormalRuleRecord",
    "FormalRuleTransition",
    "FormalRuleWindowSnapshot",
    "assign_formal_rule_identities",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rule_identity")

_CONTINUATION_JACCARD: Final[float] = 0.5
_SPLIT_CONTAINMENT: Final[float] = 0.4
_MERGE_ABSORPTION: Final[float] = 0.5


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _containment(left: frozenset[str], right: frozenset[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _creation_id(
    owner_ids: tuple[str, ...],
    scope_digest: str,
    action_token: str,
    constraint_kind: str,
    first_tick: int,
) -> str:
    material = "\x1f".join(
        (
            FORMAL_RULE_IDENTITY_POLICY_VERSION,
            *sorted(owner_ids),
            scope_digest,
            action_token,
            constraint_kind,
            str(first_tick),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return derive_formal_rule_id(digest)


@dataclass(frozen=True, slots=True)
class FormalRuleRecord:
    candidate_id: str
    candidate_key: str
    owner_ids: tuple[str, ...]
    scope_kind: str
    scope_digest: str
    action_token: str
    constraint_kind: str
    authority_kind: str
    rule_ids: tuple[str, ...]
    first_tick: int
    last_tick: int
    status: FormalRuleCandidateStatus
    coverage: FormalRuleCoverage

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "owner_ids", tuple(sorted(set(self.owner_ids)))
        )
        object.__setattr__(self, "rule_ids", tuple(sorted(set(self.rule_ids))))


@dataclass(frozen=True, slots=True)
class FormalRuleTransition:
    kind: FormalRuleLineageKind
    source_candidate_id: str | None
    target_candidate_id: str
    tick: int
    jaccard: float
    containment: float


@dataclass(frozen=True, slots=True)
class FormalRuleWindowSnapshot:
    start_tick: int
    end_tick: int
    record_ids: tuple[str, ...]
    coverage: FormalRuleCoverage
    determinism_digest: str


@dataclass(frozen=True, slots=True)
class FormalRuleIdentityAssignment:
    records: tuple[FormalRuleRecord, ...] = ()
    transitions: tuple[FormalRuleTransition, ...] = ()
    windows: tuple[FormalRuleWindowSnapshot, ...] = ()
    determinism_digest: str = ""


def _window_candidates(
    window: FormalRuleWindowEvidence,
) -> tuple[FormalRuleCandidate, ...]:
    groups: dict[tuple[str, ...], list[FormalRuleRow]] = {}
    for row in window.rules:
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
        status = (
            FormalRuleCandidateStatus.CONTESTED
            if any(row.status == "contested" for row in ordered)
            else FormalRuleCandidateStatus.RECOGNIZED
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
                members=(),
                first_tick=window.start_tick,
                last_tick=window.end_tick,
                status=status,
                coverage=window.coverage,
            )
        )
    return tuple(candidates)


def _apply_split_merge(
    assigned: list[FormalRuleRecord],
    active: tuple[FormalRuleRecord, ...],
    tick: int,
    transitions: list[FormalRuleTransition],
) -> list[FormalRuleRecord]:
    splits: dict[str, list[int]] = {}
    merges: dict[int, list[str]] = {}
    for index, candidate in enumerate(assigned):
        for prior in active:
            overlap = _containment(
                frozenset(prior.owner_ids), frozenset(candidate.owner_ids)
            )
            if overlap >= _SPLIT_CONTAINMENT:
                splits.setdefault(prior.candidate_id, []).append(index)
                merges.setdefault(index, []).append(prior.candidate_id)
    replacements: dict[int, str] = {}
    for prior_id, indices in splits.items():
        if len(indices) < 2:
            continue
        for index in indices:
            if index in replacements:
                continue
            candidate = assigned[index]
            identifier = _creation_id(
                candidate.owner_ids,
                candidate.scope_digest,
                candidate.action_token,
                candidate.constraint_kind,
                candidate.first_tick,
            )
            replacements[index] = identifier
            transitions.append(
                FormalRuleTransition(
                    kind=FormalRuleLineageKind.SPLIT,
                    source_candidate_id=prior_id,
                    target_candidate_id=identifier,
                    tick=tick,
                    jaccard=0.0,
                    containment=_SPLIT_CONTAINMENT,
                )
            )
    for index, prior_ids in merges.items():
        if len(prior_ids) < 2:
            continue
        candidate = assigned[index]
        identifier = replacements.get(index) or _creation_id(
            candidate.owner_ids,
            candidate.scope_digest,
            candidate.action_token,
            candidate.constraint_kind,
            candidate.first_tick,
        )
        replacements[index] = identifier
        for prior_id in prior_ids:
            transitions.append(
                FormalRuleTransition(
                    kind=FormalRuleLineageKind.MERGE,
                    source_candidate_id=prior_id,
                    target_candidate_id=identifier,
                    tick=tick,
                    jaccard=0.0,
                    containment=_MERGE_ABSORPTION,
                )
            )
    if not replacements:
        return assigned
    return [
        replace(record, candidate_id=replacements.get(index, record.candidate_id))
        for index, record in enumerate(assigned)
    ]


def _record(
    candidate: FormalRuleCandidate,
    candidate_id: str,
) -> FormalRuleRecord:
    return FormalRuleRecord(
        candidate_id=candidate_id,
        candidate_key=candidate.candidate_key,
        owner_ids=candidate.owner_ids,
        scope_kind=candidate.scope_kind,
        scope_digest=candidate.scope_digest,
        action_token=candidate.action_token,
        constraint_kind=candidate.constraint_kind,
        authority_kind=candidate.authority_kind,
        rule_ids=candidate.rule_ids,
        first_tick=candidate.first_tick,
        last_tick=candidate.last_tick,
        status=candidate.status,
        coverage=candidate.coverage,
    )


def assign_formal_rule_identities(
    windows: tuple[FormalRuleWindowEvidence, ...],
) -> FormalRuleIdentityAssignment:
    """Assign stable ``frule-`` identities across forward tick windows."""

    records: list[FormalRuleRecord] = []
    transitions: list[FormalRuleTransition] = []
    snapshots: list[FormalRuleWindowSnapshot] = []
    active: tuple[FormalRuleRecord, ...] = ()
    seen_ids: set[str] = set()
    for window in windows:
        current = _window_candidates(window)
        if not current:
            snapshots.append(
                FormalRuleWindowSnapshot(
                    start_tick=window.start_tick,
                    end_tick=window.end_tick,
                    record_ids=(),
                    coverage=window.coverage,
                    determinism_digest=hashlib.sha256(b"").hexdigest(),
                )
            )
            continue
        assigned: list[FormalRuleRecord] = []
        if not active:
            for candidate in current:
                identifier = _creation_id(
                    candidate.owner_ids,
                    candidate.scope_digest,
                    candidate.action_token,
                    candidate.constraint_kind,
                    candidate.first_tick,
                )
                assigned.append(_record(candidate, identifier))
                transitions.append(
                    FormalRuleTransition(
                        kind=FormalRuleLineageKind.EMERGED,
                        source_candidate_id=None,
                        target_candidate_id=identifier,
                        tick=window.start_tick,
                        jaccard=0.0,
                        containment=0.0,
                    )
                )
        else:
            prior_by_key = {
                (
                    record.scope_digest,
                    record.action_token,
                    record.constraint_kind,
                    record.authority_kind,
                ): record
                for record in active
            }
            matched_priors: set[str] = set()
            for candidate in current:
                key = (
                    candidate.scope_digest,
                    candidate.action_token,
                    candidate.constraint_kind,
                    candidate.authority_kind,
                )
                prior = prior_by_key.get(key)
                if prior is None:
                    identifier = _creation_id(
                        candidate.owner_ids,
                        candidate.scope_digest,
                        candidate.action_token,
                        candidate.constraint_kind,
                        candidate.first_tick,
                    )
                    assigned.append(_record(candidate, identifier))
                    transitions.append(
                        FormalRuleTransition(
                            kind=FormalRuleLineageKind.EMERGED,
                            source_candidate_id=None,
                            target_candidate_id=identifier,
                            tick=window.start_tick,
                            jaccard=0.0,
                            containment=0.0,
                        )
                    )
                    continue
                jaccard = _jaccard(
                    frozenset(prior.owner_ids), frozenset(candidate.owner_ids)
                )
                containment = _containment(
                    frozenset(prior.owner_ids), frozenset(candidate.owner_ids)
                )
                if jaccard >= _CONTINUATION_JACCARD:
                    matched_priors.add(prior.candidate_id)
                    assigned.append(
                        _record(
                            candidate,
                            prior.candidate_id,
                        )
                    )
                    transitions.append(
                        FormalRuleTransition(
                            kind=FormalRuleLineageKind.CONTINUED,
                            source_candidate_id=prior.candidate_id,
                            target_candidate_id=prior.candidate_id,
                            tick=window.start_tick,
                            jaccard=jaccard,
                            containment=containment,
                        )
                    )
                else:
                    identifier = _creation_id(
                        candidate.owner_ids,
                        candidate.scope_digest,
                        candidate.action_token,
                        candidate.constraint_kind,
                        candidate.first_tick,
                    )
                    assigned.append(_record(candidate, identifier))
                    transitions.append(
                        FormalRuleTransition(
                            kind=FormalRuleLineageKind.EMERGED,
                            source_candidate_id=None,
                            target_candidate_id=identifier,
                            tick=window.start_tick,
                            jaccard=jaccard,
                            containment=containment,
                        )
                    )
            for prior in active:
                if prior.candidate_id in matched_priors:
                    continue
                transitions.append(
                    FormalRuleTransition(
                        kind=FormalRuleLineageKind.DISSOLVED,
                        source_candidate_id=prior.candidate_id,
                        target_candidate_id=prior.candidate_id,
                        tick=window.start_tick,
                        jaccard=0.0,
                        containment=0.0,
                    )
                )
        assigned = _apply_split_merge(
            assigned, active, window.start_tick, transitions
        )
        window_ids = tuple(sorted({record.candidate_id for record in assigned}))
        deduped: list[FormalRuleRecord] = []
        for record in assigned:
            if record.candidate_id in seen_ids:
                continue
            seen_ids.add(record.candidate_id)
            deduped.append(record)
        records.extend(deduped)
        active = tuple(deduped)
        snapshots.append(
            FormalRuleWindowSnapshot(
                start_tick=window.start_tick,
                end_tick=window.end_tick,
                record_ids=window_ids,
                coverage=window.coverage,
                determinism_digest=hashlib.sha256(
                    "\x1f".join(window_ids).encode("utf-8")
                ).hexdigest(),
            )
        )
    digest = hashlib.sha256(
        "\x1f".join(
            sorted(
                f"{record.candidate_id}:{record.candidate_key}:{record.first_tick}"
                for record in records
            )
        ).encode("utf-8")
    ).hexdigest()
    _LOG.info(
        "formal_rule_identity records=%s transitions=%s",
        len(records),
        len(transitions),
    )
    return FormalRuleIdentityAssignment(
        records=tuple(records),
        transitions=tuple(transitions),
        windows=tuple(snapshots),
        determinism_digest=digest,
    )
