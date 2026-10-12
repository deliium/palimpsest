"""Owner-scoped acceptance memory: clamps, fingerprints, and blank slate."""

from __future__ import annotations

import pytest

from agents.cognition.acceptance_memory import (
    AcceptanceMemoryLedger,
    empty_acceptance_memories,
    note_exchange_completed,
    received_count_for,
    require_owner_acceptance_memories,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)
from simulation.serialization import (
    acceptance_memories_checkpoint_payload,
    decode_acceptance_memories_checkpoint,
)
from world.values import ItemKind


def test_newborn_ledger_is_empty_and_missing_is_not_zero() -> None:
    owner = AgentId("agent-a")
    ledger = empty_acceptance_memories(owner)
    assert ledger.rows == ()
    assert received_count_for(ledger, ItemKind.GENERIC) is None
    assert_blank_slate_subjective_state(owner, BlankSlateStoreCounts())
    with pytest.raises(ValueError, match="subjective_copy_forbidden"):
        assert_blank_slate_subjective_state(
            owner, BlankSlateStoreCounts(acceptance_memories=1)
        )


def test_completion_increments_both_sides_and_skips_repeat() -> None:
    owner = AgentId("agent-a")
    ledger = AcceptanceMemoryLedger(owner)
    ledger, status = note_exchange_completed(
        ledger,
        observation_tick=4,
        source_tick=3,
        window_ticks=8,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("item-food",),
        take_item_ids=("item-tool",),
        give_item_kinds=(ItemKind.FOOD,),
        take_item_kinds=(ItemKind.TOOL,),
    )
    assert status == "accepted"
    assert received_count_for(ledger, ItemKind.FOOD) == 1
    assert received_count_for(ledger, ItemKind.TOOL) == 1
    food = next(row for row in ledger.rows if row.item_kind is ItemKind.FOOD)
    tool = next(row for row in ledger.rows if row.item_kind is ItemKind.TOOL)
    assert food.giver_ids == ("body-b",)
    assert tool.giver_ids == ("body-a",)
    again, status = note_exchange_completed(
        ledger,
        observation_tick=4,
        source_tick=3,
        window_ticks=8,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("item-food",),
        take_item_ids=("item-tool",),
        give_item_kinds=(ItemKind.FOOD,),
        take_item_kinds=(ItemKind.TOOL,),
    )
    assert status == "skipped"
    assert received_count_for(again, ItemKind.FOOD) == 1


def test_window_and_second_same_tick_fingerprint() -> None:
    owner = AgentId("agent-a")
    ledger = AcceptanceMemoryLedger(owner)
    ignored, status = note_exchange_completed(
        ledger,
        observation_tick=20,
        source_tick=1,
        window_ticks=4,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("item-1",),
        take_item_ids=("item-2",),
        give_item_kinds=(ItemKind.GENERIC,),
        take_item_kinds=(ItemKind.FOOD,),
    )
    assert status == "ignored"
    assert ignored.rows == ()
    first, _status = note_exchange_completed(
        ledger,
        observation_tick=5,
        source_tick=5,
        window_ticks=4,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("item-1",),
        take_item_ids=("item-2",),
        give_item_kinds=(ItemKind.GENERIC,),
        take_item_kinds=(ItemKind.FOOD,),
    )
    second, status = note_exchange_completed(
        first,
        observation_tick=5,
        source_tick=5,
        window_ticks=4,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("item-3",),
        take_item_ids=("item-4",),
        give_item_kinds=(ItemKind.GENERIC,),
        take_item_kinds=(ItemKind.FOOD,),
    )
    assert status == "accepted"
    assert received_count_for(second, ItemKind.GENERIC) == 2


def test_codec_v16_round_trip_and_owner_guard() -> None:
    owner = AgentId("agent-a")
    ledger = empty_acceptance_memories(owner)
    ledger, _status = note_exchange_completed(
        ledger,
        observation_tick=2,
        source_tick=2,
        window_ticks=8,
        actor_id="body-b",
        counterparty_id="body-a",
        give_item_ids=("pebble",),
        take_item_ids=("bread",),
        give_item_kinds=(ItemKind.GENERIC,),
        take_item_kinds=(ItemKind.FOOD,),
    )
    payload = acceptance_memories_checkpoint_payload(
        {owner.value: ledger}, codec="v16"
    )
    restored = decode_acceptance_memories_checkpoint(payload, codec="v16")
    assert received_count_for(restored[owner.value], ItemKind.GENERIC) == 1
    require_owner_acceptance_memories(
        restored[owner.value], owner, field_name="acceptance_memories"
    )
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_acceptance_memories(
            restored[owner.value],
            AgentId("agent-b"),
            field_name="acceptance_memories",
        )
