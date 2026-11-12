"""Bounded credit relationship analysis composition."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.credit_relationships_analysis import (
    credit_relationships_analysis_digest,
    empty_credit_relationships_analysis,
    harvest_credit_relationships_analysis,
)
from analysis.credit_relationships_contract import (
    CreditCoverage,
    CreditOwnerStatus,
)
from analysis.credit_relationships_expectations import join_credit_relationships
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from tests.unit.credit_relationships_analysis_helpers import (
    completed,
    frame,
    given,
    talked,
)
from tests.unit.test_credit_relationships_expectations import _owner
from world.credit_relationships import CreditFrameAct

pytestmark = pytest.mark.unit


def _events():
    return [
        completed("evt-0", give_ids=("item-1",), give_kinds=("food",), tick=0),
        talked("evt-1", frame(), tick=0, sequence=1),
        talked("evt-2", frame(act=CreditFrameAct.ACCEPT), tick=1, sequence=0),
        given("evt-3", item_id="item-1", tick=2),
    ]


def test_empty_input_returns_explicit_missing_analysis() -> None:
    analysis = harvest_credit_relationships_analysis(committed_events=[])
    expected = empty_credit_relationships_analysis()
    assert analysis == expected
    assert analysis.coverage is CreditCoverage.MISSING
    assert analysis.relationships == ()
    assert analysis.claim_count == 0


def test_full_harvest_exposes_every_family() -> None:
    analysis = harvest_credit_relationships_analysis(
        committed_events=_events(),
        owner_inputs=(_owner(status=CreditOwnerStatus.REPAID),),
    )
    assert analysis.claim_count == 2
    assert analysis.transfer_count == 1
    assert len(analysis.performances) == 1
    assert len(analysis.distributions) == 2
    assert len(analysis.counterparties) == 1
    assert len(analysis.relationships) == 1
    assert len(analysis.alignments) == 1
    assert analysis.window_tick == 2


def test_digest_is_stable_and_sensitive_to_terms() -> None:
    first = harvest_credit_relationships_analysis(committed_events=_events())
    second = harvest_credit_relationships_analysis(committed_events=_events())
    assert credit_relationships_analysis_digest(first) == (
        credit_relationships_analysis_digest(second)
    )
    changed = harvest_credit_relationships_analysis(
        committed_events=[
            talked("evt-1", frame(repayment_quantity=4), tick=0),
            talked(
                "evt-2",
                frame(act=CreditFrameAct.ACCEPT, repayment_quantity=4),
                tick=1,
                sequence=1,
            ),
        ]
    )
    assert credit_relationships_analysis_digest(first) != (
        credit_relationships_analysis_digest(changed)
    )


def test_shuffled_event_order_normalizes_deterministically() -> None:
    forward = harvest_credit_relationships_analysis(committed_events=_events())
    backward = harvest_credit_relationships_analysis(
        committed_events=list(reversed(_events()))
    )
    assert credit_relationships_analysis_digest(forward) == (
        credit_relationships_analysis_digest(backward)
    )


def test_owner_inputs_without_evidence_join_not_applicable() -> None:
    analysis = harvest_credit_relationships_analysis(
        committed_events=[talked("evt-1", frame(), tick=0)],
        owner_inputs=(_owner(window_index=9),),
    )
    assert analysis.alignments[0].alignment.value == "not_applicable"
    assert analysis.relationship_coverage is CreditCoverage.PARTIAL


def test_clean_join_analysis_is_complete() -> None:
    analysis = harvest_credit_relationships_analysis(
        committed_events=_events(),
        owner_inputs=(_owner(),),
        policy=CreditRelationshipsAnalysisPolicy(min_distribution_samples=1),
    )
    assert analysis.coverage is CreditCoverage.COMPLETE


def test_no_owner_rows_marks_owner_missing() -> None:
    analysis = harvest_credit_relationships_analysis(committed_events=_events())
    assert analysis.owner_coverage is CreditCoverage.MISSING
    assert "credit_missing_owner_rows" in analysis.notices
    assert analysis.relationships == ()


def test_join_keeps_owner_rows_without_performance() -> None:
    joined = join_credit_relationships([_owner()], [])
    assert len(joined.relationships) == 1
    assert joined.alignments[0].alignment.value == "not_applicable"
