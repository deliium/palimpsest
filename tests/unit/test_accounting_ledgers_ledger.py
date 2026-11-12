"""Owner-scoped accounting ledger fold tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_RECORD_PREDICATE,
    AccountingAct,
    AccountingClaim,
    AccountingClaimSource,
    AccountingDirection,
    AccountingEntryKind,
    AccountingLedgerError,
    AccountingRecordAssessment,
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_counterparty_token,
    accounting_record_token,
    apply_accounting_ledger_update,
    empty_accounting_ledger,
    parse_accounting_record,
    validate_accounting_ledger_caps,
)
from agents.models import AgentId

OWNER = AgentId("agent-owner")
OTHER = AgentId("agent-other")


def _observation(
    *,
    artifact: str = "artifact-1",
    relations: tuple[tuple[str, str, str], ...] = (
        ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in3"),
    ),
    integrity: AccountingRecordIntegrity = AccountingRecordIntegrity.INTACT,
    content_revision: int = 0,
    tick: int = 1,
    genre: str | None = "agreement",
) -> AccountingRecordObservation:
    return AccountingRecordObservation(
        record_token=accounting_record_token(artifact),
        record_genre=genre,
        integrity=integrity,
        content_revision=content_revision,
        relations=relations,
        tick=tick,
    )


def test_parse_record_ignores_non_accounting_and_malformed_relations() -> None:
    observation = _observation(
        relations=(
            ("xch_food", "other_predicate", "in3"),
            ("bad", ACCOUNTING_RECORD_PREDICATE, "in3"),
            ("xch_candy", ACCOUNTING_RECORD_PREDICATE, "in3"),
            ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in3"),
        )
    )
    terms = parse_accounting_record(observation)
    assert len(terms) == 1
    assert terms[0].entry_kind is AccountingEntryKind.EXCHANGE
    assert terms[0].direction is AccountingDirection.INFLOW
    assert terms[0].quantity == 3


def test_genre_less_artifacts_are_not_accounting_records() -> None:
    observation = _observation(genre=None)
    assert parse_accounting_record(observation) == ()
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    assert ledger.entries == ()


def test_all_five_entry_kinds_from_records() -> None:
    observation = _observation(
        relations=(
            ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in1"),
            ("dbt_material", ACCOUNTING_RECORD_PREDICATE, "pay2"),
            ("inv_tool", ACCOUNTING_RECORD_PREDICATE, "hold3"),
            ("org_medical", ACCOUNTING_RECORD_PREDICATE, "hold4"),
            ("ctb_generic", ACCOUNTING_RECORD_PREDICATE, "ctb5"),
        )
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    kinds = {entry.terms.entry_kind for entry in ledger.entries}
    assert kinds == set(AccountingEntryKind)
    assert all(
        entry.source is AccountingClaimSource.DIRECT_RECORD
        for entry in ledger.entries
    )


def test_entries_are_deterministic_and_capped() -> None:
    relation = ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in1")
    observations = tuple(
        _observation(artifact=f"artifact-{index}", relations=(relation,))
        for index in range(40)
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=3, records=observations
    )
    assert len(ledger.entries) == 32
    assert "accounting_ledger_truncated" in ledger.notices
    validate_accounting_ledger_caps(ledger)
    assert ledger.entries == tuple(
        sorted(ledger.entries, key=lambda entry: (entry.anchor, entry.entry_id))
    )


def test_commitments_produce_payable_and_receivable_entries() -> None:
    class Commitment:
        debtor_id = OWNER.value
        creditor_id = OTHER.value
        item_kind = "food"
        quantity = 4
        status = "open"
        due_tick = 20

    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=2, commitments=(Commitment(),)
    )
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.terms.entry_kind is AccountingEntryKind.DEBT
    assert entry.terms.direction is AccountingDirection.PAYABLE
    assert entry.counterparty_token == accounting_counterparty_token(OTHER.value)


def test_contributions_and_organization_resources_produce_entries() -> None:
    class Contribution:
        actor_id = OWNER.value
        labor_delta = 3
        item_id = "item-1"
        tick = 5

    class Resource:
        anchor_id = "resource-1"
        resource_kind = "material"
        access_belief = "shared"

    class Organization:
        concept_id = "concept-1"
        resources = (Resource(),)

    ledger = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=5,
        contributions=(Contribution(),),
        organizations=(Organization(),),
    )
    kinds = {entry.terms.entry_kind for entry in ledger.entries}
    assert kinds == {
        AccountingEntryKind.CONTRIBUTION,
        AccountingEntryKind.ORGANIZATIONAL_RESOURCE,
    }
    organization = next(
        entry
        for entry in ledger.entries
        if entry.terms.entry_kind is AccountingEntryKind.ORGANIZATIONAL_RESOURCE
    )
    assert organization.organization_token is not None


def test_valuations_attach_only_to_matching_entries() -> None:
    class Valuation:
        item_kind = "food"
        reservation = 2.5
        counterparty_id = OTHER.value

    ledger = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=1,
        records=(_observation(),),
        valuations=(Valuation(),),
    )
    assert ledger.entries[0].terms.valuation_milli == 2_500

    unmatched = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=1,
        records=(_observation(),),
        valuations=(
            type(
                "Valuation",
                (),
                {
                    "item_kind": "tool",
                    "reservation": 1,
                    "counterparty_id": OTHER.value,
                },
            )(),
        ),
    )
    assert unmatched.entries[0].terms.valuation_milli is None
    assert "accounting_item_unresolved" in unmatched.notices


def test_damaged_integrity_is_an_owner_appraisal() -> None:
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=1,
        records=(
            _observation(integrity=AccountingRecordIntegrity.PARTIALLY_LOST),
        ),
    )
    assert ledger.entries[0].assessment is AccountingRecordAssessment.DAMAGED
    assert ledger.entries[0].integrity is AccountingRecordIntegrity.PARTIALLY_LOST


def test_newer_record_revision_marks_outdated() -> None:
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=1,
        records=(_observation(content_revision=0),),
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER,
        tick=2,
        records=(_observation(content_revision=1),),
        prior=ledger,
    )
    assert ledger.entries[0].assessment is AccountingRecordAssessment.OUTDATED


def test_same_anchor_disagreement_marks_suspected_fraudulent() -> None:
    first = _observation(
        relations=(("xch_food", ACCOUNTING_RECORD_PREDICATE, "in1"),)
    )
    second = _observation(
        relations=(("xch_food", ACCOUNTING_RECORD_PREDICATE, "in9"),)
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(first, second)
    )
    assert len(ledger.entries) == 1
    assert (
        ledger.entries[0].assessment
        is AccountingRecordAssessment.SUSPECTED_FRAUDULENT
    )


def test_contribution_disagreement_marks_contradicted() -> None:
    class Contribution:
        actor_id = OWNER.value
        item_id = "item-1"
        tick = 5

    first = type(
        "Contribution",
        (),
        {
            "actor_id": OWNER.value,
            "labor_delta": 2,
            "item_id": "item-1",
            "tick": 5,
        },
    )()
    second = type(
        "Contribution",
        (),
        {
            "actor_id": OWNER.value,
            "labor_delta": 7,
            "item_id": "item-1",
            "tick": 5,
        },
    )()
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=5, contributions=(first,)
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=5, contributions=(second,), prior=ledger
    )
    assert ledger.entries[0].assessment is AccountingRecordAssessment.CONTRADICTED


def test_dispute_claim_requires_confidence_and_keeps_row() -> None:
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(_observation(),)
    )
    entry = ledger.entries[0]
    claim = AccountingClaim(
        anchor=entry.anchor,
        terms=entry.terms,
        act=AccountingAct.DISPUTE_ENTRY,
        source=AccountingClaimSource.COMMUNICATED,
        confidence_milli=900,
        tick=2,
        counterparty_token=accounting_counterparty_token(OTHER.value),
    )
    disputed = apply_accounting_ledger_update(
        owner_id=OWNER, tick=2, claims=(claim,), prior=ledger
    )
    assert disputed.entries[0].assessment is (
        AccountingRecordAssessment.SUSPECTED_FRAUDULENT
    )
    assert disputed.entries[0].confidence_milli == 700
    assert len(disputed.entries[0].claims) == 1

    weak = AccountingClaim(
        anchor=entry.anchor,
        terms=entry.terms,
        act=AccountingAct.DISPUTE_ENTRY,
        source=AccountingClaimSource.DIRECT_RECORD,
        confidence_milli=300,
        tick=2,
    )
    result = apply_accounting_ledger_update(
        owner_id=OWNER, tick=2, claims=(weak,), prior=ledger
    )
    assert result.entries[0].revisions[-1].reason_code == "disputed"


def test_retract_keeps_history_and_clears_confidence() -> None:
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(_observation(),)
    )
    entry = ledger.entries[0]
    claim = AccountingClaim(
        anchor=entry.anchor,
        terms=entry.terms,
        act=AccountingAct.RETRACT_ENTRY,
        source=AccountingClaimSource.DIRECT_RECORD,
        confidence_milli=900,
        tick=3,
    )
    retracted = apply_accounting_ledger_update(
        owner_id=OWNER, tick=3, claims=(claim,), prior=ledger
    )
    assert retracted.entries[0].confidence_milli == 0
    assert retracted.entries[0].revisions[-1].reason_code == "retracted"


def test_double_fold_is_byte_identical() -> None:
    observation = _observation()
    first = apply_accounting_ledger_update(
        owner_id=OWNER, tick=4, records=(observation,)
    )
    second = apply_accounting_ledger_update(
        owner_id=OWNER, tick=4, records=(observation,), prior=first
    )
    assert first == second


def test_foreign_prior_and_malformed_rows_are_rejected() -> None:
    with pytest.raises(AccountingLedgerError):
        apply_accounting_ledger_update(
            owner_id=OWNER,
            tick=1,
            prior=empty_accounting_ledger(OTHER),
        )
    with pytest.raises(AccountingLedgerError):
        apply_accounting_ledger_update(
            owner_id=OWNER,
            tick=1,
            claims=(object(),),  # type: ignore[arg-type]
        )


def test_invalid_tokens_are_counted_and_bounded() -> None:
    observation = _observation(
        relations=(
            ("xch_candy", ACCOUNTING_RECORD_PREDICATE, "in1"),
            ("xch_food", ACCOUNTING_RECORD_PREDICATE, "in1"),
        )
    )
    ledger = apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )
    assert ledger.invalid_tokens == 1
    assert "accounting_record_invalid" in ledger.notices


def test_hypothesis_arbitrary_tokens_never_raise_or_exceed_caps() -> None:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    @settings(max_examples=50, deadline=None)
    @given(
        st.text(max_size=40),
        st.text(max_size=40),
        st.text(max_size=40),
    )
    def _check(subject: str, predicate: str, object_token: str) -> None:
        observation = _observation(
            relations=((subject, predicate, object_token),)
        )
        ledger = apply_accounting_ledger_update(
            owner_id=OWNER, tick=1, records=(observation,)
        )
        assert len(ledger.entries) <= 32
        assert len(ledger.notices) <= 8

    _check()
