"""Completed-run bridge for detached accounting analysis."""

from __future__ import annotations

from collections.abc import Sequence

from analysis.accounting_ledgers_analysis import (
    AccountingLedgersAnalysis,
    harvest_accounting_ledgers_analysis,
)
from analysis.accounting_ledgers_contract import (
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
)
from analysis.accounting_ledgers_expectations import AccountingOwnerRowInput
from analysis.accounting_ledgers_policy import AccountingLedgersAnalysisPolicy
from simulation.accounting_ledgers_export import accounting_owner_export

__all__ = [
    "accounting_owner_rows_from_result",
    "build_completed_run_accounting_ledgers_analysis",
]


def accounting_owner_rows_from_result(
    result: object,
) -> tuple[AccountingOwnerRowInput, ...]:
    """Export token-only owner rows from a completed runner result."""

    ledgers = tuple(getattr(result, "accounting_ledgers", ()) or ())
    exported = accounting_owner_export(ledgers)
    return tuple(
        AccountingOwnerRowInput(
            owner_token=row.owner_token,
            entry_token=row.entry_token,
            record_token=row.record_token,
            entry_kind=AccountingEntryKindToken(row.entry_kind),
            direction=AccountingEntryDirection(row.direction),
            item_kind=row.item_kind,
            quantity=row.quantity,
            assessment=AccountingRecordAssessmentToken(row.assessment),
            confidence_milli=row.confidence_milli,
            first_tick=row.first_tick,
            last_tick=row.last_tick,
            window_index=row.window_index,
        )
        for row in exported
    )


def build_completed_run_accounting_ledgers_analysis(
    *,
    run_id: str,
    events: Sequence[object],
    owner_rows: Sequence[AccountingOwnerRowInput] = (),
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingLedgersAnalysis:
    """Build the completed-run analysis without touching scientific status."""

    return harvest_accounting_ledgers_analysis(
        run_id=run_id,
        events=events,
        owner_rows=owner_rows,
        policy=policy,
    )
