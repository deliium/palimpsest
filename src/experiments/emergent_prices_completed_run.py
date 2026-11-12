"""Completed-run composition of detached emergent-price analysis."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis import (
    EmergentPricesAnalysis,
    EmergentPricesAnalysisPolicy,
    PriceCoverage,
    PriceMarketMembershipInput,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
    harvest_emergent_prices_analysis,
)
from simulation.emergent_prices_export import (
    EmergentPriceOwnerQuoteRow,
    EmergentPriceOwnerRow,
    price_owner_export,
)

__all__ = ["build_completed_run_emergent_prices_analysis"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.emergent_prices_completed_run"
)


def build_completed_run_emergent_prices_analysis(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    policy: EmergentPricesAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> EmergentPricesAnalysis:
    """Build one bounded price analysis for a completed run."""

    if committed_events is None:
        _LOG.error(
            "emergent_prices_completed_run_rejected reason_code=events_required"
        )
        raise ValueError("emergent_prices_analysis_missing_events")
    ledgers = getattr(runner_result, "emergent_price_ledgers", ())
    if not ledgers:
        _LOG.warning("emergent_prices_completed_run_missing_ledgers")
    rows = price_owner_export(tuple(ledgers))
    expectations: list[PriceOwnerExpectationInput] = []
    quotes: list[PriceOwnerQuoteInput] = []
    for row in rows:
        if type(row) is EmergentPriceOwnerRow:
            expectations.append(
                PriceOwnerExpectationInput(
                    owner_token=row.owner_token,
                    window_index=row.window_index,
                    item_kind=row.item_kind_token,
                    unit_kind=row.unit_token,
                    unit_source=PriceUnitSource(row.unit_source),
                    expected_ratio_milli=row.expected_ratio_milli,
                    confidence_milli=row.confidence_milli,
                    level=row.level,
                    valuation_reservation=row.valuation_reservation,
                    observation_count=row.observation_count,
                    quote_count=row.quote_count,
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                    coverage=PriceCoverage(row.coverage),
                )
            )
        elif type(row) is EmergentPriceOwnerQuoteRow:
            quotes.append(
                PriceOwnerQuoteInput(
                    owner_token=row.owner_token,
                    venue_id=row.venue_token,
                    window_index=row.window_index,
                    item_kind=row.item_kind_token,
                    unit_kind=row.unit_token,
                    direction=PriceQuoteDirection(row.direction),
                    ratio_milli=row.ratio_milli,
                    confidence_milli=row.confidence_milli,
                    source=PriceQuoteSource(row.source),
                    source_tick=row.source_tick,
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                    coverage=PriceCoverage(row.coverage),
                )
            )
    memberships = _membership_inputs(
        runner_result, committed_events=committed_events, run_id=run_id
    )
    analysis = harvest_emergent_prices_analysis(
        committed_events=committed_events,
        expectation_inputs=tuple(expectations),
        quote_inputs=tuple(quotes),
        membership_inputs=memberships,
        policy=policy,
        window_end=window_end,
    )
    _LOG.debug(
        "emergent_prices_completed_run run_id_present=%s owners=%s events=%s "
        "coverage=%s",
        bool(run_id),
        len(ledgers),
        len(committed_events),
        analysis.coverage.value,
    )
    del input_revision
    return analysis


def _membership_inputs(
    runner_result: object,
    *,
    committed_events: Sequence[object],
    run_id: str,
) -> tuple[PriceMarketMembershipInput, ...]:
    if not getattr(runner_result, "market_institution_ledgers", ()):
        return ()
    try:
        from experiments.market_institutions_completed_run import (
            build_completed_run_market_institutions_analysis,
        )

        market_analysis = build_completed_run_market_institutions_analysis(
            runner_result,
            committed_events=committed_events,
            run_id=run_id,
        )
    except Exception as exc:
        _LOG.warning(
            "price_market_membership_unavailable code=%s",
            getattr(exc, "reason_code", type(exc).__name__),
        )
        return ()
    if not market_analysis.markets:
        return ()
    latest_window = max(row.window_index for row in market_analysis.markets)
    rows: list[PriceMarketMembershipInput] = []
    for market in market_analysis.markets:
        if market.window_index != latest_window:
            continue
        for venue_id in market.venue_ids:
            rows.append(
                PriceMarketMembershipInput(
                    market_token=market.market_token,
                    venue_id=venue_id,
                    window_index=market.window_index,
                    coverage=PriceCoverage(market.coverage.value),
                )
            )
    rows.sort(
        key=lambda row: (row.market_token, row.venue_id, row.window_index)
    )
    deduplicated: dict[tuple[str, str, int], PriceMarketMembershipInput] = {}
    for row in rows:
        deduplicated.setdefault(
            (row.market_token, row.venue_id, row.window_index), row
        )
    return tuple(deduplicated.values())
