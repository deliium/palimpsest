"""Completed-run composition of detached credit relationship analysis."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis import (
    CreditClaimDirection,
    CreditCoverage,
    CreditOwnerInput,
    CreditOwnerLevel,
    CreditOwnerStatus,
    CreditRelationshipsAnalysis,
    CreditRelationshipsAnalysisPolicy,
    harvest_credit_relationships_analysis,
)
from simulation.credit_relationships_export import credit_owner_export

__all__ = ["build_completed_run_credit_relationships_analysis"]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.credit_relationships_completed_run"
)


def build_completed_run_credit_relationships_analysis(
    runner_result: object,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
    input_revision: str = "rev-run",
    window_end: int | None = None,
) -> CreditRelationshipsAnalysis:
    """Build one bounded credit analysis for a completed run."""

    if committed_events is None:
        _LOG.error(
            "credit_relationships_completed_run_rejected "
            "reason_code=events_required"
        )
        raise ValueError("credit_relationships_analysis_missing_events")
    ledgers = getattr(runner_result, "credit_relationship_ledgers", ())
    if not ledgers:
        _LOG.warning("credit_completed_run_missing_ledgers")
    rows = credit_owner_export(tuple(ledgers))
    owner_inputs = tuple(
        CreditOwnerInput(
            owner_token=row.owner_token,
            window_index=row.window_index,
            anchor_token=row.anchor_token,
            counterparty_token=row.counterparty_token,
            direction=CreditClaimDirection(row.direction),
            principal_kind=row.principal_kind_token,
            principal_quantity=row.principal_quantity,
            repayment_kind=row.repayment_kind_token,
            repayment_quantity=row.repayment_quantity,
            paid_quantity=row.paid_quantity,
            due_tick=row.due_tick,
            condition=row.condition,
            collateral_kind=row.collateral_kind,
            collateral_quantity=row.collateral_quantity,
            status=CreditOwnerStatus(row.status),
            confidence_milli=row.confidence_milli,
            level=CreditOwnerLevel(row.level),
            trust_milli=row.trust_milli,
            expectation_milli=row.expectation_milli,
            claim_count=row.claim_count,
            promise_count=row.promise_count,
            renegotiate_count=row.renegotiate_count,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            coverage=CreditCoverage(row.coverage),
        )
        for row in rows
    )
    analysis = harvest_credit_relationships_analysis(
        committed_events=committed_events,
        owner_inputs=owner_inputs,
        policy=policy,
        window_end=window_end,
    )
    _LOG.debug(
        "credit_completed_run owners=%s events=%s coverage=%s",
        len(ledgers),
        len(committed_events),
        analysis.coverage.value,
    )
    del run_id, input_revision
    return analysis
