"""Explicit teaching offers folded from public utterances.

Only ``WorldEngine`` applies the extra practice deltas. The module may use
``world._skills``. Cognition and agent packages stay outside this module.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from world._skills import SkillDomain
from world.communications import CommunicationRelation
from world.identifiers import EntityId

_LOG: Final[logging.Logger] = logging.getLogger("world._teaching")

TEACHING_INTERACTION_POLICY_VERSION: Final[str] = "teaching-interaction-v1"
_OFFER_ACTS: Final[frozenset[str]] = frozenset({"demonstrate", "practice_together"})
_EXPLAIN_BANDS: Final[frozenset[str]] = frozenset({"low", "uncertain", "high"})


class TeachingAct(StrEnum):
    """Closed utterance predicates. There is no profession or teacher label."""

    REQUEST_INSTRUCTION = "request_instruction"
    EXPLAIN = "explain"
    DEMONSTRATE = "demonstrate"
    PRACTICE_TOGETHER = "practice_together"


class ClaimBand(StrEnum):
    """Public claim band. ``unspecified`` is used when the act has no band."""

    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"
    UNSPECIFIED = "unspecified"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "teaching_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _finite_number(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number):
        raise _fail(field_name, "not_finite")
    return number


def _nonnegative_rate(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0:
        raise _fail(field_name, "negative_rate")
    return number


def _unit_interval(field_name: str, value: object) -> float:
    number = _finite_number(field_name, value)
    if number < 0.0 or number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _require_act(value: object) -> TeachingAct:
    if type(value) is not TeachingAct:
        raise _fail("act", "unknown_act")
    return value


def _require_domain(value: object) -> SkillDomain:
    if type(value) is not SkillDomain:
        raise _fail("domain", "unknown_domain")
    return value


def _offer_window(field_name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field_name, "invalid_type")
    if value < 1 or value > 64:
        raise _fail(field_name, "offer_window")
    return value


def _domain_token(token: str) -> SkillDomain | None:
    try:
        domain = SkillDomain(token)
    except ValueError:
        _LOG.error(
            "teaching_validation_failed field=%s reason_code=%s",
            "domain",
            "unknown_domain",
        )
        return None
    if type(domain) is not SkillDomain:
        return None
    return domain


@dataclass(frozen=True, slots=True)
class TeachingOffer:
    """One open demonstrate or practice-together offer. Refolded from events."""

    speaker_id: EntityId
    recipient_id: EntityId
    act: TeachingAct
    domain: SkillDomain
    delivery_tick: int

    def __post_init__(self) -> None:
        if type(self.speaker_id) is not EntityId:
            raise _fail("speaker_id", "invalid_type")
        if type(self.recipient_id) is not EntityId:
            raise _fail("recipient_id", "invalid_type")
        act = _require_act(self.act)
        if act.value not in _OFFER_ACTS:
            raise _fail("act", "not_offer")
        object.__setattr__(self, "act", act)
        object.__setattr__(self, "domain", _require_domain(self.domain))
        if isinstance(self.delivery_tick, bool) or not isinstance(
            self.delivery_tick, int
        ):
            raise _fail("delivery_tick", "invalid_type")
        if self.delivery_tick < 0:
            raise _fail("delivery_tick", "invalid_type")


@dataclass(frozen=True, slots=True)
class TeachingInteractionPolicy:
    """Locked teaching weights. Version ``teaching-interaction-v1``."""

    demonstration_rate: float = 0.02
    practice_together_rate: float = 0.02
    offer_window: int = 8
    belief_explain_rate: float = 0.08
    explain_low_below: float = 0.34
    explain_high_at: float = 0.67
    teaching_response_weight: float = 0.25
    allow_provider: bool = False
    version: str = TEACHING_INTERACTION_POLICY_VERSION

    def __post_init__(self) -> None:
        if self.version != TEACHING_INTERACTION_POLICY_VERSION:
            raise _fail("version", "unsupported_version")
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        object.__setattr__(
            self,
            "demonstration_rate",
            _nonnegative_rate("demonstration_rate", self.demonstration_rate),
        )
        object.__setattr__(
            self,
            "practice_together_rate",
            _nonnegative_rate("practice_together_rate", self.practice_together_rate),
        )
        object.__setattr__(
            self,
            "offer_window",
            _offer_window("offer_window", self.offer_window),
        )
        object.__setattr__(
            self,
            "belief_explain_rate",
            _nonnegative_rate("belief_explain_rate", self.belief_explain_rate),
        )
        low = _unit_interval("explain_low_below", self.explain_low_below)
        high = _unit_interval("explain_high_at", self.explain_high_at)
        if low >= high:
            raise _fail("explain_low_below", "threshold_order")
        object.__setattr__(self, "explain_low_below", low)
        object.__setattr__(self, "explain_high_at", high)
        object.__setattr__(
            self,
            "teaching_response_weight",
            _unit_interval("teaching_response_weight", self.teaching_response_weight),
        )
        _LOG.debug(
            "teaching_policy_built policy_version=%s act_count=%s",
            self.version,
            len(TeachingAct),
        )


def default_teaching_interaction_policy(
    *,
    allow_provider: bool = False,
) -> TeachingInteractionPolicy:
    """Locked teaching defaults. Provider selection stays off unless requested."""
    if type(allow_provider) is not bool:
        raise _fail("allow_provider", "invalid_type")
    return TeachingInteractionPolicy(allow_provider=allow_provider)


def parse_teaching_relation(
    relation: object,
) -> tuple[TeachingAct, SkillDomain, ClaimBand] | None:
    """Return the act, domain, and band for exactly one teaching relation.

    Any other shape is not a teaching act and returns ``None``.
    """
    if type(relation) is not CommunicationRelation:
        return None
    predicate = relation.predicate
    try:
        act = TeachingAct(predicate)
    except ValueError:
        return None
    if type(act) is not TeachingAct:
        return None
    if act is TeachingAct.EXPLAIN:
        domain_token, separator, band_token = relation.object.partition(":")
        if separator != ":" or ":" in band_token or not domain_token:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "object",
                "bad_claim",
            )
            return None
        if band_token not in _EXPLAIN_BANDS:
            _LOG.error(
                "teaching_validation_failed field=%s reason_code=%s",
                "band",
                "bad_claim",
            )
            return None
        domain = _domain_token(domain_token)
        if domain is None:
            return None
        return act, domain, ClaimBand(band_token)
    if ":" in relation.object:
        _LOG.error(
            "teaching_validation_failed field=%s reason_code=%s",
            "object",
            "bad_claim",
        )
        return None
    domain = _domain_token(relation.object)
    if domain is None:
        return None
    return act, domain, ClaimBand.UNSPECIFIED

