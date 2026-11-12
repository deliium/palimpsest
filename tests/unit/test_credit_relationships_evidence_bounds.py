"""Property bounds for credit evidence harvests."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.credit_relationships_events import (
    credit_evidence_digest,
    credit_evidence_rows_from_events,
)
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


@given(st.lists(st.integers(min_value=0, max_value=8), max_size=12))
@settings(max_examples=60)
def test_claim_count_never_exceeds_cap(counts: list[int]) -> None:
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
    policy = CreditRelationshipsAnalysisPolicy(max_claim_events=5)
    harvest = credit_evidence_rows_from_events(events, policy=policy)
    assert harvest.claim_count <= 5
    assert harvest.transfer_count == 0
    assert len(harvest.notices) <= 8


@given(st.lists(st.integers(min_value=0, max_value=8), max_size=12))
@settings(max_examples=60)
def test_transfer_count_never_exceeds_cap(counts: list[int]) -> None:
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
    policy = CreditRelationshipsAnalysisPolicy(max_transfer_events=5)
    harvest = credit_evidence_rows_from_events(events, policy=policy)
    assert harvest.transfer_count <= 5
    assert harvest.claim_count == 0


@given(st.lists(st.integers(min_value=0, max_value=4), max_size=6))
@settings(max_examples=40)
def test_digest_is_stable(counts: list[int]) -> None:
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
    first = credit_evidence_rows_from_events(events)
    second = credit_evidence_rows_from_events(list(reversed(events)))
    assert credit_evidence_digest(first) == credit_evidence_digest(second)
