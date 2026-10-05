"""Ephemeral capacity and fatigue accrual under developmental stage effects."""

from __future__ import annotations

import logging
from dataclasses import replace

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    LifespanDistributionSpec,
    example_developmental_lifecycle_spec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import (
    alive_body,
    make_item,
    make_location,
    make_weather,
)
from world.actions import Take, Wait
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import LifecycleStageId
from world.lifecycle_effects import StageCapabilityEffect
from world.models import non_lethal_physical_rules
from world.values import ItemKind

_LOG = logging.getLogger("tests.lifecycle_capacity_fatigue_effects")


def _developmental_engine(
    *,
    carry_capacity: int = 10,
    physical_capacity_factor: float = 0.5,
    fatigue_accrual_factor: float = 1.5,
    items: tuple = (),
    inventory: tuple[EntityId, ...] = (),
) -> WorldEngine:
    body = alive_body(
        "body-1", carry_capacity=carry_capacity, inventory=inventory
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-capacity-fatigue"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        items=items,
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    base = example_developmental_lifecycle_spec(
        lifespan_ticks=24,
        max_population=2,
        policy_id="disabled",
        intra_stage_interpolation=False,
        min_assigned_ticks=24,
    )
    effects = tuple(
        StageCapabilityEffect(
            stage_id=effect.stage_id,
            physical_capacity_factor=(
                physical_capacity_factor
                if effect.stage_id.value == "dependent"
                else effect.physical_capacity_factor
            ),
            learning_rate_factor=effect.learning_rate_factor,
            fatigue_accrual_factor=(
                fatigue_accrual_factor
                if effect.stage_id.value == "dependent"
                else effect.fatigue_accrual_factor
            ),
            denied_command_kinds=effect.denied_command_kinds,
        )
        for effect in base.stage_capability_effects
    )
    spec = replace(
        base,
        stage_capability_effects=effects,
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="fixed", params={}
        ),
    )
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=31, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )


def test_ephemeral_capacity_scales_without_rewriting_stored_capacity() -> None:
    _LOG.debug("case_id=ephemeral_capacity_scale")
    engine = _developmental_engine(carry_capacity=10, physical_capacity_factor=0.5)
    body_id = EntityId("body-1")
    stored_before = engine._snapshot.world.state.bodies[body_id].carry_capacity.value
    capacity_map = engine._lifecycle_effective_carry_capacity(tick=0)
    assert capacity_map is not None
    assert capacity_map[body_id] == 5
    assert (
        engine._snapshot.world.state.bodies[body_id].carry_capacity.value
        == stored_before
        == 10
    )


def test_effects_off_omits_capacity_map() -> None:
    _LOG.debug("case_id=effects_off_capacity_passthrough")
    body = alive_body("body-1", carry_capacity=10)
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-capacity-passthrough"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=20)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=33, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )
    assert engine._lifecycle_effective_carry_capacity(tick=0) is None
    assert engine._lifecycle_metabolism_fatigue_map(tick=0) is None


def test_overload_denies_new_take_without_forced_drop() -> None:
    _LOG.debug("case_id=overload_deny_take")
    held = make_item(
        "item-held",
        kind=ItemKind.TOOL,
        location_id=None,
        holder_id="body-1",
        load=5,
    )
    ground = make_item(
        "item-ground",
        kind=ItemKind.TOOL,
        location_id="loc-1",
        holder_id=None,
        load=1,
    )
    engine = _developmental_engine(
        carry_capacity=10,
        physical_capacity_factor=0.5,
        items=(held, ground),
        inventory=(EntityId("item-held"),),
    )
    body = engine._snapshot.world.state.bodies[EntityId("body-1")]
    held_load = sum(
        engine._snapshot.world.state.items[item_id].load.value
        for item_id in body.inventory
    )
    assert held_load == 5
    batch = engine.observe()
    result = engine.resolve_tick(
        (
            ActionSubmission(
                batch.token, AgentId("agent-1"), Take(EntityId("item-ground"))
            ),
        )
    )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    body_after = engine._snapshot.world.state.bodies[EntityId("body-1")]
    after_load = sum(
        engine._snapshot.world.state.items[item_id].load.value
        for item_id in body_after.inventory
    )
    assert after_load == 5
    assert EntityId("item-held") in body_after.inventory
    assert (
        engine._snapshot.world.state.items[EntityId("item-ground")].holder_id is None
    )


def test_fatigue_factor_multiplies_metabolism_map() -> None:
    _LOG.debug("case_id=fatigue_metabolism_map")
    engine = _developmental_engine(fatigue_accrual_factor=1.5)
    body_id = EntityId("body-1")
    assert engine._lifecycle_fatigue_factor(entity_id=body_id, tick=0) == 1.5
    metabolism = engine._lifecycle_metabolism_fatigue_map(tick=0)
    assert metabolism is not None
    assert metabolism[body_id] == 1.5
    batch = engine.observe()
    engine.resolve_tick(
        (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
    )
    # Stored capacity still untouched after a tick with effects active.
    assert (
        engine._snapshot.world.state.bodies[body_id].carry_capacity.value == 10
    )


def test_age_zero_uses_dependent_factor_immediately() -> None:
    _LOG.debug("case_id=age_zero_factor")
    engine = _developmental_engine(physical_capacity_factor=0.5)
    assert engine.lifecycle_records[0].stage == LifecycleStageId("dependent")
    assert engine.lifecycle_records[0].entry_tick == 0
    capacity_map = engine._lifecycle_effective_carry_capacity(tick=0)
    assert capacity_map is not None
    assert capacity_map[EntityId("body-1")] == 5
