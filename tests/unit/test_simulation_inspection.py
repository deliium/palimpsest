"""Detached inspection projector: objective + agent-visible without live observe."""

from __future__ import annotations

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import EnginePhase, WorldEngine
from simulation.inspection import (
    MAX_INSPECTION_PAGE_SIZE,
    AgentVisibleProjection,
    DetachedInspectionProjector,
    InspectionAvailability,
    InspectionError,
    InspectionReplayProjection,
    InspectionSurface,
    clamp_inspection_page_limit,
    project_replay_for_inspection,
)
from simulation.lifecycle import ActionSubmission
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    EVENT_SCHEMA_VERSION,
    PERSISTENCE_CODEC_VERSION,
    PROJECTOR_VERSION,
    ReplayMode,
    ReplayResult,
    ReplayStatus,
)
from simulation.replay import ReplayOutcome
from simulation.runner_models import DetachedObjectiveProjection
from tests.simulation_helpers import make_item, make_location, weather_for_locations
from world.actions import Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import AgentBody, LifeStatus
from world.observations import Observation
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

pytestmark = pytest.mark.unit


def _alive(entity_id: str, location_id: str = "loc-1") -> AgentBody:
    return AgentBody(
        entity_id=EntityId(entity_id),
        location_id=EntityId(location_id),
        health=Health(100),
        hunger=Hunger(0),
        thirst=Thirst(0),
        fatigue=Fatigue(0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(10),
    )


def _engine() -> WorldEngine:
    locations = (make_location("loc-1", name="Camp"),)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-1"),
        revision=WorldRevision(0),
        locations=locations,
        items=(make_item("item-1", name="Rock", location_id="loc-1"),),
        bodies=(_alive("body-1"), _alive("body-2")),
        weather=weather_for_locations(locations),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-1")),
            AgentRegistration(AgentId("agent-2"), EntityId("body-2")),
        ),
    )
    return WorldEngine(
        bootstrap=bootstrap,
        config=SimulationRunConfig(seed=7),
        run_id=RunId("run-inspect-1"),
    )


def test_clamp_inspection_page_limit_fail_closed() -> None:
    assert clamp_inspection_page_limit(50) == 50
    with pytest.raises(InspectionError) as exc:
        clamp_inspection_page_limit(MAX_INSPECTION_PAGE_SIZE + 1)
    assert exc.value.code == "page_limit_exceeded"
    with pytest.raises(InspectionError) as exc2:
        clamp_inspection_page_limit(0)
    assert exc2.value.code == "invalid_page_limit"


def test_detached_projection_does_not_mutate_phase() -> None:
    engine = _engine()
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    projector = DetachedInspectionProjector()
    objective = projector.project_objective(engine)
    assert type(objective) is DetachedObjectiveProjection
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    batch = projector.project_observation_batch(engine)
    assert len(batch.observations) == 2
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    view = projector.project_agent_visible(engine, AgentId("agent-1"))
    assert type(view) is AgentVisibleProjection
    assert type(view.observation) is Observation
    assert view.entity_id == "body-1"
    assert view.surface is InspectionSurface.PUBLIC
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION


def test_detached_agent_visible_matches_live_observe_content() -> None:
    engine = _engine()
    projector = DetachedInspectionProjector()
    detached = projector.project_agent_visible(engine, AgentId("agent-1"))
    live_batch = engine.observe()
    live = live_batch.for_observer(EntityId("body-1"))
    assert detached.observation.observer_id == live.observer_id
    assert detached.observation.tick == live.tick
    assert len(detached.observation.visible_bodies) == len(live.visible_bodies)
    assert len(detached.observation.items) == len(live.items)


def test_project_replay_for_inspection_strips_engine() -> None:
    engine = _engine()
    outcome = ReplayOutcome(
        result=ReplayResult(
            run_id=RunId("run-inspect-1"),
            status=ReplayStatus.OK,
            mode=ReplayMode.READONLY,
            snapshot_id=None,
            snapshot_next_tick=None,
            target_tick=engine.tick,
            events_applied=0,
            event_schema_version=EVENT_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        ),
        engine=engine,
        predecessor_commit_hash=None,
    )
    projection = project_replay_for_inspection(outcome, agent_id=AgentId("agent-1"))
    assert type(projection) is InspectionReplayProjection
    assert projection.availability is InspectionAvailability.AVAILABLE
    assert projection.objective is not None
    assert projection.agent_visible is not None
    assert not hasattr(projection, "engine")
    fields = getattr(InspectionReplayProjection, "__dataclass_fields__", {})
    assert "engine" not in fields


def test_project_replay_failed_is_unavailable() -> None:
    outcome = ReplayOutcome(
        result=ReplayResult(
            run_id=RunId("run-missing"),
            status=ReplayStatus.TARGET_UNREACHABLE,
            mode=ReplayMode.READONLY,
            snapshot_id=None,
            snapshot_next_tick=None,
            target_tick=None,
            events_applied=0,
            event_schema_version=EVENT_SCHEMA_VERSION,
            projector_version=PROJECTOR_VERSION,
            persistence_codec_version=PERSISTENCE_CODEC_VERSION,
        ),
        engine=None,
        predecessor_commit_hash=None,
    )
    projection = project_replay_for_inspection(outcome)
    assert projection.availability is InspectionAvailability.UNAVAILABLE
    assert projection.objective is None
    assert projection.agent_visible is None


def test_subjective_page_rejects_public_surface() -> None:
    from simulation.inspection import SubjectiveInspectionPage

    with pytest.raises(InspectionError) as exc:
        SubjectiveInspectionPage(
            run_id="run-1",
            owner_id="agent-1",
            limit=10,
            item_count=0,
            next_cursor=None,
            availability=InspectionAvailability.AVAILABLE,
            surface=InspectionSurface.PUBLIC,
        )
    assert exc.value.code == "subjective_requires_debug_surface"


def test_detached_projection_survives_after_tick() -> None:
    engine = _engine()
    batch = engine.observe()
    engine.resolve_tick(
        (
            ActionSubmission(
                batch.token,
                AgentId("agent-1"),
                Wait(),
            ),
        )
    )
    projector = DetachedInspectionProjector()
    # After commit, phase returns to awaiting observation for the next tick.
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
    view = projector.project_agent_visible(engine, AgentId("agent-1"))
    assert view.tick == engine.tick.value
    assert engine.phase is EnginePhase.AWAITING_OBSERVATION
