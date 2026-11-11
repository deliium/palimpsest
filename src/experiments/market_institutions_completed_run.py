"""Completed-run composition of detached market-like institution analysis."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis import (
    MarketInstitutionsAnalysis,
    MarketInstitutionsAnalysisPolicy,
    MarketOwnerExpectationInput,
    MarketOwnerRecordInput,
    MarketOwnerRoleInput,
    harvest_market_institutions_analysis,
)
from simulation.market_institutions_export import (
    market_institution_owner_export,
)

__all__ = ["build_completed_run_market_institutions_analysis"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.market_institutions_completed_run"
)


def build_completed_run_market_institutions_analysis(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    policy: MarketInstitutionsAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> MarketInstitutionsAnalysis:
    """Build one bounded analysis for a completed run."""

    if committed_events is None:
        _LOG.error(
            "market_institutions_completed_run_rejected reason_code=events_required"
        )
        raise ValueError("market_institutions_completed_run_requires_events")
    ledgers = getattr(runner_result, "market_institution_ledgers", ())
    if not ledgers:
        _LOG.warning("market_institutions_completed_run_missing_ledgers")
    rows = market_institution_owner_export(tuple(ledgers))
    expectations: list[MarketOwnerExpectationInput] = []
    roles: list[MarketOwnerRoleInput] = []
    records: list[MarketOwnerRecordInput] = []
    for row in rows:
        if row.family == "expectation":
            expectations.append(
                MarketOwnerExpectationInput(
                    owner_token=row.owner_token,
                    venue_token=row.venue_token,
                    expectation=row.expectation or "none",
                    cadence=row.cadence or "unknown",
                    interval_ticks=row.interval_ticks,
                    phase_tick=row.phase_tick,
                    schedule_window_index=row.schedule_window_index,
                    confidence_milli=row.confidence_milli or 0,
                    evidence_count=row.evidence_count or 0,
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                )
            )
        elif row.family == "role":
            roles.append(
                MarketOwnerRoleInput(
                    owner_token=row.owner_token,
                    venue_token=row.venue_token,
                    role_kind=row.role_kind or "unknown",
                    role_basis=row.role_basis or "claimed",
                    recognized=bool(row.recognized),
                    actor_token=row.actor_token or row.owner_token,
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                )
            )
        else:
            records.append(
                MarketOwnerRecordInput(
                    owner_token=row.owner_token,
                    venue_token=row.venue_token,
                    record_kind=row.record_kind or "unknown",
                    anchor_token=row.anchor_token or "unknown",
                    first_tick=row.first_tick,
                    last_tick=row.last_tick,
                )
            )
    analysis = harvest_market_institutions_analysis(
        committed_events=committed_events,
        expectation_inputs=tuple(expectations),
        role_inputs=tuple(roles),
        record_inputs=tuple(records),
        policy=policy,
        window_end=window_end,
    )
    _LOG.debug(
        "market_institutions_completed_run run_id_present=%s owners=%s events=%s "
        "coverage=%s",
        bool(run_id),
        len(ledgers),
        len(committed_events),
        analysis.coverage.value,
    )
    del input_revision
    return analysis
