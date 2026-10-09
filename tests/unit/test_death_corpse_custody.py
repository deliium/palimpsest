"""Corpse custody opens beside existing Died emissions and nowhere else."""

from __future__ import annotations

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_item, make_location, make_weather
from world._experiment_apply import _set_health
from world._operations import OperationAccepted, validate_action_request
from world._physical import apply_autonomous_physical_step
from world._rules import apply_operation
from world._state import WorldState
from world.actions import ActionRequest, Attack, Wait, require_agent_command
from world.effects import DeathCause, ResolvedActionEffects, ResolvedAttackEffect
from world.events import CorpseCustodyOpened, Died
from world.identifiers import (
    EntityId,
    ProposalId,
    RequestId,
    WorldId,
    WorldRevision,
)
from world.models import (
    AgentBody,
    LifeStatus,
    copy_body,
    default_physical_rules,
    non_lethal_physical_rules,
)
from world.values import (
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)


def _needs_body(*, inventory: tuple[EntityId, ...] = ()) -> AgentBody:
    return AgentBody(
        entity_id=EntityId("body-1"),
        location_id=EntityId("loc-1"),
        health=Health(5),
        hunger=Hunger(100),
        thirst=Thirst(100),
        fatigue=Fatigue(100),
        temperature=TemperatureCelsius(36.5),
        inventory=inventory,
        life_status=LifeStatus.ALIVE,
        carry_capacity=alive_body().carry_capacity,
    )


def _opened(step) -> tuple[CorpseCustodyOpened, ...]:
    return tuple(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is CorpseCustodyOpened
    )


def test_needs_death_keeps_item_on_a_full_location() -> None:
    item = make_item("item-1", location_id=None, holder_id="body-1")
    body = _needs_body(inventory=(item.entity_id,))
    full = make_location("loc-1", item_capacity=0, base_temperature=-40.0)
    off = apply_autonomous_physical_step(
        state=WorldState(
            WorldRevision(0),
            locations=(full,),
            items=(item,),
            bodies=(body,),
            weather=(make_weather("loc-1"),),
        ),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
    )
    assert _opened(off) == ()
    on = apply_autonomous_physical_step(
        state=WorldState(
            WorldRevision(0),
            locations=(full,),
            items=(item,),
            bodies=(body,),
            weather=(make_weather("loc-1"),),
        ),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
        possession_succession_active=True,
    )
    opened = _opened(on)
    assert len(opened) == 1
    assert opened[0].item_ids == (item.entity_id,)
    held = on.working_state.items[item.entity_id]
    assert held.holder_id == EntityId("body-1")
    assert held.location_id is None
    died = next(
        detail.details for detail in on.pending_details if type(detail.details) is Died
    )
    assert died.death_cause is DeathCause.COMBINED_NEEDS


def test_empty_inventory_still_opens_custody() -> None:
    step = apply_autonomous_physical_step(
        state=WorldState(
            WorldRevision(0),
            locations=(make_location(),),
            bodies=(_needs_body(),),
            weather=(make_weather(),),
        ),
        rules=default_physical_rules(),
        tick=0,
        hour=0,
        day_phase=DayPhase.NIGHT,
        possession_succession_active=True,
    )
    opened = _opened(step)
    assert len(opened) == 1
    assert opened[0].item_ids == ()


def test_exposure_death_opens_custody() -> None:
    item = make_item("item-1", location_id=None, holder_id="body-1")
    body = copy_body(
        alive_body("body-1", inventory=(item.entity_id,)),
        health=Health(4),
        temperature=TemperatureCelsius(50.0),
    )
    hot = make_location("loc-1", base_temperature=50.0, shelter_factor=0.0)
    step = apply_autonomous_physical_step(
        state=WorldState(
            WorldRevision(0),
            locations=(hot,),
            items=(item,),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        rules=default_physical_rules(),
        tick=6,
        hour=6,
        day_phase=DayPhase.DAY,
        possession_succession_active=True,
    )
    opened = _opened(step)
    assert len(opened) == 1
    assert opened[0].item_ids == (item.entity_id,)
    died = next(
        detail.details
        for detail in step.pending_details
        if type(detail.details) is Died
    )
    assert died.death_cause is DeathCause.EXPOSURE


def test_attack_death_opens_custody_without_moving_the_item() -> None:
    item = make_item("item-2", location_id=None, holder_id="body-2")
    state = WorldState(
        WorldRevision(1),
        locations=(make_location(item_capacity=0),),
        items=(item,),
        bodies=(
            alive_body("body-1"),
            alive_body("body-2", inventory=(item.entity_id,)),
        ),
        weather=(make_weather(),),
    )
    outcome = validate_action_request(
        world_id=WorldId("world-1"),
        state=state,
        request=ActionRequest(
            request_id=RequestId("r-1"),
            proposal_id=ProposalId("p-1"),
            world_id=WorldId("world-1"),
            actor_id=EntityId("body-1"),
            revision=WorldRevision(1),
            command=require_agent_command(Attack(EntityId("body-2"))),
        ),
    )
    assert type(outcome) is OperationAccepted
    applied = apply_operation(
        state,
        outcome.operation,
        resolved=ResolvedActionEffects(
            {
                RequestId("r-1"): ResolvedAttackEffect(
                    request_id=RequestId("r-1"), hit=True, damage=200
                )
            }
        ),
        possession_succession_active=True,
    )
    opened = [
        details
        for details in applied.extra_event_details
        if type(details) is CorpseCustodyOpened
    ]
    assert len(opened) == 1
    assert opened[0].item_ids == (item.entity_id,)
    assert applied.next_state.items[item.entity_id].holder_id == EntityId("body-2")


def test_lifespan_death_opens_custody() -> None:
    item = make_item("item-1", location_id=None, holder_id="body-1")
    body = alive_body("body-1", inventory=(item.entity_id,))
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-custody-life"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        items=(item,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=8, max_population=4)
    engine = WorldEngine(
        config=SimulationRunConfig(seed=3, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=seed_bootstrap_lifecycle_records(
            registrations=bootstrap.registrations, spec=spec
        ),
        possession_succession_active=True,
    )
    opened: list[CorpseCustodyOpened] = []
    for _ in range(9):
        batch = engine.observe()
        engine.resolve_tick(
            tuple(
                ActionSubmission(
                    batch.token,
                    engine.registration_translator.to_agent_id(
                        observation.observer_id
                    ),
                    Wait(),
                )
                for observation in batch.observations
            )
        )
        result = engine.last_tick_result
        assert result is not None
        opened.extend(
            record.event.details
            for record in result.events
            if type(record.event.details) is CorpseCustodyOpened
        )
    assert len(opened) == 1
    assert opened[0].item_ids == (item.entity_id,)


def test_experiment_harm_zero_does_not_open_custody() -> None:
    state = WorldState(
        WorldRevision(0),
        locations=(make_location(),),
        bodies=(alive_body("body-1"),),
        weather=(make_weather(),),
    )
    harmed = _set_health(state, EntityId("body-1"), 0.0)
    assert harmed.bodies[EntityId("body-1")].life_status is LifeStatus.DEAD
    assert harmed.corpse_custody_item_ids == frozenset()
