"""Accounting frame codec and bounded attachment tests."""

# mypy: ignore-errors

from __future__ import annotations

import pytest

from agents.cognition.accounting_ledgers import (
    ACCOUNTING_RECORD_PREDICATE,
    AccountingRecordIntegrity,
    AccountingRecordObservation,
    accounting_record_token,
    apply_accounting_ledger_update,
)
from agents.cognition.accounting_ledgers_communication import (
    accounting_communicate_utterance,
    accounting_inscribe_content,
)
from agents.models import AgentId
from world.accounting_ledgers import (
    ACCOUNTING_FRAME_FIELD_COUNT,
    ACCOUNTING_FRAME_MAX_CHARS,
    ACCOUNTING_FRAME_SUBJECT,
    AccountingEntryFrame,
    AccountingFrameAct,
    AccountingFrameAssessment,
    AccountingFrameDirection,
    AccountingFrameEntryKind,
    AccountingFrameIntegrity,
    accounting_entry_relation,
    accounting_record_content,
    accounting_record_genre,
    encode_accounting_entry_frame,
    parse_accounting_entry_frame,
    parse_accounting_entry_relation,
)
from world.actions import Talk, Tell, Wait
from world.artifacts import ArtifactContent, ArtifactRelation, DurableRecordGenre
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId

OWNER = AgentId("agent-owner")
RECIPIENT = EntityId("agent-2")


def _frame() -> AccountingEntryFrame:
    return AccountingEntryFrame(
        act=AccountingFrameAct.AFFIRM_ENTRY,
        entry_anchor="acct-0123456789abcdef",
        record_token="accrec-0123456789abcdef",
        entry_kind=AccountingFrameEntryKind.EXCHANGE,
        direction=AccountingFrameDirection.INFLOW,
        item_kind="food",
        quantity=3,
        organization_token=None,
        counterparty_token="accpeer-0123456789abcdef",
        assessment=AccountingFrameAssessment.CONSISTENT,
        integrity=AccountingFrameIntegrity.INTACT,
        confidence_milli=700,
        tick=4,
        revision=1,
        record_genre="agreement",
    )


def _ledger():
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-1"),
        record_genre="agreement",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(("xch_food", ACCOUNTING_RECORD_PREDICATE, "in3"),),
        tick=1,
    )
    return apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )


def _talk(relations=()) -> Talk:
    return Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("agent-owner"),
            relations=relations,
        ),
    )


def test_frame_round_trip_is_exactly_sixteen_parts() -> None:
    frame = _frame()
    encoded = encode_accounting_entry_frame(frame)
    assert len(encoded.split(":")) == ACCOUNTING_FRAME_FIELD_COUNT == 16
    assert len(encoded) <= ACCOUNTING_FRAME_MAX_CHARS
    assert parse_accounting_entry_frame(encoded) == frame


@pytest.mark.parametrize("delta", [-1, 1])
def test_frame_rejects_wrong_part_count(delta: int) -> None:
    parts = encode_accounting_entry_frame(_frame()).split(":")
    if delta < 0:
        parts = parts[:-1]
    else:
        parts = [*parts, "none"]
    with pytest.raises(ValueError):
        parse_accounting_entry_frame(":".join(parts))


def test_frame_rejects_whitespace_control_and_unknown_enums() -> None:
    encoded = encode_accounting_entry_frame(_frame())
    for candidate in (
        encoded + " ",
        encoded.replace("food", "Food"),
        encoded.replace("affirm_entry", "bogus"),
        encoded.replace("inflow", "sideways"),
        encoded.replace("consistent", "true"),
    ):
        with pytest.raises(ValueError):
            parse_accounting_entry_frame(candidate)
    with pytest.raises(ValueError):
        parse_accounting_entry_frame(encoded.replace(":4", ":-1", 1))


def test_frame_rejects_quantity_confidence_and_oversize_bounds() -> None:
    with pytest.raises(ValueError):
        AccountingEntryFrame(
            **{**_frame_kwargs(), "quantity": 0}
        )
    with pytest.raises(ValueError):
        AccountingEntryFrame(
            **{**_frame_kwargs(), "quantity": 65}
        )
    with pytest.raises(ValueError):
        AccountingEntryFrame(
            **{**_frame_kwargs(), "confidence_milli": 1_001}
        )
    with pytest.raises(ValueError):
        parse_accounting_entry_frame("acc_v1:" + "a" * 400)


def _frame_kwargs() -> dict:
    return {
        "act": AccountingFrameAct.DECLARE_ENTRY,
        "entry_anchor": "acct-0123456789abcdef",
        "record_token": None,
        "entry_kind": AccountingFrameEntryKind.DEBT,
        "direction": AccountingFrameDirection.PAYABLE,
        "item_kind": "food",
        "quantity": 1,
        "organization_token": None,
        "counterparty_token": None,
        "assessment": AccountingFrameAssessment.UNASSESSED,
        "integrity": AccountingFrameIntegrity.UNKNOWN,
        "confidence_milli": 500,
        "tick": 0,
        "revision": 0,
        "record_genre": None,
    }


def test_relation_helpers_round_trip_and_ignore_unrelated() -> None:
    relation = accounting_entry_relation(_frame())
    assert relation.subject == ACCOUNTING_FRAME_SUBJECT
    assert parse_accounting_entry_relation(relation) == _frame()
    unrelated = ArtifactRelation(subject="xch_food", predicate="acc_v1", object="in1")
    from world.communications import CommunicationRelation

    assert (
        parse_accounting_entry_relation(
            CommunicationRelation(
                subject="other", predicate="x", object="y"
            )
        )
        is None
    )
    assert unrelated.predicate == ACCOUNTING_RECORD_PREDICATE


def test_record_content_builds_validated_acc_relations() -> None:
    content = accounting_record_content(
        (("xch_food", "in3"), ("dbt_material", "pay2"))
    )
    assert len(content.relations) == 2
    assert all(
        relation.predicate == ACCOUNTING_RECORD_PREDICATE
        for relation in content.relations
    )
    assert content.marks == ()
    with pytest.raises(ValueError):
        accounting_record_content((("bad", "in1"),))
    with pytest.raises(ValueError):
        accounting_record_content((("xch_food", "in0"),))


def test_record_genre_uses_existing_values_only() -> None:
    assert accounting_record_genre(AccountingFrameEntryKind.EXCHANGE) == "agreement"
    assert accounting_record_genre(AccountingFrameEntryKind.DEBT) == "agreement"
    assert (
        accounting_record_genre(AccountingFrameEntryKind.INVENTORY)
        == "inventory_record"
    )
    assert (
        accounting_record_genre(
            AccountingFrameEntryKind.ORGANIZATIONAL_RESOURCE
        )
        == "inventory_record"
    )
    assert (
        accounting_record_genre(AccountingFrameEntryKind.CONTRIBUTION)
        == "inventory_record"
    )
    DurableRecordGenre("agreement")


def test_speech_attachment_only_touches_talk_or_tell() -> None:
    ledger = _ledger()
    for command in (_talk(), Tell(recipient_id=RECIPIENT, utterance=_talk().utterance)):
        updated = accounting_communicate_utterance(
            command, owner_id=OWNER, ledger=ledger, tick=1
        )
        assert type(updated) is type(command)
        assert updated.recipient_id == command.recipient_id
        assert updated.utterance.content.relations[
            -1
        ].subject == ACCOUNTING_FRAME_SUBJECT
    other = Wait()
    assert (
        accounting_communicate_utterance(
            other, owner_id=OWNER, ledger=ledger, tick=1
        )
        is other
    )


def test_no_duplicate_subject_and_relation_cap() -> None:
    ledger = _ledger()
    already = _talk(
        (CommunicationRelation(subject="acc_v1", predicate="x", object="y"),)
    )
    assert (
        accounting_communicate_utterance(
            already, owner_id=OWNER, ledger=ledger, tick=1
        )
        is already
    )
    full = _talk(
        tuple(
            CommunicationRelation(
                subject=f"c{index}", predicate="p", object="o"
            )
            for index in range(32)
        )
    )
    assert (
        accounting_communicate_utterance(
            full, owner_id=OWNER, ledger=ledger, tick=1
        )
        is full
    )


def test_inscribe_content_preserves_marks_relations_and_caps_at_eight() -> None:
    ledger = _ledger()
    existing = ArtifactContent(
        marks=("keep",),
        relations=(
            ArtifactRelation(subject="keep", predicate="p", object="o"),
        ),
    )
    merged = accounting_inscribe_content(
        ledger, owner_id=OWNER, tick=1, existing=existing
    )
    assert merged is not None
    assert merged.marks == ("keep",)
    assert merged.relations[0] == existing.relations[0]
    assert len(merged.relations) <= 8
    assert all(
        relation.predicate == ACCOUNTING_RECORD_PREDICATE
        for relation in merged.relations[1:]
    )
    full = ArtifactContent(
        relations=tuple(
            ArtifactRelation(subject=f"c{index}", predicate="p", object="o")
            for index in range(8)
        )
    )
    assert (
        accounting_inscribe_content(
            ledger, owner_id=OWNER, tick=1, existing=full
        )
        is None
    )


def test_inscribe_content_does_not_use_foreign_owner_ledger() -> None:
    ledger = _ledger()
    assert (
        accounting_inscribe_content(
            ledger,
            owner_id=AgentId("someone-else"),
            tick=1,
            existing=ArtifactContent(),
        )
        is None
    )
