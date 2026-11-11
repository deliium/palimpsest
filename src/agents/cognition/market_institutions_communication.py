"""Bounded ``mkt_v1`` speech frames for owner market-like institution beliefs.

Meeting expectations, schedules, broker-like role claims, and exchange-record
anchors travel only inside existing ``Talk``/``Ask``/``Tell`` utterances. A frame
is testimony, never a world timer, price, valuation, inventory, or permission.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.market_institutions import (
    MARKET_ANCHOR_MAX_LEN,
    MARKET_ANCHOR_PATTERN,
    MARKET_BELIEF_HEX_LEN,
    MARKET_LABEL_MAX_LEN,
    MARKET_LABEL_PATTERN,
    MarketCadence,
    MarketExpectation,
    MarketInstitutionError,
    MarketInstitutionLedger,
    MarketRoleKind,
)
from world.communications import CommunicationRelation

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.market_institutions_communication"
)

MARKET_FRAME_SUBJECT: Final[str] = "mkt_v1"
MARKET_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "market-institutions-communication.v1"
)
MARKET_FRAME_MAX_CHARS: Final[int] = 256
MARKET_FRAME_MAX_RELATIONS: Final[int] = 32

_LABEL_RE: Final[re.Pattern[str]] = re.compile(MARKET_LABEL_PATTERN)
_ANCHOR_RE: Final[re.Pattern[str]] = re.compile(MARKET_ANCHOR_PATTERN)
_OFFICE_REF_RE: Final[re.Pattern[str]] = re.compile(
    rf"^[0-9a-f]{{{MARKET_BELIEF_HEX_LEN}}}$"
)
_ORGANIZATION_REF_RE: Final[re.Pattern[str]] = re.compile(
    rf"^orgc-[0-9a-f]{{{MARKET_BELIEF_HEX_LEN}}}$"
)
_DIGITS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_NONE_TOKEN: Final[str] = "none"


class MarketCommunicationAct(StrEnum):
    """Closed speech act for one market-like institution claim."""

    ANNOUNCE_MEETING = "announce_meeting"
    EXPECT_MEETING = "expect_meeting"
    DECLINE_MEETING = "decline_meeting"
    CLAIM_ROLE = "claim_role"
    CITE_RECORD = "cite_record"


MARKET_ACT_PREDICATES: Final[Mapping[MarketCommunicationAct, str]] = (
    MappingProxyType(
        {
            MarketCommunicationAct.ANNOUNCE_MEETING: "mkt_meeting",
            MarketCommunicationAct.EXPECT_MEETING: "mkt_expect",
            MarketCommunicationAct.DECLINE_MEETING: "mkt_decline",
            MarketCommunicationAct.CLAIM_ROLE: "mkt_role",
            MarketCommunicationAct.CITE_RECORD: "mkt_record",
        }
    )
)
_PREDICATE_TO_ACT: Final[Mapping[str, MarketCommunicationAct]] = MappingProxyType(
    {predicate: act for act, predicate in MARKET_ACT_PREDICATES.items()}
)


def _fail(code: str) -> NoReturn:
    _LOG.error("market_frame_invalid reason_code=%s", code)
    raise MarketInstitutionError(code)


@dataclass(frozen=True, slots=True)
class MarketClaim:
    """One closed self-authored or communicated market claim."""

    act: MarketCommunicationAct
    label_token: str
    expectation: MarketExpectation = MarketExpectation.NONE
    cadence: MarketCadence = MarketCadence.UNKNOWN
    interval_ticks: int | None = None
    phase_tick: int | None = None
    window_index: int | None = None
    role_kind: MarketRoleKind = MarketRoleKind.UNKNOWN
    role_ref: str | None = None
    anchor: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not MarketCommunicationAct:
            _fail("market_institution_invalid_act")
        if (
            type(self.label_token) is not str
            or len(self.label_token) > MARKET_LABEL_MAX_LEN
            or _LABEL_RE.match(self.label_token) is None
        ):
            _fail("market_institution_invalid_label")
        if type(self.expectation) is not MarketExpectation:
            _fail("market_institution_invalid_enum")
        if type(self.cadence) is not MarketCadence:
            _fail("market_institution_invalid_enum")
        if type(self.role_kind) is not MarketRoleKind:
            _fail("market_institution_invalid_enum")
        if self.cadence is MarketCadence.RECURRING_INTERVAL:
            if (
                type(self.interval_ticks) is not int
                or not 1 <= self.interval_ticks <= 512
                or type(self.phase_tick) is not int
                or not 0 <= self.phase_tick <= 511
                or self.window_index is not None
            ):
                _fail("market_institution_invalid_schedule")
        elif self.cadence is MarketCadence.PERIODIC_WINDOW:
            if (
                type(self.window_index) is not int
                or not 0 <= self.window_index <= 511
                or self.interval_ticks is not None
                or self.phase_tick is not None
            ):
                _fail("market_institution_invalid_schedule")
        elif (
            self.interval_ticks is not None
            or self.phase_tick is not None
            or self.window_index is not None
        ):
            _fail("market_institution_invalid_schedule")
        if self.role_ref is not None:
            if (
                type(self.role_ref) is not str
                or (
                    _OFFICE_REF_RE.match(self.role_ref) is None
                    and _ORGANIZATION_REF_RE.match(self.role_ref) is None
                )
            ):
                _fail("market_institution_invalid_role_ref")
        if self.anchor is not None:
            if (
                type(self.anchor) is not str
                or len(self.anchor) > MARKET_ANCHOR_MAX_LEN
                or _ANCHOR_RE.match(self.anchor) is None
            ):
                _fail("market_institution_invalid_anchor")


def encode_market_claim(claim: MarketClaim) -> str:
    """Encode one claim into the bounded ``mkt_v1`` frame."""

    if type(claim) is not MarketClaim:
        raise TypeError("claim must be MarketClaim")
    predicate = MARKET_ACT_PREDICATES[claim.act]
    interval_slot = (
        claim.window_index
        if claim.cadence is MarketCadence.PERIODIC_WINDOW
        else claim.interval_ticks
    )
    parts = (
        MARKET_FRAME_SUBJECT,
        predicate,
        claim.label_token,
        claim.expectation.value,
        claim.cadence.value,
        _NONE_TOKEN if interval_slot is None else str(interval_slot),
        _NONE_TOKEN if claim.phase_tick is None else str(claim.phase_tick),
        claim.role_kind.value,
        _NONE_TOKEN if claim.role_ref is None else claim.role_ref,
        _NONE_TOKEN if claim.anchor is None else claim.anchor,
    )
    return ":".join(parts)


def parse_market_claim(text: str) -> MarketClaim:
    """Parse one strict ``mkt_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail("market_institution_invalid_act")
    if len(text) > MARKET_FRAME_MAX_CHARS:
        _fail("market_institution_frame_oversize")
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail("market_institution_invalid_act")
    parts = text.split(":")
    if len(parts) != 10:
        _fail("market_institution_invalid_frame")
    (
        subject,
        predicate,
        label,
        expectation,
        cadence,
        interval,
        phase,
        role_kind,
        role_ref,
        anchor,
    ) = parts
    if subject != MARKET_FRAME_SUBJECT:
        _fail("market_institution_invalid_act")
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail("market_institution_invalid_act")
    try:
        expectation_value = MarketExpectation(expectation)
        cadence_value = MarketCadence(cadence)
        role_value = MarketRoleKind(role_kind)
    except ValueError:
        _fail("market_institution_invalid_enum")
    label_token = label
    if len(label_token) > MARKET_LABEL_MAX_LEN or _LABEL_RE.match(label_token) is None:
        _fail("market_institution_invalid_label")
    interval_ticks: int | None = None
    phase_tick: int | None = None
    window_index: int | None = None
    if cadence_value is MarketCadence.RECURRING_INTERVAL:
        if interval == _NONE_TOKEN or _DIGITS_RE.match(interval) is None:
            _fail("market_institution_invalid_schedule")
        if phase == _NONE_TOKEN or _DIGITS_RE.match(phase) is None:
            _fail("market_institution_invalid_schedule")
        interval_ticks = int(interval)
        phase_tick = int(phase)
    elif cadence_value is MarketCadence.PERIODIC_WINDOW:
        if interval == _NONE_TOKEN or _DIGITS_RE.match(interval) is None:
            _fail("market_institution_invalid_schedule")
        if phase != _NONE_TOKEN:
            _fail("market_institution_invalid_schedule")
        window_index = int(interval)
    else:
        if interval != _NONE_TOKEN or phase != _NONE_TOKEN:
            _fail("market_institution_invalid_schedule")
    resolved_role_ref = None if role_ref == _NONE_TOKEN else role_ref
    resolved_anchor = None if anchor == _NONE_TOKEN else anchor
    return MarketClaim(
        act=act,
        label_token=label_token,
        expectation=expectation_value,
        cadence=cadence_value,
        interval_ticks=interval_ticks,
        phase_tick=phase_tick,
        window_index=window_index,
        role_kind=role_value,
        role_ref=resolved_role_ref,
        anchor=resolved_anchor,
    )


def market_claim_relation(claim: MarketClaim) -> CommunicationRelation:
    """Build one bounded relation atom for a market claim."""

    if type(claim) is not MarketClaim:
        raise TypeError("claim must be MarketClaim")
    frame = encode_market_claim(claim).split(":", 2)[2]
    return CommunicationRelation(
        subject=MARKET_FRAME_SUBJECT,
        predicate=MARKET_ACT_PREDICATES[claim.act],
        object=frame,
    )


def parse_market_claim_relation(relation: object) -> MarketClaim | None:
    """Parse one market relation; unrelated atoms return ``None``.

    Malformed ``mkt_v1`` objects raise ``MarketInstitutionError``.
    """

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != MARKET_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    return parse_market_claim(
        f"{MARKET_FRAME_SUBJECT}:{relation.predicate}:{relation.object}"
    )


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _select_claim(ledger: MarketInstitutionLedger) -> MarketClaim | None:
    candidates: list[tuple[int, int, int, str, MarketClaim]] = []
    for venue in ledger.venues:
        expectation_rank = {
            MarketExpectation.NONE: 0,
            MarketExpectation.WEAK: 1,
            MarketExpectation.EXPECTED: 2,
            MarketExpectation.STRONG: 3,
        }[venue.expectation.level]
        if venue.schedules:
            schedule = max(
                venue.schedules,
                key=lambda item: (item.last_tick, item.confidence_milli),
            )
            cadence = schedule.cadence
            interval = schedule.interval_ticks
            phase = schedule.phase_tick
            window = schedule.window_index
        else:
            cadence = MarketCadence.SINGLE_OCCURRENCE
            interval = None
            phase = None
            window = None
        act = (
            MarketCommunicationAct.EXPECT_MEETING
            if expectation_rank >= 2
            else MarketCommunicationAct.ANNOUNCE_MEETING
        )
        candidates.append(
            (
                1,
                -expectation_rank,
                -venue.last_tick,
                venue.venue_id,
                MarketClaim(
                    act=act,
                    label_token=venue.label_token,
                    expectation=venue.expectation.level,
                    cadence=cadence,
                    interval_ticks=interval,
                    phase_tick=phase,
                    window_index=window,
                ),
            )
        )
        broker_roles = [
            role for role in venue.roles if role.role_kind is MarketRoleKind.BROKER
        ]
        other_roles = [
            role for role in venue.roles if role.role_kind is not MarketRoleKind.BROKER
        ]
        for priority, roles in ((0, broker_roles), (2, other_roles)):
            for role in roles:
                role_ref = (
                    role.office_ref
                    if role.organization_ref is None
                    else role.organization_ref
                )
                candidates.append(
                    (
                        priority,
                        -expectation_rank,
                        -role.last_tick,
                        venue.venue_id,
                        MarketClaim(
                            act=MarketCommunicationAct.CLAIM_ROLE,
                            label_token=venue.label_token,
                            role_kind=role.role_kind,
                            role_ref=role_ref,
                        ),
                    )
                )
        for record in venue.records:
            candidates.append(
                (
                    0
                    if expectation_rank <= 1
                    else 3,
                    -expectation_rank,
                    -record.last_tick,
                    venue.venue_id,
                    MarketClaim(
                        act=MarketCommunicationAct.CITE_RECORD,
                        label_token=venue.label_token,
                        anchor=record.anchor,
                    ),
                )
            )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    return candidates[0][4]


def market_communicate_utterance(command: object, ledger: object | None) -> object:
    """Attach at most one ``mkt_v1`` relation to an already-selected utterance."""

    if type(ledger) is not MarketInstitutionLedger:
        return command
    if not ledger.venues:
        return command
    if not _is_expressible(command):
        return command
    claim = _select_claim(ledger)
    if claim is None:
        return command
    utterance = getattr(command, "utterance", None)
    if utterance is None:
        return command
    content = getattr(utterance, "content", None)
    if content is None:
        return command
    relations = tuple(getattr(content, "relations", ()))
    if any(
        relation.subject == MARKET_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= MARKET_FRAME_MAX_RELATIONS:
        _LOG.warning("market_frame_dropped reason_code=relation_cap")
        return command
    relation = market_claim_relation(claim)
    if len(encode_market_claim(claim)) > MARKET_FRAME_MAX_CHARS:
        _LOG.warning("market_frame_dropped reason_code=oversize")
        return command
    updated_content = replace(content, relations=(*relations, relation))
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug("market_frame_attached act=%s", claim.act.value)
    from typing import Any, cast

    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )


__all__ = [
    "MARKET_ACT_PREDICATES",
    "MARKET_COMMUNICATION_POLICY_VERSION",
    "MARKET_FRAME_MAX_CHARS",
    "MARKET_FRAME_MAX_RELATIONS",
    "MARKET_FRAME_SUBJECT",
    "MarketClaim",
    "MarketCommunicationAct",
    "encode_market_claim",
    "market_claim_relation",
    "market_communicate_utterance",
    "parse_market_claim",
    "parse_market_claim_relation",
]
