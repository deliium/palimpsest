"""Deterministic lifecycle stage progression and lifespan death."""

from __future__ import annotations

import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.lifecycle import ActionSubmission
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.actions import Wait
from world.effects import DeathCause
from world.events import Died, LifecycleStageChanged
from world.identifiers import WorldId, WorldRevision
from world.models import LifeStatus, non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_progression_determinism")


def _engine(*, lifespan_ticks: int = 6, policy_id: str = "disabled") -> WorldEngine:
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-lifecycle-prog"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    spec = example_population_lifecycle_spec(
        lifespan_ticks=lifespan_ticks,
        max_population=4,
        policy_id=policy_id,
    )
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=11, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )


def _step(engine: WorldEngine) -> None:
    batch = engine.observe()
    submissions = tuple(
        ActionSubmission(
            batch.token,
            engine.registration_translator.to_agent_id(observation.observer_id),
            Wait(),
        )
        for observation in batch.observations
    )
    engine.resolve_tick(submissions)


def test_stage_progression_emits_lifecycle_stage_changed() -> None:
    _LOG.debug("case_id=stage_progression")
    engine = _engine(lifespan_ticks=20)
    assert engine.lifecycle_records[0].stage.value == "infant"
    # infant inclusive max age 2 → first juvenile age is 3 (resolve tick 3)
    for _ in range(4):
        _step(engine)
    assert engine.last_tick_result is not None
    stages = [
        record.event.details
        for record in engine.last_tick_result.events
        if type(record.event.details) is LifecycleStageChanged
    ]
    assert stages
    assert stages[0].new_stage == "juvenile"
    assert engine.lifecycle_records[0].stage.value == "juvenile"


def test_lifespan_death_emits_died_lifespan() -> None:
    _LOG.debug("case_id=lifespan_death")
    engine = _engine(lifespan_ticks=8)
    # age == tick for bootstrap; death when age >= lifespan_ticks (tick 8)
    for _ in range(9):
        _step(engine)
    assert engine.last_tick_result is not None
    deaths = [
        record.event.details
        for record in engine.last_tick_result.events
        if type(record.event.details) is Died
    ]
    assert deaths
    assert deaths[0].death_cause is DeathCause.LIFESPAN
    body = engine._snapshot.world.state.bodies[
        engine.ordered_registrations[0].entity_id
    ]
    assert body.life_status is LifeStatus.DEAD


def test_same_seed_stage_timeline_identical() -> None:
    _LOG.debug("case_id=stage_timeline_twin")
    events_a: list[tuple] = []
    events_b: list[tuple] = []
    for sink in (events_a, events_b):
        engine = _engine(lifespan_ticks=20)
        for _ in range(6):
            _step(engine)
            assert engine.last_tick_result is not None
            sink.append(
                tuple(
                    (
                        record.event.details.kind,
                        getattr(record.event.details, "new_stage", None),
                        getattr(record.event.details, "death_cause", None),
                    )
                    for record in engine.last_tick_result.events
                    if type(record.event.details) in {LifecycleStageChanged, Died}
                )
            )
    assert events_a == events_b


def test_fixed_interval_demographic_admits_on_schedule() -> None:
    _LOG.debug("case_id=demographic_tick_admit")
    engine = _engine(lifespan_ticks=20, policy_id="fixed_interval_entry")
    assert len(engine.ordered_registrations) == 1
    # Policy fires when tick % 5 == 0 and tick >= 1 → first admit on tick 5.
    for _ in range(6):
        _step(engine)
    assert len(engine.ordered_registrations) == 2
    assert engine.last_tick_result is not None
    kinds = [record.event.details.kind for record in engine.last_tick_result.events]
    assert "agent_created" in kinds
    assert "agent_entered_world" in kinds

    _LOG.debug("case_id=flag_off_no_lifecycle_events")
    body = alive_body("body-1")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-lifecycle-off"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=11, physical_rules=non_lethal_physical_rules()),
        bootstrap=bootstrap,
    )
    for _ in range(4):
        _step(engine)
        assert engine.last_tick_result is not None
        for record in engine.last_tick_result.events:
            if type(record.event.details) is LifecycleStageChanged:
                raise AssertionError("unexpected lifecycle stage event")
            if (
                type(record.event.details) is Died
                and record.event.details.death_cause is DeathCause.LIFESPAN
            ):
                raise AssertionError("unexpected lifespan death")
