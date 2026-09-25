"""V2 capability flag defaults for catalog and reference scenario builders."""

from __future__ import annotations

import logging

import pytest

from agents.models import AgentId
from experiments import v1_regression_profile
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_a_memory,
    experiment_b_imagination,
    experiment_c_mortality,
    experiment_d_drives,
    experiment_e_false_story,
)
from experiments.reference_scenario import build_reference_scenario
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    AgentCognitionSpec,
    AgentRunnerSpec,
    CognitionTraceSpec,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    WorldScenarioSpec,
)
from simulation.runner_serialization import (
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=3,
        stochastic_identity="cmp-flag-defaults",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-1"),
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
                name=agent_id.value,
                initial_goals=(),
            ),
        ),
        max_ticks=2,
    )


@pytest.mark.parametrize(
    "builder",
    (
        experiment_a_memory,
        experiment_b_imagination,
        experiment_c_mortality,
        experiment_d_drives,
        experiment_e_false_story,
    ),
)
def test_catalog_conditions_default_off_flags(builder: object) -> None:
    definition = builder(_base())  # type: ignore[operator]
    assert definition.schema_version == "experiment-definition-v1"
    for condition in definition.conditions:
        config = condition.runner_config
        assert config.schema_version == RUNNER_SCHEMA_VERSION_V4
        assert config.capability_flags == V2CapabilityFlags()
        assert config.cognition_trace == CognitionTraceSpec()
        assert v1_regression_profile(config) is config
        decoded = decode_runner_config(encode_runner_config(config))
        assert decoded.capability_flags == V2CapabilityFlags()
        assert decoded.cognition_trace == CognitionTraceSpec()


def test_reference_scenario_default_off_flags(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="experiments.reference_scenario"):
        bundle = build_reference_scenario(
            seed=7, stochastic_identity="cmp-ref-flags", max_ticks=48
        )
    assert bundle.config.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert bundle.config.capability_flags == V2CapabilityFlags()
    assert bundle.config.cognition_trace == CognitionTraceSpec()
    assert v1_regression_profile(bundle.config) is bundle.config


def test_extended_self_model_is_owned_and_default_documents_stay_v4() -> None:
    base = _base()
    assert base.schema_version == RUNNER_SCHEMA_VERSION_V4
    assert base.capability_flags == V2CapabilityFlags()
    assert base.capability_flags.extended_self_model is False
    owned = V2CapabilityFlags(extended_self_model=True)
    assert owned.unimplemented_enabled_names() == ()
    assert owned.owned_enabled_names() == ("extended_self_model",)
    unowned = V2CapabilityFlags(advanced_social_inference=True)
    assert unowned.unimplemented_enabled_names() == ("advanced_social_inference",)
    base = _base()
    enabled = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        capability_flags=V2CapabilityFlags(extended_self_model=True),
    )
    with pytest.raises(ValueError, match="v1_regression_flags_enabled"):
        v1_regression_profile(enabled)


def test_v1_regression_profile_rejects_enabled_tracing() -> None:
    base = _base()
    enabled = SimulationRunnerConfig(
        seed=base.seed,
        stochastic_identity=base.stochastic_identity,
        scenario=base.scenario,
        agents=base.agents,
        stop_policy=base.stop_policy,
        cognition_trace=CognitionTraceSpec(enabled=True),
    )
    with pytest.raises(ValueError, match="v1_regression_trace_enabled"):
        v1_regression_profile(enabled)
