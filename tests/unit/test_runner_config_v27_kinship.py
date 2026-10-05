"""runner-config-v27 kinship encode/decode and gates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V23,
    RUNNER_SCHEMA_VERSION_V27,
    AgentCognitionSpec,
    AgentRunnerSpec,
    KinshipBootstrapEdgeSpec,
    KinshipSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_kinship_spec,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _two_agent_base():
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    agent_a = AgentId("agent-a")
    agent_b = AgentId("agent-b")
    return base_runner_config_from_scenario(
        seed=27,
        stochastic_identity="cmp-v27-kinship",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v27"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body_a, body_b),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_a,
                entity_id=body_a.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_a),
            ),
            AgentRunnerSpec(
                agent_id=agent_b,
                entity_id=body_b.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_b),
            ),
        ),
        max_ticks=2,
    )


def test_kinship_only_v27_round_trip() -> None:
    base = _two_agent_base()
    config = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V27,
        v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
        kinship=example_kinship_spec(
            parent_agent_id="agent-a",
            child_agent_id="agent-b",
        ),
    )
    round_trip = decode_runner_config(encode_runner_config(config))
    assert round_trip.schema_version == RUNNER_SCHEMA_VERSION_V27
    assert round_trip.kinship is not None
    assert len(round_trip.kinship.bootstrap_edges) == 1


def test_kinship_only_forbids_lifecycle_root() -> None:
    base = _two_agent_base()
    from simulation.runner_models import example_population_lifecycle_spec

    with pytest.raises(ValueError, match="kinship_only_forbids_lifecycle_spec"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V27,
            v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
            kinship=KinshipSpec(),
            population_lifecycle=example_population_lifecycle_spec(),
        )


def test_kinship_flag_requires_v27() -> None:
    base = _two_agent_base()
    with pytest.raises(ValueError, match="kinship_requires_v27"):
        replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V23,
            v3_capability_flags=V3CapabilityFlags(kinship_inheritance=True),
            kinship=KinshipSpec(
                bootstrap_edges=(
                    KinshipBootstrapEdgeSpec(
                        parent_agent_id=AgentId("agent-a"),
                        child_agent_id=AgentId("agent-b"),
                    ),
                )
            ),
        )
