"""Neutral bounded ``crd_v1`` speech-frame codec.

A credit frame states owner-relative terms and one act inside an existing
``Talk`` or ``Tell`` utterance. It is testimony, never a contract, a bank
record, or an authority to give, collect, or enforce. This module stays in
``world`` so detached analysis can parse committed speech without importing
cognition.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from world.communications import CommunicationRelation

__all__ = [
    "CREDIT_ACT_PREDICATES",
    "CREDIT_FRAME_COLLATERAL_KINDS",
    "CREDIT_FRAME_CONDITIONS",
    "CREDIT_FRAME_MAX_CHARS",
    "CREDIT_FRAME_MAX_RELATIONS",
    "CREDIT_FRAME_SUBJECT",
    "CreditClaimFrame",
    "CreditFrameAct",
    "CreditFrameDirection",
    "credit_claim_relation",
    "encode_credit_claim_frame",
    "parse_credit_claim_frame",
    "parse_credit_claim_relation",
]

_LOG: Final[logging.Logger] = logging.getLogger("world.credit_relationships")

CREDIT_FRAME_SUBJECT: Final[str] = "crd_v1"
CREDIT_FRAME_MAX_CHARS: Final[int] = 320
CREDIT_FRAME_MAX_RELATIONS: Final[int] = 32
_NONE_TOKEN: Final[str] = "none"

_ITEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_-]*$")
_ANCHOR_RE: Final[re.Pattern[str]] = re.compile(r"^crd-[0-9a-f]{16}$")
_DIGITS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")


class CreditFrameAct(StrEnum):
    """Closed credit speech act token."""

    PROPOSE = "propose"
    ACCEPT = "accept"
    DECLINE = "decline"
    REPAY = "repay"
    DEFAULT = "default"
    RENEGOTIATE = "renegotiate"
    FORGIVE = "forgive"
    DISPUTE = "dispute"
    WITHDRAW = "withdraw"


class CreditFrameDirection(StrEnum):
    """Closed speaker-relative direction token."""

    OWNER_DEBTOR = "owner_debtor"
    OWNER_CREDITOR = "owner_creditor"


CREDIT_ACT_PREDICATES: Final[Mapping[CreditFrameAct, str]] = MappingProxyType(
    {
        CreditFrameAct.PROPOSE: "crd_propose",
        CreditFrameAct.ACCEPT: "crd_accept",
        CreditFrameAct.DECLINE: "crd_decline",
        CreditFrameAct.REPAY: "crd_repay",
        CreditFrameAct.DEFAULT: "crd_default",
        CreditFrameAct.RENEGOTIATE: "crd_renegotiate",
        CreditFrameAct.FORGIVE: "crd_forgive",
        CreditFrameAct.DISPUTE: "crd_dispute",
        CreditFrameAct.WITHDRAW: "crd_withdraw",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, CreditFrameAct]] = MappingProxyType(
    {predicate: act for act, predicate in CREDIT_ACT_PREDICATES.items()}
)

CREDIT_FRAME_CONDITIONS: Final[frozenset[str]] = frozenset(
    {"on_receipt", "by_deadline", "after_return", "shared_witness", "unspecified"}
)
CREDIT_FRAME_COLLATERAL_KINDS: Final[frozenset[str]] = frozenset(
    {
        "none",
        "item_pledge",
        "service_pledge",
        "custody_pledge",
        "reputation_pledge",
        "unspecified",
    }
)


def _fail(code: str) -> NoReturn:
    _LOG.error("credit_frame_invalid reason_code=%s", code)
    raise ValueError(code)


def _quantity(text: str, *, minimum: int) -> int:
    if _DIGITS_RE.match(text) is None:
        _fail("credit_frame_quantity")
    value = int(text)
    if not minimum <= value <= 16:
        _fail("credit_frame_quantity")
    return value


def _tick(text: str) -> int:
    if _DIGITS_RE.match(text) is None:
        _fail("credit_frame_tick")
    value = int(text)
    if value < 0:
        _fail("credit_frame_tick")
    return value


@dataclass(frozen=True, slots=True)
class CreditClaimFrame:
    """One validated, immutable ``crd_v1`` frame value."""

    act: CreditFrameAct
    direction: CreditFrameDirection
    anchor: str
    principal_kind_token: str
    principal_quantity: int
    repayment_kind_token: str
    repayment_quantity: int
    paid_quantity: int
    opened_tick: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_item_token: str | None
    collateral_quantity: int
    confidence_milli: int

    def __post_init__(self) -> None:
        if type(self.act) is not CreditFrameAct:
            _fail("credit_frame_act")
        if type(self.direction) is not CreditFrameDirection:
            _fail("credit_frame_direction")
        if type(self.anchor) is not str or _ANCHOR_RE.match(self.anchor) is None:
            _fail("credit_frame_anchor")
        for token in (self.principal_kind_token, self.repayment_kind_token):
            if type(token) is not str or _ITEM_RE.match(token) is None:
                _fail("credit_frame_item")
        item_token = self.collateral_item_token
        if item_token is not None and (
            type(item_token) is not str or _ITEM_RE.match(item_token) is None
        ):
            _fail("credit_frame_item")
        if self.collateral_kind not in CREDIT_FRAME_COLLATERAL_KINDS:
            _fail("credit_frame_collateral")
        if self.condition not in CREDIT_FRAME_CONDITIONS:
            _fail("credit_frame_condition")
        if self.collateral_kind in {"none", "unspecified"}:
            if item_token is not None or self.collateral_quantity != 0:
                _fail("credit_frame_collateral")
        elif self.collateral_kind in {"item_pledge", "custody_pledge"}:
            if item_token is None or not 1 <= self.collateral_quantity <= 16:
                _fail("credit_frame_collateral")
        elif item_token is not None or self.collateral_quantity != 0:
            _fail("credit_frame_collateral")
        if self.due_tick is not None and (
            isinstance(self.due_tick, bool)
            or type(self.due_tick) is not int
            or self.due_tick < 0
        ):
            _fail("credit_frame_tick")
        if (
            isinstance(self.principal_quantity, bool)
            or type(self.principal_quantity) is not int
            or not 1 <= self.principal_quantity <= 16
            or isinstance(self.repayment_quantity, bool)
            or type(self.repayment_quantity) is not int
            or not 1 <= self.repayment_quantity <= 16
        ):
            _fail("credit_frame_quantity")
        if (
            isinstance(self.paid_quantity, bool)
            or type(self.paid_quantity) is not int
            or not 0 <= self.paid_quantity <= 16
        ):
            _fail("credit_frame_quantity")
        if self.act is not CreditFrameAct.REPAY and self.paid_quantity != 0:
            _fail("credit_frame_quantity")
        if (
            isinstance(self.opened_tick, bool)
            or type(self.opened_tick) is not int
            or self.opened_tick < 0
        ):
            _fail("credit_frame_tick")
        if (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= 1_000
        ):
            _fail("credit_frame_confidence")


def encode_credit_claim_frame(frame: CreditClaimFrame) -> str:
    """Encode one frame into the bounded sixteen-part ``crd_v1`` body."""

    if type(frame) is not CreditClaimFrame:
        raise TypeError("frame must be CreditClaimFrame")
    parts = (
        CREDIT_FRAME_SUBJECT,
        CREDIT_ACT_PREDICATES[frame.act],
        frame.direction.value,
        frame.anchor,
        frame.principal_kind_token,
        str(frame.principal_quantity),
        frame.repayment_kind_token,
        str(frame.repayment_quantity),
        str(frame.paid_quantity),
        str(frame.opened_tick),
        _NONE_TOKEN if frame.due_tick is None else str(frame.due_tick),
        frame.condition,
        frame.collateral_kind,
        _NONE_TOKEN
        if frame.collateral_item_token is None
        else frame.collateral_item_token,
        str(frame.collateral_quantity),
        str(frame.confidence_milli),
    )
    return ":".join(parts)


def parse_credit_claim_frame(text: str) -> CreditClaimFrame:
    """Parse one strict ``crd_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail("credit_frame_malformed")
    if len(text) > CREDIT_FRAME_MAX_CHARS:
        _fail("credit_frame_oversize")
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail("credit_frame_malformed")
    parts = text.split(":")
    if len(parts) != 16:
        _fail("credit_frame_malformed")
    (
        subject,
        predicate,
        direction,
        anchor,
        principal,
        principal_quantity,
        repayment,
        repayment_quantity,
        paid_quantity,
        opened_tick,
        due_tick,
        condition,
        collateral_kind,
        collateral_item,
        collateral_quantity,
        confidence,
    ) = parts
    if subject != CREDIT_FRAME_SUBJECT:
        _fail("credit_frame_malformed")
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail("credit_frame_predicate")
    try:
        direction_value = CreditFrameDirection(direction)
    except ValueError:
        _fail("credit_frame_direction")
    return CreditClaimFrame(
        act=act,
        direction=direction_value,
        anchor=anchor,
        principal_kind_token=principal,
        principal_quantity=_quantity(principal_quantity, minimum=1),
        repayment_kind_token=repayment,
        repayment_quantity=_quantity(repayment_quantity, minimum=1),
        paid_quantity=_quantity(paid_quantity, minimum=0),
        opened_tick=_tick(opened_tick),
        due_tick=None if due_tick == _NONE_TOKEN else _tick(due_tick),
        condition=condition,
        collateral_kind=collateral_kind,
        collateral_item_token=None
        if collateral_item == _NONE_TOKEN
        else collateral_item,
        collateral_quantity=_quantity(collateral_quantity, minimum=0),
        confidence_milli=_tick(confidence),
    )


def credit_claim_relation(frame: CreditClaimFrame) -> CommunicationRelation:
    """Build one bounded relation atom for a credit frame."""

    body = encode_credit_claim_frame(frame).split(":", 2)[2]
    return CommunicationRelation(
        subject=CREDIT_FRAME_SUBJECT,
        predicate=CREDIT_ACT_PREDICATES[frame.act],
        object=body,
    )


def parse_credit_claim_relation(relation: object) -> CreditClaimFrame | None:
    """Parse one credit relation; unrelated atoms return ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != CREDIT_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    return parse_credit_claim_frame(
        f"{CREDIT_FRAME_SUBJECT}:{relation.predicate}:{relation.object}"
    )
