"""Twin-run determinism with kinship channel on."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    KinshipBootstrapEdgeSpec,
    KinshipSpec,
    MortalityMode,
    V3CapabilityFlags,
    WorldScenarioSpec,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.kinship import parents_of, siblings_of
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.kinship_replay_determinism")


def _config(*, seed: int):
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    body_c = alive_body("body-c")
    return replace(
        base_runner_config_from_scenario(
            seed=seed,
            stochastic_identity=f"cmp-kinship-det-{seed}",
            scenario=WorldScenarioSpec(
                world_id=WorldId(f"world-kinship-det-{seed}"),
                revision=WorldRevision(0),
                physical_rules=non_lethal_physical_rules(),
                locations=(make_location(body_capacity=8),),
                bodies=(body_a, body_b, body_c),
                weather=(make_weather(),),
            ),
            agents=(
                AgentRunnerSpec(
                    agent_id=AgentId("agent-a"),
                    entity_id=body_a.entity_id,
                    cognition=AgentCognitionSpec(agent_id=AgentId("agent-a")),
                ),
                AgentRunnerSpec(
                    agent_id=AgentId("agent-b"),
                    entity_id=body_b.entity_id,
                    cognition=AgentCognitionSpec(agent_id=AgentId("agent-b")),
                ),
                AgentRunnerSpec(
                    agent_id=AgentId("agent-c"),
                    entity_id=body_c.entity_id,
                    cognition=AgentCognitionSpec(agent_id=AgentId("agent-c")),
                ),
            ),
            max_ticks=4,
        ),
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        kinship=KinshipSpec(
            bootstrap_edges=(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=AgentId("agent-a"),
                    child_agent_id=AgentId("agent-b"),
                ),
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=AgentId("agent-a"),
                    child_agent_id=AgentId("agent-c"),
                ),
            )
        ),
    )


def _graph_fingerprint(engine) -> tuple:
    graph = engine.kinship_graph
    return (
        parents_of(graph, AgentId("agent-b")),
        parents_of(graph, AgentId("agent-c")),
        siblings_of(graph, AgentId("agent-b")),
        tuple(sorted(edge.edge_id for edge in graph.edges)),
    )


@pytest.mark.asyncio
async def test_same_seed_twin_runs_share_kinship_graph() -> None:
    _LOG.debug("case_id=kinship_twin_determinism")
    config = _config(seed=88)
    fingerprints: list[tuple] = []
    for index in range(2):
        runner = await SimulationRunner.from_config(
            config, run_id=RunId(f"run-kinship-twin-{index}")
        )
        for _ in range(3):
            await runner.run_tick()
        fingerprints.append(_graph_fingerprint(runner.engine))
    assert fingerprints[0] == fingerprints[1]
    assert fingerprints[0][2] == (AgentId("agent-c"),)
