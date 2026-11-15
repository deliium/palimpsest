"""Frozen token-only rows for social-mobility evidence and analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.social_mobility_contract import (
    SOCIAL_MOBILITY_FORBIDDEN_KEYS,
    SocialMobilityAvailability,
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityError,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    SocialMobilityPersistence,
    assert_social_mobility_layer_separation,
    social_mobility_measures_for,
)
from world.identifiers import require_stable_id

__all__ = [
    "SocialMobilityCoverageRow",
    "SocialMobilityDomainRow",
    "SocialMobilityGenealogyRow",
    "SocialMobilityGenerationRow",
    "SocialMobilityLagRow",
    "SocialMobilityLayerBundle",
    "SocialMobilityLineageEntry",
    "SocialMobilityOutcomeRow",
    "SocialMobilityPairRow",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.social_mobility.rows")

_OWNER_LAYER_DOMAINS: Final[frozenset[SocialMobilityDomain]] = frozenset(
    {
        SocialMobilityDomain.SKILLS,
        SocialMobilityDomain.ORGANIZATION_ROLES,
    }
)


def _forbid_keys(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & SOCIAL_MOBILITY_FORBIDDEN_KEYS:
        raise SocialMobilityError("social_mobility_forbidden_key")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise SocialMobilityError("social_mobility_row_invalid")
    return value


def _bounded(value: object, minimum: int, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or type(value) is not int
        or not minimum <= value <= maximum
    ):
        raise SocialMobilityError("social_mobility_row_invalid")
    return value


def _milli(value: object) -> int:
    return _bounded(value, 0, 1_000)


def _signed_milli(value: object) -> int:
    return _bounded(value, -1_000, 1_000)


def _boolean(value: object) -> bool:
    if type(value) is not bool:
        raise SocialMobilityError("social_mobility_row_invalid")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise SocialMobilityError("social_mobility_row_invalid")
    try:
        return require_stable_id("token", value)
    except (TypeError, ValueError) as error:
        raise SocialMobilityError("social_mobility_row_invalid") from error


def _owner_token(value: object) -> str:
    token = _token(value)
    if not token.startswith("smo-"):
        raise SocialMobilityError("social_mobility_row_invalid")
    return token


def _lineage_token(value: object) -> str:
    token = _token(value)
    if not token.startswith("sml-"):
        raise SocialMobilityError("social_mobility_row_invalid")
    return token


def _enum[T](value: object, enum_type: type[T]) -> T:
    if type(value) is not enum_type:
        raise SocialMobilityError("social_mobility_row_invalid")
    return value


@dataclass(frozen=True, slots=True)
class SocialMobilityOutcomeRow:
    """One observed outcome quantity for one owner and window."""

    owner_token: str
    generation_index: int
    tick: int
    window_index: int
    domain: SocialMobilityDomain
    measure: SocialMobilityMeasure
    quantity: int
    layer: SocialMobilityLayer

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _owner_token(self.owner_token))
        for name in ("generation_index", "tick", "window_index", "quantity"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        domain = _enum(self.domain, SocialMobilityDomain)
        measure = _enum(self.measure, SocialMobilityMeasure)
        if social_mobility_measures_for(domain) != (measure,):
            raise SocialMobilityError("social_mobility_row_invalid")
        layer = _enum(self.layer, SocialMobilityLayer)
        expected = (
            SocialMobilityLayer.OWNER_OUTCOME
            if domain in _OWNER_LAYER_DOMAINS
            else SocialMobilityLayer.OBJECTIVE_OUTCOME
        )
        if layer is not expected:
            raise SocialMobilityError("social_mobility_row_invalid")

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (self.layer,)


@dataclass(frozen=True, slots=True)
class SocialMobilityGenealogyRow:
    """One committed parent→child edge in token space."""

    parent_token: str
    child_token: str
    parent_generation: int
    child_generation: int
    established_tick: int
    window_index: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "parent_token", _owner_token(self.parent_token))
        object.__setattr__(self, "child_token", _owner_token(self.child_token))
        if self.parent_token == self.child_token:
            raise SocialMobilityError("social_mobility_row_invalid")
        for name in (
            "parent_generation",
            "child_generation",
            "established_tick",
            "window_index",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityLineageEntry:
    """One depth-bounded ancestor chain in token space."""

    lineage_token: str
    ancestor_token: str
    descendant_token: str
    generation_lag: int
    ancestor_generation: int
    descendant_generation: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "lineage_token", _lineage_token(self.lineage_token))
        object.__setattr__(self, "ancestor_token", _owner_token(self.ancestor_token))
        object.__setattr__(
            self, "descendant_token", _owner_token(self.descendant_token)
        )
        if self.ancestor_token == self.descendant_token:
            raise SocialMobilityError("social_mobility_row_invalid")
        lag = _bounded(self.generation_lag, 1, 32)
        if self.descendant_generation - self.ancestor_generation != lag:
            raise SocialMobilityError("social_mobility_row_invalid")
        for name in ("ancestor_generation", "descendant_generation"):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityPairRow:
    """One ancestor/descendant quantity pair for one window and domain."""

    window_index: int
    ancestor_token: str
    descendant_token: str
    generation_lag: int
    domain: SocialMobilityDomain
    ancestor_quantity: int
    descendant_quantity: int
    ancestor_bin: int
    descendant_bin: int
    ancestor_window_index: int
    descendant_window_index: int
    resolved: bool

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "window_index", _count(self.window_index))
        object.__setattr__(self, "ancestor_token", _owner_token(self.ancestor_token))
        object.__setattr__(
            self, "descendant_token", _owner_token(self.descendant_token)
        )
        if self.ancestor_token == self.descendant_token:
            raise SocialMobilityError("social_mobility_row_invalid")
        _enum(self.domain, SocialMobilityDomain)
        for name in (
            "generation_lag",
            "ancestor_quantity",
            "descendant_quantity",
            "ancestor_window_index",
            "descendant_window_index",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.generation_lag < 1:
            raise SocialMobilityError("social_mobility_row_invalid")
        object.__setattr__(self, "resolved", _boolean(self.resolved))
        if self.resolved:
            object.__setattr__(self, "ancestor_bin", _bounded(self.ancestor_bin, 0, 9))
            object.__setattr__(
                self, "descendant_bin", _bounded(self.descendant_bin, 0, 9)
            )
        else:
            if self.ancestor_bin != -1 or self.descendant_bin != -1:
                raise SocialMobilityError("social_mobility_row_invalid")
            if self.ancestor_quantity or self.descendant_quantity:
                raise SocialMobilityError("social_mobility_row_invalid")

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityDomainRow:
    """One domain/window statistical summary; never a composite index."""

    window_index: int
    window_tick: int
    domain: SocialMobilityDomain
    measure: SocialMobilityMeasure
    pair_count: int
    resolved_pair_count: int
    rank_correlation_milli: int
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    mean_absolute_rank_change_milli: int
    persistence_direction: SocialMobilityPersistence
    coverage: SocialMobilityCoverage
    availability: SocialMobilityAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "pair_count",
            "resolved_pair_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.resolved_pair_count > self.pair_count:
            raise SocialMobilityError("social_mobility_row_invalid")
        domain = _enum(self.domain, SocialMobilityDomain)
        measure = _enum(self.measure, SocialMobilityMeasure)
        if social_mobility_measures_for(domain) != (measure,):
            raise SocialMobilityError("social_mobility_row_invalid")
        object.__setattr__(
            self, "rank_correlation_milli", _signed_milli(self.rank_correlation_milli)
        )
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
            "mean_absolute_rank_change_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        _enum(self.persistence_direction, SocialMobilityPersistence)
        _enum(self.coverage, SocialMobilityCoverage)
        _enum(self.availability, SocialMobilityAvailability)

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityGenerationRow:
    """One descendant-generation summary for one window."""

    window_index: int
    window_tick: int
    generation_index: int
    owner_count: int
    pair_count: int
    comparable: bool
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    coverage: SocialMobilityCoverage
    availability: SocialMobilityAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "generation_index",
            "owner_count",
            "pair_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "comparable", _boolean(self.comparable))
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        _enum(self.coverage, SocialMobilityCoverage)
        _enum(self.availability, SocialMobilityAvailability)

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityCoverageRow:
    """One bounded coverage summary for one window."""

    window_index: int
    window_tick: int
    generation_count: int
    owner_count: int
    genealogy_edge_count: int
    pair_count: int
    resolved_pair_count: int
    unresolved_pair_count: int
    domain_available_count: int
    truncated: bool
    coverage: SocialMobilityCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "window_index",
            "window_tick",
            "generation_count",
            "owner_count",
            "genealogy_edge_count",
            "pair_count",
            "resolved_pair_count",
            "unresolved_pair_count",
            "domain_available_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.resolved_pair_count + self.unresolved_pair_count != self.pair_count:
            raise SocialMobilityError("social_mobility_row_invalid")
        if self.resolved_pair_count > self.pair_count:
            raise SocialMobilityError("social_mobility_row_invalid")
        object.__setattr__(self, "truncated", _boolean(self.truncated))
        _enum(self.coverage, SocialMobilityCoverage)

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityLagRow:
    """One generation-distance summary for one window; no ranking."""

    window_index: int
    window_tick: int
    generation_lag: int
    pair_count: int
    comparable: bool
    same_bin_share_milli: int
    upward_share_milli: int
    downward_share_milli: int
    coverage: SocialMobilityCoverage
    availability: SocialMobilityAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in ("window_index", "window_tick", "generation_lag", "pair_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.generation_lag < 1:
            raise SocialMobilityError("social_mobility_row_invalid")
        object.__setattr__(self, "comparable", _boolean(self.comparable))
        for name in (
            "same_bin_share_milli",
            "upward_share_milli",
            "downward_share_milli",
        ):
            object.__setattr__(self, name, _milli(getattr(self, name)))
        _enum(self.coverage, SocialMobilityCoverage)
        _enum(self.availability, SocialMobilityAvailability)

    @property
    def source_layers(self) -> tuple[SocialMobilityLayer, ...]:
        return (SocialMobilityLayer.ANALYTICAL_MOBILITY,)


@dataclass(frozen=True, slots=True)
class SocialMobilityLayerBundle:
    """Objective, owner, and analytical rows kept in separate groups."""

    objective_rows: tuple[SocialMobilityOutcomeRow, ...]
    owner_rows: tuple[SocialMobilityOutcomeRow, ...]
    pair_rows: tuple[SocialMobilityPairRow, ...]
    domain_rows: tuple[SocialMobilityDomainRow, ...]
    generation_rows: tuple[SocialMobilityGenerationRow, ...]
    coverage_row: SocialMobilityCoverageRow | None

    def __post_init__(self) -> None:
        for name in (
            "objective_rows",
            "owner_rows",
            "pair_rows",
            "domain_rows",
            "generation_rows",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise SocialMobilityError("social_mobility_row_invalid")
        if self.coverage_row is not None and type(self.coverage_row) is not (
            SocialMobilityCoverageRow
        ):
            raise SocialMobilityError("social_mobility_row_invalid")
        groups = [
            self.objective_rows,
            self.owner_rows,
            self.pair_rows,
            self.domain_rows,
            self.generation_rows,
        ]
        if self.coverage_row is not None:
            groups.append((self.coverage_row,))
        assert_social_mobility_layer_separation(*groups)
