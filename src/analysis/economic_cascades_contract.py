"""Closed detached vocabulary for economic-cascade analysis.

The surface measures how already-committed objective disruptions propagate
through observable production dependencies. A chain row is a
dependency-conditioned analytical link, never an objective cause claim, and the
analysis never feeds cognition, prompts, memory, world state, observer semantics,
or stop selectors.

Stable error codes (``EconomicCascadesError.reason_code``):

- ``economic_cascades_invalid_policy``
- ``economic_cascades_invalid_cap``
- ``economic_cascades_invalid_chain``
- ``economic_cascades_invalid_event_order``
- ``economic_cascades_layer_violation``
- ``economic_cascades_unstable_token``
- ``economic_cascades_forbidden_key``
- ``economic_cascades_nonfinite_value``
- ``economic_cascades_invalid_recipe_spec``
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Sequence
from enum import StrEnum
from typing import Final

__all__ = [
    "CASCADE_FORBIDDEN_KEYS",
    "CASCADE_LAYER",
    "CHAIN_TOKEN_PREFIX",
    "ECONOMIC_CASCADES_ERROR_CODES",
    "ECONOMIC_CASCADES_POLICY_VERSION",
    "ECONOMIC_CASCADES_TOKEN_HEX_LEN",
    "NONE_TOKEN",
    "PROXY_EVIDENCE_TOKEN",
    "CascadeAvailability",
    "CascadeChainState",
    "CascadeCoverage",
    "CascadeDependencyKind",
    "CascadeDisruptionKind",
    "CascadeLayer",
    "EconomicCascadesError",
    "assert_economic_cascade_layer_separation",
    "mint_chain_token",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.contract")

ECONOMIC_CASCADES_POLICY_VERSION: Final[str] = "economic-cascades.v1"
CHAIN_TOKEN_PREFIX: Final[str] = "casc-"
PROXY_EVIDENCE_TOKEN: Final[str] = "proxy:tool-stage"
NONE_TOKEN: Final[str] = "none"
ECONOMIC_CASCADES_TOKEN_HEX_LEN: Final[int] = 16


class CascadeDisruptionKind(StrEnum):
    """Five measured objective disruption classes."""

    RESOURCE_LOSS = "resource_loss"
    ROUTE_CLOSURE = "route_closure"
    INFRASTRUCTURE_DESTRUCTION = "infrastructure_destruction"
    POPULATION_LOSS = "population_loss"
    TOOL_SHORTAGE = "tool_shortage"


class CascadeDependencyKind(StrEnum):
    """Five closed observable dependency edge kinds."""

    RESOURCE_INPUT = "resource_input"
    ITEM_INPUT = "item_input"
    TOOL_DEPENDENCY = "tool_dependency"
    INFRASTRUCTURE_DEPENDENCY = "infrastructure_dependency"
    TRANSPORT_DEPENDENCY = "transport_dependency"


class CascadeChainState(StrEnum):
    """Closed analytical link state; never a cause or severity claim."""

    LINKED = "linked"
    UNLINKED = "unlinked"
    UNRESOLVED = "unresolved"
    UNAVAILABLE = "unavailable"


class CascadeCoverage(StrEnum):
    """Coverage of one bounded evidence or analytical family."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"


class CascadeAvailability(StrEnum):
    """Closed availability of one propagation family."""

    AVAILABLE = "available"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    UNAVAILABLE = "unavailable"


class CascadeLayer(StrEnum):
    """Strictly separated objective, dependency, and analytical layers."""

    OBJECTIVE_DISRUPTION = "objective_disruption"
    DEPENDENCY_STRUCTURE = "dependency_structure"
    ANALYTICAL_CHAIN = "analytical_chain"


CASCADE_LAYER = CascadeLayer

CASCADE_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "class",
        "caste",
        "stratum",
        "elite",
        "underclass",
        "severity",
        "criticality",
        "priority",
        "impact_score",
        "cascade_score",
        "risk_score",
        "blame",
        "fault",
        "root_cause",
        "culprit",
        "economic_damage",
        "loss_value",
        "price",
        "money",
        "status_label",
    }
)

ECONOMIC_CASCADES_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "economic_cascades_invalid_policy",
        "economic_cascades_invalid_cap",
        "economic_cascades_invalid_chain",
        "economic_cascades_invalid_event_order",
        "economic_cascades_layer_violation",
        "economic_cascades_unstable_token",
        "economic_cascades_forbidden_key",
        "economic_cascades_nonfinite_value",
        "economic_cascades_invalid_recipe_spec",
    }
)

_ANALYTICAL_TOKEN_PREFIXES: Final[tuple[str, ...]] = (CHAIN_TOKEN_PREFIX,)
_OBJECTIVE_ROW_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {"chain_token", "state", "linked_chain_count"}
)
_ANALYTICAL_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {"owner_token", "actor_token", "body_token", "agent_token"}
)


class EconomicCascadesError(ValueError):
    """Fail-closed analysis error; ``args[0]`` is a stable reason code."""

    @property
    def reason_code(self) -> str:
        if not self.args:
            return "economic_cascades_invalid_chain"
        return str(self.args[0])


def _token_part(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise EconomicCascadesError("economic_cascades_unstable_token")
    if len(value) > 128 or value != value.strip():
        raise EconomicCascadesError("economic_cascades_unstable_token")
    if any(ord(char) < 32 for char in value):
        raise EconomicCascadesError("economic_cascades_unstable_token")
    return value


def _int_part(name: str, value: object, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or type(value) is not int or value < minimum:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return value


def mint_chain_token(
    *,
    disruption_kind: CascadeDisruptionKind | str,
    upstream_token: str,
    downstream_recipe_id: str,
    depth: int,
    lag_windows: int,
    window_index: int,
    evidence_tokens: Sequence[str] = (),
) -> str:
    """Mint the stable content-addressed ``casc-`` chain token."""

    if type(disruption_kind) is CascadeDisruptionKind:
        kind = disruption_kind.value
    elif type(disruption_kind) is str and disruption_kind:
        kind = disruption_kind
    else:
        raise EconomicCascadesError("economic_cascades_unstable_token")
    upstream = _token_part("upstream_token", upstream_token)
    downstream = _token_part("downstream_recipe_id", downstream_recipe_id)
    depth_value = _int_part("depth", depth, minimum=1)
    lag_value = _int_part("lag_windows", lag_windows)
    window_value = _int_part("window_index", window_index)
    if isinstance(evidence_tokens, (str, bytes)) or not isinstance(
        evidence_tokens, Sequence
    ):
        raise EconomicCascadesError("economic_cascades_unstable_token")
    evidence = tuple(
        sorted(_token_part("evidence_token", token) for token in evidence_tokens)
    )
    parts = (
        kind,
        upstream,
        downstream,
        str(depth_value),
        str(lag_value),
        str(window_value),
        *evidence,
    )
    material = "\x1f".join(f"{len(part)}:{part}" for part in parts)
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{CHAIN_TOKEN_PREFIX}{digest[:ECONOMIC_CASCADES_TOKEN_HEX_LEN]}"


def _fields(row: object) -> tuple[str, ...]:
    names = getattr(type(row), "__dataclass_fields__", None)
    if names is None:
        raise EconomicCascadesError("economic_cascades_layer_violation")
    return tuple(names)


def _string_values(row: object) -> tuple[str, ...]:
    values: list[str] = []
    for name in _fields(row):
        value = getattr(row, name, None)
        if type(value) is str:
            values.append(value)
        elif isinstance(value, tuple):
            values.extend(item for item in value if type(item) is str)
    return tuple(values)


def _reject_forbidden(row: object) -> None:
    names = set(_fields(row))
    if names & CASCADE_FORBIDDEN_KEYS:
        _LOG.error("economic_cascades_forbidden_key")
        raise EconomicCascadesError("economic_cascades_forbidden_key")


def assert_economic_cascade_layer_separation(
    *,
    objective_rows: Sequence[object] = (),
    dependency_rows: Sequence[object] = (),
    analytical_rows: Sequence[object] = (),
) -> None:
    """Reject any leak between objective, dependency, and analytical layers."""

    objective_tokens: set[str] = set()
    analytical_tokens: set[str] = set()

    for row in objective_rows:
        _reject_forbidden(row)
        names = set(_fields(row))
        if names & _OBJECTIVE_ROW_FORBIDDEN_FIELDS:
            _LOG.error("economic_cascades_layer_violation")
            raise EconomicCascadesError("economic_cascades_layer_violation")
        for name in ("subject_token", "evidence_event_token"):
            value = getattr(row, name, None)
            if type(value) is str and value:
                objective_tokens.add(value)

    for row in dependency_rows:
        _reject_forbidden(row)
        names = set(_fields(row))
        if names & _OBJECTIVE_ROW_FORBIDDEN_FIELDS:
            _LOG.error("economic_cascades_layer_violation")
            raise EconomicCascadesError("economic_cascades_layer_violation")

    for row in analytical_rows:
        _reject_forbidden(row)
        names = set(_fields(row))
        if names & _ANALYTICAL_FORBIDDEN_FIELDS:
            _LOG.error("economic_cascades_layer_violation")
            raise EconomicCascadesError("economic_cascades_layer_violation")
        for value in _string_values(row):
            if value.startswith(_ANALYTICAL_TOKEN_PREFIXES):
                analytical_tokens.add(value)

    if analytical_tokens & objective_tokens:
        _LOG.error("economic_cascades_layer_violation")
        raise EconomicCascadesError("economic_cascades_layer_violation")
