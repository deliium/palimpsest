"""Locked detached credit analysis policy boundaries."""

from __future__ import annotations

import pytest

from analysis.credit_relationships_contract import (
    CreditRelationshipAnalysisError,
)
from analysis.credit_relationships_policy import (
    CREDIT_RELATIONSHIPS_ANALYSIS_LOCKED_POLICY,
    CreditRelationshipsAnalysisPolicy,
    default_credit_relationships_analysis_policy,
    window_bounds,
    window_index_for_tick,
)

pytestmark = pytest.mark.unit


def test_locked_defaults_are_exact() -> None:
    assert dict(CREDIT_RELATIONSHIPS_ANALYSIS_LOCKED_POLICY) == {
        "window_ticks": 32,
        "max_windows": 512,
        "max_claim_events": 200_000,
        "max_transfer_events": 200_000,
        "max_owner_rows": 4_096,
        "max_claim_rows": 4_096,
        "max_relationship_rows": 8_192,
        "max_performance_rows": 8_192,
        "max_distribution_rows": 8_192,
        "max_counterparty_rows": 1_024,
        "max_alignment_rows": 4_096,
        "max_owners": 4_096,
        "max_item_kinds": 1_024,
        "min_distribution_samples": 4,
        "max_ratio_milli": 64_000,
        "alignment_high_milli": 750,
        "alignment_low_milli": 250,
    }
    assert default_credit_relationships_analysis_policy() is not None


@pytest.mark.parametrize(
    ("field", "minimum", "maximum"),
    (
        ("window_ticks", 1, 4_096),
        ("max_windows", 1, 65_536),
        ("max_claim_events", 1, 1_000_000),
        ("max_transfer_events", 1, 1_000_000),
        ("max_owner_rows", 1, 16_384),
        ("max_claim_rows", 1, 16_384),
        ("max_relationship_rows", 1, 65_536),
        ("max_performance_rows", 1, 65_536),
        ("max_distribution_rows", 1, 65_536),
        ("max_counterparty_rows", 1, 16_384),
        ("max_alignment_rows", 1, 65_536),
        ("max_owners", 1, 16_384),
        ("max_item_kinds", 1, 1_024),
        ("min_distribution_samples", 1, 1_000),
        ("max_ratio_milli", 1, 1_000_000),
    ),
)
def test_every_cap_accepts_boundaries_and_rejects_outside(
    field: str, minimum: int, maximum: int
) -> None:
    CreditRelationshipsAnalysisPolicy(**{field: minimum})
    CreditRelationshipsAnalysisPolicy(**{field: maximum})
    with pytest.raises(CreditRelationshipAnalysisError):
        CreditRelationshipsAnalysisPolicy(**{field: minimum - 1})
    with pytest.raises(CreditRelationshipAnalysisError):
        CreditRelationshipsAnalysisPolicy(**{field: maximum + 1})


def test_alignment_thresholds_must_be_ordered() -> None:
    CreditRelationshipsAnalysisPolicy(
        alignment_low_milli=0, alignment_high_milli=1
    )
    CreditRelationshipsAnalysisPolicy(
        alignment_low_milli=999, alignment_high_milli=1_000
    )
    with pytest.raises(CreditRelationshipAnalysisError):
        CreditRelationshipsAnalysisPolicy(
            alignment_low_milli=800, alignment_high_milli=700
        )


def test_window_helpers_bound_ticks() -> None:
    policy = CreditRelationshipsAnalysisPolicy()
    assert window_index_for_tick(0, policy) == 0
    assert window_index_for_tick(31, policy) == 0
    assert window_index_for_tick(32, policy) == 1
    assert window_bounds(0, policy) == (0, 32)
    assert window_bounds(1, policy) == (32, 64)
    with pytest.raises(CreditRelationshipAnalysisError):
        window_index_for_tick(-1, policy)
    with pytest.raises(CreditRelationshipAnalysisError):
        window_index_for_tick(policy.max_windows * policy.window_ticks, policy)
    with pytest.raises(CreditRelationshipAnalysisError):
        window_bounds(policy.max_windows, policy)
