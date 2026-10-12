"""A counteroffer may spend a remembered inert portable item before food."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.subjective_value import (
    SubjectiveValuationLedger,
    ValuationComponent,
    ValuationRow,
    _counter_or_withdraw,
)
from agents.models import AgentId
from world.identifiers import EntityId
from world.observations import ObservedItemPlacement
from world.values import ItemKind, ItemLoad


def _item(item_id: str, kind: ItemKind, load: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=EntityId(item_id),
        kind=kind,
        load=ItemLoad(load),
        placement=ObservedItemPlacement.HELD_BY_SELF,
        name=item_id,
    )


def _ledger() -> SubjectiveValuationLedger:
    return SubjectiveValuationLedger(
        AgentId("agent-a"),
        kind_rows=(
            ValuationRow(ItemKind.FOOD, ItemKind.FOOD, 1, (), 1),
            ValuationRow(
                ItemKind.GENERIC,
                ItemKind.FOOD,
                2,
                (ValuationComponent("observed_acceptance", 2),),
                1,
            ),
            ValuationRow(ItemKind.TOOL, ItemKind.FOOD, 4, (), 1),
        ),
    )


def test_inert_portable_is_spent_before_food() -> None:
    observation = SimpleNamespace(
        items=(
            _item("food-b", ItemKind.FOOD),
            _item("pebble", ItemKind.GENERIC),
            _item("food-a", ItemKind.FOOD),
        )
    )
    chosen = _counter_or_withdraw(
        observation,
        _ledger(),
        actor=EntityId("body-b"),
        give_ids=(EntityId("tool-1"),),
        give_kinds=(ItemKind.TOOL,),
        take_ids=(EntityId("food-b"), EntityId("food-a")),
        take_kinds=(ItemKind.FOOD, ItemKind.FOOD),
        max_bundle=8,
        prefer_inert=True,
    )
    assert chosen.act == "counteroffer"
    assert chosen.give_item_ids[0] == EntityId("pebble")
    assert chosen.give_item_ids[1:] == (
        EntityId("food-a"),
        EntityId("food-b"),
    )
    assert chosen.take_item_ids == (EntityId("tool-1"),)


def test_channel_off_keeps_reference_count() -> None:
    observation = SimpleNamespace(
        items=(
            _item("pebble", ItemKind.GENERIC),
            _item("food-a", ItemKind.FOOD),
            _item("food-b", ItemKind.FOOD),
            _item("food-c", ItemKind.FOOD),
            _item("food-d", ItemKind.FOOD),
        )
    )
    chosen = _counter_or_withdraw(
        observation,
        _ledger(),
        actor=EntityId("body-b"),
        give_ids=(EntityId("tool-1"),),
        give_kinds=(ItemKind.TOOL,),
        take_ids=(),
        take_kinds=(),
        max_bundle=8,
        prefer_inert=False,
    )
    assert chosen.act == "counteroffer"
    assert EntityId("pebble") not in chosen.give_item_ids
    assert len(chosen.give_item_ids) == 4
