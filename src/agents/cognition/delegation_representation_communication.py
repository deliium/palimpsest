"""Bounded ``rep_v1`` representation claims inside existing speech.

A delegation, acceptance, rejection, support, opposition, revocation, or
resignation travels as one closed ``CommunicationRelation`` atom inside ordinary
``Talk``/``Ask``/``Tell`` speech. Delivery proves that speech happened; it never
proves standing, legitimacy, or a binding mandate.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, NoReturn, cast

from agents.cognition.delegation_representation import (
    REPRESENTATION_MANDATE_ID_PREFIX,
    RepresentationDurationKind,
    RepresentationError,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
    require_representation_id,
    require_representation_scope_subject,
    require_representation_token,
)
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)

__all__ = [
    "REPRESENTATION_FRAME_FIELD_COUNT",
    "REPRESENTATION_FRAME_MAX_CHARS",
    "REPRESENTATION_FRAME_SUBJECT",
    "REPRESENTATION_FRAME_VERSION",
    "REPRESENTATION_PREDICATES",
    "RepresentationAct",
    "RepresentationFrame",
    "encode_representation_frame",
    "parse_representation_frame",
    "parse_representation_frame_relation",
    "representation_communicate_utterance",
    "representation_frame_party_matches",
    "representation_frame_relation",
    "representation_frames_from_observation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.delegation_representation_communication"
)

REPRESENTATION_FRAME_VERSION: Final[str] = "rep_v1"
REPRESENTATION_FRAME_SUBJECT: Final[str] = "rep_v1"
REPRESENTATION_FRAME_MAX_CHARS: Final[int] = 256
REPRESENTATION_FRAME_FIELD_COUNT: Final[int] = 11
_NONE_TOKEN: Final[str] = "none"
_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]*$")


class RepresentationAct(StrEnum):
    """Closed representation speech act."""

    CLAIM = "rep_claim"
    DELEGATE = "rep_delegate"
    ACCEPT = "rep_accept"
    REJECT = "rep_reject"
    SUPPORT = "rep_support"
    OPPOSE = "rep_oppose"
    ABSTAIN = "rep_abstain"
    REVOKE = "rep_revoke"
    RESIGN = "rep_resign"
    REPORT = "rep_report"


REPRESENTATION_PREDICATES: Final[Mapping[RepresentationAct, str]] = MappingProxyType(
    {
        RepresentationAct.CLAIM: "rep_claim",
        RepresentationAct.DELEGATE: "rep_delegate",
        RepresentationAct.ACCEPT: "rep_accept",
        RepresentationAct.REJECT: "rep_reject",
        RepresentationAct.SUPPORT: "rep_support",
        RepresentationAct.OPPOSE: "rep_oppose",
        RepresentationAct.ABSTAIN: "rep_abstain",
        RepresentationAct.REVOKE: "rep_revoke",
        RepresentationAct.RESIGN: "rep_resign",
        RepresentationAct.REPORT: "rep_report",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, RepresentationAct]] = MappingProxyType(
    {predicate: act for act, predicate in REPRESENTATION_PREDICATES.items()}
)

_FRAME_KEYS: Final[tuple[str, ...]] = (
    "act",
    "mandate_ref",
    "principal_kind",
    "principal_ref",
    "representative_ref",
    "scope_kind",
    "scope_subject",
    "duration_kind",
    "end_tick",
    "provenance",
    "revision",
)
assert len(_FRAME_KEYS) == REPRESENTATION_FRAME_FIELD_COUNT


def _fail() -> NoReturn:
    raise RepresentationError("representation_untrusted_frame")


def _optional_token(value: object) -> str | None:
    if value is None:
        return None
    return require_representation_token(value, max_chars=128)


def _optional_enum[EnumT: StrEnum](
    value: object, enum_type: type[EnumT]
) -> EnumT | None:
    if value is None:
        return None
    if type(value) is not enum_type:
        _fail()
    return value


@dataclass(frozen=True, slots=True)
class RepresentationFrame:
    """One closed, self-authored representation speech atom."""

    act: RepresentationAct
    mandate_ref: str | None = None
    principal_kind: RepresentationPrincipalKind | None = None
    principal_ref: str | None = None
    representative_ref: str | None = None
    scope_kind: RepresentationScopeKind | None = None
    scope_subject: str | None = None
    duration_kind: RepresentationDurationKind | None = None
    end_tick: int | None = None
    provenance: RepresentationProvenance | None = None
    revision: int = 0
    actor_ref: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not RepresentationAct:
            _fail()
        if self.mandate_ref is not None:
            object.__setattr__(
                self,
                "mandate_ref",
                require_representation_id(
                    self.mandate_ref, REPRESENTATION_MANDATE_ID_PREFIX
                ),
            )
        object.__setattr__(
            self,
            "principal_kind",
            _optional_enum(self.principal_kind, RepresentationPrincipalKind),
        )
        object.__setattr__(self, "principal_ref", _optional_token(self.principal_ref))
        representative = _optional_token(self.representative_ref)
        if representative is None:
            _fail()
        object.__setattr__(self, "representative_ref", representative)
        object.__setattr__(
            self, "scope_kind", _optional_enum(self.scope_kind, RepresentationScopeKind)
        )
        if self.scope_subject is not None:
            object.__setattr__(
                self,
                "scope_subject",
                require_representation_scope_subject(self.scope_subject),
            )
        object.__setattr__(
            self,
            "duration_kind",
            _optional_enum(self.duration_kind, RepresentationDurationKind),
        )
        if self.end_tick is not None and (
            type(self.end_tick) is not int
            or isinstance(self.end_tick, bool)
            or self.end_tick < 0
        ):
            _fail()
        object.__setattr__(
            self,
            "provenance",
            _optional_enum(self.provenance, RepresentationProvenance),
        )
        object.__setattr__(self, "actor_ref", _optional_token(self.actor_ref))
        if type(self.revision) is not int or isinstance(self.revision, bool):
            _fail()
        if self.revision < 0:
            _fail()
        if self.act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}:
            if self.mandate_ref is not None:
                _fail()
            if self.principal_kind is None or self.scope_kind is None:
                _fail()
            if self.duration_kind is None:
                _fail()
            if self.provenance is None:
                _fail()
        else:
            if self.mandate_ref is None:
                _fail()
        if self.principal_kind is RepresentationPrincipalKind.UNKNOWN:
            if self.principal_ref is not None:
                _fail()
        if (
            self.act
            in {
                RepresentationAct.CLAIM,
                RepresentationAct.DELEGATE,
                RepresentationAct.ACCEPT,
                RepresentationAct.REJECT,
                RepresentationAct.REVOKE,
            }
            and self.principal_kind is not RepresentationPrincipalKind.UNKNOWN
        ):
            if self.principal_ref is None:
                _fail()


def _encode_field(value: object) -> str:
    if value is None:
        return _NONE_TOKEN
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def encode_representation_frame(frame: RepresentationFrame) -> str:
    """Encode one frame into the bounded ``rep_v1`` payload."""

    if type(frame) is not RepresentationFrame:
        raise TypeError("frame must be RepresentationFrame")
    fields = tuple(_encode_field(getattr(frame, name)) for name in _FRAME_KEYS[1:])
    text = f"{REPRESENTATION_FRAME_SUBJECT}:{REPRESENTATION_PREDICATES[frame.act]}:" + (
        ":".join(fields)
    )
    if len(text) > REPRESENTATION_FRAME_MAX_CHARS:
        raise RepresentationError("representation_frame_too_large")
    return text


def parse_representation_frame(text: str) -> RepresentationFrame | None:
    """Parse one strict ``rep_v1`` frame; malformed text returns ``None``."""

    try:
        if type(text) is not str or len(text) > REPRESENTATION_FRAME_MAX_CHARS:
            return None
        if any(character.isspace() or ord(character) < 32 for character in text):
            return None
        parts = text.split(":")
        if len(parts) != REPRESENTATION_FRAME_FIELD_COUNT + 1:
            return None
        subject, predicate, *fields = parts
        if subject != REPRESENTATION_FRAME_SUBJECT:
            return None
        act = _PREDICATE_TO_ACT.get(predicate)
        if act is None:
            return None
        values = {
            name: (None if raw == _NONE_TOKEN else raw)
            for name, raw in zip(_FRAME_KEYS[1:], fields, strict=True)
        }
        principal_raw = values["principal_kind"]
        scope_raw = values["scope_kind"]
        duration_raw = values["duration_kind"]
        provenance_raw = values["provenance"]
        end_raw = values["end_tick"]
        revision_raw = values["revision"]
        if revision_raw is None:
            return None
        return RepresentationFrame(
            act=act,
            mandate_ref=values["mandate_ref"],
            principal_kind=(
                None
                if principal_raw is None
                else RepresentationPrincipalKind(principal_raw)
            ),
            principal_ref=values["principal_ref"],
            representative_ref=values["representative_ref"],
            scope_kind=(
                None if scope_raw is None else RepresentationScopeKind(scope_raw)
            ),
            scope_subject=values["scope_subject"],
            duration_kind=(
                None
                if duration_raw is None
                else RepresentationDurationKind(duration_raw)
            ),
            end_tick=None if end_raw is None else int(end_raw),
            provenance=(
                None
                if provenance_raw is None
                else RepresentationProvenance(provenance_raw)
            ),
            revision=int(revision_raw),
        )
    except (RepresentationError, TypeError, ValueError):
        _LOG.debug("representation_frame_rejected reason=malformed")
        return None


def representation_frame_relation(frame: RepresentationFrame) -> CommunicationRelation:
    """Build the ``(subject, predicate, object)`` atom for one frame."""

    if type(frame) is not RepresentationFrame:
        raise TypeError("frame must be RepresentationFrame")
    text = encode_representation_frame(frame)
    subject, predicate, *fields = text.split(":")
    return CommunicationRelation(
        subject=subject, predicate=predicate, object=":".join(fields)
    )


def parse_representation_frame_relation(
    subject: str, predicate: str, object_text: str
) -> RepresentationFrame | None:
    """Parse one relation atom; unrelated atoms return ``None``."""

    if subject != REPRESENTATION_FRAME_SUBJECT:
        return None
    if type(predicate) is not str or predicate not in _PREDICATE_TO_ACT:
        return None
    if type(object_text) is not str:
        return None
    return parse_representation_frame(f"{subject}:{predicate}:{object_text}")


def representation_frame_party_matches(
    frame: RepresentationFrame, verified_speaker: object
) -> bool:
    """Return whether the frame attributes the act to the verified speaker."""

    if type(frame) is not RepresentationFrame:
        return False
    speaker = (
        verified_speaker
        if type(verified_speaker) is str
        else getattr(verified_speaker, "value", None)
    )
    if type(speaker) is not str or not speaker:
        return False
    if frame.act in {RepresentationAct.CLAIM, RepresentationAct.RESIGN}:
        return frame.representative_ref == speaker
    if frame.act is RepresentationAct.DELEGATE:
        return (
            frame.principal_kind is RepresentationPrincipalKind.AGENT
            and frame.principal_ref == speaker
            and frame.representative_ref != speaker
        )
    if frame.act in {RepresentationAct.ACCEPT, RepresentationAct.REJECT}:
        return (
            frame.principal_kind is RepresentationPrincipalKind.AGENT
            and frame.principal_ref == speaker
        )
    if frame.act is RepresentationAct.REVOKE:
        return speaker in {frame.principal_ref, frame.representative_ref}
    return True


def representation_frames_from_observation(
    observation: object, *, owner_id: object
) -> tuple[RepresentationFrame, ...]:
    """Collect party-verified ``rep_v1`` frames from one owner's observation."""

    owner = getattr(owner_id, "value", owner_id)
    if type(owner) is not str or not owner:
        raise ValueError("owner_id must be a non-empty token")
    frames: list[RepresentationFrame] = []
    for communication in getattr(observation, "communications", ()):
        speaker = getattr(getattr(communication, "speaker_id", None), "value", None)
        utterance = getattr(communication, "utterance", None)
        content = getattr(utterance, "content", None)
        for relation in getattr(content, "relations", ()):
            frame = parse_representation_frame_relation(
                getattr(relation, "subject", ""),
                getattr(relation, "predicate", ""),
                getattr(relation, "object", ""),
            )
            if frame is None:
                continue
            if representation_frame_party_matches(frame, speaker):
                frames.append(replace(frame, actor_ref=speaker))
    frames.sort(
        key=lambda frame: (
            frame.mandate_ref or "",
            frame.act.value,
            frame.principal_ref or "",
            frame.representative_ref or "",
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


def representation_communicate_utterance(
    command: object,
    frame: RepresentationFrame,
    *,
    max_relations: int = 32,
) -> object:
    """Attach at most one ``rep_v1`` relation to an already-selected utterance."""

    if type(frame) is not RepresentationFrame:
        raise TypeError("frame must be RepresentationFrame")
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
        relation.subject == REPRESENTATION_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= max_relations:
        _LOG.warning("representation_frame_skipped reason=relation_limit")
        return command
    declared = getattr(utterance, "declared", None)
    speaker = getattr(declared, "immediate_source_id", None)
    if speaker is None:
        _LOG.warning("representation_frame_skipped reason=missing_speaker")
        return command
    if not representation_frame_party_matches(frame, speaker):
        _LOG.warning("representation_frame_party_mismatch")
        return command
    try:
        relation = representation_frame_relation(frame)
    except (RepresentationError, TypeError, ValueError):
        _LOG.warning("representation_frame_skipped reason=invalid_frame")
        return command
    updated = origin_utterance(
        text="representation",
        speaker_id=speaker,
        communication_id=f"representation-{frame.act.value}",
        relations=(*relations, relation),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    _LOG.debug("representation_frame_encoded act=%s", frame.act.value)
    typed = cast(Any, command)
    return typed.__class__(recipient_id=typed.recipient_id, utterance=updated)
