"""Observer projection does not change committed simulation results."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import pytest

from experiments.reference_scenario import LOC_CAMP, LOC_SPRING
from observer.adapt import adapt_events
from observer.layout import catalog_from_mapping, load_layout
from observer.project import project_frame
from simulation.clock import Tick
from simulation.models import RunId
from simulation.observer_facts import scene_from_facts
from simulation.replay import scene_at_tick
from simulation.runner import SimulationRunner
from simulation.runner_models import CognitionTraceSpec
from simulation.runner_serialization import exact_trajectory_hash
from tests.unit.test_cognition_trace_regression import _short_pair
from tests.unit.test_observer_replay import BODY_ID, RUN_ID, observer_replay_service
from tests.unit.test_observer_stream import _app, _open
from world.effects import ActionCause
from world.events import (
    Waited,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_EMPTY_LAYOUT = catalog_from_mapping(
    {
        "schema_version": "observer-layout-v1",
        "layout_id": "empty-auth",
        "locations": [],
    }
)

_LAYOUT = json.loads(
    Path("src/observer/layouts/reference-v1.json").read_text(encoding="utf-8")
)

_PRIVATE = (
    "relationship",
    "memory",
    "belief",
    "goal",
    "emotion",
    "utterance",
    "private_recipient",
)


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _objective(frame: object) -> object:
    world = frame.world  # type: ignore[attr-defined]
    return {
        "neighbors": {
            item.location_id: list(item.neighbor_ids) for item in world.locations
        },
        "life": {item.entity_id: item.life_status for item in world.agents},
        "holders": {item.item_id: item.holder_id for item in world.items},
        "locations": {item.entity_id: item.location_id for item in world.agents},
    }


def _screen(frame: object) -> object:
    world = frame.world  # type: ignore[attr-defined]
    return {
        item.location_id: None
        if item.presentation is None
        else (item.presentation.screen_position.x, item.presentation.screen_position.y)
        for item in world.locations
    }


@pytest.mark.asyncio
async def test_projection_and_reads_leave_committed_facts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, events = observer_replay_service()
    before_ids = tuple(event.event_id.value for event in events)
    before_hash = _digest(before_ids)
    history = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    scene_facts = tuple(
        (body.entity_id.value, body.location_id.value) for body in history.scene.bodies
    )
    with caplog.at_level(logging.DEBUG):
        frame = project_frame(
            history.scene, load_layout("reference-v1"), mode="replay", events=()
        )
        adapted = adapt_events(events)
    assert (
        tuple(
            (body.entity_id.value, body.location_id.value)
            for body in history.scene.bodies
        )
        == scene_facts
    )
    assert _digest(before_ids) == before_hash
    assert tuple(event.event_id.value for event in events) == before_ids
    assert [item.location_id for item in frame.world.locations]
    assert "observer_frame_projected" in caplog.text
    assert "observer_event_adapted" in caplog.text
    again = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    assert (
        tuple(
            (body.entity_id.value, body.location_id.value)
            for body in again.scene.bodies
        )
        == scene_facts
    )
    assert again.snapshot_body_locations == ((BODY_ID, LOC_CAMP),)
    assert scene_facts == ((BODY_ID, LOC_SPRING),)
    assert [(item.tick, item.sequence) for item in adapted] == [
        (event.tick, event.sequence) for event in events
    ]


def test_sequence_gaps_are_preserved() -> None:
    details = Waited()
    first = make_physical_replayable_event(
        event_id=EventId("evt-gap-0"),
        run_id=RUN_ID,
        world_id=WorldId("world-observer"),
        tick=3,
        sequence=0,
        cause=ActionCause(RequestId("req-gap-0"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId(LOC_CAMP)
        ),
    )
    second = make_physical_replayable_event(
        event_id=EventId("evt-gap-7"),
        run_id=RUN_ID,
        world_id=WorldId("world-observer"),
        tick=3,
        sequence=7,
        cause=ActionCause(RequestId("req-gap-7"), EntityId(BODY_ID)),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId(LOC_CAMP)
        ),
    )
    adapted = adapt_events((first, second))
    assert [(item.tick, item.sequence) for item in adapted] == [(3, 0), (3, 7)]


@pytest.mark.asyncio
async def test_layouts_change_coordinates_only() -> None:
    service, _events = observer_replay_service()
    history = await scene_at_tick(service, RunId(RUN_ID), target_tick=Tick(1))
    raw = _LAYOUT
    shifted = json.loads(json.dumps(raw))
    shifted["layout_id"] = "shifted-v1"
    shifted["locations"][0]["screen_position"]["x"] = 40.0
    left = project_frame(
        history.scene, catalog_from_mapping(raw), mode="replay", events=()
    )
    right = project_frame(
        history.scene, catalog_from_mapping(shifted), mode="replay", events=()
    )
    assert _objective(left) == _objective(right)
    assert _screen(left) != _screen(right)


@pytest.mark.asyncio
async def test_missed_events_resume_without_duplicates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from api.observer_service import ObserverReadService

    service, _events = observer_replay_service()
    reader = ObserverReadService(service)
    page = await reader.events(
        RUN_ID,
        after_tick=0,
        after_sequence=0,
        limit=10,
        layout_id="reference-v1",
    )
    assert [item.event_id for item in page.events] == ["evt-wait"]
    app = _app()
    app.state.observer_run_completed = lambda _run_id: True

    async def _collect(query: bytes) -> list[dict[str, object]]:
        session, task = await _open(
            app,
            f"/v1/simulations/{RUN_ID}/observer/stream",
            query=query,
        )
        found: list[dict[str, object]] = []
        try:
            while True:
                payload = await session.next_payload()
                found.append(payload)
                if payload["kind"] == "completion":
                    break
        finally:
            await session.disconnect()
            task.cancel()
        return found

    with caplog.at_level(logging.DEBUG):
        missed = await _collect(b"after_tick=0&after_sequence=0")
        resumed = await _collect(b"after_tick=0&after_sequence=1")
    missed_ids = [
        item["event"]["event_id"] for item in missed if item["kind"] == "event"
    ]
    resumed_ids = [
        item["event"]["event_id"] for item in resumed if item["kind"] == "event"
    ]
    assert missed_ids == ["evt-wait"]
    assert resumed_ids == []
    assert resumed[0]["kind"] == "hello"
    hello = json.dumps(resumed[0])
    state = await reader.state(RUN_ID, tick=None, layout_id="reference-v1")
    encoded = state.model_dump_json()
    for key in _PRIVATE:
        assert f'"{key}"' not in hello
        assert f'"{key}"' not in encoded
    assert "observer_stream_gap" in caplog.text
    assert "observer_stream_open" in caplog.text


class _ProjectingRunner(SimulationRunner):
    async def run_tick(self):  # type: ignore[override]
        receipt = await super().run_tick()
        scene = scene_from_facts(self.engine.detached_objective_facts())
        project_frame(scene, _EMPTY_LAYOUT, mode="live")
        return receipt


@pytest.mark.asyncio
async def test_same_seed_with_and_without_projection() -> None:
    config = _short_pair(cognition_trace=CognitionTraceSpec())

    async def _drive(
        runner_type: type[SimulationRunner],
    ) -> tuple[str, tuple[str, ...]]:
        async with await runner_type.from_config(
            config, run_id=RunId("run-observer-auth")
        ) as runner:
            result = await runner.run()
            exported = tuple(
                event.event_id.value for event in runner.engine.export_events().events
            )
        return (
            exact_trajectory_hash(
                run_id="run-observer-auth",
                tick_receipts=result.finalized_tick_receipts,
            ),
            exported,
        )

    plain = await _drive(SimulationRunner)
    projected = await _drive(_ProjectingRunner)
    assert plain[0] == projected[0]
    assert plain[1] == projected[1]


@pytest.mark.asyncio
async def test_observer_graphical_projection_does_not_change_trajectory(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from experiments.observer_graphical_scenario import (
        build_observer_graphical_scenario,
    )

    bundle = build_observer_graphical_scenario(max_ticks=4, death_tick=1)
    config = bundle.config

    async def _hash(runner_type: type[SimulationRunner]) -> str:
        async with await runner_type.from_config(
            config, run_id=RunId("run-observer-graphical-auth")
        ) as runner:
            result = await runner.run()
        return exact_trajectory_hash(
            run_id="run-observer-graphical-auth",
            tick_receipts=result.finalized_tick_receipts,
        )

    with caplog.at_level(logging.INFO):
        plain = await _hash(SimulationRunner)
        projected = await _hash(_ProjectingRunner)
    assert plain == projected
    assert plain  # non-empty hash
