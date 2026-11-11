"""Programmatic composition and publication of market-institution snapshots."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from analysis import (
    MarketInstitutionsAnalysis,
    MarketInstitutionsAnalysisPolicy,
)
from experiments.market_institutions_completed_run import (
    build_completed_run_market_institutions_analysis,
)
from simulation.market_institutions_codec import (
    finalize_market_institutions_snapshot,
)
from simulation.market_institutions_models import (
    MARKET_INSTITUTIONS_MAX_GATHERINGS,
    MARKET_INSTITUTIONS_MAX_LINEAGE,
    MARKET_INSTITUTIONS_MAX_MARKETS,
    MARKET_INSTITUTIONS_MAX_RECORDS,
    MARKET_INSTITUTIONS_MAX_ROLES,
    MARKET_INSTITUTIONS_MAX_VENUES,
    MarketCandidateRecord,
    MarketExpectationRecord,
    MarketGatheringRecord,
    MarketInstitutionsSnapshot,
    MarketInstitutionsSummaryRecord,
    MarketLineageRecord,
    MarketRecordAnchorRecord,
    MarketRoleRecord,
    MarketVenueRecord,
)
from simulation.market_institutions_ports import MarketInstitutionsPublisher

__all__ = [
    "MarketInstitutionsHarvest",
    "MarketInstitutionsReceipt",
    "build_market_institutions_harvest_result",
    "compose_market_institutions_snapshot",
    "publish_market_institutions_snapshot",
]

_LOG: logging.Logger = logging.getLogger(
    "experiments.market_institutions_publication"
)


@dataclass(frozen=True, slots=True)
class MarketInstitutionsReceipt:
    run_id: str
    publication_id: str
    digest: str
    stored: bool
    reason_code: str
    coverage: str
    notices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MarketInstitutionsHarvest:
    run_id: str
    analysis: MarketInstitutionsAnalysis
    snapshot: MarketInstitutionsSnapshot
    receipt: MarketInstitutionsReceipt


def _venue(analysis: MarketInstitutionsAnalysis) -> tuple[MarketVenueRecord, ...]:
    return tuple(
        MarketVenueRecord(
            venue_id=row.venue_id,
            window_index=row.window_index,
            location_id=row.location_token,
            exchange_count=row.exchange_count,
            proposal_count=row.proposal_count,
            withdrawn_count=row.withdrawn_count,
            distinct_party_count=row.distinct_party_count,
            distinct_actor_count=row.distinct_actor_count,
            active_window_count=row.active_window_count,
            recurrence_milli=row.recurrence_milli,
            status=row.status.value,
            market_like=row.market_like,
            coverage=row.coverage,
        )
        for row in analysis.venues
    )


def _gathering(
    analysis: MarketInstitutionsAnalysis,
) -> tuple[MarketGatheringRecord, ...]:
    return tuple(
        MarketGatheringRecord(
            venue_id=row.venue_id,
            window_index=row.window_index,
            location_id=row.location_token,
            exchange_count=row.exchange_count,
            proposal_count=row.proposal_count,
            withdrawn_count=row.withdrawn_count,
            distinct_party_count=row.distinct_party_count,
            status=row.status.value,
            coverage=row.coverage,
        )
        for row in analysis.gatherings
    )


def _expectation(
    analysis: MarketInstitutionsAnalysis,
) -> tuple[MarketExpectationRecord, ...]:
    return tuple(
        MarketExpectationRecord(
            venue_id=row.venue_id,
            window_index=row.window_index,
            owner_token=row.owner_token,
            expectation=row.expectation,
            cadence=row.cadence,
            interval_ticks=row.interval_ticks,
            phase_tick=row.phase_tick,
            schedule_window_index=row.schedule_window_index,
            confidence_milli=row.confidence_milli,
            evidence_count=row.evidence_count,
            alignment=row.alignment.value,
            coverage=row.coverage,
        )
        for row in analysis.expectations
    )


def _role(analysis: MarketInstitutionsAnalysis) -> tuple[MarketRoleRecord, ...]:
    return tuple(
        MarketRoleRecord(
            venue_id=row.venue_id,
            window_index=row.window_index,
            actor_token=row.actor_token,
            role_kind=row.role_kind,
            role_basis=row.role_basis,
            recognized=row.recognized,
            exchange_count=row.exchange_count,
            counterparty_count=row.counterparty_count,
            active_window_count=row.active_window_count,
            coverage=row.coverage,
        )
        for row in analysis.roles
    )


def _record(
    analysis: MarketInstitutionsAnalysis,
) -> tuple[MarketRecordAnchorRecord, ...]:
    return tuple(
        MarketRecordAnchorRecord(
            venue_id=row.venue_id,
            window_index=row.window_index,
            record_kind=row.record_kind,
            anchor_token=row.anchor_token,
            owner_row_count=row.owner_row_count,
            coverage=row.coverage,
        )
        for row in analysis.records
    )


def _market(analysis: MarketInstitutionsAnalysis) -> tuple[MarketCandidateRecord, ...]:
    return tuple(
        MarketCandidateRecord(
            market_id=row.market_token,
            window_index=row.window_index,
            venue_ids=row.venue_ids,
            exchange_count=row.exchange_count,
            distinct_party_count=row.distinct_party_count,
            coverage=row.coverage,
        )
        for row in analysis.markets
    )


def _lineage(analysis: MarketInstitutionsAnalysis) -> tuple[MarketLineageRecord, ...]:
    return tuple(
        MarketLineageRecord(
            window_index=row.window_index,
            market_id=row.market_token,
            venue_ids=row.venue_ids,
            party_count=row.party_count,
            status=row.status.value,
            previous_market_ids=row.previous_market_tokens,
            next_market_ids=row.next_market_tokens,
            rerouted=row.rerouted,
            sustained=row.sustained,
            coverage=row.coverage,
        )
        for row in analysis.lineage
    )


def _latest_venues(
    rows: Sequence[MarketVenueRecord],
) -> dict[str, MarketVenueRecord]:
    latest: dict[str, MarketVenueRecord] = {}
    for row in rows:
        current = latest.get(row.venue_id)
        if current is None or row.window_index >= current.window_index:
            latest[row.venue_id] = row
    return latest


def _latest_markets(
    rows: Sequence[MarketCandidateRecord],
) -> dict[str, MarketCandidateRecord]:
    latest: dict[str, MarketCandidateRecord] = {}
    for row in rows:
        current = latest.get(row.market_id)
        if current is None or row.window_index >= current.window_index:
            latest[row.market_id] = row
    return latest


def _summary(
    analysis: MarketInstitutionsAnalysis,
    *,
    venues: Sequence[MarketVenueRecord],
    gatherings: Sequence[MarketGatheringRecord],
    expectations: Sequence[MarketExpectationRecord],
    roles: Sequence[MarketRoleRecord],
    records: Sequence[MarketRecordAnchorRecord],
    markets: Sequence[MarketCandidateRecord],
    lineage: Sequence[MarketLineageRecord],
    truncated: bool,
) -> MarketInstitutionsSummaryRecord:
    latest_venues = _latest_venues(venues)
    latest_markets = _latest_markets(markets)
    status_counts = {
        status: sum(1 for row in lineage if row.status == status)
        for status in (
            "emerged",
            "continued",
            "transformed",
            "split",
            "merge",
            "dissolved",
        )
    }
    coverage = analysis.coverage
    return MarketInstitutionsSummaryRecord(
        window_tick=analysis.window_tick,
        venue_count=len({row.venue_id for row in venues}),
        gathering_count=sum(1 for row in gatherings if row.status == "gathering"),
        market_like_venue_count=sum(
            1
            for row in latest_venues.values()
            if row.status == "market_like_persistent"
        ),
        recurring_venue_count=sum(
            1
            for row in latest_venues.values()
            if row.status == "recurring_gathering"
        ),
        expected_venue_count=len(
            {
                row.venue_id
                for row in expectations
                if row.expectation in {"expected", "strong"}
            }
        ),
        market_count=len(latest_markets),
        expectation_row_count=len(expectations),
        role_row_count=len(roles),
        record_anchor_count=len({row.anchor_token for row in records}),
        emerged_count=status_counts["emerged"],
        continued_count=status_counts["continued"],
        transformed_count=status_counts["transformed"],
        split_count=status_counts["split"],
        merge_count=status_counts["merge"],
        dissolved_count=status_counts["dissolved"],
        sustained_market_count=len(
            {row.market_id for row in lineage if row.sustained}
        ),
        lineage_edge_count=len(lineage),
        coverage=coverage,
        truncated=truncated,
    )


def _cap[T](
    rows: tuple[T, ...], limit: int
) -> tuple[tuple[T, ...], bool]:
    if len(rows) <= limit:
        return rows, False
    return rows[:limit], True


def compose_market_institutions_snapshot(
    analysis: MarketInstitutionsAnalysis,
    *,
    run_id: str,
) -> MarketInstitutionsSnapshot:
    """Map one analysis into a canonical, finalized snapshot."""

    if type(analysis) is not MarketInstitutionsAnalysis:
        raise ValueError("market_institutions_analysis_invalid")
    venues, v_trunc = _cap(_venue(analysis), MARKET_INSTITUTIONS_MAX_VENUES)
    gatherings, g_trunc = _cap(
        _gathering(analysis), MARKET_INSTITUTIONS_MAX_GATHERINGS
    )
    expectations, e_trunc = _cap(
        _expectation(analysis), 2_048
    )
    roles, r_trunc = _cap(_role(analysis), MARKET_INSTITUTIONS_MAX_ROLES)
    records, rec_trunc = _cap(_record(analysis), MARKET_INSTITUTIONS_MAX_RECORDS)
    markets, m_trunc = _cap(_market(analysis), MARKET_INSTITUTIONS_MAX_MARKETS)
    lineage, l_trunc = _cap(_lineage(analysis), MARKET_INSTITUTIONS_MAX_LINEAGE)
    truncated = any(
        (v_trunc, g_trunc, e_trunc, r_trunc, rec_trunc, m_trunc, l_trunc)
    )
    summary = _summary(
        analysis,
        venues=venues,
        gatherings=gatherings,
        expectations=expectations,
        roles=roles,
        records=records,
        markets=markets,
        lineage=lineage,
        truncated=truncated,
    )
    snapshot = MarketInstitutionsSnapshot(
        run_id=run_id,
        schema_version="market-institutions-snapshot-v1",
        policy_version="market-institutions.v1",
        summary=summary,
        venues=venues,
        gatherings=gatherings,
        expectations=expectations,
        roles=roles,
        records=records,
        markets=markets,
        lineage=lineage,
    )
    return finalize_market_institutions_snapshot(snapshot)


def build_market_institutions_harvest_result(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    publisher: MarketInstitutionsPublisher | None = None,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> MarketInstitutionsHarvest:
    """Build analysis, snapshot, and receipt for a completed run."""

    analysis = build_completed_run_market_institutions_analysis(
        runner_result,
        committed_events=committed_events,
        run_id=run_id,
        policy=policy,
        input_revision=input_revision,
        window_end=window_end,
    )
    snapshot = compose_market_institutions_snapshot(analysis, run_id=run_id)
    receipt = publish_market_institutions_snapshot(snapshot, publisher)
    return MarketInstitutionsHarvest(
        run_id=run_id, analysis=analysis, snapshot=snapshot, receipt=receipt
    )


def publish_market_institutions_snapshot(
    snapshot: MarketInstitutionsSnapshot | None,
    publisher: MarketInstitutionsPublisher | None,
) -> MarketInstitutionsReceipt:
    """Publish one snapshot if enabled; never raise for a missing analysis."""

    if snapshot is None or snapshot.summary.coverage == "missing":
        _LOG.warning("market_institutions_publication_missing")
        return MarketInstitutionsReceipt(
            run_id="" if snapshot is None else snapshot.run_id,
            publication_id="" if snapshot is None else snapshot.publication_id,
            digest="" if snapshot is None else snapshot.digest,
            stored=False,
            reason_code="market_institutions_publication_missing",
            coverage="missing",
            notices=(),
        )
    if publisher is None:
        return MarketInstitutionsReceipt(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            stored=False,
            reason_code="market_institutions_publication_disabled",
            coverage=snapshot.summary.coverage,
            notices=(),
        )
    publisher.publish(snapshot)
    _LOG.info(
        "market_institutions_publication stored=true coverage=%s",
        snapshot.summary.coverage,
    )
    return MarketInstitutionsReceipt(
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        stored=True,
        reason_code="published",
        coverage=snapshot.summary.coverage,
        notices=(),
    )
