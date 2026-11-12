"""Token-only accounting owner export tests."""

# mypy: ignore-errors

from __future__ import annotations

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_RECORD_PREDICATE,
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.models import AgentId
from simulation.accounting_ledgers_export import accounting_owner_export


def test_export_contains_tokens_only() -> None:
    owner = AgentId("owner-raw-id")
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-raw-id"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(("xch_food", ACCOUNTING_RECORD_PREDICATE, "in2"),),
        tick=31,
    )
    ledger = apply_accounting_ledger_update(
        owner_id=owner, tick=31, records=(observation,)
    )
    rows = accounting_owner_export((ledger,))
    assert len(rows) == 1
    row = rows[0]
    assert row.owner_token.startswith("acco-")
    assert "owner-raw-id" not in row.owner_token
    assert "artifact-raw-id" not in row.record_token
    assert row.window_index == 0
    assert row.entry_kind == "exchange"
