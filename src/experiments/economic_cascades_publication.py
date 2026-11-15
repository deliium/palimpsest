"""Programmatic post-completion publication for economic-cascade snapshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.economic_cascades_analysis import EconomicCascadesAnalysis
from analysis.economic_cascades_contract import CascadeCoverage
from simulation.economic_cascades_codec import (
    finalize_economic_cascades_snapshot,
)
from simulation.economic_cascades_models import (
    ECONOMIC_CASCADES_POLICY_VERSION,
    ECONOMIC_CASCADES_SNAPSHOT_VERSION,
    EconomicCascadeChainRecord,
    EconomicCascadeCoverageRecord,
    EconomicCascadeDependencyRecord,
    EconomicCascadeDisruptionRecord,
    EconomicCascadePropagationRecord,
    EconomicCascadesSnapshot,
    EconomicCascadeSummaryRecord,
)
from simulation.economic_cascades_ports import EconomicCascadesPublisher

__all__ = [
    "EconomicCascadesHarvest",
    "EconomicCascadesReceipt",
    "build_economic_cascades_harvest_result",
    "compose_economic_cascades_snapshot",
    "publish_economic_cascades_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_cascades_publication"
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
class EconomicCascadesReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.reason_code not in _REASON_CODES:
            raise ValueError("economic_cascades_receipt_invalid")
        if type(self.stored) is not bool:
            raise ValueError("economic_cascades_receipt_invalid")


@dataclass(frozen=True, slots=True)
class EconomicCascadesHarvest:
    analysis: EconomicCascadesAnalysis
    receipt: EconomicCascadesReceipt


def compose_economic_cascades_snapshot(
    analysis: EconomicCascadesAnalysis,
    *,
    run_id: str,
    generated_from_tick: int | None = None,
) -> EconomicCascadesSnapshot:
    """Map one analysis harvest into the canonical sibling snapshot."""

    if type(analysis) is not EconomicCascadesAnalysis:
        raise TypeError("analysis must be EconomicCascadesAnalysis")
    disruptions = tuple(
        EconomicCascadeDisruptionRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            kind=row.kind.value,
            disruption_count=row.disruption_count,
            magnitude_total=row.magnitude_total,
            subject_count=row.subject_count,
            coverage=row.coverage.value,
        )
        for row in analysis.episodes
    )
    dependencies = tuple(
        EconomicCascadeDependencyRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            upstream_token=row.upstream_token,
            downstream_recipe_token=row.downstream_recipe_id,
            kind=row.kind.value,
            depth=row.depth,
            evidence_count=row.evidence_count,
        )
        for row in analysis.edges
    )
    chains = tuple(
        EconomicCascadeChainRecord(
            chain_token=row.chain_token,
            window_index=row.window_index,
            window_tick=row.window_tick,
            disruption_kind=row.disruption_kind.value,
            depth=row.depth,
            lag_windows=row.lag_windows,
            shortfall_share_milli=row.shortfall_share_milli,
            state=row.state.value,
            coverage=row.coverage.value,
        )
        for row in analysis.chains
    )
    propagation = tuple(
        EconomicCascadePropagationRecord(
            window_index=row.window_index,
            window_tick=row.window_tick,
            disruption_kind=row.disruption_kind.value,
            chain_count=row.chain_count,
            linked_chain_count=row.linked_chain_count,
            unlinked_chain_count=row.unlinked_chain_count,
            unresolved_chain_count=row.unresolved_chain_count,
            mean_depth_milli=row.mean_depth_milli,
            mean_lag_milli=row.mean_lag_milli,
            downstream_stage_count=row.downstream_stage_count,
            coverage=row.coverage.value,
            availability=row.availability.value,
        )
        for row in analysis.propagation_rows
    )
    coverage_row = analysis.coverage_row
    coverage = (
        EconomicCascadeCoverageRecord(
            window_index=coverage_row.window_index,
            window_tick=coverage_row.window_tick,
            window_count=coverage_row.window_count,
            event_count=coverage_row.event_count,
            disruption_count=coverage_row.disruption_count,
            stage_count=coverage_row.stage_count,
            dependency_edge_count=coverage_row.dependency_edge_count,
            labor_join_count=coverage_row.labor_join_count,
            chain_count=coverage_row.chain_count,
            linked_chain_count=coverage_row.linked_chain_count,
            truncated=coverage_row.truncated,
            coverage=coverage_row.coverage.value,
            availability=coverage_row.availability.value,
        ),
    )
    summary = EconomicCascadeSummaryRecord(
        window_tick=analysis.window_tick,
        window_count=analysis.window_count,
        coverage=analysis.coverage.value,
        availability=coverage_row.availability.value,
        event_count=analysis.event_count,
        disruption_count=analysis.disruption_count,
        stage_count=analysis.stage_count,
        dependency_edge_count=analysis.dependency_edge_count,
        chain_count=analysis.chain_count,
        linked_chain_count=analysis.linked_chain_count,
        disruption_kind_count=analysis.disruption_kind_count,
        max_depth=analysis.max_depth,
    )
    return finalize_economic_cascades_snapshot(
        EconomicCascadesSnapshot(
            snapshot_version=ECONOMIC_CASCADES_SNAPSHOT_VERSION,
            policy_version=ECONOMIC_CASCADES_POLICY_VERSION,
            run_id=run_id,
            generated_from_tick=(
                analysis.window_tick
                if generated_from_tick is None
                else generated_from_tick
            ),
            summary=summary,
            disruptions=disruptions,
            dependencies=dependencies,
            chains=chains,
            propagation=propagation,
            coverage=coverage,
        )
    )


def publish_economic_cascades_snapshot(
    *,
    analysis: EconomicCascadesAnalysis,
    run_id: str,
    reader: object | None = None,
    publisher: EconomicCascadesPublisher | None = None,
    enabled: bool = True,
    options: object | None = None,
) -> EconomicCascadesReceipt:
    """Compose and publish programmatically; map every failure to a status."""

    snapshot = compose_economic_cascades_snapshot(analysis, run_id=run_id)
    if analysis.coverage is CascadeCoverage.MISSING:
        return EconomicCascadesReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=False,
            reason_code="publication_missing",
            coverage="missing",
        )
    if not enabled or publisher is None:
        _LOG.warning("economic_cascades_publication_disabled")
        return EconomicCascadesReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
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
            "economic_cascades_published status=%s", code
        )
        return EconomicCascadesReceipt(
            run_id=run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.internal_digest,
            stored=False,
            reason_code=code,
            coverage=snapshot.summary.coverage,
        )
    stored = bool(getattr(receipt, "stored", True))
    _LOG.info("economic_cascades_published status=published stored=%s", stored)
    return EconomicCascadesReceipt(
        run_id=run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.internal_digest,
        stored=stored,
        reason_code="published",
        coverage=snapshot.summary.coverage,
        notices=tuple(getattr(receipt, "notices", ())),
    )


def build_economic_cascades_harvest_result(
    analysis: EconomicCascadesAnalysis,
    publication: EconomicCascadesReceipt,
) -> EconomicCascadesHarvest:
    """Return the analysis plus its publication receipt."""

    if type(publication) is not EconomicCascadesReceipt:
        raise TypeError("publication must be EconomicCascadesReceipt")
    return EconomicCascadesHarvest(analysis=analysis, receipt=publication)
