"""Closed detached-analysis vocabulary for trade networks.

V4-18 deepens the owned ``infrastructure_networks`` V4 context, the V3
``regions_migration`` seam, and the V3 exchange/valuation seam. It adds no V4
context, flag, command, event, observer semantic type, write pair, or migration.
Trade corridors, networks, dependence, and cross-society flows are analytical
labels over committed evidence; they never feed cognition, prompts, memory,
world state, stop selectors, Observation, or presentation physics. No price,
money, currency, central planner, quota, allocation, score, or ranking exists.
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import StrEnum
from typing import Final

from world.identifiers import require_stable_id

__all__ = [
    "NONE_TOKEN",
    "TRADE_CORRIDOR_PREFIX",
    "TRADE_FORBIDDEN_KEYS",
    "TRADE_LAYER_FORBIDDEN_PREFIXES",
    "TRADE_NETWORKS_ANALYSIS_POLICY_VERSION",
    "TRADE_NETWORKS_ERROR_CODES",
    "TRADE_NETWORK_PREFIX",
    "TRADE_PAIR_PREFIX",
    "TradeCoverage",
    "TradeFlowClass",
    "TradeLayer",
    "TradeNetworksError",
    "analysis_trade_candidate_id",
    "canonical_trade_pair",
]

TRADE_NETWORKS_ANALYSIS_POLICY_VERSION: Final[str] = "trade-networks.v1"
TRADE_CORRIDOR_PREFIX: Final[str] = "trd-cor-"
TRADE_NETWORK_PREFIX: Final[str] = "trd-net-"
TRADE_PAIR_PREFIX: Final[str] = "trd-pair-"
NONE_TOKEN: Final[str] = "none"

_TRADE_ID_HEX_CHARS: Final[int] = 16
_TRADE_ID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^trd-(?:cor|net|pair)-[0-9a-f]{16}$"
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.trade_networks.contract")


class TradeFlowClass(StrEnum):
    """Closed exchangeable-flow taxonomy."""

    FOOD = "food"
    MATERIALS = "materials"
    TOOLS = "tools"
    RECORDS = "records"
    DURABLE_EXCHANGE_MEDIA = "durable_exchange_media"
    OTHER = "other"


class TradeCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class TradeLayer(StrEnum):
    """Strictly separated objective and analytical trade representations."""

    OBJECTIVE_TRANSFER = "objective_transfer"
    ANALYTICAL_CORRIDOR = "analytical_corridor"
    ANALYTICAL_NETWORK = "analytical_network"
    COMPARISON_VIEW = "comparison_view"


TRADE_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "rate",
        "money",
        "currency",
        "numeraire",
        "is_money",
        "medium_of_exchange",
        "store_of_value",
        "unit_of_account",
        "central_planner",
        "route_plan",
        "allocation",
        "quota",
        "score",
        "ranking",
    }
)

# Each layer may use only its own identity space. Objective rows never carry an
# analytical corridor/network id; corridor rows never carry a network id;
# network rows never carry a society-pair id; comparison views never carry raw
# objective event tokens.
TRADE_LAYER_FORBIDDEN_PREFIXES: Final[dict[TradeLayer, frozenset[str]]] = {
    TradeLayer.OBJECTIVE_TRANSFER: frozenset(
        {TRADE_CORRIDOR_PREFIX, TRADE_NETWORK_PREFIX}
    ),
    TradeLayer.ANALYTICAL_CORRIDOR: frozenset({TRADE_NETWORK_PREFIX}),
    TradeLayer.ANALYTICAL_NETWORK: frozenset({TRADE_PAIR_PREFIX}),
    TradeLayer.COMPARISON_VIEW: frozenset({"event_token", "raw_event_token"}),
}

TRADE_NETWORKS_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "trade_networks_invalid_identity",
        "trade_networks_invalid_pair",
        "trade_networks_invalid_input",
        "trade_networks_invalid_policy",
        "trade_networks_window_out_of_range",
        "trade_networks_duplicate_event",
        "trade_networks_invalid_exchange",
        "trade_networks_conflicting_item_kind",
        "trade_networks_missing_recipe_kind",
        "trade_networks_unknown_item_kind",
        "trade_networks_unresolved_item_origin",
        "trade_networks_transfer_truncated",
        "trade_networks_corridor_truncated",
        "trade_networks_location_truncated",
        "trade_networks_network_truncated",
        "trade_networks_lineage_truncated",
        "trade_networks_pair_truncated",
        "trade_networks_layer_leak",
    }
)


class TradeNetworksError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "trade_networks_invalid_input"
        return str(self.args[0])


def _require_nonempty_material(material: str) -> str:
    if not isinstance(material, str) or not material:
        _LOG.debug(
            "trade_networks_contract_rejected "
            "reason_code=trade_networks_invalid_identity"
        )
        raise TradeNetworksError("trade_networks_invalid_identity")
    return material


def analysis_trade_candidate_id(kind: str, material: str) -> str:
    """Content-addressed ``trd-`` id over a lowercase kind and material."""
    if not isinstance(kind, str) or not kind:
        _LOG.debug(
            "trade_networks_contract_rejected "
            "reason_code=trade_networks_invalid_identity"
        )
        raise TradeNetworksError("trade_networks_invalid_identity")
    normalized_kind = kind.lower()
    payload = _require_nonempty_material(material)
    if normalized_kind == "corridor":
        prefix = TRADE_CORRIDOR_PREFIX
    elif normalized_kind == "network":
        prefix = TRADE_NETWORK_PREFIX
    else:
        prefix = TRADE_PAIR_PREFIX
    digest = hashlib.sha256(f"{normalized_kind}\x1f{payload}".encode()).hexdigest()
    return f"{prefix}{digest[:_TRADE_ID_HEX_CHARS]}"


def require_trade_candidate_id(value: str) -> str:
    """Validate an exact ``trd-cor-``/``trd-net-``/``trd-pair-`` id."""
    if not isinstance(value, str) or not _TRADE_ID_PATTERN.match(value):
        _LOG.debug(
            "trade_networks_contract_rejected "
            "reason_code=trade_networks_invalid_identity"
        )
        raise TradeNetworksError("trade_networks_invalid_identity")
    return value


def canonical_trade_pair(left: str, right: str) -> tuple[str, str]:
    """Return a canonically ordered pair, rejecting equal or empty tokens."""
    if not isinstance(left, str) or not left or not isinstance(right, str) or not right:
        _LOG.debug(
            "trade_networks_contract_rejected reason_code=trade_networks_invalid_pair"
        )
        raise TradeNetworksError("trade_networks_invalid_pair")
    first = require_stable_id("trade_pair_left", left)
    second = require_stable_id("trade_pair_right", right)
    if first == second:
        _LOG.debug(
            "trade_networks_contract_rejected reason_code=trade_networks_invalid_pair"
        )
        raise TradeNetworksError("trade_networks_invalid_pair")
    return (first, second) if first < second else (second, first)
