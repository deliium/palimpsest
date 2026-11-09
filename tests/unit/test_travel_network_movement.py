"""V4-17 movement admission and application use one route condition."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._operations import (
    OperationAccepted,
    ValidatedWorldOperation,
    prepare_action_batch,
    validate_action_request,
)
from world._rules import (
    RuleDisposition,
    RuleReason,
    apply_operation,
    find_eligible_flee_destinations,
)
from world._state import WorldState
from world.actions import ActionRequest, AgentCommand, Flee, Move, Transport
from world.dependency_care import DependencyCareRuleContext
from world.effects import ResolvedActionEffects, ResolvedFleeEffect
from world.environment import Season
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import AgentBody, PhysicalRules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.travel_network import (
    RouteBlockageCause,
    RouteCondition,
    RouteStatus,
    SeasonalAvailability,
)

pytestmark = pytest.mark.unit

A = EntityId("loc-a")
B = EntityId("loc-b")


def _spec() -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("west", "West"), RegionDefinition("east", "East")),
        location_regions=(LocationRegion(A, "west"), LocationRegion(B, "east")),
        routes=(RouteSpec(A, B, 2, 3.0),),
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _condition(
    *,
    status: RouteStatus = RouteStatus.OPEN,
    duration: int = 1,
    fatigue: float = 1.5,
    capacity: int = 8,
) -> RouteCondition:
    return RouteCondition(
        origin_id=A,
        destination_id=B,
        status=status,
        seasonal_availability=SeasonalAvailability.OPEN,
        blockage_cause=(
            RouteBlockageCause.SEASONAL
            if status is RouteStatus.CLOSED
            else RouteBlockageCause.NONE
        ),
        duration_ticks=duration,
        fatigue_cost=fatigue,
        capacity=capacity,
        risk=0.0,
        infrastructure_quality=0.0,
        reason_codes=(),
        as_of_tick=0,
    )


def _state(
    *,
    condition: RouteCondition,
    bodies: Sequence[AgentBody],
) -> WorldState:
    return WorldState(
        WorldRevision(0),
        locations=(
            make_location("loc-a", adjacent=("loc-b",)),
            make_location("loc-b", adjacent=("loc-a",), body_capacity=4),
        ),
        bodies=tuple(bodies),
        weather=(make_weather("loc-a"), make_weather("loc-b")),
        regions_migration=_spec(),
        travel_network=(condition,),
    )


def _request(
    state: WorldState, command: AgentCommand, *, actor: str = "body-1"
) -> ValidatedWorldOperation:
    outcome = validate_action_request(
        world_id=WorldId("world-travel"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("request-1"),
            proposal_id=ProposalId("proposal-1"),
            world_id=WorldId("world-travel"),
            actor_id=EntityId(actor),
            revision=state.revision,
            command=command,
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    return outcome.operation


def test_open_move_uses_condition_duration_and_fatigue() -> None:
    state = _state(
        condition=_condition(), bodies=(alive_body("body-1", location_id="loc-a"),)
    )
    application = apply_operation(
        state,
        _request(state, Move(B)),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        season=Season.SPRING,
        travel_network_active=True,
    )
    assert application.result.disposition is RuleDisposition.MUTATE
    assert application.next_state.bodies[EntityId("body-1")].location_id == B
    assert application.next_state.bodies[
        EntityId("body-1")
    ].fatigue.value == pytest.approx(1.5)


def test_closed_move_is_rejected() -> None:
    state = _state(
        condition=_condition(status=RouteStatus.CLOSED),
        bodies=(alive_body("body-1", location_id="loc-a"),),
    )
    application = apply_operation(
        state,
        _request(state, Move(B)),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        season=Season.WINTER,
        travel_network_active=True,
    )
    assert application.result.disposition is RuleDisposition.REJECT
    assert application.result.reason is RuleReason.ROUTE_BLOCKED


def test_flee_on_closed_route_uses_route_reason() -> None:
    state = _state(
        condition=_condition(status=RouteStatus.CLOSED),
        bodies=(alive_body("body-1", location_id="loc-a"),),
    )
    assert (
        find_eligible_flee_destinations(
            state,
            EntityId("body-1"),
            season=Season.WINTER,
            travel_network_active=True,
        )
        == ()
    )
    effect = ResolvedActionEffects(
        by_request={
            RequestId("request-1"): ResolvedFleeEffect(
                RequestId("request-1"),
                success=True,
                destination_index=0,
                destination_id=B,
            )
        }
    )
    application = apply_operation(
        state,
        _request(state, Flee()),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        season=Season.WINTER,
        resolved=effect,
        travel_network_active=True,
    )
    assert application.result.disposition is RuleDisposition.REJECT
    assert application.result.reason is RuleReason.ROUTE_BLOCKED


def test_transport_capacity_overflow_is_rejected() -> None:
    state = _state(
        condition=_condition(capacity=1),
        bodies=(
            alive_body("body-1", location_id="loc-a"),
            alive_body("body-2", location_id="loc-a"),
        ),
    )
    context = DependencyCareRuleContext(
        dependent_body_ids=frozenset({EntityId("body-2")}),
        allow_feed=True,
        allow_transport=True,
    )
    application = apply_operation(
        state,
        _request(state, Transport(EntityId("body-2"), B)),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        dependency_care_context=context,
        season=Season.SPRING,
        travel_network_active=True,
    )
    assert application.result.disposition is RuleDisposition.REJECT
    assert application.result.reason is RuleReason.ROUTE_CAPACITY_EXCEEDED


def test_transport_at_capacity_two_succeeds() -> None:
    state = _state(
        condition=_condition(capacity=2),
        bodies=(
            alive_body("body-1", location_id="loc-a"),
            alive_body("body-2", location_id="loc-a"),
        ),
    )
    context = DependencyCareRuleContext(
        dependent_body_ids=frozenset({EntityId("body-2")}),
        allow_feed=True,
        allow_transport=True,
    )
    application = apply_operation(
        state,
        _request(state, Transport(EntityId("body-2"), B)),
        rules=PhysicalRules(move_fatigue=5, transport_fatigue=2),
        tick=0,
        dependency_care_context=context,
        season=Season.SPRING,
        travel_network_active=True,
    )
    assert application.result.disposition is RuleDisposition.MUTATE
    assert application.next_state.bodies[EntityId("body-2")].location_id == B


def test_inactive_channel_keeps_legacy_behavior() -> None:
    state = _state(
        condition=_condition(status=RouteStatus.CLOSED),
        bodies=(alive_body("body-1", location_id="loc-a"),),
    )
    application = apply_operation(
        state,
        _request(state, Move(B)),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        season=Season.WINTER,
        travel_network_active=False,
    )
    assert application.result.disposition is RuleDisposition.MUTATE


def test_prepare_action_batch_threads_condition() -> None:
    state = _state(
        condition=_condition(status=RouteStatus.CLOSED),
        bodies=(alive_body("body-1", location_id="loc-a"),),
    )
    request = _request(state, Move(B))
    # Rebuild a raw ActionRequest for the batch API.
    raw = ActionRequest(
        request_id=request.request_id,
        proposal_id=ProposalId("proposal-1"),
        world_id=WorldId("world-travel"),
        actor_id=request.actor_id,
        revision=state.revision,
        command=Move(B),
    )
    pending = prepare_action_batch(
        world_id=WorldId("world-travel"),
        starting_state=state,
        requests=(raw,),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
        season=Season.WINTER,
        travel_network_active=True,
    )
    assert pending.outcomes[0].status.value == "rejected"
    assert pending.outcomes[0].reason == RuleReason.ROUTE_BLOCKED.value
