"""Price beliefs never create or replace a command."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.emergent_prices import apply_emergent_price_update
from agents.cognition.emergent_prices_communication import (
    price_communicate_utterance,
)
from tests.unit.emergent_prices_helpers import (
    OWNER,
    OWNER_ENTITY,
    observation,
    valuations,
)
from world.actions import Give, Move, NegotiateExchange, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

RECIPIENT = EntityId("body-2")


def _ledger():
    return apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=tuple(
            observation(source_tick=tick) for tick in range(1, 5)
        ),
        observed_quotes=(),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )


def test_non_speech_commands_are_never_replaced() -> None:
    for command in (
        Wait(),
        Move(destination_id=EntityId("loc-b")),
        Give(recipient_id=RECIPIENT, item_id=EntityId("item-1")),
        NegotiateExchange(
            counterparty_id=RECIPIENT,
            act="offer",
            give_item_ids=(EntityId("item-1"),),
            take_item_ids=(EntityId("item-2"),),
        ),
    ):
        assert (
            price_communicate_utterance(
                command,
                owner_id=OWNER,
                ledger=_ledger(),
                counterparty_id=RECIPIENT,
            )
            is command
        )


def test_talk_gains_one_relation_without_replacing_the_command() -> None:
    command = Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    updated = price_communicate_utterance(
        command,
        owner_id=OWNER,
        ledger=_ledger(),
        counterparty_id=RECIPIENT,
    )
    assert type(updated) is Talk
    assert updated.recipient_id == command.recipient_id
    assert updated.utterance.content.text == command.utterance.content.text
    assert len(updated.utterance.content.relations) == 1


def test_exchange_admission_inputs_are_untouched() -> None:
    command = NegotiateExchange(
        counterparty_id=RECIPIENT,
        act="counteroffer",
        give_item_ids=(EntityId("item-1"),),
        take_item_ids=(EntityId("item-2"),),
    )
    assert (
        price_communicate_utterance(
            command,
            owner_id=OWNER,
            ledger=_ledger(),
            counterparty_id=RECIPIENT,
        )
        is command
    )
