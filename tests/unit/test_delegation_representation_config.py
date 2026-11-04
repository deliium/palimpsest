"""V4-09 representation seam: organizations ownership and cognition mode."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    REPRESENTATION_POLICY_VERSION,
    RepresentationPolicy,
    default_representation_policy,
)
from agents.cognition.configuration import (
    CognitionLoopConfig,
    CognitionRepresentationMode,
    build_cognitive_loop,
)
from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.runner import _cognition_config_for
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V55,
    RUNNER_SCHEMA_VERSION_V56,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import encode_runner_config
from simulation.v4_architecture import V4_CAPABILITY_FLAGS
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-representation-config",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-representation"),
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


def _config(**flags: bool) -> SimulationRunnerConfig:
    return replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(**flags),
    )


@pytest.mark.parametrize(
    "schema_version",
    (RUNNER_SCHEMA_VERSION_V4, RUNNER_SCHEMA_VERSION_V55),
)
def test_organizations_requires_v56_on_older_schemas(schema_version: str) -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            _base(),
            schema_version=schema_version,
            v4_capability_flags=V4CapabilityFlags(organizations=True),
        )


def test_no_representation_runner_key() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    assert not hasattr(spec, "representation_mode")
    assert not hasattr(spec, "representation_policy")
    assert "representation_mode" not in SimulationRunnerConfig.__dataclass_fields__
    assert "representation_policy" not in SimulationRunnerConfig.__dataclass_fields__


def test_disabled_representation_mode_allocates_nothing() -> None:
    config = CognitionLoopConfig()
    assert config.representation_mode is CognitionRepresentationMode.DISABLED
    assert config.representation_policy is None
    assert "representation_mode" not in config.condition_fingerprint_material()

    loop = build_cognitive_loop(config)
    assert loop._representation_mode is CognitionRepresentationMode.DISABLED
    assert loop._representation_policy is None
    assert loop._prepared_representation is None


def test_deterministic_representation_mode_installs_locked_policy() -> None:
    config = CognitionLoopConfig(
        representation_mode=CognitionRepresentationMode.DETERMINISTIC
    )
    assert config.representation_policy is not None
    assert config.representation_policy == default_representation_policy()

    loop = build_cognitive_loop(config)
    assert loop._representation_mode is CognitionRepresentationMode.DETERMINISTIC
    assert type(loop._representation_policy) is RepresentationPolicy
    assert loop._prepared_representation is None


def test_disabled_mode_clears_policy_and_rejects_foreign_types() -> None:
    config = CognitionLoopConfig(
        representation_mode=CognitionRepresentationMode.DISABLED,
        representation_policy=default_representation_policy(),
    )
    assert config.representation_policy is None

    with pytest.raises(TypeError, match="representation_mode"):
        CognitionLoopConfig(representation_mode="deterministic")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="representation_policy"):
        CognitionLoopConfig(
            representation_mode=CognitionRepresentationMode.DETERMINISTIC,
            representation_policy=object(),  # type: ignore[arg-type]
        )


def test_fingerprint_material_is_additive_and_disabled_stable() -> None:
    disabled = CognitionLoopConfig().condition_fingerprint_material()
    assert "representation_mode" not in disabled
    assert "representation_policy_version" not in disabled
    assert CognitionLoopConfig().condition_fingerprint_material() == disabled

    deterministic = CognitionLoopConfig(
        representation_mode=CognitionRepresentationMode.DETERMINISTIC
    ).condition_fingerprint_material()
    assert deterministic["representation_mode"] == "deterministic"
    assert deterministic["representation_policy_version"] == (
        REPRESENTATION_POLICY_VERSION
    )


def test_organizations_flag_derives_deterministic_representation_mode() -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))

    disabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=False,
    )
    assert disabled.representation_mode is CognitionRepresentationMode.DISABLED
    assert disabled.representation_policy is None

    enabled = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=True,
    )
    assert enabled.representation_mode is CognitionRepresentationMode.DETERMINISTIC
    assert enabled.representation_policy == default_representation_policy()


@pytest.mark.parametrize("flag_name", sorted(V4_CAPABILITY_FLAGS))
def test_only_organizations_activates_representation(flag_name: str) -> None:
    spec = AgentCognitionSpec(agent_id=AgentId("agent-1"))
    config = _cognition_config_for(
        spec,
        mortality_mode=MortalityMode.DISABLED,
        capability_flags=V2CapabilityFlags(),
        organizations_enabled=flag_name == "organizations",
        formal_rules_enabled=flag_name == "formal_rules",
        legal_disputes_enabled=flag_name == "legal_disputes",
    )
    expected = (
        CognitionRepresentationMode.DETERMINISTIC
        if flag_name == "organizations"
        else CognitionRepresentationMode.DISABLED
    )
    assert config.representation_mode is expected


def test_runner_serialization_gains_no_representation_key() -> None:
    encoded = encode_runner_config(_config(organizations=True)).decode("utf-8")

    assert "representation_mode" not in encoded
    assert "representation_policy" not in encoded
