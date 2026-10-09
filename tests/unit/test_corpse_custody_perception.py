"""Colocated agents see corpse items without a foreign holder id."""

from __future__ import annotations

from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._perception import PerceptionService, _public_facts_for_role
from world._state import WorldState
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V16,
    CorpseCustodyOpened,
    OccurrenceContext,
    PossessionClaimAsserted,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import LifeStatus, copy_body
from world.observations import (
    ObservationAudienceRole,
    ObservationContext,
    ObservedItemPlacement,
)
from world.values import Health


def _state():
    item = make_item("item-1", location_id=None, holder_id="body-dead")
    corpse = copy_body(
        alive_body("body-dead", inventory=(item.entity_id,)),
        life_status=LifeStatus.DEAD,
        health=Health(0),
    )
    near = alive_body("body-near")
    far = alive_body("body-far", location_id="loc-2")
    locations = (
        make_location("loc-1", adjacent=("loc-2",)),
        make_location("loc-2", adjacent=("loc-1",)),
    )
    state = WorldState(
        WorldRevision(1),
        locations=locations,
        items=(item,),
        bodies=(corpse, near, far),
        weather=tuple(make_weather(loc.entity_id.value) for loc in locations),
        corpse_custody_item_ids=frozenset({item.entity_id}),
    )
    return state, item


def _observe(state: WorldState, observer: str, *, active: bool):
    observations = PerceptionService(possession_succession_active=active).project(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId(observer),),
        context=ObservationContext(tick=1),
    )
    return observations[0]


def test_colocated_agent_sees_corpse_item_without_holder_id() -> None:
    state, item = _state()
    seen = _observe(state, "body-near", active=True)
    corpse_items = [
        observed
        for observed in seen.items
        if observed.placement is ObservedItemPlacement.CORPSE_HERE
    ]
    assert len(corpse_items) == 1
    assert corpse_items[0].entity_id == item.entity_id
    assert not hasattr(corpse_items[0], "holder_id")
    far = _observe(state, "body-far", active=True)
    assert all(
        observed.placement is not ObservedItemPlacement.CORPSE_HERE
        for observed in far.items
    )
    hidden = _observe(state, "body-near", active=False)
    assert all(
        observed.placement is not ObservedItemPlacement.CORPSE_HERE
        for observed in hidden.items
    )


def test_custody_occurrence_facts_include_doctrine_for_a_claim() -> None:
    opened = CorpseCustodyOpened(
        EntityId("body-dead"), EntityId("loc-1"), (EntityId("item-1"),)
    )
    context = build_occurrence_context(opened, origin_location_id=EntityId("loc-1"))
    assert context.affected_entity_ids[0] == EntityId("body-dead")
    event = make_physical_replayable_event(
        event_id=EventId("evt-claim"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=SystemCause(
            RequestId("req-claim"),
            SystemEffectFamily.LIFECYCLE,
            EntityId("body-dead"),
            0,
        ),
        resulting_revision=WorldRevision(1),
        details=PossessionClaimAsserted(
            EntityId("body-dead"), "children_should_inherit", EntityId("item-1")
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V16,
    )
    facts = _public_facts_for_role(event, ObservationAudienceRole.BYSTANDER)
    assert facts["decedent_id"] == "body-dead"
    assert facts["item_ids"] == ["item-1"]
    assert facts["doctrine"] == "children_should_inherit"
    assert "actor_id" not in facts
