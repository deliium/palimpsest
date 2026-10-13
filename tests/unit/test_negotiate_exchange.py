"""NegotiateExchange swaps named items and never reads a valuation."""

from __future__ import annotations

from typing import get_args

import pytest

from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._operations import (
    OperationAccepted,
    prepare_action_batch,
    validate_action_request,
)
from world._rules import RuleReason, evaluate_operation
from world._state import WorldState
from world.actions import (
    ActionRequest,
    AgentCommand,
    Give,
    NegotiateExchange,
    require_agent_command,
)
from world.events import ExchangeCompleted, ExchangeProposed
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.subjective_value import SubjectiveValuationRuleContext
from world.values import ItemKind

_WORLD = WorldId("world-1")


def _context(*, horizon: int = 2, bundle: int = 8) -> SubjectiveValuationRuleContext:
    return SubjectiveValuationRuleContext(
        allow_negotiate=True, horizon_ticks=horizon, max_bundle=bundle
    )


def _world(
    *,
    alice_capacity: int = 10,
    foods: int = 4,
    extra_body: bool = False,
):
    tool = make_item(
        "tool-1", name="Axe", kind=ItemKind.TOOL, location_id=None, holder_id="body-a"
    )
    food = tuple(
        make_item(
            f"food-{index}",
            name="Bread",
            kind=ItemKind.FOOD,
            location_id=None,
            holder_id="body-b",
        )
        for index in range(foods)
    )
    alice = alive_body(
        "body-a", inventory=(tool.entity_id,), carry_capacity=alice_capacity
    )
    bob = alive_body("body-b", inventory=tuple(item.entity_id for item in food))
    bodies = [alice, bob]
    items = [tool, *food]
    if extra_body:
        cara_food = make_item(
            "food-c",
            name="Bread",
            kind=ItemKind.FOOD,
            location_id=None,
            holder_id="body-c",
        )
        bodies.append(alive_body("body-c", inventory=(cara_food.entity_id,)))
        items.append(cara_food)
    else:
        cara_food = None
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(),),
        items=tuple(items),
        bodies=tuple(bodies),
        weather=(make_weather(),),
    )
    return state, tool, food, cara_food


def _request(command, *, actor: str, request_id: str) -> ActionRequest:
    return ActionRequest(
        request_id=RequestId(request_id),
        proposal_id=ProposalId(f"p-{request_id}"),
        world_id=_WORLD,
        actor_id=EntityId(actor),
        revision=WorldRevision(1),
        command=require_agent_command(command),
    )


def _offer(tool: EntityId, food: tuple[EntityId, ...], *, actor: str = "body-a"):
    return NegotiateExchange(
        EntityId("body-b" if actor == "body-a" else "body-a"),
        "offer",
        (tool,) if actor == "body-a" else food,
        food if actor == "body-a" else (tool,),
    )


def _run(state, requests, *, tick: int = 1, context=None):
    return prepare_action_batch(
        world_id=_WORLD,
        starting_state=state,
        requests=requests,
        tick=tick,
        subjective_valuation_context=_context() if context is None else context,
    )


def test_offer_writes_a_row_and_leaves_holders() -> None:
    state, tool, food, _cara = _world()
    pending = _run(
        state,
        (
            _request(
                _offer(tool.entity_id, tuple(item.entity_id for item in food)),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
    )
    assert pending.working_state.items[tool.entity_id].holder_id == EntityId("body-a")
    assert len(pending.working_state.exchange_offers) == 1
    assert type(pending.pending_events[0].details) is ExchangeProposed


def test_accept_swaps_tool_and_four_food_and_drops_the_row() -> None:
    state, tool, food, _cara = _world()
    food_ids = tuple(item.entity_id for item in food)
    offered = _run(
        state,
        (
            _request(
                _offer(tool.entity_id, food_ids),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
    )
    accepted = _run(
        offered.working_state,
        (
            _request(
                NegotiateExchange(
                    EntityId("body-a"),
                    "accept",
                    food_ids,
                    (tool.entity_id,),
                ),
                actor="body-b",
                request_id="r-accept",
            ),
        ),
        tick=2,
    )
    assert accepted.working_state.items[tool.entity_id].holder_id == EntityId("body-b")
    assert all(
        accepted.working_state.items[item_id].holder_id == EntityId("body-a")
        for item_id in food_ids
    )
    assert accepted.working_state.exchange_offers == ()
    assert type(accepted.pending_events[0].details) is ExchangeCompleted


def test_failed_accept_keeps_holders_and_the_row() -> None:
    state, tool, food, _cara = _world(alice_capacity=1)
    food_ids = tuple(item.entity_id for item in food)
    offered = _run(
        state,
        (
            _request(
                _offer(tool.entity_id, food_ids),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
    )
    accepted = _run(
        offered.working_state,
        (
            _request(
                NegotiateExchange(
                    EntityId("body-a"),
                    "accept",
                    food_ids,
                    (tool.entity_id,),
                ),
                actor="body-b",
                request_id="r-accept",
            ),
        ),
        tick=2,
    )
    assert accepted.outcomes[0].reason == RuleReason.NO_CARRY_CAPACITY.value
    assert accepted.working_state.items[tool.entity_id].holder_id == EntityId("body-a")
    assert len(accepted.working_state.exchange_offers) == 1


def test_give_leaves_the_offer_row() -> None:
    state, tool, food, _cara = _world(foods=1)
    food_id = food[0].entity_id
    offered = _run(
        state,
        (
            _request(
                _offer(tool.entity_id, (food_id,)),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
    )
    given = prepare_action_batch(
        world_id=_WORLD,
        starting_state=offered.working_state,
        requests=(
            _request(
                Give(EntityId("body-b"), tool.entity_id),
                actor="body-a",
                request_id="r-give",
            ),
        ),
        tick=2,
    )
    assert given.working_state.items[tool.entity_id].holder_id == EntityId("body-b")
    assert len(given.working_state.exchange_offers) == 1


def test_channel_off_rejects_only_negotiate() -> None:
    state, tool, food, _cara = _world(foods=1)
    pending = prepare_action_batch(
        world_id=_WORLD,
        starting_state=state,
        requests=(
            _request(
                _offer(tool.entity_id, (food[0].entity_id,)),
                actor="body-a",
                request_id="r-offer",
            ),
            _request(
                Give(EntityId("body-b"), tool.entity_id),
                actor="body-a",
                request_id="r-give",
            ),
        ),
        tick=1,
        subjective_valuation_context=None,
    )
    assert (
        pending.outcomes[0].reason == RuleReason.SUBJECTIVE_VALUATION_CHANNEL_OFF.value
    )
    assert pending.outcomes[1].reason == RuleReason.OCCURRENCE.value
    assert pending.working_state.exchange_offers == ()


def test_expired_row_is_replaced_by_the_next_offer() -> None:
    state, tool, food, _cara = _world(foods=1)
    food_id = food[0].entity_id
    offered = _run(
        state,
        (
            _request(
                _offer(tool.entity_id, (food_id,)),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
        tick=1,
        context=_context(horizon=1),
    )
    replaced = _run(
        offered.working_state,
        (
            _request(
                _offer(tool.entity_id, (food_id,)),
                actor="body-a",
                request_id="r-next",
            ),
        ),
        tick=3,
        context=_context(horizon=1),
    )
    assert replaced.outcomes[0].reason == RuleReason.OCCURRENCE.value
    assert replaced.working_state.exchange_offers[0].tick == 3
    assert all(
        type(event.details) is ExchangeProposed for event in replaced.pending_events
    )


def test_empty_side_offer_is_rejected() -> None:
    state, tool, _food, _cara = _world(foods=1)
    pending = _run(
        state,
        (
            _request(
                NegotiateExchange(EntityId("body-b"), "offer", (tool.entity_id,), ()),
                actor="body-a",
                request_id="r-empty",
            ),
        ),
    )
    assert pending.outcomes[0].reason == RuleReason.EXCHANGE_EMPTY_SIDE.value
    assert pending.working_state.exchange_offers == ()


def test_second_pair_accept_fails_not_held() -> None:
    state, tool, food, cara_food = _world(foods=1, extra_body=True)
    assert cara_food is not None
    first = _run(
        state,
        (
            _request(
                NegotiateExchange(
                    EntityId("body-b"), "offer", (tool.entity_id,), (food[0].entity_id,)
                ),
                actor="body-a",
                request_id="r-bob",
            ),
            _request(
                NegotiateExchange(
                    EntityId("body-c"),
                    "offer",
                    (tool.entity_id,),
                    (cara_food.entity_id,),
                ),
                actor="body-a",
                request_id="r-cara",
            ),
        ),
    )
    accepted = _run(
        first.working_state,
        (
            _request(
                NegotiateExchange(
                    EntityId("body-a"),
                    "accept",
                    (food[0].entity_id,),
                    (tool.entity_id,),
                ),
                actor="body-b",
                request_id="r-take",
            ),
            _request(
                NegotiateExchange(
                    EntityId("body-a"),
                    "accept",
                    (cara_food.entity_id,),
                    (tool.entity_id,),
                ),
                actor="body-c",
                request_id="r-late",
            ),
        ),
        tick=2,
    )
    assert accepted.outcomes[0].reason == RuleReason.OCCURRENCE.value
    assert accepted.outcomes[1].reason == RuleReason.NOT_HELD.value
    assert accepted.working_state.items[tool.entity_id].holder_id == EntityId("body-b")


def test_same_tick_accept_before_offer_does_not_match() -> None:
    state, tool, food, _cara = _world(foods=1)
    food_id = food[0].entity_id
    pending = _run(
        state,
        (
            _request(
                NegotiateExchange(
                    EntityId("body-a"),
                    "accept",
                    (food_id,),
                    (tool.entity_id,),
                ),
                actor="body-b",
                request_id="r-accept",
            ),
            _request(
                _offer(tool.entity_id, (food_id,)),
                actor="body-a",
                request_id="r-offer",
            ),
        ),
    )
    assert pending.outcomes[0].reason == RuleReason.EXCHANGE_NO_LIVE_OFFER.value
    assert pending.outcomes[1].reason == RuleReason.OCCURRENCE.value
    assert pending.working_state.items[tool.entity_id].holder_id == EntityId("body-a")


def test_command_registry_includes_negotiate_once() -> None:
    args = get_args(AgentCommand)
    assert args.count(NegotiateExchange) == 1
    assert len(args) == 40


def test_command_round_trips() -> None:
    command = NegotiateExchange(
        EntityId("body-b"),
        "offer",
        (EntityId("tool-1"),),
        (EntityId("food-1"),),
    )
    assert decode_domain(encode_domain(command)) == command


def test_rule_context_rejects_a_ledger() -> None:
    state, tool, food, _cara = _world(foods=1)

    class Ledger:
        reservation = 8

    accepted = validate_action_request(
        world_id=_WORLD,
        state=state,
        request=_request(
            _offer(tool.entity_id, (food[0].entity_id,)),
            actor="body-a",
            request_id="r-type",
        ),
    )
    assert type(accepted) is OperationAccepted
    with pytest.raises(TypeError, match="SubjectiveValuationRuleContext"):
        evaluate_operation(
            state,
            accepted.operation,
            tick=1,
            subjective_valuation_context=Ledger(),
        )
