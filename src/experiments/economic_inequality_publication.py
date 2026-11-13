"""Programmatic post-completion publication for inequality snapshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.economic_inequality_analysis import EconomicInequalityAnalysis
from analysis.economic_inequality_contract import EconomicInequalityCoverage
from simulation.economic_inequality_codec import (
    finalize_economic_inequality_snapshot,
)
from simulation.economic_inequality_models import (
    ECONOMIC_INEQUALITY_POLICY_VERSION,
    ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
    EconomicCohortRecord,
    EconomicDimensionRecord,
    EconomicInequalitySnapshot,
    EconomicInequalitySummaryRecord,
    EconomicSocietyRecord,
)
from simulation.economic_inequality_ports import EconomicInequalityPublisher

__all__ = [
    "EconomicInequalityHarvest",
    "EconomicInequalityReceipt",
    "build_economic_inequality_harvest_result",
    "compose_economic_inequality_snapshot",
    "publish_economic_inequality_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_inequality_publication"
)

_REASON_CODES: Final[frozenset[str]] = frozenset(
    {
        "published",
        "publication_disabled",
        "publication_missing",
        "store_quota_exceeded",
        "store_corrupt",
    }
)


@dataclass(frozen=True, slots=True)
class EconomicInequalityReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _REASON_CODES:
            raise ValueError("economic_inequality_receipt_invalid")
        if type(self.stored) is not bool:
            raise ValueError("economic_inequality_receipt_invalid")


@dataclass(frozen=True, slots=True)
class EconomicInequalityHarvest:
    run_id: str
    analysis: EconomicInequalityAnalysis
    snapshot: EconomicInequalitySnapshot
    receipt: EconomicInequalityReceipt


def compose_economic_inequality_snapshot(
    analysis: EconomicInequalityAnalysis, *, run_id: str
) -> EconomicInequalitySnapshot:
    """Map one analysis harvest into the canonical sibling snapshot."""

    if type(analysis) is not EconomicInequalityAnalysis:
        raise TypeError("analysis must be EconomicInequalityAnalysis")
    dimensions = tuple(
        EconomicDimensionRecord(
            dimension=row.dimension.value,
            measure=row.measure.value,
            window_index=row.window_index,
            window_tick=row.window_tick,
            owner_count=row.owner_count,
            observed_owner_count=row.observed_owner_count,
            minimum=row.minimum,
            p25=row.p25,
            median=row.median,
            p75=row.p75,
            maximum=row.maximum,
            iqr=row.iqr,
            dispersion=row.dispersion,
            bin_shares_milli=row.bin_shares_milli,
            gini_milli=row.gini_milli,
            theil_t_milli=row.theil_t_milli,
            atkinson_eps_1_milli=row.atkinson_eps_1_milli,
            top_share_milli=row.top_share_milli,
            availability=row.availability.value,
            coverage=row.coverage.value,
        )
        for row in analysis.dimension_rows
    )
    cohorts = tuple(
        EconomicCohortRecord(
            cohort_token=row.cohort_token,
            generation_index=row.generation_index,
            window_index=row.window_index,
            owner_count=row.owner_count,
            comparable=row.comparable,
            gini_milli=row.gini_milli,
            median_milli=row.median_milli,
            iqr_milli=row.iqr_milli,
            trend=row.trend.value,
            availability=row.availability.value,
        )
        for row in analysis.cohort_rows
    )
    societies = tuple(
        EconomicSocietyRecord(
            society_token=row.society_token,
            window_index=row.window_index,
            owner_count=row.owner_count,
            comparable=row.comparable,
            gini_milli=row.gini_milli,
            median_milli=row.median_milli,
            iqr_milli=row.iqr_milli,
            trend=row.trend.value,
            availability=row.availability.value,
        )
        for row in analysis.society_rows
    )
    truncated = (
        analysis.coverage is EconomicInequalityCoverage.PARTIAL
        or any("truncated" in notice for notice in analysis.notices)
    )
    summary = EconomicInequalitySummaryRecord(
        dimension_row_count=len(dimensions),
        cohort_row_count=len(cohorts),
        society_row_count=len(societies),
        window_count=analysis.window_count,
        owner_count=analysis.owner_count,
        observed_owner_count=analysis.observed_owner_count,
        overlap_member_count=analysis.overlap_member_count,
        coverage=analysis.coverage.value,
        evidence_coverage=analysis.evidence_coverage.value,
        dimension_coverage=analysis.dimension_coverage.value,
        comparison_coverage=analysis.comparison_coverage.value,
        truncated=truncated,
    )
    return finalize_economic_inequality_snapshot(
        EconomicInequalitySnapshot(
            run_id=run_id,
            schema_version=ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
            policy_version=ECONOMIC_INEQUALITY_POLICY_VERSION,
            summary=summary,
            dimensions=dimensions,
            cohorts=cohorts,
            societies=societies,
        )
    )


def publish_economic_inequality_snapshot(
    snapshot: EconomicInequalitySnapshot,
    publisher: EconomicInequalityPublisher | None,
) -> EconomicInequalityReceipt:
    """Publish programmatically; map disabled/missing/quota/corruption."""

    if type(snapshot) is not EconomicInequalitySnapshot:
        raise TypeError("snapshot must be EconomicInequalitySnapshot")
    if snapshot.summary.coverage == EconomicInequalityCoverage.MISSING.value:
        return EconomicInequalityReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_missing",
            coverage="missing",
        )
    if publisher is None:
        return EconomicInequalityReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_disabled",
            coverage=snapshot.summary.coverage,
        )
    try:
        receipt = publisher.publish(snapshot)
    except ValueError as error:
        message = str(error)
        code = (
            "store_quota_exceeded" if "quota" in message else "store_corrupt"
        )
        _LOG.warning(
            "economic_inequality_published stored=%s reason=%s", False, code
        )
        return EconomicInequalityReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code=code,
            coverage=snapshot.summary.coverage,
        )
    stored = bool(getattr(receipt, "stored", True))
    _LOG.info(
        "economic_inequality_published stored=%s rows=%d",
        stored,
        snapshot.summary.dimension_row_count
        + snapshot.summary.cohort_row_count
        + snapshot.summary.society_row_count,
    )
    return EconomicInequalityReceipt(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        stored=stored,
        reason_code="published",
        coverage=snapshot.summary.coverage,
        notices=tuple(getattr(receipt, "notices", ())),
    )


def build_economic_inequality_harvest_result(
    analysis: EconomicInequalityAnalysis,
    *,
    run_id: str,
    publisher: EconomicInequalityPublisher | None,
) -> EconomicInequalityHarvest:
    """Compose and publish one completed-run harvest programmatically."""

    snapshot = compose_economic_inequality_snapshot(analysis, run_id=run_id)
    receipt = publish_economic_inequality_snapshot(snapshot, publisher)
    return EconomicInequalityHarvest(
        run_id=run_id,
        analysis=analysis,
        snapshot=snapshot,
        receipt=receipt,
    )
