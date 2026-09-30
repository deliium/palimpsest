"""Owner-scoped declarative advice. This is not a belief or a skill level.

Advice records heard public acts. It does not import ``world._skills``,
``world._teaching``, or ``world._state``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from unicodedata import category

from agents.models import AgentId

_LOG: Final[logging.Logger] = logging.getLogger("agents.cognition.teaching")

_CURSOR_CAP: Final[int] = 32
_ACT_COUNT: Final[int] = 4
_CONTRACT_VERSION: Final[str] = "teaching-interaction-v1"


class AdviceAct(StrEnum):
    """Closed acts. String values match the objective teaching predicates."""

    REQUEST_INSTRUCTION = "request_instruction"
    EXPLAIN = "explain"
    DEMONSTRATE = "demonstrate"
    PRACTICE_TOGETHER = "practice_together"


class AdviceDomain(StrEnum):
    """Closed domain tokens. String values match the objective skill domains."""

    FORAGING = "foraging"
    NAVIGATION = "navigation"
    RESOURCE_DETECTION = "resource_detection"
    CRAFTING = "crafting"
    BUILDING = "building"
    HEALING = "healing"
    COMMUNICATION = "communication"
    TEACHING = "teaching"


class AdviceBand(StrEnum):
    """Public band stored with the advice. ``unspecified`` has no claim."""

    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"
    UNSPECIFIED = "unspecified"


_EXPLAIN_BANDS: Final[frozenset[AdviceBand]] = frozenset(
    {AdviceBand.LOW, AdviceBand.UNCERTAIN, AdviceBand.HIGH}
)


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.error(
        "teaching_validation_failed field=%s reason_code=%s",
        field_name,
        code,
    )
    return ValueError(f"{field_name}: {code}")


def _require_act(value: object) -> AdviceAct:
    if type(value) is not AdviceAct:
        raise _fail("act", "unknown_act")
    return value


def _require_domain(value: object) -> AdviceDomain:
    if type(value) is not AdviceDomain:
        raise _fail("domain", "unknown_domain")
    return value


def _require_band(value: object) -> AdviceBand:
    if type(value) is not AdviceBand:
        raise _fail("band", "bad_claim")
    return value


def _occurrence_id(value: object) -> str:
    if not isinstance(value, str):
        raise _fail("occurrence_id", "invalid_type")
    length = len(value)
    if length < 1 or length > 128 or value != value.strip():
        raise _fail("occurrence_id", "invalid_type")
    if any(category(char) == "Cc" for char in value):
        raise _fail("occurrence_id", "invalid_type")
    return value


def _delivery_tick(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _fail("delivery_tick", "invalid_type")
    return value


@dataclass(frozen=True, slots=True)
class DeclarativeAdvice:
    """One heard act. The band is ``unspecified`` when the act has no claim."""

    occurrence_id: str
    source_agent_id: AgentId
    act: AdviceAct
    domain: AdviceDomain
    band: AdviceBand
    delivery_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "occurrence_id", _occurrence_id(self.occurrence_id))
        if type(self.source_agent_id) is not AgentId:
            raise _fail("source_agent_id", "invalid_type")
        act = _require_act(self.act)
        band = _require_band(self.band)
        if act is AdviceAct.EXPLAIN:
            if band not in _EXPLAIN_BANDS:
                raise _fail("band", "bad_claim")
        elif band is not AdviceBand.UNSPECIFIED:
            raise _fail("band", "bad_claim")
        object.__setattr__(self, "act", act)
        object.__setattr__(self, "domain", _require_domain(self.domain))
        object.__setattr__(self, "band", band)
        object.__setattr__(self, "delivery_tick", _delivery_tick(self.delivery_tick))


@dataclass(frozen=True, slots=True)
class AdviceStore:
    """Owner-scoped advice. Occurrence ids cap at 32 per domain."""

    owner_id: AgentId
    rows: tuple[DeclarativeAdvice, ...] = ()

    def __post_init__(self) -> None:
        if type(self.owner_id) is not AgentId:
            raise _fail("owner_id", "invalid_type")
        if isinstance(self.rows, (str, bytes, set, frozenset)) or not isinstance(
            self.rows, tuple
        ):
            raise _fail("rows", "invalid_type")
        seen: set[str] = set()
        counts: dict[AdviceDomain, int] = {}
        normalized: list[DeclarativeAdvice] = []
        for row in self.rows:
            if type(row) is not DeclarativeAdvice:
                raise _fail("rows", "invalid_type")
            if row.occurrence_id in seen:
                raise _fail("occurrence_id", "duplicate_occurrence")
            seen.add(row.occurrence_id)
            counts[row.domain] = counts.get(row.domain, 0) + 1
            if counts[row.domain] > _CURSOR_CAP:
                raise _fail("occurrence_id", "cursor_overflow")
            normalized.append(row)
        object.__setattr__(self, "rows", tuple(normalized))
        _LOG.debug(
            "advice_store_built policy_version=%s act_count=%s",
            _CONTRACT_VERSION,
            _ACT_COUNT,
        )

    def record(self, advice: DeclarativeAdvice) -> AdviceStore:
        """Append one row. A stored occurrence id is skipped.

        The cursor keeps the newest 32 rows of that domain and drops the oldest.
        """
        if type(advice) is not DeclarativeAdvice:
            raise _fail("rows", "invalid_type")
        if any(row.occurrence_id == advice.occurrence_id for row in self.rows):
            return self
        retained: list[DeclarativeAdvice] = []
        domain_seen = 0
        for row in self.rows:
            if row.domain is advice.domain:
                domain_seen += 1
        overflow = domain_seen + 1 - _CURSOR_CAP
        dropped = 0
        for row in self.rows:
            if row.domain is advice.domain and dropped < overflow:
                dropped += 1
                continue
            retained.append(row)
        retained.append(advice)
        return AdviceStore(owner_id=self.owner_id, rows=tuple(retained))


def empty_advice_store(owner_id: AgentId) -> AdviceStore:
    """An owner starts with no heard acts."""
    if type(owner_id) is not AgentId:
        raise _fail("owner_id", "invalid_type")
    return AdviceStore(owner_id=owner_id)


@dataclass(frozen=True, slots=True)
class TeachingClaimPolicy:
    """Cognition-side teaching weights. Version ``teaching-interaction-v1``."""

    belief_explain_rate: float = 0.08
    explain_low_below: float = 0.34
    explain_high_at: float = 0.67
    teaching_response_weight: float = 0.25
    belief_prior: float = 1.0
    allow_provider: bool = False
    version: str = _CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.version != _CONTRACT_VERSION:
            raise _fail("version", "unsupported_version")
        if type(self.allow_provider) is not bool:
            raise _fail("allow_provider", "invalid_type")
        rate = _unit_rate("belief_explain_rate", self.belief_explain_rate)
        low = _unit_rate("explain_low_below", self.explain_low_below)
        high = _unit_rate("explain_high_at", self.explain_high_at)
        if low >= high:
            raise _fail("explain_low_below", "threshold_order")
        weight = _unit_rate("teaching_response_weight", self.teaching_response_weight)
        prior = _nonnegative("belief_prior", self.belief_prior)
        object.__setattr__(self, "belief_explain_rate", rate)
        object.__setattr__(self, "explain_low_below", low)
        object.__setattr__(self, "explain_high_at", high)
        object.__setattr__(self, "teaching_response_weight", weight)
        object.__setattr__(self, "belief_prior", prior)
        _LOG.debug(
            "teaching_claim_policy_built policy_version=%s act_count=%s",
            self.version,
            _ACT_COUNT,
        )


def _unit_rate(field_name: str, value: object) -> float:
    number = _nonnegative(field_name, value)
    if number > 1.0:
        raise _fail(field_name, "out_of_range")
    return number


def _nonnegative(field_name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(field_name, "not_finite")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise _fail(field_name, "not_finite")
    return number
