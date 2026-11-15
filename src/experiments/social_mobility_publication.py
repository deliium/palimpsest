"""Programmatic post-completion publication for social-mobility snapshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.social_mobility_analysis import SocialMobilityAnalysis
from analysis.social_mobility_contract import SocialMobilityCoverage
from simulation.social_mobility_codec import finalize_social_mobility_snapshot
from simulation.social_mobility_models import (
    SOCIAL_MOBILITY_POLICY_VERSION,
    SOCIAL_MOBILITY_SNAPSHOT_VERSION,
    SocialMobilityCoverageRecord,
    SocialMobilityDomainRecord,
    SocialMobilityGenerationRecord,
    SocialMobilityLagRecord,
    SocialMobilitySnapshot,
    SocialMobilitySummaryRecord,
)
from simulation.social_mobility_ports import SocialMobilityPublisher

__all__ = [
    "SocialMobilityHarvest",
    "SocialMobilityReceipt",
    "build_social_mobility_harvest_result",
    "compose_social_mobility_snapshot",
    "publish_social_mobility_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.social_mobility_publication"
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
class SocialMobilityReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _REASON_CODES:
            raise ValueError("social_mobility_receipt_invalid")
        if type(self.stored) is not bool:
            raise ValueError("social_mobility_receipt_invalid")


@dataclass(frozen=True, slots=True)
class SocialMobilityHarvest:
    run_id: str
    analysis: SocialMobilityAnalysis
    snapshot: SocialMobilitySnapshot
    receipt: SocialMobilityReceipt


def compose_social_mobility_snapshot(
    analysis: SocialMobilityAnalysis, *, run_id: str
) -> SocialMobilitySnapshot:
    """Map one analysis harvest into the canonical sibling snapshot."""

    if type(analysis) is not SocialMobilityAnalysis:
        raise TypeError("analysis must be SocialMobilityAnalysis")
    domains = tuple(
        SocialMobilityDomainRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            domain=row.domain.value,
            measure=row.measure.value,
            pair_count=row.pair_count,
            resolved_pair_count=row.resolved_pair_count,
            rank_correlation_milli=row.rank_correlation_milli,
            same_bin_share_milli=row.same_bin_share_milli,
            upward_share_milli=row.upward_share_milli,
            downward_share_milli=row.downward_share_milli,
            mean_absolute_rank_change_milli=(row.mean_absolute_rank_change_milli),
            persistence_direction=row.persistence_direction.value,
            coverage=row.coverage.value,
            availability=row.availability.value,
        )
        for row in analysis.domain_rows
    )
    generations = tuple(
        SocialMobilityGenerationRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            generation_index=row.generation_index,
            owner_count=row.owner_count,
            pair_count=row.pair_count,
            comparable=row.comparable,
            same_bin_share_milli=row.same_bin_share_milli,
            upward_share_milli=row.upward_share_milli,
            downward_share_milli=row.downward_share_milli,
            coverage=row.coverage.value,
            availability=row.availability.value,
        )
        for row in analysis.generation_rows
    )
    lags = tuple(
        SocialMobilityLagRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            generation_lag=row.generation_lag,
            pair_count=row.pair_count,
            comparable=row.comparable,
            same_bin_share_milli=row.same_bin_share_milli,
            upward_share_milli=row.upward_share_milli,
            downward_share_milli=row.downward_share_milli,
            coverage=row.coverage.value,
            availability=row.availability.value,
        )
        for row in analysis.lag_rows
    )
    coverage = (
        ()
        if analysis.coverage_row is None
        else (
            SocialMobilityCoverageRecord(
                window_index=analysis.coverage_row.window_index,
                window_tick=analysis.coverage_row.window_tick,
                generation_count=analysis.coverage_row.generation_count,
                owner_count=analysis.coverage_row.owner_count,
                genealogy_edge_count=analysis.coverage_row.genealogy_edge_count,
                pair_count=analysis.coverage_row.pair_count,
                resolved_pair_count=analysis.coverage_row.resolved_pair_count,
                unresolved_pair_count=analysis.coverage_row.unresolved_pair_count,
                domain_available_count=analysis.coverage_row.domain_available_count,
                truncated=analysis.coverage_row.truncated,
                coverage=analysis.coverage_row.coverage.value,
            ),
        )
    )
    truncated = analysis.coverage is SocialMobilityCoverage.PARTIAL or any(
        "truncated" in notice for notice in analysis.notices
    )
    summary = SocialMobilitySummaryRecord(
        domain_row_count=len(domains),
        generation_row_count=len(generations),
        lag_row_count=len(lags),
        window_count=analysis.window_count,
        owner_count=analysis.owner_count,
        generation_count=analysis.generation_count,
        genealogy_edge_count=analysis.genealogy_edge_count,
        pair_count=analysis.pair_count,
        resolved_pair_count=analysis.resolved_pair_count,
        unresolved_pair_count=analysis.unresolved_pair_count,
        domain_available_count=analysis.domain_available_count,
        coverage=analysis.coverage.value,
        evidence_coverage=analysis.evidence_coverage.value,
        domain_coverage=analysis.domain_coverage.value,
        generation_coverage=analysis.generation_coverage.value,
        truncated=truncated,
    )
    return finalize_social_mobility_snapshot(
        SocialMobilitySnapshot(
            run_id=run_id,
            schema_version=SOCIAL_MOBILITY_SNAPSHOT_VERSION,
            policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
            summary=summary,
            domains=domains,
            generations=generations,
            lags=lags,
            coverage=coverage,
        )
    )


def publish_social_mobility_snapshot(
    snapshot: SocialMobilitySnapshot,
    publisher: SocialMobilityPublisher | None,
) -> SocialMobilityReceipt:
    """Publish programmatically; map disabled/missing/quota/corruption."""

    if type(snapshot) is not SocialMobilitySnapshot:
        raise TypeError("snapshot must be SocialMobilitySnapshot")
    if snapshot.summary.coverage == SocialMobilityCoverage.MISSING.value:
        return SocialMobilityReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="publication_missing",
            coverage="missing",
        )
    if publisher is None:
        return SocialMobilityReceipt(
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
        code = "store_quota_exceeded" if "quota" in message else "store_corrupt"
        _LOG.warning("social_mobility_published stored=%s reason=%s", False, code)
        return SocialMobilityReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code=code,
            coverage=snapshot.summary.coverage,
        )
    stored = bool(getattr(receipt, "stored", True))
    _LOG.info(
        "social_mobility_published stored=%s rows=%d",
        stored,
        snapshot.summary.domain_row_count
        + snapshot.summary.generation_row_count
        + snapshot.summary.lag_row_count,
    )
    return SocialMobilityReceipt(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        stored=stored,
        reason_code="published",
        coverage=snapshot.summary.coverage,
        notices=tuple(getattr(receipt, "notices", ())),
    )


def build_social_mobility_harvest_result(
    analysis: SocialMobilityAnalysis,
    *,
    run_id: str,
    publisher: SocialMobilityPublisher | None,
) -> SocialMobilityHarvest:
    """Compose and publish one completed-run harvest programmatically."""

    snapshot = compose_social_mobility_snapshot(analysis, run_id=run_id)
    receipt = publish_social_mobility_snapshot(snapshot, publisher)
    return SocialMobilityHarvest(
        run_id=run_id,
        analysis=analysis,
        snapshot=snapshot,
        receipt=receipt,
    )
