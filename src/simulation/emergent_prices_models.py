"""Canonical ``emergent-prices-snapshot-v1`` read model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "EMERGENT_PRICES_ARTIFACT_MAX_BYTES",
    "EMERGENT_PRICES_MAX_DISTRIBUTIONS",
    "EMERGENT_PRICES_MAX_EXPECTATIONS",
    "EMERGENT_PRICES_MAX_MARKETS",
    "EMERGENT_PRICES_MAX_QUOTES",
    "EMERGENT_PRICES_MAX_RELATIONS",
    "EMERGENT_PRICES_MAX_UNITS",
    "EMERGENT_PRICES_MAX_WINDOWS",
    "EMERGENT_PRICES_PUBLICATION_PREFIX",
    "EMERGENT_PRICES_SNAPSHOT_POLICY",
    "EMERGENT_PRICES_SNAPSHOT_VERSION",
    "EmergentPricesSnapshot",
    "EmergentPricesSummaryRecord",
    "PriceDistributionRecord",
    "PriceExpectationRecord",
    "PriceMarketRecord",
    "PriceQuoteRecord",
    "PriceRelationRecord",
    "PriceUnitRecord",
    "empty_emergent_prices_snapshot",
]

EMERGENT_PRICES_SNAPSHOT_VERSION: Final[str] = "emergent-prices-snapshot-v1"
EMERGENT_PRICES_SNAPSHOT_POLICY: Final[str] = "emergent-prices.v1"
EMERGENT_PRICES_PUBLICATION_PREFIX: Final[str] = "prc-pub-"

EMERGENT_PRICES_MAX_UNITS: Final[int] = 64
EMERGENT_PRICES_MAX_EXPECTATIONS: Final[int] = 2_048
EMERGENT_PRICES_MAX_QUOTES: Final[int] = 2_048
EMERGENT_PRICES_MAX_DISTRIBUTIONS: Final[int] = 4_096
EMERGENT_PRICES_MAX_MARKETS: Final[int] = 1_024
EMERGENT_PRICES_MAX_RELATIONS: Final[int] = 16_384
EMERGENT_PRICES_MAX_WINDOWS: Final[int] = 512
EMERGENT_PRICES_ARTIFACT_MAX_BYTES: Final[int] = 8_388_608

_COVERAGE = {"complete", "partial", "missing"}


def _count(value: object) -> int:
    return require_exact_nonneg_int("count", value)


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("emergent_prices_snapshot_invalid")
    return require_stable_id("token", value)


def _coverage(value: object) -> str:
    token = getattr(value, "value", value)
    if token not in _COVERAGE:
        raise ValueError("emergent_prices_snapshot_invalid")
    return str(token)


def _enum(value: object, allowed: set[str]) -> str:
    token = getattr(value, "value", value)
    if token not in allowed:
        raise ValueError("emergent_prices_snapshot_invalid")
    return str(token)


@dataclass(frozen=True, slots=True)
class PriceUnitRecord:
    unit_token: str
    unit_source: str
    owner_count: int
    expectation_count: int
    distribution_count: int
    median_confidence_milli: int
    unit_alignment: str
    coverage: str

    def __post_init__(self) -> None:
        _token(self.unit_token)
        object.__setattr__(
            self,
            "unit_source",
            _enum(
                self.unit_source,
                {
                    "owner_reference",
                    "observed_medium",
                    "exchange_counterpart",
                    "quoted",
                    "unknown",
                },
            ),
        )
        for name in (
            "owner_count",
            "expectation_count",
            "distribution_count",
            "median_confidence_milli",
        ):
            _count(getattr(self, name))
        object.__setattr__(
            self,
            "unit_alignment",
            _enum(
                self.unit_alignment,
                {"consistent", "unresolved", "inconsistent", "not_applicable"},
            ),
        )
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class PriceExpectationRecord:
    expectation_id: str
    window_index: int
    owner_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    expected_ratio_milli: int
    confidence_milli: int
    level: str
    valuation_reservation: int
    observation_count: int
    quote_count: int
    distribution_source: str
    alignment: str
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "expectation_id",
            "owner_token",
            "item_kind",
            "unit_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(
            self,
            "unit_source",
            _enum(
                self.unit_source,
                {
                    "owner_reference",
                    "observed_medium",
                    "exchange_counterpart",
                    "quoted",
                    "unknown",
                },
            ),
        )
        for name in (
            "window_index",
            "expected_ratio_milli",
            "confidence_milli",
            "valuation_reservation",
            "observation_count",
            "quote_count",
        ):
            _count(getattr(self, name))
        object.__setattr__(
            self, "level", _enum(self.level, {"none", "weak", "expected", "strong"})
        )
        object.__setattr__(
            self,
            "distribution_source",
            _enum(self.distribution_source, {"completed", "quoted", "none"}),
        )
        object.__setattr__(
            self,
            "alignment",
            _enum(
                self.alignment,
                {"consistent", "unresolved", "inconsistent", "not_applicable"},
            ),
        )
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class PriceQuoteRecord:
    quote_id: str
    window_index: int
    venue_id: str
    actor_token: str
    counterparty_token: str
    item_kind: str
    unit_kind: str
    direction: str
    ratio_milli: int
    confidence_milli: int
    source: str
    source_tick: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "quote_id",
            "venue_id",
            "actor_token",
            "counterparty_token",
            "item_kind",
            "unit_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(
            self,
            "direction",
            _enum(self.direction, {"give_for_unit", "unit_for_give"}),
        )
        object.__setattr__(
            self,
            "source",
            _enum(self.source, {"observed_offer", "communicated", "self_authored"}),
        )
        for name in (
            "window_index",
            "ratio_milli",
            "confidence_milli",
            "source_tick",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class PriceDistributionRecord:
    distribution_id: str
    window_index: int
    venue_id: str
    market_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    sample_source: str
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: str
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "distribution_id",
            "venue_id",
            "market_token",
            "item_kind",
            "unit_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(
            self,
            "unit_source",
            _enum(
                self.unit_source,
                {
                    "owner_reference",
                    "observed_medium",
                    "exchange_counterpart",
                    "quoted",
                    "unknown",
                },
            ),
        )
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, {"completed", "quoted"})
        )
        for name in (
            "window_index",
            "sample_count",
            "min_ratio_milli",
            "p25_ratio_milli",
            "median_ratio_milli",
            "p75_ratio_milli",
            "max_ratio_milli",
            "iqr_milli",
            "dispersion_milli",
        ):
            _count(getattr(self, name))
        bins = tuple(self.bin_shares_milli)
        if len(bins) != 5 or any(
            isinstance(item, bool)
            or type(item) is not int
            or not 0 <= item <= 1_000
            for item in bins
        ):
            raise ValueError("emergent_prices_snapshot_invalid")
        object.__setattr__(self, "bin_shares_milli", bins)
        object.__setattr__(
            self,
            "status",
            _enum(self.status, {"available", "insufficient_samples"}),
        )
        object.__setattr__(self, "coverage", _coverage(self.coverage))
        if self.status == "available" and sum(bins) != 1_000:
            raise ValueError("emergent_prices_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class PriceMarketRecord:
    market_token: str
    window_index: int
    venue_count: int
    distribution_count: int
    sample_count: int
    item_kind_count: int
    unit_count: int
    coverage: str

    def __post_init__(self) -> None:
        _token(self.market_token)
        for name in (
            "window_index",
            "venue_count",
            "distribution_count",
            "sample_count",
            "item_kind_count",
            "unit_count",
        ):
            _count(getattr(self, name))
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class PriceRelationRecord:
    relation_id: str
    window_index: int
    group_kind: str
    group_a_token: str
    group_b_token: str
    item_kind: str
    unit_kind: str
    unit_source: str
    sample_source: str
    overlap_milli: int
    median_gap_milli: int
    relation: str
    sample_a: int
    sample_b: int
    coverage: str

    def __post_init__(self) -> None:
        for name in (
            "relation_id",
            "group_a_token",
            "group_b_token",
            "item_kind",
            "unit_kind",
        ):
            _token(getattr(self, name))
        object.__setattr__(
            self, "group_kind", _enum(self.group_kind, {"venue", "market"})
        )
        object.__setattr__(
            self,
            "unit_source",
            _enum(
                self.unit_source,
                {
                    "owner_reference",
                    "observed_medium",
                    "exchange_counterpart",
                    "quoted",
                    "unknown",
                },
            ),
        )
        object.__setattr__(
            self, "sample_source", _enum(self.sample_source, {"completed", "quoted"})
        )
        for name in (
            "window_index",
            "overlap_milli",
            "median_gap_milli",
            "sample_a",
            "sample_b",
        ):
            _count(getattr(self, name))
        object.__setattr__(
            self,
            "relation",
            _enum(
                self.relation,
                {
                    "converged",
                    "partially_converged",
                    "divergent",
                    "insufficient_evidence",
                },
            ),
        )
        object.__setattr__(self, "coverage", _coverage(self.coverage))


@dataclass(frozen=True, slots=True)
class EmergentPricesSummaryRecord:
    window_tick: int
    window_count: int
    unit_count: int
    expectation_count: int
    quote_count: int
    distribution_count: int
    market_count: int
    relation_count: int
    exchange_count: int
    quote_event_count: int
    evidence_coverage: str
    expectation_coverage: str
    quote_coverage: str
    distribution_coverage: str
    market_coverage: str
    relation_coverage: str
    coverage: str
    truncated: bool

    def __post_init__(self) -> None:
        for name in (
            "window_tick",
            "window_count",
            "unit_count",
            "expectation_count",
            "quote_count",
            "distribution_count",
            "market_count",
            "relation_count",
            "exchange_count",
            "quote_event_count",
        ):
            _count(getattr(self, name))
        for name in (
            "evidence_coverage",
            "expectation_coverage",
            "quote_coverage",
            "distribution_coverage",
            "market_coverage",
            "relation_coverage",
            "coverage",
        ):
            object.__setattr__(self, name, _coverage(getattr(self, name)))
        if type(self.truncated) is not bool:
            raise ValueError("emergent_prices_snapshot_invalid")


@dataclass(frozen=True, slots=True)
class EmergentPricesSnapshot:
    run_id: str
    schema_version: str
    policy_version: str
    summary: EmergentPricesSummaryRecord
    units: tuple[PriceUnitRecord, ...]
    expectations: tuple[PriceExpectationRecord, ...]
    quotes: tuple[PriceQuoteRecord, ...]
    distributions: tuple[PriceDistributionRecord, ...]
    markets: tuple[PriceMarketRecord, ...]
    relations: tuple[PriceRelationRecord, ...]
    digest: str = ""
    publication_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "run_id", require_stable_id("run_id", self.run_id)
        )
        if self.schema_version != EMERGENT_PRICES_SNAPSHOT_VERSION:
            raise ValueError("emergent_prices_snapshot_version")
        if self.policy_version != EMERGENT_PRICES_SNAPSHOT_POLICY:
            raise ValueError("emergent_prices_snapshot_version")
        if type(self.summary) is not EmergentPricesSummaryRecord:
            raise ValueError("emergent_prices_snapshot_invalid")
        for name, row_type, cap in (
            ("units", PriceUnitRecord, EMERGENT_PRICES_MAX_UNITS),
            (
                "expectations",
                PriceExpectationRecord,
                EMERGENT_PRICES_MAX_EXPECTATIONS,
            ),
            ("quotes", PriceQuoteRecord, EMERGENT_PRICES_MAX_QUOTES),
            (
                "distributions",
                PriceDistributionRecord,
                EMERGENT_PRICES_MAX_DISTRIBUTIONS,
            ),
            ("markets", PriceMarketRecord, EMERGENT_PRICES_MAX_MARKETS),
            ("relations", PriceRelationRecord, EMERGENT_PRICES_MAX_RELATIONS),
        ):
            values = getattr(self, name)
            if type(values) is not tuple or len(values) > cap:
                raise ValueError("emergent_prices_snapshot_invalid")
            for row in values:
                if type(row) is not row_type:
                    raise ValueError("emergent_prices_snapshot_invalid")
        if type(self.digest) is not str or type(self.publication_id) is not str:
            raise ValueError("emergent_prices_snapshot_invalid")


def empty_emergent_prices_snapshot(
    run_id: str, *, digest: str = "", publication_id: str = ""
) -> EmergentPricesSnapshot:
    """Return one empty canonical snapshot."""

    missing = "missing"
    return EmergentPricesSnapshot(
        run_id=run_id,
        schema_version=EMERGENT_PRICES_SNAPSHOT_VERSION,
        policy_version=EMERGENT_PRICES_SNAPSHOT_POLICY,
        summary=EmergentPricesSummaryRecord(
            window_tick=0,
            window_count=0,
            unit_count=0,
            expectation_count=0,
            quote_count=0,
            distribution_count=0,
            market_count=0,
            relation_count=0,
            exchange_count=0,
            quote_event_count=0,
            evidence_coverage=missing,
            expectation_coverage=missing,
            quote_coverage=missing,
            distribution_coverage=missing,
            market_coverage=missing,
            relation_coverage=missing,
            coverage=missing,
            truncated=False,
        ),
        units=(),
        expectations=(),
        quotes=(),
        distributions=(),
        markets=(),
        relations=(),
        digest=digest,
        publication_id=publication_id,
    )
