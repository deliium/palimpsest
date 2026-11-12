"""Descriptive accounting detection from detached evidence only.

No wealth, rank, audit, or truth finding exists. Every output is a count,
integer claim sum, or milli share.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Final

from analysis.accounting_ledgers_contract import (
    AccountingAnalysisError,
    AccountingDistributionStatus,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    accounting_entry_row_token,
    assert_accounting_layer_separation,
)
from analysis.accounting_ledgers_policy import (
    AccountingLedgersAnalysisPolicy,
    default_accounting_ledgers_analysis_policy,
    window_index_for_tick,
)
from analysis.accounting_ledgers_rows import (
    AccountingClaimEvidenceRow,
    AccountingContributionEvidenceRow,
    AccountingCounterpartyRow,
    AccountingDistributionSummary,
    AccountingEvidenceHarvest,
    AccountingFlowRow,
    AccountingRecordConditionRow,
    AccountingTransferEvidenceRow,
    AnalyticalAccountingEntryRow,
)

__all__ = [
    "accounting_distribution_summary",
    "detect_accounting_counterparties",
    "detect_accounting_entries",
    "detect_accounting_flows",
    "detect_record_conditions",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.detection"
)


def _policy(value: object) -> AccountingLedgersAnalysisPolicy:
    if value is None:
        return default_accounting_ledgers_analysis_policy()
    if type(value) is not AccountingLedgersAnalysisPolicy:
        raise AccountingAnalysisError("accounting_analysis_invalid_policy")
    return value


def detect_accounting_entries(
    harvest: AccountingEvidenceHarvest,
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> tuple[AnalyticalAccountingEntryRow, ...]:
    """Merge committed claims into descriptive analytical entries."""

    if type(harvest) is not AccountingEvidenceHarvest:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    active = _policy(policy)
    grouped: dict[
        tuple[str, str, str, str, int],
        list[AccountingClaimEvidenceRow],
    ] = defaultdict(list)
    for claim in harvest.claims:
        window = window_index_for_tick(claim.tick, active)
        grouped[
            (
                claim.record_token,
                claim.entry_kind.value,
                claim.direction.value,
                claim.item_kind,
                window,
            )
        ].append(claim)
    entries: list[AnalyticalAccountingEntryRow] = []
    for (record_token, kind, direction, item_kind, window), rows in sorted(
        grouped.items()
    ):
        quantity = min(
            active.max_quantity,
            sum(row.quantity for row in rows),
        )
        confidence = max(row.confidence_milli for row in rows)
        assessment = max(
            (row.assessment for row in rows),
            key=lambda value: _assessment_rank(value),
        )
        first_tick = min(row.tick for row in rows)
        last_tick = max(row.tick for row in rows)
        entries.append(
            AnalyticalAccountingEntryRow(
                entry_token=accounting_entry_row_token(
                    f"{record_token}|{kind}|{direction}|{item_kind}",
                    window,
                ),
                record_token=record_token,
                entry_kind=AccountingEntryKindToken(kind),
                direction=AccountingEntryDirection(direction),
                item_kind=item_kind,
                quantity=quantity,
                assessment=assessment,
                confidence_milli=confidence,
                first_tick=first_tick,
                last_tick=last_tick,
                window_index=window,
            )
        )
    entries.sort(key=lambda row: (row.window_index, row.entry_token))
    if len(entries) > active.max_entry_rows:
        entries = entries[: active.max_entry_rows]
    assert_accounting_layer_separation(*entries)
    _LOG.debug("accounting_ledger_detected entries=%s", len(entries))
    return tuple(entries)


def _assessment_rank(value: AccountingRecordAssessmentToken) -> int:
    order = {
        AccountingRecordAssessmentToken.UNASSESSED: 0,
        AccountingRecordAssessmentToken.CONSISTENT: 1,
        AccountingRecordAssessmentToken.SUSPECTED_FRAUDULENT: 2,
        AccountingRecordAssessmentToken.CONTRADICTED: 3,
        AccountingRecordAssessmentToken.OUTDATED: 4,
        AccountingRecordAssessmentToken.DAMAGED: 5,
    }
    return order[value]


def detect_record_conditions(
    entries: Sequence[AnalyticalAccountingEntryRow],
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> tuple[AccountingRecordConditionRow, ...]:
    """Count entries by owner appraisal and window. Never adjudicate truth."""

    active = _policy(policy)
    groups: dict[tuple[str, int], list[AnalyticalAccountingEntryRow]] = defaultdict(
        list
    )
    for entry in entries:
        if type(entry) is not AnalyticalAccountingEntryRow:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        groups[(entry.assessment.value, entry.window_index)].append(entry)
    window_totals: dict[int, int] = defaultdict(int)
    for entry in entries:
        window_totals[entry.window_index] += 1
    rows: list[AccountingRecordConditionRow] = []
    for (condition, window), group in sorted(groups.items()):
        histogram = Counter(entry.quantity for entry in group)
        total = sum(histogram.values())
        window_total = window_totals[window]
        rows.append(
            AccountingRecordConditionRow(
                condition=condition,
                record_count=total,
                quantity_histogram=tuple(sorted(histogram.items())),
                share_milli=(
                    0 if window_total == 0 else total * 1_000 // window_total
                ),
                window_index=window,
                availability=(
                    "insufficient_samples"
                    if window_total < active.min_distribution_samples
                    else "available"
                ),
            )
        )
    rows.sort(key=lambda row: (row.window_index, row.condition))
    if len(rows) > active.max_condition_rows:
        rows = rows[: active.max_condition_rows]
    assert_accounting_layer_separation(*rows)
    _LOG.debug("[FIX] accounting_condition_shares rows=%s", len(rows))
    return tuple(rows)


def detect_accounting_flows(
    entries: Sequence[AnalyticalAccountingEntryRow],
    transfers: Sequence[AccountingTransferEvidenceRow] = (),
    contributions: Sequence[AccountingContributionEvidenceRow] = (),
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> tuple[AccountingFlowRow, ...]:
    """Descriptive per-window claim sums. Never a wealth or worth claim."""

    active = _policy(policy)
    windows: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    owners: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    counterparties: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for entry in entries:
        if type(entry) is not AnalyticalAccountingEntryRow:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        key = (entry.entry_kind.value, entry.direction.value, entry.window_index)
        windows[key].append(entry.quantity)
    for transfer in transfers:
        if type(transfer) is not AccountingTransferEvidenceRow:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        window = window_index_for_tick(transfer.tick, active)
        kind = (
            transfer.item_kind
            if transfer.item_kind
            in {member.value for member in AccountingEntryKindToken}
            else "exchange"
        )
        key = (kind, AccountingEntryDirection.INFLOW.value, window)
        windows[key].append(transfer.quantity)
        owners[key].add(transfer.receiver_token)
        counterparties[key].add(transfer.giver_token)
    for contribution in contributions:
        if type(contribution) is not AccountingContributionEvidenceRow:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        window = window_index_for_tick(contribution.tick, active)
        key = (
            AccountingEntryKindToken.CONTRIBUTION.value,
            AccountingEntryDirection.CONTRIBUTION.value,
            window,
        )
        windows[key].append(max(1, contribution.labor_delta))
        owners[key].add(contribution.actor_token)
    rows: list[AccountingFlowRow] = []
    for (kind, direction, window), values in sorted(windows.items()):
        rows.append(
            AccountingFlowRow(
                entry_kind=AccountingEntryKindToken(kind),
                direction=AccountingEntryDirection(direction),
                event_count=len(values),
                quantity_sum=min(
                    active.max_quantity * max(1, len(values)),
                    sum(values),
                ),
                owner_count=len(owners[(kind, direction, window)]),
                counterparty_count=len(
                    counterparties[(kind, direction, window)]
                ),
                window_index=window,
            )
        )
    rows.sort(
        key=lambda row: (
            row.window_index,
            row.entry_kind.value,
            row.direction.value,
        )
    )
    if len(rows) > active.max_flow_rows:
        rows = rows[: active.max_flow_rows]
    assert_accounting_layer_separation(*rows)
    return tuple(rows)


def detect_accounting_counterparties(
    claims: Sequence[AccountingClaimEvidenceRow],
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> tuple[AccountingCounterpartyRow, ...]:
    """Aggregate claims by speaker token; never a trust or fraud score."""

    active = _policy(policy)
    groups: dict[str, list[AccountingClaimEvidenceRow]] = defaultdict(list)
    for claim in claims:
        if type(claim) is not AccountingClaimEvidenceRow:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        groups[claim.speaker_token].append(claim)
    rows: list[AccountingCounterpartyRow] = []
    for token, group in sorted(groups.items()):
        rows.append(
            AccountingCounterpartyRow(
                counterparty_token=token,
                entry_count=len(group),
                kinds=tuple(sorted({row.entry_kind.value for row in group})),
                first_tick=min(row.tick for row in group),
                last_tick=max(row.tick for row in group),
            )
        )
    if len(rows) > active.max_counterparty_rows:
        rows = rows[: active.max_counterparty_rows]
    assert_accounting_layer_separation(*rows)
    return tuple(rows)


def _quantile(sorted_values: Sequence[int], numerator: int, denominator: int) -> int:
    if not sorted_values:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = numerator * (len(sorted_values) - 1)
    lower, remainder = divmod(position, denominator)
    upper = min(len(sorted_values) - 1, lower + 1)
    return (
        sorted_values[lower] * (denominator - remainder)
        + sorted_values[upper] * remainder
    ) // denominator


def accounting_distribution_summary(
    values: Sequence[int],
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingDistributionSummary:
    """Return a descriptive distribution, or an explicit insufficient state."""

    active = _policy(policy)
    cleaned = sorted(
        value
        for value in values
        if isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= active.max_quantity
    )
    if len(cleaned) < active.min_distribution_samples:
        return AccountingDistributionSummary(
            status=AccountingDistributionStatus.INSUFFICIENT_SAMPLES,
            sample_count=len(cleaned),
            minimum=None,
            p25=None,
            median=None,
            p75=None,
            maximum=None,
            iqr=None,
            dispersion=None,
            bin_shares_milli=(),
        )
    p25 = _quantile(cleaned, 1, 4)
    median = _quantile(cleaned, 2, 4)
    p75 = _quantile(cleaned, 3, 4)
    minimum = cleaned[0]
    maximum = cleaned[-1]
    span = max(1, maximum - minimum + 1)
    bins = [0, 0, 0, 0, 0]
    for value in cleaned:
        index = min(4, (value - minimum) * 5 // span)
        bins[index] += 1
    total = len(cleaned)
    return AccountingDistributionSummary(
        status=AccountingDistributionStatus.AVAILABLE,
        sample_count=total,
        minimum=minimum,
        p25=p25,
        median=median,
        p75=p75,
        maximum=maximum,
        iqr=p75 - p25,
        dispersion=maximum - minimum,
        bin_shares_milli=tuple(count * 1_000 // total for count in bins),
    )
