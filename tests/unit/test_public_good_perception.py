"""Public-good history and events are local, opt-in observations."""

from __future__ import annotations

import json

import pytest

from simulation.serialization import decode_domain, encode_domain
from tests.simulation_helpers import alive_body, make_location, make_weather
from world._perception import project_observations
from world._state import WorldState
from world.collective_projects import (
    CollectiveProject,
    CollectiveProjectKind,
    CollectiveProjectStatus,
    PublicGoodAct,
    PublicGoodActKind,
    PublicGoodActSource,
)
from world.effects import ActionCause
from world.events import (
    EVENT_SCHEMA_REPLAY_V20,
    OccurrenceContext,
    ProjectContributed,
    PublicGoodBenefit,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision
from world.observations import ObservationContext
from world.production import Structure, StructureKind

pytestmark = pytest.mark.unit


def _state() -> WorldState:
    structure_id = EntityId("structure-well")
    project = CollectiveProject(
        project_id=EntityId("project-well"),
        location_id=EntityId("loc-1"),
        kind=CollectiveProjectKind.WELL,
        status=CollectiveProjectStatus.COMPLETED,
        labor_done=3,
        labor_required=3,
        materials_done=2,
        materials_required=2,
        opened_tick=0,
        last_accepted_tick=1,
        shortage_count=0,
        linked_structure_id=structure_id,
        public_acts=(
            PublicGoodAct(
                actor_id=EntityId("body-b"),
                tick=2,
                act=PublicGoodActKind.DRAW,
                source=PublicGoodActSource.COMMAND,
            ),
        ),
    )
    return WorldState(
        WorldRevision(1),
        locations=(
            make_location(adjacent=("loc-2",)),
            make_location("loc-2", name="Far", adjacent=("loc-1",)),
        ),
        bodies=(
            alive_body("body-a"),
            alive_body("body-b"),
            alive_body("body-r", location_id="loc-2"),
        ),
        weather=(make_weather(), make_weather("loc-2")),
        structures=(
            Structure(
                entity_id=structure_id,
                location_id=EntityId("loc-1"),
                kind=StructureKind.WELL,
                integrity=1.0,
                stored_quantity=0,
            ),
        ),
        collective_projects=(project,),
    )


def _event(details: object, *, event_id: str, sequence: int):
    actor_id = details.actor_id  # type: ignore[attr-defined]
    return make_physical_replayable_event(
        event_id=EventId(event_id),
        run_id="run-public-goods",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=sequence,
        cause=ActionCause(RequestId(f"request-{event_id}"), actor_id),
        resulting_revision=WorldRevision(1),
        details=details,  # type: ignore[arg-type]
        occurrence=OccurrenceContext(origin_location_id=EntityId("loc-1")),
        schema_version=EVENT_SCHEMA_REPLAY_V20,
    )


def _observe(*, public_goods_active: bool):
    project_id = EntityId("project-well")
    events = (
        _event(
            ProjectContributed(
                project_id=project_id,
                actor_id=EntityId("body-a"),
                accepted=True,
                labor_done=3,
                materials_done=2,
            ),
            event_id="event-contribute",
            sequence=0,
        ),
        _event(
            PublicGoodBenefit(
                project_id=project_id,
                actor_id=EntityId("body-b"),
                project_kind="well",
                benefit_code="draw",
                source="command",
                integrity_millis=1000,
                resulting_thirst=4.0,
            ),
            event_id="event-draw",
            sequence=1,
        ),
    )
    return project_observations(
        world_id=WorldId("world-1"),
        state=_state(),
        observer_ids=(EntityId("body-a"), EntityId("body-r")),
        context=ObservationContext(tick=3),
        prior_events=events,
        collective_projects_active=True,
        public_goods_active=public_goods_active,
    )


def test_colocated_observer_sees_non_contributor_draw_and_act_tail() -> None:
    local, remote = _observe(public_goods_active=True)
    assert local.collective_projects[0].linked_structure_id == EntityId(
        "structure-well"
    )
    assert local.collective_projects[0].public_acts[0].actor_id == EntityId("body-b")
    benefits = [row for row in local.occurrences if row.kind == "public_good_benefit"]
    assert benefits[0].public_facts == {
        "benefit_code": "draw",
        "kind": "well",
        "project_id": "project-well",
        "resulting_thirst": 4.0,
        "source": "command",
    }
    assert remote.collective_projects == ()
    assert remote.occurrences == ()
    restored = decode_domain(encode_domain(local))
    assert (
        restored.collective_projects[0].public_acts
        == local.collective_projects[0].public_acts
    )


def test_channel_off_omits_public_fields_and_occurrences() -> None:
    local, _remote = _observe(public_goods_active=False)
    encoded = json.loads(encode_domain(local))["data"]
    project = encoded["collective_projects"][0]
    assert "public_acts" not in project
    assert "linked_structure_id" not in project
    contribution = next(
        row for row in local.occurrences if row.kind == "project_contributed"
    )
    assert "public_good" not in contribution.public_facts
    assert "accepted" not in contribution.public_facts
    assert all(row.kind != "public_good_benefit" for row in local.occurrences)
