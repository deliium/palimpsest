"""Join detached owner credit rows to objective evidence for researchers only."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, cast

from analysis.credit_relationships_contract import (
    CreditAlignment,
    CreditCoverage,
    CreditOwnerStatus,
    CreditPerformanceOutcome,
    CreditRelationshipAnalysisError,
    credit_alignment_token,
    credit_owner_token,
)
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
    default_credit_relationships_analysis_policy,
)
from analysis.credit_relationships_rows import (
    AnalyticalCreditRelationshipRow,
    CreditAlignmentRow,
    CreditOwnerInput,
    CreditPerformanceRow,
)

__all__ = [
    "CreditOwnerJoin",
    "join_credit_relationships",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.credit_relationships.expectations"
)

_REPAID_STATUSES: Final[frozenset[CreditOwnerStatus]] = frozenset(
    {CreditOwnerStatus.PARTIALLY_REPAID, CreditOwnerStatus.REPAID}
)


@dataclass(frozen=True, slots=True)
class CreditOwnerJoin:
    """Bounded owner relationship rows and researcher-only alignments."""

    relationships: tuple[AnalyticalCreditRelationshipRow, ...]
    alignments: tuple[CreditAlignmentRow, ...]
    coverage: CreditCoverage
    notices: tuple[str, ...]


def _policy(
    policy: CreditRelationshipsAnalysisPolicy | None,
) -> CreditRelationshipsAnalysisPolicy:
    active = (
        default_credit_relationships_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not CreditRelationshipsAnalysisPolicy:
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_policy")
    return active


def _rows[T](value: object, row_type: type[T]) -> tuple[T, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    rows = tuple(value)
    for row in rows:
        if type(row) is not row_type:
            raise CreditRelationshipAnalysisError("credit_analysis_invalid_row")
    return cast(tuple[T, ...], rows)


def _alignment(
    *,
    gap: int,
    status: CreditOwnerStatus,
    observed_transfers: int,
    owner_paid: int,
    repayment_quantity: int,
    policy: CreditRelationshipsAnalysisPolicy,
) -> CreditAlignment:
    if (
        gap >= policy.alignment_high_milli
        or (status is CreditOwnerStatus.REPAID and observed_transfers == 0)
        or (
            status is CreditOwnerStatus.DEFAULTED
            and owner_paid >= repayment_quantity
        )
    ):
        return CreditAlignment.INCONSISTENT
    if (
        gap <= policy.alignment_low_milli
        and status in _REPAID_STATUSES
        and observed_transfers > 0
    ):
        return CreditAlignment.CONSISTENT
    return CreditAlignment.UNRESOLVED


def join_credit_relationships(
    owner_inputs: Sequence[CreditOwnerInput],
    performances: Sequence[CreditPerformanceRow],
    *,
    policy: CreditRelationshipsAnalysisPolicy | None = None,
) -> CreditOwnerJoin:
    """Project owner rows and compare them with committed evidence."""

    active = _policy(policy)
    inputs = _rows(owner_inputs, CreditOwnerInput)
    performance_rows = _rows(performances, CreditPerformanceRow)
    if not inputs:
        return CreditOwnerJoin(
            relationships=(),
            alignments=(),
            coverage=CreditCoverage.MISSING,
            notices=("credit_missing_owner_rows",),
        )
    by_anchor = {
        (row.anchor_token, row.window_index): row for row in performance_rows
    }
    notices: set[str] = set()
    relationships: list[AnalyticalCreditRelationshipRow] = []
    alignments: list[CreditAlignmentRow] = []
    for item in inputs:
        ratio = min(
            active.max_ratio_milli,
            item.repayment_quantity * 1_000 // item.principal_quantity,
        )
        coverage = item.coverage
        performance = by_anchor.get((item.anchor_token, item.window_index))
        if performance is None:
            alignment = CreditAlignment.NOT_APPLICABLE
            outcome = CreditPerformanceOutcome.INSUFFICIENT_EVIDENCE
            gap = 0
            coverage = CreditCoverage.PARTIAL
            notices.add("credit_missing_evidence")
        else:
            gap = (
                abs(item.paid_quantity - performance.observed_transfer_count)
                * 1_000
                // max(1, item.repayment_quantity)
            )
            alignment = _alignment(
                gap=gap,
                status=item.status,
                observed_transfers=performance.observed_transfer_count,
                owner_paid=item.paid_quantity,
                repayment_quantity=item.repayment_quantity,
                policy=active,
            )
            outcome = performance.outcome
            if performance.coverage is CreditCoverage.PARTIAL:
                coverage = CreditCoverage.PARTIAL
        relationships.append(
            AnalyticalCreditRelationshipRow(
                relationship_id=credit_owner_token(
                    item.owner_token, item.anchor_token, item.window_index
                ),
                window_index=item.window_index,
                owner_token=item.owner_token,
                counterparty_token=item.counterparty_token,
                direction=item.direction,
                anchor_token=item.anchor_token,
                principal_kind=item.principal_kind,
                principal_quantity=item.principal_quantity,
                repayment_kind=item.repayment_kind,
                repayment_quantity=item.repayment_quantity,
                repayment_ratio_milli=ratio,
                due_tick=item.due_tick,
                condition=item.condition,
                collateral_kind=item.collateral_kind,
                collateral_quantity=item.collateral_quantity,
                status=item.status,
                confidence_milli=item.confidence_milli,
                expectation_milli=item.expectation_milli,
                trust_milli=item.trust_milli,
                claim_count=item.claim_count,
                renegotiate_count=item.renegotiate_count,
                coverage=coverage,
            )
        )
        alignments.append(
            CreditAlignmentRow(
                alignment_id=credit_alignment_token(
                    item.owner_token, item.anchor_token, item.window_index
                ),
                window_index=item.window_index,
                owner_token=item.owner_token,
                anchor_token=item.anchor_token,
                alignment=alignment,
                owner_status=item.status,
                analytical_outcome=outcome,
                owner_paid_quantity=item.paid_quantity,
                declared_repayment_quantity=item.repayment_quantity,
                observed_transfer_count=(
                    0 if performance is None else performance.observed_transfer_count
                ),
                gap_milli=gap,
                coverage=coverage,
            )
        )

    relationships.sort(
        key=lambda row: (row.owner_token, row.window_index, row.anchor_token)
    )
    alignments.sort(key=lambda row: (row.window_index, row.alignment_id))
    if len(relationships) > active.max_relationship_rows:
        relationships = relationships[: active.max_relationship_rows]
        relationships = [
            replace(row, coverage=CreditCoverage.PARTIAL) for row in relationships
        ]
        notices.add("credit_owner_truncated")
        _LOG.warning(
            "credit_owner_truncated family=relationships count=%s",
            active.max_relationship_rows,
        )
    if len(alignments) > active.max_alignment_rows:
        alignments = alignments[: active.max_alignment_rows]
        alignments = [
            replace(row, coverage=CreditCoverage.PARTIAL) for row in alignments
        ]
        notices.add("credit_alignment_truncated")
        _LOG.warning(
            "credit_alignment_truncated count=%s", active.max_alignment_rows
        )
    coverage = (
        CreditCoverage.MISSING
        if not relationships
        else (CreditCoverage.PARTIAL if notices else CreditCoverage.COMPLETE)
    )
    _LOG.debug(
        "credit_owner_join relationships=%s alignments=%s coverage=%s",
        len(relationships),
        len(alignments),
        coverage.value,
    )
    return CreditOwnerJoin(
        relationships=tuple(relationships),
        alignments=tuple(alignments),
        coverage=coverage,
        notices=tuple(sorted(notices)),
    )
