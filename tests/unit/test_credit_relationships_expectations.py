"""Detached owner credit rows and researcher-only alignment joins."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.credit_relationships_contract import (
    CreditAlignment,
    CreditClaimDirection,
    CreditCoverage,
    CreditOwnerLevel,
    CreditOwnerStatus,
    CreditPerformanceOutcome,
    credit_peer_token,
)
from analysis.credit_relationships_detection import detect_credit_performances
from analysis.credit_relationships_events import credit_evidence_rows_from_events
from analysis.credit_relationships_expectations import join_credit_relationships
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from analysis.credit_relationships_rows import CreditOwnerInput
from tests.unit.credit_relationships_analysis_helpers import (
    ANCHOR,
    frame,
    given,
    talked,
)

pytestmark = pytest.mark.unit

OWNER_TOKEN = "owner-agent"
PEER_TOKEN = credit_peer_token("body-b")


def _owner(
    *,
    status: CreditOwnerStatus = CreditOwnerStatus.REPAID,
    paid: int = 1,
    repayment: int = 1,
    principal: int = 2,
    anchor: str = ANCHOR,
    window_index: int = 0,
    coverage: CreditCoverage = CreditCoverage.COMPLETE,
) -> CreditOwnerInput:
    return CreditOwnerInput(
        owner_token=OWNER_TOKEN,
        window_index=window_index,
        anchor_token=anchor,
        counterparty_token=PEER_TOKEN,
        direction=CreditClaimDirection.OWNER_DEBTOR,
        principal_kind="food",
        principal_quantity=principal,
        repayment_kind="water",
        repayment_quantity=repayment,
        paid_quantity=paid,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_quantity=0,
        status=status,
        confidence_milli=500,
        level=CreditOwnerLevel.EXPECTED,
        trust_milli=500,
        expectation_milli=500,
        claim_count=1,
        promise_count=0,
        renegotiate_count=0,
        first_tick=0,
        last_tick=1,
        coverage=coverage,
    )


def _performance(*, transfers: int = 1):
    events = [talked("evt-1", frame(repayment_quantity=1), tick=0)]
    for index in range(transfers):
        events.append(
            given(
                f"evt-g-{index}",
                item_id=f"item-{index}",
                tick=1,
                sequence=index,
            )
        )
    evidence = credit_evidence_rows_from_events(events)
    return detect_credit_performances(evidence)[0]


def test_matching_repaid_owner_row_with_one_transfer_is_consistent() -> None:
    joined = join_credit_relationships([_owner()], [_performance()])
    assert joined.alignments[0].alignment is CreditAlignment.CONSISTENT
    assert joined.coverage is CreditCoverage.COMPLETE


def test_claimed_repayment_without_transfer_is_inconsistent() -> None:
    joined = join_credit_relationships([_owner()], [_performance(transfers=0)])
    assert joined.alignments[0].alignment is CreditAlignment.INCONSISTENT


def test_defaulted_owner_with_full_claimed_repayment_is_inconsistent() -> None:
    joined = join_credit_relationships(
        [
            _owner(
                status=CreditOwnerStatus.DEFAULTED,
                paid=1,
                repayment=1,
            )
        ],
        [_performance(transfers=1)],
    )
    assert joined.alignments[0].alignment is CreditAlignment.INCONSISTENT


def test_owner_row_without_performance_is_not_applicable() -> None:
    joined = join_credit_relationships([_owner()], [])
    assert joined.alignments[0].alignment is CreditAlignment.NOT_APPLICABLE
    assert (
        joined.alignments[0].analytical_outcome
        is CreditPerformanceOutcome.INSUFFICIENT_EVIDENCE
    )
    assert joined.relationships[0].anchor_token == ANCHOR


def test_gap_boundaries_use_policy_thresholds() -> None:
    performance = _performance(transfers=3)
    low = join_credit_relationships(
        [_owner(paid=4, repayment=4)], [performance]
    )
    assert low.alignments[0].gap_milli == 250
    assert low.alignments[0].alignment is CreditAlignment.CONSISTENT
    high = join_credit_relationships(
        [_owner(paid=4, repayment=4)],
        [_performance(transfers=0)],
    )
    assert high.alignments[0].gap_milli == 1_000
    assert high.alignments[0].alignment is CreditAlignment.INCONSISTENT


def test_no_owner_rows_is_missing_without_fabricated_tokens() -> None:
    joined = join_credit_relationships([], [_performance()])
    assert joined.relationships == ()
    assert joined.alignments == ()
    assert joined.coverage is CreditCoverage.MISSING
    assert "credit_missing_owner_rows" in joined.notices


def test_relationship_cap_truncates_and_marks_partial() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_relationship_rows=1)
    joined = join_credit_relationships(
        [_owner(), _owner(anchor="crd-0000000000000002")],
        [_performance()],
        policy=policy,
    )
    assert len(joined.relationships) == 1
    assert joined.relationships[0].coverage is CreditCoverage.PARTIAL
    assert "credit_owner_truncated" in joined.notices


def test_alignment_cap_truncates_and_marks_partial() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_alignment_rows=1)
    joined = join_credit_relationships(
        [_owner(), _owner(anchor="crd-0000000000000002")],
        [_performance()],
        policy=policy,
    )
    assert len(joined.alignments) == 1
    assert joined.alignments[0].coverage is CreditCoverage.PARTIAL
    assert "credit_alignment_truncated" in joined.notices


def test_owner_rows_never_modify_performance_rows() -> None:
    performance = _performance()
    before = performance
    join_credit_relationships([_owner()], [performance])
    assert performance == before
