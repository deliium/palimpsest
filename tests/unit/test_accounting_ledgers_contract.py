"""Contract tests for the owner-scoped accounting ledger vocabulary."""

# mypy: ignore-errors

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_ANCHOR_HEX_LEN,
    ACCOUNTING_DIRECTION_CODES,
    ACCOUNTING_ENTRY_KIND_CODES,
    ACCOUNTING_FORBIDDEN_FIELD_NAMES,
    ACCOUNTING_ITEM_KINDS,
    ACCOUNTING_LEDGERS_LOCKED_POLICY,
    ACCOUNTING_LEDGERS_POLICY_VERSION,
    ACCOUNTING_RECORD_PREDICATE,
    AccountingAct,
    AccountingClaimSource,
    AccountingDirection,
    AccountingEntryKind,
    AccountingLedgerError,
    AccountingLedgerPolicy,
    AccountingRecordAssessment,
    AccountingRecordIntegrity,
    accounting_counterparty_token,
    accounting_entry_anchor,
    accounting_entry_id,
    accounting_organization_token,
    accounting_publication_id,
    accounting_record_token,
    default_accounting_ledger_policy,
    parse_accounting_record_relation,
    require_accounting_anchor,
    require_accounting_counterparty_token,
    require_accounting_entry_id,
    require_accounting_organization_token,
    require_accounting_publication_id,
    require_accounting_record_token,
)


def test_policy_version_and_predicate_are_locked() -> None:
    assert ACCOUNTING_LEDGERS_POLICY_VERSION == "accounting-ledgers.v1"
    assert ACCOUNTING_RECORD_PREDICATE == "acc_v1"


def test_entry_kinds_are_closed_and_exact() -> None:
    assert {kind.value for kind in AccountingEntryKind} == {
        "exchange",
        "debt",
        "inventory",
        "organizational_resource",
        "contribution",
    }


def test_directions_are_closed_and_exact() -> None:
    assert {direction.value for direction in AccountingDirection} == {
        "inflow",
        "outflow",
        "holding",
        "receivable",
        "payable",
        "contribution",
    }


def test_assessments_are_closed_and_exact() -> None:
    assert {assessment.value for assessment in AccountingRecordAssessment} == {
        "unassessed",
        "consistent",
        "contradicted",
        "outdated",
        "suspected_fraudulent",
        "damaged",
    }


def test_integrity_claim_sources_and_acts_are_closed() -> None:
    assert {value.value for value in AccountingRecordIntegrity} == {
        "intact",
        "damaged",
        "partially_lost",
        "unknown",
    }
    assert {value.value for value in AccountingClaimSource} == {
        "direct_record",
        "communicated",
        "derived",
        "unknown",
    }
    assert {value.value for value in AccountingAct} == {
        "declare_entry",
        "cite_record",
        "affirm_entry",
        "dispute_entry",
        "correct_entry",
        "retract_entry",
    }


def test_policy_defaults_match_the_locked_map() -> None:
    policy = default_accounting_ledger_policy()
    assert policy is default_accounting_ledger_policy()
    for name, expected in ACCOUNTING_LEDGERS_LOCKED_POLICY.items():
        assert getattr(policy, name) == expected


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("max_entries", 33),
        ("max_claims_per_entry", 17),
        ("max_revisions_per_entry", 9),
        ("max_evidence_per_entry", 9),
        ("max_notices", 9),
        ("max_counterparties", 9),
        ("max_quantity", 65),
        ("max_valuation_milli", 64_001),
        ("max_confidence_milli", 1_001),
        ("max_record_age_ticks", 129),
        ("max_due_horizon_ticks", 65),
        ("strong_confidence_milli", 751),
        ("disputed_confidence_milli", 501),
        ("trust_neutral_milli", 501),
        ("communicated_confidence_penalty_milli", 201),
    ],
)
def test_policy_rejects_widened_values(name: str, value: int) -> None:
    with pytest.raises(AccountingLedgerError):
        AccountingLedgerPolicy(**{name: value})


def test_policy_rejects_booleans_and_floats() -> None:
    with pytest.raises(AccountingLedgerError):
        AccountingLedgerPolicy(max_entries=True)  # type: ignore[arg-type]
    with pytest.raises(AccountingLedgerError):
        AccountingLedgerPolicy(max_entries=32.0)  # type: ignore[arg-type]


def test_identifier_grammars_accept_canonical_values() -> None:
    record = accounting_record_token("artifact-1")
    organization = accounting_organization_token("concept-1")
    counterparty = accounting_counterparty_token("agent-1")
    anchor = accounting_entry_anchor(
        owner_id="owner-1",
        record_token=record,
        entry_kind=AccountingEntryKind.EXCHANGE,
        ordinal=0,
    )
    entry_id = accounting_entry_id("owner-1", anchor)
    publication = accounting_publication_id("run-1|completed=1")

    assert require_accounting_record_token(record) == record
    assert require_accounting_organization_token(organization) == organization
    assert require_accounting_counterparty_token(counterparty) == counterparty
    assert require_accounting_anchor(anchor) == anchor
    assert require_accounting_entry_id(entry_id) == entry_id
    assert require_accounting_publication_id(publication) == publication
    assert len(anchor) == len("acct-") + ACCOUNTING_ANCHOR_HEX_LEN


@pytest.mark.parametrize(
    ("validator", "value"),
    [
        (require_accounting_record_token, "accrec-"),
        (require_accounting_record_token, "accrec-0123456789ABCDEf"),
        (require_accounting_record_token, "accrec-0123456789abcdef0"),
        (require_accounting_record_token, "record-0123456789abcdef"),
        (require_accounting_organization_token, "accorg-xyz"),
        (require_accounting_counterparty_token, "accpeer-"),
        (require_accounting_anchor, "acct-0123456789abcdef0"),
        (require_accounting_entry_id, "acce-0123456789abcde"),
        (require_accounting_publication_id, "acct-pub-x"),
    ],
)
def test_identifier_grammars_reject_malformed_values(validator, value: str) -> None:
    with pytest.raises(AccountingLedgerError):
        validator(value)


def test_identifier_grammars_reject_non_strings() -> None:
    for validator in (
        require_accounting_record_token,
        require_accounting_organization_token,
        require_accounting_counterparty_token,
        require_accounting_anchor,
        require_accounting_entry_id,
        require_accounting_publication_id,
    ):
        with pytest.raises(AccountingLedgerError):
            validator(1)


def test_tokens_are_deterministic_and_distinct() -> None:
    assert accounting_record_token("artifact-1") == accounting_record_token(
        "artifact-1"
    )
    assert accounting_record_token("artifact-1") != accounting_record_token(
        "artifact-2"
    )
    anchor = accounting_entry_anchor(
        owner_id="owner-1",
        record_token=accounting_record_token("artifact-1"),
        entry_kind=AccountingEntryKind.DEBT,
        ordinal=2,
    )
    assert anchor == accounting_entry_anchor(
        owner_id="owner-1",
        record_token=accounting_record_token("artifact-1"),
        entry_kind=AccountingEntryKind.DEBT,
        ordinal=2,
    )


def test_record_grammar_accepts_every_code_combination() -> None:
    for entry_code, entry_kind in ACCOUNTING_ENTRY_KIND_CODES.items():
        for direction_code, direction in ACCOUNTING_DIRECTION_CODES.items():
            for item_kind in ACCOUNTING_ITEM_KINDS:
                subject = f"{entry_code}_{item_kind}"
                object_token = f"{direction_code}5"
                term = parse_accounting_record_relation(subject, object_token)
                assert term.entry_kind is entry_kind
                assert term.direction is direction
                assert term.item_kind == item_kind
                assert term.quantity == 5


@pytest.mark.parametrize(
    ("subject", "object_token"),
    [
        ("zzz_food", "in1"),
        ("xch_candy", "in1"),
        ("xch_food", "zz1"),
        ("xch_food", "in0"),
        ("xch_food", "in65"),
        ("xch_food", ""),
        ("xch_food", "in"),
        ("xch_food", "in-1"),
        ("xch_food", "in1 "),
        ("xch_food", "in01"),
        ("xch_food", "IN1"),
        ("xch_food", "a" * 33),
    ],
)
def test_record_grammar_rejects_invalid_pairs(
    subject: str, object_token: str
) -> None:
    with pytest.raises(AccountingLedgerError):
        parse_accounting_record_relation(subject, object_token)


def test_no_accounting_dataclass_uses_a_forbidden_field_name() -> None:
    import agents.cognition.accounting_ledgers as module

    found = []
    for name in dir(module):
        value = getattr(module, name)
        if is_dataclass(value) and isinstance(value, type):
            for field in fields(value):
                if field.name in ACCOUNTING_FORBIDDEN_FIELD_NAMES:
                    found.append(f"{name}.{field.name}")
    assert found == []


def test_digest_is_a_pure_function_of_input() -> None:
    from agents.cognition.accounting_ledgers import _digest16

    assert _digest16("material") == _digest16("material")
    assert len(_digest16("material")) == ACCOUNTING_ANCHOR_HEX_LEN
