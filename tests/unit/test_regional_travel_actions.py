"""Route-aware movement starts journeys through existing Move/Transport actions."""

from __future__ import annotations

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._operations import (
    OperationAccepted,
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
from world.actions import ActionRequest, Flee, Move, Transport, Wait
from world.dependency_care import DependencyCareRuleContext
from world.effects import ResolvedActionEffects, ResolvedFleeEffect
from world.identifiers import EntityId, ProposalId, RequestId, WorldId, WorldRevision
from world.models import PhysicalRules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)


def _spec(routes: tuple[RouteSpec, ...]) -> RegionsMigrationSpec:
    return RegionsMigrationSpec(
        regions=(RegionDefinition("region", "Region"),),
        location_regions=tuple(
            LocationRegion(EntityId(location_id), "region")
            for location_id in ("loc-1", "loc-2", "loc-3")
        ),
        routes=routes,
        max_arrival_wait_ticks=2,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )


def _request(state: WorldState, command, *, actor: str = "body-1"):
    from world.actions import require_agent_command

    outcome = validate_action_request(
        world_id=WorldId("world-routes"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("request-1"),
            proposal_id=ProposalId("proposal-1"),
            world_id=WorldId("world-routes"),
            actor_id=EntityId(actor),
            revision=state.revision,
            command=require_agent_command(command),
        ),
    )
    assert isinstance(outcome, OperationAccepted)
    return outcome.operation


def _world_state(*, spec: RegionsMigrationSpec, bodies):
    locations = (
        make_location("loc-1", adjacent=("loc-2", "loc-3"), body_capacity=4),
        make_location("loc-2", adjacent=("loc-1",), body_capacity=1),
        make_location("loc-3", adjacent=("loc-1",), body_capacity=4),
    )
    return WorldState(
        WorldRevision(0),
        locations=locations,
        bodies=tuple(bodies),
        weather=tuple(make_weather(location.entity_id.value) for location in locations),
        regions_migration=spec,
    )


def test_long_move_starts_at_origin_without_reserving_full_destination() -> None:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, 7),))
    state = _world_state(
        spec=spec,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("blocker", location_id="loc-2"),
        ),
    )
    application = apply_operation(
        state,
        _request(state, Move(EntityId("loc-2"))),
        rules=PhysicalRules(move_fatigue=5),
        tick=10,
    )
    assert application.result.disposition is RuleDisposition.MUTATE
    assert len(application.all_event_details()) == 1
    assert application.event_details is not None
    assert application.event_details.kind == "journey_started"
    assert application.next_state.bodies[EntityId("body-1")].location_id == EntityId(
        "loc-1"
    )
    assert application.next_state.bodies[EntityId("body-1")].fatigue.value == 7
    journey = application.event_details.journey  # type: ignore[union-attr]
    assert journey.due_tick == 12
    assert journey.charged_fatigue_cost == 7


def test_duration_one_move_emits_start_then_arrival_and_keeps_baseline_cost() -> None:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 1, 2),))
    state = _world_state(spec=spec, bodies=(alive_body("body-1"),))
    application = apply_operation(
        state,
        _request(state, Move(EntityId("loc-2"))),
        rules=PhysicalRules(move_fatigue=5),
        tick=0,
    )
    assert [item.kind for item in application.all_event_details()] == [
        "journey_started",
        "journey_arrived",
    ]
    assert application.next_state.bodies[EntityId("body-1")].location_id == EntityId(
        "loc-2"
    )
    assert application.next_state.bodies[EntityId("body-1")].fatigue.value == 2
    assert application.next_state.journeys == {}


def test_grouped_transport_starts_one_journey_and_charges_only_caregiver() -> None:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 9),))
    state = _world_state(
        spec=spec,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
            alive_body("blocker", location_id="loc-2"),
        ),
    )
    care = DependencyCareRuleContext(
        dependent_body_ids=frozenset({EntityId("body-2")}),
        allow_feed=False,
        allow_transport=True,
    )
    application = apply_operation(
        state,
        _request(state, Transport(EntityId("body-2"), EntityId("loc-2"))),
        rules=PhysicalRules(move_fatigue=5, transport_fatigue=8),
        tick=1,
        dependency_care_context=care,
    )
    assert application.event_details is not None
    assert application.event_details.kind == "journey_started"
    journey = application.event_details.journey
    assert journey.participant_body_ids == (EntityId("body-1"), EntityId("body-2"))
    assert journey.charged_fatigue_cost == 12
    assert application.next_state.bodies[EntityId("body-1")].fatigue.value == 12
    assert application.next_state.bodies[EntityId("body-2")].fatigue.value == 0
    assert application.next_state.bodies[EntityId("body-2")].location_id == EntityId(
        "loc-1"
    )


def test_flee_uses_only_short_routes_and_never_redirects_bound_destination() -> None:
    spec = _spec(
        (
            RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 1, 1),
            RouteSpec(EntityId("loc-1"), EntityId("loc-3"), 2, 1),
        )
    )
    origin = _world_state(spec=spec, bodies=(alive_body("body-1"),))
    assert find_eligible_flee_destinations(origin, EntityId("body-1")) == (
        EntityId("loc-2"),
    )
    redirect_spec = _spec(
        (
            RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 1, 1),
            RouteSpec(EntityId("loc-1"), EntityId("loc-3"), 1, 1),
        )
    )
    crowded = _world_state(
        spec=redirect_spec,
        bodies=(
            alive_body("body-1"),
            alive_body("blocker", location_id="loc-2"),
        ),
    )
    operation = _request(crowded, Flee())
    effect = ResolvedActionEffects(
        by_request={
            RequestId("request-1"): ResolvedFleeEffect(
                RequestId("request-1"),
                success=True,
                destination_index=0,
                destination_id=EntityId("loc-2"),
            )
        }
    )
    application = apply_operation(crowded, operation, resolved=effect)
    assert application.result.disposition is RuleDisposition.REJECT
    assert application.result.reason is RuleReason.FLEE_DESTINATION_UNAVAILABLE


def test_deferred_flee_resolution_sees_prior_working_state_change() -> None:
    from world.actions import require_agent_command

    spec = _spec(
        (
            RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 1, 1),
            RouteSpec(EntityId("loc-1"), EntityId("loc-3"), 1, 1),
        )
    )
    state = _world_state(
        spec=spec,
        bodies=(
            alive_body("body-1", location_id="loc-1"),
            alive_body("body-2", location_id="loc-1"),
        ),
    )
    world_id = WorldId("world-routes")
    requests = (
        ActionRequest(
            RequestId("request-move"),
            ProposalId("proposal-move"),
            world_id,
            EntityId("body-2"),
            state.revision,
            require_agent_command(Move(EntityId("loc-2"))),
        ),
        ActionRequest(
            RequestId("request-flee"),
            ProposalId("proposal-flee"),
            world_id,
            EntityId("body-1"),
            state.revision,
            require_agent_command(Flee()),
        ),
    )
    seen: list[tuple[EntityId, ...]] = []

    def resolve_flee(request: ActionRequest, working: WorldState):
        destinations = find_eligible_flee_destinations(working, request.actor_id)
        seen.append(destinations)
        assert EntityId("loc-2") not in destinations
        assert EntityId("loc-3") in destinations
        return ResolvedFleeEffect(
            request.request_id,
            success=True,
            destination_index=0,
            destination_id=destinations[0],
        )

    pending = prepare_action_batch(
        world_id=world_id,
        starting_state=state,
        requests=requests,
        rules=PhysicalRules(),
        tick=0,
        deferred_regional_flee_effect=resolve_flee,
    )
    assert len(seen) == 1
    assert pending.working_state.bodies[EntityId("body-1")].location_id == EntityId(
        "loc-3"
    )


def test_long_only_flee_routes_skip_deferred_random_resolution() -> None:
    from world.actions import require_agent_command

    spec = _spec(
        (
            RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 1),
            RouteSpec(EntityId("loc-1"), EntityId("loc-3"), 3, 1),
        )
    )
    state = _world_state(spec=spec, bodies=(alive_body("body-1"),))
    request = ActionRequest(
        RequestId("request-flee"),
        ProposalId("proposal-flee"),
        WorldId("world-routes"),
        EntityId("body-1"),
        state.revision,
        require_agent_command(Flee()),
    )
    calls = 0

    def resolve_flee(_request: ActionRequest, _working: WorldState):
        nonlocal calls
        calls += 1
        return None

    pending = prepare_action_batch(
        world_id=WorldId("world-routes"),
        starting_state=state,
        requests=(request,),
        rules=PhysicalRules(),
        tick=0,
        deferred_regional_flee_effect=resolve_flee,
    )
    assert calls == 0
    assert pending.outcomes[0].status.value == "rejected"


def test_transport_conflicts_second_caregiver_but_allows_wait() -> None:
    from world.actions import require_agent_command

    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 3),))
    state = _world_state(
        spec=spec,
        bodies=(
            alive_body("caregiver-1", location_id="loc-1"),
            alive_body("caregiver-2", location_id="loc-1"),
            alive_body("dependent", location_id="loc-1"),
        ),
    )
    world_id = WorldId("world-routes")

    def request(request_id: str, actor_id: str, command):
        return ActionRequest(
            RequestId(request_id),
            ProposalId(f"proposal-{request_id}"),
            world_id,
            EntityId(actor_id),
            state.revision,
            require_agent_command(command),
        )

    flee_calls = 0

    def resolve_flee(request_value: ActionRequest, working: WorldState):
        nonlocal flee_calls
        flee_calls += 1
        destinations = find_eligible_flee_destinations(working, request_value.actor_id)
        return ResolvedFleeEffect(
            request_value.request_id,
            success=True,
            destination_index=0,
            destination_id=destinations[0],
        )

    pending = prepare_action_batch(
        world_id=world_id,
        starting_state=state,
        requests=(
            request(
                "care-1",
                "caregiver-1",
                Transport(EntityId("dependent"), EntityId("loc-2")),
            ),
            request(
                "care-2",
                "caregiver-2",
                Transport(EntityId("dependent"), EntityId("loc-2")),
            ),
            request("dependent-wait", "dependent", Wait()),
            request("dependent-move", "dependent", Move(EntityId("loc-3"))),
            request("dependent-flee", "dependent", Flee()),
        ),
        rules=PhysicalRules(),
        tick=0,
        dependency_care_context=DependencyCareRuleContext(
            dependent_body_ids=frozenset({EntityId("dependent")}),
            allow_feed=False,
            allow_transport=True,
        ),
        deferred_regional_flee_effect=resolve_flee,
    )
    assert [outcome.status.value for outcome in pending.outcomes] == [
        "applied",
        "conflicted",
        "applied",
        "conflicted",
        "conflicted",
    ]
    assert flee_calls == 0
    assert pending.working_state.journeys is not None
    assert len(pending.working_state.journeys) == 1
    assert pending.working_state.bodies[EntityId("dependent")].location_id == EntityId(
        "loc-1"
    )


def test_world_engine_resolve_tick_gates_caregivers_and_traveller_commands() -> None:
    from dataclasses import replace

    from agents.models import AgentId
    from simulation.bootstrap import AgentRegistration, WorldBootstrap
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from simulation.models import SimulationRunConfig
    from simulation.runner_models import (
        example_dependency_care_spec,
        example_population_lifecycle_spec,
        seed_bootstrap_lifecycle_records,
    )
    from tests.simulation_helpers import connected_locations, weather_for_locations
    from world.identifiers import WorldRevision
    from world.lifecycle import DependencyStatus, LifecycleStageId
    from world.models import non_lethal_physical_rules

    bodies = (
        alive_body("caregiver-1", location_id="loc-1"),
        alive_body("caregiver-2", location_id="loc-1"),
        alive_body("dependent", location_id="loc-1"),
    )
    registrations = (
        AgentRegistration(AgentId("agent-care-1"), bodies[0].entity_id),
        AgentRegistration(AgentId("agent-care-2"), bodies[1].entity_id),
        AgentRegistration(AgentId("agent-dependent"), bodies[2].entity_id),
    )
    locations = connected_locations(
        ("loc-1", "One"), ("loc-2", "Two"), ("loc-3", "Three")
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-engine-routes"),
        revision=WorldRevision(0),
        locations=locations,
        bodies=bodies,
        weather=weather_for_locations(locations),
        registrations=registrations,
        regions_migration=_spec(
            (RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 2, 3),)
        ),
    )
    lifecycle = example_population_lifecycle_spec(lifespan_ticks=40, max_population=5)
    records = seed_bootstrap_lifecycle_records(
        registrations=registrations, spec=lifecycle
    )
    lifecycle_records = (
        replace(
            records[0],
            stage=LifecycleStageId("adult"),
            dependency_status=DependencyStatus.INDEPENDENT,
        ),
        replace(
            records[1],
            stage=LifecycleStageId("adult"),
            dependency_status=DependencyStatus.INDEPENDENT,
        ),
        replace(
            records[2],
            stage=LifecycleStageId("infant"),
            dependency_status=DependencyStatus.DEPENDENT,
        ),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=9, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        population_lifecycle=lifecycle,
        lifecycle_records=lifecycle_records,
        dependency_care_spec=example_dependency_care_spec(),
    )
    observation = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                observation.token,
                AgentId("agent-care-1"),
                Transport(EntityId("dependent"), EntityId("loc-2")),
            ),
            ActionSubmission(
                observation.token,
                AgentId("agent-care-2"),
                Transport(EntityId("dependent"), EntityId("loc-2")),
            ),
            ActionSubmission(observation.token, AgentId("agent-dependent"), Wait()),
        )
    )
    assert result is not None
    assert [resolution.status.value for resolution in result.resolutions] == [
        "applied",
        "conflicted",
        "applied",
    ]
    assert any(
        record.event.details.kind == "journey_started" for record in result.events
    )
    assert all(record.event.schema_version == 21 for record in result.events)
    assert engine._snapshot.world.state.bodies[
        EntityId("dependent")
    ].location_id == EntityId("loc-1")
    assert len(engine._snapshot.world.state.journeys or {}) == 1
