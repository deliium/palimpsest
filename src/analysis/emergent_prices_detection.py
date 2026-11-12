"""Deterministic analytical price distributions and pairwise relations.

Every distribution reports a sample count, five quantiles, IQR, dispersion, and
five bin shares in integer milli. Completed and quoted samples stay separate.
There is no canonical price, score, ranking, severity, or recommendation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.emergent_prices_contract import (
    PRICE_LAYER_FORBIDDEN_PREFIXES,
    EmergentPriceAnalysisError,
    PriceCoverage,
    PriceDistributionStatus,
    PriceLayer,
    PriceRelation,
    PriceSampleSource,
    PriceUnitSource,
    price_distribution_token,
    price_relation_token,
)
from analysis.emergent_prices_policy import (
    EmergentPricesAnalysisPolicy,
    default_emergent_prices_analysis_policy,
)
from analysis.emergent_prices_rows import (
    ExchangePriceEvidenceRow,
    PriceDistributionRow,
    PriceEvidenceHarvest,
    PriceQuoteEvidenceRow,
    PriceRelationRow,
)

__all__ = [
    "assert_price_layer_separation",
    "detect_price_relations",
    "detect_venue_distributions",
    "distribution_summary",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.emergent_prices.detection"
)


def _policy(
    policy: EmergentPricesAnalysisPolicy | None,
) -> EmergentPricesAnalysisPolicy:
    active = (
        default_emergent_prices_analysis_policy() if policy is None else policy
    )
    if type(active) is not EmergentPricesAnalysisPolicy:
        raise EmergentPriceAnalysisError("price_analysis_invalid_policy")
    return active


@dataclass(frozen=True, slots=True)
class _Summary:
    status: PriceDistributionStatus
    sample_count: int
    minimum: int
    p25: int
    median: int
    p75: int
    maximum: int
    iqr: int
    dispersion: int
    bins: tuple[int, int, int, int, int]


def distribution_summary(
    ratios: Sequence[int],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> _Summary:
    """Return nearest-rank quantiles and five bin shares for raw ratios."""

    active = _policy(policy)
    values = sorted(ratios)
    count = len(values)
    if count < active.min_distribution_samples:
        return _Summary(
            status=PriceDistributionStatus.INSUFFICIENT_SAMPLES,
            sample_count=count,
            minimum=0,
            p25=0,
            median=0,
            p75=0,
            maximum=0,
            iqr=0,
            dispersion=0,
            bins=(0, 0, 0, 0, 0),
        )
    minimum = values[0]
    maximum = values[-1]
    p25 = values[(count - 1) // 4]
    median = values[(count - 1) // 2]
    p75 = values[(3 * (count - 1)) // 4]
    iqr = p75 - p25
    dispersion = iqr * 1_000 // max(1, median)
    q20 = values[(count - 1) // 5]
    q40 = values[(2 * (count - 1)) // 5]
    q60 = values[(3 * (count - 1)) // 5]
    q80 = values[(4 * (count - 1)) // 5]
    counts = [0, 0, 0, 0, 0]
    for value in values:
        if value < q20:
            counts[0] += 1
        elif value < q40:
            counts[1] += 1
        elif value < q60:
            counts[2] += 1
        elif value < q80:
            counts[3] += 1
        else:
            counts[4] += 1
    shares = [bucket * 1_000 // count for bucket in counts]
    shares[4] = 1_000 - sum(shares[:4])
    return _Summary(
        status=PriceDistributionStatus.AVAILABLE,
        sample_count=count,
        minimum=minimum,
        p25=p25,
        median=median,
        p75=p75,
        maximum=maximum,
        iqr=iqr,
        dispersion=dispersion,
        bins=(shares[0], shares[1], shares[2], shares[3], shares[4]),
    )


def _paired_exchange(
    evidence: PriceEvidenceHarvest,
) -> dict[tuple[int, str, str, str], list[int]]:
    grouped: dict[tuple[int, str, str, str], list[int]] = defaultdict(list)
    for row in evidence.exchanges:
        if row.pairing.value != "paired" or row.ratio_milli is None:
            continue
        grouped[
            (row.window_index, row.venue_token, row.item_kind, row.unit_kind)
        ].append(row.ratio_milli)
    return grouped


def detect_venue_distributions(
    evidence: PriceEvidenceHarvest,
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> tuple[PriceDistributionRow, ...]:
    """Emit one completed and one quoted distribution per venue/window/pair."""

    active = _policy(policy)
    if type(evidence) is not PriceEvidenceHarvest:
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    completed = _paired_exchange(evidence)
    quoted: dict[tuple[int, str, str, str], list[int]] = defaultdict(list)
    for quote in evidence.quotes:
        if quote.pairing.value != "paired" or quote.ratio_milli is None:
            continue
        quoted[
            (quote.window_index, quote.venue_token, quote.item_kind, quote.unit_kind)
        ].append(quote.ratio_milli)

    rows: list[PriceDistributionRow] = []
    for sample_source, grouped in (
        (PriceSampleSource.COMPLETED, completed),
        (PriceSampleSource.QUOTED, quoted),
    ):
        for key in sorted(grouped):
            window_index, venue_id, item_kind, unit_kind = key
            summary = distribution_summary(grouped[key], policy=active)
            coverage = evidence.coverage
            if venue_id == "none" or coverage is PriceCoverage.PARTIAL:
                coverage = PriceCoverage.PARTIAL
            rows.append(
                PriceDistributionRow(
                    distribution_id=price_distribution_token(
                        venue_id,
                        window_index,
                        item_kind,
                        unit_kind,
                        PriceUnitSource.EXCHANGE_COUNTERPART.value,
                        sample_source.value,
                    ),
                    window_index=window_index,
                    venue_id=venue_id,
                    market_token="none",
                    item_kind=item_kind,
                    unit_kind=unit_kind,
                    unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
                    sample_source=sample_source,
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
                    coverage=coverage,
                )
            )
    rows.sort(
        key=lambda row: (
            row.window_index,
            row.sample_source.value,
            row.venue_id,
            row.item_kind,
            row.unit_kind,
        )
    )
    if len(rows) > active.max_distribution_rows:
        rows = rows[: active.max_distribution_rows]
        rows = [replace(row, coverage=PriceCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "price_distribution_truncated count=%s", active.max_distribution_rows
        )
    return tuple(rows)



def _overlap(left: Sequence[int], right: Sequence[int]) -> int:
    return sum(min(a, b) for a, b in zip(left, right, strict=True))


def detect_price_relations(
    distributions: Sequence[PriceDistributionRow],
    *,
    policy: EmergentPricesAnalysisPolicy | None = None,
) -> tuple[PriceRelationRow, ...]:
    """Compare every ordered group pair for one window and sample source."""

    active = _policy(policy)
    if isinstance(distributions, (str, bytes)) or not isinstance(
        distributions, Sequence
    ):
        raise EmergentPriceAnalysisError("price_analysis_invalid_row")
    grouped: dict[
        tuple[int, str, str, str, str, str], list[PriceDistributionRow]
    ] = defaultdict(list)
    for row in distributions:
        if type(row) is not PriceDistributionRow:
            raise EmergentPriceAnalysisError("price_analysis_invalid_row")
        group_kind = "market" if row.market_token != "none" else "venue"
        grouped[
            (
                row.window_index,
                row.item_kind,
                row.unit_kind,
                row.unit_source.value,
                row.sample_source.value,
                group_kind,
            )
        ].append(row)

    rows: list[PriceRelationRow] = []
    for key in sorted(grouped):
        window_index, item_kind, unit_kind, unit_source, sample_source, group_kind = key
        members = sorted(
            grouped[key],
            key=lambda row: (
                row.market_token if row.market_token != "none" else row.venue_id
            ),
        )
        for index, left in enumerate(members):
            for right in members[index + 1 :]:
                left_token = (
                    left.market_token if left.market_token != "none" else left.venue_id
                )
                right_token = (
                    right.market_token
                    if right.market_token != "none"
                    else right.venue_id
                )
                if left_token == right_token:
                    continue
                group_a, group_b = sorted((left_token, right_token))
                first, second = (
                    (left, right) if left_token < right_token else (right, left)
                )
                overlap = _overlap(
                    first.bin_shares_milli, second.bin_shares_milli
                )
                median_gap = abs(
                    first.median_ratio_milli - second.median_ratio_milli
                ) * 1_000 // max(
                    1, max(first.median_ratio_milli, second.median_ratio_milli)
                )
                if (
                    first.sample_count < active.min_distribution_samples
                    or second.sample_count < active.min_distribution_samples
                    or first.status is PriceDistributionStatus.INSUFFICIENT_SAMPLES
                    or second.status is PriceDistributionStatus.INSUFFICIENT_SAMPLES
                ):
                    relation = PriceRelation.INSUFFICIENT_EVIDENCE
                elif (
                    overlap >= active.convergence_high_milli
                    and median_gap <= active.convergence_low_milli
                ):
                    relation = PriceRelation.CONVERGED
                elif (
                    overlap < active.convergence_low_milli
                    or median_gap >= active.convergence_high_milli
                ):
                    relation = PriceRelation.DIVERGENT
                else:
                    relation = PriceRelation.PARTIALLY_CONVERGED
                coverage = (
                    PriceCoverage.PARTIAL
                    if first.coverage is PriceCoverage.PARTIAL
                    or second.coverage is PriceCoverage.PARTIAL
                    else PriceCoverage.COMPLETE
                )
                rows.append(
                    PriceRelationRow(
                        relation_id=price_relation_token(
                            window_index,
                            group_kind,
                            group_a,
                            group_b,
                            item_kind,
                            unit_kind,
                            unit_source,
                            sample_source,
                        ),
                        window_index=window_index,
                        group_kind=group_kind,
                        group_a_token=group_a,
                        group_b_token=group_b,
                        item_kind=item_kind,
                        unit_kind=unit_kind,
                        unit_source=PriceUnitSource(unit_source),
                        sample_source=PriceSampleSource(sample_source),
                        overlap_milli=overlap,
                        median_gap_milli=median_gap,
                        relation=relation,
                        sample_a=first.sample_count,
                        sample_b=second.sample_count,
                        coverage=coverage,
                    )
                )
    rows.sort(key=lambda row: (row.window_index, row.relation_id))
    if len(rows) > active.max_relation_rows:
        rows = rows[: active.max_relation_rows]
        rows = [replace(row, coverage=PriceCoverage.PARTIAL) for row in rows]
        _LOG.warning(
            "price_relation_truncated count=%s", active.max_relation_rows
        )
    _LOG.debug(
        "price_distributions_computed distributions=%s relations=%s",
        len(distributions),
        len(rows),
    )
    return tuple(rows)


def _infer_layer(row: object) -> PriceLayer:
    if isinstance(row, (ExchangePriceEvidenceRow, PriceQuoteEvidenceRow)):
        return PriceLayer.OBJECTIVE_EXCHANGE
    if isinstance(row, PriceDistributionRow):
        return PriceLayer.ANALYTICAL_DISTRIBUTION
    if isinstance(row, PriceRelationRow):
        return PriceLayer.COMPARISON_VIEW
    return PriceLayer.OWNER_EXPECTATION


def assert_price_layer_separation(
    layers: Mapping[PriceLayer, Sequence[object]] | Sequence[object],
) -> None:
    """Raise on a forbidden field or a cross-layer identity/value leak."""

    entries: list[tuple[PriceLayer, object]] = []
    if isinstance(layers, Mapping):
        for layer, rows in layers.items():
            if type(layer) is not PriceLayer:
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
                raise EmergentPriceAnalysisError("price_analysis_invalid_row")
            entries.extend((layer, row) for row in rows)
    elif isinstance(layers, (str, bytes)) or not isinstance(layers, Sequence):
        raise EmergentPriceAnalysisError("price_analysis_missing_input")
    else:
        for row in layers:
            entries.append((_infer_layer(row), row))

    from analysis.emergent_prices_contract import PRICE_FORBIDDEN_KEYS

    for layer, row in entries:
        fields = getattr(type(row), "__dataclass_fields__", {})
        if set(fields) & PRICE_FORBIDDEN_KEYS:
            raise EmergentPriceAnalysisError("price_analysis_forbidden_key")
        forbidden = PRICE_LAYER_FORBIDDEN_PREFIXES[layer]
        for name in fields:
            if name in forbidden or any(name.startswith(pre) for pre in forbidden):
                raise EmergentPriceAnalysisError("price_analysis_layer_leak")
            value = getattr(row, name)
            values = value if isinstance(value, (tuple, list)) else (value,)
            for item in values:
                if type(item) is not str:
                    continue
                for prefix in forbidden:
                    if prefix.endswith("-") and item.startswith(prefix):
                        raise EmergentPriceAnalysisError(
                            "price_analysis_layer_leak"
                        )
