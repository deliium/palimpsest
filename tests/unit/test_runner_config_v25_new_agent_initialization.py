"""runner-config-v25 new_agent_initialization encode/decode and schema gates."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.new_agent_initialization import (
    ObjectiveInheritancePolicy,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    AgentCognitionSpec,
    AgentRunnerSpec,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
    runner_config_fingerprint,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

_LOG = logging.getLogger("tests.runner_config_v25_new_agent_initialization")


def _base():
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=25,
        stochastic_identity="cmp-v25-init",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v25"),
            revision=WorldRevision(0),
            physical_rules=default_physical_rules(),
            locations=(make_location(),),
            bodies=(body,),
            weather=(make_weather(),),
        ),
        agents=(
            AgentRunnerSpec(
                agent_id=agent_id,
                entity_id=body.entity_id,
                cognition=AgentCognitionSpec(agent_id=agent_id),
            ),
        ),
        max_ticks=2,
    )


def test_default_write_stays_v4_when_v3_flags_off() -> None:
    _LOG.debug("case_id=default_write_v4")
    config = _base()
    assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert config.new_agent_initialization is None


def test_all_off_v25_round_trip() -> None:
    _LOG.debug("case_id=all_off_v25_round_trip")
    init = default_new_agent_initialization_spec()
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=init,
        v3_capability_flags=V3CapabilityFlags(),
    )
    encoded = encode_runner_config(config)
    decoded = decode_runner_config(encoded)
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V25
    assert decoded.new_agent_initialization is not None
    assert (
        decoded.new_agent_initialization.canonical_payload()
        == init.canonical_payload()
    )
    assert runner_config_fingerprint(decoded) == runner_config_fingerprint(config)


def test_v24_decode_synthesizes_default_init() -> None:
    _LOG.debug("case_id=v24_decode_synthesizes_default_init")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=example_population_lifecycle_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    assert config.new_agent_initialization is None
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.schema_version == RUNNER_SCHEMA_VERSION_V24
    assert decoded.new_agent_initialization is not None
    assert (
        decoded.new_agent_initialization.canonical_payload()
        == default_new_agent_initialization_spec().canonical_payload()
    )


def test_generational_population_accepts_v25() -> None:
    _LOG.debug("case_id=generational_accepts_v25")
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V25,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
    )
    assert config.v3_capability_flags.generational_population is True


def test_v25_requires_new_agent_initialization() -> None:
    _LOG.debug("case_id=v25_requires_init")
    with pytest.raises(ValueError, match="v25_requires_new_agent_initialization"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V25,
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=None,
        )


def test_non_default_init_requires_v25() -> None:
    _LOG.debug("case_id=non_default_init_requires_v25")
    non_default = replace(
        default_new_agent_initialization_spec(),
        objective_inheritance=ObjectiveInheritancePolicy(
            allowed_keys=("carry_capacity",)
        ),
    )
    with pytest.raises(ValueError, match="new_agent_initialization_requires_v25"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V24,
            population_lifecycle=example_population_lifecycle_spec(),
            new_agent_initialization=non_default,
            v3_capability_flags=V3CapabilityFlags(generational_population=True),
        )


def test_v25_encode_omits_init_from_v24_wire() -> None:
    _LOG.debug("case_id=v24_wire_omits_init_key")
    import json

    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        population_lifecycle=example_population_lifecycle_spec(),
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
    )
    document = json.loads(encode_runner_config(config).decode("utf-8"))
    assert "new_agent_initialization" not in document
    assert "population_lifecycle" in document
