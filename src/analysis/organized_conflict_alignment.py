# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Researcher-only interpretation alignment for organized conflict."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.organized_conflict_contract import ConflictAlignment
from analysis.organized_conflict_detection import ConflictEpisodeCandidate

__all__ = [
    "ConflictAlignmentRow",
    "ConflictAnalysisSummary",
    "align_conflict_interpretations",
    "summarize_organized_conflict",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.organized_conflict.alignment")

_ROLE_KIND_CLASSES: Final[dict[str, str]] = {
    "defense": "attack",
    "retreat": "retreat",
    "assistance": "assistance",
    "resource_capture": "custody_capture",
    "route_blocking": "route_denial",
    "structure_attack": "structure_opposition",
}
_KINDS: Final[frozenset[str]] = frozenset(
    {
        "individual_violence",
        "coordinated_conflict",
        "defense",
        "retreat",
        "assistance",
        "resource_capture",
        "route_blocking",
        "structure_attack",
        "persistent_inter_group_conflict",
        "unclear",
    }
)


@dataclass(frozen=True, slots=True)
class ConflictAlignmentRow:
    interpretation_id: str
    owner_token: str
    candidate_id: str
    alignment: ConflictAlignment
    interpretation_kind: str
    candidate_classification: str


@dataclass(frozen=True, slots=True)
class ConflictAnalysisSummary:
    candidate_count: int = 0
    interpretation_count: int = 0
    consistent_count: int = 0
    unresolved_count: int = 0
    inconsistent_count: int = 0
    not_applicable_count: int = 0
    owner_disagreement_count: int = 0

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise TypeError(f"ConflictAnalysisSummary.{name} must be non-negative")


def _match(
    tick: int,
    interpretation: object,
    candidate: ConflictEpisodeCandidate,
) -> ConflictEpisodeCandidate | None:
    if not candidate.start_tick <= tick <= candidate.end_tick:
        return None
    participants = set(getattr(interpretation, "participant_tokens", ()) or ())
    opponents = set(getattr(interpretation, "opponent_tokens", ()) or ())
    if participants or opponents:
        if participants & set(candidate.participant_tokens):
            return candidate
        if opponents & set(candidate.opponent_tokens):
            return candidate
        return None
    return candidate


def _align(kind: str, candidate: ConflictEpisodeCandidate) -> ConflictAlignment:
    if kind == "unclear":
        return ConflictAlignment.UNRESOLVED
    role_class = _ROLE_KIND_CLASSES.get(kind)
    if role_class is not None:
        return (
            ConflictAlignment.CONSISTENT
            if role_class in candidate.event_classes
            else ConflictAlignment.UNRESOLVED
        )
    classification = candidate.classification
    if kind == "individual_violence":
        return (
            ConflictAlignment.CONSISTENT
            if classification == "individual_violence"
            else ConflictAlignment.INCONSISTENT
        )
    if kind == "coordinated_conflict":
        return (
            ConflictAlignment.CONSISTENT
            if classification
            in {"coordinated_conflict", "persistent_inter_group_conflict"}
            else ConflictAlignment.INCONSISTENT
        )
    if kind == "persistent_inter_group_conflict":
        return (
            ConflictAlignment.CONSISTENT
            if classification == "persistent_inter_group_conflict"
            else ConflictAlignment.INCONSISTENT
        )
    return ConflictAlignment.UNRESOLVED


def align_conflict_interpretations(
    interpretations: Sequence[object],
    candidates: Sequence[ConflictEpisodeCandidate],
) -> tuple[ConflictAlignmentRow, ...]:
    """Classify owner interpretations against objective episodes for researchers."""

    rows: list[ConflictAlignmentRow] = []
    for interpretation in interpretations:
        kind = str(getattr(interpretation, "kind", ""))
        if kind not in _KINDS:
            kind = "unclear"
        tick = int(getattr(interpretation, "tick", 0))
        matches = [
            candidate
            for candidate in candidates
            if _match(tick, interpretation, candidate)
        ]
        if not matches:
            alignment = (
                ConflictAlignment.NOT_APPLICABLE
                if not candidates
                else ConflictAlignment.UNRESOLVED
            )
            candidate_id = ""
            classification = ""
        else:
            candidate = sorted(matches, key=lambda row: row.candidate_id)[0]
            alignment = _align(kind, candidate)
            candidate_id = candidate.candidate_id
            classification = candidate.classification
        rows.append(
            ConflictAlignmentRow(
                interpretation_id=str(getattr(interpretation, "interpretation_id", "")),
                owner_token=str(getattr(interpretation, "owner_token", "")),
                candidate_id=candidate_id,
                alignment=alignment,
                interpretation_kind=kind,
                candidate_classification=classification,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.owner_token, row.interpretation_id)))


def summarize_organized_conflict(
    rows: object,
    candidates: Sequence[ConflictEpisodeCandidate],
    alignment: Sequence[ConflictAlignmentRow],
) -> ConflictAnalysisSummary:
    """Return counts and coverage only; never a truth or quality score."""

    interpretations = tuple(getattr(rows, "owner_interpretations", ()) or ())
    kinds_by_candidate: dict[str, set[str]] = {}
    for row in alignment:
        if row.candidate_id:
            kinds_by_candidate.setdefault(row.candidate_id, set()).add(
                row.interpretation_kind
            )
    disagreement = sum(1 for kinds in kinds_by_candidate.values() if len(kinds) > 1)
    return ConflictAnalysisSummary(
        candidate_count=len(candidates),
        interpretation_count=len(interpretations),
        consistent_count=sum(
            1 for row in alignment if row.alignment is ConflictAlignment.CONSISTENT
        ),
        unresolved_count=sum(
            1 for row in alignment if row.alignment is ConflictAlignment.UNRESOLVED
        ),
        inconsistent_count=sum(
            1 for row in alignment if row.alignment is ConflictAlignment.INCONSISTENT
        ),
        not_applicable_count=sum(
            1 for row in alignment if row.alignment is ConflictAlignment.NOT_APPLICABLE
        ),
        owner_disagreement_count=disagreement,
    )
