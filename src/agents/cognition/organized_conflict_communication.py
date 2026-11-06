# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Bounded ``ocf_v1`` conflict speech claims.

``ocf_v1`` is one frozen 12-field subject carried as at most one relation inside
existing ``Talk``/``Ask``/``Tell`` speech. It is not a new command, event, wire
record, or free-text channel. Peer-declared targets, sides, roles, and plan
references are untrusted; the receiver assigns provenance from delivery and
verifies the speaker before retaining anything.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Final

from agents.cognition.organized_conflict import (
    ORGANIZED_CONFLICT_FRAME_FIELD_COUNT,
    ORGANIZED_CONFLICT_FRAME_MAX_CHARS,
    ORGANIZED_CONFLICT_FRAME_VERSION,
    ConflictOperation,
    ConflictRole,
    ConflictTargetKind,
    OrganizedConflictError,
    conflict_target_token,
)
from world.actions import AgentCommand, Ask, Talk, Tell
from world.communications import CommunicationRelation, StructuredUtterance

__all__ = [
    "CONFLICT_FRAME_FIELD_COUNT",
    "CONFLICT_FRAME_MAX_CHARS",
    "CONFLICT_FRAME_VERSION",
    "ConflictAct",
    "ConflictFrame",
    "conflict_communicate_utterance",
    "conflict_frame_party_matches",
    "conflict_frame_relation",
    "conflict_frames_from_command",
    "conflict_frames_from_observation",
    "encode_conflict_frame",
    "parse_conflict_frame",
    "parse_conflict_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.organized_conflict.communication"
)

CONFLICT_FRAME_VERSION: Final[str] = ORGANIZED_CONFLICT_FRAME_VERSION
CONFLICT_FRAME_MAX_CHARS: Final[int] = ORGANIZED_CONFLICT_FRAME_MAX_CHARS
CONFLICT_FRAME_FIELD_COUNT: Final[int] = ORGANIZED_CONFLICT_FRAME_FIELD_COUNT

_MAX_PARTICIPANTS: Final[int] = 4
_NONE: Final[str] = "none"
_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{16}$")
_PLAN_RE: Final[re.Pattern[str]] = re.compile(r"^ocp-[0-9a-f]{16}$")
_EPISODE_RE: Final[re.Pattern[str]] = re.compile(r"^oce-[0-9a-f]{16}$")
_CONTROL_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f\s]")


class ConflictAct(StrEnum):
    """Closed ``ocf_v1`` speech act."""

    PROPOSE = "propose"
    JOIN = "join"
    DECLINE = "decline"
    WITHDRAW = "withdraw"
    COORDINATE = "coordinate"
    REPORT = "report"
    INTERPRET = "interpret"
    CONCLUDE = "conclude"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ConflictFrame:
    """Exactly twelve bounded fields. No free text, no durable anchor."""

    act: ConflictAct
    plan_ref: str = _NONE
    episode_ref: str = _NONE
    operation: ConflictOperation | None = None
    target_kind: ConflictTargetKind | None = None
    target_ref: str = _NONE
    role: ConflictRole | None = None
    side_ref: str = _NONE
    window_start: int | None = None
    window_end: int | None = None
    participant_refs: tuple[str, ...] = ()
    subject: str = CONFLICT_FRAME_VERSION

    def __post_init__(self) -> None:
        if self.subject != CONFLICT_FRAME_VERSION:
            raise OrganizedConflictError("organized_conflict_frame_invalid")
        if type(self.act) is not ConflictAct:
            raise TypeError("ConflictFrame.act must be ConflictAct")
        if self.plan_ref != _NONE and _PLAN_RE.match(self.plan_ref) is None:
            raise OrganizedConflictError("organized_conflict_frame_invalid")
        if self.episode_ref != _NONE and _EPISODE_RE.match(self.episode_ref) is None:
            raise OrganizedConflictError("organized_conflict_frame_invalid")
        if self.operation is not None and type(self.operation) is not ConflictOperation:
            raise TypeError("ConflictFrame.operation must be ConflictOperation or None")
        if (
            self.target_kind is not None
            and type(self.target_kind) is not ConflictTargetKind
        ):
            raise TypeError(
                "ConflictFrame.target_kind must be ConflictTargetKind or None"
            )
        if self.target_ref != _NONE and _HEX_RE.match(self.target_ref) is None:
            raise OrganizedConflictError("organized_conflict_frame_invalid")
        if self.role is not None and type(self.role) is not ConflictRole:
            raise TypeError("ConflictFrame.role must be ConflictRole or None")
        if self.side_ref != _NONE and _HEX_RE.match(self.side_ref) is None:
            raise OrganizedConflictError("organized_conflict_frame_invalid")
        for name in ("window_start", "window_end"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise TypeError(f"ConflictFrame.{name} must be a non-negative int")
        if isinstance(self.participant_refs, (str, bytes, set, frozenset)):
            raise TypeError("ConflictFrame.participant_refs must be an ordered tuple")
        participants = tuple(self.participant_refs)
        if len(participants) > _MAX_PARTICIPANTS:
            raise ValueError("ConflictFrame.participant_refs exceeds the cap")
        if len(set(participants)) != len(participants):
            raise ValueError("ConflictFrame.participant_refs contains duplicates")
        for participant in participants:
            if _HEX_RE.match(participant) is None:
                raise OrganizedConflictError("organized_conflict_frame_invalid")
        object.__setattr__(self, "participant_refs", participants)

    @property
    def field_count(self) -> int:
        return CONFLICT_FRAME_FIELD_COUNT


def _encode_optional(value: object | None) -> str:
    if value is None:
        return _NONE
    if isinstance(value, StrEnum):
        return value.value
    return str(value)


def encode_conflict_frame(frame: ConflictFrame) -> str:
    """Encode one frame to its 12-field pipe form, bounded at 256 characters."""

    if type(frame) is not ConflictFrame:
        raise TypeError("frame must be ConflictFrame")
    fields = (
        CONFLICT_FRAME_VERSION,
        frame.act.value,
        frame.plan_ref,
        frame.episode_ref,
        _encode_optional(frame.operation),
        _encode_optional(frame.target_kind),
        frame.target_ref,
        _encode_optional(frame.role),
        frame.side_ref,
        _encode_optional(frame.window_start),
        _encode_optional(frame.window_end),
        ",".join(frame.participant_refs) if frame.participant_refs else _NONE,
    )
    text = "|".join(fields)
    if len(text) > CONFLICT_FRAME_MAX_CHARS:
        _LOG.debug("organized_conflict_frame_dropped reason=oversize count=1")
        raise OrganizedConflictError("organized_conflict_frame_too_large")
    if _CONTROL_RE.search(text) is not None:
        raise OrganizedConflictError("organized_conflict_frame_invalid")
    return text


def _parse_optional_enum(value: str, enum_type: type[StrEnum]) -> Any:
    if value == _NONE:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _parse_optional_int(value: str) -> int | None:
    if value == _NONE:
        return None
    if not value.isdigit():
        return None
    return int(value)


def parse_conflict_frame(text: str) -> ConflictFrame | None:
    """Parse one bounded frame, returning ``None`` on any malformed input."""

    if type(text) is not str or not text or len(text) > CONFLICT_FRAME_MAX_CHARS:
        return None
    if _CONTROL_RE.search(text) is not None:
        return None
    fields = text.split("|")
    if len(fields) != CONFLICT_FRAME_FIELD_COUNT:
        return None
    (
        subject,
        act_text,
        plan_ref,
        episode_ref,
        operation_text,
        target_kind_text,
        target_ref,
        role_text,
        side_ref,
        window_start_text,
        window_end_text,
        participants_text,
    ) = fields
    if subject != CONFLICT_FRAME_VERSION:
        return None
    try:
        act = ConflictAct(act_text)
    except ValueError:
        return None
    operation = _parse_optional_enum(operation_text, ConflictOperation)
    target_kind = _parse_optional_enum(target_kind_text, ConflictTargetKind)
    role = _parse_optional_enum(role_text, ConflictRole)
    if operation_text != _NONE and operation is None:
        return None
    if target_kind_text != _NONE and target_kind is None:
        return None
    if role_text != _NONE and role is None:
        return None
    window_start = _parse_optional_int(window_start_text)
    window_end = _parse_optional_int(window_end_text)
    if window_start_text != _NONE and window_start is None:
        return None
    if window_end_text != _NONE and window_end is None:
        return None
    if (
        window_start is not None
        and window_end is not None
        and window_end < window_start
    ):
        return None
    if participants_text == _NONE:
        participants: tuple[str, ...] = ()
    else:
        participants = tuple(participants_text.split(","))
    try:
        return ConflictFrame(
            act=act,
            plan_ref=plan_ref,
            episode_ref=episode_ref,
            operation=operation,
            target_kind=target_kind,
            target_ref=target_ref,
            role=role,
            side_ref=side_ref,
            window_start=window_start,
            window_end=window_end,
            participant_refs=participants,
        )
    except (TypeError, ValueError):
        return None


def conflict_frame_relation(frame: ConflictFrame) -> CommunicationRelation:
    """Map one frame to one existing speech relation."""

    text = encode_conflict_frame(frame)
    _, predicate, remainder = text.split("|", 2)
    return CommunicationRelation(
        subject=CONFLICT_FRAME_VERSION, predicate=predicate, object=remainder
    )


def parse_conflict_frame_relation(
    subject: str, predicate: str, object: str
) -> ConflictFrame | None:
    """Reassemble one relation and parse the frame; reject foreign subjects."""

    if subject != CONFLICT_FRAME_VERSION:
        return None
    if (
        type(predicate) is not str
        or type(object) is not str
        or not predicate
        or not object
    ):
        return None
    return parse_conflict_frame(f"{subject}|{predicate}|{object}")


def conflict_frame_party_matches(frame: ConflictFrame, verified_speaker: str) -> bool:
    """A speaker may only claim its own side/participation."""

    expected = conflict_target_token(verified_speaker)
    if frame.side_ref != expected:
        return False
    if frame.act in {
        ConflictAct.JOIN,
        ConflictAct.DECLINE,
        ConflictAct.WITHDRAW,
    }:
        return (
            len(frame.participant_refs) == 1 and frame.participant_refs[0] == expected
        )
    return True


def _utterance_frames(utterance: StructuredUtterance) -> tuple[ConflictFrame, ...]:
    frames: list[ConflictFrame] = []
    for relation in utterance.content.relations:
        if relation.subject != CONFLICT_FRAME_VERSION:
            continue
        frame = parse_conflict_frame_relation(
            relation.subject, relation.predicate, relation.object
        )
        if frame is not None:
            frames.append(frame)
    return tuple(frames)


def conflict_frames_from_observation(
    observation: object,
) -> tuple[ConflictFrame | None, ...]:
    """Return parsed frames from delivered speech, or ``None`` for drops."""

    frames: list[ConflictFrame | None] = []
    for communication in getattr(observation, "communications", ()):
        speaker = getattr(communication, "speaker_id", None)
        speaker_value = getattr(speaker, "value", None)
        if not speaker_value:
            continue
        for frame in _utterance_frames(communication.utterance):
            if not conflict_frame_party_matches(frame, str(speaker_value)):
                _LOG.debug(
                    "organized_conflict_frame_dropped reason=speaker_mismatch count=1"
                )
                frames.append(None)
                continue
            frames.append(frame)
    return tuple(frames)


def conflict_frames_from_command(
    command: AgentCommand, owner_id: object
) -> tuple[ConflictFrame, ...]:
    """Return the owner's own ``ocf_v1`` frames from a selected speech command."""

    if not isinstance(command, (Talk, Ask, Tell)):
        return ()
    owner_value = getattr(owner_id, "value", None)
    if not owner_value:
        return ()
    speaker = command.utterance.declared.immediate_source_id
    if getattr(speaker, "value", None) != owner_value:
        return ()
    frames: list[ConflictFrame] = []
    for frame in _utterance_frames(command.utterance):
        if not conflict_frame_party_matches(frame, str(owner_value)):
            _LOG.debug(
                "organized_conflict_frame_dropped reason=speaker_mismatch count=1"
            )
            continue
        frames.append(frame)
    return tuple(frames)


def conflict_communicate_utterance(
    command: AgentCommand,
    frame: ConflictFrame,
    *,
    owner_id: object,
    tick: int,
) -> AgentCommand:
    """Attach at most one ``ocf_v1`` relation to an already-selected speech command."""

    if not isinstance(command, (Talk, Ask, Tell)):
        raise TypeError("command must be Talk, Ask, or Tell")
    speech = command
    if type(tick) is not int or tick < 0:
        raise TypeError("tick must be a non-negative int")
    owner_value = getattr(owner_id, "value", None)
    speaker = speech.utterance.declared.immediate_source_id
    if not owner_value or getattr(speaker, "value", None) != owner_value:
        raise OrganizedConflictError("organized_conflict_frame_speaker_mismatch")
    if not conflict_frame_party_matches(frame, str(owner_value)):
        raise OrganizedConflictError("organized_conflict_frame_speaker_mismatch")
    if any(
        relation.subject == CONFLICT_FRAME_VERSION
        for relation in speech.utterance.content.relations
    ):
        raise OrganizedConflictError("organized_conflict_duplicate_relation")
    relation = conflict_frame_relation(frame)
    content = speech.utterance.content
    if len(content.relations) >= 32:
        raise OrganizedConflictError("organized_conflict_relation_cap")
    updated = replace(
        speech.utterance,
        content=replace(
            content,
            text=CONFLICT_FRAME_VERSION,
            relations=(*content.relations, relation),
        ),
    )
    _LOG.debug(
        "organized_conflict_utterance_attached act=%s tick=%s",
        frame.act.value,
        tick,
    )
    return replace(speech, utterance=updated)
