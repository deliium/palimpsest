"""Closed detached-analysis vocabulary for multi-stage supply chains.

V4-19 owns the declared ``supply_chains`` context. Dependency graphs, chain
paths, bottlenecks, and lineage are analytical labels over committed production
events and explicitly detached facts. No central planner, optimizer, quota,
automatic allocation, price, money, currency, ranking, severity, or
recommendation exists.
"""

from __future__ import annotations

import hashlib
import logging
import re
from enum import StrEnum
from typing import Final

__all__ = [
    "NONE_TOKEN",
    "SUPPLY_BOTTLENECK_PREFIX",
    "SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION",
    "SUPPLY_CHAIN_ERROR_CODES",
    "SUPPLY_CHAIN_PREFIX",
    "SUPPLY_EDGE_PREFIX",
    "SUPPLY_FORBIDDEN_KEYS",
    "SUPPLY_LAYER_FORBIDDEN_PREFIXES",
    "SUPPLY_STAGE_PREFIX",
    "SupplyBottleneckKind",
    "SupplyChainError",
    "SupplyCoverage",
    "SupplyEdgeKind",
    "SupplyLayer",
    "SupplyNodeKind",
    "analysis_supply_token",
    "canonical_supply_pair",
]

SUPPLY_CHAIN_ANALYSIS_POLICY_VERSION: Final[str] = "supply-chains.v1"
SUPPLY_STAGE_PREFIX: Final[str] = "sc-stage-"
SUPPLY_EDGE_PREFIX: Final[str] = "sc-edge-"
SUPPLY_CHAIN_PREFIX: Final[str] = "sc-chain-"
SUPPLY_BOTTLENECK_PREFIX: Final[str] = "sc-neck-"
NONE_TOKEN: Final[str] = "-"

_TOKEN_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^sc-(?:stage|edge|chain|neck)-[0-9a-f]{16}$"
)
_TOKEN_PREFIXES: Final[frozenset[str]] = frozenset(
    {
        SUPPLY_STAGE_PREFIX,
        SUPPLY_EDGE_PREFIX,
        SUPPLY_CHAIN_PREFIX,
        SUPPLY_BOTTLENECK_PREFIX,
    }
)

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.contract")


class SupplyCoverage(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class SupplyLayer(StrEnum):
    OBJECTIVE_DERIVED = "objective_derived"
    ANALYTICAL = "analytical"
    OWNER_CLAIMS = "owner_claims"


class SupplyNodeKind(StrEnum):
    RESOURCE = "resource"
    ITEM = "item"
    STRUCTURE = "structure"
    STORAGE = "storage"
    LOCATION = "location"
    INFRASTRUCTURE = "infrastructure"
    ORGANIZATION = "organization"
    TOOL = "tool"
    SKILL = "skill"


class SupplyEdgeKind(StrEnum):
    RESOURCE_TO_ITEM = "resource_to_item"
    ITEM_TO_ITEM = "item_to_item"
    ITEM_TO_STRUCTURE = "item_to_structure"
    ITEM_TO_STORAGE = "item_to_storage"
    TRANSPORT = "transport"
    LOCATION_TO_STAGE = "location_to_stage"
    INFRASTRUCTURE_TO_STAGE = "infrastructure_to_stage"
    ORGANIZATION_TO_STAGE = "organization_to_stage"
    TOOL_TO_STAGE = "tool_to_stage"
    SKILL_TO_STAGE = "skill_to_stage"


class SupplyBottleneckKind(StrEnum):
    UPSTREAM_SHORTFALL = "upstream_shortfall"
    SINGLE_LOCATION_CONCENTRATION = "single_location_concentration"
    TRANSPORT_DEPENDENCY = "transport_dependency"
    TOOL_DEPENDENCY = "tool_dependency"
    INFRASTRUCTURE_DEPENDENCY = "infrastructure_dependency"
    ORGANIZATION_DEPENDENCY = "organization_dependency"
    SKILL_CONSTRAINT = "skill_constraint"


SUPPLY_CHAIN_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "supply_chain_invalid_policy",
        "supply_chain_invalid_cap",
        "supply_chain_invalid_window",
        "supply_chain_invalid_recipe_spec",
        "supply_chain_duplicate_event",
        "supply_chain_invalid_event_order",
        "supply_chain_evidence_truncated",
        "supply_chain_stage_truncated",
        "supply_chain_edge_truncated",
        "supply_chain_chain_truncated",
        "supply_chain_bottleneck_truncated",
        "supply_chain_lineage_truncated",
        "supply_chain_location_truncated",
        "supply_chain_organization_truncated",
        "supply_chain_invalid_token",
        "supply_chain_layer_leak",
    }
)

SUPPLY_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "price",
        "cost",
        "currency",
        "money",
        "quota",
        "allocation",
        "optimizer",
        "plan_score",
        "priority_score",
        "recommendation",
        "rank",
        "severity",
    }
)

SUPPLY_LAYER_FORBIDDEN_PREFIXES: Final[dict[SupplyLayer, frozenset[str]]] = {
    SupplyLayer.OBJECTIVE_DERIVED: frozenset(
        {SUPPLY_CHAIN_PREFIX, SUPPLY_BOTTLENECK_PREFIX}
    ),
    SupplyLayer.ANALYTICAL: frozenset(),
    SupplyLayer.OWNER_CLAIMS: frozenset(
        {SUPPLY_STAGE_PREFIX, SUPPLY_EDGE_PREFIX, SUPPLY_CHAIN_PREFIX}
    ),
}


class SupplyChainError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "supply_chain_invalid_policy"
        return str(self.args[0])


def analysis_supply_token(prefix: str, payload: str) -> str:
    """Mint a deterministic ``sc-`` token over a closed prefix and payload."""
    if prefix not in _TOKEN_PREFIXES:
        _LOG.warning(
            "supply_chain_policy_invalid field=prefix code=supply_chain_invalid_token"
        )
        raise SupplyChainError("supply_chain_invalid_token")
    if not isinstance(payload, str) or not payload:
        _LOG.warning(
            "supply_chain_policy_invalid field=payload code=supply_chain_invalid_token"
        )
        raise SupplyChainError("supply_chain_invalid_token")
    digest = hashlib.blake2b(f"{prefix}{payload}".encode(), digest_size=8).hexdigest()
    _LOG.debug("supply_chain_token_minted prefix=%s", prefix)
    return f"{prefix}{digest}"


def require_supply_token(value: object) -> str:
    if not isinstance(value, str) or not _TOKEN_PATTERN.match(value):
        raise SupplyChainError("supply_chain_invalid_token")
    return value


def canonical_supply_pair(left: object, right: object) -> tuple[str, str]:
    """Return an order-independent pair of two distinct non-empty tokens."""
    if (
        not isinstance(left, str)
        or not left
        or not isinstance(right, str)
        or not right
        or left == right
    ):
        raise SupplyChainError("supply_chain_invalid_token")
    return (left, right) if left < right else (right, left)
