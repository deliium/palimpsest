"""Completed-run composition of credit analysis."""

# mypy: ignore-errors


from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.credit_relationships import (
    apply_credit_relationship_update,
)
from analysis.credit_relationships_analysis import CreditRelationshipsAnalysis
from experiments.credit_relationships_completed_run import (
    build_completed_run_credit_relationships_analysis,
)
from tests.unit.credit_relationships_analysis_helpers import (
    ANCHOR,
    completed,
    frame,
    given,
    talked,
)
from tests.unit.test_credit_relationships_helpers import OWNER, claim


def _ledger():
    return apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(opened_tick=0),)
    )


def _events(anchor: str = ANCHOR):
    return [
        completed("evt-0", give_ids=("item-1",), give_kinds=("food",), tick=0),
        talked("evt-1", frame(anchor=anchor), tick=0, sequence=1),
        given("evt-2", item_id="item-1", tick=1),
    ]


def test_missing_events_are_rejected() -> None:
    with pytest.raises(
        ValueError, match="credit_relationships_analysis_missing_events"
    ):
        build_completed_run_credit_relationships_analysis(
            SimpleNamespace(), committed_events=None, run_id="run-1"
        )


def test_missing_ledgers_still_yield_analysis() -> None:
    analysis = build_completed_run_credit_relationships_analysis(
        SimpleNamespace(credit_relationship_ledgers=()),
        committed_events=_events(),
        run_id="run-1",
    )
    assert type(analysis) is CreditRelationshipsAnalysis
    assert analysis.relationships == ()
    assert analysis.owner_coverage.value == "missing"


def test_owner_rows_are_injected() -> None:
    ledger = _ledger()
    analysis = build_completed_run_credit_relationships_analysis(
        SimpleNamespace(credit_relationship_ledgers=(ledger,)),
        committed_events=_events(anchor=ledger.rows[0].anchor),
        run_id="run-1",
    )
    assert len(analysis.relationships) == 1
    assert analysis.owner_coverage.value == "complete"


def test_window_end_is_forwarded() -> None:
    analysis = build_completed_run_credit_relationships_analysis(
        SimpleNamespace(credit_relationship_ledgers=(_ledger(),)),
        committed_events=_events(),
        run_id="run-1",
        window_end=64,
    )
    assert analysis.window_tick == 64
