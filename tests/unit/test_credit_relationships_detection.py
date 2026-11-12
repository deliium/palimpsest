"""Descriptive credit performance, distribution, and counterparty detection."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.credit_relationships_contract import (
    CreditClaimAct,
    CreditClaimDirection,
    CreditCoverage,
    CreditDistributionStatus,
    CreditPerformanceOutcome,
    CreditSampleSource,
    credit_claim_token,
)
from analysis.credit_relationships_detection import (
    assert_credit_layer_separation,
    credit_distribution_summary,
    detect_credit_counterparties,
    detect_credit_distributions,
    detect_credit_performances,
)
from analysis.credit_relationships_events import credit_evidence_rows_from_events
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from analysis.credit_relationships_rows import (
    CreditClaimEvidenceRow,
    CreditEvidenceHarvest,
)
from tests.unit.credit_relationships_analysis_helpers import (
    ANCHOR,
    frame,
    given,
    talked,
)
from world.credit_relationships import CreditFrameAct

pytestmark = pytest.mark.unit


def _harvest(*frames, window_end_tick: int = 0):
    events = [
        talked(f"evt-{index + 1}", item, tick=index)
        for index, item in enumerate(frames)
    ]
    return credit_evidence_rows_from_events(events)


def _outcome(harvest, window_end=None):
    rows = detect_credit_performances(harvest, window_end=window_end)
    assert len(rows) == 1
    return rows[0].outcome


def test_active_outcome_before_deadline() -> None:
    harvest = _harvest(frame())
    assert _outcome(harvest, window_end=5) is CreditPerformanceOutcome.ACTIVE


def test_expired_outcome_after_grace() -> None:
    harvest = _harvest(frame(due_tick=10))
    assert _outcome(harvest, window_end=20) is CreditPerformanceOutcome.EXPIRED


def test_partial_and_full_repayment_outcomes() -> None:
    partial = _harvest(
        frame(),
        frame(act=CreditFrameAct.REPAY, paid_quantity=1),
    )
    assert _outcome(partial) is CreditPerformanceOutcome.PARTIALLY_REPAID
    repaid = _harvest(
        frame(),
        frame(act=CreditFrameAct.REPAY, paid_quantity=3),
    )
    assert _outcome(repaid) is CreditPerformanceOutcome.REPAID


def test_default_forgive_and_dispute_priority() -> None:
    assert _outcome(
        _harvest(frame(), frame(act=CreditFrameAct.DEFAULT))
    ) is CreditPerformanceOutcome.DEFAULTED
    assert _outcome(
        _harvest(frame(), frame(act=CreditFrameAct.FORGIVE))
    ) is CreditPerformanceOutcome.FORGIVEN
    assert _outcome(
        _harvest(frame(), frame(act=CreditFrameAct.DISPUTE))
    ) is CreditPerformanceOutcome.DISPUTED


def test_repaid_outranks_default() -> None:
    harvest = _harvest(
        frame(),
        frame(act=CreditFrameAct.DEFAULT),
        frame(
            act=CreditFrameAct.REPAY,
            paid_quantity=3,
        ),
    )
    assert _outcome(harvest) is CreditPerformanceOutcome.REPAID


def test_direction_conflict_marks_partial() -> None:
    from world.credit_relationships import CreditFrameDirection

    harvest = _harvest(
        frame(),
        frame(
            act=CreditFrameAct.ACCEPT,
            direction=CreditFrameDirection.OWNER_CREDITOR,
        ),
    )
    row = detect_credit_performances(harvest)[0]
    assert row.direction_conflict is True
    assert row.coverage is CreditCoverage.PARTIAL


def test_proposed_and_agreed_samples_stay_separate() -> None:
    harvest = _harvest(
        frame(),
        frame(act=CreditFrameAct.ACCEPT),
    )
    rows = detect_credit_distributions(harvest)
    assert len(rows) == 2
    assert {row.sample_source for row in rows} == {
        CreditSampleSource.PROPOSED,
        CreditSampleSource.AGREED,
    }
    assert all(row.sample_count == 1 for row in rows)
    assert all(
        row.status is CreditDistributionStatus.INSUFFICIENT_SAMPLES
        for row in rows
    )


def test_four_agreed_samples_are_available() -> None:
    harvest = _harvest(
        frame(),
        frame(act=CreditFrameAct.ACCEPT),
        frame(act=CreditFrameAct.ACCEPT, opened_tick=1),
        frame(act=CreditFrameAct.ACCEPT, opened_tick=2),
        frame(act=CreditFrameAct.ACCEPT, opened_tick=3),
    )
    rows = detect_credit_distributions(harvest)
    agreed = [row for row in rows if row.sample_source is CreditSampleSource.AGREED]
    assert agreed[0].sample_count == 4
    assert agreed[0].status is CreditDistributionStatus.AVAILABLE


def test_distribution_summary_reports_quantiles_and_bins() -> None:
    summary = credit_distribution_summary([1_000, 2_000, 3_000, 4_000])
    assert summary.status is CreditDistributionStatus.AVAILABLE
    assert summary.sample_count == 4
    assert summary.minimum == 1_000
    assert summary.p25 == 1_000
    assert summary.median == 2_000
    assert summary.p75 == 3_000
    assert summary.maximum == 4_000
    assert summary.iqr == 2_000
    assert sum(summary.bins) == 1_000


def test_out_of_range_ratio_is_excluded() -> None:
    row = CreditClaimEvidenceRow(
        claim_id=credit_claim_token("evt-x", "propose", "owner_debtor"),
        tick=0,
        window_index=0,
        event_token="evt-x",
        actor_token="body-a",
        counterparty_token="body-b",
        act=CreditClaimAct.PROPOSE,
        direction=CreditClaimDirection.OWNER_DEBTOR,
        anchor_token=ANCHOR,
        principal_kind="food",
        principal_quantity=1,
        repayment_kind="water",
        repayment_quantity=65,
        paid_quantity=0,
        opened_tick=0,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_item_kind=None,
        collateral_quantity=0,
        confidence_milli=500,
        coverage=CreditCoverage.COMPLETE,
    )
    harvest = CreditEvidenceHarvest(
        claims=(row,),
        transfers=(),
        coverage=CreditCoverage.COMPLETE,
        notices=(),
        claim_count=1,
        transfer_count=0,
    )
    assert detect_credit_distributions(harvest) == ()


def test_counterparty_aggregate_counts() -> None:
    harvest = _harvest(
        frame(),
        frame(act=CreditFrameAct.REPAY, paid_quantity=1),
    )
    rows = detect_credit_counterparties(harvest)
    assert len(rows) == 1
    row = rows[0]
    assert row.relationship_count == 1
    assert row.owner_count == 1
    assert row.claim_count == 2
    assert row.repay_claim_count == 1


def test_transfer_count_reaches_performance_and_counterparty() -> None:
    events = [
        talked("evt-1", frame(), tick=0),
        given("evt-2", item_id="item-1", tick=1, sequence=1),
    ]
    harvest = credit_evidence_rows_from_events(events)
    performance = detect_credit_performances(harvest)[0]
    assert performance.observed_transfer_count == 1
    counterparty = detect_credit_counterparties(harvest)[0]
    assert counterparty.observed_transfer_count == 1


def test_performance_cap_truncates_and_marks_partial() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_performance_rows=1)
    harvest = _harvest(
        frame(anchor="crd-0000000000000001"),
        frame(anchor="crd-0000000000000002", opened_tick=1),
    )
    rows = detect_credit_performances(harvest, policy=policy)
    assert len(rows) == 1
    assert rows[0].coverage is CreditCoverage.PARTIAL


def test_distribution_cap_truncates_and_marks_partial() -> None:
    policy = CreditRelationshipsAnalysisPolicy(max_distribution_rows=1)
    harvest = _harvest(
        frame(),
        frame(
            act=CreditFrameAct.ACCEPT,
            repayment_kind="tool",
        ),
    )
    rows = detect_credit_distributions(harvest, policy=policy)
    assert len(rows) == 1
    assert rows[0].coverage is CreditCoverage.PARTIAL


def test_layer_separation_rejects_owner_tokens_in_objective_layer() -> None:
    from analysis.credit_relationships_contract import (
        CreditAnalysisLayer,
        CreditRelationshipAnalysisError,
    )

    performance = detect_credit_performances(_harvest(frame()))[0]
    assert_credit_layer_separation(
        {CreditAnalysisLayer.ANALYTICAL_PERFORMANCE: (performance,)}
    )
    with pytest.raises(CreditRelationshipAnalysisError):
        assert_credit_layer_separation(
            {CreditAnalysisLayer.OBJECTIVE_CLAIM: (performance,)}
        )


def test_empty_evidence_has_no_rows() -> None:
    harvest = credit_evidence_rows_from_events([])
    assert detect_credit_performances(harvest) == ()
    assert detect_credit_distributions(harvest) == ()
    assert detect_credit_counterparties(harvest) == ()
