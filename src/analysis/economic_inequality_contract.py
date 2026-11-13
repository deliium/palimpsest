"""Closed detached vocabulary for economic-inequality analysis.

The surface measures distributions and inequality indices over already-committed
economic evidence. It never asserts legitimate ownership, desert, merit, fault,
poverty status, or a welfare ranking, and it never feeds cognition, prompts,
memory, world state, observer semantics, or stop selectors.

Stable error codes (``EconomicInequalityError.reason_code``):

- ``economic_inequality_invalid_input``
- ``economic_inequality_invalid_policy``
- ``economic_inequality_invalid_window``
- ``economic_inequality_invalid_row``
- ``economic_inequality_forbidden_key``
- ``economic_inequality_layer_leak``
- ``economic_inequality_cap_exceeded``
"""

from __future__ import annotations

import hashlib
import logging
from enum import StrEnum
from typing import Final

__all__ = [
    "ECONOMIC_INEQUALITY_ANALYSIS_LAYER",
    "ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION",
    "ECONOMIC_INEQUALITY_ANALYSIS_TOKEN_HEX_LEN",
    "ECONOMIC_INEQUALITY_COHORT_PREFIX",
    "ECONOMIC_INEQUALITY_FORBIDDEN_KEYS",
    "ECONOMIC_INEQUALITY_OWNER_PREFIX",
    "ECONOMIC_INEQUALITY_SOCIETY_PREFIX",
    "EconomicInequalityAvailability",
    "EconomicInequalityComparisonKind",
    "EconomicInequalityCoverage",
    "EconomicInequalityDimension",
    "EconomicInequalityError",
    "EconomicInequalityLayer",
    "EconomicInequalityMeasure",
    "EconomicInequalityTrend",
    "assert_economic_inequality_layer_separation",
    "economic_inequality_cohort_token",
    "economic_inequality_measures_for",
    "economic_inequality_owner_token",
    "economic_inequality_society_token",
    "economic_inequality_token_hash",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.contract"
)

ECONOMIC_INEQUALITY_ANALYSIS_POLICY_VERSION: Final[str] = "economic-inequality.v1"
ECONOMIC_INEQUALITY_OWNER_PREFIX: Final[str] = "eio-"
ECONOMIC_INEQUALITY_COHORT_PREFIX: Final[str] = "eic-"
ECONOMIC_INEQUALITY_SOCIETY_PREFIX: Final[str] = "eis-"
ECONOMIC_INEQUALITY_ANALYSIS_TOKEN_HEX_LEN: Final[int] = 16


class EconomicInequalityDimension(StrEnum):
    """Six independent measured dimensions; never pooled into one score."""

    RESOURCE_POSSESSION = "resource_possession"
    PRODUCTIVE_TOOL_ACCESS = "productive_tool_access"
    INFRASTRUCTURE_ACCESS = "infrastructure_access"
    STORAGE_ACCESS = "storage_access"
    CREDIT_RELATIONSHIP = "credit_relationship"
    ORGANIZATIONAL_RESOURCE_CONTROL = "organizational_resource_control"


class EconomicInequalityMeasure(StrEnum):
    """Closed measured quantity vocabulary."""

    OBSERVED_ITEM_COUNT = "observed_item_count"
    OBSERVED_TOOL_COUNT = "observed_tool_count"
    ACCESSIBLE_INFRASTRUCTURE_COUNT = "accessible_infrastructure_count"
    ACCESSIBLE_STORAGE_COUNT = "accessible_storage_count"
    CLAIMED_PRINCIPAL_QUANTITY = "claimed_principal_quantity"
    OBSERVED_REPAYMENT_QUANTITY = "observed_repayment_quantity"
    CLAIMED_RELATIONSHIP_COUNT = "claimed_relationship_count"
    CLAIMED_RESOURCE_CONTROL_COUNT = "claimed_resource_control_count"
    CLAIMED_STORAGE_CONTROL_COUNT = "claimed_storage_control_count"


class EconomicInequalityLayer(StrEnum):
    """Strictly separated objective, owner-claim, and analytical layers."""

    OBJECTIVE_POSSESSION = "objective_possession"
    OBJECTIVE_ACCESS = "objective_access"
    OWNER_CLAIM = "owner_claim"
    ANALYTICAL_COMPARISON = "analytical_comparison"


ECONOMIC_INEQUALITY_ANALYSIS_LAYER = EconomicInequalityLayer


class EconomicInequalityCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class EconomicInequalityAvailability(StrEnum):
    """Closed availability of one distribution or comparison."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


class EconomicInequalityTrend(StrEnum):
    """Closed longitudinal direction; never a value judgement."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


class EconomicInequalityComparisonKind(StrEnum):
    """Closed comparison stratum kind."""

    COHORT = "cohort"
    SOCIETY = "society"


ECONOMIC_INEQUALITY_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "wealth",
        "net_worth",
        "ownership",
        "ownership_score",
        "legitimate_owner",
        "merit",
        "poverty",
        "rank",
        "score",
    }
)

_DIMENSION_MEASURES: Final[
    dict[EconomicInequalityDimension, tuple[EconomicInequalityMeasure, ...]]
] = {
    EconomicInequalityDimension.RESOURCE_POSSESSION: (
        EconomicInequalityMeasure.OBSERVED_ITEM_COUNT,
    ),
    EconomicInequalityDimension.PRODUCTIVE_TOOL_ACCESS: (
        EconomicInequalityMeasure.OBSERVED_TOOL_COUNT,
    ),
    EconomicInequalityDimension.INFRASTRUCTURE_ACCESS: (
        EconomicInequalityMeasure.ACCESSIBLE_INFRASTRUCTURE_COUNT,
    ),
    EconomicInequalityDimension.STORAGE_ACCESS: (
        EconomicInequalityMeasure.ACCESSIBLE_STORAGE_COUNT,
    ),
    EconomicInequalityDimension.CREDIT_RELATIONSHIP: (
        EconomicInequalityMeasure.CLAIMED_PRINCIPAL_QUANTITY,
        EconomicInequalityMeasure.OBSERVED_REPAYMENT_QUANTITY,
        EconomicInequalityMeasure.CLAIMED_RELATIONSHIP_COUNT,
    ),
    EconomicInequalityDimension.ORGANIZATIONAL_RESOURCE_CONTROL: (
        EconomicInequalityMeasure.CLAIMED_RESOURCE_CONTROL_COUNT,
        EconomicInequalityMeasure.CLAIMED_STORAGE_CONTROL_COUNT,
    ),
}


def economic_inequality_measures_for(
    dimension: EconomicInequalityDimension,
) -> tuple[EconomicInequalityMeasure, ...]:
    """Return the closed measures for ``dimension``."""

    if type(dimension) is not EconomicInequalityDimension:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    return _DIMENSION_MEASURES[dimension]


class EconomicInequalityError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "economic_inequality_invalid_input"
        return str(self.args[0])


def economic_inequality_token_hash(prefix: str, *parts: str) -> str:
    """Length-prefixed content-addressed token helper."""

    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{prefix}{digest[:ECONOMIC_INEQUALITY_ANALYSIS_TOKEN_HEX_LEN]}"


def economic_inequality_owner_token(owner_id: str) -> str:
    """Mint the stable ``eio-`` owner token used by detached rows."""

    if type(owner_id) is not str or not owner_id:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    return economic_inequality_token_hash(
        ECONOMIC_INEQUALITY_OWNER_PREFIX, owner_id
    )


def economic_inequality_cohort_token(generation_index: int) -> str:
    """Mint the stable ``eic-`` cohort token for one generation index."""

    if (
        isinstance(generation_index, bool)
        or type(generation_index) is not int
        or generation_index < 0
    ):
        raise EconomicInequalityError("economic_inequality_invalid_input")
    return economic_inequality_token_hash(
        ECONOMIC_INEQUALITY_COHORT_PREFIX, str(generation_index)
    )


def economic_inequality_society_token(society_id: str) -> str:
    """Mint the stable ``eis-`` token for one detached society candidate."""

    if type(society_id) is not str or not society_id:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    return economic_inequality_token_hash(
        ECONOMIC_INEQUALITY_SOCIETY_PREFIX, society_id
    )


def _layer_group(layer: object) -> str:
    value = layer.value if hasattr(layer, "value") else str(layer)
    if value in {
        EconomicInequalityLayer.OBJECTIVE_POSSESSION.value,
        EconomicInequalityLayer.OBJECTIVE_ACCESS.value,
    }:
        return "objective"
    if value == EconomicInequalityLayer.OWNER_CLAIM.value:
        return "owner_claim"
    if value == EconomicInequalityLayer.ANALYTICAL_COMPARISON.value:
        return "analytical_comparison"
    raise EconomicInequalityError("economic_inequality_layer_leak")


def assert_economic_inequality_layer_separation(*rows: object) -> None:
    """Reject a mixed list of objective, claim, and analytical rows."""

    observed: set[tuple[str, ...]] = set()
    for row in rows:
        layers = getattr(row, "source_layers", None)
        if layers is None:
            _LOG.error("economic_inequality_layer_leak")
            raise EconomicInequalityError("economic_inequality_layer_leak")
        try:
            normalized = tuple(
                _layer_group(layer) for layer in layers
            )
        except (TypeError, EconomicInequalityError) as error:
            _LOG.error("economic_inequality_layer_leak")
            raise EconomicInequalityError(
                "economic_inequality_layer_leak"
            ) from error
        observed.add(normalized)
    if len(observed) > 1:
        _LOG.error("economic_inequality_layer_leak")
        raise EconomicInequalityError("economic_inequality_layer_leak")
