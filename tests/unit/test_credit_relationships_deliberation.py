"""Credit beliefs never create or replace a command."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.credit_relationships import apply_credit_relationship_update
from agents.cognition.credit_relationships_communication import (
    credit_communicate_utterance,
)
from tests.unit.test_credit_relationships_helpers import OWNER, PEER, claim
from world.actions import Give, Move, NegotiateExchange, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER_ENTITY = EntityId("body-1")


def _ledger():
    return apply_credit_relationship_update(
        owner_id=OWNER, tick=2, claims=(claim(),)
    )


def test_non_speech_commands_are_never_replaced() -> None:
    for command in (
        Wait(),
        Move(destination_id=EntityId("loc-b")),
        Give(recipient_id=PEER, item_id=EntityId("item-1")),
        NegotiateExchange(
            counterparty_id=PEER,
            act="offer",
            give_item_ids=(EntityId("item-1"),),
            take_item_ids=(EntityId("item-2"),),
        ),
    ):
        assert (
            credit_communicate_utterance(
                command, owner_id=OWNER, ledger=_ledger(), tick=3
            )
            is command
        )


def test_talk_gains_one_relation_without_replacing_the_command() -> None:
    from agents.cognition.credit_relationships import CreditClaimSource

    ledger = apply_credit_relationship_update(
        owner_id=OWNER,
        tick=2,
        claims=(
            claim(source=CreditClaimSource.COMMUNICATED, source_tick=2),
        ),
    )
    command = Talk(
        recipient_id=PEER,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    updated = credit_communicate_utterance(
        command, owner_id=OWNER, ledger=ledger, tick=3
    )
    assert type(updated) is Talk
    assert updated.recipient_id == command.recipient_id
    assert updated.utterance.content.text == command.utterance.content.text
    assert len(updated.utterance.content.relations) == 1
    assert len(command.utterance.content.relations) == 0


def test_disabled_mode_attaches_nothing() -> None:
    command = Talk(
        recipient_id=PEER,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    assert (
        credit_communicate_utterance(
            command, owner_id=OWNER, ledger=None, tick=3
        )
        is command
    )
