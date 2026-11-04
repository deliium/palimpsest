"""Bounded ``dip_v1`` diplomacy claims inside existing speech.

A contact, accreditation, recall, negotiation, proposal, promise, acceptance,
rejection, withdrawal, dispute, shared project, or report travels as one closed
``CommunicationRelation`` atom inside ordinary ``Talk``/``Ask``/``Tell`` speech.
Delivery proves that speech happened; it never proves authority, legitimacy,
truth, or that an agreement binds anyone.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.diplomacy import (
    DiplomacyError,
    DiplomaticContactKind,
    DiplomaticInstrumentKind,
    DiplomaticPartyKind,
    DiplomaticProvenance,
    DiplomaticTermKind,
    require_diplomacy_subject,
    require_diplomacy_token,
)
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)

__all__ = [
    "DIPLOMACY_CONTACT_ANCHOR_SOURCE",
    "DIPLOMACY_FRAME_FIELD_COUNT",
    "DIPLOMACY_FRAME_MAX_CHARS",
    "DIPLOMACY_FRAME_SUBJECT",
    "DIPLOMACY_FRAME_VERSION",
    "DIPLOMACY_PREDICATES",
    "DiplomacyContactAnchor",
    "DiplomacyFrame",
    "DiplomaticAct",
    "diplomacy_communicate_utterance",
    "diplomacy_contact_anchors_from_observation",
    "diplomacy_frame_party_matches",
    "diplomacy_frame_relation",
    "diplomacy_frames_from_command",
    "diplomacy_frames_from_observation",
    "encode_diplomacy_frame",
    "parse_diplomacy_frame",
    "parse_diplomacy_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.diplomacy_communication"
)

DIPLOMACY_FRAME_VERSION: Final[str] = "dip_v1"
DIPLOMACY_FRAME_SUBJECT: Final[str] = "dip_v1"
DIPLOMACY_FRAME_MAX_CHARS: Final[int] = 320
DIPLOMACY_FRAME_FIELD_COUNT: Final[int] = 15
DIPLOMACY_CONTACT_ANCHOR_SOURCE: Final[str] = "contact_recorded"
_SEPARATOR: Final[str] = "|"
_NONE_TOKEN: Final[str] = "none"
_TOPIC_ACTS: Final[frozenset[str]] = frozenset(
    {
        "dip_open_negotiation",
        "dip_propose",
        "dip_promise",
        "dip_dispute",
        "dip_shared_project",
    }
)


class DiplomaticAct(StrEnum):
    """Closed diplomacy speech act."""

    CONTACT = "dip_contact"
    ACCREDIT = "dip_accredit"
    RECALL = "dip_recall"
    OPEN_NEGOTIATION = "dip_open_negotiation"
    PROPOSE = "dip_propose"
    PROMISE = "dip_promise"
    ACCEPT = "dip_accept"
    REJECT = "dip_reject"
    WITHDRAW = "dip_withdraw"
    DISPUTE = "dip_dispute"
    SHARED_PROJECT = "dip_shared_project"
    REPORT = "dip_report"


DIPLOMACY_PREDICATES: Final[Mapping[DiplomaticAct, str]] = MappingProxyType(
    {act: act.value for act in DiplomaticAct}
)
_PREDICATE_TO_ACT: Final[Mapping[str, DiplomaticAct]] = MappingProxyType(
    {predicate: act for act, predicate in DIPLOMACY_PREDICATES.items()}
)

_FRAME_KEYS: Final[tuple[str, ...]] = (
    "act",
    "relation_ref",
    "party_kind",
    "party_ref",
    "envoy_ref",
    "mandate_ref",
    "negotiation_ref",
    "instrument_ref",
    "instrument_kind",
    "term_kind",
    "topic_subject",
    "declaration_ref",
    "end_tick",
    "provenance",
    "revision",
)
assert len(_FRAME_KEYS) == DIPLOMACY_FRAME_FIELD_COUNT


def _fail() -> NoReturn:
    raise DiplomacyError("diplomacy_untrusted_frame")


def _optional_token(value: object) -> str | None:
    if value is None:
        return None
    return require_diplomacy_token(value, max_chars=128)


def _optional_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT | None:
    if value is None:
        return None
    if type(value) is not enum_type:
        _fail()
    return value


@dataclass(frozen=True, slots=True)
class DiplomacyFrame:
    """One closed, self-authored diplomacy speech atom."""

    act: DiplomaticAct
    relation_ref: str | None = None
    party_kind: DiplomaticPartyKind | None = None
    party_ref: str | None = None
    envoy_ref: str | None = None
    mandate_ref: str | None = None
    negotiation_ref: str | None = None
    instrument_ref: str | None = None
    instrument_kind: DiplomaticInstrumentKind | None = None
    term_kind: DiplomaticTermKind | None = None
    topic_subject: str | None = None
    declaration_ref: str | None = None
    end_tick: int | None = None
    provenance: DiplomaticProvenance | None = None
    revision: int = 0
    actor_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not DiplomaticAct:
            _fail()
        object.__setattr__(self, "relation_ref", _optional_token(self.relation_ref))
        object.__setattr__(
            self, "party_kind", _optional_enum(self.party_kind, DiplomaticPartyKind)
        )
        object.__setattr__(self, "party_ref", _optional_token(self.party_ref))
        envoy = _optional_token(self.envoy_ref)
        if envoy is None:
            _fail()
        object.__setattr__(self, "envoy_ref", envoy)
        object.__setattr__(self, "mandate_ref", _optional_token(self.mandate_ref))
        object.__setattr__(
            self, "negotiation_ref", _optional_token(self.negotiation_ref)
        )
        object.__setattr__(self, "instrument_ref", _optional_token(self.instrument_ref))
        object.__setattr__(
            self,
            "instrument_kind",
            _optional_enum(self.instrument_kind, DiplomaticInstrumentKind),
        )
        object.__setattr__(
            self, "term_kind", _optional_enum(self.term_kind, DiplomaticTermKind)
        )
        if self.topic_subject is not None:
            object.__setattr__(
                self, "topic_subject", require_diplomacy_subject(self.topic_subject)
            )
        object.__setattr__(
            self, "declaration_ref", _optional_token(self.declaration_ref)
        )
        if self.end_tick is not None and (
            type(self.end_tick) is not int
            or isinstance(self.end_tick, bool)
            or self.end_tick < 0
        ):
            _fail()
        object.__setattr__(
            self, "provenance", _optional_enum(self.provenance, DiplomaticProvenance)
        )
        object.__setattr__(self, "actor_ref", _optional_token(self.actor_ref))
        if type(self.revision) is not int or isinstance(self.revision, bool):
            _fail()
        if self.revision < 0:
            _fail()
        if (
            self.party_kind is DiplomaticPartyKind.UNKNOWN
            and self.party_ref is not None
        ):
            _fail()
        if self.act.value in _TOPIC_ACTS and self.topic_subject is None:
            _fail()
        if self.act.value not in _TOPIC_ACTS and self.topic_subject is not None:
            _fail()
        if (
            self.act
            in {
                DiplomaticAct.ACCEPT,
                DiplomaticAct.REJECT,
                DiplomaticAct.WITHDRAW,
                DiplomaticAct.REPORT,
            }
            and self.instrument_ref is None
        ):
            _fail()
        if self.act is DiplomaticAct.RECALL and self.negotiation_ref is not None:
            _fail()


def _encode_field(value: object) -> str:
    if value is None:
        return _NONE_TOKEN
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def encode_diplomacy_frame(frame: DiplomacyFrame) -> str:
    """Encode one frame into the bounded ``dip_v1`` payload."""

    if type(frame) is not DiplomacyFrame:
        raise TypeError("frame must be DiplomacyFrame")
    fields = tuple(_encode_field(getattr(frame, name)) for name in _FRAME_KEYS[1:])
    text = (
        f"{DIPLOMACY_FRAME_SUBJECT}{_SEPARATOR}"
        f"{DIPLOMACY_PREDICATES[frame.act]}{_SEPARATOR}" + _SEPARATOR.join(fields)
    )
    if len(text) > DIPLOMACY_FRAME_MAX_CHARS:
        raise DiplomacyError("diplomacy_frame_too_large")
    return text


def parse_diplomacy_frame(text: str) -> DiplomacyFrame | None:
    """Parse one strict ``dip_v1`` frame; malformed text returns ``None``."""

    try:
        if type(text) is not str or len(text) > DIPLOMACY_FRAME_MAX_CHARS:
            _LOG.debug("diplomacy_frame_dropped reason=oversize")
            return None
        if any(character.isspace() or ord(character) < 32 for character in text):
            _LOG.debug("diplomacy_frame_dropped reason=invalid")
            return None
        parts = text.split(_SEPARATOR)
        if len(parts) != DIPLOMACY_FRAME_FIELD_COUNT + 1:
            _LOG.debug("diplomacy_frame_dropped reason=invalid")
            return None
        subject, predicate, *fields = parts
        if subject != DIPLOMACY_FRAME_SUBJECT:
            _LOG.debug("diplomacy_frame_dropped reason=unknown_subject")
            return None
        act = _PREDICATE_TO_ACT.get(predicate)
        if act is None:
            _LOG.debug("diplomacy_frame_dropped reason=invalid")
            return None
        values = {
            name: (None if raw == _NONE_TOKEN else raw)
            for name, raw in zip(_FRAME_KEYS[1:], fields, strict=True)
        }
        revision_raw = values["revision"]
        if revision_raw is None:
            return None
        party_kind_raw = values["party_kind"]
        instrument_kind_raw = values["instrument_kind"]
        term_kind_raw = values["term_kind"]
        provenance_raw = values["provenance"]
        end_raw = values["end_tick"]
        return DiplomacyFrame(
            act=act,
            relation_ref=values["relation_ref"],
            party_kind=(
                None if party_kind_raw is None else DiplomaticPartyKind(party_kind_raw)
            ),
            party_ref=values["party_ref"],
            envoy_ref=values["envoy_ref"],
            mandate_ref=values["mandate_ref"],
            negotiation_ref=values["negotiation_ref"],
            instrument_ref=values["instrument_ref"],
            instrument_kind=(
                None
                if instrument_kind_raw is None
                else DiplomaticInstrumentKind(instrument_kind_raw)
            ),
            term_kind=(
                None if term_kind_raw is None else DiplomaticTermKind(term_kind_raw)
            ),
            topic_subject=values["topic_subject"],
            declaration_ref=values["declaration_ref"],
            end_tick=None if end_raw is None else int(end_raw),
            provenance=(
                None if provenance_raw is None else DiplomaticProvenance(provenance_raw)
            ),
            revision=int(revision_raw),
        )
    except (DiplomacyError, TypeError, ValueError):
        _LOG.debug("diplomacy_frame_dropped reason=invalid")
        return None


def diplomacy_frame_relation(frame: DiplomacyFrame) -> CommunicationRelation:
    """Build the ``(subject, predicate, object)`` atom for one frame."""

    if type(frame) is not DiplomacyFrame:
        raise TypeError("frame must be DiplomacyFrame")
    text = encode_diplomacy_frame(frame)
    subject, predicate, object_text = text.split(_SEPARATOR, 2)
    return CommunicationRelation(
        subject=subject, predicate=predicate, object=object_text
    )


def parse_diplomacy_frame_relation(
    subject: str, predicate: str, object_text: str
) -> DiplomacyFrame | None:
    """Parse one relation atom; unrelated atoms return ``None``."""

    if subject != DIPLOMACY_FRAME_SUBJECT:
        return None
    if type(predicate) is not str or predicate not in _PREDICATE_TO_ACT:
        return None
    if type(object_text) is not str:
        return None
    return parse_diplomacy_frame(
        f"{subject}{_SEPARATOR}{predicate}{_SEPARATOR}{object_text}"
    )


def diplomacy_frame_party_matches(
    frame: DiplomacyFrame, verified_speaker: object
) -> bool:
    """Return whether the frame attributes the claim to the verified speaker."""

    if type(frame) is not DiplomacyFrame:
        return False
    speaker = (
        verified_speaker
        if type(verified_speaker) is str
        else getattr(verified_speaker, "value", None)
    )
    if type(speaker) is not str or not speaker:
        return False
    return frame.envoy_ref == speaker


def diplomacy_frames_from_observation(
    observation: object, *, owner_id: object
) -> tuple[DiplomacyFrame, ...]:
    """Collect speaker-verified ``dip_v1`` frames from one owner's observation."""

    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        raise ValueError("owner_id must be a non-empty token")
    frames: list[DiplomacyFrame] = []
    for communication in getattr(observation, "communications", ()):
        speaker = getattr(getattr(communication, "speaker_id", None), "value", None)
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        for relation in getattr(content, "relations", ()):
            frame = parse_diplomacy_frame_relation(
                getattr(relation, "subject", ""),
                getattr(relation, "predicate", ""),
                getattr(relation, "object", ""),
            )
            if frame is None:
                continue
            if not diplomacy_frame_party_matches(frame, speaker):
                _LOG.warning("diplomacy_party_mismatch count=1")
                continue
            frames.append(
                replace(
                    frame,
                    actor_ref=speaker,
                    provenance=DiplomaticProvenance.COMMUNICATED,
                )
            )
    frames.sort(
        key=lambda frame: (
            frame.act.value,
            frame.relation_ref or "",
            frame.instrument_ref or "",
            frame.topic_subject or "",
            frame.revision,
        )
    )
    return tuple(frames)


def diplomacy_frames_from_command(
    command: object, *, owner_id: object
) -> tuple[DiplomacyFrame, ...]:
    """Parse the owner's own already-selected ``dip_v1`` speech."""

    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        raise ValueError("owner_id must be a non-empty token")
    frames: list[DiplomacyFrame] = []
    for relation in _relations(command):
        frame = parse_diplomacy_frame_relation(
            getattr(relation, "subject", ""),
            getattr(relation, "predicate", ""),
            getattr(relation, "object", ""),
        )
        if frame is None:
            continue
        if frame.envoy_ref != owner:
            _LOG.warning("diplomacy_party_mismatch count=1")
            continue
        frames.append(
            replace(
                frame,
                actor_ref=owner,
                provenance=DiplomaticProvenance.SELF_DECLARED,
            )
        )
    frames.sort(
        key=lambda frame: (
            frame.act.value,
            frame.relation_ref or "",
            frame.instrument_ref or "",
            frame.topic_subject or "",
            frame.revision,
        )
    )
    return tuple(frames)


def _is_expressible(command: object) -> bool:
    from world.actions import Ask, Talk, Tell

    return type(command) in {Talk, Ask, Tell}


def _relations(command: object) -> tuple[CommunicationRelation, ...]:
    utterance = getattr(command, "utterance", None)
    content = getattr(utterance, "content", None)
    return tuple(getattr(content, "relations", ()) or ())


def diplomacy_communicate_utterance(
    command: object,
    frame: DiplomacyFrame,
    *,
    max_chars: int = DIPLOMACY_FRAME_MAX_CHARS,
) -> object:
    """Attach at most one ``dip_v1`` relation to an already-selected utterance."""

    import world.communications as communications_module

    max_relations = getattr(communications_module, "MAX_COMMUNICATION_RELATIONS", 32)
    if type(frame) is not DiplomacyFrame:
        raise TypeError("frame must be DiplomacyFrame")
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
        relation.subject == DIPLOMACY_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= max_relations:
        _LOG.warning("diplomacy_frame_skipped reason=relation_limit")
        return command
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    if speaker is None:
        _LOG.warning("diplomacy_frame_skipped reason=missing_speaker")
        return command
    if not diplomacy_frame_party_matches(frame, speaker):
        _LOG.warning("diplomacy_party_mismatch count=1")
        return command
    try:
        relation = diplomacy_frame_relation(frame)
        encoded = encode_diplomacy_frame(frame)
    except (DiplomacyError, TypeError, ValueError):
        _LOG.warning("diplomacy_frame_skipped reason=invalid_frame")
        return command
    if len(encoded) > max_chars:
        _LOG.warning("diplomacy_frame_skipped reason=oversize")
        return command
    updated = origin_utterance(
        text="diplomacy",
        speaker_id=speaker,
        communication_id=f"diplomacy-{frame.act.value}",
        relations=(*relations, relation),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug("diplomacy_frame_encoded act=%s", frame.act.value)
    typed = cast(Any, command)
    return typed.__class__(recipient_id=typed.recipient_id, utterance=updated)


@dataclass(frozen=True, slots=True)
class DiplomacyContactAnchor:
    """One bounded contact anchor from owner-visible objective facts."""

    location_anchor: str | None
    participant_refs: tuple[str, ...]
    participant_count: int
    contact_kind: DiplomaticContactKind
    source_ref: str | None


def diplomacy_contact_anchors_from_observation(
    observation: object, *, owner_id: object | None = None
) -> tuple[DiplomacyContactAnchor, ...]:
    """Map objective contact occurrences to bounded anchors."""

    owner = getattr(owner_id, "value", owner_id) if owner_id is not None else None
    anchors: list[DiplomacyContactAnchor] = []
    for occurrence in getattr(observation, "occurrences", ()):
        if getattr(occurrence, "kind", None) != DIPLOMACY_CONTACT_ANCHOR_SOURCE:
            continue
        facts = getattr(occurrence, "public_facts", None)
        if not isinstance(facts, Mapping):
            _LOG.debug("diplomacy_contact_dropped reason=malformed")
            continue
        participants = facts.get("contact_participant_ids")
        location = facts.get("contact_location_id")
        if not isinstance(participants, (list, tuple)):
            _LOG.debug("diplomacy_contact_dropped reason=malformed")
            continue
        refs: list[str] = []
        all_refs: list[str] = []
        for raw in participants:
            value = getattr(raw, "value", raw)
            if type(value) is not str or not value:
                continue
            try:
                validated = require_diplomacy_token(value, max_chars=128)
            except DiplomacyError:
                continue
            all_refs.append(validated)
            if validated != owner:
                refs.append(validated)
        if not refs:
            continue
        source = getattr(
            getattr(occurrence, "provenance", None), "source_event_id", None
        )
        source_value = getattr(source, "value", source)
        anchors.append(
            DiplomacyContactAnchor(
                location_anchor=(
                    require_diplomacy_token(location, max_chars=128)
                    if type(location) is str and location
                    else None
                ),
                participant_refs=tuple(sorted(set(refs))),
                participant_count=len(all_refs),
                contact_kind=DiplomaticContactKind.DIRECT_CO_PRESENCE,
                source_ref=(
                    require_diplomacy_token(source_value, max_chars=128)
                    if type(source_value) is str and source_value
                    else None
                ),
            )
        )
    return tuple(
        sorted(
            anchors,
            key=lambda item: (
                item.source_ref or "",
                item.location_anchor or "",
                item.participant_refs,
            ),
        )
    )
