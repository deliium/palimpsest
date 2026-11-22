# mypy: ignore-errors

"""Deterministic private disease lifecycle pass."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from tests.simulation_helpers import alive_body, make_location, make_weather
from world._disease import (
    DiseaseConditionRow,
    DiseasePhase,
    advance_disease_pass,
    disease_net_transitions,
    reconcile_disease_rows_for_dead_bodies,
)
from world._state import WorldState
from world.identifiers import EntityId, WorldRevision
from world.models import LifeStatus
from world.regions import Journey, RegionsMigrationSpec
from world.values import Health

pytestmark = pytest.mark.unit


def _state(
    bodies,
    *,
    disease_state=None,
    journeys=None,
    regions_migration=None,
    locations=None,
) -> WorldState:
    locs = locations or (make_location("loc-1"),)
    return WorldState(
        WorldRevision(0),
        locations=locs,
        bodies=tuple(bodies),
        weather=tuple(make_weather(loc.entity_id.value) for loc in locs),
        disease_state=disease_state,
        disease_require_living=False,
        regions_migration=regions_migration,
        journeys=journeys,
    )


def _draw(outcomes: dict[tuple[str, str], bool]):
    calls: list[tuple[str, str]] = []

    def draw(entity_id: EntityId, kind: str) -> bool:
        key = (entity_id.value, kind)
        calls.append(key)
        return outcomes.get(key, False)

    draw.calls = calls  # type: ignore[attr-defined]
    return draw


def test_disabled_channel_is_inert() -> None:
    body = alive_body("body-1", location_id="loc-1")
    start = _state([body], disease_state=None)
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw({}),
    )
    assert result.disease_state is None
    assert result.mortality_body_ids == ()
    assert result.bodies[body.entity_id].life_status is LifeStatus.ALIVE


def test_enabled_empty_tick_stays_empty() -> None:
    body = alive_body("body-1", location_id="loc-1")
    start = _state([body], disease_state={})
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw({("body-1", "exposure"): True, ("body-1", "transmission"): True}),
    )
    assert result.disease_state is not None
    assert dict(result.disease_state) == {}


def test_zero_and_full_milli_trials() -> None:
    active = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _state([active, susceptible], disease_state=rows)
    never = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=_draw({}),
    )
    assert susceptible.entity_id not in never.disease_state
    always = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=3,
        immunity_after_recovery=False,
        draw=_draw(
            {
                ("body-b", "exposure"): True,
                ("body-b", "transmission"): True,
            }
        ),
    )
    assert always.disease_state[susceptible.entity_id].phase is DiseasePhase.LATENT
    assert always.disease_state[susceptible.entity_id].due_tick == 2


def test_multiple_active_sources_dedupe_trials() -> None:
    a = alive_body("body-a", location_id="loc-1")
    b = alive_body("body-b", location_id="loc-1")
    c = alive_body("body-c", location_id="loc-1")
    rows = {
        a.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        ),
        b.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=True
        ),
    }
    start = _state([a, b, c], disease_state=rows)
    draw = _draw(
        {("body-c", "exposure"): True, ("body-c", "transmission"): True}
    )
    advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=draw,
    )
    assert draw.calls.count(("body-c", "exposure")) == 1
    assert draw.calls.count(("body-c", "transmission")) == 1


def test_remote_location_excluded() -> None:
    active = alive_body("body-a", location_id="loc-1")
    remote = alive_body("body-b", location_id="loc-2")
    locs = (
        make_location("loc-1", adjacent=("loc-2",)),
        make_location("loc-2", adjacent=("loc-1",)),
    )
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _state(
        [active, remote],
        disease_state=rows,
        locations=locs,
    )
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw(
            {
                ("body-b", "exposure"): True,
                ("body-b", "transmission"): True,
            }
        ),
    )
    assert remote.entity_id not in result.disease_state


def test_transit_participant_excluded() -> None:
    from world.regions import CognitionMode, LocationRegion, RegionDefinition, RouteSpec

    loc_a = make_location("loc-a", adjacent=("loc-b",))
    loc_b = make_location("loc-b", adjacent=("loc-a",))
    active = alive_body("body-a", location_id="loc-a")
    traveler = alive_body("body-b", location_id="loc-a")
    spec = RegionsMigrationSpec(
        regions=(RegionDefinition("all", "All"),),
        location_regions=(
            LocationRegion(EntityId("loc-a"), "all"),
            LocationRegion(EntityId("loc-b"), "all"),
        ),
        routes=(RouteSpec(EntityId("loc-a"), EntityId("loc-b"), 1, 1.0),),
        max_arrival_wait_ticks=1,
        residence_min_ticks=1,
        destination_memory_limit=2,
        destination_hop_limit=1,
        cognition_mode=CognitionMode.DISABLED,
    )
    journey = Journey(
        journey_id="j-1",
        participant_body_ids=(traveler.entity_id,),
        actor_body_id=traveler.entity_id,
        origin_location_id=EntityId("loc-a"),
        destination_location_id=EntityId("loc-b"),
        origin_region_id="all",
        destination_region_id="all",
        start_tick=0,
        due_tick=1,
        charged_fatigue_cost=1.0,
        arrival_wait_deadline_tick=2,
    )
    rows = {
        active.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=9, symptomatic=False
        )
    }
    start = _state(
        [active, traveler],
        disease_state=rows,
        locations=(loc_a, loc_b),
        regions_migration=spec,
        journeys=(journey,),
    )
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw(
            {
                ("body-b", "exposure"): True,
                ("body-b", "transmission"): True,
            }
        ),
    )
    assert traveler.entity_id not in result.disease_state


def test_same_pass_no_infection_chain() -> None:
    latent = alive_body("body-a", location_id="loc-1")
    susceptible = alive_body("body-b", location_id="loc-1")
    rows = {
        latent.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.LATENT, due_tick=0
        )
    }
    start = _state([latent, susceptible], disease_state=rows)
    result = advance_disease_pass(
        tick=0,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=False,
        draw=_draw(
            {
                ("body-a", "symptom"): True,
                ("body-b", "exposure"): True,
                ("body-b", "transmission"): True,
            }
        ),
    )
    assert result.disease_state[latent.entity_id].phase is DiseasePhase.ACTIVE
    assert susceptible.entity_id not in result.disease_state


def test_onset_and_terminal_ticks_and_immunity_branches() -> None:
    body = alive_body("body-1", location_id="loc-1")
    latent_rows = {
        body.entity_id: DiseaseConditionRow(phase=DiseasePhase.LATENT, due_tick=3)
    }
    start = _state([body], disease_state=latent_rows)
    onset = advance_disease_pass(
        tick=3,
        start_state=start,
        working_state=start,
        latent_ticks=2,
        active_ticks=4,
        immunity_after_recovery=True,
        draw=_draw({("body-1", "symptom"): False}),
    )
    assert onset.disease_state[body.entity_id] == DiseaseConditionRow(
        phase=DiseasePhase.ACTIVE, due_tick=7, symptomatic=False
    )
    active_start = _state(
        [body], disease_state={body.entity_id: onset.disease_state[body.entity_id]}
    )
    recovered = advance_disease_pass(
        tick=7,
        start_state=active_start,
        working_state=active_start,
        latent_ticks=2,
        active_ticks=4,
        immunity_after_recovery=True,
        draw=_draw({("body-1", "terminal"): False}),
    )
    assert recovered.disease_state[body.entity_id].phase is DiseasePhase.IMMUNE
    susceptible_again = advance_disease_pass(
        tick=7,
        start_state=active_start,
        working_state=active_start,
        latent_ticks=2,
        active_ticks=4,
        immunity_after_recovery=False,
        draw=_draw({("body-1", "terminal"): False}),
    )
    assert body.entity_id not in susceptible_again.disease_state


def test_disease_mortality_and_physics_precedence() -> None:
    body = alive_body("body-1", location_id="loc-1")
    rows = {
        body.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=1, symptomatic=True
        )
    }
    start = _state([body], disease_state=rows)
    killed = advance_disease_pass(
        tick=1,
        start_state=start,
        working_state=start,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw({("body-1", "terminal"): True}),
    )
    assert killed.mortality_body_ids == (body.entity_id,)
    assert killed.bodies[body.entity_id].life_status is LifeStatus.DEAD
    assert body.entity_id not in killed.disease_state

    already_dead = replace(
        body, life_status=LifeStatus.DEAD, health=Health(0.0)
    )
    dead_working = _state([already_dead], disease_state=rows)
    skipped = advance_disease_pass(
        tick=1,
        start_state=start,
        working_state=dead_working,
        latent_ticks=1,
        active_ticks=1,
        immunity_after_recovery=False,
        draw=_draw({("body-1", "terminal"): True}),
    )
    assert skipped.mortality_body_ids == ()
    assert body.entity_id in skipped.disease_state


def test_engine_disabled_and_onset_and_candidate_abandon() -> None:
    from dataclasses import replace

    from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec
    from simulation.engine import WorldEngine
    from simulation.lifecycle import ActionSubmission
    from tests.physical_helpers import physical_config, two_location_fixture
    from world._disease import bootstrap_disease_rows
    from world.actions import Wait
    from world.events import Died, DiseaseStateChanged
    from world.models import non_lethal_physical_rules

    fixture = two_location_fixture()
    body = fixture.bodies[0]
    off = WorldEngine(
        config=physical_config(3, rules=non_lethal_physical_rules()),
        bootstrap=fixture.as_bootstrap(),
    )
    batch = off.observe()
    off.resolve_tick(
        tuple(
            ActionSubmission(batch.token, reg.agent_id, Wait())
            for reg in fixture.registrations
        )
    )
    assert off._snapshot.world.state.disease_state is None

    rows = bootstrap_disease_rows(
        founder_ids=(body.entity_id,),
        latent_ticks=1,
        tick0=0,
        body_index={item.entity_id: item for item in fixture.bodies},
    )
    bootstrap = replace(fixture.as_bootstrap(), disease_state=rows)
    spec = DiseaseMechanicsSpec(
        policy_id=DISEASE_POLICY_ID,
        initial_latent_entity_ids=(body.entity_id,),
        exposure_chance_milli=0,
        transmission_chance_milli=0,
        symptom_chance_milli=1000,
        mortality_chance_milli=0,
        latent_ticks=1,
        active_ticks=2,
        immunity_after_recovery=True,
    )
    engine = WorldEngine(
        config=physical_config(5, rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        disease_mechanics=spec,
    )
    assert engine._snapshot.world.state.disease_state[body.entity_id].phase is (
        DiseasePhase.LATENT
    )
    before = engine._snapshot.world.state
    batch = engine.observe()
    submissions = tuple(
        ActionSubmission(batch.token, reg.agent_id, Wait())
        for reg in fixture.registrations
    )
    candidate = engine._prepare_tick_candidate(submissions)
    assert engine._snapshot.world.state is before
    assert candidate.next_snapshot.world.state.disease_state[body.entity_id].phase is (
        DiseasePhase.LATENT
    )
    engine._finalize_tick_candidate(candidate)
    batch = engine.observe()
    result = engine.resolve_tick(
        tuple(
            ActionSubmission(batch.token, reg.agent_id, Wait())
            for reg in fixture.registrations
        )
    )
    assert engine._snapshot.world.state.disease_state[body.entity_id].phase is (
        DiseasePhase.ACTIVE
    )
    kinds = [record.event.details.kind for record in result.events]
    assert "disease_state_changed" in kinds
    disease_indexes = [
        index
        for index, record in enumerate(result.events)
        if type(record.event.details) is DiseaseStateChanged
    ]
    died_indexes = [
        index
        for index, record in enumerate(result.events)
        if type(record.event.details) is Died
    ]
    assert disease_indexes
    if died_indexes:
        assert max(died_indexes) < min(disease_indexes)


def test_reconcile_and_net_transitions() -> None:
    living = alive_body("body-a", location_id="loc-1")
    dead = replace(
        alive_body("body-b", location_id="loc-1"),
        life_status=LifeStatus.DEAD,
        health=Health(0.0),
    )
    rows = MappingProxyType(
        {
            living.entity_id: DiseaseConditionRow(phase=DiseasePhase.IMMUNE),
            dead.entity_id: DiseaseConditionRow(
                phase=DiseasePhase.LATENT, due_tick=4
            ),
        }
    )
    reconciled = reconcile_disease_rows_for_dead_bodies(
        rows, body_index={living.entity_id: living, dead.entity_id: dead}
    )
    assert dict(reconciled) == {
        living.entity_id: DiseaseConditionRow(phase=DiseasePhase.IMMUNE)
    }
    start = {
        living.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.LATENT, due_tick=1
        )
    }
    final = {
        living.entity_id: DiseaseConditionRow(
            phase=DiseasePhase.ACTIVE, due_tick=3, symptomatic=True
        )
    }
    assert disease_net_transitions(start, final) == (
        (
            living.entity_id,
            start[living.entity_id],
            final[living.entity_id],
        ),
    )
    assert disease_net_transitions(start, start) == ()
