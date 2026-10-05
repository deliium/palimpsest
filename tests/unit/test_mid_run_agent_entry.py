"""Mid-run admit_population_entry under generational_population channel."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.demographic_policy import DemographicEntryCandidate
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import AgentCreated, AgentEnteredWorld
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import OriginProvenance

_LOG = logging.getLogger("tests.mid_run_agent_entry")


def _bootstrap() -> WorldBootstrap:
    body = alive_body("body-1")
    return WorldBootstrap(
        world_id=WorldId("world-admit"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )


def _candidate(**overrides: object) -> DemographicEntryCandidate:
    base = {
        "agent_id": AgentId("entrant-0000-00"),
        "body_id": EntityId("body-entrant-0000-00"),
        "spawn_location_id": EntityId("loc-1"),
        "generation_index": 1,
        "cohort_id": "cohort-0000",
        "provenance": OriginProvenance.DEMOGRAPHIC_POLICY,
        "name_prefix": "entrant",
        "sort_key": ("entrant-0000-00", "body-entrant-0000-00"),
    }
    base.update(overrides)
    return DemographicEntryCandidate(**base)  # type: ignore[arg-type]


def _engine(*, channel_on: bool, max_population: int = 8) -> WorldEngine:
    bootstrap = _bootstrap()
    if not channel_on:
        return WorldEngine(config=SimulationRunConfig(seed=3), bootstrap=bootstrap)
    spec = example_population_lifecycle_spec(max_population=max_population)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    return WorldEngine(
        config=SimulationRunConfig(seed=3),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
    )


def test_flag_off_rejects_admit() -> None:
    _LOG.debug("case_id=admit_channel_off")
    engine = _engine(channel_on=False)
    with pytest.raises(RuntimeError, match="lifecycle_channel_off"):
        engine.admit_population_entry(_candidate())


def test_admit_appends_body_registration_lifecycle_and_events() -> None:
    _LOG.debug("case_id=admit_success")
    engine = _engine(channel_on=True)
    admission = engine.admit_population_entry(_candidate())
    assert admission.agent_id.value == "entrant-0000-00"
    assert admission.entry_tick == 0
    assert admission.provenance is OriginProvenance.DEMOGRAPHIC_POLICY
    assert len(engine.ordered_registrations) == 2
    assert engine.ordered_registrations[-1].agent_id == admission.agent_id
    assert engine.registration_translator.to_entity_id(admission.agent_id) == (
        admission.body_id
    )
    assert admission.body_id in engine._snapshot.world.state.bodies
    assert len(engine.lifecycle_records) == 2
    record = engine.lifecycle_records[-1]
    assert record.entry_tick == 0
    assert record.cohort_id == "cohort-0000"
    assert len(admission.events) == 2
    assert type(admission.events[0].details) is AgentCreated
    assert type(admission.events[1].details) is AgentEnteredWorld
    history = engine._snapshot.event_history
    assert history[-2:] == admission.events
    assert history[-2].sequence == 0
    assert history[-1].sequence == 1


def test_admit_enforces_population_cap() -> None:
    _LOG.debug("case_id=admit_population_cap")
    engine = _engine(channel_on=True, max_population=1)
    with pytest.raises(ValueError, match="population_cap"):
        engine.admit_population_entry(_candidate())


def test_admit_rejects_id_collision() -> None:
    _LOG.debug("case_id=admit_id_collision")
    engine = _engine(channel_on=True)
    engine.admit_population_entry(_candidate())
    with pytest.raises(ValueError, match="id_collision"):
        engine.admit_population_entry(_candidate())


def test_admit_rejects_bootstrap_provenance() -> None:
    _LOG.debug("case_id=admit_bootstrap_forbidden")
    engine = _engine(channel_on=True)
    with pytest.raises(ValueError, match="lifecycle_bootstrap_no_created_event"):
        engine.admit_population_entry(
            _candidate(provenance=OriginProvenance.BOOTSTRAP)
        )
