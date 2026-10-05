"""Mid-run admit emits AgentCreated → AgentInitializationRecorded → AgentEnteredWorld."""

from __future__ import annotations

import logging

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.demographic_policy import DemographicEntryCandidate
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import (
    AgentCreated,
    AgentEnteredWorld,
    AgentInitializationRecorded,
    EVENT_SCHEMA_REPLAY_V10,
)
from world.identifiers import EntityId, WorldId, WorldRevision
from world.lifecycle import OriginProvenance

_LOG = logging.getLogger("tests.new_agent_provenance_events")


def _bootstrap() -> WorldBootstrap:
    body = alive_body("body-1")
    return WorldBootstrap(
        world_id=WorldId("world-prov"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )


def _candidate() -> DemographicEntryCandidate:
    return DemographicEntryCandidate(
        agent_id=AgentId("entrant-0000-00"),
        body_id=EntityId("body-entrant-0000-00"),
        spawn_location_id=EntityId("loc-1"),
        generation_index=1,
        cohort_id="cohort-0000",
        provenance=OriginProvenance.DEMOGRAPHIC_POLICY,
        name_prefix="entrant",
        sort_key=("entrant-0000-00", "body-entrant-0000-00"),
        creation_reason="demographic_policy",
        origin_refs=(),
    )


def test_admit_emits_provenance_triple_when_init_active() -> None:
    _LOG.debug("case_id=admit_provenance_triple")
    bootstrap = _bootstrap()
    spec = example_population_lifecycle_spec(max_population=8)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=spec
    )
    engine = WorldEngine(
        config=SimulationRunConfig(seed=3),
        bootstrap=bootstrap,
        population_lifecycle=spec,
        lifecycle_records=records,
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    assert engine.new_agent_provenance_active is True
    admission = engine.admit_population_entry(_candidate())
    assert len(admission.events) == 3
    assert type(admission.events[0].details) is AgentCreated
    assert type(admission.events[1].details) is AgentInitializationRecorded
    assert type(admission.events[2].details) is AgentEnteredWorld
    assert admission.events[0].schema_version == EVENT_SCHEMA_REPLAY_V10
    assert admission.events[1].details.creation_reason == "demographic_policy"
    assert admission.creation_config_id is not None
    assert admission.creation_config_id.startswith("nai-")
