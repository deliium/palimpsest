"""Replay restores season, weather, quantity, and hazards at any tick."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.clock import Tick
from simulation.engine import WorldEngine
from simulation.journal import (
    PersistenceSerializationError,
    decode_persistence,
    encode_persistence,
)
from simulation.lifecycle import ActionSubmission
from simulation.models import DERIVATION_VERSION, RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    PayloadHash,
    SnapshotId,
    WorldSnapshot,
)
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_weather,
    weather_for_locations,
)
from world._replay import ProjectionError, project_event_prefix
from world.actions import Wait
from world.effects import SystemCause, SystemEffectFamily
from world.environment import (
    Season,
    example_environmental_dynamics,
    scarcity_scenario_dynamics,
    temperature_band,
)
from world.events import (
    EVENT_SCHEMA_REPLAY_V7,
    SeasonChanged,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.values import round_physical


def _engine(seed: int, spec: object | None) -> WorldEngine:
    locations = (make_location("loc-1"),)
    return WorldEngine(
        config=SimulationRunConfig(seed=seed),
        bootstrap=WorldBootstrap(
            world_id=WorldId("world-1"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(alive_body(),),
            weather=weather_for_locations(locations),
            registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        ),
        environmental_dynamics=spec,
    )


def _trace(
    seed: int, spec: object, *, steps: int = 10
) -> tuple[WorldEngine, list[tuple[object, tuple[object, ...], object]]]:
    engine = _engine(seed, spec)
    groups: list[tuple[object, tuple[object, ...], object]] = []
    for _tick in range(steps):
        before = engine._snapshot.world.state
        token = engine.observe().token
        result = engine.resolve_tick(
            (ActionSubmission(token, AgentId("agent-1"), Wait()),)
        )
        groups.append(
            (
                before,
                tuple(record.event for record in result.events),
                engine._snapshot.world.state,
            )
        )
    return engine, groups


def _band(state: object, tick: int, spec: object) -> object:
    rules = default_physical_rules()
    location = state.locations[EntityId("loc-1")]  # type: ignore[attr-defined]
    weather = state.weather[EntityId("loc-1")]  # type: ignore[attr-defined]
    phase_offsets = rules.phase_temperature_offset
    weather_offsets = rules.weather_temperature_offset
    assert phase_offsets is not None and weather_offsets is not None
    ambient = round_physical(
        location.base_temperature.value
        + weather_offsets[weather.condition]
        + phase_offsets[rules.day_phase_for_tick(tick)]
        + spec.offset_for(spec.season_at(tick))  # type: ignore[attr-defined]
    )
    return temperature_band(ambient)


def _scene(state: object, tick: int, spec: object) -> tuple[object, ...]:
    weather = state.weather[EntityId("loc-1")].condition  # type: ignore[attr-defined]
    hazards = tuple(
        hazard.kind
        for hazard in state.active_hazards  # type: ignore[attr-defined]
        if hazard.contains(tick)
    )
    return (
        spec.season_at(tick),  # type: ignore[attr-defined]
        weather,
        _band(state, tick, spec),
        state.resources,  # type: ignore[attr-defined]
        hazards,
    )


def test_prefix_matches_the_live_scene_at_three_ticks(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="simulation.replay")
    spec = scarcity_scenario_dynamics()
    engine, groups = _trace(4, spec)
    for tick in (1, 4, 9):
        before, events, after = groups[tick]
        folded = project_event_prefix(
            before,  # type: ignore[arg-type]
            events,  # type: ignore[arg-type]
            expected_run_id=engine.run_id.value,
            expected_world_id=engine.world_id,
            includes_last_event=True,
            environmental_dynamics=spec,
        )
        assert _scene(folded, tick, spec) == _scene(after, tick, spec)
        if folded.active_hazards:
            hazard = folded.active_hazards[0]
            remaining = hazard.duration_ticks - (tick - hazard.start_tick)
            assert hazard.remaining_ticks(tick) == remaining
    assert any(
        "environment_fold tick=" in record.getMessage() for record in caplog.records
    )
    _again, groups_again = _trace(4, spec)
    _other, groups_other = _trace(11, spec)
    def _season_ticks(
        groups: list[tuple[object, tuple[object, ...], object]],
    ) -> list[int]:
        ticks: list[int] = []
        for _before, events, _after in groups:
            for event in events:
                if event.details.kind == "season_changed":  # type: ignore[attr-defined]
                    ticks.append(event.tick)  # type: ignore[attr-defined]
        return ticks

    assert _season_ticks(groups_again) == _season_ticks(groups_other)

    def _conditions(
        groups: list[tuple[object, tuple[object, ...], object]],
    ) -> tuple[object, ...]:
        return tuple(
            group[2].weather[EntityId("loc-1")].condition  # type: ignore[attr-defined]
            for group in groups
        )

    assert _conditions(groups) == _conditions(groups_again)
    longer = _trace(4, spec, steps=36)[1]
    other_longer = _trace(21, spec, steps=36)[1]
    assert _season_ticks(longer) == _season_ticks(other_longer)
    assert _conditions(longer) != _conditions(other_longer)


def test_season_witness_mismatch_names_tick_and_kind(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger="simulation.replay")
    details = SeasonChanged(Season.SUMMER)
    event = make_physical_replayable_event(
        event_id=EventId("evt-season"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=SystemCause(
            RequestId("sys-1"), SystemEffectFamily.SEASON, EntityId("loc-1"), 0
        ),
        resulting_revision=WorldRevision(1),
        details=details,
        occurrence=build_occurrence_context(
            details, origin_location_id=EntityId("loc-1")
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V7,
    )
    engine = _engine(1, example_environmental_dynamics())
    with pytest.raises(ProjectionError, match="environment_witness_mismatch"):
        project_event_prefix(
            engine._snapshot.world.state,
            (event,),
            expected_run_id="run-1",
            expected_world_id=WorldId("world-1"),
            includes_last_event=True,
            environmental_dynamics=example_environmental_dynamics(),
        )
    assert any(
        record.levelno == logging.ERROR
        and "environment_witness_mismatch tick=1 kind=season_changed"
        in record.getMessage()
        for record in caplog.records
    )
    assert not any("seed" in record.getMessage() for record in caplog.records)
    assert isinstance(event, WorldEvent)


def test_codec_v4_round_trips_hazards_and_v3_rejects_them() -> None:
    from world.environment import ActiveHazard, HazardKind

    location = make_location("loc-1")
    hazard = ActiveHazard(EntityId("loc-1"), HazardKind.HEAT, 4, 6)
    snapshot = WorldSnapshot(
        snapshot_id=SnapshotId("snap-env"),
        run_id=RunId("run-env"),
        world_id=WorldId("world-1"),
        seed=7,
        config=SimulationRunConfig(seed=7),
        registrations=(AgentRegistration(AgentId("agent-1"), EntityId("body-1")),),
        locations=(location,),
        bodies=(alive_body(),),
        items=(),
        resources=(),
        weather=(make_weather(),),
        next_tick=Tick(0),
        revision=WorldRevision(0),
        event_schema_version=EVENT_SCHEMA_REPLAY_V7,
        projector_version=PROJECTOR_VERSION,
        persistence_codec_version="v4",
        derivation_version=DERIVATION_VERSION,
        integrity_hash=PayloadHash("a" * 64),
        predecessor_commit_hash=None,
        active_hazards=(hazard,),
    )
    restored = decode_persistence(encode_persistence(snapshot), WorldSnapshot)
    assert isinstance(restored, WorldSnapshot)
    assert restored.active_hazards == (hazard,)
    assert restored.structures == ()
    document = encode_persistence(snapshot).decode()
    assert "remaining_ticks" not in document
    rejected = document.replace(
        '"persistence_codec_version":"v4"',
        '"persistence_codec_version":"v3"',
    )
    with pytest.raises(PersistenceSerializationError):
        decode_persistence(rejected.encode(), WorldSnapshot)
    assert PERSISTENCE_CODEC_VERSION == "v2"
    assert EVENT_SCHEMA_VERSION == 5
