"""Closed vocabulary for detached market-like institution analysis.

Analysis reads committed exchange evidence and produces objective venue rows plus
owner-token joins. It never reads ``WorldState``, cognition ledgers, API objects,
or persistence. No price, money, credit, allocation, quota, score, ranking, or
recommendation vocabulary exists.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Final

__all__ = [
    "MARKET_ANALYSIS_HEX_LEN",
    "MARKET_CANDIDATE_PREFIX",
    "MARKET_FORBIDDEN_KEYS",
    "MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION",
    "MARKET_INSTITUTIONS_ERROR_CODES",
    "MARKET_LAYER_FORBIDDEN_PREFIXES",
    "MARKET_NONE_TOKEN",
    "MARKET_VENUE_PREFIX",
    "MarketAlignment",
    "MarketAttemptKind",
    "MarketCoverage",
    "MarketGatheringStatus",
    "MarketInstitutionsError",
    "MarketLayer",
    "MarketLineageStatus",
    "MarketVenueStatus",
    "market_candidate_token",
    "market_venue_token",
    "require_market_candidate_token",
    "require_market_venue_token",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.market_institutions.contract"
)

MARKET_INSTITUTIONS_ANALYSIS_POLICY_VERSION: Final[str] = "market-institutions.v1"
MARKET_VENUE_PREFIX: Final[str] = "mkt-ven-"
MARKET_CANDIDATE_PREFIX: Final[str] = "mktc-"
MARKET_NONE_TOKEN: Final[str] = "none"
MARKET_ANALYSIS_HEX_LEN: Final[int] = 16

_VENUE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{MARKET_VENUE_PREFIX}[0-9a-f]{{{MARKET_ANALYSIS_HEX_LEN}}}$"
)
_CANDIDATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"^{MARKET_CANDIDATE_PREFIX}[0-9a-f]{{{MARKET_ANALYSIS_HEX_LEN}}}$"
)


class MarketCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class MarketLayer(StrEnum):
    """Strictly separated objective, owner, analytical, and comparison layers."""

    OBJECTIVE_EXCHANGE = "objective_exchange"
    OWNER_EXPECTATION = "owner_expectation"
    ANALYTICAL_MARKET = "analytical_market"
    COMPARISON_VIEW = "comparison_view"


class MarketVenueStatus(StrEnum):
    """Closed objective venue persistence status; never a score or rank."""

    SINGLE_GATHERING = "single_gathering"
    RECURRING_GATHERING = "recurring_gathering"
    MARKET_LIKE_PERSISTENT = "market_like_persistent"
    DORMANT = "dormant"


class MarketGatheringStatus(StrEnum):
    """Closed gathering qualification status."""

    GATHERING = "gathering"
    BELOW_THRESHOLD = "below_threshold"


class MarketLineageStatus(StrEnum):
    """Closed forward-only lineage status."""

    EMERGED = "emerged"
    CONTINUED = "continued"
    TRANSFORMED = "transformed"
    SPLIT = "split"
    MERGE = "merge"
    DISSOLVED = "dissolved"


class MarketAlignment(StrEnum):
    """Researcher-only alignment classification; never reaches cognition."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


class MarketAttemptKind(StrEnum):
    """Closed exchange-attempt kind."""

    OFFER = "offer"
    COUNTEROFFER = "counteroffer"
    WITHDRAW = "withdraw"


MARKET_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "clearing_price",
        "bid",
        "ask",
        "spread",
        "fee",
        "commission",
        "tax",
        "debt",
        "credit_limit",
        "market_score",
        "score",
        "ranking",
        "severity",
        "recommendation",
        "allocation",
        "quota",
        "central_planner",
        "is_money",
        "medium_of_exchange",
        "store_of_value",
        "unit_of_account",
        "volume",
        "turnover",
        "liquidity",
    }
)

MARKET_LAYER_FORBIDDEN_PREFIXES: Final[Mapping[MarketLayer, frozenset[str]]] = {
    MarketLayer.OBJECTIVE_EXCHANGE: frozenset(
        {MARKET_VENUE_PREFIX, MARKET_CANDIDATE_PREFIX}
    ),
    MarketLayer.OWNER_EXPECTATION: frozenset({MARKET_CANDIDATE_PREFIX}),
    MarketLayer.ANALYTICAL_MARKET: frozenset({"event_token", "raw_event_token"}),
    MarketLayer.COMPARISON_VIEW: frozenset({"event_token", "raw_event_token"}),
}

MARKET_INSTITUTIONS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "market_institutions_invalid_input",
        "market_institutions_invalid_policy",
        "market_institutions_invalid_identity",
        "market_institutions_invalid_window",
        "market_institutions_duplicate_event",
        "market_institutions_invalid_exchange",
        "market_institutions_unknown_location",
        "market_institutions_exchange_truncated",
        "market_institutions_attempt_truncated",
        "market_institutions_venue_truncated",
        "market_institutions_gathering_truncated",
        "market_institutions_market_truncated",
        "market_institutions_participation_truncated",
        "market_institutions_expectation_truncated",
        "market_institutions_role_truncated",
        "market_institutions_record_truncated",
        "market_institutions_lineage_truncated",
        "market_institutions_layer_leak",
    }
)


class MarketInstitutionsError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "market_institutions_invalid_input"
        return str(self.args[0])


def _require_material(value: str) -> str:
    if type(value) is not str or not value:
        _LOG.error(
            "market_institutions_contract_invalid "
            "reason_code=market_institutions_invalid_identity"
        )
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    return value


def market_venue_token(location_token: str) -> str:
    """Content-addressed ``mkt-ven-`` token for one logical location."""

    material = _require_material(location_token)
    digest = hashlib.sha256(f"venue\x1f{material}".encode()).hexdigest()
    return f"{MARKET_VENUE_PREFIX}{digest[:MARKET_ANALYSIS_HEX_LEN]}"


def market_candidate_token(venue_tokens: Sequence[str]) -> str:
    """Content-addressed ``mktc-`` token for a sorted venue-id set."""

    if isinstance(venue_tokens, (str, bytes)) or not isinstance(
        venue_tokens, Sequence
    ):
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    values = tuple(sorted(set(venue_tokens)))
    if not values:
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    for value in values:
        require_market_venue_token(value)
    payload = "market\x1f" + "\x1e".join(values)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{MARKET_CANDIDATE_PREFIX}{digest[:MARKET_ANALYSIS_HEX_LEN]}"


def require_market_venue_token(value: str) -> str:
    """Validate one exact ``mkt-ven-`` token."""

    if type(value) is not str or _VENUE_PATTERN.match(value) is None:
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    return value


def require_market_candidate_token(value: str) -> str:
    """Validate one exact ``mktc-`` token."""

    if type(value) is not str or _CANDIDATE_PATTERN.match(value) is None:
        raise MarketInstitutionsError("market_institutions_invalid_identity")
    return value
