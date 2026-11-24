"""Bounded ``cgo_v1`` commons-governance frames inside ordinary speech.

One addressed ``Talk``/``Tell`` may carry at most one ``cgo_v1`` relation. The
frame is fallible testimony: it never grants entitlement, proves a draw, or
binds a peer. Malformed, oversized, or non-canonical frames are rejected.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from world.actions import Talk, Tell
from world.communications import CommunicationRelation
from world.identifiers import EntityId

__all__ = [
    "CGO_FRAME_MAX_CHARS",
    "CGO_FRAME_MAX_RELATIONS",
    "CGO_FRAME_SUBJECT",
    "CGO_NONE_TOKEN",
    "CGO_RELATION_PREDICATES",
    "CommonsAct",
    "CommonsFrame",
    "CommonsFrameError",
    "CommonsTopic",
    "attach_commons_frame",
    "commons_frame_relation",
    "encode_commons_frame",
    "parse_commons_frame",
    "parse_commons_frame_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.commons_governance_communication"
)

CGO_FRAME_SUBJECT: Final[str] = "cgo_v1"
CGO_FRAME_MAX_CHARS: Final[int] = 256
CGO_FRAME_MAX_RELATIONS: Final[int] = 1
CGO_NONE_TOKEN: Final[str] = "none"

_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PROPOSAL_RE: Final[re.Pattern[str]] = re.compile(r"^cgp-[0-9a-f]{32}$")
_DIGITS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_CONTROL_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f\s]")


class CommonsFrameError(ValueError):
    """Strict ``cgo_v1`` frame failure with a stable reason code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CommonsAct(StrEnum):
    """Closed commons-governance speech act."""

    PROPOSE = "propose"
    SUPPORT = "support"
    OPPOSE = "oppose"
    CLAIM_ACCESS = "claim_access"
    REPORT_USE = "report_use"
    REPORT_REST = "report_rest"
    CRITICIZE = "criticize"


class CommonsTopic(StrEnum):
    """Closed arrangement topic carried by a ``cgo_v1`` frame."""

    REST = "rest"
    TURN = "turn"
    ACCESS = "access"


CGO_RELATION_PREDICATES: Final[Mapping[CommonsAct, str]] = MappingProxyType(
    {
        CommonsAct.PROPOSE: "cgo_propose",
        CommonsAct.SUPPORT: "cgo_support",
        CommonsAct.OPPOSE: "cgo_oppose",
        CommonsAct.CLAIM_ACCESS: "cgo_claim_access",
        CommonsAct.REPORT_USE: "cgo_report_use",
        CommonsAct.REPORT_REST: "cgo_report_rest",
        CommonsAct.CRITICIZE: "cgo_criticize",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, CommonsAct]] = MappingProxyType(
    {predicate: act for act, predicate in CGO_RELATION_PREDICATES.items()}
)


def _fail(code: str) -> NoReturn:
    _LOG.debug("commons_frame_invalid reason_code=%s count=1", code)
    raise CommonsFrameError(code)


def _require_token(value: object, *, code: str) -> str:
    if type(value) is not str or not value or _TOKEN_RE.match(value) is None:
        _fail(code)
    if "|" in value:
        _fail(code)
    return value


def _require_optional_entity(value: EntityId | None) -> EntityId | None:
    if value is None:
        return None
    if type(value) is not EntityId:
        _fail("commons_frame_peer_invalid")
    _require_token(value.value, code="commons_frame_peer_invalid")
    return value


def _require_optional_proposal(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _PROPOSAL_RE.match(value) is None:
        _fail("commons_frame_proposal_invalid")
    return value


def _require_optional_tick(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or type(value) is not int or value < 0:
        _fail("commons_frame_tick_invalid")
    return value


@dataclass(frozen=True, slots=True)
class CommonsFrame:
    """One closed ``cgo_v1`` claim. Absent optional fields use the sentinel."""

    act: CommonsAct
    topic: CommonsTopic
    stock_id: EntityId
    peer_id: EntityId | None = None
    proposal_id: str | None = None
    reported_tick: int | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not CommonsAct:
            _fail("commons_frame_act_invalid")
        if type(self.topic) is not CommonsTopic:
            _fail("commons_frame_topic_invalid")
        if type(self.stock_id) is not EntityId:
            _fail("commons_frame_stock_invalid")
        _require_token(self.stock_id.value, code="commons_frame_stock_invalid")
        object.__setattr__(self, "peer_id", _require_optional_entity(self.peer_id))
        object.__setattr__(
            self, "proposal_id", _require_optional_proposal(self.proposal_id)
        )
        object.__setattr__(
            self, "reported_tick", _require_optional_tick(self.reported_tick)
        )
        self._validate_combination()

    def _validate_combination(self) -> None:
        act = self.act
        topic = self.topic
        peer = self.peer_id
        proposal = self.proposal_id
        reported = self.reported_tick
        if act is CommonsAct.PROPOSE:
            if topic is CommonsTopic.REST:
                if peer is not None or proposal is not None or reported is not None:
                    _fail("commons_frame_fields_invalid")
                return
            if topic is CommonsTopic.TURN:
                if peer is None or proposal is not None or reported is not None:
                    _fail("commons_frame_fields_invalid")
                return
            _fail("commons_frame_topic_invalid")
        if act in {CommonsAct.SUPPORT, CommonsAct.OPPOSE}:
            if topic not in {CommonsTopic.REST, CommonsTopic.TURN}:
                _fail("commons_frame_topic_invalid")
            if peer is not None or proposal is None or reported is not None:
                _fail("commons_frame_fields_invalid")
            return
        if act is CommonsAct.CLAIM_ACCESS:
            if topic is not CommonsTopic.ACCESS:
                _fail("commons_frame_topic_invalid")
            if peer is not None or proposal is not None or reported is not None:
                _fail("commons_frame_fields_invalid")
            return
        if act in {
            CommonsAct.REPORT_USE,
            CommonsAct.REPORT_REST,
            CommonsAct.CRITICIZE,
        }:
            if topic not in {CommonsTopic.REST, CommonsTopic.TURN}:
                _fail("commons_frame_topic_invalid")
            if peer is not None or proposal is None or reported is None:
                _fail("commons_frame_fields_invalid")
            return
        _fail("commons_frame_act_invalid")


def encode_commons_frame(frame: CommonsFrame) -> str:
    """Encode one frame; reject rather than truncate when oversize."""

    if type(frame) is not CommonsFrame:
        raise TypeError("frame must be CommonsFrame")
    predicate = CGO_RELATION_PREDICATES[frame.act]
    parts = (
        CGO_FRAME_SUBJECT,
        predicate,
        frame.topic.value,
        frame.stock_id.value,
        CGO_NONE_TOKEN if frame.peer_id is None else frame.peer_id.value,
        CGO_NONE_TOKEN if frame.proposal_id is None else frame.proposal_id,
        CGO_NONE_TOKEN if frame.reported_tick is None else str(frame.reported_tick),
    )
    text = "|".join(parts)
    if len(text) > CGO_FRAME_MAX_CHARS:
        _fail("commons_frame_oversize")
    if _CONTROL_RE.search(text) is not None:
        _fail("commons_frame_invalid")
    round_trip = parse_commons_frame(text)
    if (
        round_trip.act is not frame.act
        or round_trip.topic is not frame.topic
        or round_trip.stock_id != frame.stock_id
        or round_trip.peer_id != frame.peer_id
        or round_trip.proposal_id != frame.proposal_id
        or round_trip.reported_tick != frame.reported_tick
    ):
        _fail("commons_frame_round_trip")
    return text


def parse_commons_frame(text: str) -> CommonsFrame:
    """Parse one strict ``cgo_v1`` frame; malformed input fails closed."""

    if type(text) is not str:
        _fail("commons_frame_invalid")
    if not text or len(text) > CGO_FRAME_MAX_CHARS:
        _fail(
            "commons_frame_oversize"
            if len(text) > CGO_FRAME_MAX_CHARS
            else "commons_frame_invalid"
        )
    if _CONTROL_RE.search(text) is not None:
        _fail("commons_frame_invalid")
    parts = text.split("|")
    if len(parts) != 7:
        _fail("commons_frame_invalid")
    subject, predicate, topic_raw, stock_raw, peer_raw, proposal_raw, tick_raw = parts
    if subject != CGO_FRAME_SUBJECT:
        _fail("commons_frame_invalid")
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail("commons_frame_act_invalid")
    try:
        topic = CommonsTopic(topic_raw)
    except ValueError:
        _fail("commons_frame_topic_invalid")
    stock_token = _require_token(stock_raw, code="commons_frame_stock_invalid")
    peer: EntityId | None
    if peer_raw == CGO_NONE_TOKEN:
        peer = None
    else:
        peer = EntityId(_require_token(peer_raw, code="commons_frame_peer_invalid"))
    proposal: str | None
    if proposal_raw == CGO_NONE_TOKEN:
        proposal = None
    else:
        proposal = _require_optional_proposal(proposal_raw)
    reported: int | None
    if tick_raw == CGO_NONE_TOKEN:
        reported = None
    else:
        if _DIGITS_RE.match(tick_raw) is None:
            _fail("commons_frame_tick_invalid")
        reported = int(tick_raw)
    return CommonsFrame(
        act=act,
        topic=topic,
        stock_id=EntityId(stock_token),
        peer_id=peer,
        proposal_id=proposal,
        reported_tick=reported,
    )


def commons_frame_relation(frame: CommonsFrame) -> CommunicationRelation:
    """Build the single bounded relation atom for one frame."""

    encoded = encode_commons_frame(frame)
    _subject, predicate, object_payload = encoded.split("|", 2)
    return CommunicationRelation(
        subject=CGO_FRAME_SUBJECT,
        predicate=predicate,
        object=object_payload,
    )


def parse_commons_frame_relation(relation: object) -> CommonsFrame | None:
    """Parse one relation; unrelated atoms return ``None``, malformed fails closed."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != CGO_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    return parse_commons_frame(
        f"{CGO_FRAME_SUBJECT}|{relation.predicate}|{relation.object}"
    )


def attach_commons_frame(
    utterance: Talk | Tell, frame: CommonsFrame | None
) -> Talk | Tell:
    """Attach one ``cgo_v1`` relation to an existing addressed Talk/Tell."""

    if frame is None:
        return utterance
    if type(frame) is not CommonsFrame:
        raise TypeError("frame must be CommonsFrame")
    if type(utterance) is not Talk and type(utterance) is not Tell:
        raise TypeError("cgo_v1 requires Talk or Tell")
    content = utterance.utterance.content
    relations = tuple(content.relations)
    if any(getattr(row, "subject", None) == CGO_FRAME_SUBJECT for row in relations):
        _LOG.debug("commons_frame_attach_skipped reason_code=duplicate count=1")
        return utterance
    if len(relations) + 1 > 32:
        _LOG.debug("commons_frame_attach_skipped reason_code=relation_cap count=1")
        return utterance
    relation = commons_frame_relation(frame)
    if (
        frame.act is CommonsAct.PROPOSE
        and frame.topic is CommonsTopic.TURN
        and frame.peer_id is not None
        and utterance.recipient_id != frame.peer_id
    ):
        _fail("commons_frame_addressee_mismatch")
    if frame.act is CommonsAct.CRITICIZE:
        # Criticism must name the reporting actor as the addressed peer; the
        # caller supplies that recipient. Absence is rejected at attach time.
        if utterance.recipient_id is None:
            _fail("commons_frame_addressee_mismatch")
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(utterance.utterance, content=updated_content)
    return utterance.__class__(
        recipient_id=utterance.recipient_id, utterance=updated_utterance
    )
