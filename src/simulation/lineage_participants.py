"""Pure teacher/learner/content participant cards from native lineage records.

Captured mentorship records already identify teacher, learner, content and
evidence. This module copies that safe metadata; it never rewrites a capture,
infers teaching from speech, or crosses owner/family identity boundaries.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from simulation.lineage_identity import (
    LineageEvidenceClass,
    LineageEvidenceRef,
    LineageFamily,
    LineageNativeKind,
    LineageNodeRef,
)
from simulation.lineage_models import (
    LineageError,
    LineageNode,
    MentorshipLineageRecord,
)

_LOGGER: Final[logging.Logger] = logging.getLogger(
    "simulation.lineage_participants"
)

ParticipantRole = Literal["teacher", "learner", "both"]
_ROLES: Final[frozenset[str]] = frozenset({"teacher", "learner", "both"})

__all__ = [
    "LineageParticipantCard",
    "ParticipantRole",
    "order_participant_cards",
    "project_participant_card",
]


@dataclass(frozen=True, slots=True)
class LineageParticipantCard:
    """One native mentorship-entry participant view (no content text)."""

    ref: LineageNodeRef
    teacher_id: str
    learner_id: str
    owner_id: str
    lineage_id: str
    root_id: str
    parent_ids: tuple[str, ...]
    content_kind: str
    content_key: str
    hop: int
    acquisition_tick: int
    update_tick: int
    attempt_count: int
    learning_evidence_count: int
    confidence_band: str | None
    mutated: bool
    native_status: str | None
    evidence_refs: tuple[LineageEvidenceRef, ...]
    policy_version: str
    observed_boundary: int
    source_observed_boundary: int
    learning_state: Literal["attempt_only", "learning_evidence"]

    def __post_init__(self) -> None:
        if type(self.ref) is not LineageNodeRef:
            raise ValueError("LineageParticipantCard.ref must be LineageNodeRef")
        if self.learning_state not in {"attempt_only", "learning_evidence"}:
            raise ValueError("LineageParticipantCard.learning_state is closed")
        object.__setattr__(self, "parent_ids", tuple(self.parent_ids))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


def project_participant_card(
    node: LineageNode,
    *,
    agent_id: str,
    role: str = "both",
) -> LineageParticipantCard | None:
    """Return one participant card, or ``None`` for unrelated/absent metadata."""
    if type(node) is not LineageNode:
        raise TypeError("node must be LineageNode")
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError("agent_id must be a non-empty str")
    if role not in _ROLES:
        raise LineageError("invalid_participant_role")
    record = node.mentorship_record
    if record is None:
        return None
    if (
        node.ref.family is not LineageFamily.MENTORSHIP
        or node.ref.native_kind is not LineageNativeKind.MENTORSHIP_ENTRY
        or node.ref.evidence_class is LineageEvidenceClass.OBJECTIVE
    ):
        raise LineageError("invalid_participant_family")
    if (
        node.ref.evidence_class is LineageEvidenceClass.SUBJECTIVE
        and node.ref.identity_owner != record.owner_id
    ):
        raise LineageError("invalid_participant_scope")
    is_teacher = record.teacher_id == agent_id
    is_learner = record.learner_id == agent_id
    if role == "teacher" and not is_teacher:
        return None
    if role == "learner" and not is_learner:
        return None
    if role == "both" and not (is_teacher or is_learner):
        return None
    return _card(node.ref, record)


def _card(
    ref: LineageNodeRef, record: MentorshipLineageRecord
) -> LineageParticipantCard:
    return LineageParticipantCard(
        ref=ref,
        teacher_id=record.teacher_id,
        learner_id=record.learner_id,
        owner_id=record.owner_id,
        lineage_id=record.lineage_id,
        root_id=record.root_id,
        parent_ids=record.parent_ids,
        content_kind=record.content_kind,
        content_key=record.content_key,
        hop=record.hop,
        acquisition_tick=record.acquisition_tick,
        update_tick=record.update_tick,
        attempt_count=record.attempt_count,
        learning_evidence_count=record.learning_evidence_count,
        confidence_band=record.confidence_band,
        mutated=record.mutated,
        native_status=record.native_status,
        evidence_refs=record.evidence_refs,
        policy_version=record.policy_version,
        observed_boundary=record.observed_boundary,
        source_observed_boundary=record.source_observed_boundary,
        learning_state=(
            "learning_evidence"
            if record.learning_evidence_count > 0
            else "attempt_only"
        ),
    )


def order_participant_cards(
    cards: Sequence[LineageParticipantCard],
) -> tuple[LineageParticipantCard, ...]:
    """Disclosed evidence-priority order within retrieved records only.

    Learning evidence descends, attempts descend, acquisition tick ascends,
    then the qualified node key breaks ties. Attempt-only cards naturally trail
    evidence-positive cards and remain identifiable via ``learning_state``.
    """
    if isinstance(cards, (str, bytes, set, frozenset)) or not isinstance(
        cards, Sequence
    ):
        raise TypeError("cards must be an ordered sequence")
    for card in cards:
        if type(card) is not LineageParticipantCard:
            raise TypeError("cards entries must be LineageParticipantCard")
    ordered = tuple(
        sorted(
            cards,
            key=lambda card: (
                -card.learning_evidence_count,
                -card.attempt_count,
                card.acquisition_tick,
                card.ref.key,
            ),
        )
    )
    attempt_only = sum(
        1 for card in ordered if card.learning_state == "attempt_only"
    )
    _LOGGER.debug(
        "participant_cards_ordered card_count=%s attempt_only=%s",
        len(ordered),
        attempt_only,
    )
    return ordered
