"""Exchange occurrences stay colocated and holdings stay off the price field."""

from __future__ import annotations

from world._perception import project_observations
from world._state import WorldState
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V18,
    ExchangeProposed,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationContext
from world.values import ItemKind
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)


def _scene():
    tool = make_item(
        "tool-1", name="Axe", kind=ItemKind.TOOL, location_id=None, holder_id="body-a"
    )
    food = make_item(
        "food-1", name="Bread", kind=ItemKind.FOOD, location_id=None, holder_id="body-b"
    )
    alice = alive_body("body-a", inventory=(tool.entity_id,))
    bob = alive_body("body-b", inventory=(food.entity_id,))
    witness = alive_body("body-w")
    remote = alive_body("body-r", location_id="loc-2")
    state = WorldState(
        WorldRevision(1),
        locations=(
            make_location(adjacent=("loc-2",)),
            make_location("loc-2", name="Far", adjacent=("loc-1",)),
        ),
        items=(tool, food),
        bodies=(alice, bob, witness, remote),
        weather=(make_weather(), make_weather("loc-2")),
    )
    event = make_physical_replayable_event(
        event_id=EventId("evt-offer"),
        run_id="run-exchange",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-offer"), alice.entity_id),
        resulting_revision=WorldRevision(1),
        details=ExchangeProposed(
            alice.entity_id,
            bob.entity_id,
            "offer",
            (tool.entity_id,),
            (food.entity_id,),
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V18,
    )
    return state, event, tool, food


def _observe(state, event, *, active: bool):
    return project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(
            EntityId("body-a"),
            EntityId("body-b"),
            EntityId("body-w"),
            EntityId("body-r"),
        ),
        context=ObservationContext(tick=12),
        prior_events=(event,),
        subjective_valuation_active=active,
    )


def test_colocated_agents_see_the_same_bundle_tokens() -> None:
    state, event, tool, food = _scene()
    alice, bob, witness, remote = _observe(state, event, active=True)
    facts = {
        "act": "offer",
        "give_item_ids": (tool.entity_id.value,),
        "take_item_ids": (food.entity_id.value,),
        "give_item_kinds": (ItemKind.TOOL.value,),
        "take_item_kinds": (ItemKind.FOOD.value,),
    }
    for observation in (alice, bob, witness):
        assert len(observation.occurrences) == 1
        public = observation.occurrences[0].public_facts
        for key, value in facts.items():
            assert public[key] == value
        assert "reservation" not in public
    assert remote.occurrences == ()


def test_channel_off_omits_occurrence_and_holdings() -> None:
    state, event, _tool, _food = _scene()
    observations = _observe(state, event, active=False)
    for observation in observations:
        assert observation.occurrences == ()
        assert observation.exchange_visible_holdings is None


def test_channel_on_lists_other_held_items_without_needs() -> None:
    state, event, _tool, food = _scene()
    alice, _bob, _witness, remote = _observe(state, event, active=True)
    assert alice.exchange_visible_holdings is not None
    food_rows = [
        row for row in alice.exchange_visible_holdings if row.item_id == food.entity_id
    ]
    assert len(food_rows) == 1
    row = food_rows[0]
    assert row.body_id == EntityId("body-b")
    assert row.kind is ItemKind.FOOD
    assert not hasattr(row, "health")
    assert not hasattr(row, "hunger")
    assert not hasattr(row, "reservation")
    assert remote.exchange_visible_holdings == ()
