"""Colocated agents hear commitment tokens; channel-off gives stay unchanged."""

from __future__ import annotations

from dataclasses import fields

from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._perception import PerceptionService
from world._state import WorldState
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V17,
    CommitmentDeclared,
    Given,
    OccurrenceContext,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationContext
from world.values import ItemKind

_RUN = "run-perception"
_WORLD = WorldId("world-perception")


def _state():
    food = make_item("food-1", kind=ItemKind.FOOD, location_id=None, holder_id="body-a")
    giver = alive_body("body-a", inventory=(food.entity_id,))
    other = alive_body("body-b")
    witness = alive_body("body-c")
    remote = alive_body("body-far", location_id="loc-2")
    locations = (
        make_location("loc-1", adjacent=("loc-2",)),
        make_location("loc-2", adjacent=("loc-1",)),
    )
    state = WorldState(
        WorldRevision(1),
        locations=locations,
        items=(food,),
        bodies=(giver, other, witness, remote),
        weather=tuple(make_weather(loc.entity_id.value) for loc in locations),
    )
    return state, food, giver, other


def _declaration(giver, other):
    return make_physical_replayable_event(
        event_id=EventId("evt-declare"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-declare"), giver.entity_id),
        resulting_revision=WorldRevision(1),
        details=CommitmentDeclared(
            giver.entity_id,
            other.entity_id,
            "future_exchange",
            "propose",
            "counterparty",
            "none",
            1,
            "by_tick",
            "material",
            4,
            "food",
        ),
        occurrence=OccurrenceContext(origin_location_id=giver.location_id),
        schema_version=EVENT_SCHEMA_REPLAY_V17,
    )


def _given(giver, other, food):
    return make_physical_replayable_event(
        event_id=EventId("evt-give"),
        run_id=_RUN,
        world_id=_WORLD,
        tick=1,
        sequence=1,
        cause=ActionCause(RequestId("req-give"), giver.entity_id),
        resulting_revision=WorldRevision(1),
        details=Given(other.entity_id, food.entity_id, other.entity_id),
        occurrence=OccurrenceContext(origin_location_id=giver.location_id),
    )


def _see(state, observer: str, events, *, active: bool):
    return PerceptionService(structured_commitments_active=active).project(
        world_id=_WORLD,
        state=state,
        observer_ids=(EntityId(observer),),
        context=ObservationContext(tick=2),
        prior_events=events,
    )[0]


def test_colocated_roles_hear_every_commitment_token() -> None:
    state, _food, giver, other = _state()
    event = _declaration(giver, other)
    for observer in ("body-a", "body-b", "body-c"):
        seen = _see(state, observer, (event,), active=True)
        assert len(seen.occurrences) == 1
        facts = seen.occurrences[0].public_facts
        assert facts["kind"] == "future_exchange"
        assert facts["act"] == "propose"
        assert facts["owed_by"] == "counterparty"
        assert facts["item_kind"] == "material"
        assert facts["now_item_kind"] == "food"
        assert facts["due_kind"] == "by_tick"
        assert facts["due_tick"] == 4
        assert "structured_commitments" not in {field.name for field in fields(seen)}
    remote = _see(state, "body-far", (event,), active=True)
    assert remote.occurrences == ()


def test_channel_on_give_adds_item_kind_only_for_actor_and_target() -> None:
    state, food, giver, other = _state()
    event = _given(giver, other, food)
    actor = _see(state, "body-a", (event,), active=True)
    assert actor.occurrences[0].public_facts["item_id"] == "food-1"
    assert actor.occurrences[0].public_facts["item_kind"] == "food"
    target = _see(state, "body-b", (event,), active=True)
    assert target.occurrences[0].public_facts["item_kind"] == "food"
    witness = _see(state, "body-c", (event,), active=True)
    assert "item_kind" not in witness.occurrences[0].public_facts
    assert witness.occurrences[0].public_facts["kind"] == "give"
    off = _see(state, "body-a", (event,), active=False)
    assert "item_kind" not in off.occurrences[0].public_facts
    assert "item_id" not in off.occurrences[0].public_facts
