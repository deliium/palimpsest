"""Bounded detached emergent-price analysis composition and digest."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Final, cast

from analysis.emergent_prices_contract import (
    EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
    EmergentPriceAnalysisError,
    PriceCoverage,
)
from analysis.emergent_prices_detection import (
    detect_price_relations,
    detect_venue_distributions,
)
from analysis.emergent_prices_events import (
    price_evidence_rows_from_events,
)
from analysis.emergent_prices_expectations import (
    join_price_expectations,
    join_price_quotes,
    summarize_price_units,
)
from analysis.emergent_prices_markets import join_market_memberships
from analysis.emergent_prices_policy import (
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
    window_index_for_tick,
)
from analysis.emergent_prices_rows import (
    ExchangePriceEvidenceRow,
    OwnerPriceExpectationRow,
    OwnerPriceQuoteRow,
    PriceDistributionRow,
    PriceMarketMembershipInput,
    PriceMarketRow,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
    PriceQuoteEvidenceRow,
    PriceRelationRow,
    PriceUnitRow,
)

__all__ = [
    "EmergentPricesAnalysis",
    "emergent_prices_analysis_digest",
    "empty_emergent_prices_analysis",
    "harvest_emergent_prices_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.emergent_prices.analysis"
)


@dataclass(frozen=True, slots=True)
class EmergentPricesAnalysis:
    """One deterministic, detached emergent-price analysis result."""

    window_tick: int
    policy_version: str
    evidence_coverage: PriceCoverage
    expectation_coverage: PriceCoverage
    quote_coverage: PriceCoverage
    distribution_coverage: PriceCoverage
    market_coverage: PriceCoverage
    relation_coverage: PriceCoverage
    coverage: PriceCoverage
    units: tuple[PriceUnitRow, ...]
    expectations: tuple[OwnerPriceExpectationRow, ...]
    quotes: tuple[OwnerPriceQuoteRow, ...]
    distributions: tuple[PriceDistributionRow, ...]
    markets: tuple[PriceMarketRow, ...]
    relations: tuple[PriceRelationRow, ...]
    notices: tuple[str, ...]
    exchange_count: int
    quote_count: int
    evidence: tuple[ExchangePriceEvidenceRow | PriceQuoteEvidenceRow, ...] = ()

    def __post_init__(self) -> None:
        if type(self.policy_version) is not str:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in (
            "evidence_coverage",
            "expectation_coverage",
            "quote_coverage",
            "distribution_coverage",
            "market_coverage",
            "relation_coverage",
            "coverage",
        ):
            if type(getattr(self, name)) is not PriceCoverage:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        for name in ("window_tick", "exchange_count", "quote_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        object.__setattr__(self, "notices", tuple(sorted(set(self.notices))))


def empty_emergent_prices_analysis() -> EmergentPricesAnalysis:
    """Return the explicit missing analysis for absent committed events."""

    missing = PriceCoverage.MISSING
    return EmergentPricesAnalysis(
        window_tick=0,
        policy_version=EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
        evidence_coverage=missing,
        expectation_coverage=missing,
        quote_coverage=missing,
        distribution_coverage=missing,
        market_coverage=missing,
        relation_coverage=missing,
        coverage=missing,
        units=(),
        expectations=(),
        quotes=(),
        distributions=(),
        markets=(),
        relations=(),
        notices=(),
        exchange_count=0,
        quote_count=0,
    )


def _rows[T](value: object, row_type: type[T]) -> tuple[T, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    rows = tuple(value)
    for row in rows:
        if type(row) is not row_type:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return cast(tuple[T, ...], rows)


def _any_partial(*coverages: PriceCoverage) -> bool:
    return any(
        coverage in {PriceCoverage.PARTIAL, PriceCoverage.MISSING}
        for coverage in coverages
    )


def harvest_emergent_prices_analysis(
    *,
    committed_events: Iterable[object],
    expectation_inputs: Sequence[PriceOwnerExpectationInput] = (),
    quote_inputs: Sequence[PriceOwnerQuoteInput] = (),
    membership_inputs: Sequence[PriceMarketMembershipInput] = (),
    policy: EmergentPricesAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> EmergentPricesAnalysis:
    """Compose evidence, distributions, markets, and owner joins."""

    active = (
        default_emergent_prices_analysis_policy() if policy is None else policy
    )
    if type(active) is not EmergentPricesAnalysisPolicy:
        raise EmergentPriceAnalysisError("price_analysis_invalid_policy")
    if isinstance(committed_events, (str, bytes)) or not isinstance(
        committed_events, Iterable
    ):
        raise EmergentPriceAnalysisError("price_analysis_missing_input")
    events = tuple(committed_events)
    if not events:
        return empty_emergent_prices_analysis()
    evidence = price_evidence_rows_from_events(events, policy=active)
    latest_tick = max(
        (getattr(event, "tick", 0) for event in events), default=0
    )
    if window_end is None:
        window_end = latest_tick
    if isinstance(window_end, bool) or type(window_end) is not int or window_end < 0:
        raise EmergentPriceAnalysisError("price_analysis_invalid_window")
    window_index_for_tick(window_end, active)

    venue_distributions = detect_venue_distributions(evidence, policy=active)
    market_join = join_market_memberships(
        membership_inputs, evidence, venue_distributions, policy=active
    )
    expectation_input_rows = _rows(
        expectation_inputs, PriceOwnerExpectationInput
    )
    quote_input_rows = _rows(quote_inputs, PriceOwnerQuoteInput)
    expectation_join = join_price_expectations(
        expectation_input_rows, venue_distributions, policy=active
    )
    quote_join = join_price_quotes(quote_input_rows, policy=active)
    units = summarize_price_units(
        expectation_join.rows,
        quote_join.rows,
        venue_distributions,
        policy=active,
    )
    if market_join.distributions:
        distributions = (*venue_distributions, *market_join.distributions)
    else:
        distributions = venue_distributions
    if market_join.markets:
        relations = market_join.relations
        relation_coverage = market_join.relation_coverage
    else:
        relations = detect_price_relations(venue_distributions, policy=active)
        relation_coverage = (
            PriceCoverage.MISSING
            if not relations
            else (
                PriceCoverage.PARTIAL
                if any(
                    row.coverage is PriceCoverage.PARTIAL for row in relations
                )
                else PriceCoverage.COMPLETE
            )
        )

    distribution_coverage = (
        PriceCoverage.MISSING
        if not distributions
        else (
            PriceCoverage.PARTIAL
            if _any_partial(
                *(row.coverage for row in distributions)
            )
            or any(
                row.status.value == "insufficient_samples"
                for row in distributions
            )
            else PriceCoverage.COMPLETE
        )
    )
    notices = set(evidence.notices)
    notices.update(expectation_join.notices)
    notices.update(quote_join.notices)
    notices.update(units.notices)
    notices.update(market_join.notices)
    if (
        evidence.coverage is PriceCoverage.MISSING
        or not distributions
        or distribution_coverage is PriceCoverage.MISSING
    ):
        overall = PriceCoverage.MISSING
    elif _any_partial(
        evidence.coverage,
        expectation_join.coverage,
        quote_join.coverage,
        distribution_coverage,
        market_join.market_coverage,
        relation_coverage,
    ):
        overall = PriceCoverage.PARTIAL
    else:
        overall = PriceCoverage.COMPLETE

    analysis = EmergentPricesAnalysis(
        window_tick=window_end,
        policy_version=EMERGENT_PRICES_ANALYSIS_POLICY_VERSION,
        evidence_coverage=evidence.coverage,
        expectation_coverage=expectation_join.coverage,
        quote_coverage=quote_join.coverage,
        distribution_coverage=distribution_coverage,
        market_coverage=market_join.market_coverage,
        relation_coverage=relation_coverage,
        coverage=overall,
        units=units.rows,
        expectations=expectation_join.rows,
        quotes=quote_join.rows,
        distributions=distributions,
        markets=market_join.markets,
        relations=relations,
        notices=tuple(sorted(notices)),
        exchange_count=evidence.exchange_count,
        quote_count=evidence.quote_count,
        evidence=(*evidence.exchanges, *evidence.quotes),
    )
    _LOG.info(
        "price_analysis_harvested distributions=%s markets=%s relations=%s coverage=%s",
        len(analysis.distributions),
        len(analysis.markets),
        len(analysis.relations),
        analysis.coverage.value,
    )
    return analysis


def _canonical(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {
            key: _canonical(item)
            for key, item in asdict(value).items()
        }
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value


def emergent_prices_analysis_digest(analysis: EmergentPricesAnalysis) -> str:
    """Return a deterministic digest using canonical JSON conventions."""

    if type(analysis) is not EmergentPricesAnalysis:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    payload = json.dumps(
        _canonical(analysis),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
