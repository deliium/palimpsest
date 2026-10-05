"""Mid-run admit establishes kinship edges via parent_agent_ids."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.demographic_policy import DemographicEntryCandidate
from simulation.engine import WorldEngine
from simulation.models import SimulationRunConfig
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner_models import (
    KinshipAdmitLinkPolicy,
    KinshipSpec,
    example_population_lifecycle_spec,
    seed_bootstrap_lifecycle_records,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.events import KinshipEdgeRecorded
from world.identifiers import EntityId, WorldId, WorldRevision
from world.kinship import parents_of
from world.lifecycle import OriginProvenance
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.kinship_admit_parent_links")


def _bootstrap() -> WorldBootstrap:
    body = alive_body("body-1")
    return WorldBootstrap(
        world_id=WorldId("world-kinship-admit"),
        revision=WorldRevision(0),
        locations=(make_location(body_capacity=8),),
        bodies=(body,),
        weather=(make_weather(),),
        registrations=(AgentRegistration(AgentId("agent-1"), body.entity_id),),
    )


def _engine(*, allow_parent_links: bool) -> WorldEngine:
    bootstrap = _bootstrap()
    lifecycle = example_population_lifecycle_spec(max_population=8)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=lifecycle
    )
    kinship = KinshipSpec(
        admit_link_policy=KinshipAdmitLinkPolicy(
            allow_parent_links_on_admit=allow_parent_links,
            require_living_parent=True,
        )
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=11, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=lifecycle,
        lifecycle_records=records,
        new_agent_initialization=default_new_agent_initialization_spec(),
        kinship_spec=kinship,
    )


def _candidate(
    *, parent_agent_ids: tuple[AgentId, ...] = ()
) -> DemographicEntryCandidate:
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
        parent_agent_ids=parent_agent_ids,
    )


def test_admit_establishes_parent_edge_when_policy_allows() -> None:
    _LOG.debug("case_id=admit_parent_links_on")
    engine = _engine(allow_parent_links=True)
    admission = engine.admit_population_entry(
        _candidate(parent_agent_ids=(AgentId("agent-1"),))
    )
    kinship_events = [
        event
        for event in admission.events
        if type(event.details) is KinshipEdgeRecorded
    ]
    assert len(kinship_events) == 1
    details = kinship_events[0].details
    assert details.parent_agent_id == "agent-1"
    assert details.child_agent_id == "entrant-0000-00"
    assert parents_of(engine.kinship_graph, AgentId("entrant-0000-00")) == (
        AgentId("agent-1"),
    )


def test_admit_parent_links_reject_when_policy_disabled() -> None:
    _LOG.debug("case_id=admit_parent_links_disabled")
    engine = _engine(allow_parent_links=False)
    with pytest.raises(ValueError, match="kinship_admit_links_disabled"):
        engine.admit_population_entry(
            _candidate(parent_agent_ids=(AgentId("agent-1"),))
        )


def test_admit_parent_links_require_kinship_channel() -> None:
    _LOG.debug("case_id=admit_requires_kinship_flag")
    bootstrap = _bootstrap()
    lifecycle = example_population_lifecycle_spec(max_population=8)
    records = seed_bootstrap_lifecycle_records(
        registrations=bootstrap.registrations, spec=lifecycle
    )
    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=13, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        population_lifecycle=lifecycle,
        lifecycle_records=records,
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    with pytest.raises(ValueError, match="kinship_admit_requires_flag"):
        engine.admit_population_entry(
            _candidate(parent_agent_ids=(AgentId("agent-1"),))
        )
