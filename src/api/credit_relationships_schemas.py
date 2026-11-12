"""Strict frozen response models for credit relationship read routes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CreditAlignmentOut",
    "CreditAlignmentPageOut",
    "CreditClaimOut",
    "CreditClaimsPageOut",
    "CreditCounterpartiesPageOut",
    "CreditCounterpartyOut",
    "CreditDistributionOut",
    "CreditDistributionsPageOut",
    "CreditPerformanceOut",
    "CreditPerformancesPageOut",
    "CreditRelationshipOut",
    "CreditRelationshipsPageOut",
    "CreditRelationshipsSummaryOut",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CreditRelationshipOut(_Strict):
    relationship_id: str
    window_index: int
    owner_token: str
    counterparty_token: str
    direction: str
    anchor_token: str
    principal_kind: str
    principal_quantity: int
    repayment_kind: str
    repayment_quantity: int
    repayment_ratio_milli: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    status: str
    confidence_milli: int
    expectation_milli: int
    trust_milli: int
    claim_count: int
    coverage: str


class CreditClaimOut(_Strict):
    claim_id: str
    window_index: int
    event_token: str
    actor_token: str
    counterparty_token: str
    act: str
    direction: str
    anchor_token: str
    principal_kind: str
    principal_quantity: int
    repayment_kind: str
    repayment_quantity: int
    paid_quantity: int
    opened_tick: int
    due_tick: int | None
    condition: str
    collateral_kind: str
    collateral_quantity: int
    confidence_milli: int
    coverage: str


class CreditPerformanceOut(_Strict):
    performance_id: str
    window_index: int
    anchor_token: str
    claim_count: int
    repay_claim_count: int
    default_claim_count: int
    forgive_claim_count: int
    dispute_claim_count: int
    renegotiate_claim_count: int
    observed_transfer_count: int
    repaid_quantity: int
    principal_quantity: int
    repayment_quantity: int
    outcome: str
    coverage: str


class CreditDistributionOut(_Strict):
    distribution_id: str
    window_index: int
    principal_kind: str
    repayment_kind: str
    sample_source: str
    sample_count: int
    min_ratio_milli: int
    p25_ratio_milli: int
    median_ratio_milli: int
    p75_ratio_milli: int
    max_ratio_milli: int
    iqr_milli: int
    dispersion_milli: int
    bin_shares_milli: tuple[int, int, int, int, int]
    status: str
    coverage: str


class CreditCounterpartyOut(_Strict):
    counterparty_token: str
    window_index: int
    relationship_count: int
    owner_count: int
    claim_count: int
    repay_claim_count: int
    default_claim_count: int
    forgive_claim_count: int
    dispute_claim_count: int
    observed_transfer_count: int
    coverage: str


class CreditAlignmentOut(_Strict):
    alignment_id: str
    window_index: int
    owner_token: str
    anchor_token: str
    alignment: str
    owner_status: str
    analytical_outcome: str
    owner_paid_quantity: int
    declared_repayment_quantity: int
    observed_transfer_count: int
    gap_milli: int
    coverage: str


class CreditRelationshipsSummaryOut(_Strict):
    run_id: str
    publication_id: str
    digest: str
    schema_version: str
    window_tick: int
    window_count: int
    relationship_count: int
    claim_count: int
    performance_count: int
    distribution_count: int
    counterparty_count: int
    alignment_count: int
    claim_event_count: int
    transfer_event_count: int
    evidence_coverage: str
    owner_coverage: str
    relationship_coverage: str
    performance_coverage: str
    distribution_coverage: str
    counterparty_coverage: str
    alignment_coverage: str
    coverage: str
    truncated: bool


class _PageOut(_Strict):
    run_id: str
    publication_id: str
    window_index: int | None
    next_cursor: str | None
    coverage: str


class CreditRelationshipsPageOut(_PageOut):
    rows: tuple[CreditRelationshipOut, ...] = Field(default_factory=tuple)


class CreditClaimsPageOut(_PageOut):
    rows: tuple[CreditClaimOut, ...] = Field(default_factory=tuple)


class CreditPerformancesPageOut(_PageOut):
    rows: tuple[CreditPerformanceOut, ...] = Field(default_factory=tuple)


class CreditDistributionsPageOut(_PageOut):
    rows: tuple[CreditDistributionOut, ...] = Field(default_factory=tuple)


class CreditCounterpartiesPageOut(_PageOut):
    rows: tuple[CreditCounterpartyOut, ...] = Field(default_factory=tuple)


class CreditAlignmentPageOut(_PageOut):
    rows: tuple[CreditAlignmentOut, ...] = Field(default_factory=tuple)
