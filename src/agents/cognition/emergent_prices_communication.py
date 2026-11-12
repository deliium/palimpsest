"""Bounded ``prc_v1`` speech frames for owner price expectations.

A quoted offer or an expectation travels only inside an existing ``Talk`` or
``Tell`` utterance. The frame is testimony, never a world price and never an
authority to exchange. Malformed or oversize frames are dropped.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Final, NoReturn

from agents.cognition.emergent_prices import (
    PRICE_CONFIDENCE_MAX_MILLI,
    PRICE_RATIO_MAX_MILLI,
    EmergentPriceLedger,
    EmergentPricePolicy,
    PriceExpectationLevel,
    PriceExpectationRow,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
    default_emergent_price_policy,
)
from agents.models import AgentId
from world.communications import CommunicationRelation

__all__ = [
    "PRICE_ACT_PREDICATES",
    "PRICE_COMMUNICATION_POLICY_VERSION",
    "PRICE_FRAME_MAX_CHARS",
    "PRICE_FRAME_MAX_RELATIONS",
    "PRICE_FRAME_SUBJECT",
    "PriceClaim",
    "PriceCommunicationAct",
    "encode_price_claim",
    "parse_price_claim",
    "parse_price_claim_relation",
    "price_claim_relation",
    "price_communicate_utterance",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "agents.cognition.emergent_prices_communication"
)

PRICE_FRAME_SUBJECT: Final[str] = "prc_v1"
PRICE_COMMUNICATION_POLICY_VERSION: Final[str] = (
    "emergent-prices-communication.v1"
)
PRICE_FRAME_MAX_CHARS: Final[int] = 256
PRICE_FRAME_MAX_RELATIONS: Final[int] = 32
_PRICE_ANCHOR_MAX_LEN: Final[int] = 64

_ITEM_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_-]*$")
_ANCHOR_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
_DIGITS_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9]+$")
_NONE_TOKEN: Final[str] = "none"


class PriceCommunicationAct(StrEnum):
    """Closed speech act for one quoted offer or cited expectation."""

    QUOTE_OFFER = "quote_offer"
    QUOTE_COUNTER = "quote_counter"
    WITHDRAW_QUOTE = "withdraw_quote"
    CITE_EXPECTATION = "cite_expectation"


PRICE_ACT_PREDICATES: Final[Mapping[PriceCommunicationAct, str]] = MappingProxyType(
    {
        PriceCommunicationAct.QUOTE_OFFER: "prc_quote",
        PriceCommunicationAct.QUOTE_COUNTER: "prc_counter",
        PriceCommunicationAct.WITHDRAW_QUOTE: "prc_withdraw",
        PriceCommunicationAct.CITE_EXPECTATION: "prc_expect",
    }
)
_PREDICATE_TO_ACT: Final[Mapping[str, PriceCommunicationAct]] = MappingProxyType(
    {predicate: act for act, predicate in PRICE_ACT_PREDICATES.items()}
)
_ACT_TO_SOURCE: Final[Mapping[PriceCommunicationAct, PriceQuoteSource]] = (
    MappingProxyType(
        {
            PriceCommunicationAct.QUOTE_OFFER: PriceQuoteSource.COMMUNICATED,
            PriceCommunicationAct.QUOTE_COUNTER: PriceQuoteSource.COMMUNICATED,
            PriceCommunicationAct.WITHDRAW_QUOTE: PriceQuoteSource.COMMUNICATED,
            PriceCommunicationAct.CITE_EXPECTATION: PriceQuoteSource.COMMUNICATED,
        }
    )
)


def _fail(code: str) -> NoReturn:
    _LOG.error("price_frame_invalid reason_code=%s", code)
    raise ValueError(code)


@dataclass(frozen=True, slots=True)
class PriceClaim:
    """One closed self-authored or communicated price claim."""

    act: PriceCommunicationAct
    item_kind_token: str
    unit_token: str
    unit_source: PriceUnitSource
    direction: PriceQuoteDirection
    ratio_milli: int
    confidence_milli: int
    anchor: str | None = None

    def __post_init__(self) -> None:
        if type(self.act) is not PriceCommunicationAct:
            _fail("price_invalid_frame")
        if (
            type(self.item_kind_token) is not str
            or _ITEM_RE.match(self.item_kind_token) is None
        ):
            _fail("price_invalid_enum")
        if type(self.unit_token) is not str or (
            self.unit_token != _NONE_TOKEN
            and _ITEM_RE.match(self.unit_token) is None
        ):
            _fail("price_invalid_enum")
        if type(self.unit_source) is not PriceUnitSource:
            _fail("price_invalid_enum")
        if type(self.direction) is not PriceQuoteDirection:
            _fail("price_invalid_enum")
        if (self.unit_token == _NONE_TOKEN) is not (
            self.unit_source is PriceUnitSource.UNKNOWN
        ):
            _fail("price_invalid_enum")
        if (
            isinstance(self.ratio_milli, bool)
            or type(self.ratio_milli) is not int
            or not 0 <= self.ratio_milli <= PRICE_RATIO_MAX_MILLI
        ):
            _fail("price_invalid_ratio")
        if (
            isinstance(self.confidence_milli, bool)
            or type(self.confidence_milli) is not int
            or not 0 <= self.confidence_milli <= PRICE_CONFIDENCE_MAX_MILLI
        ):
            _fail("price_invalid_enum")
        if self.anchor is not None:
            if (
                type(self.anchor) is not str
                or len(self.anchor) > _PRICE_ANCHOR_MAX_LEN
                or _ANCHOR_RE.match(self.anchor) is None
            ):
                _fail("price_invalid_anchor")


def encode_price_claim(claim: PriceClaim) -> str:
    """Encode one claim into the bounded nine-part ``prc_v1`` frame."""

    if type(claim) is not PriceClaim:
        raise TypeError("claim must be PriceClaim")
    parts = (
        PRICE_FRAME_SUBJECT,
        PRICE_ACT_PREDICATES[claim.act],
        claim.item_kind_token,
        claim.unit_token,
        claim.unit_source.value,
        claim.direction.value,
        str(claim.ratio_milli),
        str(claim.confidence_milli),
        _NONE_TOKEN if claim.anchor is None else claim.anchor,
    )
    return ":".join(parts)


def parse_price_claim(text: str) -> PriceClaim:
    """Parse one strict ``prc_v1`` frame; malformed text fails closed."""

    if type(text) is not str:
        _fail("price_invalid_frame")
    if len(text) > PRICE_FRAME_MAX_CHARS:
        _fail("price_frame_oversize")
    if any(character.isspace() or ord(character) < 32 for character in text):
        _fail("price_invalid_frame")
    parts = text.split(":")
    if len(parts) != 9:
        _fail("price_invalid_frame")
    (
        subject,
        predicate,
        item,
        unit,
        unit_source,
        direction,
        ratio,
        confidence,
        anchor,
    ) = parts
    if subject != PRICE_FRAME_SUBJECT:
        _fail("price_invalid_frame")
    act = _PREDICATE_TO_ACT.get(predicate)
    if act is None:
        _fail("price_invalid_frame")
    try:
        source = PriceUnitSource(unit_source)
        direction_value = PriceQuoteDirection(direction)
    except ValueError:
        _fail("price_invalid_enum")
    if _DIGITS_RE.match(ratio) is None or _DIGITS_RE.match(confidence) is None:
        _fail("price_invalid_ratio")
    resolved_anchor = None if anchor == _NONE_TOKEN else anchor
    return PriceClaim(
        act=act,
        item_kind_token=item,
        unit_token=unit,
        unit_source=source,
        direction=direction_value,
        ratio_milli=int(ratio),
        confidence_milli=int(confidence),
        anchor=resolved_anchor,
    )


def price_claim_relation(claim: PriceClaim) -> CommunicationRelation:
    """Build one bounded relation atom for a price claim."""

    if type(claim) is not PriceClaim:
        raise TypeError("claim must be PriceClaim")
    frame = encode_price_claim(claim).split(":", 2)[2]
    return CommunicationRelation(
        subject=PRICE_FRAME_SUBJECT,
        predicate=PRICE_ACT_PREDICATES[claim.act],
        object=frame,
    )


def parse_price_claim_relation(relation: object) -> PriceClaim | None:
    """Parse one price relation; unrelated atoms return ``None``."""

    if type(relation) is not CommunicationRelation:
        raise TypeError("relation must be CommunicationRelation")
    if relation.subject != PRICE_FRAME_SUBJECT:
        return None
    if relation.predicate not in _PREDICATE_TO_ACT:
        return None
    return parse_price_claim(
        f"{PRICE_FRAME_SUBJECT}:{relation.predicate}:{relation.object}"
    )


def _is_expressible(command: object) -> bool:
    from world.actions import Talk, Tell

    return type(command) in {Talk, Tell}


def _select_claim(
    ledger: EmergentPriceLedger, policy: EmergentPricePolicy
) -> PriceClaim | None:
    candidates: list[tuple[int, int, str, str, PriceExpectationRow]] = []
    for row in ledger.rows:
        if row.unit_kind is None:
            continue
        if row.confidence_milli < policy.quote_min_confidence_milli:
            continue
        candidates.append(
            (
                -row.confidence_milli,
                -row.expected_ratio_milli,
                row.item_kind.value,
                row.unit_kind.value,
                row,
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[:4])
    row = candidates[0][4]
    assert row.unit_kind is not None
    act = (
        PriceCommunicationAct.QUOTE_OFFER
        if row.level in {PriceExpectationLevel.EXPECTED, PriceExpectationLevel.STRONG}
        else PriceCommunicationAct.CITE_EXPECTATION
    )
    return PriceClaim(
        act=act,
        item_kind_token=row.item_kind.value,
        unit_token=row.unit_kind.value,
        unit_source=row.unit_source,
        direction=PriceQuoteDirection.GIVE_FOR_UNIT,
        ratio_milli=row.expected_ratio_milli,
        confidence_milli=row.confidence_milli,
    )


def price_communicate_utterance(
    command: object,
    *,
    owner_id: AgentId,
    ledger: object | None,
    counterparty_id: object | None,
    policy: EmergentPricePolicy | None = None,
) -> object:
    """Attach at most one ``prc_v1`` relation to an already-selected utterance."""

    if type(owner_id) is not AgentId:
        raise TypeError("owner_id must be AgentId")
    if type(ledger) is not EmergentPriceLedger:
        return command
    if ledger.owner_id != owner_id or not ledger.rows:
        return command
    if not _is_expressible(command):
        return command
    active = default_emergent_price_policy() if policy is None else policy
    if type(active) is not EmergentPricePolicy:
        raise TypeError("policy must be EmergentPricePolicy or None")
    claim = _select_claim(ledger, active)
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
        relation.subject == PRICE_FRAME_SUBJECT
        or relation.predicate in _PREDICATE_TO_ACT
        for relation in relations
    ):
        return command
    if len(relations) >= PRICE_FRAME_MAX_RELATIONS:
        _LOG.warning("price_frame_dropped reason_code=relation_cap")
        return command
    if len(encode_price_claim(claim)) > PRICE_FRAME_MAX_CHARS:
        _LOG.warning("price_frame_dropped reason_code=oversize")
        return command
    updated_content = replace(
        content, relations=(*relations, price_claim_relation(claim))
    )
    updated_utterance = replace(utterance, content=updated_content)
    _LOG.debug("price_frame_attached act=%s", claim.act.value)
    from typing import Any, cast

    typed = cast(Any, command)
    return typed.__class__(
        recipient_id=typed.recipient_id,
        utterance=updated_utterance,
    )
