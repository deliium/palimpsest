"""Bounded ``ev_v1`` evidence and testimony speech inside existing Talk/Tell.

An owner may assert a source, testify, cite a record, claim custody, interpret,
contradict, or retract through one closed ``CommunicationRelation`` atom inside
ordinary ``Talk``/``Tell`` speech. Delivery proves that speech happened; it never
proves truth, authenticity, a witness identity, or a binding finding.

No command, event, observer semantic type, free-text body, or new relation
subject other than ``ev_v1`` is added.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.evidence_testimony import (
    EvidenceContradictionKind,
    EvidenceCustodyRole,
    EvidenceError,
    EvidenceInterpretationKind,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
)
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)

__all__ = [
    "EVIDENCE_COMMUNICATION_POLICY_VERSION",
    "EVIDENCE_CONFIDENCE_BANDS",
    "EVIDENCE_FRAME_FIELD_COUNT",
    "EVIDENCE_FRAME_SUBJECT",
    "EVIDENCE_FRAME_TERMS_MAX",
    "EVIDENCE_FRAME_TOKEN_MAX",
    "EVIDENCE_PREDICATES",
    "EvidenceAct",
    "EvidenceFrame",
    "encode_evidence_frame",
    "evidence_communicate_utterance",
    "evidence_frame_party_matches",
    "evidence_frame_relation",
    "parse_evidence_frame",
    "parse_evidence_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.evidence_testimony_communication"
)

EVIDENCE_FRAME_SUBJECT: Final[str] = "ev_v1"
EVIDENCE_COMMUNICATION_POLICY_VERSION: Final[str] = "evidence-communication.v1"
EVIDENCE_FRAME_FIELD_COUNT: Final[int] = 17
EVIDENCE_FRAME_TOKEN_MAX: Final[int] = 128
EVIDENCE_FRAME_TERMS_MAX: Final[int] = 4
EVIDENCE_FRAME_MAX_CHARS: Final[int] = 256

EVIDENCE_CONFIDENCE_BANDS: Final[Mapping[str, float]] = MappingProxyType(
    {"low": 0.25, "mid": 0.55, "high": 0.85}
)

_NONE_TOKEN: Final[str] = "none"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]*$")


class EvidenceAct(StrEnum):
    """Closed evidence speech act."""

    ASSERT_SOURCE = "assert_source"
    TESTIFY = "testify"
    CITE_RECORD = "cite_record"
    CLAIM_CUSTODY = "claim_custody"
    INTERPRET = "interpret"
    CONTRADICT = "contradict"
    RETRACT = "retract"


EVIDENCE_PREDICATES: Final[Mapping[EvidenceAct, str]] = MappingProxyType(
    {
        EvidenceAct.ASSERT_SOURCE: "ev_source",
        EvidenceAct.TESTIFY: "ev_testify",
        EvidenceAct.CITE_RECORD: "ev_record",
        EvidenceAct.CLAIM_CUSTODY: "ev_custody",
        EvidenceAct.INTERPRET: "ev_interpret",
        EvidenceAct.CONTRADICT: "ev_contradict",
        EvidenceAct.RETRACT: "ev_retract",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, EvidenceAct]] = MappingProxyType(
    {predicate: act for act, predicate in EVIDENCE_PREDICATES.items()}
)

_FRAME_KEYS: Final[tuple[str, ...]] = (
    "act",
    "subject_token",
    "source_kind",
    "reference_kind",
    "reference_id",
    "witness_id",
    "testimony_channel",
    "root_ref",
    "confidence_band",
    "interpretation",
    "contradiction_kind",
    "first_ref",
    "second_ref",
    "custody_role",
    "counterparty_token",
    "location_token",
    "custodian_token",
)
assert len(_FRAME_KEYS) == EVIDENCE_FRAME_FIELD_COUNT

_REQUIRED_FIELDS: Final[Mapping[EvidenceAct, frozenset[str]]] = MappingProxyType(
    {
        EvidenceAct.ASSERT_SOURCE: frozenset(
            {
                "subject_token",
                "source_kind",
                "reference_kind",
                "reference_id",
                "confidence_band",
            }
        ),
        EvidenceAct.CITE_RECORD: frozenset(
            {
                "subject_token",
                "reference_kind",
                "reference_id",
                "confidence_band",
            }
        ),
        EvidenceAct.TESTIFY: frozenset(
            {
                "subject_token",
                "testimony_channel",
                "witness_id",
                "confidence_band",
            }
        ),
        EvidenceAct.CLAIM_CUSTODY: frozenset(
            {
                "subject_token",
                "custody_role",
                "reference_id",
                "confidence_band",
            }
        ),
        EvidenceAct.INTERPRET: frozenset(
            {
                "subject_token",
                "interpretation",
                "reference_id",
                "confidence_band",
            }
        ),
        EvidenceAct.CONTRADICT: frozenset(
            {
                "subject_token",
                "contradiction_kind",
                "first_ref",
                "second_ref",
                "confidence_band",
            }
        ),
        EvidenceAct.RETRACT: frozenset(
            {"subject_token", "reference_id", "confidence_band"}
        ),
    }
)

_CUSTODY_FIELDS: Final[tuple[str, ...]] = (
    "counterparty_token",
    "location_token",
    "custodian_token",
)
_REQUIRED_CUSTODY_FIELD: Final[Mapping[EvidenceCustodyRole, str]] = MappingProxyType(
    {
        EvidenceCustodyRole.HOLDER: "counterparty_token",
        EvidenceCustodyRole.LOCATION: "location_token",
        EvidenceCustodyRole.REPOSITORY_CUSTODIAN: "custodian_token",
    }
)


def _fail() -> NoReturn:
    raise EvidenceError("evidence_untrusted_frame")


def _require_token(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > EVIDENCE_FRAME_TOKEN_MAX
        or _TOKEN_PATTERN.match(value) is None
    ):
        _fail()
    return value


def _optional_token(value: object) -> str | None:
    if value is None:
        return None
    return _require_token(value)


def _optional_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT | None:
    if value is None:
        return None
    if type(value) is not enum_type:
        _fail()
    return value


@dataclass(frozen=True, slots=True)
class EvidenceFrame:
    """One closed self-authored evidence speech atom. Carries no payload body."""

    act: EvidenceAct
    subject_token: str | None = None
    source_kind: EvidenceSourceKind | None = None
    reference_kind: EvidenceReferenceKind | None = None
    reference_id: str | None = None
    witness_id: str | None = None
    testimony_channel: EvidenceTestimonyChannel | None = None
    root_ref: str | None = None
    confidence_band: str | None = None
    interpretation: EvidenceInterpretationKind | None = None
    contradiction_kind: EvidenceContradictionKind | None = None
    first_ref: str | None = None
    second_ref: str | None = None
    custody_role: EvidenceCustodyRole | None = None
    counterparty_token: str | None = None
    location_token: str | None = None
    custodian_token: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not EvidenceAct:
            _fail()
        object.__setattr__(self, "subject_token", _optional_token(self.subject_token))
        object.__setattr__(
            self, "source_kind", _optional_enum(self.source_kind, EvidenceSourceKind)
        )
        object.__setattr__(
            self,
            "reference_kind",
            _optional_enum(self.reference_kind, EvidenceReferenceKind),
        )
        for name in (
            "reference_id",
            "witness_id",
            "root_ref",
            "first_ref",
            "second_ref",
            "counterparty_token",
            "location_token",
            "custodian_token",
        ):
            object.__setattr__(self, name, _optional_token(getattr(self, name)))
        object.__setattr__(
            self,
            "testimony_channel",
            _optional_enum(self.testimony_channel, EvidenceTestimonyChannel),
        )
        object.__setattr__(
            self,
            "interpretation",
            _optional_enum(self.interpretation, EvidenceInterpretationKind),
        )
        object.__setattr__(
            self,
            "contradiction_kind",
            _optional_enum(self.contradiction_kind, EvidenceContradictionKind),
        )
        object.__setattr__(
            self,
            "custody_role",
            _optional_enum(self.custody_role, EvidenceCustodyRole),
        )
        band = self.confidence_band
        if type(band) is not str or band not in EVIDENCE_CONFIDENCE_BANDS:
            _fail()
        object.__setattr__(self, "confidence_band", band)

        for name in _REQUIRED_FIELDS[self.act]:
            if getattr(self, name) is None:
                _fail()

        if self.act in {EvidenceAct.ASSERT_SOURCE, EvidenceAct.CITE_RECORD}:
            if self.reference_kind is None:
                _fail()
            if self.act is EvidenceAct.ASSERT_SOURCE and self.source_kind is None:
                _fail()
            if self.act is EvidenceAct.CITE_RECORD:
                if self.source_kind is not None and (
                    self.source_kind is not EvidenceSourceKind.WRITTEN_RECORD
                ):
                    _fail()
                object.__setattr__(
                    self, "source_kind", EvidenceSourceKind.WRITTEN_RECORD
                )
        else:
            for name in (
                "source_kind",
                "reference_kind",
            ):
                if getattr(self, name) is not None:
                    _fail()

        if self.act is EvidenceAct.TESTIFY:
            if self.testimony_channel is None:
                _fail()
            if self.testimony_channel is EvidenceTestimonyChannel.COMMUNICATED:
                if self.root_ref is None:
                    _fail()
            elif self.root_ref is not None:
                _fail()
        else:
            if self.testimony_channel is not None or self.root_ref is not None:
                _fail()

        if self.act is not EvidenceAct.TESTIFY and self.witness_id is not None:
            _fail()

        if self.act is not EvidenceAct.INTERPRET and self.interpretation is not None:
            _fail()
        if self.act is not EvidenceAct.CONTRADICT and (
            self.contradiction_kind is not None
            or self.first_ref is not None
            or self.second_ref is not None
        ):
            _fail()
        if self.act is EvidenceAct.CONTRADICT:
            if self.first_ref == self.second_ref:
                _fail()

        if self.act is EvidenceAct.CLAIM_CUSTODY:
            role = self.custody_role
            if role is None:
                _fail()
            present = [
                name for name in _CUSTODY_FIELDS if getattr(self, name) is not None
            ]
            if role is EvidenceCustodyRole.OBSERVER:
                if present:
                    _fail()
            elif present != [_REQUIRED_CUSTODY_FIELD[role]]:
                _fail()
        else:
            if self.custody_role is not None:
                _fail()
            if any(getattr(self, name) is not None for name in _CUSTODY_FIELDS):
                _fail()


def _encode_field(value: object) -> str:
    if value is None:
        return _NONE_TOKEN
    if isinstance(value, StrEnum):
        return value.value
    return cast(str, value)


def encode_evidence_frame(frame: EvidenceFrame) -> str:
    """Encode one frame into the bounded 17-field ``ev_v1`` payload.

    The payload travels as one existing ``CommunicationRelation`` object, whose
    transport bound is 256 characters, so an attachable frame is bounded by that
    smaller limit rather than the 768-character parse ceiling.
    """

    if type(frame) is not EvidenceFrame:
        raise TypeError("frame must be EvidenceFrame")
    fields = tuple(_encode_field(getattr(frame, name)) for name in _FRAME_KEYS[1:])
    text = f"{EVIDENCE_FRAME_SUBJECT}:{EVIDENCE_PREDICATES[frame.act]}:" + ":".join(
        fields
    )
    if len(text) > EVIDENCE_FRAME_MAX_CHARS:
        raise EvidenceError("evidence_untrusted_frame")
    return text


def parse_evidence_frame(text: str) -> EvidenceFrame | None:
    """Parse one strict ``ev_v1`` frame; malformed text returns ``None``."""

    try:
        if type(text) is not str or len(text) > EVIDENCE_FRAME_MAX_CHARS:
            return None
        if any(character.isspace() or ord(character) < 32 for character in text):
            return None
        parts = text.split(":")
        if len(parts) != EVIDENCE_FRAME_FIELD_COUNT + 1:
            return None
        subject, predicate, *fields = parts
        if subject != EVIDENCE_FRAME_SUBJECT:
            return None
        act = _PREDICATE_TO_ACT.get(predicate)
        if act is None:
            return None
        values = {
            name: (None if raw == _NONE_TOKEN else raw)
            for name, raw in zip(_FRAME_KEYS[1:], fields, strict=True)
        }
        source_kind_raw = values["source_kind"]
        reference_kind_raw = values["reference_kind"]
        testimony_raw = values["testimony_channel"]
        interpretation_raw = values["interpretation"]
        contradiction_raw = values["contradiction_kind"]
        custody_raw = values["custody_role"]
        return EvidenceFrame(
            act=act,
            subject_token=values["subject_token"],
            source_kind=(
                None if source_kind_raw is None else EvidenceSourceKind(source_kind_raw)
            ),
            reference_kind=(
                None
                if reference_kind_raw is None
                else EvidenceReferenceKind(reference_kind_raw)
            ),
            reference_id=values["reference_id"],
            witness_id=values["witness_id"],
            testimony_channel=(
                None
                if testimony_raw is None
                else EvidenceTestimonyChannel(testimony_raw)
            ),
            root_ref=values["root_ref"],
            confidence_band=values["confidence_band"],
            interpretation=(
                None
                if interpretation_raw is None
                else EvidenceInterpretationKind(interpretation_raw)
            ),
            contradiction_kind=(
                None
                if contradiction_raw is None
                else EvidenceContradictionKind(contradiction_raw)
            ),
            first_ref=values["first_ref"],
            second_ref=values["second_ref"],
            custody_role=(
                None if custody_raw is None else EvidenceCustodyRole(custody_raw)
            ),
            counterparty_token=values["counterparty_token"],
            location_token=values["location_token"],
            custodian_token=values["custodian_token"],
        )
    except (EvidenceError, TypeError, ValueError):
        _LOG.debug("evidence_frame_rejected reason=malformed")
        return None


def evidence_frame_relation(frame: EvidenceFrame) -> CommunicationRelation:
    """Build the ``(subject, predicate, object)`` atom for one frame."""

    if type(frame) is not EvidenceFrame:
        raise TypeError("frame must be EvidenceFrame")
    text = encode_evidence_frame(frame)
    subject, predicate, *fields = text.split(":")
    return CommunicationRelation(
        subject=subject, predicate=predicate, object=":".join(fields)
    )


def parse_evidence_frame_relation(relation: object) -> EvidenceFrame | None:
    """Parse one relation atom; unrelated atoms return ``None``."""

    subject = getattr(relation, "subject", None)
    predicate = getattr(relation, "predicate", None)
    body = getattr(relation, "object", None)
    if subject != EVIDENCE_FRAME_SUBJECT:
        return None
    if type(predicate) is not str or predicate not in _PREDICATE_TO_ACT:
        return None
    if type(body) is not str:
        return None
    return parse_evidence_frame(f"{subject}:{predicate}:{body}")


def evidence_frame_party_matches(
    frame: EvidenceFrame, verified_speaker: object
) -> bool:
    """Return whether the frame's witness claim is the verified speaker."""

    if type(frame) is not EvidenceFrame:
        return False
    speaker = (
        verified_speaker
        if type(verified_speaker) is str
        else getattr(verified_speaker, "value", None)
    )
    if type(speaker) is not str or not speaker:
        return False
    if frame.witness_id is None:
        return frame.act is not EvidenceAct.TESTIFY
    return frame.witness_id == speaker


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _relations(command: object) -> tuple[CommunicationRelation, ...]:
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    return tuple(getattr(content, "relations", ()) or ())


def evidence_communicate_utterance(
    command: object,
    frame: EvidenceFrame,
    *,
    max_relations: int = 32,
) -> object:
    """Attach at most one ``ev_v1`` relation to an already-selected utterance.

    The command type, recipient, delivery, and every existing relation are
    preserved. Foreign actors, invalid frames, and relation-limit overflow leave
    the command unchanged; no command is created, replaced, or re-targeted.
    """

    if type(frame) is not EvidenceFrame:
        raise TypeError("frame must be EvidenceFrame")
    if not _is_expressible(command):
        return command
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = _relations(command)
    if any(
        relation.subject == EVIDENCE_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= max_relations:
        _LOG.warning("evidence_frame_skipped reason=relation_limit")
        return command
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    if speaker is None:
        _LOG.warning("evidence_frame_skipped reason=missing_speaker")
        return command
    if not evidence_frame_party_matches(frame, speaker):
        _LOG.warning("evidence_frame_foreign_witness")
        return command
    try:
        relation = evidence_frame_relation(frame)
    except (EvidenceError, TypeError, ValueError):
        _LOG.warning("evidence_frame_skipped reason=invalid_frame")
        return command
    updated = origin_utterance(
        text="evidence",
        speaker_id=speaker,
        communication_id=f"evidence-{frame.act.value}",
        relations=(*relations, relation),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug("evidence_frame_encoded act=%s", frame.act.value)
    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated,
    )
