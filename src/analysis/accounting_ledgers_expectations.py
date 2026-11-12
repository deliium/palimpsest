"""Token-only owner joins and researcher-only accounting alignment."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.accounting_ledgers_contract import (
    AccountingAlignment,
    AccountingAnalysisError,
    AccountingCoverage,
    AccountingEntryDirection,
    AccountingEntryKindToken,
    AccountingRecordAssessmentToken,
    accounting_alignment_token,
)
from analysis.accounting_ledgers_policy import (
    AccountingLedgersAnalysisPolicy,
    default_accounting_ledgers_analysis_policy,
)
from analysis.accounting_ledgers_rows import (
    AccountingAlignmentRow,
    AccountingRecordEvidenceRow,
    AccountingTransferEvidenceRow,
)

__all__ = [
    "AccountingOwnerJoin",
    "AccountingOwnerRowInput",
    "join_accounting_owners",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.expectations"
)


def _count(value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return value


def _token(value: object) -> str:
    if type(value) is not str or not value:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return value


@dataclass(frozen=True, slots=True)
class AccountingOwnerRowInput:
    """One token-only detached owner accounting row. Never a shared ledger."""

    owner_token: str
    entry_token: str
    record_token: str
    entry_kind: AccountingEntryKindToken
    direction: AccountingEntryDirection
    item_kind: str
    quantity: int
    assessment: AccountingRecordAssessmentToken
    confidence_milli: int
    first_tick: int
    last_tick: int
    window_index: int

    def __post_init__(self) -> None:
        for name in ("owner_token", "entry_token", "record_token", "item_kind"):
            object.__setattr__(self, name, _token(getattr(self, name)))
        if type(self.entry_kind) is not AccountingEntryKindToken:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if type(self.direction) is not AccountingEntryDirection:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        for name in (
            "quantity",
            "confidence_milli",
            "first_tick",
            "last_tick",
            "window_index",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if not 1 <= self.quantity <= 64:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if self.confidence_milli > 1_000:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if self.last_tick < self.first_tick:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if type(self.assessment) is not AccountingRecordAssessmentToken:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")

    @property
    def source_layers(self) -> tuple[str, ...]:
        return ("owner_claim",)


@dataclass(frozen=True, slots=True)
class AccountingOwnerJoin:
    """One bounded owner join plus researcher-only alignment rows."""

    owner_rows: tuple[AccountingOwnerRowInput, ...]
    alignments: tuple[AccountingAlignmentRow, ...]
    coverage: AccountingCoverage
    notices: tuple[str, ...] = ()
    duplicate_owner_rows: int = 0

    def __post_init__(self) -> None:
        if type(self.coverage) is not AccountingCoverage:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if isinstance(self.owner_rows, (str, bytes)) or not isinstance(
            self.owner_rows, tuple
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if isinstance(self.alignments, (str, bytes)) or not isinstance(
            self.alignments, tuple
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if isinstance(self.notices, (str, bytes)) or not isinstance(
            self.notices, tuple
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(
            self, "duplicate_owner_rows", _count(self.duplicate_owner_rows)
        )


def _gap_milli(owner_quantity: int, evidence_quantity: int) -> int:
    return min(
        1_000,
        abs(owner_quantity - evidence_quantity)
        * 1_000
        // max(1, evidence_quantity),
    )


def join_accounting_owners(
    *,
    owner_rows: tuple[AccountingOwnerRowInput, ...],
    record_rows: tuple[AccountingRecordEvidenceRow, ...],
    transfer_rows: tuple[AccountingTransferEvidenceRow, ...],
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingOwnerJoin:
    """Join token-only owner rows to committed evidence for researchers only."""

    active = (
        default_accounting_ledgers_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not AccountingLedgersAnalysisPolicy:
        raise AccountingAnalysisError("accounting_analysis_invalid_policy")
    notices: set[str] = set()
    seen: set[tuple[str, str]] = set()
    unique: list[AccountingOwnerRowInput] = []
    duplicates = 0
    for row in owner_rows:
        if type(row) is not AccountingOwnerRowInput:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        key = (row.owner_token, row.entry_token)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(row)
    if len(unique) > active.max_owner_rows:
        unique = unique[: active.max_owner_rows]
        notices.add("accounting_owner_truncated")
        notices.add("accounting_evidence_truncated")
    if not unique:
        return AccountingOwnerJoin(
            owner_rows=(),
            alignments=(),
            coverage=AccountingCoverage.MISSING,
            notices=tuple(sorted(notices)),
            duplicate_owner_rows=duplicates,
        )
    records_by_token = {row.record_token: row for row in record_rows}
    transfers = tuple(transfer_rows)
    alignments: list[AccountingAlignmentRow] = []
    for row in unique:
        record = records_by_token.get(row.record_token)
        candidates = [
            transfer
            for transfer in transfers
            if transfer.item_kind == row.item_kind
        ]
        if record is None and not candidates:
            alignments.append(
                AccountingAlignmentRow(
                    entry_token=accounting_alignment_token(
                        row.entry_token, row.window_index
                    ),
                    alignment=AccountingAlignment.NOT_APPLICABLE,
                    gap_milli=0,
                    record_token=row.record_token,
                )
            )
            continue
        if not candidates:
            alignments.append(
                AccountingAlignmentRow(
                    entry_token=accounting_alignment_token(
                        row.entry_token, row.window_index
                    ),
                    alignment=AccountingAlignment.UNRESOLVED,
                    gap_milli=1_000,
                    record_token=row.record_token,
                )
            )
            continue
        evidence_quantity = max(transfer.quantity for transfer in candidates)
        gap = _gap_milli(row.quantity, evidence_quantity)
        if gap <= active.alignment_consistent_milli:
            alignment = AccountingAlignment.CONSISTENT
        elif gap >= active.alignment_inconsistent_milli:
            alignment = AccountingAlignment.INCONSISTENT
        else:
            alignment = AccountingAlignment.UNRESOLVED
        alignments.append(
            AccountingAlignmentRow(
                entry_token=accounting_alignment_token(
                    row.entry_token, row.window_index
                ),
                alignment=alignment,
                gap_milli=gap,
                record_token=row.record_token,
            )
        )
    if len(alignments) > active.max_alignment_rows:
        alignments = alignments[: active.max_alignment_rows]
        notices.add("accounting_alignment_truncated")
        notices.add("accounting_evidence_truncated")
    coverage = (
        AccountingCoverage.PARTIAL
        if notices or duplicates
        else AccountingCoverage.COMPLETE
    )
    _LOG.debug(
        "accounting_ledger_joined owners=%s alignments=%s",
        len(unique),
        len(alignments),
    )
    return AccountingOwnerJoin(
        owner_rows=tuple(unique),
        alignments=tuple(alignments),
        coverage=coverage,
        notices=tuple(sorted(notices)),
        duplicate_owner_rows=duplicates,
    )
