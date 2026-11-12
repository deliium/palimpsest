"""One-way joins from detached owner beliefs to analytical distributions.

Owner rows never create, change, dominate, or replace a distribution. Alignment
is researcher-only and never returns to cognition. Missing input is ``missing``,
never complete with zeros.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.emergent_prices_contract import (
    EmergentPriceAnalysisError,
    PriceAlignment,
    PriceCoverage,
    PriceUnitSource,
    price_expectation_token,
    price_quote_token,
)
from analysis.emergent_prices_policy import (
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
)
from analysis.emergent_prices_rows import (
    OwnerPriceExpectationRow,
    OwnerPriceQuoteRow,
    PriceDistributionRow,
    PriceOwnerExpectationInput,
    PriceOwnerQuoteInput,
    PriceUnitRow,
)

__all__ = [
    "PriceExpectationJoin",
    "PriceQuoteJoin",
    "PriceUnitSummary",
    "join_price_expectations",
    "join_price_quotes",
    "summarize_price_units",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.emergent_prices.expectations"
)


@dataclass(frozen=True, slots=True)
class PriceExpectationJoin:
    """Bounded owner expectation rows with explicit coverage."""

    rows: tuple[OwnerPriceExpectationRow, ...]
    coverage: PriceCoverage
    notices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PriceQuoteJoin:
    """Bounded owner quote rows with explicit coverage."""

    rows: tuple[OwnerPriceQuoteRow, ...]
    coverage: PriceCoverage
    notices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PriceUnitSummary:
    """Bounded unit summary rows with explicit coverage."""

    rows: tuple[PriceUnitRow, ...]
    coverage: PriceCoverage
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


def _alignment(gap: int, policy: EmergentPricesAnalysisPolicy) -> PriceAlignment:
    if gap <= policy.alignment_low_milli:
        return PriceAlignment.CONSISTENT
    if gap >= policy.alignment_high_milli:
        return PriceAlignment.INCONSISTENT
    return PriceAlignment.UNRESOLVED


def join_price_expectations(
    inputs: Sequence[PriceOwnerExpectationInput],
    distributions: Sequence[PriceDistributionRow],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> PriceExpectationJoin:
    """Attach each owner expectation to at most one distribution."""

    active = _policy(policy)
    expectation_inputs = _rows(inputs, PriceOwnerExpectationInput)
    distribution_rows = _rows(distributions, PriceDistributionRow)
    if not expectation_inputs:
        return PriceExpectationJoin(
            rows=(),
            coverage=PriceCoverage.MISSING,
            notices=("price_owner_rows_missing",),
        )
    venues = [
        row for row in distribution_rows if row.venue_id != "none"
    ]
    rows: list[OwnerPriceExpectationRow] = []
    notices: set[str] = set()
    seen_owners: set[str] = set()
    for item in expectation_inputs:
        seen_owners.add(item.owner_token)
        candidates = [
            row
            for row in venues
            if row.window_index == item.window_index
            and row.item_kind == item.item_kind
            and row.unit_kind == item.unit_kind
        ]
        completed = [
            row
            for row in candidates
            if row.sample_source.value == "completed"
            and row.status.value == "available"
        ]
        quoted = [
            row
            for row in candidates
            if row.sample_source.value == "quoted"
            and row.status.value == "available"
        ]
        pool = completed if completed else quoted
        source = "completed" if completed else ("quoted" if quoted else "none")
        if not pool:
            rows.append(
                OwnerPriceExpectationRow(
                    expectation_id=price_expectation_token(
                        item.owner_token,
                        item.item_kind,
                        item.unit_kind,
                        item.window_index,
                        item.unit_source.value,
                    ),
                    window_index=item.window_index,
                    owner_token=item.owner_token,
                    item_kind=item.item_kind,
                    unit_kind=item.unit_kind,
                    unit_source=item.unit_source,
                    expected_ratio_milli=item.expected_ratio_milli,
                    confidence_milli=item.confidence_milli,
                    level=item.level,
                    valuation_reservation=item.valuation_reservation,
                    observation_count=item.observation_count,
                    quote_count=item.quote_count,
                    distribution_source="none",
                    alignment=PriceAlignment.NOT_APPLICABLE,
                    coverage=PriceCoverage.PARTIAL,
                )
            )
            continue
        chosen = sorted(
            pool, key=lambda row: (-row.sample_count, row.venue_id)
        )[0]
        gap = abs(item.expected_ratio_milli - chosen.median_ratio_milli) * 1_000 // max(
            1, max(item.expected_ratio_milli, chosen.median_ratio_milli)
        )
        coverage = (
            PriceCoverage.PARTIAL
            if len(candidates) > 1
            or item.coverage is PriceCoverage.PARTIAL
            or chosen.coverage is PriceCoverage.PARTIAL
            else PriceCoverage.COMPLETE
        )
        rows.append(
            OwnerPriceExpectationRow(
                expectation_id=price_expectation_token(
                    item.owner_token,
                    item.item_kind,
                    item.unit_kind,
                    item.window_index,
                    item.unit_source.value,
                ),
                window_index=item.window_index,
                owner_token=item.owner_token,
                item_kind=item.item_kind,
                unit_kind=item.unit_kind,
                unit_source=item.unit_source,
                expected_ratio_milli=item.expected_ratio_milli,
                confidence_milli=item.confidence_milli,
                level=item.level,
                valuation_reservation=item.valuation_reservation,
                observation_count=item.observation_count,
                quote_count=item.quote_count,
                distribution_source=source,
                alignment=_alignment(gap, active),
                coverage=coverage,
            )
        )
    if len(seen_owners) > active.max_owners:
        seen_owners = set(sorted(seen_owners)[: active.max_owners])
        rows = [row for row in rows if row.owner_token in seen_owners]
        notices.add("price_expectation_truncated")
    rows.sort(key=lambda row: (row.window_index, row.expectation_id))
    if len(rows) > active.max_expectation_rows:
        rows = rows[: active.max_expectation_rows]
        notices.add("price_expectation_truncated")
        _LOG.warning(
            "price_expectation_truncated count=%s", active.max_expectation_rows
        )
    coverage = (
        PriceCoverage.MISSING
        if not rows
        else (PriceCoverage.PARTIAL if notices else PriceCoverage.COMPLETE)
    )
    _LOG.debug(
        "price_owner_join expectations=%s quotes=%s coverage=%s",
        len(rows),
        0,
        coverage.value,
    )
    return PriceExpectationJoin(
        rows=tuple(rows), coverage=coverage, notices=tuple(sorted(notices))
    )


def join_price_quotes(
    inputs: Sequence[PriceOwnerQuoteInput],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> PriceQuoteJoin:
    """Emit one detached owner quote row per exported quote input."""

    active = _policy(policy)
    quote_inputs = _rows(inputs, PriceOwnerQuoteInput)
    if not quote_inputs:
        return PriceQuoteJoin(
            rows=(),
            coverage=PriceCoverage.MISSING,
            notices=("price_owner_rows_missing",),
        )
    rows = [
        OwnerPriceQuoteRow(
            quote_id=price_quote_token(
                item.owner_token,
                item.venue_id,
                item.item_kind,
                item.unit_kind,
                item.direction.value,
                item.source.value,
                item.source_tick,
                item.window_index,
            ),
            window_index=item.window_index,
            venue_id=item.venue_id,
            actor_token=item.owner_token,
            counterparty_token="none",
            item_kind=item.item_kind,
            unit_kind=item.unit_kind,
            direction=item.direction,
            ratio_milli=item.ratio_milli,
            confidence_milli=item.confidence_milli,
            source=item.source,
            source_tick=item.source_tick,
            coverage=item.coverage,
        )
        for item in quote_inputs
    ]
    rows.sort(
        key=lambda row: (
            row.window_index,
            row.venue_id,
            row.actor_token,
            row.item_kind,
            row.unit_kind,
            row.direction.value,
            row.ratio_milli,
        )
    )
    notices: set[str] = set()
    if len(rows) > active.max_owner_quote_rows:
        rows = rows[: active.max_owner_quote_rows]
        notices.add("price_quote_truncated")
        _LOG.warning(
            "price_quote_truncated count=%s", active.max_owner_quote_rows
        )
    coverage = PriceCoverage.PARTIAL if notices else PriceCoverage.COMPLETE
    return PriceQuoteJoin(
        rows=tuple(rows), coverage=coverage, notices=tuple(sorted(notices))
    )


def summarize_price_units(
    expectations: Sequence[OwnerPriceExpectationRow],
    quotes: Sequence[OwnerPriceQuoteRow],
    distributions: Sequence[PriceDistributionRow],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> PriceUnitSummary:
    """Summarize unit sources without merging sources into one price."""

    active = _policy(policy)
    expectation_rows = _rows(expectations, OwnerPriceExpectationRow)
    quote_rows = _rows(quotes, OwnerPriceQuoteRow)
    distribution_rows = _rows(distributions, PriceDistributionRow)
    if not expectation_rows:
        return PriceUnitSummary(
            rows=(), coverage=PriceCoverage.MISSING, notices=()
        )
    groups: dict[tuple[str, PriceUnitSource], list[OwnerPriceExpectationRow]] = (
        defaultdict(list)
    )
    for row in expectation_rows:
        groups[(row.unit_kind, row.unit_source)].append(row)
    item_kinds_by_group = {
        key: {row.item_kind for row in values} for key, values in groups.items()
    }
    rows: list[PriceUnitRow] = []
    for (unit_kind, unit_source), values in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1].value)
    ):
        owners = {row.owner_token for row in values if row.unit_kind != "none"}
        confidences = sorted(row.confidence_milli for row in values)
        median_confidence = (
            confidences[(len(confidences) - 1) // 2] if confidences else 0
        )
        relevant = [
            row
            for row in distribution_rows
            if row.item_kind in item_kinds_by_group[(unit_kind, unit_source)]
        ]
        same_unit = [row for row in relevant if row.unit_kind == unit_kind]
        if unit_source is PriceUnitSource.UNKNOWN or unit_kind == "none":
            alignment = PriceAlignment.NOT_APPLICABLE
        elif any(
            row.unit_source is PriceUnitSource.EXCHANGE_COUNTERPART
            for row in same_unit
        ):
            alignment = PriceAlignment.CONSISTENT
        elif relevant:
            alignment = PriceAlignment.INCONSISTENT
        else:
            alignment = PriceAlignment.UNRESOLVED
        rows.append(
            PriceUnitRow(
                unit_token=unit_kind,
                unit_kind=unit_kind,
                unit_source=unit_source,
                owner_count=len(owners),
                expectation_count=len(values),
                distribution_count=len(same_unit),
                median_confidence_milli=median_confidence,
                unit_alignment=alignment,
                coverage=(
                    PriceCoverage.PARTIAL
                    if any(
                        row.coverage is PriceCoverage.PARTIAL for row in values
                    )
                    else PriceCoverage.COMPLETE
                ),
            )
        )
    notices: set[str] = set()
    rows.sort(key=lambda row: (row.unit_kind, row.unit_source.value))
    if len(rows) > active.max_units:
        rows = rows[: active.max_units]
        notices.add("price_unit_truncated")
    coverage = PriceCoverage.PARTIAL if notices else PriceCoverage.COMPLETE
    _LOG.debug(
        "price_units_summarized units=%s quotes=%s", len(rows), len(quote_rows)
    )
    return PriceUnitSummary(
        rows=tuple(rows), coverage=coverage, notices=tuple(sorted(notices))
    )
