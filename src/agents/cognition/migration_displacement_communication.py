# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Bounded ``mdp_v1`` migration speech carried inside existing Talk/Ask/Tell.

A frame group is one to four colon-separated relations, each a complete
fourteen-part frame (a subject marker plus thirteen semantic fields). It is not
a new event, command, observer semantic type, or wire genre. The receiver binds
the frame to the verified speaker and assigns provenance from delivery; a
frame-declared provenance reference is only an untrusted claim and is never used
for lookup or independence. Logs carry reason codes and counts only.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from agents.cognition.migration_displacement import (
    MigrationCauseKind,
    MigrationCauseSource,
)
from agents.models import AgentId
from world.actions import Ask, Talk, Tell
from world.communications import CommunicationRelation
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.migration_displacement_communication"
)

MIGRATION_FRAME_SUBJECT: Final[str] = "mdp_v1"
MIGRATION_FRAME_VERSION: Final[str] = "migration-displacement-communication.v1"
MIGRATION_FRAME_MAX_CHARS: Final[int] = 256
MIGRATION_FRAME_MAX_RELATIONS: Final[int] = 4
# The subject marker plus thirteen semantic fields (fourteen colon-joined parts).
MIGRATION_FRAME_FIELD_COUNT: Final[int] = 14
MIGRATION_FRAME_MAX_ROUTE_TOKENS: Final[int] = 4
_MAX_RELATIONS_PER_COMMAND: Final[int] = 32
_MAX_TOKEN_CHARS: Final[int] = 128
_NONE: Final[str] = "-"
_ROUTE_SEPARATOR: Final[str] = "~"


class MigrationFrameError(ValueError):
    """Stable-code frame violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class MigrationFrameAct(StrEnum):
    """Closed speech acts a migration frame may carry."""

    REPORT_INTENT = "report_intent"
    REPORT_ROUTE = "report_route"
    REPORT_CAUSE = "report_cause"
    REPORT_CLUSTER = "report_cluster"
    REPORT_OUTCOME = "report_outcome"
    ASK_ROUTE = "ask_route"
    UNKNOWN = "unknown"


_ROUTE_REQUIRED_ACTS: Final[frozenset[MigrationFrameAct]] = frozenset(
    {MigrationFrameAct.REPORT_INTENT, MigrationFrameAct.REPORT_ROUTE}
)


def _token(value: object, code: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise MigrationFrameError(code)
    if not value:
        if allow_empty:
            return value
        raise MigrationFrameError(code)
    if (
        len(value) > _MAX_TOKEN_CHARS
        or value == _NONE
        or value != value.strip()
        or any(char in value for char in (":", "\n", "\r", _ROUTE_SEPARATOR))
        or any(ord(char) < 32 for char in value)
    ):
        raise MigrationFrameError(code)
    return value


def _optional_token(value: object, code: str) -> str | None:
    if value is None:
        return None
    return _token(value, code)


@dataclass(frozen=True, slots=True)
class MigrationFrame:
    """Exactly bounded semantic content of one delivered migration relation."""

    act: MigrationFrameAct
    speaker_ref: str
    subject_ref: str
    origin_ref: str
    route_refs: tuple[str, ...]
    destination_ref: str
    cause_kind: MigrationCauseKind
    source_kind: MigrationCauseSource
    cluster_ref: str | None
    confidence_q: int
    as_of_tick: int
    evidence_ref: str | None
    declared_provenance_ref: str | None

    def __post_init__(self) -> None:
        if type(self.act) is not MigrationFrameAct:
            raise MigrationFrameError("frame_act")
        _token(self.speaker_ref, "frame_speaker")
        _token(self.subject_ref, "frame_subject_ref")
        _token(self.origin_ref, "frame_origin", allow_empty=True)
        _token(self.destination_ref, "frame_destination", allow_empty=True)
        if isinstance(self.route_refs, (str, bytes)) or not isinstance(
            self.route_refs, Sequence
        ):
            raise MigrationFrameError("frame_route")
        route = tuple(_token(item, "frame_route") for item in self.route_refs)
        if len(route) > MIGRATION_FRAME_MAX_ROUTE_TOKENS:
            raise MigrationFrameError("frame_route_count")
        if len(set(route)) != len(route):
            raise MigrationFrameError("frame_route_duplicate")
        if self.act in _ROUTE_REQUIRED_ACTS:
            if not 2 <= len(route) <= MIGRATION_FRAME_MAX_ROUTE_TOKENS:
                raise MigrationFrameError("frame_route_count")
        elif self.act is not MigrationFrameAct.ASK_ROUTE and route:
            raise MigrationFrameError("frame_route_forbidden")
        if route:
            if self.origin_ref and self.origin_ref != route[0]:
                raise MigrationFrameError("frame_route_origin")
            if self.act in _ROUTE_REQUIRED_ACTS:
                if not self.origin_ref:
                    raise MigrationFrameError("frame_route_origin")
                if self.destination_ref != route[-1]:
                    raise MigrationFrameError("frame_route_destination")
        if self.act is MigrationFrameAct.REPORT_OUTCOME and not self.destination_ref:
            raise MigrationFrameError("frame_destination")
        object.__setattr__(self, "route_refs", route)
        if type(self.cause_kind) is not MigrationCauseKind:
            raise MigrationFrameError("frame_enum")
        if type(self.source_kind) is not MigrationCauseSource:
            raise MigrationFrameError("frame_enum")
        _optional_token(self.cluster_ref, "frame_cluster")
        if (
            isinstance(self.confidence_q, bool)
            or type(self.confidence_q) is not int
            or not 0 <= self.confidence_q <= 100
        ):
            raise MigrationFrameError("frame_confidence")
        if (
            isinstance(self.as_of_tick, bool)
            or type(self.as_of_tick) is not int
            or self.as_of_tick < 0
        ):
            raise MigrationFrameError("frame_tick")
        _optional_token(self.evidence_ref, "frame_evidence")
        _optional_token(self.declared_provenance_ref, "frame_provenance")


@dataclass(frozen=True, slots=True)
class MigrationFrameDelivery:
    """One delivered, speaker-bound frame. Provenance comes from delivery."""

    speaker_token: str
    speaker_owner: AgentId
    delivery_tick: int
    frame: MigrationFrame

    def __post_init__(self) -> None:
        if type(self.speaker_token) is not str or not self.speaker_token:
            raise MigrationFrameError("frame_speaker")
        if type(self.speaker_owner) is not AgentId:
            raise MigrationFrameError("frame_speaker")
        if (
            isinstance(self.delivery_tick, bool)
            or type(self.delivery_tick) is not int
            or self.delivery_tick < 0
        ):
            raise MigrationFrameError("frame_tick")
        if type(self.frame) is not MigrationFrame:
            raise MigrationFrameError("frame_type")


def _present(value: str | None) -> str:
    return _NONE if value is None or value == "" else value


def encode_migration_displacement_claim(frame: MigrationFrame) -> str:
    """Encode one frame as one bounded fourteen-part relation payload."""
    if type(frame) is not MigrationFrame:
        raise TypeError("frame must be MigrationFrame")
    text = ":".join(
        (
            MIGRATION_FRAME_SUBJECT,
            frame.act.value,
            frame.speaker_ref,
            frame.subject_ref,
            _present(frame.origin_ref),
            _ROUTE_SEPARATOR.join(frame.route_refs) or _NONE,
            _present(frame.destination_ref),
            frame.cause_kind.value,
            frame.source_kind.value,
            _present(frame.cluster_ref),
            str(frame.confidence_q),
            str(frame.as_of_tick),
            _present(frame.evidence_ref),
            _present(frame.declared_provenance_ref),
        )
    )
    if len(text) > MIGRATION_FRAME_MAX_CHARS:
        raise MigrationFrameError("frame_too_large")
    return text


def _parse_int(token: str, code: str) -> int:
    if not token.isdigit() or not token.isascii():
        raise MigrationFrameError(code)
    return int(token)


def _absent(token: str) -> str:
    return "" if token == _NONE else token


def parse_migration_displacement_claim(text: str) -> MigrationFrame:
    """Parse one relation payload into a frame or raise a stable code."""
    if type(text) is not str:
        raise TypeError("text must be str")
    if len(text) > MIGRATION_FRAME_MAX_CHARS:
        raise MigrationFrameError("frame_too_large")
    parts = text.split(":")
    if len(parts) != MIGRATION_FRAME_FIELD_COUNT:
        raise MigrationFrameError("frame_field_count")
    (
        marker,
        act_token,
        speaker,
        subject,
        origin,
        route_token,
        destination,
        cause_token,
        source_token,
        cluster,
        confidence_token,
        as_of_token,
        evidence,
        provenance,
    ) = parts
    if marker != MIGRATION_FRAME_SUBJECT:
        raise MigrationFrameError("frame_subject")
    try:
        act = MigrationFrameAct(act_token)
        cause_kind = MigrationCauseKind(cause_token)
        source_kind = MigrationCauseSource(source_token)
    except ValueError as exc:
        raise MigrationFrameError("frame_enum") from exc
    route = () if route_token == _NONE else tuple(route_token.split(_ROUTE_SEPARATOR))
    return MigrationFrame(
        act=act,
        speaker_ref=speaker,
        subject_ref=subject,
        origin_ref=_absent(origin),
        route_refs=route,
        destination_ref=_absent(destination),
        cause_kind=cause_kind,
        source_kind=source_kind,
        cluster_ref=None if cluster == _NONE else cluster,
        confidence_q=_parse_int(confidence_token, "frame_confidence"),
        as_of_tick=_parse_int(as_of_token, "frame_tick"),
        evidence_ref=None if evidence == _NONE else evidence,
        declared_provenance_ref=None if provenance == _NONE else provenance,
    )


def parse_migration_displacement_relation(relation: object) -> str:
    """Return the raw payload of one relation object or raise a stable code."""
    payload = getattr(relation, "object", None)
    if type(payload) is not str:
        raise MigrationFrameError("frame_relation")
    if getattr(relation, "subject", None) != MIGRATION_FRAME_SUBJECT:
        raise MigrationFrameError("frame_subject")
    return payload


def migration_displacement_claim_relation(
    frame: MigrationFrame,
) -> tuple[CommunicationRelation, ...]:
    """Build the relation atom(s) for one frame."""
    return (
        CommunicationRelation(
            subject=MIGRATION_FRAME_SUBJECT,
            predicate="relation",
            object=encode_migration_displacement_claim(frame),
        ),
    )


def _speech(command: object) -> Talk | Ask | Tell:
    if type(command) is Talk:
        return command
    if type(command) is Ask:
        return command
    if type(command) is Tell:
        return command
    raise MigrationFrameError("malformed_frame")


def attach_migration_displacement_relation(
    command: object, frame: MigrationFrame | Sequence[MigrationFrame]
) -> object:
    """Append one ``mdp_v1`` group to an existing speech command.

    The group holds one to four frames. Any other command type is rejected with
    ``malformed_frame`` and at most one group is accepted per command.
    """
    speech = _speech(command)
    frames: tuple[MigrationFrame, ...]
    if type(frame) is MigrationFrame:
        frames = (frame,)
    elif isinstance(frame, Sequence) and not isinstance(frame, (str, bytes)):
        frames = tuple(frame)
    else:
        raise TypeError("frame must be MigrationFrame or a sequence of frames")
    if not 1 <= len(frames) <= MIGRATION_FRAME_MAX_RELATIONS:
        raise MigrationFrameError("frame_count")
    if any(type(item) is not MigrationFrame for item in frames):
        raise TypeError("frame must be MigrationFrame")
    if any(
        relation.subject == MIGRATION_FRAME_SUBJECT
        for relation in speech.utterance.content.relations
    ):
        raise MigrationFrameError("frame_duplicate_group")
    additions: list[CommunicationRelation] = []
    for item in frames:
        additions.extend(migration_displacement_claim_relation(item))
    relations = tuple(speech.utterance.content.relations) + tuple(additions)
    if len(relations) > _MAX_RELATIONS_PER_COMMAND:
        raise MigrationFrameError("frame_relation_cap")
    content = replace(speech.utterance.content, relations=relations)
    utterance = replace(speech.utterance, content=content)
    return replace(speech, utterance=utterance)


def migration_frame_root_key(frame: MigrationFrame) -> str:
    """Content root of a claim, independent of speaker and declared provenance.

    Two deliveries with the same root key repeat one claim; they are never
    independent corroboration.
    """
    if type(frame) is not MigrationFrame:
        raise TypeError("frame must be MigrationFrame")
    material = "|".join(
        (
            frame.act.value,
            frame.subject_ref,
            frame.origin_ref,
            _ROUTE_SEPARATOR.join(frame.route_refs),
            frame.destination_ref,
            frame.cause_kind.value,
            _present(frame.cluster_ref),
            _present(frame.evidence_ref),
            str(frame.as_of_tick),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def independent_migration_root_count(
    deliveries: Sequence[MigrationFrameDelivery],
) -> int:
    """Count distinct claim roots; same-root repeats are not independent."""
    return len({migration_frame_root_key(item.frame) for item in deliveries})


def _group_frames(
    relations: Sequence[object], *, speaker_token: str
) -> tuple[MigrationFrame, ...]:
    payloads: list[str] = []
    for relation in relations:
        if getattr(relation, "subject", None) != MIGRATION_FRAME_SUBJECT:
            continue
        payload = getattr(relation, "object", None)
        if type(payload) is not str or len(payload) > MIGRATION_FRAME_MAX_CHARS:
            raise MigrationFrameError("frame_too_large")
        payloads.append(payload)
    if not payloads:
        return ()
    if len(payloads) > MIGRATION_FRAME_MAX_RELATIONS:
        raise MigrationFrameError("frame_count")
    frames = tuple(parse_migration_displacement_claim(item) for item in payloads)
    for frame in frames:
        if frame.speaker_ref != speaker_token:
            raise MigrationFrameError("frame_speaker_mismatch")
    return frames


def _has_group(relations: object) -> bool:
    if not isinstance(relations, Sequence) or isinstance(relations, (str, bytes)):
        return False
    return any(
        getattr(item, "subject", None) == MIGRATION_FRAME_SUBJECT for item in relations
    )


def _identity_entity(identity: object | None) -> EntityId | None:
    if identity is None:
        return None
    value = getattr(identity, "owner_entity_id", None)
    return value if type(value) is EntityId else None


def _agent_for_entity(identity: object | None, entity: object) -> AgentId | None:
    if identity is None or type(entity) is not EntityId:
        return None
    if getattr(identity, "owner_entity_id", None) == entity:
        owner = getattr(identity, "owner_id", None)
        return owner if type(owner) is AgentId else None
    for binding in getattr(identity, "counterparts", ()) or ():
        if getattr(binding, "entity_id", None) == entity:
            agent = getattr(binding, "agent_id", None)
            return agent if type(agent) is AgentId else None
    return None


def _deliveries_from_entries(
    entries: Sequence[tuple[object, object, int]],
    *,
    identity: object | None,
) -> tuple[list[MigrationFrameDelivery], int]:
    """Return deliveries and the number of dropped groups."""
    deliveries: list[MigrationFrameDelivery] = []
    dropped: dict[str, int] = {}
    for speaker, relations, tick in entries:
        if not _has_group(relations):
            continue
        speaker_owner = _agent_for_entity(identity, speaker)
        if speaker_owner is None or type(speaker) is not EntityId:
            dropped["unresolved_speaker"] = dropped.get("unresolved_speaker", 0) + 1
            continue
        try:
            frames = _group_frames(
                relations,  # type: ignore[arg-type]
                speaker_token=speaker.value,
            )
        except MigrationFrameError as exc:
            dropped[exc.code] = dropped.get(exc.code, 0) + 1
            continue
        except ValueError:
            dropped["frame_invalid"] = dropped.get("frame_invalid", 0) + 1
            continue
        deliveries.extend(
            MigrationFrameDelivery(
                speaker_token=speaker.value,
                speaker_owner=speaker_owner,
                delivery_tick=tick,
                frame=frame,
            )
            for frame in frames
        )
    for code in sorted(dropped):
        _LOG.warning(
            "migration_displacement_frame_dropped reason_code=%s count=%s",
            code,
            dropped[code],
        )
    if deliveries:
        _LOG.debug("migration_displacement_frame_delivered count=%s", len(deliveries))
    return deliveries, sum(dropped.values())


def _communication_entries(
    communications: Sequence[object],
    *,
    owner_entity: EntityId | None,
    default_tick: int,
) -> list[tuple[object, object, int]]:
    entries: list[tuple[object, object, int]] = []
    for communication in communications:
        listener = getattr(communication, "listener_id", None)
        if (
            owner_entity is not None
            and listener is not None
            and listener != owner_entity
        ):
            continue
        utterance = getattr(communication, "utterance", None)
        relations = getattr(getattr(utterance, "content", None), "relations", ())
        provenance = getattr(communication, "provenance", None)
        tick = getattr(provenance, "source_tick", default_tick)
        if isinstance(tick, bool) or type(tick) is not int or tick < 0:
            tick = default_tick
        entries.append((getattr(communication, "speaker_id", None), relations, tick))
    return entries


def _inbox_entries(
    inbox: Sequence[object], *, default_tick: int
) -> list[tuple[object, object, int]]:
    entries: list[tuple[object, object, int]] = []
    for entry in inbox:
        if type(entry) in (Talk, Ask, Tell):
            utterance = entry.utterance  # type: ignore[attr-defined]
            relations = utterance.content.relations
            speaker = utterance.declared.immediate_source_id
            entries.append((speaker, relations, default_tick))
            continue
        utterance = getattr(entry, "utterance", None)
        relations = getattr(getattr(utterance, "content", None), "relations", ())
        provenance = getattr(entry, "provenance", None)
        tick = getattr(provenance, "source_tick", default_tick)
        if isinstance(tick, bool) or type(tick) is not int or tick < 0:
            tick = default_tick
        entries.append((getattr(entry, "speaker_id", None), relations, tick))
    return entries


def migration_displacement_frame_deliveries(
    communications: Sequence[object],
    identity: object | None,
    *,
    default_tick: int = 0,
) -> tuple[MigrationFrameDelivery, ...]:
    """Return speaker-bound deliveries from observed communications."""
    if isinstance(communications, (str, bytes)) or not isinstance(
        communications, Sequence
    ):
        raise TypeError("communications must be a sequence")
    entries = _communication_entries(
        communications,
        owner_entity=_identity_entity(identity),
        default_tick=default_tick,
    )
    deliveries, _ = _deliveries_from_entries(entries, identity=identity)
    return tuple(deliveries)


def migration_displacement_inbox_deliveries(
    inbox: Sequence[object],
    identity: object | None,
    *,
    default_tick: int = 0,
) -> tuple[MigrationFrameDelivery, ...]:
    """Return speaker-bound deliveries from the runtime inbox."""
    if isinstance(inbox, (str, bytes)) or not isinstance(inbox, Sequence):
        raise TypeError("inbox must be a sequence")
    entries = _inbox_entries(inbox, default_tick=default_tick)
    deliveries, _ = _deliveries_from_entries(entries, identity=identity)
    return tuple(deliveries)


def scan_migration_displacement_deliveries(
    observation: object | None,
    inbox: object | None,
    identity: object | None,
    *,
    default_tick: int,
) -> tuple[tuple[MigrationFrameDelivery, ...], int]:
    """Return all deliveries for one owner plus the dropped-group count."""
    entries: list[tuple[object, object, int]] = []
    communications = getattr(observation, "communications", ()) or ()
    if isinstance(communications, Sequence) and not isinstance(
        communications, (str, bytes)
    ):
        entries.extend(
            _communication_entries(
                communications,
                owner_entity=_identity_entity(identity),
                default_tick=default_tick,
            )
        )
    if (
        inbox is not None
        and isinstance(inbox, Sequence)
        and not isinstance(inbox, (str, bytes))
    ):
        entries.extend(_inbox_entries(inbox, default_tick=default_tick))
    deliveries, dropped = _deliveries_from_entries(entries, identity=identity)
    return tuple(deliveries), dropped


def migration_displacement_frames_from_observation(
    observation: object, identity: object | None = None
) -> tuple[MigrationFrame, ...]:
    """Parse speaker-bound frames delivered through one owner's observation."""
    communications = getattr(observation, "communications", ()) or ()
    return tuple(
        item.frame
        for item in migration_displacement_frame_deliveries(
            tuple(communications), identity
        )
    )


def migration_displacement_frames_from_inbox(
    inbox: Sequence[object], identity: object | None = None
) -> tuple[MigrationFrame, ...]:
    """Parse speaker-bound frames delivered through the runtime inbox."""
    return tuple(
        item.frame for item in migration_displacement_inbox_deliveries(inbox, identity)
    )


__all__ = [
    "MIGRATION_FRAME_FIELD_COUNT",
    "MIGRATION_FRAME_MAX_CHARS",
    "MIGRATION_FRAME_MAX_RELATIONS",
    "MIGRATION_FRAME_MAX_ROUTE_TOKENS",
    "MIGRATION_FRAME_SUBJECT",
    "MIGRATION_FRAME_VERSION",
    "MigrationFrame",
    "MigrationFrameAct",
    "MigrationFrameDelivery",
    "MigrationFrameError",
    "attach_migration_displacement_relation",
    "encode_migration_displacement_claim",
    "independent_migration_root_count",
    "migration_displacement_claim_relation",
    "migration_displacement_frame_deliveries",
    "migration_displacement_frames_from_inbox",
    "migration_displacement_frames_from_observation",
    "migration_displacement_inbox_deliveries",
    "migration_frame_root_key",
    "parse_migration_displacement_claim",
    "parse_migration_displacement_relation",
    "scan_migration_displacement_deliveries",
]
