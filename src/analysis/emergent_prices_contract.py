"""Closed vocabulary for detached emergent price analysis.

Analysis reconstructs exchange-implied ratios and analytical distributions from
committed events and detached owner export rows. It never reads ``WorldState``,
cognition ledgers, persistence, API objects, or observers. No canonical price,
money, currency, credit, allocation, quota, score, ranking, or recommendation
vocabulary exists.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from enum import StrEnum
from typing import Final

__all__ = [
    "EMERGENT_PRICES_ANALYSIS_POLICY_VERSION",
    "PRICE_ALIGNMENT",
    "PRICE_ANALYSIS_ERROR_CODES",
    "PRICE_ANALYSIS_HEX_LEN",
    "PRICE_DISTRIBUTION_PREFIX",
    "PRICE_EXPECTATION_LEVELS",
    "PRICE_EXPECTATION_PREFIX",
    "PRICE_FORBIDDEN_KEYS",
    "PRICE_LAYER_FORBIDDEN_PREFIXES",
    "PRICE_MARKET_NONE_TOKEN",
    "PRICE_QUOTE_PREFIX",
    "PRICE_RELATION_PREFIX",
    "EmergentPriceAnalysisError",
    "PriceAlignment",
    "PriceCoverage",
    "PriceDistributionStatus",
    "PriceLayer",
    "PricePairing",
    "PriceQuoteDirection",
    "PriceQuoteSource",
    "PriceRelation",
    "PriceSampleSource",
    "PriceUnitSource",
    "price_distribution_token",
    "price_expectation_token",
    "price_quote_token",
    "price_relation_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.emergent_prices.contract")

EMERGENT_PRICES_ANALYSIS_POLICY_VERSION: Final[str] = "emergent-prices.v1"
PRICE_EXPECTATION_PREFIX: Final[str] = "prce-"
PRICE_QUOTE_PREFIX: Final[str] = "prcq-"
PRICE_DISTRIBUTION_PREFIX: Final[str] = "prcd-"
PRICE_RELATION_PREFIX: Final[str] = "prcr-"
PRICE_MARKET_NONE_TOKEN: Final[str] = "none"
PRICE_ANALYSIS_HEX_LEN: Final[int] = 16

PRICE_EXPECTATION_LEVELS: Final[frozenset[str]] = frozenset(
    {"none", "weak", "expected", "strong"}
)


class PriceCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class PriceLayer(StrEnum):
    """Strictly separated objective, owner, analytical, and comparison layers."""

    OBJECTIVE_EXCHANGE = "objective_exchange"
    OWNER_EXPECTATION = "owner_expectation"
    ANALYTICAL_DISTRIBUTION = "analytical_distribution"
    COMPARISON_VIEW = "comparison_view"


class PriceUnitSource(StrEnum):
    """Closed source of one owner unit candidate."""

    OWNER_REFERENCE = "owner_reference"
    OBSERVED_MEDIUM = "observed_medium"
    EXCHANGE_COUNTERPART = "exchange_counterpart"
    QUOTED = "quoted"
    UNKNOWN = "unknown"


class PriceQuoteDirection(StrEnum):
    """Closed direction of one quoted offer."""

    GIVE_FOR_UNIT = "give_for_unit"
    UNIT_FOR_GIVE = "unit_for_give"


class PriceQuoteSource(StrEnum):
    """Closed provenance of one quote."""

    OBSERVED_OFFER = "observed_offer"
    COMMUNICATED = "communicated"
    SELF_AUTHORED = "self_authored"


class PricePairing(StrEnum):
    """Closed outcome of one exchange-side pairing attempt."""

    PAIRED = "paired"
    HETEROGENEOUS = "heterogeneous"
    SAME_KIND = "same_kind"
    OUT_OF_RANGE = "out_of_range"


class PriceDistributionStatus(StrEnum):
    """Closed availability of one analytical distribution."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


class PriceSampleSource(StrEnum):
    """Closed source of distribution samples; never pooled together."""

    COMPLETED = "completed"
    QUOTED = "quoted"


class PriceRelation(StrEnum):
    """Closed pairwise convergence classification; never a score."""

    CONVERGED = "converged"
    PARTIALLY_CONVERGED = "partially_converged"
    DIVERGENT = "divergent"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class PriceAlignment(StrEnum):
    """Researcher-only alignment; never reaches cognition."""

    CONSISTENT = "consistent"
    UNRESOLVED = "unresolved"
    INCONSISTENT = "inconsistent"
    NOT_APPLICABLE = "not_applicable"


PRICE_ALIGNMENT: Final[frozenset[PriceAlignment]] = frozenset(PriceAlignment)

PRICE_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "canonical_price",
        "price_index",
        "clearing_price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "bid",
        "ask",
        "spread",
        "fee",
        "commission",
        "tax",
        "debt",
        "credit_limit",
        "market_score",
        "ranking",
        "severity",
        "recommendation",
        "allocation",
        "quota",
        "is_money",
        "medium_of_exchange",
        "store_of_value",
        "unit_of_account",
        "central_planner",
    }
)

PRICE_LAYER_FORBIDDEN_PREFIXES: Final[Mapping[PriceLayer, frozenset[str]]] = {
    PriceLayer.OBJECTIVE_EXCHANGE: frozenset(
        {
            PRICE_EXPECTATION_PREFIX,
            PRICE_QUOTE_PREFIX,
            PRICE_DISTRIBUTION_PREFIX,
            PRICE_RELATION_PREFIX,
        }
    ),
    PriceLayer.OWNER_EXPECTATION: frozenset(
        {PRICE_DISTRIBUTION_PREFIX, PRICE_RELATION_PREFIX}
    ),
    PriceLayer.ANALYTICAL_DISTRIBUTION: frozenset(
        {"event_token", "raw_event_token"}
    ),
    PriceLayer.COMPARISON_VIEW: frozenset({"event_token", "raw_event_token"}),
}

PRICE_ANALYSIS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "price_analysis_invalid_policy",
        "price_analysis_invalid_row",
        "price_analysis_invalid_window",
        "price_analysis_cap_exceeded",
        "price_analysis_forbidden_key",
        "price_analysis_layer_leak",
        "price_analysis_missing_input",
    }
)


class EmergentPriceAnalysisError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "price_analysis_invalid_row"
        return str(self.args[0])


def _require_material(value: object) -> str:
    if type(value) is not str or not value:
        _LOG.error(
            "emergent_prices_analysis_invalid "
            "code=price_analysis_invalid_row"
        )
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


def _token_hash(prefix: str, *parts: str) -> str:
    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:PRICE_ANALYSIS_HEX_LEN]}"


def price_expectation_token(
    owner_token: str,
    item_kind: str,
    unit_token: str,
    window_index: int,
    unit_source: str,
) -> str:
    """Content-addressed ``prce-`` token for one owner expectation."""

    return _token_hash(
        PRICE_EXPECTATION_PREFIX,
        _require_material(owner_token),
        _require_material(item_kind),
        _require_material(unit_token),
        str(_require_window(window_index)),
        _require_material(unit_source),
    )


def price_quote_token(
    owner_token: str,
    venue_id: str,
    item_kind: str,
    unit_token: str,
    direction: str,
    source: str,
    source_tick: int,
    window_index: int,
) -> str:
    """Content-addressed ``prcq-`` token for one owner quote row.

    The source and source tick participate in the identity because a bounded
    owner ledger may retain several quotes for the same window, pair, and
    direction. Without them, distinct quotes would share one pagination key.
    """

    return _token_hash(
        PRICE_QUOTE_PREFIX,
        _require_material(owner_token),
        _require_material(venue_id),
        _require_material(item_kind),
        _require_material(unit_token),
        _require_material(direction),
        _require_material(source),
        str(_require_source_tick(source_tick)),
        str(_require_window(window_index)),
    )


def price_distribution_token(
    group_token: str,
    window_index: int,
    item_kind: str,
    unit_token: str,
    unit_source: str,
    sample_source: str,
) -> str:
    """Content-addressed ``prcd-`` token for one distribution group.

    Completed and quoted distributions are separate analytical rows, so the
    unit source and sample source must participate in the identity.
    """

    return _token_hash(
        PRICE_DISTRIBUTION_PREFIX,
        _require_material(group_token),
        str(_require_window(window_index)),
        _require_material(item_kind),
        _require_material(unit_token),
        _require_material(unit_source),
        _require_material(sample_source),
    )


def price_relation_token(
    window_index: int,
    group_kind: str,
    group_a: str,
    group_b: str,
    item_kind: str,
    unit_token: str,
    unit_source: str,
    sample_source: str,
) -> str:
    """Content-addressed ``prcr-`` token for one symmetric relation pair."""

    left, right = sorted((group_a, group_b))
    return _token_hash(
        PRICE_RELATION_PREFIX,
        str(_require_window(window_index)),
        _require_material(group_kind),
        _require_material(left),
        _require_material(right),
        _require_material(item_kind),
        _require_material(unit_token),
        _require_material(unit_source),
        _require_material(sample_source),
    )


def _require_source_tick(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


def _require_window(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise EmergentPriceAnalysisError("price_analysis_invalid_window")
    return value
