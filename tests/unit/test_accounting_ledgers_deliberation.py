"""Accounting attachment only decorates an already-selected command."""

# mypy: ignore-errors

from __future__ import annotations

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
from world.accounting_ledgers import AccountingFrameEntryKind, accounting_record_genre
from world.actions import Inscribe, Talk, Wait
from world.artifacts import (
    MAX_ARTIFACT_RELATIONS,
    ArtifactContent,
    ArtifactKind,
    DurableRecordGenre,
)
from world.communications import origin_utterance
from world.identifiers import EntityId

OWNER = AgentId("agent-owner")
RECIPIENT = EntityId("agent-2")


def _ledger():
    observation = AccountingRecordObservation(
        record_token=accounting_record_token("artifact-1"),
        record_genre="inventory_record",
        integrity=AccountingRecordIntegrity.INTACT,
        content_revision=0,
        relations=(("inv_food", ACCOUNTING_RECORD_PREDICATE, "hold2"),),
        tick=1,
    )
    return apply_accounting_ledger_update(
        owner_id=OWNER, tick=1, records=(observation,)
    )


def _talk() -> Talk:
    return Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(
            text="hello", speaker_id=EntityId("agent-owner")
        ),
    )


def test_talk_attachment_preserves_command_class_and_recipient() -> None:
    command = _talk()
    updated = accounting_communicate_utterance(
        command, owner_id=OWNER, ledger=_ledger(), tick=1
    )
    assert type(updated) is Talk
    assert updated.recipient_id == command.recipient_id
    assert len(updated.utterance.content.relations) == 1


def test_inscribe_extension_keeps_verb_and_marks() -> None:
    command = Inscribe(
        kind=ArtifactKind.RECORD,
        content=ArtifactContent(marks=("keep",)),
        hold=False,
        record_genre=DurableRecordGenre.INVENTORY_RECORD,
    )
    merged = accounting_inscribe_content(
        _ledger(), owner_id=OWNER, tick=1, existing=command.content
    )
    assert merged is not None
    assert merged.marks == command.content.marks
    assert len(merged.relations) <= MAX_ARTIFACT_RELATIONS
    extended = Inscribe(
        kind=command.kind,
        content=merged,
        hold=command.hold,
        record_genre=command.record_genre,
    )
    assert extended.kind is command.kind
    assert extended.hold is command.hold
    assert extended.record_genre is command.record_genre


def test_no_attachment_for_another_command_type() -> None:
    command = Wait()
    assert (
        accounting_communicate_utterance(
            command, owner_id=OWNER, ledger=_ledger(), tick=1
        )
        is command
    )
    assert (
        accounting_inscribe_content(
            _ledger(),
            owner_id=AgentId("someone-else"),
            tick=1,
            existing=ArtifactContent(),
        )
        is None
    )


def test_genre_for_inscribe_maps_existing_values() -> None:
    assert (
        accounting_record_genre(AccountingFrameEntryKind.INVENTORY)
        == DurableRecordGenre.INVENTORY_RECORD.value
    )
