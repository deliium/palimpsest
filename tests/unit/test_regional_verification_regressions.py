"""Regressions for mixed-duration travel and route-base fatigue composition."""

from __future__ import annotations

from dataclasses import replace
from itertools import groupby

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    LifespanDistributionSpec,
    example_developmental_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body
from tests.unit.test_regional_travel_actions import _request, _spec, _world_state
from world._operations import prepare_action_batch
from world._replay import project_event_prefix
from world._rules import apply_operation
from world._skills import (
    ObjectiveSkillLedger,
    SkillDomain,
    SkillEfficiencyOverride,
    default_objective_skill_policy,
)
from world.actions import ActionRequest, Move, Transport
from world.dependency_care import DependencyCareRuleContext
from world.events import JourneyArrived, JourneyEnded, JourneyStarted
from world.identifiers import EntityId, ProposalId, RequestId, WorldId
from world.models import PhysicalRules, non_lethal_physical_rules
from world.regions import RouteSpec
from world.values import round_physical


def _engine(
    *,
    move_fatigue: float = 5,
    route_cost: float = 9,
    fatigue_factor: float | None = None,
    skilled: bool = False,
) -> WorldEngine:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, route_cost),))
    state = _world_state(spec=spec, bodies=(alive_body("body-1"), alive_body("body-2")))
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-routes"),
        revision=state.revision,
        locations=tuple(state.locations.values()),
        bodies=tuple(state.bodies.values()),
        weather=tuple(state.weather.values()),
        regions_migration=spec,
        registrations=tuple(
            AgentRegistration(AgentId(body_id.value), body_id)
            for body_id in state.bodies
        ),
    )
    lifecycle = None
    records = ()
    if fatigue_factor is not None:
        base = example_developmental_lifecycle_spec(
            lifespan_ticks=24,
            max_population=3,
            policy_id="disabled",
            intra_stage_interpolation=False,
            min_assigned_ticks=24,
        )
        lifecycle = replace(
            base,
            lifespan_distribution=LifespanDistributionSpec(
                distribution_id="fixed", params={}
            ),
            stage_capability_effects=tuple(
                replace(
                    effect,
                    fatigue_accrual_factor=fatigue_factor,
                    denied_command_kinds=(),
                )
                for effect in base.stage_capability_effects
            ),
        )
        records = seed_bootstrap_lifecycle_records(
            registrations=bootstrap.registrations, spec=lifecycle
        )
    policy = default_objective_skill_policy() if skilled else None
    ledger = (
        ObjectiveSkillLedger.bootstrap((EntityId("body-1"),)).apply_summed_deltas(
            {EntityId("body-1"): {SkillDomain.NAVIGATION: 1.0}}
        )
        if skilled
        else None
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=77,
            physical_rules=replace(
                non_lethal_physical_rules(), move_fatigue=move_fatigue
            ),
        ),
        bootstrap=bootstrap,
        population_lifecycle=lifecycle,
        lifecycle_records=records,
        skill_policy=policy,
        skill_ledger=ledger,
        skill_entity_ids=(EntityId("body-1"),) if skilled else None,
    )


@pytest.mark.parametrize("short_tick", (0, 1))
def test_short_move_preserves_another_journey_and_all_live_replay_prefixes(
    short_tick: int,
) -> None:
    engine = _engine()
    initial = engine._snapshot.world.state
    for tick in range(3):
        batch = engine.observe()
        submissions = []
        if tick == 0:
            submissions.append(
                ActionSubmission(
                    batch.token, AgentId("body-1"), Move(EntityId("loc-2"))
                )
            )
        if tick == short_tick:
            submissions.append(
                ActionSubmission(
                    batch.token, AgentId("body-2"), Move(EntityId("loc-3"))
                )
            )
        engine.resolve_tick(tuple(submissions))
        if tick == short_tick:
            pending = tuple(engine._snapshot.world.state.journeys.values())
            assert len(pending) == 1
            assert pending[0].participant_body_ids == (EntityId("body-1"),)
    state = engine._snapshot.world.state
    assert state.journeys == {}
    assert state.bodies[EntityId("body-1")].location_id == EntityId("loc-2")
    assert state.bodies[EntityId("body-2")].location_id == EntityId("loc-3")
    events = engine._snapshot.event_history
    assert sum(isinstance(event.details, JourneyStarted) for event in events) == 2
    assert sum(isinstance(event.details, JourneyArrived) for event in events) == 2
    assert not any(isinstance(event.details, JourneyEnded) for event in events)
    completed = initial
    for _, group in groupby(events, key=lambda event: event.tick):
        tick_events = tuple(group)
        for end in range(1, len(tick_events) + 1):
            projected = project_event_prefix(
                completed,
                tick_events[:end],
                expected_run_id=engine.run_id.value,
                expected_world_id=engine.world_id,
                includes_last_event=end == len(tick_events),
            )
        completed = projected
    assert completed.bodies == state.bodies
    assert completed.journeys == state.journeys
    assert completed.revision == state.revision


def test_short_grouped_transport_preserves_unrelated_journey() -> None:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, 9),))
    state = _world_state(
        spec=spec, bodies=tuple(alive_body(f"body-{i}") for i in (1, 2, 3))
    )
    care = DependencyCareRuleContext(
        dependent_body_ids=frozenset({EntityId("body-3")}),
        allow_feed=False,
        allow_transport=True,
    )
    requests = tuple(
        ActionRequest(
            request_id=RequestId(f"request-{index}"),
            proposal_id=ProposalId(f"proposal-{index}"),
            world_id=WorldId("world-routes"),
            revision=state.revision,
            actor_id=EntityId(actor),
            command=command,
        )
        for index, (actor, command) in enumerate(
            (
                ("body-1", Move(EntityId("loc-2"))),
                ("body-2", Transport(EntityId("body-3"), EntityId("loc-3"))),
            )
        )
    )
    result = prepare_action_batch(
        world_id=WorldId("world-routes"),
        starting_state=state,
        requests=requests,
        rules=PhysicalRules(),
        tick=0,
        dependency_care_context=care,
    )
    journeys = tuple(result.working_state.journeys.values())
    assert len(journeys) == 1
    assert journeys[0].participant_body_ids == (EntityId("body-1"),)
    assert all(
        result.working_state.bodies[EntityId(body)].location_id == EntityId("loc-3")
        for body in ("body-2", "body-3")
    )
    assert [event.details.kind for event in result.pending_events] == [
        "journey_started",
        "journey_started",
        "journey_arrived",
    ]


@pytest.mark.parametrize("transport", (False, True))
@pytest.mark.parametrize("factor", (0.5, 2.0))
def test_route_base_cost_receives_the_existing_movement_adjustment_once(
    transport: bool, factor: float
) -> None:
    spec = _spec((RouteSpec(EntityId("loc-1"), EntityId("loc-2"), 3, 9),))
    state = _world_state(spec=spec, bodies=(alive_body("body-1"), alive_body("body-2")))
    rules = PhysicalRules(move_fatigue=5, transport_fatigue=8)
    command = (
        Transport(EntityId("body-2"), EntityId("loc-2"))
        if transport
        else Move(EntityId("loc-2"))
    )
    care = DependencyCareRuleContext(
        dependent_body_ids=frozenset({EntityId("body-2")}),
        allow_feed=False,
        allow_transport=True,
    )
    result = apply_operation(
        state,
        _request(state, command),
        rules=rules,
        tick=0,
        dependency_care_context=care,
        skill_efficiency=SkillEfficiencyOverride(
            move_fatigue=rules.move_fatigue * factor,
            flee_fatigue=rules.flee_fatigue,
            help_health_gain=rules.help_health_gain,
        ),
    )
    base_cost = 8 + (9 - 5) if transport else 9
    assert isinstance(result.event_details, JourneyStarted)
    assert result.event_details.journey.charged_fatigue_cost == round_physical(
        base_cost * factor
    )
    assert result.next_state.bodies[EntityId("body-2")].fatigue.value == 0


@pytest.mark.parametrize("move_fatigue", (0, 5))
@pytest.mark.parametrize("route_cost", (0, 9))
@pytest.mark.parametrize("fatigue_factor", (None, 2.0))
@pytest.mark.parametrize("skilled", (False, True))
def test_engine_composes_route_base_with_skill_and_lifecycle_even_with_zero_baseline(
    move_fatigue: float,
    route_cost: float,
    fatigue_factor: float | None,
    skilled: bool,
) -> None:
    engine = _engine(
        move_fatigue=move_fatigue,
        route_cost=route_cost,
        fatigue_factor=fatigue_factor,
        skilled=skilled,
    )
    batch = engine.observe()
    result = engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("body-1"), Move(EntityId("loc-2"))),)
    )
    starts = [
        record.event.details
        for record in result.events
        if isinstance(record.event.details, JourneyStarted)
    ]
    assert len(starts) == 1
    divisor = 1 + default_objective_skill_policy().efficiency_gain if skilled else 1
    expected = round_physical(route_cost * (fatigue_factor or 1) / divisor)
    assert starts[0].journey.charged_fatigue_cost == expected
