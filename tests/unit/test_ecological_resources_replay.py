# mypy: ignore-errors

"""Ecological schema 25 / codec v23 selection, codecs, and fold."""

from __future__ import annotations

import pytest

from simulation.persistence import checkpoint_schema_for_production
from simulation.serialization import decode_domain, encode_domain
from simulation.versioning import (
    ECOLOGY_WRITE_PAIR_CODEC,
    ECOLOGY_WRITE_PAIR_EVENT,
    EPIDEMICS_WRITE_PAIR_CODEC,
    EPIDEMICS_WRITE_PAIR_EVENT,
)
from tests.simulation_helpers import make_location, make_resource, make_weather
from world._ecological_resources import bootstrap_ecological_rows
from world._replay import ProjectionError, project_events
from world._state import WorldState
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V24,
    EVENT_SCHEMA_REPLAY_V25,
    EcologicalResourceChanged,
    OccurrenceContext,
    ResourceRegenerated,
    WorldEvent,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit


def test_ecology_pair_selected_before_disease() -> None:
    schema, codec = checkpoint_schema_for_production(
        production_active=True,
        dynamics_active=True,
        ecological_feedback_active=True,
        disease_active=True,
        measurement_active=True,
        travel_network_active=True,
    )
    assert (schema, codec) == (ECOLOGY_WRITE_PAIR_EVENT, ECOLOGY_WRITE_PAIR_CODEC)
    schema, codec = checkpoint_schema_for_production(
        production_active=False,
        disease_active=True,
    )
    assert (schema, codec) == (
        EPIDEMICS_WRITE_PAIR_EVENT,
        EPIDEMICS_WRITE_PAIR_CODEC,
    )


_DEFAULT_RESOURCE = EntityId("res-food")
_DEFAULT_LOCATION = EntityId("loc-1")


def _ecology_event(
    *,
    before: int,
    after: int,
    schema: int = EVENT_SCHEMA_REPLAY_V25,
    resource_id: EntityId | None = None,
    location_id: EntityId | None = None,
) -> WorldEvent:
    if resource_id is None:
        resource_id = _DEFAULT_RESOURCE
    if location_id is None:
        location_id = _DEFAULT_LOCATION
    details = EcologicalResourceChanged(
        resource_id=resource_id,
        before_damage_tenths=before,
        after_damage_tenths=after,
    )
    return WorldEvent(
        event_id=EventId("evt-eco-1"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=0,
        request_id=RequestId("sys-eco-1"),
        resulting_revision=WorldRevision(1),
        schema_version=schema,
        details=details,
        actor_id=None,
        target_id=resource_id,
        cause=SystemCause(
            RequestId("sys-eco-1"),
            SystemEffectFamily.REGENERATION,
            resource_id,
            0,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=location_id,
            destination_location_id=None,
            affected_entity_ids=(resource_id,),
            private_recipient_ids=(),
        ),
    )


def test_encode_decode_ecological_resource_changed() -> None:
    event = _ecology_event(before=0, after=20)
    round_tripped = decode_domain(encode_domain(event))
    assert type(round_tripped) is WorldEvent
    assert type(round_tripped.details) is EcologicalResourceChanged
    assert round_tripped.details.before_damage_tenths == 0
    assert round_tripped.details.after_damage_tenths == 20
    assert round_tripped.schema_version == EVENT_SCHEMA_REPLAY_V25


def test_reject_ecology_event_on_legacy_schema() -> None:
    with pytest.raises(ValueError, match="invalid_event_schema_version"):
        _ecology_event(before=0, after=10, schema=EVENT_SCHEMA_REPLAY_V24)


def test_fold_ecology_and_regen_without_policy() -> None:
    food = make_resource(
        "res-food",
        quantity=2.0,
        maximum_quantity=4.0,
        regeneration_per_tick=1.0,
    )
    rows = bootstrap_ecological_rows(nodes=((food.entity_id, 10),))
    state = WorldState(
        WorldRevision(0),
        locations=(make_location("loc-1"),),
        resources=(food,),
        weather=(make_weather("loc-1"),),
        ecological_resources=rows,
        ecological_policy_digest="a" * 64,
    )
    eco = _ecology_event(before=0, after=20)
    projected = project_events(
        state,
        (eco,),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    assert projected.ecological_resources[food.entity_id].damage_tenths == 20
    assert projected.resources[food.entity_id].quantity == 2.0
    # Non-positive regen delta is rejected.
    bad_regen = WorldEvent(
        event_id=EventId("evt-regen-bad"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=1,
        sequence=1,
        request_id=RequestId("sys-regen-bad"),
        resulting_revision=WorldRevision(1),
        schema_version=EVENT_SCHEMA_REPLAY_V25,
        details=ResourceRegenerated(
            resource_id=food.entity_id,
            quantity_delta=0.0,
            resulting_quantity=2.0,
        ),
        actor_id=None,
        target_id=food.entity_id,
        cause=SystemCause(
            RequestId("sys-regen-bad"),
            SystemEffectFamily.REGENERATION,
            food.entity_id,
            1,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            destination_location_id=None,
            affected_entity_ids=(food.entity_id,),
            private_recipient_ids=(),
        ),
    )
    with pytest.raises(ProjectionError):
        project_events(
            projected,
            (bad_regen,),
            expected_run_id="run-1",
            expected_world_id=WorldId("world-1"),
        )
    recover = WorldEvent(
        event_id=EventId("evt-eco-2"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=0,
        request_id=RequestId("sys-eco-2"),
        resulting_revision=WorldRevision(2),
        schema_version=EVENT_SCHEMA_REPLAY_V25,
        details=EcologicalResourceChanged(
            resource_id=food.entity_id,
            before_damage_tenths=20,
            after_damage_tenths=15,
        ),
        actor_id=None,
        target_id=food.entity_id,
        cause=SystemCause(
            RequestId("sys-eco-2"),
            SystemEffectFamily.REGENERATION,
            food.entity_id,
            0,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            destination_location_id=None,
            affected_entity_ids=(food.entity_id,),
            private_recipient_ids=(),
        ),
    )
    regen_ok = WorldEvent(
        event_id=EventId("evt-regen-2"),
        run_id="run-1",
        world_id=WorldId("world-1"),
        tick=2,
        sequence=1,
        request_id=RequestId("sys-regen-2"),
        resulting_revision=WorldRevision(2),
        schema_version=EVENT_SCHEMA_REPLAY_V25,
        details=ResourceRegenerated(
            resource_id=food.entity_id,
            quantity_delta=0.5,
            resulting_quantity=2.5,
        ),
        actor_id=None,
        target_id=food.entity_id,
        cause=SystemCause(
            RequestId("sys-regen-2"),
            SystemEffectFamily.REGENERATION,
            food.entity_id,
            1,
        ),
        occurrence=OccurrenceContext(
            origin_location_id=EntityId("loc-1"),
            destination_location_id=None,
            affected_entity_ids=(food.entity_id,),
            private_recipient_ids=(),
        ),
    )
    folded = project_events(
        projected,
        (recover, regen_ok),
        expected_run_id="run-1",
        expected_world_id=WorldId("world-1"),
    )
    assert folded.ecological_resources[food.entity_id].damage_tenths == 15
    assert folded.resources[food.entity_id].quantity == 2.5
