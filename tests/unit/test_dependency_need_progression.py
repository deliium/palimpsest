"""Deterministic dependency unmet-need progression tests."""

from __future__ import annotations

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
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Wait
from world.dependency_care import CareNeedId, compute_unmet_tick_effects
from world.identifiers import WorldId, WorldRevision
from world.lifecycle import DependencyStatus
from world.models import non_lethal_physical_rules


def test_compute_unmet_tick_effects_food_accrual() -> None:
    from simulation.runner_models import example_dependency_care_spec as make_spec

    spec = make_spec(enabled_needs=("food",))
    policies = spec.to_domain_policies()
    effect = compute_unmet_tick_effects(
        body_id="body-1",
        status=DependencyStatus.DEPENDENT,
        enabled_needs=(CareNeedId.FOOD,),
        policies=policies,  # type: ignore[arg-type]
        hunger=50.0,
        thirst=0.0,
        health=100.0,
        fatigue=0.0,
        shelter_factor=1.0,
    )
    assert effect.hunger_extra > 0.0
    independent = compute_unmet_tick_effects(
        body_id="body-1",
        status=DependencyStatus.INDEPENDENT,
        enabled_needs=(CareNeedId.FOOD,),
        policies=policies,  # type: ignore[arg-type]
        hunger=50.0,
        thirst=0.0,
        health=100.0,
        fatigue=0.0,
        shelter_factor=1.0,
    )
    assert independent.hunger_extra == 0.0


def _engine() -> WorldEngine:
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-need-prog"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(lifespan_ticks=40, max_population=2)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=55, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
        dependency_care_spec=example_dependency_care_spec(
            enabled_needs=("food", "water")
        ),
    )


def test_unmet_need_progression_twin_run_deterministic() -> None:
    def _run() -> tuple[float, float]:
        engine = _engine()
        for _ in range(3):
            batch = engine.observe()
            engine.resolve_tick(
                (ActionSubmission(batch.token, AgentId("agent-1"), Wait()),)
            )
        body = next(iter(engine._snapshot.world.state.bodies.values()))
        return body.hunger.value, body.thirst.value

    first = _run()
    second = _run()
    assert first == second
    assert first[0] > 0.0 or first[1] > 0.0
