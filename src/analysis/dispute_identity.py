"""Deterministic detached dispute identity assignment.

Candidate identities are minted from creation evidence only: the first observed
window's sorted owner and case sets plus the grouping key. A later member, status
change, or kind refinement never changes an identity.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.dispute_contract import (
    DISPUTE_FOREIGN_CANDIDATE_PREFIXES,
    DISPUTE_IDENTITY_POLICY_VERSION,
    DisputeAnalysisError,
    DisputeCandidateStatus,
    DisputeCoverage,
    DisputeLineageKind,
    derive_dispute_candidate_id,
    require_dispute_candidate_id,
)
from analysis.dispute_detection import DisputeCandidate

__all__ = [
    "DisputeIdentityAssignment",
    "DisputeRecord",
    "DisputeTransition",
    "DisputeWindowSnapshot",
    "assign_dispute_identities",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.dispute_identity")

_SPLIT_CONTAINMENT: Final[float] = 0.4
_MERGE_ABSORPTION: Final[float] = 0.4


def _containment(left: frozenset[str], right: frozenset[str]) -> float:
    if not left:
        return 0.0
    return len(left & right) / len(left)


def _fail(code: str = "dispute_invalid_candidate") -> None:
    raise DisputeAnalysisError(code)


def creation_digest(candidate: DisputeCandidate | DisputeRecord) -> str:
    """Return the content-addressed digest of one candidate's creation evidence."""
    material = "\x1f".join(
        (
            DISPUTE_IDENTITY_POLICY_VERSION,
            candidate.subject_token,
            candidate.party_digest,
            *candidate.owner_ids,
            *candidate.case_refs,
            str(candidate.first_tick),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class DisputeRecord:
    """One stable analytical dispute identity across tick windows."""

    candidate_key: str
    candidate_id: str
    creation_digest: str
    kind: str
    subject_token: str
    party_digest: str
    party_ids: tuple[str, ...]
    owner_ids: tuple[str, ...]
    case_refs: tuple[str, ...]
    claim_refs: tuple[str, ...]
    first_tick: int
    last_tick: int
    status: DisputeCandidateStatus
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        require_dispute_candidate_id(self.candidate_id)
        if type(self.creation_digest) is not str or len(self.creation_digest) != 64:
            _fail()
        if derive_dispute_candidate_id(self.creation_digest) != self.candidate_id:
            _fail()
        if self.candidate_id.startswith(DISPUTE_FOREIGN_CANDIDATE_PREFIXES):
            _fail()
        if type(self.status) is not DisputeCandidateStatus:
            _fail()
        if type(self.coverage) is not DisputeCoverage:
            _fail()
        object.__setattr__(self, "party_ids", tuple(sorted(set(self.party_ids))))
        object.__setattr__(self, "owner_ids", tuple(sorted(set(self.owner_ids))))
        object.__setattr__(self, "case_refs", tuple(sorted(set(self.case_refs))))
        object.__setattr__(self, "claim_refs", tuple(sorted(set(self.claim_refs))))
        for name in ("first_tick", "last_tick"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                _fail()
        if self.last_tick < self.first_tick:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeTransition:
    """One forward-only identity transition between windows."""

    source: str | None
    target: str
    kind: DisputeLineageKind
    tick: int

    def __post_init__(self) -> None:
        if self.source is not None:
            require_dispute_candidate_id(self.source)
        require_dispute_candidate_id(self.target)
        if type(self.kind) is not DisputeLineageKind:
            _fail()
        if isinstance(self.tick, bool) or type(self.tick) is not int or self.tick < 0:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeWindowSnapshot:
    """The analytically detected candidates inside one tick window."""

    start_tick: int
    end_tick: int
    candidates: tuple[DisputeCandidate, ...] = ()

    def __post_init__(self) -> None:
        for name in ("start_tick", "end_tick"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                _fail()
        if self.end_tick < self.start_tick:
            _fail()
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True, slots=True)
class DisputeIdentityAssignment:
    """Stable records plus forward-only transitions over ordered windows."""

    candidates: tuple[DisputeRecord, ...] = ()
    transitions: tuple[DisputeTransition, ...] = ()


def _record(
    candidate: DisputeCandidate,
    candidate_id: str,
    digest: str,
) -> DisputeRecord:
    return DisputeRecord(
        candidate_key=candidate.candidate_key,
        candidate_id=candidate_id,
        creation_digest=digest,
        kind=candidate.kind,
        subject_token=candidate.subject_token,
        party_digest=candidate.party_digest,
        party_ids=candidate.party_ids,
        owner_ids=candidate.owner_ids,
        case_refs=candidate.case_refs,
        claim_refs=candidate.claim_refs,
        first_tick=candidate.first_tick,
        last_tick=candidate.last_tick,
        status=candidate.status,
        coverage=candidate.coverage,
    )


def _mint(candidate: DisputeCandidate | DisputeRecord) -> tuple[str, str]:
    digest = creation_digest(candidate)
    return digest, derive_dispute_candidate_id(digest)


def _apply_split_merge(
    assigned: list[DisputeRecord],
    active: tuple[DisputeRecord, ...],
    tick: int,
    transitions: list[DisputeTransition],
) -> list[DisputeRecord]:
    splits: dict[str, list[int]] = {}
    merges: dict[int, list[str]] = {}
    for index, candidate in enumerate(assigned):
        current = frozenset(candidate.party_ids)
        for prior in active:
            if prior.candidate_id == candidate.candidate_id:
                continue
            overlap = _containment(frozenset(prior.party_ids), current)
            if overlap < _SPLIT_CONTAINMENT:
                continue
            splits.setdefault(prior.candidate_id, []).append(index)
            merges.setdefault(index, []).append(prior.candidate_id)
    replacements: dict[int, tuple[str, str]] = {}
    for prior_id in sorted(splits):
        indices = splits[prior_id]
        if len(indices) < 2:
            continue
        for index in indices:
            if index in replacements:
                continue
            digest, identifier = _mint(assigned[index])
            replacements[index] = (digest, identifier)
            transitions.append(
                DisputeTransition(
                    source=prior_id,
                    target=identifier,
                    kind=DisputeLineageKind.SPLIT,
                    tick=tick,
                )
            )
    for index in sorted(merges):
        prior_ids = merges[index]
        if len(prior_ids) < 2:
            continue
        digest, identifier = _mint(assigned[index])
        replacements[index] = (digest, identifier)
        for prior_id in sorted(prior_ids):
            transitions.append(
                DisputeTransition(
                    source=prior_id,
                    target=identifier,
                    kind=DisputeLineageKind.MERGE,
                    tick=tick,
                )
            )
    if not replacements:
        return assigned
    return [
        replace(
            record,
            candidate_id=replacements[index][1],
            creation_digest=replacements[index][0],
        )
        if index in replacements
        else record
        for index, record in enumerate(assigned)
    ]


def assign_dispute_identities(
    windows: Sequence[DisputeWindowSnapshot],
) -> DisputeIdentityAssignment:
    """Assign stable ``disp-`` identities across forward-only tick windows."""

    if isinstance(windows, (str, bytes)) or not isinstance(windows, Sequence):
        raise TypeError("windows must be a Sequence")
    records: list[DisputeRecord] = []
    by_id: dict[str, DisputeRecord] = {}
    transitions: list[DisputeTransition] = []
    active: tuple[DisputeRecord, ...] = ()
    for window in windows:
        if type(window) is not DisputeWindowSnapshot:
            raise TypeError("windows must contain DisputeWindowSnapshot")
        current = tuple(
            sorted(
                window.candidates,
                key=lambda candidate: (
                    candidate.subject_token,
                    candidate.party_digest,
                    candidate.kind,
                ),
            )
        )
        if not current:
            for lost in active:
                transitions.append(
                    DisputeTransition(
                        source=lost.candidate_id,
                        target=lost.candidate_id,
                        kind=DisputeLineageKind.DISSOLVED,
                        tick=window.start_tick,
                    )
                )
            active = ()
            continue
        assigned: list[DisputeRecord] = []
        if not active:
            for candidate in current:
                digest, identifier = _mint(candidate)
                assigned.append(_record(candidate, identifier, digest))
                transitions.append(
                    DisputeTransition(
                        source=None,
                        target=identifier,
                        kind=DisputeLineageKind.EMERGED,
                        tick=window.start_tick,
                    )
                )
        else:
            by_group = {
                (record.subject_token, record.party_digest): record for record in active
            }
            by_party: dict[str, DisputeRecord] = {}
            for record in active:
                by_party.setdefault(record.party_digest, record)
            matched: set[str] = set()
            for candidate in current:
                prior = by_group.get((candidate.subject_token, candidate.party_digest))
                if prior is not None and prior.candidate_id not in matched:
                    assigned.append(
                        _record(
                            candidate,
                            prior.candidate_id,
                            prior.creation_digest,
                        )
                    )
                    transitions.append(
                        DisputeTransition(
                            source=prior.candidate_id,
                            target=prior.candidate_id,
                            kind=DisputeLineageKind.CONTINUED,
                            tick=window.start_tick,
                        )
                    )
                    matched.add(prior.candidate_id)
                    continue
                same_parties = by_party.get(candidate.party_digest)
                if (
                    same_parties is not None
                    and same_parties.candidate_id not in matched
                ):
                    assigned.append(
                        _record(
                            candidate,
                            same_parties.candidate_id,
                            same_parties.creation_digest,
                        )
                    )
                    transitions.append(
                        DisputeTransition(
                            source=same_parties.candidate_id,
                            target=same_parties.candidate_id,
                            kind=DisputeLineageKind.TRANSFORMED,
                            tick=window.start_tick,
                        )
                    )
                    matched.add(same_parties.candidate_id)
                    continue
                digest, identifier = _mint(candidate)
                assigned.append(_record(candidate, identifier, digest))
                transitions.append(
                    DisputeTransition(
                        source=None,
                        target=identifier,
                        kind=DisputeLineageKind.EMERGED,
                        tick=window.start_tick,
                    )
                )
            for prior in active:
                if prior.candidate_id in matched:
                    continue
                transitions.append(
                    DisputeTransition(
                        source=prior.candidate_id,
                        target=prior.candidate_id,
                        kind=DisputeLineageKind.DISSOLVED,
                        tick=window.start_tick,
                    )
                )
        assigned = _apply_split_merge(assigned, active, window.start_tick, transitions)
        window_ids = sorted({record.candidate_id for record in assigned})
        for record in assigned:
            if record.candidate_id in by_id:
                continue
            by_id[record.candidate_id] = record
            records.append(record)
        active = tuple(
            sorted(
                (by_id[identifier] for identifier in window_ids),
                key=lambda record: record.candidate_id,
            )
        )
    _LOG.debug(
        "dispute_identity records=%s transitions=%s",
        len(records),
        len(transitions),
    )
    return DisputeIdentityAssignment(
        candidates=tuple(records),
        transitions=tuple(transitions),
    )
