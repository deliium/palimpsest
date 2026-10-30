"""Stable analytical ``org-`` identities across evidence windows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.organization_contract import (
    CONTINUATION_JACCARD,
    ORGANIZATION_IDENTITY_POLICY_VERSION,
    OrganizationAnalysisError,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    derive_organization_id,
    require_organization_id,
)
from analysis.organization_detection import (
    OrganizationCandidate,
    OrganizationDetectionResult,
)
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "OrganizationIdentityAssignment",
    "OrganizationRecord",
    "OrganizationTransition",
    "OrganizationWindowSnapshot",
    "assign_organization_identities",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organization_identity")


@dataclass(frozen=True, slots=True)
class OrganizationRecord:
    organization_id: str
    creation_tick: int
    first_tick: int
    last_tick: int
    status: OrganizationCandidateStatus
    member_ids: tuple[str, ...]
    anchor_signature: tuple[str, ...]
    window_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "organization_id", require_organization_id(self.organization_id)
        )
        require_exact_nonneg_int("creation_tick", self.creation_tick)
        require_exact_nonneg_int("first_tick", self.first_tick)
        require_exact_nonneg_int("last_tick", self.last_tick)
        if self.last_tick < self.first_tick:
            raise OrganizationAnalysisError("organization_identity_invalid")
        indexes = tuple(self.window_indexes)
        if indexes != tuple(sorted(set(indexes))):
            raise OrganizationAnalysisError("organization_identity_window")
        object.__setattr__(self, "window_indexes", indexes)


@dataclass(frozen=True, slots=True)
class OrganizationTransition:
    from_id: str | None
    to_id: str
    window_index: int
    jaccard: float
    anchor_shared: bool

    def __post_init__(self) -> None:
        if self.from_id is not None:
            require_organization_id(self.from_id)
        require_organization_id(self.to_id)
        require_exact_nonneg_int("window_index", self.window_index)


@dataclass(frozen=True, slots=True)
class OrganizationWindowSnapshot:
    window_index: int
    start_tick: int
    end_tick: int
    candidates: tuple[OrganizationCandidate, ...]
    overlap_person_ids: tuple[str, ...]
    lane_presence: tuple[tuple[str, bool], ...]
    coverage: OrganizationCoverage

    def __post_init__(self) -> None:
        require_exact_nonneg_int("window_index", self.window_index)
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(self.candidates, key=lambda item: item.candidate_key)),
        )


@dataclass(frozen=True, slots=True)
class OrganizationIdentityAssignment:
    policy_version: str
    records: tuple[OrganizationRecord, ...]
    transitions: tuple[OrganizationTransition, ...]
    windows: tuple[OrganizationWindowSnapshot, ...]
    coverage: OrganizationCoverage
    candidate_ids: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def record_for(self, organization_id: str) -> OrganizationRecord | None:
        for record in self.records:
            if record.organization_id == organization_id:
                return record
        return None


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _anchor_kinds(signature: Sequence[str]) -> set[str]:
    return {item.partition(":")[0] for item in signature}


def _shared_anchor_kind(left: Sequence[str], right: Sequence[str]) -> bool:
    return bool(_anchor_kinds(left) & _anchor_kinds(right))


def assign_organization_identities(
    detection: OrganizationDetectionResult,
    *,
    policy_version: str = ORGANIZATION_IDENTITY_POLICY_VERSION,
) -> OrganizationIdentityAssignment:
    """Assign stable analytical ids across ordered detection windows."""

    if type(detection) is not OrganizationDetectionResult:
        raise OrganizationAnalysisError("organization_identity_invalid")
    windows = tuple(detection.windows)
    if [window.window_index for window in windows] != sorted(
        window.window_index for window in windows
    ):
        raise OrganizationAnalysisError("organization_identity_window")

    by_window: dict[int, list[OrganizationCandidate]] = {}
    for candidate in detection.candidates:
        by_window.setdefault(candidate.window_index, []).append(candidate)

    records: dict[str, OrganizationRecord] = {}
    transitions: list[OrganizationTransition] = []
    snapshots: list[OrganizationWindowSnapshot] = []
    candidate_ids: list[tuple[str, str]] = []
    alive: list[OrganizationRecord] = []

    for window in windows:
        candidates = sorted(
            by_window.get(window.window_index, ()),
            key=lambda item: item.candidate_key,
        )
        matches: dict[str, list[OrganizationRecord]] = {}
        for candidate in candidates:
            matches[candidate.candidate_key] = [
                record
                for record in alive
                if _jaccard(set(record.member_ids), set(candidate.member_ids))
                >= CONTINUATION_JACCARD
                and _shared_anchor_kind(
                    record.anchor_signature, candidate.anchor_signature
                )
            ]
        prior_hits: dict[str, int] = {}
        for record in alive:
            hits = sum(
                1
                for candidate in candidates
                if record in matches[candidate.candidate_key]
            )
            prior_hits[record.organization_id] = hits

        new_alive: list[OrganizationRecord] = []
        for candidate in candidates:
            matched = matches[candidate.candidate_key]
            inherit: OrganizationRecord | None = None
            if len(matched) == 1 and prior_hits.get(matched[0].organization_id) == 1:
                inherit = matched[0]
            if inherit is not None:
                organization_id = inherit.organization_id
                jaccard = _jaccard(set(inherit.member_ids), set(candidate.member_ids))
                transition = OrganizationTransition(
                    from_id=inherit.organization_id,
                    to_id=organization_id,
                    window_index=window.window_index,
                    jaccard=jaccard,
                    anchor_shared=(
                        set(inherit.anchor_signature)
                        == set(candidate.anchor_signature)
                    ),
                )
                transitions.append(transition)
            else:
                organization_id = derive_organization_id(
                    creation_tick=candidate.first_tick,
                    founding_member_ids=candidate.member_ids,
                    structural_anchors=candidate.anchor_signature,
                )
                for prior in matched:
                    transitions.append(
                        OrganizationTransition(
                            from_id=prior.organization_id,
                            to_id=organization_id,
                            window_index=window.window_index,
                            jaccard=_jaccard(
                                set(prior.member_ids), set(candidate.member_ids)
                            ),
                            anchor_shared=False,
                        )
                    )
                if not matched:
                    transitions.append(
                        OrganizationTransition(
                            from_id=None,
                            to_id=organization_id,
                            window_index=window.window_index,
                            jaccard=0.0,
                            anchor_shared=False,
                        )
                    )
            existing = records.get(organization_id)
            indexes = (
                tuple(sorted({*existing.window_indexes, window.window_index}))
                if existing is not None
                else (window.window_index,)
            )
            record = OrganizationRecord(
                organization_id=organization_id,
                creation_tick=(
                    existing.creation_tick
                    if existing is not None
                    else candidate.first_tick
                ),
                first_tick=(
                    min(existing.first_tick, candidate.first_tick)
                    if existing is not None
                    else candidate.first_tick
                ),
                last_tick=(
                    max(existing.last_tick, candidate.last_tick)
                    if existing is not None
                    else candidate.last_tick
                ),
                status=candidate.status,
                member_ids=candidate.member_ids,
                anchor_signature=candidate.anchor_signature,
                window_indexes=indexes,
            )
            records[organization_id] = record
            new_alive.append(record)
            candidate_ids.append((candidate.candidate_key, organization_id))
        alive = new_alive
        snapshots.append(
            OrganizationWindowSnapshot(
                window_index=window.window_index,
                start_tick=window.start_tick,
                end_tick=window.end_tick,
                candidates=tuple(candidates),
                overlap_person_ids=tuple(
                    sorted(
                        {
                            member
                            for candidate in candidates
                            for member in candidate.overlap_member_ids
                        }
                    )
                ),
                lane_presence=window.lane_presence,
                coverage=detection.coverage,
            )
        )

    identifiers = [record.organization_id for record in records.values()]
    if len(set(identifiers)) != len(identifiers):
        raise OrganizationAnalysisError("organization_identity_reuse")
    _LOG.info(
        "organization_identity records=%s transitions=%s",
        len(records),
        len(transitions),
    )
    return OrganizationIdentityAssignment(
        policy_version=policy_version,
        records=tuple(sorted(records.values(), key=lambda item: item.organization_id)),
        transitions=tuple(
            sorted(
                transitions,
                key=lambda item: (
                    item.window_index,
                    item.from_id or "",
                    item.to_id,
                ),
            )
        ),
        windows=tuple(snapshots),
        coverage=detection.coverage,
        candidate_ids=tuple(sorted(candidate_ids)),
    )
