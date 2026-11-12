"""Hypothesis cap bounds for credit evidence and analysis families."""

# mypy: ignore-errors


from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.credit_relationships_contract import CreditCoverage
from analysis.credit_relationships_events import credit_evidence_rows_from_events
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from tests.unit.credit_relationships_analysis_helpers import (
    frame,
    talked,
)
from tests.unit.credit_relationships_analysis_helpers import (
    given as given_event,
)

pytestmark = pytest.mark.unit


@given(st.lists(st.integers(min_value=0, max_value=6), max_size=10))
@settings(max_examples=50)
def test_claim_cap_is_a_sorted_partial_prefix(counts: list[int]) -> None:
    events = []
    for group, count in enumerate(counts):
        for index in range(count):
            events.append(
                talked(
                    f"evt-{group}-{index}",
                    frame(opened_tick=index),
                    tick=group,
                    sequence=index,
                )
            )
    policy = CreditRelationshipsAnalysisPolicy(max_claim_events=4)
    harvest = credit_evidence_rows_from_events(events, policy=policy)
    assert harvest.claim_count <= 4
    assert harvest.claims == tuple(
        sorted(
            harvest.claims,
            key=lambda row: (row.tick, row.event_token, row.claim_id),
        )
    )
    if len(events) > 4:
        assert "credit_evidence_truncated" in harvest.notices
        assert harvest.coverage is CreditCoverage.PARTIAL


@given(st.lists(st.integers(min_value=0, max_value=6), max_size=10))
@settings(max_examples=50)
def test_transfer_cap_is_a_sorted_partial_prefix(counts: list[int]) -> None:
    events = []
    for group, count in enumerate(counts):
        for index in range(count):
            events.append(
                given_event(
                    f"evt-{group}-{index}",
                    item_id=f"item-{group}-{index}",
                    tick=group,
                    sequence=index,
                )
            )
    policy = CreditRelationshipsAnalysisPolicy(max_transfer_events=4)
    harvest = credit_evidence_rows_from_events(events, policy=policy)
    assert harvest.transfer_count <= 4
    assert harvest.transfers == tuple(
        sorted(harvest.transfers, key=lambda row: (row.tick, row.event_token))
    )


@given(st.lists(st.integers(min_value=1, max_value=16), min_size=1, max_size=8))
@settings(max_examples=40)
def test_distribution_bins_sum_to_one_thousand(ratios: list[int]) -> None:
    from analysis.credit_relationships_detection import (
        credit_distribution_summary,
    )

    summary = credit_distribution_summary(
        ratios, policy=CreditRelationshipsAnalysisPolicy(min_distribution_samples=1)
    )
    assert sum(summary.bins) == 1_000


def test_fewer_than_four_samples_is_insufficient() -> None:
    from analysis.credit_relationships_detection import (
        credit_distribution_summary,
    )

    assert (
        credit_distribution_summary([1, 2, 3]).status.value
        == "insufficient_samples"
    )
    assert credit_distribution_summary([1, 2, 3, 4]).status.value == "available"
