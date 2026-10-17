"""Cross-channel travel, effort, benefit, and event-prefix regression gates."""

from __future__ import annotations

import logging
from dataclasses import replace
from itertools import groupby

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agents.models import AgentId
from experiments.persistence import regional_context_from_snapshot
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from tests.unit.test_experiment_ax import _skilled
from tests.unit.test_regional_demographics import _inputs, _move
from tests.unit.test_regional_travel_checkpoint import _snapshot
from world._replay import project_event_prefix
from world.actions import (
    AgentCommand,
    ContributeCollectiveProject,
    Move,
    StartCollectiveProject,
    Wait,
)
from world.events import JourneyArrived, JourneyStarted, PublicGoodBenefit
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import non_lethal_physical_rules
from world.regions import (
    CognitionMode,
    LocationRegion,
    RegionDefinition,
    RegionsMigrationSpec,
    RouteSpec,
)
from world.values import ItemKind


@pytest.mark.parametrize("duration", (1, 3))
def test_arrival_gets_local_public_benefit_and_every_prefix_replays(
    duration: int, caplog: pytest.LogCaptureFixture
) -> None:
    """Travel and autonomous benefits compose without duplicate placement/effort."""
    origin, destination = EntityId("origin"), EntityId("destination")
    traveler, builder = EntityId("traveler"), EntityId("builder")
    wood = tuple(
        make_item(
            f"wood-{index}",
            name="wood",
            location_id=None,
            holder_id=builder.value,
        )
        for index in range(2)
    )
    wood = tuple(replace(item, kind=ItemKind.MATERIAL) for item in wood)
    locations = (
        make_location(origin.value, adjacent=(destination.value,)),
        make_location(destination.value, adjacent=(origin.value,)),
    )
    regions = RegionsMigrationSpec(
        regions=(
            RegionDefinition("west", "Private-free west"),
            RegionDefinition("east", "Private-free east"),
        ),
        location_regions=(
            LocationRegion(origin, "west"),
            LocationRegion(destination, "east"),
        ),
        routes=(RouteSpec(origin, destination, duration, 6.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=2,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    policy, ledger = _skilled((traveler, builder))
    engine = WorldEngine(
        config=SimulationRunConfig(seed=21, physical_rules=non_lethal_physical_rules()),
        bootstrap=WorldBootstrap(
            world_id=WorldId("regional-public-benefits"),
            revision=WorldRevision(0),
            locations=locations,
            bodies=(
                alive_body(traveler.value, location_id=origin.value),
                alive_body(
                    builder.value,
                    location_id=destination.value,
                    inventory=tuple(item.entity_id for item in wood),
                ),
            ),
            items=wood,
            weather=tuple(
                make_weather(location.entity_id.value) for location in locations
            ),
            registrations=(
                AgentRegistration(AgentId("traveler"), traveler),
                AgentRegistration(AgentId("builder"), builder),
            ),
            regions_migration=regions,
        ),
        collective_projects_active=True,
        public_goods_active=True,
        skill_policy=policy,
        skill_entity_ids=(traveler, builder),
        skill_ledger=ledger,
    )
    initial = engine._snapshot.world.state

    def step(*, travel: AgentCommand | None = None, build: AgentCommand | None = None):
        batch = engine.observe()
        return engine.resolve_tick(
            (
                ActionSubmission(batch.token, AgentId("traveler"), travel or Wait()),
                ActionSubmission(batch.token, AgentId("builder"), build or Wait()),
            )
        )

    step(build=StartCollectiveProject("shared_shelter"))
    project_id = next(iter(engine._snapshot.world.state.collective_projects))
    for item in wood:
        step(build=ContributeCollectiveProject(project_id, item.entity_id))
    step(build=ContributeCollectiveProject(project_id))
    with caplog.at_level(logging.INFO, logger="simulation.engine"):
        departure = step(travel=Move(destination))
        for _ in range(duration - 1):
            step()
    assert departure is not None
    events = engine._snapshot.event_history
    starts = [event for event in events if type(event.details) is JourneyStarted]
    arrivals = [event for event in events if type(event.details) is JourneyArrived]
    assert len(starts) == len(arrivals) == 1
    assert starts[0].tick + duration - 1 == arrivals[0].tick
    benefits = [
        event
        for event in events
        if type(event.details) is PublicGoodBenefit
        and event.details.actor_id == traveler
    ]
    assert benefits and all(event.tick >= arrivals[0].tick for event in benefits)
    assert not any(event.details.kind == "move" for event in events)
    completed = initial
    for _, tick_events in groupby(events, key=lambda event: event.tick):
        tick_events = tuple(tick_events)
        for end in range(1, len(tick_events) + 1):
            projected = project_event_prefix(
                completed,
                tick_events[:end],
                expected_run_id=engine.run_id.value,
                expected_world_id=engine.world_id,
                includes_last_event=end == len(tick_events),
            )
        completed = projected
    assert completed.bodies == engine._snapshot.world.state.bodies
    assert (
        completed.collective_projects
        == engine._snapshot.world.state.collective_projects
    )
    assert completed.journeys == {}
    assert "Private-free" not in caplog.text


def test_persisted_regional_context_matches_snapshot_and_stays_detached() -> None:
    snapshot = _snapshot()
    context = regional_context_from_snapshot(snapshot)
    assert context is not None
    assert context.region_ids == ("north", "south")
    assert context.initial_placements[0].location_id == "loc-1"
    assert context.initial_placements[0].alive
    assert context.initial_placements[0].stage_id is None
    assert context.owner_ids == ("agent-1",)
    assert not hasattr(context, "journeys")
    assert not hasattr(context, "config")


@given(st.lists(st.sampled_from(("loc-a", "loc-b", "loc-c", "loc-x")), max_size=20))
def test_arbitrary_crossings_conserve_assigned_and_unassigned_people(
    destinations: list[str],
) -> None:
    from analysis.regional_population import fold_regional_history

    previous = "loc-a"
    events = []
    for tick, destination in enumerate(destinations):
        events.append(_move(tick, tick, "body-1", previous, destination))
        previous = destination
    history = fold_regional_history(
        _inputs(window_end=max(1, len(destinations)), events=tuple(events))
    )
    assert (
        sum(history.final_population.values()) + history.final_unassigned_population
        == 1
    )
    assert (
        sum(history.person_ticks.values()) + history.unassigned_person_ticks
        == max(1, len(destinations)) + 1
    )
