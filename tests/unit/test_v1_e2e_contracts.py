"""End-to-end V1 trust pipeline and coverage registries."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.models import AgentId
from simulation.actions import admit_agent_command
from simulation.models import SimulationRunConfig
from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import (
    make_item,
    make_location,
    make_resource,
    weather_for_locations,
)
from world._operations import OperationRejected
from world._state import World, WorldState
from world._transitions import TransitionResult
from world.actions import (
    Ask,
    Attack,
    Drink,
    Drop,
    Eat,
    Flee,
    Give,
    Help,
    Move,
    Search,
    Sleep,
    Take,
    Talk,
    Tell,
    TransitionOutcome,
    Wait,
)
from world.events import (
    Asked,
    Attacked,
    Dropped,
    Drunk,
    Eaten,
    EventDetails,
    Fled,
    Given,
    Helped,
    Moved,
    Searched,
    Slept,
    Taken,
    Talked,
    Told,
    Waited,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

COMMAND_VARIANTS = (
    Move(EntityId("loc-1")),
    Search(),
    Take(EntityId("item-1")),
    Drop(EntityId("item-1")),
    Give(EntityId("body-2"), EntityId("item-1")),
    Eat(EntityId("item-1")),
    Drink(EntityId("res-1")),
    Sleep(),
    Talk(EntityId("body-2"), "hi"),
    Ask(EntityId("body-2"), "hi"),
    Tell(EntityId("body-2"), "hi"),
    Help(EntityId("body-2")),
    Attack(EntityId("body-2")),
    Flee(),
    Wait(),
)

EVENT_DETAILS: tuple[EventDetails, ...] = (
    Moved(EntityId("loc-1")),
    Searched(),
    Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
    Dropped(EntityId("item-1"), resulting_location_id=EntityId("loc-1")),
    Given(
        EntityId("body-2"),
        EntityId("item-1"),
        resulting_holder_id=EntityId("body-2"),
    ),
    Eaten(EntityId("item-1")),
    Drunk(EntityId("res-1")),
    Slept(),
    Talked(EntityId("body-2"), "hi"),
    Asked(EntityId("body-2"), "hi"),
    Told(EntityId("body-2"), "hi"),
    Helped(EntityId("body-2")),
    Attacked(EntityId("body-2")),
    Fled(),
    Waited(),
)


class _Translator:
    def to_entity_id(self, agent_id: AgentId) -> EntityId:
        return EntityId("body-1")

    def to_agent_id(self, entity_id: EntityId) -> AgentId:
        return AgentId("agent-1")


def _world() -> World:
    locations = (make_location("loc-1", name="Camp"),)
    return World(
        WorldId("world-1"),
        WorldState(
            WorldRevision(0),
            locations=locations,
            items=(make_item("item-1", name="Cup", location_id="loc-1"),),
            resources=(
                make_resource(
                    "res-1",
                    name="Water",
                    location_id="loc-1",
                    quantity=1.0,
                    unit="liters",
                ),
            ),
            bodies=(
                AgentBody(
                    entity_id=EntityId("body-1"),
                    location_id=EntityId("loc-1"),
                    health=Health(50),
                    hunger=Hunger(0),
                    thirst=Thirst(0),
                    fatigue=Fatigue(0),
                    temperature=TemperatureCelsius(36.5),
                    inventory=(),
                    life_status=LifeStatus.ALIVE,
                    carry_capacity=CarryCapacity(10),
                ),
                AgentBody(
                    entity_id=EntityId("body-2"),
                    location_id=EntityId("loc-1"),
                    health=Health(50),
                    hunger=Hunger(0),
                    thirst=Thirst(0),
                    fatigue=Fatigue(0),
                    temperature=TemperatureCelsius(36.5),
                    inventory=(),
                    life_status=LifeStatus.ALIVE,
                    carry_capacity=CarryCapacity(10),
                ),
            ),
            weather=weather_for_locations(locations),
        ),
    )


@pytest.mark.parametrize("command", COMMAND_VARIANTS)
def test_registry_every_command_is_serializable(command: object) -> None:
    assert decode_domain(encode_domain(command)) == command


@pytest.mark.parametrize("details", EVENT_DETAILS)
def test_registry_every_event_detail_kind_exists(details: EventDetails) -> None:
    assert details.kind in {
        "move",
        "search",
        "take",
        "drop",
        "give",
        "eat",
        "drink",
        "sleep",
        "talk",
        "ask",
        "tell",
        "help",
        "attack",
        "flee",
        "wait",
    }


@given(st.sampled_from(COMMAND_VARIANTS))
@settings(max_examples=15, deadline=None)
def test_property_command_encode_is_idempotent(command: object) -> None:
    encoded = encode_domain(command)
    assert encode_domain(decode_domain(encoded)) == encoded


def test_end_to_end_decoded_command_to_transition_boundary() -> None:
    encoded = encode_domain(Wait())
    command = decode_domain(encoded)
    _proposal, request = admit_agent_command(
        config=SimulationRunConfig(seed=3),
        agent_id=AgentId("agent-1"),
        command=command,
        translator=_Translator(),
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        keys=("e2e", "1"),
    )
    outcome = _world().apply_admitted_request(
        request,
        event_ids=(EventId("evt-e2e"),),
        run_id="run-1",
        tick=0,
    )
    assert isinstance(outcome, TransitionResult)
    assert outcome.outcome is TransitionOutcome.APPLIED
    assert outcome.events[0].details == Waited()
    assert not isinstance(outcome, OperationRejected)
