"""Property helpers for detached accounting evidence reconstruction."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from analysis.accounting_ledgers_events import (
    accounting_evidence_digest,
    accounting_evidence_rows_from_events,
)
from tests.unit.test_accounting_ledgers_events import _talked


def test_permuting_committed_events_preserves_digest() -> None:
    events = (
        _talked("ev-a", tick=1),
        _talked("ev-b", tick=2, sequence=1),
        _talked("ev-c", tick=3, sequence=2),
    )
    baseline = accounting_evidence_digest(
        accounting_evidence_rows_from_events(events, run_id="run-1")
    )
    for permutation in (
        (events[2], events[0], events[1]),
        (events[1], events[2], events[0]),
        (events[0], events[2], events[1]),
    ):
        candidate = accounting_evidence_digest(
            accounting_evidence_rows_from_events(permutation, run_id="run-1")
        )
        assert candidate == baseline


def test_hypothesis_permutations_preserve_digest() -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    events = (
        _talked("ev-a", tick=1),
        _talked("ev-b", tick=2, sequence=1),
        _talked("ev-c", tick=3, sequence=2),
    )
    baseline = accounting_evidence_digest(
        accounting_evidence_rows_from_events(events, run_id="run-1")
    )

    @settings(max_examples=25, deadline=None)
    @given(st.permutations(events))
    def _check(order) -> None:
        assert (
            accounting_evidence_digest(
                accounting_evidence_rows_from_events(tuple(order), run_id="run-1")
            )
            == baseline
        )

    _check()


def test_duplicate_event_tokens_fail_closed() -> None:
    from analysis.accounting_ledgers_contract import AccountingAnalysisError

    events = (_talked("ev-a", tick=1), _talked("ev-a", tick=2, sequence=1))
    with pytest.raises(AccountingAnalysisError):
        accounting_evidence_rows_from_events(events, run_id="run-1")


def test_missing_run_id_fails_closed() -> None:
    from analysis.accounting_ledgers_contract import AccountingAnalysisError

    with pytest.raises(AccountingAnalysisError):
        accounting_evidence_rows_from_events((), run_id="")
