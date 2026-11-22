"""Bounded ``mb_v1`` medical-belief testimony inside ordinary speech."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, replace
from typing import Any, Final, cast

from agents.cognition.medical_beliefs import (
    MB_RELATION_PREDICATE,
    MB_RELATION_SUBJECT,
    MedicalBeliefLedger,
    MedicalCause,
    MedicalOutlook,
    MedicalPractice,
    latest_outlook,
    practice_support,
    relay_anchor,
    relay_anchor_hop,
    root_for_belief,
)
from world.actions import Talk, Tell
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId
from world.models import LifeStatus
from world.observations import Observation

__all__ = [
    "MB_RELATION_MAX",
    "MedicalBeliefMessage",
    "attach_medical_belief_message",
    "build_medical_belief_talk",
    "encode_medical_belief_message",
    "select_medical_belief_message",
    "select_medical_recipient",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.medical_beliefs_communication"
)

MB_RELATION_MAX: Final[int] = 32
_HOP_MAX: Final[int] = 4
_CAUSE_ORDER: Final[dict[MedicalCause, int]] = {
    cause: index for index, cause in enumerate(MedicalCause)
}
_PRACTICE_ORDER: Final[dict[MedicalPractice, int]] = {
    practice: index for index, practice in enumerate(MedicalPractice)
}


@dataclass(frozen=True, slots=True)
class MedicalBeliefMessage:
    cause: MedicalCause
    practice: MedicalPractice
    outlook: MedicalOutlook
    root: str
    hop: int

    def __post_init__(self) -> None:
        if type(self.cause) is not MedicalCause:
            raise TypeError("cause must be MedicalCause")
        if type(self.practice) is not MedicalPractice:
            raise TypeError("practice must be MedicalPractice")
        if type(self.outlook) is not MedicalOutlook:
            raise TypeError("outlook must be MedicalOutlook")
        if (
            type(self.root) is not str
            or len(self.root) != 32
            or self.root.lower() != self.root
        ):
            raise ValueError("root must be 32 lowercase hex characters")
        if type(self.hop) is not int or not 0 <= self.hop <= _HOP_MAX:
            raise ValueError("hop must be 0..4")


def encode_medical_belief_message(
    message: MedicalBeliefMessage,
) -> CommunicationRelation:
    if type(message) is not MedicalBeliefMessage:
        raise TypeError("message must be MedicalBeliefMessage")
    return CommunicationRelation(
        subject=MB_RELATION_SUBJECT,
        predicate=MB_RELATION_PREDICATE,
        object="|".join(
            (
                message.cause.value,
                message.practice.value,
                message.outlook.value,
                message.root,
                str(message.hop),
            )
        ),
    )


def _has_local_belief(ledger: MedicalBeliefLedger, cause: MedicalCause) -> bool:
    from agents.cognition.medical_beliefs import MedicalBeliefRow

    return any(
        isinstance(row, MedicalBeliefRow) and row.cause is cause
        for row in ledger.rows
    )


def _ranked_pairs(
    ledger: MedicalBeliefLedger,
) -> list[tuple[int, int, int, int, MedicalCause, MedicalPractice]]:
    cause_scores = dict(ledger.cause_scores)
    rows: list[tuple[int, int, int, int, MedicalCause, MedicalPractice]] = []
    for cause in MedicalCause:
        cause_score = cause_scores.get(cause, 0)
        if cause_score <= 0:
            continue
        for practice in MedicalPractice:
            score = practice_support(ledger, cause, practice)
            if score <= 0 and not _has_local_belief(ledger, cause):
                continue
            rows.append(
                (
                    cause_score,
                    score,
                    -_CAUSE_ORDER[cause],
                    -_PRACTICE_ORDER[practice],
                    cause,
                    practice,
                )
            )
    rows.sort(reverse=True)
    return rows


def select_medical_belief_message(
    ledger: MedicalBeliefLedger, *, tick: int
) -> MedicalBeliefMessage | None:
    """Select one strongest relayable or locally rooted belief pair."""
    if type(ledger) is not MedicalBeliefLedger:
        raise TypeError("ledger must be MedicalBeliefLedger")
    if isinstance(tick, bool) or type(tick) is not int or tick < 0:
        raise ValueError("tick must be non-negative")
    for _cause_score, _practice_score, _co, _po, cause, practice in _ranked_pairs(
        ledger
    ):
        root = relay_anchor(ledger, cause, practice)
        hop = relay_anchor_hop(ledger, cause, practice)
        if root is not None and hop is not None and hop < _HOP_MAX:
            return MedicalBeliefMessage(
                cause=cause,
                practice=practice,
                outlook=latest_outlook(ledger, cause, practice),
                root=root,
                hop=hop + 1,
            )
        if _has_local_belief(ledger, cause):
            return MedicalBeliefMessage(
                cause=cause,
                practice=practice,
                outlook=latest_outlook(ledger, cause, practice),
                root=root_for_belief(
                    ledger, tick=tick, cause=cause, practice=practice
                ),
                hop=0,
            )
    return None


def _relations(utterance: object) -> tuple[CommunicationRelation, ...]:
    content = getattr(getattr(utterance, "utterance", utterance), "content", None)
    if content is None:
        return ()
    rows = getattr(content, "relations", ())
    if isinstance(rows, (str, bytes)) or not isinstance(rows, tuple):
        return ()
    return tuple(row for row in rows if type(row) is CommunicationRelation)


def attach_medical_belief_message(
    utterance: object, message: MedicalBeliefMessage | None
) -> object:
    """Attach one ``mb_v1`` relation to an existing addressed Talk/Tell."""
    if message is None:
        return utterance
    if type(message) is not MedicalBeliefMessage:
        raise TypeError("message must be MedicalBeliefMessage")
    if type(utterance) not in {Talk, Tell}:
        raise TypeError("mb_v1 requires Talk or Tell")
    content = getattr(getattr(utterance, "utterance", None), "content", None)
    if content is None:
        return utterance
    relations = tuple(getattr(content, "relations", ()))
    if any(
        getattr(row, "subject", None) == MB_RELATION_SUBJECT for row in relations
    ):
        return utterance
    if len(relations) + 1 > MB_RELATION_MAX:
        _LOG.debug("medical_belief_speech_skipped reason_code=relation_cap")
        return utterance
    relation = encode_medical_belief_message(message)
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(
        cast(Any, utterance).utterance, content=updated_content
    )
    typed = cast(Any, utterance)
    return typed.__class__(
        recipient_id=typed.recipient_id, utterance=updated_utterance
    )


def select_medical_recipient(observation: Observation) -> EntityId | None:
    peers = sorted(
        (
            body
            for body in observation.visible_bodies
            if body.life_status is LifeStatus.ALIVE
        ),
        key=lambda body: body.entity_id.value,
    )
    return None if not peers else peers[0].entity_id


def build_medical_belief_talk(
    observation: Observation,
    ledger: MedicalBeliefLedger,
    *,
    tick: int,
    recipient_id: object,
    message: MedicalBeliefMessage,
) -> Talk | None:
    """Build one ordinary belief-basis Talk, or return None when it cannot fit."""
    if type(observation) is not Observation:
        raise TypeError("observation must be Observation")
    if type(message) is not MedicalBeliefMessage:
        raise TypeError("message must be MedicalBeliefMessage")
    relation = encode_medical_belief_message(message)
    material = "|".join(
        (
            ledger.owner_id.value,
            str(tick),
            message.cause.value,
            message.practice.value,
            message.root,
        )
    )
    communication_id = (
        "comm-mb-"
        + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    )
    utterance = origin_utterance(
        text="medical-beliefs",
        speaker_id=ledger.observer_entity_id,
        communication_id=communication_id,
        relations=(relation,),
    )
    return Talk(recipient_id=recipient_id, utterance=utterance)  # type: ignore[arg-type]
