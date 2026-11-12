"""Lift venue distributions to V4-20 markets through detached memberships.

V4-21 never mints, changes, splits, merges, or dissolves a market identity. A
market distribution recomputes quantiles and five bin shares from raw paired
samples and remains a distribution, never a single market price.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.emergent_prices_contract import (
    EmergentPriceAnalysisError,
    PriceCoverage,
    PriceSampleSource,
    PriceUnitSource,
    price_distribution_token,
)
from analysis.emergent_prices_detection import (
    detect_price_relations,
    distribution_summary,
)
from analysis.emergent_prices_policy import (
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
)
from analysis.emergent_prices_rows import (
    PriceDistributionRow,
    PriceEvidenceHarvest,
    PriceMarketMembershipInput,
    PriceMarketRow,
    PriceRelationRow,
)

__all__ = ["PriceMarketJoin", "join_market_memberships"]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.emergent_prices.markets")


@dataclass(frozen=True, slots=True)
class PriceMarketJoin:
    """Bounded market-level distributions, summaries, and relations."""

    distributions: tuple[PriceDistributionRow, ...]
    markets: tuple[PriceMarketRow, ...]
    relations: tuple[PriceRelationRow, ...]
    market_coverage: PriceCoverage
    relation_coverage: PriceCoverage
    notices: tuple[str, ...]


def _policy(
    policy: EmergentPricesAnalysisPolicy | None,
) -> EmergentPricesAnalysisPolicy:
    active = (
        default_emergent_prices_analysis_policy() if policy is None else policy
    )
    if type(active) is not EmergentPricesAnalysisPolicy:
        raise EmergentPriceAnalysisError("price_analysis_invalid_policy")
    return active


def _rows[T](value: object, row_type: type[T]) -> tuple[T, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    rows = tuple(value)
    for row in rows:
        if type(row) is not row_type:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    return cast(tuple[T, ...], rows)


def join_market_memberships(
    memberships: Sequence[PriceMarketMembershipInput],
    evidence: PriceEvidenceHarvest,
    venue_distributions: Sequence[PriceDistributionRow],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> PriceMarketJoin:
    """Regroup paired evidence by detached market membership."""

    active = _policy(policy)
    membership_rows = _rows(memberships, PriceMarketMembershipInput)
    if type(evidence) is not PriceEvidenceHarvest:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    _rows(venue_distributions, PriceDistributionRow)
    if not membership_rows:
        return PriceMarketJoin(
            distributions=(),
            markets=(),
            relations=(),
            market_coverage=PriceCoverage.MISSING,
            relation_coverage=PriceCoverage.MISSING,
            notices=("price_market_membership_missing",),
        )

    venue_to_market: dict[tuple[int, str], str] = {}
    seen: set[tuple[str, str, int]] = set()
    notices: set[str] = set()
    conflicts = 0
    for membership_row in membership_rows:
        key = (
            membership_row.market_token,
            membership_row.venue_id,
            membership_row.window_index,
        )
        if key in seen:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        seen.add(key)
        if membership_row.market_token == "none":
            continue
        venue_key = (membership_row.window_index, membership_row.venue_id)
        existing = venue_to_market.get(venue_key)
        if existing is not None and existing != membership_row.market_token:
            conflicts += 1
            notices.add("price_market_membership_conflict")
            continue
        venue_to_market[venue_key] = membership_row.market_token
    if conflicts:
        _LOG.warning("price_market_membership_conflict count=%s", conflicts)

    grouped: dict[tuple[int, str, str, str, str], list[int]] = defaultdict(list)
    for exchange_row in evidence.exchanges:
        if exchange_row.ratio_milli is None:
            continue
        market_token = venue_to_market.get(
            (exchange_row.window_index, exchange_row.venue_token)
        )
        if market_token is None:
            continue
        grouped[
            (
                exchange_row.window_index,
                market_token,
                exchange_row.item_kind,
                exchange_row.unit_kind,
                PriceSampleSource.COMPLETED.value,
            )
        ].append(exchange_row.ratio_milli)
    for quote_row in evidence.quotes:
        if quote_row.ratio_milli is None:
            continue
        market_token = venue_to_market.get(
            (quote_row.window_index, quote_row.venue_token)
        )
        if market_token is None:
            continue
        grouped[
            (
                quote_row.window_index,
                market_token,
                quote_row.item_kind,
                quote_row.unit_kind,
                PriceSampleSource.QUOTED.value,
            )
        ].append(quote_row.ratio_milli)

    distributions: list[PriceDistributionRow] = []
    for group_key in sorted(grouped):
        (
            window_index,
            market_token,
            item_kind,
            unit_kind,
            sample_source,
        ) = group_key
        summary = distribution_summary(grouped[group_key], policy=active)
        distributions.append(
            PriceDistributionRow(
                distribution_id=price_distribution_token(
                    market_token,
                    window_index,
                    item_kind,
                    unit_kind,
                    PriceUnitSource.EXCHANGE_COUNTERPART.value,
                    sample_source,
                ),
                window_index=window_index,
                venue_id="none",
                market_token=market_token,
                item_kind=item_kind,
                unit_kind=unit_kind,
                unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
                sample_source=PriceSampleSource(sample_source),
                sample_count=summary.sample_count,
                min_ratio_milli=summary.minimum,
                p25_ratio_milli=summary.p25,
                median_ratio_milli=summary.median,
                p75_ratio_milli=summary.p75,
                max_ratio_milli=summary.maximum,
                iqr_milli=summary.iqr,
                dispersion_milli=summary.dispersion,
                bin_shares_milli=summary.bins,
                status=summary.status,
                coverage=(
                    PriceCoverage.PARTIAL
                    if evidence.coverage is PriceCoverage.PARTIAL
                    else PriceCoverage.COMPLETE
                ),
            )
        )
    if len(distributions) > active.max_distribution_rows:
        distributions = distributions[: active.max_distribution_rows]
        notices.add("price_distribution_truncated")

    markets: list[PriceMarketRow] = []
    market_windows: dict[tuple[str, int], list[PriceDistributionRow]] = defaultdict(
        list
    )
    for distribution_row in distributions:
        market_windows[
            (distribution_row.market_token, distribution_row.window_index)
        ].append(distribution_row)
    venue_sets: dict[tuple[str, int], set[str]] = defaultdict(set)
    for membership_row in membership_rows:
        if membership_row.market_token == "none":
            continue
        venue_sets[
            (membership_row.market_token, membership_row.window_index)
        ].add(membership_row.venue_id)
    for (market_token, window_index), rows in sorted(market_windows.items()):
        markets.append(
            PriceMarketRow(
                market_token=market_token,
                window_index=window_index,
                venue_count=len(venue_sets[(market_token, window_index)]),
                distribution_count=len(rows),
                sample_count=sum(row.sample_count for row in rows),
                item_kind_count=len({row.item_kind for row in rows}),
                unit_count=len({row.unit_kind for row in rows}),
                coverage=(
                    PriceCoverage.PARTIAL
                    if any(row.coverage is PriceCoverage.PARTIAL for row in rows)
                    else PriceCoverage.COMPLETE
                ),
            )
        )
    if len(markets) > active.max_market_rows:
        markets = markets[: active.max_market_rows]
        notices.add("price_market_truncated")

    relations = list(detect_price_relations(distributions, policy=active))
    if len(relations) > active.max_relation_rows:
        relations = relations[: active.max_relation_rows]
        notices.add("price_relation_truncated")

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
    market_coverage = (
        PriceCoverage.MISSING
        if not markets
        else (PriceCoverage.PARTIAL if notices else PriceCoverage.COMPLETE)
    )
    _LOG.debug(
        "price_markets_joined markets=%s relations=%s",
        len(markets),
        len(relations),
    )
    return PriceMarketJoin(
        distributions=tuple(distributions),
        markets=tuple(markets),
        relations=tuple(relations),
        market_coverage=market_coverage,
        relation_coverage=relation_coverage,
        notices=tuple(sorted(notices)),
    )
