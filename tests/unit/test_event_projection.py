"""Private event projector contracts for effect-complete replay."""

from __future__ import annotations

import pytest

from world._replay import ProjectionError, ProjectionErrorCode, project_events
from world._state import WorldState
from world.events import (
    Dropped,
    EventDetails,
    Given,
    Taken,
    Waited,
    WorldEvent,
    make_replayable_event,
)
from world.identifiers import (
    EntityId,
    EventId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import AgentBody, Item, LifeStatus, Location
from world.values import Fatigue, Health, Hunger, TemperatureCelsius, Thirst

_RUN = "run-1"
_WORLD = WorldId("world-1")


def _alive(
    entity_id: str,
    location_id: str,
    inventory: tuple[EntityId, ...] = (),
) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(50),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
    )


def _base_state(
    *,
    items: tuple[Item, ...] = (),
    bodies: tuple[AgentBody, ...] | None = None,
    revision: int = 0,
) -> WorldState:
    return WorldState(
        WorldRevision(revision),
        locations=(
            Location(entity_id=EntityId("loc-1"), name="Camp"),
            Location(entity_id=EntityId("loc-2"), name="River"),
        ),
        items=items,
        bodies=bodies
        if bodies is not None
        else (
            _alive("body-1", "loc-1"),
            _alive("body-2", "loc-1"),
        ),
        resources=(),
        weather=(),
    )


def _event(
    *,
    event_id: str,
    tick: int,
    sequence: int,
    revision: int,
    details: EventDetails,
    actor_id: str | None = "body-1",
) -> WorldEvent:
    return make_replayable_event(
        event_id=EventId(event_id),
        run_id=_RUN,
        world_id=_WORLD,
        tick=tick,
        sequence=sequence,
        request_id=RequestId(f"req-{event_id}"),
        resulting_revision=WorldRevision(revision),
        details=details,
        actor_id=None if actor_id is None else EntityId(actor_id),
    )


def test_empty_events_returns_same_state() -> None:
    state = _base_state()
    assert project_events(
        state, (), expected_run_id=_RUN, expected_world_id=_WORLD
    ) is state


def test_event_only_wait_preserves_revision_and_items() -> None:
    state = _base_state()
    events = (
        _event(
            event_id="evt-1",
            tick=0,
            sequence=0,
            revision=0,
            details=Waited(),
            actor_id="body-1",
        ),
    )
    projected = project_events(
        state, events, expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert projected.revision == WorldRevision(0)
    assert projected.items == state.items
    assert projected.bodies == state.bodies


def test_take_drop_give_projection_applies_recorded_effects() -> None:
    ground = Item(
        entity_id=EntityId("item-1"),
        name="Rock",
        location_id=EntityId("loc-1"),
    )
    state = _base_state(items=(ground,))
    take = _event(
        event_id="evt-take",
        tick=0,
        sequence=0,
        revision=1,
        details=Taken(EntityId("item-1"), resulting_holder_id=EntityId("body-1")),
    )
    after_take = project_events(
        state, (take,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_take.revision == WorldRevision(1)
    assert after_take.items[EntityId("item-1")].holder_id == EntityId("body-1")
    assert EntityId("item-1") in after_take.bodies[EntityId("body-1")].inventory

    give = _event(
        event_id="evt-give",
        tick=1,
        sequence=0,
        revision=2,
        details=Given(
            EntityId("body-2"),
            EntityId("item-1"),
            resulting_holder_id=EntityId("body-2"),
        ),
    )
    after_give = project_events(
        after_take, (give,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_give.items[EntityId("item-1")].holder_id == EntityId("body-2")
    assert EntityId("item-1") not in after_give.bodies[EntityId("body-1")].inventory
    assert EntityId("item-1") in after_give.bodies[EntityId("body-2")].inventory

    drop = _event(
        event_id="evt-drop",
        tick=2,
        sequence=0,
        revision=3,
        details=Dropped(
            EntityId("item-1"), resulting_location_id=EntityId("loc-1")
        ),
        actor_id="body-2",
    )
    after_drop = project_events(
        after_give, (drop,), expected_run_id=_RUN, expected_world_id=_WORLD
    )
    assert after_drop.items[EntityId("item-1")].location_id == EntityId("loc-1")
    assert after_drop.items[EntityId("item-1")].holder_id is None
    assert EntityId("item-1") not in after_drop.bodies[EntityId("body-2")].inventory


def test_rejects_mixed_run_world_duplicate_gap_and_revision() -> None:
    state = _base_state()
    wait = _event(
        event_id="evt-1",
        tick=0,
        sequence=0,
        revision=0,
        details=Waited(),
    )

    wrong_run = make_replayable_event(
        event_id=EventId("evt-2"),
        run_id="other-run",
        world_id=_WORLD,
        tick=0,
        sequence=0,
        request_id=RequestId("req-2"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    with pytest.raises(ProjectionError) as run_err:
        project_events(
            state, (wrong_run,), expected_run_id=_RUN, expected_world_id=_WORLD
        )
    assert run_err.value.code == ProjectionErrorCode.RUN_ID_MISMATCH.value

    wrong_world = make_replayable_event(
        event_id=EventId("evt-3"),
        run_id=_RUN,
        world_id=WorldId("world-other"),
        tick=0,
        sequence=0,
        request_id=RequestId("req-3"),
        resulting_revision=WorldRevision(0),
        details=Waited(),
        actor_id=EntityId("body-1"),
    )
    with pytest.raises(ProjectionError) as world_err:
        project_events(
            state, (wrong_world,), expected_run_id=_RUN, expected_world_id=_WORLD
        )
    assert world_err.value.code == ProjectionErrorCode.WORLD_ID_MISMATCH.value

    with pytest.raises(ProjectionError) as dup:
        project_events(
            state, (wait, wait), expected_run_id=_RUN, expected_world_id=_WORLD
        )
    assert dup.value.code == ProjectionErrorCode.DUPLICATE_EVENT.value

    gap = (
        wait,
        _event(
            event_id="evt-gap",
            tick=0,
            sequence=2,
            revision=0,
            details=Waited(),
        ),
    )
    with pytest.raises(ProjectionError) as order:
        project_events(state, gap, expected_run_id=_RUN, expected_world_id=_WORLD)
    assert order.value.code == ProjectionErrorCode.INVALID_ORDERING.value

    bad_rev = (
        _event(
            event_id="evt-rev",
            tick=0,
            sequence=0,
            revision=5,
            details=Waited(),
        ),
    )
    with pytest.raises(ProjectionError) as rev:
        project_events(state, bad_rev, expected_run_id=_RUN, expected_world_id=_WORLD)
    assert rev.value.code == ProjectionErrorCode.REVISION_MISMATCH.value


def test_projector_does_not_import_rules_module() -> None:
    from pathlib import Path

    import world._replay as replay_mod

    source = Path(replay_mod.__file__).read_text(encoding="utf-8")
    assert "from world._rules" not in source
    assert "import world._rules" not in source
    assert "world._operations" not in source
