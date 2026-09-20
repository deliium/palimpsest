"""Private deterministic perception projector."""

from __future__ import annotations

import pytest

from tests.simulation_helpers import (
    connected_locations,
    make_item,
    make_resource,
    make_weather,
)
from world._perception import project_observations
from world._state import WorldState
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import (
    CONTENT_VISIBILITY_THRESHOLD,
    PERCEPTION_FIELD_ACCESS,
    ObservationContext,
    ObservationFieldAccess,
    ObservedItemPlacement,
    ObservedLocation,
    ObservedResource,
    ObservedSelf,
)
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
    WeatherCondition,
)


def _body(
    entity_id: str,
    location_id: str,
    *,
    inventory: tuple[EntityId, ...] = (),
    dead: bool = False,
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(0 if dead else 100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.DEAD if dead else LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _rich_state() -> WorldState:
    cup = make_item("item-cup", name="Cup", location_id=None, holder_id="body-1")
    rock = make_item("item-rock", name="Rock", location_id="loc-1")
    distant = make_item("item-far", name="Far", location_id="loc-2")
    return WorldState(
        WorldRevision(3),
        locations=connected_locations(("loc-1", "Camp"), ("loc-2", "Forest")),
        items=(cup, rock, distant),
        resources=(
            make_resource(
                "res-b", name="Berries", location_id="loc-1", quantity=2.0, unit="kg"
            ),
            make_resource(
                "res-a", name="Water", location_id="loc-1", quantity=1.0, unit="L"
            ),
            make_resource(
                "res-far", name="Ore", location_id="loc-2", quantity=5.0, unit="kg"
            ),
        ),
        bodies=(
            _body("body-1", "loc-1", inventory=(EntityId("item-cup"),)),
            _body("body-2", "loc-2"),
            _body("body-dead", "loc-1", dead=True),
        ),
        weather=(
            make_weather("loc-1", condition=WeatherCondition.CLEAR),
            make_weather("loc-2", condition=WeatherCondition.CLOUDY),
        ),
    )


def test_observations_follow_registration_order_and_v1_policy() -> None:
    state = _rich_state()
    # Daytime keeps cloudy visibility above the ground-content threshold.
    context = ObservationContext(tick=12)
    observations = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-2"), EntityId("body-1")),
        context=context,
    )
    assert [obs.observer_id for obs in observations] == [
        EntityId("body-2"),
        EntityId("body-1"),
    ]
    first, second = observations
    assert isinstance(first.self_body, ObservedSelf)
    assert first.self_body.entity_id == EntityId("body-2")
    assert first.locations == (
        ObservedLocation(entity_id=EntityId("loc-2"), name="Forest"),
    )
    assert not hasattr(first.locations[0], "body_capacity")
    assert [item.entity_id for item in first.items] == [EntityId("item-far")]
    assert first.items[0].placement is ObservedItemPlacement.GROUND_HERE
    assert [resource.entity_id for resource in first.resources] == [EntityId("res-far")]
    assert isinstance(first.resources[0], ObservedResource)
    assert not hasattr(first.resources[0], "regeneration_per_tick")
    assert first.weather_condition == WeatherCondition.CLOUDY

    assert second.self_body is not None
    assert second.self_body.entity_id == EntityId("body-1")
    assert [item.entity_id for item in second.items] == [
        EntityId("item-cup"),
        EntityId("item-rock"),
    ]
    assert second.items[0].placement is ObservedItemPlacement.HELD_BY_SELF
    assert [resource.entity_id for resource in second.resources] == [
        EntityId("res-a"),
        EntityId("res-b"),
    ]
    assert all(isinstance(obs.self_body, ObservedSelf) for obs in observations)
    for obs in observations:
        body = obs.self_body
        assert body is not None
        assert body.entity_id == obs.observer_id
        assert obs.occurrences == ()
        assert obs.communications == ()


def test_dead_bodies_still_receive_observations() -> None:
    state = _rich_state()
    observations = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-dead"),),
    )
    assert observations[0].self_body is not None
    assert observations[0].self_body.life_status is LifeStatus.DEAD
    assert observations[0].locations[0].entity_id == EntityId("loc-1")


def test_missing_observer_fails_before_any_result() -> None:
    state = _rich_state()
    with pytest.raises(ValueError, match="missing from world state"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids=(EntityId("body-1"), EntityId("ghost")),
        )


def test_repeated_projection_is_idempotent_and_detached() -> None:
    state = _rich_state()
    first = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
    )
    second = project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-1"),),
    )
    assert first == second
    assert first[0].self_body is not None
    assert first[0].self_body.entity_id == EntityId("body-1")
    assert first[0].items[0].entity_id == EntityId("item-cup")


def test_unordered_or_duplicate_observers_rejected() -> None:
    state = _rich_state()
    with pytest.raises(TypeError, match="ordered sequence"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids={EntityId("body-1")},  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="duplicates"):
        project_observations(
            world_id=WorldId("world-1"),
            state=state,
            observer_ids=(EntityId("body-1"), EntityId("body-1")),
        )


def test_visibility_matrix_constants_match_projector_threshold() -> None:
    assert CONTENT_VISIBILITY_THRESHOLD == 0.5
    assert (
        PERCEPTION_FIELD_ACCESS["ground_items"]
        is ObservationFieldAccess.VISIBILITY_GATED
    )
    assert PERCEPTION_FIELD_ACCESS["exits"] is ObservationFieldAccess.ALWAYS_SELF
    assert PERCEPTION_FIELD_ACCESS["held_items"] is ObservationFieldAccess.ALWAYS_SELF


def test_perception_service_projects_prior_events_by_audience() -> None:
    from world._perception import PerceptionService
    from world.effects import ActionCause
    from world.events import (
        Moved,
        Talked,
        build_occurrence_context,
        make_physical_replayable_event,
    )
    from world.identifiers import EventId, RequestId
    from world.observations import ObservationAudienceRole, ObservationSourceKind

    state = _rich_state()
    move = make_physical_replayable_event(
        event_id=EventId("evt-move"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=0,
        cause=ActionCause(RequestId("r-move"), EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=Moved(
            EntityId("loc-2"),
            resulting_location_id=EntityId("loc-2"),
            fatigue_delta=5.0,
            resulting_fatigue=5.0,
        ),
        occurrence=build_occurrence_context(
            Moved(
                EntityId("loc-2"),
                resulting_location_id=EntityId("loc-2"),
                fatigue_delta=5.0,
                resulting_fatigue=5.0,
            ),
            origin_location_id=EntityId("loc-1"),
        ),
    )
    talk = make_physical_replayable_event(
        event_id=EventId("evt-talk"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=0,
        sequence=1,
        cause=ActionCause(RequestId("r-talk"), EntityId("body-1")),
        resulting_revision=WorldRevision(1),
        details=Talked(EntityId("body-dead"), "psst"),
        occurrence=build_occurrence_context(
            Talked(EntityId("body-dead"), "psst"),
            origin_location_id=EntityId("loc-1"),
        ),
    )
    context = ObservationContext(tick=1)
    service = PerceptionService()
    body1, body2, dead = service.project(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(
            EntityId("body-1"),
            EntityId("body-2"),
            EntityId("body-dead"),
        ),
        context=context,
        prior_events=(move, talk),
    )
    assert body1.occurrences[0].audience_role is ObservationAudienceRole.ACTOR
    assert body1.communications[0].text == "psst"
    assert body1.communications[0].provenance.source_kind is (
        ObservationSourceKind.COMMUNICATION
    )
    # body-2 is at destination of the move.
    assert body2.occurrences[0].audience_role is ObservationAudienceRole.WITNESS
    assert body2.communications == ()
    assert dead.communications[0].listener_id == EntityId("body-dead")
    assert dead.communications[0].text == "psst"
