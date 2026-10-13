"""Colocated agents see a work site. An empty observation omits the key."""

from __future__ import annotations

import json
import logging

import pytest

from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._perception import project_observations
from world._state import WorldState
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
    ProjectCreated,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationContext

pytestmark = pytest.mark.unit


def _project() -> CollectiveProject:
    return CollectiveProject(
        project_id=EntityId("project-b"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.STORAGE,
        status=CollectiveProjectStatus.OPEN,
        labor_done=1,
        labor_required=2,
        materials_done=1,
        materials_required=1,
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
                item_id=EntityId("wood-1"),
            ),
        ),
    )


def _state(*, visibility: float = 1.0) -> WorldState:
    return WorldState(
        WorldRevision(1),
        locations=(
            make_location(adjacent=("loc-2",), visibility_factor=visibility),
            make_location("loc-2", name="Far", adjacent=("loc-1",)),
        ),
        bodies=(
            alive_body("body-a"),
            alive_body("body-b"),
            alive_body("body-r", location_id="loc-2"),
        ),
        weather=(make_weather(), make_weather("loc-2")),
        collective_projects=(_project(),),
    )


def _event():
    return make_physical_replayable_event(
        event_id=EventId("evt-open"),
        run_id="run-projects",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        cause=ActionCause(RequestId("req-open"), EntityId("body-a")),
        resulting_revision=WorldRevision(1),
        details=ProjectCreated(
            project_id=EntityId("project-b"),
            location_id=EntityId("loc-1"),
            project_kind="storage",
            actor_id=EntityId("body-a"),
            labor_required=2,
            materials_required=1,
        ),
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V19,
    )


def _observe(state, *, active: bool):
    return project_observations(
        world_id=WorldId("world-1"),
        state=state,
        observer_ids=(EntityId("body-a"), EntityId("body-r")),
        context=ObservationContext(tick=2),
        prior_events=(_event(),),
        collective_projects_active=active,
    )


def test_colocated_agent_sees_counters_and_both_contributors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._perception")
    local, remote = _observe(_state(), active=True)
    assert len(local.collective_projects) == 1
    site = local.collective_projects[0]
    assert site.labor_done == 1
    assert site.materials_done == 1
    assert tuple(row.actor_id.value for row in site.contributions) == (
        "body-b",
        "body-a",
    )
    assert remote.collective_projects == ()
    assert "collective_projects_perceived location_id=loc-1 count=1" in caplog.text
    created = [
        item
        for item in local.occurrences
        if item.public_facts.get("project_id") == "project-b"
    ]
    assert created
    assert created[0].public_facts["status"] == "open"
    assert remote.occurrences == ()


def test_hidden_location_omits_the_site(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="world._perception")
    local, _remote = _observe(_state(visibility=0.0), active=True)
    assert local.collective_projects == ()
    assert "collective_projects_hidden reason=content_hidden" in caplog.text


def test_channel_off_encode_omits_the_key(caplog: pytest.LogCaptureFixture) -> None:
    local, _remote = _observe(_state(), active=False)
    assert local.collective_projects == ()
    caplog.set_level(logging.DEBUG, logger="simulation.serialization")
    encoded = json.loads(encode_domain(local))
    assert "collective_projects" not in encoded["data"]
    assert "collective_projects_observation_omitted reason=empty" in caplog.text
    restored = decode_domain(encode_domain(local))
    assert restored.collective_projects == ()
