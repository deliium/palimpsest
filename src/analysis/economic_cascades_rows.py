"""Frozen token-only rows for economic-cascade evidence and analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_contract import (
    CASCADE_FORBIDDEN_KEYS,
    CHAIN_TOKEN_PREFIX,
    CascadeAvailability,
    CascadeChainState,
    CascadeCoverage,
    CascadeDependencyKind,
    CascadeDisruptionKind,
    CascadeLayer,
    EconomicCascadesError,
)
from world.identifiers import require_stable_id

__all__ = [
    "CascadeChainRow",
    "CascadeCoverageRow",
    "CascadeDependencyEdgeRow",
    "CascadeDisruptionRow",
    "CascadeEpisodeRow",
    "CascadePropagationRow",
    "CascadeStageRow",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.economic_cascades.rows")

_ACTIONS: Final[frozenset[str]] = frozenset(
    {"harvest", "craft", "build", "repair", "store"}
)
_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "food",
        "water",
        "material",
        "medical",
        "generic",
        "tool",
        "structure",
        "storage",
    }
)


def _forbid_keys(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & CASCADE_FORBIDDEN_KEYS:
        raise EconomicCascadesError("economic_cascades_forbidden_key")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return value


def _share(value: object) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or value < 0
        or value > 1_000
    ):
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise EconomicCascadesError("economic_cascades_unstable_token")
    try:
        return require_stable_id("token", value)
    except (TypeError, ValueError) as error:
        raise EconomicCascadesError(
            "economic_cascades_unstable_token"
        ) from error


def _text(value: object) -> str:
    if type(value) is not str or not value:
        raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
    return value


def _enum(value: object, enum_type: type) -> object:
    if type(value) is not enum_type:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return value


def _flag(value: object) -> bool:
    if type(value) is not bool:
        raise EconomicCascadesError("economic_cascades_invalid_chain")
    return value


@dataclass(frozen=True, slots=True)
class CascadeDisruptionRow:
    """One committed objective disruption observation."""

    window_index: int
    window_tick: int
    sequence: int
    kind: CascadeDisruptionKind
    subject_token: str
    magnitude_count: int
    evidence_event_token: str
    coverage: CascadeCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick", "sequence"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "kind", _enum(self.kind, CascadeDisruptionKind))
        object.__setattr__(self, "subject_token", _token(self.subject_token))
        object.__setattr__(
            self, "magnitude_count", _count(self.magnitude_count)
        )
        object.__setattr__(
            self, "evidence_event_token", _token(self.evidence_event_token)
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.OBJECTIVE_DISRUPTION,)


@dataclass(frozen=True, slots=True)
class CascadeEpisodeRow:
    """Disruption rows collapsed per window and kind."""

    window_index: int
    window_tick: int
    kind: CascadeDisruptionKind
    disruption_count: int
    magnitude_total: int
    subject_count: int
    first_sequence: int
    last_sequence: int
    coverage: CascadeCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "disruption_count",
            "magnitude_total",
            "subject_count",
            "first_sequence",
            "last_sequence",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "kind", _enum(self.kind, CascadeDisruptionKind))
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))
        if self.first_sequence > self.last_sequence:
            raise EconomicCascadesError("economic_cascades_invalid_chain")

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.ANALYTICAL_CHAIN,)


@dataclass(frozen=True, slots=True)
class CascadeStageRow:
    """One observed production stage with demand and completions."""

    window_index: int
    window_tick: int
    recipe_id: str
    action: str
    output_name: str
    output_kind: str
    location_token: str
    demand_count: int
    attempt_count: int
    completion_count: int
    tool_dependent: bool
    has_infrastructure: bool
    coverage: CascadeCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "recipe_id", _token(self.recipe_id))
        action = _text(self.action)
        if action not in _ACTIONS:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "output_name", _text(self.output_name))
        output_kind = _text(self.output_kind)
        if output_kind not in _OUTPUT_KINDS:
            raise EconomicCascadesError("economic_cascades_invalid_recipe_spec")
        object.__setattr__(self, "output_kind", output_kind)
        object.__setattr__(self, "location_token", _token(self.location_token))
        for name in ("demand_count", "attempt_count", "completion_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "tool_dependent", _flag(self.tool_dependent))
        object.__setattr__(
            self, "has_infrastructure", _flag(self.has_infrastructure)
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))
        if (
            self.completion_count > self.demand_count
            or self.attempt_count > self.demand_count
        ):
            raise EconomicCascadesError("economic_cascades_invalid_chain")

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.OBJECTIVE_DISRUPTION,)


@dataclass(frozen=True, slots=True)
class CascadeDependencyEdgeRow:
    """One observable production dependency edge."""

    window_index: int
    window_tick: int
    upstream_token: str
    downstream_recipe_id: str
    kind: CascadeDependencyKind
    depth: int
    evidence_count: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "upstream_token", _token(self.upstream_token))
        object.__setattr__(
            self, "downstream_recipe_id", _token(self.downstream_recipe_id)
        )
        object.__setattr__(
            self, "kind", _enum(self.kind, CascadeDependencyKind)
        )
        depth = _count(self.depth)
        if depth < 1:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        object.__setattr__(self, "depth", depth)
        object.__setattr__(self, "evidence_count", _count(self.evidence_count))

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.DEPENDENCY_STRUCTURE,)


@dataclass(frozen=True, slots=True)
class CascadeChainRow:
    """One dependency-conditioned analytical chain link."""

    chain_token: str
    window_index: int
    window_tick: int
    disruption_kind: CascadeDisruptionKind
    upstream_token: str
    downstream_recipe_id: str
    depth: int
    lag_windows: int
    shortfall_share_milli: int
    state: CascadeChainState
    coverage: CascadeCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        token = _token(self.chain_token)
        if not token.startswith(CHAIN_TOKEN_PREFIX):
            raise EconomicCascadesError("economic_cascades_unstable_token")
        object.__setattr__(self, "chain_token", token)
        for name in ("window_index", "window_tick", "lag_windows"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self,
            "disruption_kind",
            _enum(self.disruption_kind, CascadeDisruptionKind),
        )
        object.__setattr__(self, "upstream_token", _token(self.upstream_token))
        object.__setattr__(
            self, "downstream_recipe_id", _token(self.downstream_recipe_id)
        )
        depth = _count(self.depth)
        if depth < 1:
            raise EconomicCascadesError("economic_cascades_invalid_chain")
        object.__setattr__(self, "depth", depth)
        object.__setattr__(
            self,
            "shortfall_share_milli",
            _share(self.shortfall_share_milli),
        )
        object.__setattr__(self, "state", _enum(self.state, CascadeChainState))
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.ANALYTICAL_CHAIN,)


@dataclass(frozen=True, slots=True)
class CascadePropagationRow:
    """Per-kind descriptive chain counts and depth/lag means."""

    window_index: int
    window_tick: int
    disruption_kind: CascadeDisruptionKind
    chain_count: int
    linked_chain_count: int
    unlinked_chain_count: int
    unresolved_chain_count: int
    mean_depth_milli: int
    mean_lag_milli: int
    downstream_stage_count: int
    coverage: CascadeCoverage
    availability: CascadeAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "chain_count",
            "linked_chain_count",
            "unlinked_chain_count",
            "unresolved_chain_count",
            "mean_depth_milli",
            "mean_lag_milli",
            "downstream_stage_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(
            self,
            "disruption_kind",
            _enum(self.disruption_kind, CascadeDisruptionKind),
        )
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, CascadeAvailability),
        )
        classified = (
            self.linked_chain_count
            + self.unlinked_chain_count
            + self.unresolved_chain_count
        )
        if classified != self.chain_count:
            raise EconomicCascadesError("economic_cascades_invalid_chain")

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.ANALYTICAL_CHAIN,)


@dataclass(frozen=True, slots=True)
class CascadeCoverageRow:
    """Bounded evidence coverage for one window."""

    window_index: int
    window_tick: int
    window_count: int
    event_count: int
    disruption_count: int
    stage_count: int
    dependency_edge_count: int
    labor_join_count: int
    chain_count: int
    linked_chain_count: int
    truncated: bool
    coverage: CascadeCoverage
    availability: CascadeAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "window_count",
            "event_count",
            "disruption_count",
            "stage_count",
            "dependency_edge_count",
            "labor_join_count",
            "chain_count",
            "linked_chain_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "truncated", _flag(self.truncated))
        object.__setattr__(self, "coverage", _enum(self.coverage, CascadeCoverage))
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, CascadeAvailability),
        )

    @property
    def source_layers(self) -> tuple[CascadeLayer, ...]:
        return (CascadeLayer.ANALYTICAL_CHAIN,)
