"""Observer semantics expose a work site without a leader."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from observer.adapt import adapt_event
from observer.contracts import ScreenPoint
from observer.layout import LocationVisualSpec, ObserverLayoutCatalog
from observer.project import project_frame
from observer.version import OBSERVER_LAYOUT_SCHEMA_VERSION, SEMANTIC_EVENT_TYPES
from simulation.bootstrap import AgentRegistration
from simulation.observer_facts import ObjectiveScene
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.collective_projects import (
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectStatus,
    ProjectContribution,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V19,
    OccurrenceContext,
    ProjectAbandoned,
    ProjectCompleted,
    ProjectContributed,
    ProjectCreated,
    ProjectShortage,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

_PROJECT_TYPES = (
    "PROJECT_CREATED",
    "PROJECT_CONTRIBUTED",
    "PROJECT_SHORTAGE",
    "PROJECT_ABANDONED",
    "PROJECT_COMPLETED",
)


def test_semantic_catalog_counts_sixty_six() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 69
    for name in _PROJECT_TYPES:
        assert name in SEMANTIC_EVENT_TYPES


def test_project_events_adapt(caplog: pytest.LogCaptureFixture) -> None:
    project_id = EntityId("project-1")
    actor = EntityId("body-a")
    details = (
        ProjectCreated(
            project_id=project_id,
            location_id=EntityId("loc-1"),
            project_kind="bridge",
            actor_id=actor,
            labor_required=4,
            materials_required=2,
        ),
        ProjectContributed(
            project_id=project_id,
            actor_id=actor,
            accepted=False,
            labor_done=0,
            materials_done=0,
        ),
        ProjectShortage(project_id=project_id, actor_id=actor, shortage_count=1),
        ProjectAbandoned(project_id=project_id, idle_ticks=4),
        ProjectCompleted(
            project_id=project_id,
            project_kind="bridge",
            structure_id=EntityId("structure-project-1"),
        ),
    )
    caplog.set_level(logging.DEBUG, logger="observer.adapt")
    adapted = []
    for index, item in enumerate(details):
        event = make_physical_replayable_event(
            event_id=EventId(f"evt-{index}"),
            run_id="run-observer",
            world_id=WorldId("world-observer"),
            tick=1,
            sequence=index,
            cause=ActionCause(RequestId(f"req-{index}"), actor),
            resulting_revision=WorldRevision(1),
            details=item,
            occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
            schema_version=EVENT_SCHEMA_REPLAY_V19,
        )
        adapted.append(adapt_event(event))
    assert [item.type for item in adapted] == list(_PROJECT_TYPES)
    assert "observer_event_adapted kind=project_created" in caplog.text


def test_scene_lists_sorted_contributors_without_a_leader() -> None:
    project = CollectiveProject(
        project_id=EntityId("project-b"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.BRIDGE,
        status=CollectiveProjectStatus.OPEN,
        labor_done=1,
        labor_required=4,
        materials_done=1,
        materials_required=2,
        opened_tick=1,
        last_accepted_tick=1,
        shortage_count=0,
        contributions=(
            ProjectContribution(
                actor_id=EntityId("body-b"),
                tick=1,
                accepted=True,
                labor_delta=0,
            ),
            ProjectContribution(
                actor_id=EntityId("body-a"),
                tick=1,
                accepted=True,
                labor_delta=1,
            ),
        ),
    )
    location = make_location()
    scene = ObjectiveScene(
        run_id="run-observer",
        world_id="world-observer",
        tick=1,
        revision=1,
        locations=(location,),
        bodies=(alive_body("body-a"), alive_body("body-b")),
        items=(),
        resources=(),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-1"), EntityId("body-a")),
        ),
        collective_projects=(project,),
    )
    frame = project_frame(
        scene,
        ObserverLayoutCatalog(
            layout_id="projects",
            schema_version=OBSERVER_LAYOUT_SCHEMA_VERSION,
            specs=(
                LocationVisualSpec(
                    location_id="loc-1",
                    display_name="Camp",
                    screen_position=ScreenPoint(0.0, 0.0),
                    visual_bounds=None,
                    theme=None,
                    icon_ref=None,
                    background_ref=None,
                    connection_anchors=(),
                    slot_anchors=(),
                ),
            ),
        ),
        mode="live",
    )
    observed = frame.world.collective_projects
    assert len(observed) == 1
    assert observed[0].contributor_ids == ("body-a", "body-b")
    assert "leader" not in observed[0].__dataclass_fields__
    assert "leader_id" not in frame.world.__dataclass_fields__
