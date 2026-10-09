"""Corpse Take is physical appropriation. Doctrine never gates it."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._operations import OperationAccepted, validate_action_request
from world._rules import (
    RuleDisposition,
    RuleReason,
    apply_operation,
    evaluate_operation,
)
from world._state import WorldState
from world.actions import ActionRequest, Give, Take, require_agent_command
from world.events import Taken, TakenFromCorpse
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus, copy_body
from world.possession_succession import PossessionSuccessionRuleContext
from world.values import CarryCapacity, Health


def _context() -> PossessionSuccessionRuleContext:
    return PossessionSuccessionRuleContext(allow_corpse_take=True, allow_claim=True)


def _corpse_state(*, location: str = "loc-1", load: int = 1, capacity: int = 10):
    item = make_item("item-1", location_id=None, holder_id="body-dead", load=load)
    corpse = copy_body(
        alive_body("body-dead", location_id=location, inventory=(item.entity_id,)),
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    living = copy_body(alive_body("body-live"), carry_capacity=CarryCapacity(capacity))
    locations = (make_location("loc-1"),)
    if location != "loc-1":
        locations = (
            make_location("loc-1", adjacent=("loc-2",)),
            make_location("loc-2", adjacent=("loc-1",)),
        )
    state = WorldState(
        WorldRevision(1),
        locations=locations,
        items=(item,),
        bodies=(corpse, living),
        weather=tuple(make_weather(loc.entity_id.value) for loc in locations),
        corpse_custody_item_ids=frozenset({item.entity_id}),
    )
    return state, item


def _take(state: WorldState):
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-1"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-live"),
            revision=WorldRevision(1),
            command=require_agent_command(Take(EntityId("item-1"))),
        ),
    )
    assert type(outcome) is OperationAccepted
    return outcome.operation


def test_ground_take_is_unchanged_when_channel_is_off() -> None:
    item = make_item("item-ground")
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=(item,),
        bodies=(alive_body("body-live"),),
        weather=(make_weather(),),
    )
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-1"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-live"),
            revision=WorldRevision(1),
            command=require_agent_command(Take(item.entity_id)),
        ),
    )
    assert type(outcome) is OperationAccepted
    applied = apply_operation(state, outcome.operation)
    assert applied.result.disposition is RuleDisposition.MUTATE
    assert applied.result.reason is not RuleReason.POSSESSION_SUCCESSION_CHANNEL_OFF
    assert type(applied.event_details) is Taken
    assert applied.next_state.items[item.entity_id].holder_id == EntityId("body-live")


def test_corpse_take_moves_holder_only() -> None:
    state, item = _corpse_state()
    applied = apply_operation(
        state, _take(state), possession_succession_context=_context()
    )
    assert type(applied.event_details) is TakenFromCorpse
    assert applied.event_details.source_body_id == EntityId("body-dead")
    assert applied.next_state.corpse_custody_item_ids == frozenset()
    dead_inventory = applied.next_state.bodies[EntityId("body-dead")].inventory
    live_inventory = applied.next_state.bodies[EntityId("body-live")].inventory
    assert item.entity_id not in dead_inventory
    assert live_inventory == (item.entity_id,)


def test_remote_corpse_and_capacity_and_channel_off() -> None:
    remote, _item = _corpse_state(location="loc-2")
    rejected = evaluate_operation(
        remote, _take(remote), possession_succession_context=_context()
    )
    assert rejected.reason is RuleReason.NOT_COLOCATED

    heavy, _item = _corpse_state(load=5, capacity=1)
    over = evaluate_operation(
        heavy, _take(heavy), possession_succession_context=_context()
    )
    assert over.reason is RuleReason.NO_CARRY_CAPACITY

    closed, _item = _corpse_state()
    off = evaluate_operation(closed, _take(closed))
    assert off.reason is RuleReason.POSSESSION_SUCCESSION_CHANNEL_OFF


def test_give_to_corpse_stays_dead_target() -> None:
    state, item = _corpse_state()
    held = make_item("item-gift", location_id=None, holder_id="body-live")
    living = state.bodies[EntityId("body-live")]
    giver = copy_body(living, inventory=(held.entity_id,))
    bodies = dict(state.bodies)
    bodies[giver.entity_id] = giver
    items = dict(state.items)
    items[held.entity_id] = held
    giving = WorldState(
        state.revision,
        locations=tuple(state.locations.values()),
        items=tuple(items.values()),
        bodies=tuple(bodies.values()),
        weather=tuple(state.weather.values()),
        corpse_custody_item_ids=state.corpse_custody_item_ids,
    )
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=giving,
        request=ActionRequest(
            request_id=RequestId("r-give"),
            proposal_id=ProposalId("p-give"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-live"),
            revision=state.revision,
            command=require_agent_command(
                Give(EntityId("body-dead"), held.entity_id)
            ),
        ),
    )
    assert type(outcome) is OperationAccepted
    result = evaluate_operation(
        giving, outcome.operation, possession_succession_context=_context()
    )
    assert result.reason is RuleReason.DEAD_TARGET
    assert item.entity_id in giving.corpse_custody_item_ids


def test_ledger_object_is_not_a_succession_context() -> None:
    state, _item = _corpse_state()
    with pytest.raises(TypeError, match="PossessionSuccessionRuleContext"):
        evaluate_operation(
            state,
            _take(state),
            possession_succession_context={"doctrine": "children_should_inherit"},
        )
