"""V4-17 route-condition event contract, replay schemas, and observer alias."""

from __future__ import annotations

import pytest

import observer
from observer.version import SEMANTIC_EVENT_TYPES, SEMANTIC_TYPE_BY_KIND
from simulation.serialization import decode_domain, encode_domain
from world.effects import SystemCause, SystemEffectFamily
from world.events import (
    EVENT_SCHEMA_REPLAY_V23,
    EVENT_SCHEMA_REPLAY_V27,
    ContactRecorded,
    EventValidationCode,
    InfrastructureConstructed,
    JourneyArrived,
    OccurrenceContext,
    RouteConditionChanged,
    WorldEvent,
    build_occurrence_context,
    make_physical_replayable_event,
)
from world.identifiers import EntityId, EventId, RequestId, WorldId, WorldRevision

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _detail(**changes: object) -> RouteConditionChanged:
    values: dict[str, object] = {
        "origin_location_id": B,
        "destination_location_id": A,
        "previous_status": "open",
        "current_status": "restricted",
        "previous_seasonal_availability": "open",
        "current_seasonal_availability": "restricted",
        "duration_ticks": 2,
        "fatigue_cost": 1.5,
        "capacity": 6,
        "risk": 0.3,
        "infrastructure_quality": 0.4,
        "blockage_cause": "seasonal",
        "reason_codes": ("season_autumn", "route_restricted"),
        "season": "autumn",
        "as_of_tick": 4,
    }
    values.update(changes)
    return RouteConditionChanged(**values)  # type: ignore[arg-type]


def _event(detail: RouteConditionChanged, schema_version: int) -> WorldEvent:
    return make_physical_replayable_event(
        event_id=EventId("event-route-1"),
        run_id="run-route",
        world_id=WorldId("world-route"),
        tick=4,
        sequence=1,
        resulting_revision=WorldRevision(1),
        details=detail,
        cause=SystemCause(
            cause_id=RequestId("cause-route-1"),
            effect_family=SystemEffectFamily.TRAVEL,
            entity_id=A,
            family_ordinal=1,
        ),
        occurrence=build_occurrence_context(detail, origin_location_id=None),
        schema_version=schema_version,
    )


def test_detail_orders_endpoints_and_validates() -> None:
    detail = _detail()
    assert detail.origin_location_id == A
    assert detail.destination_location_id == B
    assert detail.kind == "route_condition_changed"


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"current_status": "unknown"}, "route_condition_changed_current_status"),
        (
            {"current_seasonal_availability": "bad"},
            "route_condition_changed_current_seasonal_availability",
        ),
        ({"blockage_cause": "bad"}, "route_condition_changed_blockage_cause"),
        ({"season": "monsoon"}, "route_condition_changed_season"),
        ({"duration_ticks": 0}, "route_condition_changed_duration"),
        ({"fatigue_cost": -1.0}, "route_condition_changed_fatigue"),
        ({"capacity": 0}, "route_condition_changed_capacity"),
        ({"capacity": 25}, "route_condition_changed_capacity"),
        ({"risk": 1.1}, "route_condition_changed_risk"),
        (
            {"infrastructure_quality": -0.1},
            "route_condition_changed_infrastructure_quality",
        ),
        (
            {"reason_codes": tuple(f"r{index}" for index in range(9))},
            "route_condition_changed_reason_codes",
        ),
        ({"as_of_tick": -1}, "route_condition_changed_tick"),
    ],
)
def test_detail_rejects_invalid_values(changes: dict[str, object], code: str) -> None:
    with pytest.raises(ValueError, match=code):
        _detail(**changes)


def test_no_op_route_transition_without_previous_values_is_rejected() -> None:
    with pytest.raises(ValueError, match="route_condition_changed_no_change"):
        _detail(
            previous_status="open",
            current_status="open",
            previous_seasonal_availability="open",
            current_seasonal_availability="open",
        )


def test_no_op_route_transition_is_rejected() -> None:
    with pytest.raises(ValueError, match="route_condition_changed_no_change"):
        _detail(
            previous_status="restricted",
            current_status="restricted",
            previous_seasonal_availability="restricted",
            current_seasonal_availability="restricted",
            previous_duration_ticks=2,
            previous_fatigue_cost=1.5,
            previous_capacity=6,
            previous_risk=0.3,
            previous_infrastructure_quality=0.4,
            previous_blockage_cause="seasonal",
            previous_reason_codes=("season_autumn", "route_restricted"),
        )


def test_route_event_requires_v27() -> None:
    event = _event(_detail(), EVENT_SCHEMA_REPLAY_V27)
    assert event.schema_version == 27
    assert event.target_id is None
    assert event.occurrence is not None
    assert event.occurrence.affected_entity_ids == (A, B)
    for version in (EVENT_SCHEMA_REPLAY_V23, 26):
        with pytest.raises(
            ValueError, match=EventValidationCode.INVALID_SCHEMA_VERSION.value
        ):
            _event(_detail(), version)


def test_legacy_infrastructure_event_is_valid_under_v27() -> None:
    detail = InfrastructureConstructed(
        asset_id=EntityId("infra-road"),
        asset_kind="road",
        topology="edge",
        status="operational",
        integrity=0.8,
        location_id=A,
        endpoint_location_id=B,
        linked_structure_id=None,
        linked_project_id=EntityId("proj-1"),
        tick=1,
    )
    event = make_physical_replayable_event(
        event_id=EventId("event-infra-1"),
        run_id="run-route",
        world_id=WorldId("world-route"),
        tick=1,
        sequence=2,
        resulting_revision=WorldRevision(2),
        details=detail,
        cause=SystemCause(
            cause_id=RequestId("cause-infra-1"),
            effect_family=SystemEffectFamily.PRODUCTION,
            entity_id=A,
            family_ordinal=1,
        ),
        occurrence=build_occurrence_context(detail, origin_location_id=None),
        schema_version=EVENT_SCHEMA_REPLAY_V27,
    )
    assert event.details.kind == "infrastructure_constructed"


def test_round_trip_and_schema_rejection() -> None:
    event = _event(_detail(), EVENT_SCHEMA_REPLAY_V27)
    decoded = decode_domain(encode_domain(event))
    assert decoded == event
    with pytest.raises(Exception, match="invalid_event_schema_version"):
        decode_domain(
            encode_domain(_event(_detail(), EVENT_SCHEMA_REPLAY_V27)).replace(
                b'"schema_version":27', b'"schema_version":23'
            )
        )


def test_contact_and_journey_events_are_valid_under_v27() -> None:
    contact = ContactRecorded(
        relocation_kind="move",
        location_id=A,
        participant_ids=(EntityId("body-1"),),
        present_ids=(EntityId("body-2"),),
        origin_region_id="west",
        destination_region_id="east",
    )
    contact_event = make_physical_replayable_event(
        event_id=EventId("event-contact-1"),
        run_id="run-route",
        world_id=WorldId("world-route"),
        tick=4,
        sequence=1,
        resulting_revision=WorldRevision(4),
        details=contact,
        cause=SystemCause(
            cause_id=RequestId("cause-contact-1"),
            effect_family=SystemEffectFamily.TRAVEL,
            entity_id=EntityId("body-1"),
            family_ordinal=0,
        ),
        occurrence=OccurrenceContext(
            destination_location_id=A,
            affected_entity_ids=(EntityId("body-1"),),
        ),
        schema_version=EVENT_SCHEMA_REPLAY_V27,
    )
    assert decode_domain(encode_domain(contact_event)) == contact_event

    journey = JourneyArrived(
        journey_id="journey-1",
        participant_body_ids=(EntityId("body-1"),),
        origin_location_id=A,
        destination_location_id=B,
    )
    journey_event = make_physical_replayable_event(
        event_id=EventId("event-journey-1"),
        run_id="run-route",
        world_id=WorldId("world-route"),
        tick=4,
        sequence=2,
        resulting_revision=WorldRevision(4),
        details=journey,
        cause=SystemCause(
            cause_id=RequestId("cause-journey-1"),
            effect_family=SystemEffectFamily.TRAVEL,
            entity_id=EntityId("body-1"),
            family_ordinal=1,
        ),
        occurrence=build_occurrence_context(journey, origin_location_id=A),
        schema_version=EVENT_SCHEMA_REPLAY_V27,
    )
    assert decode_domain(encode_domain(journey_event)) == journey_event


def test_observer_alias_and_semantic_count() -> None:
    assert SEMANTIC_TYPE_BY_KIND["route_condition_changed"] == "WEATHER_CHANGED"
    assert "WEATHER_CHANGED" in SEMANTIC_EVENT_TYPES
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert observer.SEMANTIC_EVENT_TYPES is SEMANTIC_EVENT_TYPES
