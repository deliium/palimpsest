# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Bounded ``bdr_v1`` border speech carried inside existing Talk/Ask/Tell.

The frame is a set of at most eight colon-separated relations. It is not a new
event, command, observer semantic type, or wire genre. Speaker identity and
provenance always come from delivery, never from a frame field.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from agents.cognition.borders import (
    AccessExpectationMode,
    AgreementAct,
    AgreementProvision,
    CounterpartyKind,
    domain_claim_token_id,
)
from agents.models import AgentId
from world.actions import Ask, Talk, Tell
from world.communications import CommunicationRelation
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.borders_communication"
)

BORDER_FRAME_SUBJECT: Final[str] = "bdr_v1"
BORDER_FRAME_VERSION: Final[str] = "borders-communication.v1"
BORDER_FRAME_MAX_CHARS: Final[int] = 256
BORDER_FRAME_MAX_RELATIONS: Final[int] = 8
# The subject marker plus ten relation fields (eleven colon-separated parts).
BORDER_FRAME_FIELD_COUNT: Final[int] = 11
_NONE: Final[str] = "-"
_MAX_PARTY_CHARS: Final[int] = 128
_MAX_LOCATION_CHARS: Final[int] = 128


class BorderFrameError(ValueError):
    """Stable-code frame violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BorderFrame:
    """Exactly bounded semantic content of one delivered frame group."""

    act: AgreementAct
    domain_id: str
    party_kind: CounterpartyKind
    party_ref: str | None
    locations: tuple[str, ...]
    expiry_tick: int | None = None
    access_mode: AccessExpectationMode | None = None
    provision: AgreementProvision | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not AgreementAct:
            raise BorderFrameError("frame_act")
        if (
            type(self.domain_id) is not str
            or not self.domain_id.startswith("bdc-")
            or len(self.domain_id) != 20
        ):
            raise BorderFrameError("frame_domain")
        if type(self.party_kind) is not CounterpartyKind:
            raise BorderFrameError("frame_party_kind")
        if self.party_kind is CounterpartyKind.UNKNOWN:
            if self.party_ref is not None:
                raise BorderFrameError("frame_party_ref")
        elif (
            type(self.party_ref) is not str
            or not self.party_ref
            or len(self.party_ref) > _MAX_PARTY_CHARS
        ):
            raise BorderFrameError("frame_party_ref")
        locations = tuple(self.locations)
        if not 1 <= len(locations) <= BORDER_FRAME_MAX_RELATIONS:
            raise BorderFrameError("frame_location_count")
        if len(set(locations)) != len(locations):
            raise BorderFrameError("frame_duplicate_location")
        for item in locations:
            if (
                type(item) is not str
                or not item
                or len(item) > _MAX_LOCATION_CHARS
            ):
                raise BorderFrameError("frame_location")
        object.__setattr__(self, "locations", tuple(sorted(locations)))
        if self.expiry_tick is not None and (
            type(self.expiry_tick) is not int or self.expiry_tick < 0
        ):
            raise BorderFrameError("frame_expiry")
        if self.access_mode is not None and (
            type(self.access_mode) is not AccessExpectationMode
        ):
            raise BorderFrameError("frame_access_mode")
        if self.provision is not None and (
            type(self.provision) is not AgreementProvision
        ):
            raise BorderFrameError("frame_provision")


def _party_token(frame: BorderFrame) -> str:
    return _NONE if frame.party_ref is None else frame.party_ref


def _encode_one(
    frame: BorderFrame, *, index: int, count: int, location: str
) -> str:
    return ":".join(
        (
            BORDER_FRAME_SUBJECT,
            frame.act.value,
            frame.domain_id,
            frame.party_kind.value,
            _party_token(frame),
            str(index),
            str(count),
            location,
            _NONE if frame.expiry_tick is None else str(frame.expiry_tick),
            _NONE if frame.access_mode is None else frame.access_mode.value,
            _NONE if frame.provision is None else frame.provision.value,
        )
    )


def encode_border_claim(frame: BorderFrame) -> str:
    """Encode one frame group as newline-separated bounded relations."""
    if type(frame) is not BorderFrame:
        raise TypeError("frame must be BorderFrame")
    count = len(frame.locations)
    lines = tuple(
        _encode_one(frame, index=index, count=count, location=location)
        for index, location in enumerate(frame.locations)
    )
    for line in lines:
        if len(line) > BORDER_FRAME_MAX_CHARS:
            raise BorderFrameError("frame_too_large")
    return "\n".join(lines)


def _parse_int(token: str, code: str) -> int:
    if not token.isdigit():
        raise BorderFrameError(code)
    value = int(token)
    if value < 0:
        raise BorderFrameError(code)
    return value


_ParsedRelation = tuple[
    AgreementAct,
    str,
    CounterpartyKind,
    str | None,
    int,
    int,
    str,
    int | None,
    AccessExpectationMode | None,
    AgreementProvision | None,
]


def _parse_one(text: str) -> _ParsedRelation:
    if type(text) is not str or len(text) > BORDER_FRAME_MAX_CHARS:
        raise BorderFrameError("frame_too_large")
    parts = text.split(":")
    if len(parts) != BORDER_FRAME_FIELD_COUNT:
        raise BorderFrameError("frame_field_count")
    (
        subject,
        act_token,
        domain_id,
        party_kind_token,
        party_ref,
        index_token,
        count_token,
        location,
        expiry_token,
        access_token,
        provision_token,
    ) = parts
    if subject != BORDER_FRAME_SUBJECT:
        raise BorderFrameError("frame_subject")
    try:
        act = AgreementAct(act_token)
        party_kind = CounterpartyKind(party_kind_token)
    except ValueError as exc:
        raise BorderFrameError("frame_enum") from exc
    if not domain_id.startswith("bdc-") or len(domain_id) != 20:
        raise BorderFrameError("frame_domain")
    if party_kind is CounterpartyKind.UNKNOWN:
        if party_ref != _NONE:
            raise BorderFrameError("frame_party_ref")
        parsed_party: str | None = None
    else:
        if (
            party_ref == _NONE
            or not party_ref
            or len(party_ref) > _MAX_PARTY_CHARS
        ):
            raise BorderFrameError("frame_party_ref")
        parsed_party = party_ref
    index = _parse_int(index_token, "frame_index")
    count = _parse_int(count_token, "frame_count")
    if not 1 <= count <= BORDER_FRAME_MAX_RELATIONS or index >= count:
        raise BorderFrameError("frame_count")
    if not location or location == _NONE or len(location) > _MAX_LOCATION_CHARS:
        raise BorderFrameError("frame_location")
    expiry = None if expiry_token == _NONE else _parse_int(expiry_token, "frame_expiry")
    access_mode = None
    if access_token != _NONE:
        try:
            access_mode = AccessExpectationMode(access_token)
        except ValueError as exc:
            raise BorderFrameError("frame_access_mode") from exc
    provision = None
    if provision_token != _NONE:
        try:
            provision = AgreementProvision(provision_token)
        except ValueError as exc:
            raise BorderFrameError("frame_provision") from exc
    return (
        act,
        domain_id,
        party_kind,
        parsed_party,
        index,
        count,
        location,
        expiry,
        access_mode,
        provision,
    )


def parse_border_claim_relation(relation: object) -> str:
    """Return the raw payload of one relation object or raise a stable code."""
    payload = getattr(relation, "object", None)
    if type(payload) is not str:
        raise BorderFrameError("frame_relation")
    if getattr(relation, "subject", None) != BORDER_FRAME_SUBJECT:
        raise BorderFrameError("frame_subject")
    return payload


def parse_border_claim(text: str) -> BorderFrame:
    """Parse one newline-separated frame group into a single frame."""
    if type(text) is not str:
        raise TypeError("text must be str")
    lines = [line for line in text.split("\n") if line]
    if not 1 <= len(lines) <= BORDER_FRAME_MAX_RELATIONS:
        raise BorderFrameError("frame_count")
    parsed = [_parse_one(line) for line in lines]
    first = parsed[0]
    act, domain_id, party_kind, party_ref, _, count, _, expiry, access, provision = (
        first
    )
    if count != len(parsed):
        raise BorderFrameError("frame_count")
    indices: list[int] = []
    locations: list[str] = []
    for row in parsed:
        if (
            row[0] is not act
            or row[1] != domain_id
            or row[2] is not party_kind
            or row[3] != party_ref
            or row[5] != count
            or row[7] != expiry
            or row[8] is not access
            or row[9] is not provision
        ):
            raise BorderFrameError("frame_mixed_group")
        indices.append(row[4])
        locations.append(row[6])
    if indices != list(range(count)):
        raise BorderFrameError("frame_index_order")
    if len(set(locations)) != len(locations):
        raise BorderFrameError("frame_duplicate_location")
    return BorderFrame(
        act=act,
        domain_id=domain_id,
        party_kind=party_kind,
        party_ref=party_ref,
        locations=tuple(locations),
        expiry_tick=expiry,
        access_mode=access,
        provision=provision,
    )


def border_claim_relation(frame: BorderFrame) -> tuple[CommunicationRelation, ...]:
    """Build ordered relation atoms for one frame group."""
    if type(frame) is not BorderFrame:
        raise TypeError("frame must be BorderFrame")
    count = len(frame.locations)
    return tuple(
        CommunicationRelation(
            subject=BORDER_FRAME_SUBJECT,
            predicate="relation",
            object=_encode_one(
                frame, index=index, count=count, location=location
            ),
        )
        for index, location in enumerate(frame.locations)
    )


def _speech(command: object) -> Talk | Ask | Tell:
    if type(command) is Talk:
        return command
    if type(command) is Ask:
        return command
    if type(command) is Tell:
        return command
    raise TypeError("command must be Talk, Ask, or Tell")


def attach_border_relation(command: object, frame: BorderFrame) -> object:
    """Append one ``bdr_v1`` group to an existing speech command."""
    speech = _speech(command)
    if type(frame) is not BorderFrame:
        raise TypeError("frame must be BorderFrame")
    if any(
        relation.subject == BORDER_FRAME_SUBJECT
        for relation in speech.utterance.content.relations
    ):
        raise BorderFrameError("frame_duplicate_group")
    relations = tuple(speech.utterance.content.relations) + border_claim_relation(
        frame
    )
    if len(relations) > 32:
        raise BorderFrameError("frame_relation_cap")
    content = replace(speech.utterance.content, relations=relations)
    utterance = replace(speech.utterance, content=content)
    return replace(speech, utterance=utterance)


def _group_frames(
    relations: Sequence[object],
    *,
    speaker_token: str,
    speaker_owner: AgentId | None,
) -> tuple[BorderFrame, ...]:
    payloads: list[str] = []
    for relation in relations:
        if getattr(relation, "subject", None) != BORDER_FRAME_SUBJECT:
            continue
        payload = getattr(relation, "object", None)
        if type(payload) is not str or len(payload) > BORDER_FRAME_MAX_CHARS:
            raise BorderFrameError("frame_too_large")
        payloads.append(payload)
    if not payloads:
        return ()
    if len(payloads) > BORDER_FRAME_MAX_RELATIONS:
        raise BorderFrameError("frame_count")
    frame = parse_border_claim("\n".join(payloads))
    if frame.party_ref is not None and frame.party_ref == speaker_token:
        raise BorderFrameError("frame_speaker_mismatch")
    if speaker_owner is not None:
        expected = domain_claim_token_id(speaker_owner, frame.locations)
        if frame.domain_id != expected:
            raise BorderFrameError("frame_domain_mismatch")
    return (frame,)


def _identity_entity(identity: object | None) -> EntityId | None:
    if identity is None:
        return None
    value = getattr(identity, "owner_entity_id", None)
    return value if type(value) is EntityId else None


def _agent_for_entity(identity: object | None, entity: EntityId) -> AgentId | None:
    if identity is None:
        return None
    if getattr(identity, "owner_entity_id", None) == entity:
        owner = getattr(identity, "owner_id", None)
        return owner if type(owner) is AgentId else None
    for binding in getattr(identity, "counterparts", ()) or ():
        if getattr(binding, "entity_id", None) == entity:
            agent = getattr(binding, "agent_id", None)
            return agent if type(agent) is AgentId else None
    return None


def _frames_from_communications(
    communications: Sequence[object],
    *,
    identity: object | None,
    owner_entity: EntityId | None,
) -> tuple[tuple[str, BorderFrame], ...]:
    frames: list[tuple[str, BorderFrame]] = []
    for communication in communications:
        listener = getattr(communication, "listener_id", None)
        if (
            owner_entity is not None
            and listener is not None
            and listener != owner_entity
        ):
            continue
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        relations = getattr(content, "relations", ()) or ()
        speaker = getattr(communication, "speaker_id", None)
        speaker_token = getattr(speaker, "value", "")
        if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
            continue
        speaker_owner = (
            _agent_for_entity(identity, speaker)
            if type(speaker) is EntityId
            else None
        )
        if speaker_owner is None:
            _LOG.warning(
                "borders_frame_dropped reason_code=unresolved_speaker count=1"
            )
            continue
        try:
            parsed = _group_frames(
                relations,
                speaker_token=str(speaker_token),
                speaker_owner=speaker_owner,
            )
        except BorderFrameError as exc:
            _LOG.warning(
                "borders_frame_dropped reason_code=%s count=1", exc.code
            )
            continue
        frames.extend((str(speaker_token), frame) for frame in parsed)
    return tuple(frames)


def border_frame_deliveries(
    observation: object,
    *,
    inbox: Sequence[object] | None = None,
    identity: object | None = None,
) -> tuple[tuple[str, BorderFrame], ...]:
    """Return ``(verified_speaker_token, frame)`` deliveries for one owner."""
    communications = getattr(observation, "communications", ()) or ()
    owner_entity = _identity_entity(identity)
    deliveries = list(
        _frames_from_communications(
            communications, identity=identity, owner_entity=owner_entity
        )
    )
    if inbox is not None:
        deliveries.extend(
            _deliveries_from_inbox(inbox, identity=identity)
        )
    return tuple(deliveries)


def _deliveries_from_inbox(
    inbox: Sequence[object], *, identity: object | None
) -> list[tuple[str, BorderFrame]]:
    frames: list[tuple[str, BorderFrame]] = []
    for entry in inbox:
        if type(entry) in (Talk, Ask, Tell):
            utterance = entry.utterance
            relations = utterance.content.relations
            speaker = utterance.declared.immediate_source_id
            speaker_token = speaker.value
        else:
            utterance = getattr(entry, "utterance", None)
            relations = getattr(
                getattr(utterance, "content", None), "relations", ()
            )
            speaker = getattr(entry, "speaker_id", None)
            speaker_token = getattr(speaker, "value", "")
        if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
            continue
        speaker_owner = (
            _agent_for_entity(identity, speaker)
            if type(speaker) is EntityId
            else None
        )
        if speaker_owner is None:
            _LOG.warning(
                "borders_frame_dropped reason_code=unresolved_speaker count=1"
            )
            continue
        try:
            parsed = _group_frames(
                relations,
                speaker_token=str(speaker_token),
                speaker_owner=speaker_owner,
            )
        except BorderFrameError as exc:
            _LOG.warning(
                "borders_frame_dropped reason_code=%s count=1", exc.code
            )
            continue
        frames.extend((str(speaker_token), frame) for frame in parsed)
    return frames


def border_frames_from_observation(
    observation: object, *, identity: object | None = None
) -> tuple[BorderFrame, ...]:
    """Parse speaker-bound delivered frames from one owner's observation."""
    communications = getattr(observation, "communications", ()) or ()
    owner_entity = _identity_entity(identity)
    return tuple(
        frame
        for _, frame in _frames_from_communications(
            communications, identity=identity, owner_entity=owner_entity
        )
    )


def border_frames_from_inbox(
    inbox: Sequence[object], *, identity: object | None = None
) -> tuple[BorderFrame, ...]:
    """Parse frames delivered through the runtime inbox."""
    if isinstance(inbox, (str, bytes)) or not isinstance(inbox, Sequence):
        raise TypeError("inbox must be a sequence")
    return tuple(
        frame for _, frame in _deliveries_from_inbox(inbox, identity=identity)
    )


__all__ = [
    "BORDER_FRAME_FIELD_COUNT",
    "BORDER_FRAME_MAX_CHARS",
    "BORDER_FRAME_MAX_RELATIONS",
    "BORDER_FRAME_SUBJECT",
    "BORDER_FRAME_VERSION",
    "BorderFrame",
    "BorderFrameError",
    "attach_border_relation",
    "border_claim_relation",
    "border_frames_from_inbox",
    "border_frames_from_observation",
    "encode_border_claim",
    "parse_border_claim",
    "parse_border_claim_relation",
]
