"""Compose and programmatically publish completed-run price snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis import (
    EmergentPricesAnalysis,
    EmergentPricesAnalysisPolicy,
)
from simulation.emergent_prices_codec import finalize_emergent_prices_snapshot
from simulation.emergent_prices_models import (
    EMERGENT_PRICES_MAX_DISTRIBUTIONS,
    EMERGENT_PRICES_MAX_EXPECTATIONS,
    EMERGENT_PRICES_MAX_MARKETS,
    EMERGENT_PRICES_MAX_QUOTES,
    EMERGENT_PRICES_MAX_RELATIONS,
    EMERGENT_PRICES_MAX_UNITS,
    EMERGENT_PRICES_SNAPSHOT_POLICY,
    EMERGENT_PRICES_SNAPSHOT_VERSION,
    EmergentPricesSnapshot,
    EmergentPricesSummaryRecord,
    PriceDistributionRecord,
    PriceExpectationRecord,
    PriceMarketRecord,
    PriceQuoteRecord,
    PriceRelationRecord,
    PriceUnitRecord,
)
from simulation.emergent_prices_ports import (
    EmergentPricesPublisher,
    EmergentPricesReader,
)

__all__ = [
    "EmergentPricesHarvest",
    "EmergentPricesReceipt",
    "build_emergent_prices_harvest_result",
    "compose_emergent_prices_snapshot",
    "publish_emergent_prices_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.emergent_prices_publication"
)

_RECEIPT_CODES: Final[frozenset[str]] = frozenset(
    {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }
)


@dataclass(frozen=True, slots=True)
class EmergentPricesReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _RECEIPT_CODES:
            raise ValueError("emergent_prices_invalid_receipt")


@dataclass(frozen=True, slots=True)
class EmergentPricesHarvest:
    run_id: str
    analysis: EmergentPricesAnalysis
    snapshot: EmergentPricesSnapshot
    receipt: EmergentPricesReceipt


def _latest(rows: Sequence[Any], cap: int) -> tuple[Any, ...]:
    ordered = sorted(
        rows,
        key=lambda row: (
            getattr(row, "window_index", 0),
            getattr(row, "distribution_id", ""),
            getattr(row, "expectation_id", ""),
            getattr(row, "quote_id", ""),
            getattr(row, "market_token", ""),
            getattr(row, "relation_id", ""),
            getattr(row, "unit_token", ""),
        ),
    )
    return tuple(ordered[:cap])


def compose_emergent_prices_snapshot(
    analysis: EmergentPricesAnalysis, *, run_id: str
) -> EmergentPricesSnapshot:
    """Map one analysis into the canonical snapshot and finalize it."""

    if type(analysis) is not EmergentPricesAnalysis:
        raise ValueError("emergent_prices_invalid_analysis")
    units = _latest(analysis.units, EMERGENT_PRICES_MAX_UNITS)
    expectations = _latest(analysis.expectations, EMERGENT_PRICES_MAX_EXPECTATIONS)
    quotes = _latest(analysis.quotes, EMERGENT_PRICES_MAX_QUOTES)
    distributions = _latest(
        analysis.distributions, EMERGENT_PRICES_MAX_DISTRIBUTIONS
    )
    markets = _latest(analysis.markets, EMERGENT_PRICES_MAX_MARKETS)
    relations = _latest(analysis.relations, EMERGENT_PRICES_MAX_RELATIONS)
    truncated = (
        len(units) < len(analysis.units)
        or len(expectations) < len(analysis.expectations)
        or len(quotes) < len(analysis.quotes)
        or len(distributions) < len(analysis.distributions)
        or len(markets) < len(analysis.markets)
        or len(relations) < len(analysis.relations)
    )
    window_indices: list[int] = []
    window_indices.extend(row.window_index for row in analysis.expectations)
    window_indices.extend(row.window_index for row in analysis.quotes)
    window_indices.extend(row.window_index for row in analysis.distributions)
    window_indices.extend(row.window_index for row in analysis.markets)
    window_indices.extend(row.window_index for row in analysis.relations)
    window_count = 0 if not window_indices else max(window_indices) + 1
    summary = EmergentPricesSummaryRecord(
        window_tick=analysis.window_tick,
        window_count=window_count,
        unit_count=len(analysis.units),
        expectation_count=len(analysis.expectations),
        quote_count=len(analysis.quotes),
        distribution_count=len(analysis.distributions),
        market_count=len(analysis.markets),
        relation_count=len(analysis.relations),
        exchange_count=analysis.exchange_count,
        quote_event_count=analysis.quote_count,
        evidence_coverage=analysis.evidence_coverage.value,
        expectation_coverage=analysis.expectation_coverage.value,
        quote_coverage=analysis.quote_coverage.value,
        distribution_coverage=analysis.distribution_coverage.value,
        market_coverage=analysis.market_coverage.value,
        relation_coverage=analysis.relation_coverage.value,
        coverage=analysis.coverage.value,
        truncated=truncated,
    )
    snapshot = EmergentPricesSnapshot(
        run_id=run_id,
        schema_version=EMERGENT_PRICES_SNAPSHOT_VERSION,
        policy_version=EMERGENT_PRICES_SNAPSHOT_POLICY,
        summary=summary,
        units=tuple(
            PriceUnitRecord(
                unit_token=row.unit_token,
                unit_source=row.unit_source.value,
                owner_count=row.owner_count,
                expectation_count=row.expectation_count,
                distribution_count=row.distribution_count,
                median_confidence_milli=row.median_confidence_milli,
                unit_alignment=row.unit_alignment.value,
                coverage=row.coverage.value,
            )
            for row in units
        ),
        expectations=tuple(
            PriceExpectationRecord(
                expectation_id=row.expectation_id,
                window_index=row.window_index,
                owner_token=row.owner_token,
                item_kind=row.item_kind,
                unit_kind=row.unit_kind,
                unit_source=row.unit_source.value,
                expected_ratio_milli=row.expected_ratio_milli,
                confidence_milli=row.confidence_milli,
                level=row.level,
                valuation_reservation=row.valuation_reservation,
                observation_count=row.observation_count,
                quote_count=row.quote_count,
                distribution_source=row.distribution_source,
                alignment=row.alignment.value,
                coverage=row.coverage.value,
            )
            for row in expectations
        ),
        quotes=tuple(
            PriceQuoteRecord(
                quote_id=row.quote_id,
                window_index=row.window_index,
                venue_id=row.venue_id,
                actor_token=row.actor_token,
                counterparty_token=row.counterparty_token,
                item_kind=row.item_kind,
                unit_kind=row.unit_kind,
                direction=row.direction.value,
                ratio_milli=row.ratio_milli,
                confidence_milli=row.confidence_milli,
                source=row.source.value,
                source_tick=row.source_tick,
                coverage=row.coverage.value,
            )
            for row in quotes
        ),
        distributions=tuple(
            PriceDistributionRecord(
                distribution_id=row.distribution_id,
                window_index=row.window_index,
                venue_id=row.venue_id,
                market_token=row.market_token,
                item_kind=row.item_kind,
                unit_kind=row.unit_kind,
                unit_source=row.unit_source.value,
                sample_source=row.sample_source.value,
                sample_count=row.sample_count,
                min_ratio_milli=row.min_ratio_milli,
                p25_ratio_milli=row.p25_ratio_milli,
                median_ratio_milli=row.median_ratio_milli,
                p75_ratio_milli=row.p75_ratio_milli,
                max_ratio_milli=row.max_ratio_milli,
                iqr_milli=row.iqr_milli,
                dispersion_milli=row.dispersion_milli,
                bin_shares_milli=row.bin_shares_milli,
                status=row.status.value,
                coverage=row.coverage.value,
            )
            for row in distributions
        ),
        markets=tuple(
            PriceMarketRecord(
                market_token=row.market_token,
                window_index=row.window_index,
                venue_count=row.venue_count,
                distribution_count=row.distribution_count,
                sample_count=row.sample_count,
                item_kind_count=row.item_kind_count,
                unit_count=row.unit_count,
                coverage=row.coverage.value,
            )
            for row in markets
        ),
        relations=tuple(
            PriceRelationRecord(
                relation_id=row.relation_id,
                window_index=row.window_index,
                group_kind=row.group_kind,
                group_a_token=row.group_a_token,
                group_b_token=row.group_b_token,
                item_kind=row.item_kind,
                unit_kind=row.unit_kind,
                unit_source=row.unit_source.value,
                sample_source=row.sample_source.value,
                overlap_milli=row.overlap_milli,
                median_gap_milli=row.median_gap_milli,
                relation=row.relation.value,
                sample_a=row.sample_a,
                sample_b=row.sample_b,
                coverage=row.coverage.value,
            )
            for row in relations
        ),
    )
    return finalize_emergent_prices_snapshot(snapshot)


def publish_emergent_prices_snapshot(
    snapshot: EmergentPricesSnapshot,
    publisher: EmergentPricesPublisher | EmergentPricesReader | None,
) -> EmergentPricesReceipt:
    """Publish one snapshot; disabled and missing publication never raise."""

    coverage = snapshot.summary.coverage
    if coverage == "missing":
        return EmergentPricesReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_missing",
            coverage=coverage,
        )
    if publisher is None:
        return EmergentPricesReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=coverage,
        )
    publish = getattr(publisher, "publish", None)
    if publish is None:
        return EmergentPricesReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=coverage,
        )
    try:
        publication = publish(snapshot)
    except ValueError as exc:
        code = str(exc)
        reason = (
            "store_quota_exceeded"
            if "quota" in code
            else "store_corrupt" if "corrupt" in code else "publication_missing"
        )
        _LOG.warning("price_snapshot_partial coverage=%s", coverage)
        return EmergentPricesReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code=reason,
            coverage=coverage,
        )
    _LOG.info(
        "emergent_prices_publication_completed stored=%s reason_code=published",
        True,
    )
    return EmergentPricesReceipt(
        run_id=snapshot.run_id,
        publication_id=publication.publication_id,
        digest=publication.digest,
        stored=True,
        reason_code="published",
        coverage=coverage,
    )


def build_emergent_prices_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    publisher: EmergentPricesPublisher | None = None,
    policy: EmergentPricesAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> EmergentPricesHarvest:
    """Build analysis, snapshot, and receipt for one completed run."""

    from experiments.emergent_prices_completed_run import (
        build_completed_run_emergent_prices_analysis,
    )

    analysis = build_completed_run_emergent_prices_analysis(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        policy=policy,
        input_revision=input_revision,
        window_end=window_end,
    )
    snapshot = compose_emergent_prices_snapshot(analysis, run_id=run_id)
    receipt = publish_emergent_prices_snapshot(snapshot, publisher)
    return EmergentPricesHarvest(
        run_id=run_id, analysis=analysis, snapshot=snapshot, receipt=receipt
    )
