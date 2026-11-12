"""Hypothesis cap bounds for accounting folds and detection."""

# mypy: ignore-errors

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from agents.cognition.accounting_ledgers import (
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.models import AgentId

OWNER = AgentId("owner-1")


@settings(max_examples=60, deadline=None)
@given(
    st.text(max_size=40),
    st.text(max_size=40),
    st.text(max_size=40),
)
def test_arbitrary_record_tokens_never_escape_caps(
    subject: str, predicate: str, object_token: str
) -> None:
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=((subject, predicate, object_token),),
        tick=1,
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    assert len(ledger.entries) <= 32
    assert len(ledger.notices) <= 8
    for entry in ledger.entries:
        assert 1 <= entry.terms.quantity <= 64
        assert 0 <= entry.confidence_milli <= 1_000
