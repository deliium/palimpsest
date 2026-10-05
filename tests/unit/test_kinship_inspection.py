"""Inspection projection helpers for objective kinship."""

from __future__ import annotations

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.inspection import DetachedInspectionProjector
from simulation.models import RunId, SimulationRunConfig
from simulation.runner_models import example_kinship_spec
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules


def _engine() -> WorldEngine:
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-kinship-inspect"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-a"), body_a.entity_id),
            AgentRegistration(AgentId("agent-b"), body_b.entity_id),
        ),
    )
    return WorldEngine(
        config=SimulationRunConfig(
            seed=17, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-kinship-inspect"),
        kinship_spec=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )


def test_project_kinship_document() -> None:
    projector = DetachedInspectionProjector()
    document = projector.project_kinship(_engine())
    assert document.channel_active is True
    assert len(document.edges) == 1
    assert document.edges[0].parent_agent_id == "agent-a"
    assert document.edges[0].child_agent_id == "agent-b"


def test_query_kinship_relations() -> None:
    projector = DetachedInspectionProjector()
    engine = _engine()
    assert projector.query_kinship(
        engine, agent_id=AgentId("agent-b"), relation="parents"
    ) == ("agent-a",)
    assert projector.query_kinship(
        engine, agent_id=AgentId("agent-a"), relation="children"
    ) == ("agent-b",)
    assert projector.query_kinship(
        engine,
        agent_id=AgentId("agent-b"),
        relation="ancestors",
        max_depth=2,
    ) == ("agent-a",)
