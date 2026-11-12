"""Shared builders for credit snapshot and publication tests."""

# mypy: ignore-errors


from __future__ import annotations

from simulation.credit_relationships_models import (
    CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
    CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    CreditAlignmentRecord,
    CreditClaimRecord,
    CreditCounterpartyRecord,
    CreditDistributionRecord,
    CreditPerformanceRecord,
    CreditRelationshipRecord,
    CreditRelationshipsSnapshot,
    CreditSummaryRecord,
)

ANCHOR = "crd-0123456789abcdef"
OWNER = "owner-1"
PEER = "credpeer-0123456789abcdef"


def summary(**overrides: object) -> CreditSummaryRecord:
    values = {
        "window_tick": 3,
        "window_count": 1,
        "relationship_count": 1,
        "claim_count": 1,
        "performance_count": 1,
        "distribution_count": 1,
        "counterparty_count": 1,
        "alignment_count": 1,
        "claim_event_count": 1,
        "transfer_event_count": 1,
        "evidence_coverage": "complete",
        "owner_coverage": "complete",
        "relationship_coverage": "complete",
        "performance_coverage": "complete",
        "distribution_coverage": "complete",
        "counterparty_coverage": "complete",
        "alignment_coverage": "complete",
        "coverage": "complete",
        "truncated": False,
    }
    values.update(overrides)
    return CreditSummaryRecord(**values)


def relationship(
    relationship_id: str = "credo-0123456789abcdef",
) -> CreditRelationshipRecord:
    return CreditRelationshipRecord(
        relationship_id=relationship_id,
        window_index=0,
        owner_token=OWNER,
        counterparty_token=PEER,
        direction="owner_debtor",
        anchor_token=ANCHOR,
        principal_kind="food",
        principal_quantity=2,
        repayment_kind="water",
        repayment_quantity=3,
        repayment_ratio_milli=1_500,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_quantity=0,
        status="repaid",
        confidence_milli=500,
        expectation_milli=500,
        trust_milli=500,
        claim_count=1,
        coverage="complete",
    )


def claim(claim_id: str = "credcl-0123456789abcdef") -> CreditClaimRecord:
    return CreditClaimRecord(
        claim_id=claim_id,
        window_index=0,
        event_token="evt-1",
        actor_token="body-a",
        counterparty_token="body-b",
        act="propose",
        direction="owner_debtor",
        anchor_token=ANCHOR,
        principal_kind="food",
        principal_quantity=2,
        repayment_kind="water",
        repayment_quantity=3,
        paid_quantity=0,
        opened_tick=0,
        due_tick=10,
        condition="by_deadline",
        collateral_kind="none",
        collateral_quantity=0,
        confidence_milli=500,
        coverage="complete",
    )


def performance(
    performance_id: str = "credp-0123456789abcdef",
) -> CreditPerformanceRecord:
    return CreditPerformanceRecord(
        performance_id=performance_id,
        window_index=0,
        anchor_token=ANCHOR,
        claim_count=1,
        repay_claim_count=1,
        default_claim_count=0,
        forgive_claim_count=0,
        dispute_claim_count=0,
        renegotiate_claim_count=0,
        observed_transfer_count=1,
        repaid_quantity=3,
        principal_quantity=2,
        repayment_quantity=3,
        outcome="repaid",
        coverage="complete",
    )


def distribution(
    distribution_id: str = "credd-0123456789abcdef",
) -> CreditDistributionRecord:
    return CreditDistributionRecord(
        distribution_id=distribution_id,
        window_index=0,
        principal_kind="food",
        repayment_kind="water",
        sample_source="agreed",
        sample_count=4,
        min_ratio_milli=1_000,
        p25_ratio_milli=1_000,
        median_ratio_milli=2_000,
        p75_ratio_milli=2_000,
        max_ratio_milli=3_000,
        iqr_milli=1_000,
        dispersion_milli=500,
        bin_shares_milli=(250, 0, 500, 0, 250),
        status="available",
        coverage="complete",
    )


def counterparty(
    counterparty_token: str = "credcp-0123456789abcdef",
) -> CreditCounterpartyRecord:
    return CreditCounterpartyRecord(
        counterparty_token=counterparty_token,
        window_index=0,
        relationship_count=1,
        owner_count=1,
        claim_count=1,
        repay_claim_count=1,
        default_claim_count=0,
        forgive_claim_count=0,
        dispute_claim_count=0,
        observed_transfer_count=1,
        coverage="complete",
    )


def alignment(alignment_id: str = "creda-0123456789abcdef") -> CreditAlignmentRecord:
    return CreditAlignmentRecord(
        alignment_id=alignment_id,
        window_index=0,
        owner_token=OWNER,
        anchor_token=ANCHOR,
        alignment="consistent",
        owner_status="repaid",
        analytical_outcome="repaid",
        owner_paid_quantity=3,
        declared_repayment_quantity=3,
        observed_transfer_count=1,
        gap_milli=0,
        coverage="complete",
    )


def snapshot(
    *,
    run_id: str = "run-credit-1",
    digest: str = "",
    publication_id: str = "",
) -> CreditRelationshipsSnapshot:
    return CreditRelationshipsSnapshot(
        run_id=run_id,
        schema_version=CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
        policy_version=CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
        summary=summary(),
        relationships=(relationship(),),
        claims=(claim(),),
        performances=(performance(),),
        distributions=(distribution(),),
        counterparties=(counterparty(),),
        alignments=(alignment(),),
        digest=digest,
        publication_id=publication_id,
    )
