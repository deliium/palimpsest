"""Regional presentation is detached and agrees across live/restore/seek facts."""

from dataclasses import replace

from api.observer_service import _frame_out
from observer.adapt import adapt_event
from observer.layout import ObserverLayoutCatalog
from observer.project import project_frame
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION, SEMANTIC_EVENT_TYPES
from simulation.engine import WorldEngine
from simulation.observer_facts import scene_from_facts, scene_from_snapshot
from tests.unit.test_regional_travel_checkpoint import _snapshot
from tests.unit.test_regional_travel_lifecycle import _engine, _move


def _frame(scene, mode="replay"):
    return project_frame(
        scene,
        ObserverLayoutCatalog(
            layout_id="regional-test",
            schema_version=OBSERVER_LAYOUT_SCHEMA_VERSION,
            specs=(),
        ),
        mode=mode,
    )


def test_pending_snapshot_and_live_frames_match_and_keep_origin_placement() -> None:
    snapshot = _snapshot()
    restored = WorldEngine.restore_from_snapshot(snapshot)
    facts = restored.detached_objective_facts()
    frame = _frame(scene_from_facts(facts))
    assert frame == _frame(scene_from_snapshot(snapshot))
    agent = frame.world.agents[0]
    assert agent.location_id == agent.journey.origin_location_id == "loc-1"
    assert agent.journey.phase == "preparing"
    assert frame.world.locations[0].region_label == "North"
    waiting = _frame(scene_from_facts(replace(facts, tick=3)))
    assert waiting.world.agents[0].journey.phase == "capacity_wait"
    assert waiting.world.agents[0].location_id == "loc-1"
    # Screen/layout choices never mutate the detached authority or its snapshot.
    assert restored.detached_objective_facts() == facts
    wire = _frame_out(frame).model_dump(mode="json")
    assert wire["world"]["agents"][0]["journey"]["due_tick"] == 2
    assert wire["world"]["locations"][0]["region_id"] == "north"


def test_live_start_arrival_and_timeout_adapt_once_and_frames_replace_journey() -> None:
    engine = _engine(destination_capacity=2, blocker=False)
    started = _move(engine)
    start = next(
        row.event
        for row in started.events
        if row.event.details.kind == "journey_started"
    )
    semantic = adapt_event(start)
    assert semantic.type == "JOURNEY_STARTED"
    assert semantic.journey is not None
    assert semantic.participant_body_ids == ("body-mover",)
    pending = _frame(scene_from_facts(engine.detached_objective_facts()))
    assert pending.world.agents[0].journey is not None
    engine.observe()
    result = engine.resolve_tick(())
    arrived = next(
        row.event
        for row in result.events
        if row.event.details.kind == "journey_arrived"
    )
    assert adapt_event(arrived).type == "JOURNEY_ARRIVED"
    assert adapt_event(arrived).actor_id == "body-mover"
    frame = _frame(scene_from_facts(engine.detached_objective_facts()))
    assert frame.world.agents[0].journey is None
    assert frame.world.agents[0].location_id == "loc-2"
    blocked = _engine(destination_capacity=1, blocker=True)
    _move(blocked)
    blocked.observe()
    blocked.resolve_tick(())
    blocked.observe()
    timed_out = blocked.resolve_tick(())
    ended = next(
        row.event
        for row in timed_out.events
        if row.event.details.kind == "journey_ended"
    )
    assert adapt_event(ended).type == "JOURNEY_ENDED"
    assert len(SEMANTIC_EVENT_TYPES) == 73


def test_channel_off_api_omits_optional_regional_fields() -> None:
    snapshot = _snapshot()
    facts = WorldEngine.restore_from_snapshot(snapshot).detached_objective_facts()
    scene = scene_from_facts(replace(facts, regions_migration=None, journeys=()))
    payload = _frame_out(_frame(scene)).model_dump(mode="json")
    assert all("journey" not in item for item in payload["world"]["agents"])
    assert all("region_id" not in item for item in payload["world"]["locations"])
