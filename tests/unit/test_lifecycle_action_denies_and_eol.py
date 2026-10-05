"""Stage action denies and assigned-lifespan EOL integration."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionResolutionStatus, ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    LifespanDistributionSpec,
    example_developmental_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_resource, make_weather
from world.actions import Harvest, Wait
from world.effects import DeathCause
from world.events import Died
from world.identifiers import EntityId, RecipeId, WorldId, WorldRevision
from world.lifecycle_effects import resolve_stage_effect
from world.models import LifeStatus, non_lethal_physical_rules
from world.production import example_production_catalog
from world.values import ResourceKind

_LOG = logging.getLogger("tests.lifecycle_action_denies_and_eol")


def _engine(*, lifespan_ticks: int = 8) -> WorldEngine:
    body = alive_body("body-1")
    resource = make_resource(
        "res-wood",
        name="Wood",
        kind=ResourceKind.MATERIAL,
        location_id="loc-1",
    )
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-deny-eol"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        resources=(resource,),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_developmental_lifecycle_spec(
        lifespan_ticks=lifespan_ticks,
        max_population=2,
        policy_id="disabled",
        intra_stage_interpolation=False,
        min_assigned_ticks=lifespan_ticks,
    )
    spec = replace(
        spec,
        lifespan_distribution=LifespanDistributionSpec(
            distribution_id="fixed", params={}
        ),
    )
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=19, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
        production_catalog=example_production_catalog(),
    )


def _step(engine: WorldEngine, command=Wait()) -> object:
    batch = engine.observe()
    submissions = tuple(
        ActionSubmission(
            batch.token,
            engine.registration_translator.to_agent_id(observation.observer_id),
            command,
        )
        for observation in batch.observations
    )
    return engine.resolve_tick(submissions)


def test_dependent_denies_harvest_structural_rejection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=dependent_harvest_denied")
    engine = _engine(lifespan_ticks=20)
    assert engine.lifecycle_records[0].stage.value == "dependent"
    with caplog.at_level(logging.WARNING):
        result = _step(
            engine, Harvest(RecipeId("harvest_wood"), EntityId("res-wood"))
        )
    assert result.resolutions[0].status is ActionResolutionStatus.REJECTED
    assert "lifecycle_stage_action_denied" in caplog.text


def test_elder_empty_denies_match_independent() -> None:
    _LOG.debug("case_id=elder_vs_independent_denies")
    spec = example_developmental_lifecycle_spec(lifespan_ticks=24)
    independent = resolve_stage_effect(
        next(
            item.stage_id
            for item in spec.stage_thresholds
            if item.stage_id.value == "independent"
        ),
        spec.stage_capability_effects,
    )
    elder = resolve_stage_effect(
        next(
            item.stage_id
            for item in spec.stage_thresholds
            if item.stage_id.value == "elder"
        ),
        spec.stage_capability_effects,
    )
    assert independent.denied_command_kinds == ()
    assert elder.denied_command_kinds == ()


def test_assigned_lifespan_eol_emits_died_lifespan() -> None:
    _LOG.debug("case_id=assigned_eol")
    engine = _engine(lifespan_ticks=6)
    assert engine.lifecycle_records[0].assigned_lifespan_ticks == 6
    for _ in range(8):
        _step(engine)
    body = next(iter(engine._snapshot.world.state.bodies.values()))
    assert body.life_status is LifeStatus.DEAD
    deaths = [
        event.details
        for event in engine._snapshot.event_history
        if type(event.details) is Died
    ]
    assert any(death.death_cause is DeathCause.LIFESPAN for death in deaths)
