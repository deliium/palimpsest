"""Neutral contact emission after a successful cross-region flee relocation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._operations import (
    OperationAccepted,
    ValidatedWorldOperation,
    prepare_action_batch,
    validate_action_request,
)
from world._rules import RuleDisposition, apply_operation
from world._state import WorldState
from world.actions import ActionRequest, Flee, require_agent_command
from world.effects import ResolvedActionEffects, ResolvedFleeEffect
from world.events import ContactRecorded, Fled
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, Location
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _spec(*, same_region: bool = False) -> RegionsMigrationSpec:
    east = "west" if same_region else "east"
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(
            LocationRegion(EntityId("loc-1"), "west"),
            LocationRegion(EntityId("loc-2"), east),
        ),
        routes=(RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 1, 1),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _state(
    *,
    spec: RegionsMigrationSpec,
    bodies: Sequence[AgentBody],
    locations: tuple[Location, ...] | None = None,
) -> WorldState:
    locations = locations or (
        make_location("loc-1", adjacent=("loc-2",), body_capacity=4),
        make_location("loc-2", adjacent=("loc-1",), body_capacity=4),
    )
    return WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=tuple(bodies),
        weather=tuple(make_weather(item.entity_id.value) for item in locations),
        regions_migration=spec,
    )


def _operation(state: WorldState) -> ValidatedWorldOperation:
    outcome = validate_action_request(
        world_id=WorldId("world-contact-flee"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("request-1"),
            proposal_id=ProposalId("proposal-1"),
            world_id=WorldId("world-contact-flee"),
            actor_id=EntityId("body-1"),
            revision=state.revision,
            command=require_agent_command(Flee()),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    return outcome.operation


def _effects(
    *, destination: str = "loc-2", success: bool = True
) -> ResolvedActionEffects:
    return ResolvedActionEffects(
        by_request={
            RequestId("request-1"): ResolvedFleeEffect(
                RequestId("request-1"),
                success=success,
                destination_index=0 if success else None,
                destination_id=EntityId(destination) if success else None,
            )
        }
    )


def test_cross_region_flee_emits_one_contact_after_relocation() -> None:
    state = _state(
        spec=_spec(),
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("local", location_id="loc-2"),
        ),
    )
    application = apply_operation(
        state, _operation(state), resolved=_effects(), contact_enabled=True
    )
    assert application.result.disposition is RuleDisposition.MUTATE
    assert isinstance(application.event_details, Fled)
    assert application.event_details.success is True
    assert len(application.extra_event_details) == 1
    contact = application.extra_event_details[0]
    assert isinstance(contact, ContactRecorded)
    assert contact.relocation_kind == "fled"
    assert contact.journey_id is None
    assert contact.location_id == EntityId("loc-2")
    assert contact.participant_ids == (EntityId("body-1"),)
    assert contact.present_ids == (EntityId("local"),)
    assert contact.origin_region_id == "west"
    assert contact.destination_region_id == "east"


def test_same_region_flee_emits_no_contact() -> None:
    state = _state(
        spec=_spec(same_region=True),
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("local", location_id="loc-2"),
        ),
    )
    application = apply_operation(
        state, _operation(state), resolved=_effects(), contact_enabled=True
    )
    assert application.extra_event_details == ()


def test_failed_flee_emits_no_contact() -> None:
    state = _state(
        spec=_spec(),
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("local", location_id="loc-2"),
        ),
    )
    application = apply_operation(
        state,
        _operation(state),
        resolved=_effects(success=False),
        contact_enabled=True,
    )
    assert application.result.disposition is RuleDisposition.EVENT_ONLY
    assert application.extra_event_details == ()


def test_empty_destination_emits_no_contact() -> None:
    state = _state(
        spec=_spec(),
        bodies=(alive_body("body-1", location_id="loc-1"),),
    )
    application = apply_operation(
        state, _operation(state), resolved=_effects(), contact_enabled=True
    )
    assert application.extra_event_details == ()


def test_contact_disabled_emits_no_contact() -> None:
    state = _state(
        spec=_spec(),
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("local", location_id="loc-2"),
        ),
    )
    application = apply_operation(
        state, _operation(state), resolved=_effects(), contact_enabled=False
    )
    assert application.extra_event_details == ()


def test_batch_preserves_action_cause_for_contact_event() -> None:
    state = _state(
        spec=_spec(),
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("local", location_id="loc-2"),
        ),
    )
    request = ActionRequest(
        request_id=RequestId("request-1"),
        proposal_id=ProposalId("proposal-1"),
        world_id=WorldId("world-contact-flee"),
        actor_id=EntityId("body-1"),
        revision=state.revision,
        command=require_agent_command(Flee()),
    )
    pending = prepare_action_batch(
        world_id=WorldId("world-contact-flee"),
        starting_state=state,
        requests=(request,),
        resolved_effects=_effects(),
        contact_enabled=True,
        deferred_regional_flee_effect=lambda _request, _working: cast(
            ResolvedFleeEffect, _effects().by_request[RequestId("request-1")]
        ),
    )
    contacts = [
        event
        for event in pending.pending_events
        if isinstance(event.details, ContactRecorded)
    ]
    assert len(contacts) == 1
    from world.effects import ActionCause

    assert isinstance(contacts[0].cause, ActionCause)
    assert contacts[0].cause.request_id == RequestId("request-1")
    assert contacts[0].cause.actor_id == EntityId("body-1")
