"""Accounting evidence candidate bridge tests."""

# mypy: ignore-errors

from __future__ import annotations

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_RECORD_PREDICATE,
    AccountingEntryKind,
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_evidence_candidates,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.cognition.evidence_testimony import (
    EvidenceObservedReference,
    EvidencePriorAgreement,
)
from agents.models import AgentId

OWNER = AgentId("agent-owner")
OTHER = AgentId("agent-other")


def _ledger():
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-1"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(
            ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in3"),
            ("dbt_material", ACCOUNTING_RECORD_PREDICATE, "pay2"),
        ),
        tick=1,
    )
    return apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )


def test_candidates_are_bounded_owner_scoped_and_read_only() -> None:
    ledger = _ledger()
    before = ledger
    candidates = accounting_evidence_candidates(ledger, owner_id=OWNER, tick=2)
    assert 0 < len(candidates) <= 4
    assert ledger == before
    assert all(
        isinstance(candidate, (EvidenceObservedReference, EvidencePriorAgreement))
        for candidate in candidates
    )
    assert all(
        getattr(candidate, "owner_id", None) == OWNER.value
        for candidate in candidates
    )


def test_record_candidates_map_integrity_and_debt_uses_prior_agreement() -> None:
    ledger = _ledger()
    candidates = accounting_evidence_candidates(ledger, owner_id=OWNER, tick=2)
    kinds = {type(candidate) for candidate in candidates}
    assert EvidenceObservedReference in kinds
    assert EvidencePriorAgreement in kinds


def test_foreign_owner_is_rejected() -> None:
    import pytest

    ledger = _ledger()
    from agents.cognition.accounting_ledgers import AccountingLedgerError

    with pytest.raises(AccountingLedgerError):
        accounting_evidence_candidates(
            ledger, owner_id=AgentId("someone-else"), tick=2
        )


def test_debt_candidate_carries_counterparty_token_only() -> None:
    ledger = _ledger()
    candidates = accounting_evidence_candidates(ledger, owner_id=OWNER, tick=2)
    debt = next(
        candidate
        for candidate in candidates
        if isinstance(candidate, EvidencePriorAgreement)
    )
    assert debt.kind == "commitment"
    assert len(debt.parties) == 2


def test_all_entry_kinds_have_a_candidate_projection() -> None:
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-2"),
        record_genre="inventory_record",
        integrity=AccountingRecordIntegrity.PARTIALLY_LOST,
        content_revision=0,
        relations=(
            ("inv_tool", ACCOUNTING_RECORD_PREDICATE, "hold1"),
            ("org_medical", ACCOUNTING_RECORD_PREDICATE, "hold2"),
            ("ctb_generic", ACCOUNTING_RECORD_PREDICATE, "ctb1"),
        ),
        tick=1,
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    assert len(ledger.entries) == 3
    candidates = accounting_evidence_candidates(ledger, owner_id=OWNER, tick=2)
    assert len(candidates) == 3
    assert all(
        entry.terms.entry_kind
        in {
            AccountingEntryKind.INVENTORY,
            AccountingEntryKind.ORGANIZATIONAL_RESOURCE,
            AccountingEntryKind.CONTRIBUTION,
        }
        for entry in ledger.entries
    )
