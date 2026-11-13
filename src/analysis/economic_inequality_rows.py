"""Frozen token-only rows for economic-inequality evidence and analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.economic_inequality_contract import (
    ECONOMIC_INEQUALITY_FORBIDDEN_KEYS,
    EconomicInequalityAvailability,
    EconomicInequalityCoverage,
    EconomicInequalityDimension,
    EconomicInequalityError,
    EconomicInequalityLayer,
    EconomicInequalityMeasure,
    EconomicInequalityTrend,
    assert_economic_inequality_layer_separation,
)
from world.identifiers import require_stable_id

__all__ = [
    "EconomicAccessRow",
    "EconomicCohortMembership",
    "EconomicCohortRow",
    "EconomicControlClaimRow",
    "EconomicCreditClaimRow",
    "EconomicDimensionWindowRow",
    "EconomicLayerBundle",
    "EconomicPossessionRow",
    "EconomicSocietyMembership",
    "EconomicSocietyRow",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.rows"
)


def _forbid_keys(cls: type[object]) -> None:
    names = set(getattr(cls, "__dataclass_fields__", {}))
    if names & ECONOMIC_INEQUALITY_FORBIDDEN_KEYS:
        raise EconomicInequalityError("economic_inequality_forbidden_key")


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise EconomicInequalityError("economic_inequality_invalid_row")
    return value


def _optional_count(value: object) -> int | None:
    if value is None:
        return None
    return _count(value)


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise EconomicInequalityError("economic_inequality_invalid_row")
    try:
        return require_stable_id("token", value)
    except (TypeError, ValueError) as error:
        raise EconomicInequalityError(
            "economic_inequality_invalid_row"
        ) from error


def _enum(value: object, enum_type: type) -> object:
    if type(value) is not enum_type:
        raise EconomicInequalityError("economic_inequality_invalid_row")
    return value


def _optional_bool(value: object) -> bool:
    if type(value) is not bool:
        raise EconomicInequalityError("economic_inequality_invalid_row")
    return value


def _shares(value: object) -> tuple[int, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise EconomicInequalityError("economic_inequality_invalid_row")
    normalized = tuple(_count(share) for share in value)
    if len(normalized) != 5:
        raise EconomicInequalityError("economic_inequality_invalid_row")
    if any(share > 1_000 for share in normalized):
        raise EconomicInequalityError("economic_inequality_invalid_row")
    return normalized


@dataclass(frozen=True, slots=True)
class EconomicPossessionRow:
    """One committed objective custody observation for one owner and tick."""

    owner_token: str
    tick: int
    window_index: int
    observed_item_count: int
    observed_tool_count: int
    unknown_kind_count: int = 0

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        for name in (
            "tick",
            "window_index",
            "observed_item_count",
            "observed_tool_count",
            "unknown_kind_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.observed_tool_count > self.observed_item_count:
            raise EconomicInequalityError("economic_inequality_invalid_row")

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.OBJECTIVE_POSSESSION,)


@dataclass(frozen=True, slots=True)
class EconomicAccessRow:
    """One committed physical-presence access observation for one owner."""

    owner_token: str
    tick: int
    window_index: int
    accessible_infrastructure_count: int
    accessible_storage_count: int
    location_known: bool

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        for name in (
            "tick",
            "window_index",
            "accessible_infrastructure_count",
            "accessible_storage_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "location_known", _optional_bool(self.location_known))

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.OBJECTIVE_ACCESS,)


@dataclass(frozen=True, slots=True)
class EconomicCreditClaimRow:
    """One committed ``crd_v1`` credit claim aggregate, token-only."""

    owner_token: str
    tick: int
    window_index: int
    claimed_principal_quantity: int
    observed_repayment_quantity: int
    claimed_relationship_count: int
    contested_count: int = 0

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        for name in (
            "tick",
            "window_index",
            "claimed_principal_quantity",
            "observed_repayment_quantity",
            "claimed_relationship_count",
            "contested_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.OWNER_CLAIM,)


@dataclass(frozen=True, slots=True)
class EconomicControlClaimRow:
    """One detached organization-operation control claim aggregate."""

    owner_token: str
    tick: int
    window_index: int
    claimed_resource_control_count: int
    claimed_storage_control_count: int
    contested_count: int = 0

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        for name in (
            "tick",
            "window_index",
            "claimed_resource_control_count",
            "claimed_storage_control_count",
            "contested_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.OWNER_CLAIM,)


@dataclass(frozen=True, slots=True)
class EconomicCohortMembership:
    """One owner's generation cohort membership."""

    owner_token: str
    generation_index: int
    first_tick: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        for name in ("generation_index", "first_tick"):
            object.__setattr__(self, name, _count(getattr(self, name)))

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)


@dataclass(frozen=True, slots=True)
class EconomicSocietyMembership:
    """One owner's membership in one detached ``msoc-`` candidate."""

    owner_token: str
    society_token: str
    window_indexes: tuple[int, ...]

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token(self.owner_token))
        object.__setattr__(self, "society_token", _token(self.society_token))
        if (
            isinstance(self.window_indexes, (str, bytes))
            or not isinstance(self.window_indexes, tuple)
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        normalized = tuple(_count(index) for index in self.window_indexes)
        if not normalized or len(set(normalized)) != len(normalized):
            raise EconomicInequalityError("economic_inequality_invalid_row")
        object.__setattr__(self, "window_indexes", normalized)

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)


@dataclass(frozen=True, slots=True)
class EconomicLayerBundle:
    """Bounded evidence grouped by its strict source layer."""

    possession_rows: tuple[EconomicPossessionRow, ...] = ()
    access_rows: tuple[EconomicAccessRow, ...] = ()
    credit_claim_rows: tuple[EconomicCreditClaimRow, ...] = ()
    control_claim_rows: tuple[EconomicControlClaimRow, ...] = ()

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        for name in (
            "possession_rows",
            "access_rows",
            "credit_claim_rows",
            "control_claim_rows",
        ):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicInequalityError("economic_inequality_invalid_row")
        assert_economic_inequality_layer_separation(
            *self.possession_rows,
            *self.access_rows,
            *self.credit_claim_rows,
            *self.control_claim_rows,
        )

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        layers: list[EconomicInequalityLayer] = []
        for row in (
            *self.possession_rows,
            *self.access_rows,
            *self.credit_claim_rows,
            *self.control_claim_rows,
        ):
            layers.extend(row.source_layers)  # type: ignore[attr-defined]
        return tuple(dict.fromkeys(layers))


@dataclass(frozen=True, slots=True)
class EconomicDimensionWindowRow:
    """One descriptive per-window, per-measure distribution and indices."""

    dimension: EconomicInequalityDimension
    measure: EconomicInequalityMeasure
    window_index: int
    window_tick: int
    owner_count: int
    observed_owner_count: int
    minimum: int | None
    p25: int | None
    median: int | None
    p75: int | None
    maximum: int | None
    iqr: int | None
    dispersion: int | None
    bin_shares_milli: tuple[int, ...]
    gini_milli: int | None
    theil_t_milli: int | None
    atkinson_eps_1_milli: int | None
    top_share_milli: int | None
    availability: EconomicInequalityAvailability
    coverage: EconomicInequalityCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "dimension",
            _enum(self.dimension, EconomicInequalityDimension),
        )
        object.__setattr__(
            self, "measure", _enum(self.measure, EconomicInequalityMeasure)
        )
        for name in (
            "window_index",
            "window_tick",
            "owner_count",
            "observed_owner_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        for name in (
            "minimum",
            "p25",
            "median",
            "p75",
            "maximum",
            "iqr",
            "dispersion",
            "gini_milli",
            "theil_t_milli",
            "atkinson_eps_1_milli",
            "top_share_milli",
        ):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(
            self, "bin_shares_milli", _shares(self.bin_shares_milli)
        )
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, EconomicInequalityAvailability),
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, EconomicInequalityCoverage)
        )
        if (
            self.availability is EconomicInequalityAvailability.AVAILABLE
            and self.observed_owner_count < 1
        ):
            raise EconomicInequalityError("economic_inequality_invalid_row")

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)


@dataclass(frozen=True, slots=True)
class EconomicCohortRow:
    """One generation-cohort comparison; never a ranking."""

    cohort_token: str
    generation_index: int
    window_index: int
    owner_count: int
    comparable: bool
    gini_milli: int | None
    median_milli: int | None
    iqr_milli: int | None
    trend: EconomicInequalityTrend
    availability: EconomicInequalityAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "cohort_token", _token(self.cohort_token))
        for name in ("generation_index", "window_index", "owner_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "comparable", _optional_bool(self.comparable))
        for name in ("gini_milli", "median_milli", "iqr_milli"):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(self, "trend", _enum(self.trend, EconomicInequalityTrend))
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, EconomicInequalityAvailability),
        )

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)


@dataclass(frozen=True, slots=True)
class EconomicSocietyRow:
    """One detached society comparison; never a ranking."""

    society_token: str
    window_index: int
    owner_count: int
    comparable: bool
    gini_milli: int | None
    median_milli: int | None
    iqr_milli: int | None
    trend: EconomicInequalityTrend
    availability: EconomicInequalityAvailability

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "society_token", _token(self.society_token))
        for name in ("window_index", "owner_count"):
            object.__setattr__(self, name, _count(getattr(self, name)))
        object.__setattr__(self, "comparable", _optional_bool(self.comparable))
        for name in ("gini_milli", "median_milli", "iqr_milli"):
            object.__setattr__(self, name, _optional_count(getattr(self, name)))
        object.__setattr__(self, "trend", _enum(self.trend, EconomicInequalityTrend))
        object.__setattr__(
            self,
            "availability",
            _enum(self.availability, EconomicInequalityAvailability),
        )

    @property
    def source_layers(self) -> tuple[EconomicInequalityLayer, ...]:
        return (EconomicInequalityLayer.ANALYTICAL_COMPARISON,)
