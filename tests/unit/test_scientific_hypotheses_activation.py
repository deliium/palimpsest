# mypy: ignore-errors
"""Science capability ownership and fail-closed activation matrix (V4-27)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import base_runner_config_from_scenario
from simulation.compatibility import V4_OWNED_CAPABILITY_FLAGS
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    SUPPORTED_RUNNER_SCHEMA_VERSIONS,
    AgentCognitionSpec,
    AgentRunnerSpec,
    BoundedExperimentationSpec,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog

pytestmark = pytest.mark.unit


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-scientific-hypotheses",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-scientific-hypotheses"),
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


def _bounded_spec() -> BoundedExperimentationSpec:
    return BoundedExperimentationSpec(laws=(example_experiment_law(),))


def _with_catalog(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    catalog = example_production_catalog()
    agents = tuple(
        replace(
            agent,
            cognition=replace(agent.cognition, production_catalog=catalog),
        )
        for agent in config.agents
    )
    return replace(config, agents=agents)


def _science_ready() -> SimulationRunnerConfig:
    return _with_catalog(
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            capability_flags=V2CapabilityFlags(predictive_world_model=True),
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            bounded_experimentation=_bounded_spec(),
            v4_capability_flags=V4CapabilityFlags(science=True),
        )
    )


@pytest.mark.asyncio
async def test_science_validates_with_both_prerequisites() -> None:
    config = _science_ready()
    decoded = decode_runner_config(encode_runner_config(config))
    assert decoded.v4_capability_flags.science is True
    assert decoded.capability_flags.predictive_world_model is True
    assert decoded.bounded_experimentation is not None

    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-science-ready")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == ("science",)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()


def test_science_requires_bounded_experimentation() -> None:
    with pytest.raises(
        ValueError, match="code=science_requires_bounded_experimentation"
    ):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            capability_flags=V2CapabilityFlags(predictive_world_model=True),
            v4_capability_flags=V4CapabilityFlags(science=True),
        )


def test_science_requires_predictive_world_model() -> None:
    with pytest.raises(
        ValueError, match="code=science_requires_predictive_world_model"
    ):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
            cultural_feature_provenance=example_cultural_feature_provenance_spec(),
            bounded_experimentation=_bounded_spec(),
            v4_capability_flags=V4CapabilityFlags(science=True),
        )


@pytest.mark.parametrize(
    "schema_version",
    (RUNNER_SCHEMA_VERSION_V4, "runner-config-v55"),
)
def test_science_requires_v56(schema_version: str) -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(
            _base(),
            schema_version=schema_version,
            capability_flags=V2CapabilityFlags(predictive_world_model=True),
            bounded_experimentation=_bounded_spec(),
            v4_capability_flags=V4CapabilityFlags(science=True),
        )


def test_science_is_owned_and_three_flags_remain_unowned() -> None:
    assert "science" in V4_OWNED_CAPABILITY_FLAGS
    unowned = {
        name
        for name in (
            "organizations",
            "formal_rules",
            "legal_disputes",
            "diplomacy",
            "organized_conflict",
            "infrastructure_networks",
            "supply_chains",
            "markets_credit",
            "science",
            "epidemics",
            "ecological_feedback",
            "disasters",
        )
        if name not in V4_OWNED_CAPABILITY_FLAGS
    }
    assert unowned == {"epidemics", "ecological_feedback", "disasters"}


def test_science_off_is_byte_identical() -> None:
    base = _base()
    explicit_off = replace(base, v4_capability_flags=V4CapabilityFlags())
    assert encode_runner_config(base) == encode_runner_config(explicit_off)
    assert V4CapabilityFlags(science=False) == V4CapabilityFlags()


def test_runner_config_v57_is_absent() -> None:
    assert "runner-config-v58" not in SUPPORTED_RUNNER_SCHEMA_VERSIONS
