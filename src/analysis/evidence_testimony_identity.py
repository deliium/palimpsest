"""Forward-only evidence candidate identity and lineage.

Identity is creation-evidence based and deterministic. Lineage is acyclic,
monotone in window index, and never reuses another context's identity.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.evidence_testimony_contract import (
    EVIDENCE_IDENTITY_VERSION,
    EvidenceAnalysisError,
    EvidenceLineageKind,
    evidence_edge_id,
    require_candidate_id,
)
from analysis.evidence_testimony_detection import EvidenceCandidate

__all__ = [
    "EVIDENCE_IDENTITY_MERGE_THRESHOLD",
    "EVIDENCE_IDENTITY_SPLIT_THRESHOLD",
    "EvidenceIdentityAssignment",
    "EvidenceRecord",
    "EvidenceTransition",
    "EvidenceWindowSnapshot",
    "assign_evidence_identities",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.evidence_testimony_identity")

EVIDENCE_IDENTITY_SPLIT_THRESHOLD: Final[float] = 0.4
EVIDENCE_IDENTITY_MERGE_THRESHOLD: Final[float] = 0.4


@dataclass(frozen=True, slots=True)
class EvidenceWindowSnapshot:
    """One window's candidates, already detected and sorted."""

    window_index: int
    candidates: tuple[EvidenceCandidate, ...] = ()

    def __post_init__(self) -> None:
        if type(self.window_index) is not int or self.window_index < 0:
            raise EvidenceAnalysisError("evidence_testimony_invalid_input")
        if isinstance(self.candidates, (str, bytes)) or not isinstance(
            self.candidates, (tuple, list)
        ):
            raise EvidenceAnalysisError("evidence_testimony_invalid_input")
        object.__setattr__(self, "candidates", tuple(self.candidates))


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One forward-only candidate record across windows."""

    candidate_id: str
    subject_token: str
    source_kind_family: str
    first_window: int
    last_window: int

    def __post_init__(self) -> None:
        require_candidate_id(self.candidate_id)
        if self.last_window < self.first_window:
            raise EvidenceAnalysisError("evidence_testimony_lineage_invalid")


@dataclass(frozen=True, slots=True)
class EvidenceTransition:
    """One forward-only lineage edge."""

    edge_id: str
    kind: EvidenceLineageKind
    source_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    window_index: int

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceLineageKind):
            raise EvidenceAnalysisError("evidence_testimony_lineage_invalid")
        if type(self.window_index) is not int or self.window_index < 0:
            raise EvidenceAnalysisError("evidence_testimony_lineage_invalid")
        if not self.source_ids and not self.target_ids:
            raise EvidenceAnalysisError("evidence_testimony_lineage_invalid")


@dataclass(frozen=True, slots=True)
class EvidenceIdentityAssignment:
    """Complete identity assignment over ordered windows."""

    identity_version: str = EVIDENCE_IDENTITY_VERSION
    records: tuple[EvidenceRecord, ...] = ()
    transitions: tuple[EvidenceTransition, ...] = ()


def _transition(
    kind: EvidenceLineageKind,
    source_ids: Sequence[str],
    target_ids: Sequence[str],
    window_index: int,
) -> EvidenceTransition:
    sources = tuple(sorted(source_ids))
    targets = tuple(sorted(target_ids))
    edge = evidence_edge_id(
        ",".join(sources), ",".join(targets), kind.value, window_index
    )
    return EvidenceTransition(
        edge_id=edge,
        kind=kind,
        source_ids=sources,
        target_ids=targets,
        window_index=window_index,
    )


def assign_evidence_identities(
    snapshots: Sequence[EvidenceWindowSnapshot],
) -> EvidenceIdentityAssignment:
    """Assign continued/transformed/emerged/dissolved/split/merge transitions."""

    if isinstance(snapshots, (str, bytes)) or not isinstance(snapshots, Sequence):
        raise EvidenceAnalysisError("evidence_testimony_invalid_input")
    windows = sorted(snapshots, key=lambda snapshot: snapshot.window_index)
    if len({snapshot.window_index for snapshot in windows}) != len(windows):
        raise EvidenceAnalysisError("evidence_testimony_identity_conflict")

    records: dict[str, EvidenceRecord] = {}
    transitions: list[EvidenceTransition] = []
    active: dict[str, EvidenceCandidate] = {}

    for snapshot in windows:
        new_by_subject: dict[str, list[EvidenceCandidate]] = {}
        for candidate in sorted(
            snapshot.candidates, key=lambda item: item.candidate_id
        ):
            new_by_subject.setdefault(candidate.subject_token, []).append(candidate)
        previous_by_subject: dict[str, list[EvidenceCandidate]] = {}
        for candidate in active.values():
            previous_by_subject.setdefault(candidate.subject_token, []).append(
                candidate
            )

        consumed_new: set[str] = set()
        consumed_old: set[str] = set()
        for subject in sorted(set(new_by_subject) | set(previous_by_subject)):
            old = sorted(
                previous_by_subject.get(subject, []),
                key=lambda item: item.candidate_id,
            )
            new = sorted(
                new_by_subject.get(subject, []),
                key=lambda item: item.candidate_id,
            )
            if not old and new:
                transitions.append(
                    _transition(
                        EvidenceLineageKind.EMERGED,
                        (),
                        [candidate.candidate_id for candidate in new],
                        snapshot.window_index,
                    )
                )
                consumed_new.update(candidate.candidate_id for candidate in new)
                continue
            if old and not new:
                transitions.append(
                    _transition(
                        EvidenceLineageKind.DISSOLVED,
                        [candidate.candidate_id for candidate in old],
                        (),
                        snapshot.window_index,
                    )
                )
                consumed_old.update(candidate.candidate_id for candidate in old)
                continue
            old_ids = {candidate.candidate_id for candidate in old}
            new_ids = {candidate.candidate_id for candidate in new}
            if len(old) == 1 and len(new) > 1:
                transitions.append(
                    _transition(
                        EvidenceLineageKind.SPLIT,
                        tuple(old_ids),
                        tuple(new_ids),
                        snapshot.window_index,
                    )
                )
                consumed_old.update(old_ids)
                consumed_new.update(new_ids)
            elif len(old) > 1 and len(new) == 1:
                transitions.append(
                    _transition(
                        EvidenceLineageKind.MERGE,
                        tuple(old_ids),
                        tuple(new_ids),
                        snapshot.window_index,
                    )
                )
                consumed_old.update(old_ids)
                consumed_new.update(new_ids)
            elif len(old) == 1 and len(new) == 1:
                old_id = next(iter(old_ids))
                new_id = next(iter(new_ids))
                kind = (
                    EvidenceLineageKind.CONTINUED
                    if old_id == new_id
                    else EvidenceLineageKind.TRANSFORMED
                )
                transitions.append(
                    _transition(kind, (old_id,), (new_id,), snapshot.window_index)
                )
                consumed_old.add(old_id)
                consumed_new.add(new_id)
            else:
                # Many-to-many changes are deterministic pairwise edges.
                for old_candidate in old:
                    if old_candidate.candidate_id in consumed_old:
                        continue
                    transitions.append(
                        _transition(
                            EvidenceLineageKind.DISSOLVED,
                            (old_candidate.candidate_id,),
                            (),
                            snapshot.window_index,
                        )
                    )
                    consumed_old.add(old_candidate.candidate_id)
                for new_candidate in new:
                    transitions.append(
                        _transition(
                            EvidenceLineageKind.EMERGED,
                            (),
                            (new_candidate.candidate_id,),
                            snapshot.window_index,
                        )
                    )
                    consumed_new.add(new_candidate.candidate_id)

        for candidate in snapshot.candidates:
            if candidate.candidate_id in consumed_new:
                continue
            transitions.append(
                _transition(
                    EvidenceLineageKind.EMERGED,
                    (),
                    (candidate.candidate_id,),
                    snapshot.window_index,
                )
            )
            consumed_new.add(candidate.candidate_id)
        for candidate in active.values():
            if candidate.candidate_id in consumed_old:
                continue
            if candidate.candidate_id in {
                item.candidate_id for item in snapshot.candidates
            }:
                continue
            transitions.append(
                _transition(
                    EvidenceLineageKind.DISSOLVED,
                    (candidate.candidate_id,),
                    (),
                    snapshot.window_index,
                )
            )

        for candidate in snapshot.candidates:
            existing = records.get(candidate.candidate_id)
            if existing is None:
                records[candidate.candidate_id] = EvidenceRecord(
                    candidate_id=candidate.candidate_id,
                    subject_token=candidate.subject_token,
                    source_kind_family=candidate.source_kind_family,
                    first_window=snapshot.window_index,
                    last_window=snapshot.window_index,
                )
            else:
                records[candidate.candidate_id] = EvidenceRecord(
                    candidate_id=existing.candidate_id,
                    subject_token=existing.subject_token,
                    source_kind_family=existing.source_kind_family,
                    first_window=existing.first_window,
                    last_window=snapshot.window_index,
                )
        active = {
            candidate.candidate_id: candidate for candidate in snapshot.candidates
        }

    transitions.sort(
        key=lambda edge: (
            edge.window_index,
            edge.kind.value,
            edge.source_ids,
            edge.target_ids,
        )
    )
    _LOG.debug(
        "evidence_identity_assigned records=%s transitions=%s",
        len(records),
        len(transitions),
    )
    return EvidenceIdentityAssignment(
        records=tuple(records[key] for key in sorted(records)),
        transitions=tuple(transitions),
    )
