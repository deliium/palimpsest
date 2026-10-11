"""The proposer names item ids and never a reservation."""

from __future__ import annotations

from types import SimpleNamespace

from agents.cognition.subjective_value import (
    propose_exchange_command,
    refresh_owner_ledgers,
)
from agents.models import AgentId
from world.actions import Attack, Give, NegotiateExchange
from world.identifiers import EntityId
from world.observations import ObservationAudienceRole, ObservedItemPlacement
from world.values import ItemKind


def test_alice_counters_toward_eight_food() -> None:
    tool = EntityId("tool-1")
    foods = tuple(EntityId(f"food-{index}") for index in range(8))
    alice = _alice()
    observation = _observation(
        actor=EntityId("bob"),
        give_ids=foods[:3],
        give_kinds=("food", "food", "food"),
        take_ids=(tool,),
        take_kinds=("tool",),
        holdings=tuple(
            _holding(EntityId("bob"), item, ItemKind.FOOD) for item in foods
        ),
        own=((tool, ItemKind.TOOL),),
    )
    chosen = propose_exchange_command(
        _wait(),
        observation,
        channel_on=True,
        max_bundle=8,
        valuations=alice,
        owner_entity_id=EntityId("alice-body"),
    )
    assert type(chosen) is NegotiateExchange
    assert chosen.act == "counteroffer"
    assert chosen.give_item_ids == (tool,)
    assert chosen.take_item_ids == foods
    assert not hasattr(chosen, "reservation")


def test_bob_refuses_an_eight_food_ask() -> None:
    tool = EntityId("tool-1")
    foods = tuple(EntityId(f"food-{index}") for index in range(8))
    bob = _bob()
    observation = _observation(
        actor=EntityId("alice-body"),
        give_ids=(tool,),
        give_kinds=("tool",),
        take_ids=foods,
        take_kinds=tuple("food" for _item in foods),
        holdings=(_holding(EntityId("alice-body"), tool, ItemKind.TOOL),),
        own=tuple((item, ItemKind.FOOD) for item in foods),
    )
    chosen = propose_exchange_command(
        _wait(),
        observation,
        channel_on=True,
        max_bundle=8,
        valuations=bob,
        owner_entity_id=EntityId("bob"),
    )
    assert type(chosen) is NegotiateExchange
    assert chosen.act == "counteroffer"
    assert chosen.give_item_ids == foods[:3]
    assert chosen.take_item_ids == (tool,)


def test_accept_when_the_bundles_overlap() -> None:
    tool = EntityId("tool-1")
    foods = tuple(EntityId(f"food-{index}") for index in range(3))
    alice = refresh_owner_ledgers(
        owner_id=AgentId("alice"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(ItemKind.TOOL,),
        location_id=EntityId("camp"),
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )[0]
    observation = _observation(
        actor=EntityId("bob"),
        give_ids=foods,
        give_kinds=("food", "food", "food"),
        take_ids=(tool,),
        take_kinds=("tool",),
        holdings=(),
        own=((tool, ItemKind.TOOL),),
    )
    chosen = propose_exchange_command(
        _wait(),
        observation,
        channel_on=True,
        max_bundle=8,
        valuations=alice,
        owner_entity_id=EntityId("alice-body"),
    )
    assert type(chosen) is NegotiateExchange
    assert chosen.act == "accept"
    assert chosen.give_item_ids == (tool,)
    assert chosen.take_item_ids == foods


def test_unfilled_counter_withdraws() -> None:
    tool = EntityId("tool-1")
    foods = tuple(EntityId(f"food-{index}") for index in range(3))
    observation = _observation(
        actor=EntityId("bob"),
        give_ids=foods,
        give_kinds=("food", "food", "food"),
        take_ids=(tool,),
        take_kinds=("tool",),
        holdings=tuple(
            _holding(EntityId("bob"), item, ItemKind.FOOD) for item in foods
        ),
        own=((tool, ItemKind.TOOL),),
    )
    chosen = propose_exchange_command(
        _wait(),
        observation,
        channel_on=True,
        max_bundle=8,
        valuations=_alice(),
        owner_entity_id=EntityId("alice-body"),
    )
    assert type(chosen) is NegotiateExchange
    assert chosen.act == "withdraw"
    assert chosen.give_item_ids == ()
    assert chosen.take_item_ids == ()


def test_channel_off_keeps_the_ranked_command() -> None:
    ranked = Give(recipient_id=EntityId("bob"), item_id=EntityId("tool-1"))
    assert (
        propose_exchange_command(
            ranked,
            _observation(
                actor=EntityId("bob"),
                give_ids=(EntityId("food-1"),),
                give_kinds=("food",),
                take_ids=(EntityId("tool-1"),),
                take_kinds=("tool",),
                holdings=(),
                own=(),
            ),
            channel_on=False,
            max_bundle=8,
            valuations=_alice(),
            owner_entity_id=EntityId("alice-body"),
        )
        is ranked
    )


def test_selected_command_is_not_a_give_or_an_attack() -> None:
    incoming = Attack(target_id=EntityId("bob"))
    chosen = propose_exchange_command(
        incoming,
        _observation(
            actor=EntityId("bob"),
            give_ids=tuple(EntityId(f"food-{index}") for index in range(8)),
            give_kinds=tuple("food" for _index in range(8)),
            take_ids=(EntityId("tool-1"),),
            take_kinds=("tool",),
            holdings=tuple(
                _holding(EntityId("bob"), EntityId(f"food-{index}"), ItemKind.FOOD)
                for index in range(8)
            ),
            own=((EntityId("tool-1"), ItemKind.TOOL),),
        ),
        channel_on=True,
        max_bundle=8,
        valuations=_alice(),
        owner_entity_id=EntityId("alice-body"),
    )
    assert type(chosen) is not Give
    assert type(chosen) is not Attack
    assert type(chosen) is NegotiateExchange


def _alice() -> object:
    return refresh_owner_ledgers(
        owner_id=AgentId("alice"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={ItemKind.TOOL: 1},
        ground_kinds=(),
        other_held_kinds=(),
        location_id=EntityId("camp"),
        plan_kinds=frozenset({ItemKind.TOOL}),
        risk_active=False,
        future_kinds=frozenset(),
    )[0]


def _bob() -> object:
    return refresh_owner_ledgers(
        owner_id=AgentId("bob"),
        valuations=None,
        scarcity=None,
        tick=1,
        hunger=0,
        thirst=0,
        health=100,
        body_present=True,
        held_counts={},
        ground_kinds=(),
        other_held_kinds=(ItemKind.TOOL,),
        location_id=EntityId("camp"),
        plan_kinds=frozenset(),
        risk_active=False,
        future_kinds=frozenset(),
    )[0]


def _wait() -> SimpleNamespace:
    return SimpleNamespace(kind="wait")


def _holding(body: EntityId, item: EntityId, kind: ItemKind) -> SimpleNamespace:
    return SimpleNamespace(body_id=body, item_id=item, kind=kind)


def _observation(
    *,
    actor: EntityId,
    give_ids: tuple[EntityId, ...],
    give_kinds: tuple[str, ...],
    take_ids: tuple[EntityId, ...],
    take_kinds: tuple[str, ...],
    holdings: tuple[object, ...],
    own: tuple[tuple[EntityId, ItemKind], ...],
) -> SimpleNamespace:
    return SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                audience_role=ObservationAudienceRole.TARGET,
                actor_id=actor,
                public_facts={
                    "kind": "exchange_proposed",
                    "act": "offer",
                    "give_item_ids": tuple(item.value for item in give_ids),
                    "take_item_ids": tuple(item.value for item in take_ids),
                    "give_item_kinds": give_kinds,
                    "take_item_kinds": take_kinds,
                },
            ),
        ),
        exchange_visible_holdings=holdings,
        items=tuple(
            SimpleNamespace(
                entity_id=item_id,
                kind=kind,
                placement=ObservedItemPlacement.HELD_BY_SELF,
            )
            for item_id, kind in own
        ),
    )
