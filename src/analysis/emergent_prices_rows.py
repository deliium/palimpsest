"""Frozen detached rows for emergent-price analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final, cast

from analysis.emergent_prices_contract import (
    PRICE_EXPECTATION_LEVELS,
    PRICE_FORBIDDEN_KEYS,
    EmergentPriceAnalysisError,
    PriceAlignment,
    PriceCoverage,
    PriceDistributionStatus,
    PricePairing,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceRelation,
    PriceSampleSource,
    PriceUnitSource,
)
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "ExchangePriceEvidenceRow",
    "OwnerPriceExpectationRow",
    "OwnerPriceQuoteRow",
    "PriceDistributionRow",
    "PriceEvidenceHarvest",
    "PriceMarketMembershipInput",
    "PriceMarketRow",
    "PriceQuoteEvidenceRow",
    "PriceRelationRow",
    "PriceUnitRow",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.emergent_prices.rows")

MAX_RATIO_MILLI: Final[int] = 64_000


def _forbid_keys(cls: type[object]) -> None:
    if set(getattr(cls, "__dataclass_fields__", {})) & PRICE_FORBIDDEN_KEYS:
        raise EmergentPriceAnalysisError("price_analysis_forbidden_key")


def _count(name: str, value: object) -> int:
    try:
        return require_exact_nonneg_int(name, value)
    except (TypeError, ValueError) as exc:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row") from exc


def _token(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    try:
        return require_stable_id(name, value)
    except (TypeError, ValueError) as exc:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row") from exc


def _enum(value: object, enum_type: type) -> object:
    if type(value) is not enum_type:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


@dataclass(frozen=True, slots=True)
class ExchangePriceEvidenceRow:
    """One committed exchange with an optional exchange-implied ratio."""

    tick: int
    window_index: int
    venue_token: str
    event_token: str
    event_kind: str
    actor_token: str
    counterparty_token: str
    item_kind: str
    unit_kind: str
    item_count: int
    unit_count: int
    ratio_milli: int | None
    pairing: PricePairing
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "tick", _count("tick", self.tick))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "venue_token", _token("venue_token", self.venue_token)
        )
        object.__setattr__(
            self, "event_token", _token("event_token", self.event_token)
        )
        if self.event_kind not in {"completed", "proposed", "withdrawn"}:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "actor_token", _token("actor_token", self.actor_token)
        )
        object.__setattr__(
            self,
            "counterparty_token",
            _token("counterparty_token", self.counterparty_token),
        )
        object.__setattr__(
            self, "item_kind", _token("item_kind", self.item_kind)
        )
        object.__setattr__(
            self, "unit_kind", _token("unit_kind", self.unit_kind)
        )
        object.__setattr__(
            self, "item_count", _count("item_count", self.item_count)
        )
        object.__setattr__(
            self, "unit_count", _count("unit_count", self.unit_count)
        )
        object.__setattr__(
            self, "pairing", _enum(self.pairing, PricePairing)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )
        if self.ratio_milli is not None:
            ratio = _count("ratio_milli", self.ratio_milli)
            if ratio > MAX_RATIO_MILLI:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if self.pairing is not PricePairing.PAIRED:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if self.pairing is PricePairing.PAIRED and self.ratio_milli is None:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")


@dataclass(frozen=True, slots=True)
class PriceQuoteEvidenceRow:
    """One offer or withdrawal with an optional quoted ratio."""

    tick: int
    window_index: int
    venue_token: str
    event_token: str
    actor_token: str
    counterparty_token: str
    item_kind: str
    unit_kind: str
    direction: PriceQuoteDirection
    ratio_milli: int | None
    pairing: PricePairing
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "tick", _count("tick", self.tick))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        for name in (
            "venue_token",
            "event_token",
            "actor_token",
            "counterparty_token",
            "item_kind",
            "unit_kind",
        ):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "direction", _enum(self.direction, PriceQuoteDirection)
        )
        object.__setattr__(self, "pairing", _enum(self.pairing, PricePairing))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )
        if self.ratio_milli is not None:
            ratio = _count("ratio_milli", self.ratio_milli)
            if ratio > MAX_RATIO_MILLI:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if self.pairing is not PricePairing.PAIRED:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if self.pairing is PricePairing.PAIRED and self.ratio_milli is None:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")


@dataclass(frozen=True, slots=True)
class PriceEvidenceHarvest:
    """Bounded, token-only exchange evidence with explicit coverage."""

    exchanges: tuple[ExchangePriceEvidenceRow, ...]
    quotes: tuple[PriceQuoteEvidenceRow, ...]
    coverage: PriceCoverage
    notices: tuple[str, ...]
    exchange_count: int
    quote_count: int

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )
        for exchange_row in self.exchanges:
            if type(exchange_row) is not ExchangePriceEvidenceRow:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for quote_row in self.quotes:
            if type(quote_row) is not PriceQuoteEvidenceRow:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if self.exchange_count != len(self.exchanges):
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if self.quote_count != len(self.quotes):
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))


def _validated_bins(value: object) -> tuple[int, int, int, int, int]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    values = tuple(value)
    if len(values) != 5:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    for item in values:
        if isinstance(item, bool) or type(item) is not int or not 0 <= item <= 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return cast(tuple[int, int, int, int, int], values)


def _distribution_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("prcd-")
        or len(value) != 5 + 16
    ):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


def _relation_id(value: object) -> str:
    if (
        type(value) is not str
        or not value.startswith("prcr-")
        or len(value) != 5 + 16
    ):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


def _group_token(name: str, value: object, prefix: str) -> str:
    if value == "none":
        return "none"
    if (
        type(value) is not str
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 16
    ):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


@dataclass(frozen=True, slots=True)
class PriceDistributionRow:
    """One analytical ratio distribution over a venue or market."""

    distribution_id: str
    window_index: int
    venue_id: str
    market_token: str
    item_kind: str
    unit_kind: str
    unit_source: PriceUnitSource
    sample_source: PriceSampleSource
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: PriceDistributionStatus
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "distribution_id", _distribution_id(self.distribution_id)
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self,
            "venue_id",
            _group_token("venue_id", self.venue_id, "mkt-ven-"),
        )
        object.__setattr__(
            self,
            "market_token",
            _group_token("market_token", self.market_token, "mktc-"),
        )
        if (self.venue_id == "none") is (self.market_token == "none"):
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in ("item_kind", "unit_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "unit_source", _enum(self.unit_source, PriceUnitSource)
        )
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, PriceSampleSource)
        )
        for name in (
            "sample_count",
            "min_ratio_milli",
            "p25_ratio_milli",
            "median_ratio_milli",
            "p75_ratio_milli",
            "max_ratio_milli",
            "iqr_milli",
            "dispersion_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        bins = _validated_bins(self.bin_shares_milli)
        object.__setattr__(self, "bin_shares_milli", bins)
        object.__setattr__(
            self, "status", _enum(self.status, PriceDistributionStatus)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )
        if self.status is PriceDistributionStatus.AVAILABLE:
            if not (
                self.min_ratio_milli
                <= self.p25_ratio_milli
                <= self.median_ratio_milli
                <= self.p75_ratio_milli
                <= self.max_ratio_milli
            ):
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if sum(bins) != 1_000:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if self.sample_count < 1:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if self.iqr_milli != self.p75_ratio_milli - self.p25_ratio_milli:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")


@dataclass(frozen=True, slots=True)
class PriceMarketRow:
    """One market/window summary over member venue distributions."""

    market_token: str
    window_index: int
    venue_count: int
    distribution_count: int
    sample_count: int
    item_kind_count: int
    unit_count: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "market_token",
            _group_token("market_token", self.market_token, "mktc-"),
        )
        if self.market_token == "none":
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in (
            "window_index",
            "venue_count",
            "distribution_count",
            "sample_count",
            "item_kind_count",
            "unit_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class PriceRelationRow:
    """One pairwise distributional convergence/divergence observation."""

    relation_id: str
    window_index: int
    group_kind: str
    group_a_token: str
    group_b_token: str
    item_kind: str
    unit_kind: str
    unit_source: PriceUnitSource
    sample_source: PriceSampleSource
    overlap_milli: int
    median_gap_milli: int
    relation: PriceRelation
    sample_a: int
    sample_b: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "relation_id", _relation_id(self.relation_id))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        if self.group_kind not in {"venue", "market"}:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in ("group_a_token", "group_b_token"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or not (
                    (
                        value.startswith("mkt-ven-")
                        and len(value) == len("mkt-ven-") + 16
                    )
                    or (
                        value.startswith("mktc-")
                        and len(value) == len("mktc-") + 16
                    )
                )
            ):
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if not self.group_a_token < self.group_b_token:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in ("item_kind", "unit_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "unit_source", _enum(self.unit_source, PriceUnitSource)
        )
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, PriceSampleSource)
        )
        for name in (
            "overlap_milli",
            "median_gap_milli",
            "sample_a",
            "sample_b",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.overlap_milli > 1_000 or self.median_gap_milli > 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "relation", _enum(self.relation, PriceRelation)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


def _level(value: object) -> str:
    if type(value) is not str or value not in PRICE_EXPECTATION_LEVELS:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


def _unit_token(value: object) -> str:
    if value == "none":
        return "none"
    return _token("unit_token", value)


def _prefixed_id(value: object, prefix: str) -> str:
    if (
        type(value) is not str
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 16
    ):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return value


@dataclass(frozen=True, slots=True)
class PriceOwnerExpectationInput:
    """Analysis boundary row for one owner expectation."""

    owner_token: str
    window_index: int
    item_kind: str
    unit_kind: str
    unit_source: PriceUnitSource
    expected_ratio_milli: int
    confidence_milli: int
    level: str
    valuation_reservation: int
    observation_count: int
    quote_count: int
    first_tick: int
    last_tick: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "item_kind", _token("item_kind", self.item_kind))
        object.__setattr__(self, "unit_kind", _unit_token(self.unit_kind))
        object.__setattr__(
            self, "unit_source", _enum(self.unit_source, PriceUnitSource)
        )
        object.__setattr__(
            self,
            "expected_ratio_milli",
            _count("expected_ratio_milli", self.expected_ratio_milli),
        )
        object.__setattr__(
            self, "confidence_milli", _count("confidence_milli", self.confidence_milli)
        )
        if self.confidence_milli > 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(self, "level", _level(self.level))
        for name in (
            "valuation_reservation",
            "observation_count",
            "quote_count",
            "first_tick",
            "last_tick",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.last_tick < self.first_tick:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class PriceOwnerQuoteInput:
    """Analysis boundary row for one owner quote."""

    owner_token: str
    venue_id: str
    window_index: int
    item_kind: str
    unit_kind: str
    direction: PriceQuoteDirection
    ratio_milli: int
    confidence_milli: int
    source: PriceQuoteSource
    source_tick: int
    first_tick: int
    last_tick: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        object.__setattr__(
            self, "venue_id", _group_token("venue_id", self.venue_id, "mkt-ven-")
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "item_kind", _token("item_kind", self.item_kind))
        object.__setattr__(self, "unit_kind", _unit_token(self.unit_kind))
        object.__setattr__(
            self, "direction", _enum(self.direction, PriceQuoteDirection)
        )
        object.__setattr__(
            self, "source", _enum(self.source, PriceQuoteSource)
        )
        for name in (
            "ratio_milli",
            "confidence_milli",
            "source_tick",
            "first_tick",
            "last_tick",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.confidence_milli > 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        if self.last_tick < self.first_tick:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class OwnerPriceExpectationRow:
    """Detached owner expectation joined to an analytical distribution."""

    expectation_id: str
    window_index: int
    owner_token: str
    item_kind: str
    unit_kind: str
    unit_source: PriceUnitSource
    expected_ratio_milli: int
    confidence_milli: int
    level: str
    valuation_reservation: int
    observation_count: int
    quote_count: int
    distribution_source: str
    alignment: PriceAlignment
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self, "expectation_id", _prefixed_id(self.expectation_id, "prce-")
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(self, "owner_token", _token("owner_token", self.owner_token))
        for name in ("item_kind", "unit_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "unit_source", _enum(self.unit_source, PriceUnitSource)
        )
        for name in (
            "expected_ratio_milli",
            "confidence_milli",
            "valuation_reservation",
            "observation_count",
            "quote_count",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        object.__setattr__(self, "level", _level(self.level))
        if self.distribution_source not in {"completed", "quoted", "none"}:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "alignment", _enum(self.alignment, PriceAlignment)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class OwnerPriceQuoteRow:
    """Detached owner quote row with no live counterparty id."""

    quote_id: str
    window_index: int
    venue_id: str
    actor_token: str
    counterparty_token: str
    item_kind: str
    unit_kind: str
    direction: PriceQuoteDirection
    ratio_milli: int
    confidence_milli: int
    source: PriceQuoteSource
    source_tick: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "quote_id", _prefixed_id(self.quote_id, "prcq-"))
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "venue_id", _group_token("venue_id", self.venue_id, "mkt-ven-")
        )
        for name in ("actor_token", "counterparty_token", "item_kind", "unit_kind"):
            object.__setattr__(self, name, _token(name, getattr(self, name)))
        object.__setattr__(
            self, "direction", _enum(self.direction, PriceQuoteDirection)
        )
        object.__setattr__(self, "source", _enum(self.source, PriceQuoteSource))
        for name in (
            "ratio_milli",
            "confidence_milli",
            "source_tick",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.confidence_milli > 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class PriceUnitRow:
    """One detached unit summary across owners and distributions."""

    unit_token: str
    unit_kind: str
    unit_source: PriceUnitSource
    owner_count: int
    expectation_count: int
    distribution_count: int
    median_confidence_milli: int
    unit_alignment: PriceAlignment
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(self, "unit_token", _unit_token(self.unit_token))
        object.__setattr__(self, "unit_kind", _unit_token(self.unit_kind))
        object.__setattr__(
            self, "unit_source", _enum(self.unit_source, PriceUnitSource)
        )
        for name in (
            "owner_count",
            "expectation_count",
            "distribution_count",
            "median_confidence_milli",
        ):
            object.__setattr__(self, name, _count(name, getattr(self, name)))
        if self.median_confidence_milli > 1_000:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(
            self, "unit_alignment", _enum(self.unit_alignment, PriceAlignment)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )


@dataclass(frozen=True, slots=True)
class PriceMarketMembershipInput:
    """Detached V4-20 market membership supplied as analysis input."""

    market_token: str
    venue_id: str
    window_index: int
    coverage: PriceCoverage

    def __post_init__(self) -> None:
        _forbid_keys(type(self))
        object.__setattr__(
            self,
            "market_token",
            _group_token("market_token", self.market_token, "mktc-"),
        )
        object.__setattr__(
            self, "venue_id", _group_token("venue_id", self.venue_id, "mkt-ven-")
        )
        object.__setattr__(
            self, "window_index", _count("window_index", self.window_index)
        )
        object.__setattr__(
            self, "coverage", _enum(self.coverage, PriceCoverage)
        )
