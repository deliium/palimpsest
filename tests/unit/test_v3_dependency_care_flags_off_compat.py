"""Flags-off / channel-off dependency-care must leave AE-AH baselines intact."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from agents.models import AgentId
from experiments.catalog import (
    base_runner_config_from_scenario,
    experiment_ae_generational_population,
    experiment_ah_kinship_genealogy,
    v3_scaffolding_profile,
)
from simulation.models import RunId
from simulation.new_agent_initialization import default_new_agent_initialization_spec
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V27,
    RUNNER_SCHEMA_VERSION_V28,
    AgentCognitionSpec,
    AgentRunnerSpec,
    MortalityMode,
    RunnerStopPolicy,
    V3CapabilityFlags,
    WorldScenarioSpec,
    example_dependency_care_spec,
    example_population_lifecycle_spec,
)
from simulation.runner_serialization import (
    build_runner_result_document,
    decode_runner_config,
    encode_runner_config,
)
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.v3_dependency_care_flags_off_compat")


def _base(*, max_ticks: int = 3, agents: int = 2):
    bodies = tuple(alive_body(f"body-{index}") for index in range(agents))
    specs = tuple(
        AgentRunnerSpec(
            agent_id=AgentId(f"agent-{index}"),
            entity_id=body.entity_id,
            cognition=AgentCognitionSpec(agent_id=AgentId(f"agent-{index}")),
        )
        for index, body in enumerate(bodies)
    )
    return base_runner_config_from_scenario(
        seed=48,
        stochastic_identity="cmp-v3-dep-care-flags-off",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v3-dep-care-off"),
            revision=WorldRevision(0),
            physical_rules=non_lethal_physical_rules(),
            locations=(make_location(body_capacity=8),),
            bodies=bodies,
            weather=(make_weather(),),
        ),
        agents=specs,
        max_ticks=max_ticks,
    )


@pytest.mark.asyncio
async def test_flags_off_v4_and_v28_absent_share_trajectory_hash() -> None:
    _LOG.info("case_id=flags_off_dep_care_traj_hash")
    base = replace(
        _base(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
    )
    v4 = replace(base, schema_version=RUNNER_SCHEMA_VERSION_V4)
    v28_off = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V4,
        v3_capability_flags=V3CapabilityFlags(),
        dependency_care=None,
        population_lifecycle=None,
    )
    v3_scaffolding_profile(v4)
    v3_scaffolding_profile(v28_off)

    run_id = RunId("run-dep-care-off-shared")
    async with await SimulationRunner.from_config(v4, run_id=run_id) as runner:
        result_v4 = await runner.run()
        assert runner.engine.dependency_care_channel_active is False
    async with await SimulationRunner.from_config(v28_off, run_id=run_id) as runner:
        result_off = await runner.run()
        assert runner.engine.dependency_care_channel_active is False

    doc_v4 = build_runner_result_document(result=result_v4, config=v4)
    doc_off = build_runner_result_document(result=result_off, config=v28_off)
    _LOG.info(
        "case_id=flags_off_dep_care_traj_hash hash_prefix=%s",
        doc_v4.exact_trajectory_hash[:12],
    )
    assert doc_v4.exact_trajectory_hash == doc_off.exact_trajectory_hash


@pytest.mark.asyncio
async def test_lifecycle_on_without_dependency_care_matches_baseline() -> None:
    """AE-style lifecycle without dependency_care stays channel-off for care."""
    base = replace(
        _base(max_ticks=3),
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=3),
        schema_version=RUNNER_SCHEMA_VERSION_V24,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40, max_population=4
        ),
        dependency_care=None,
    )
    run_id = RunId("run-lifecycle-no-dep-care")
    async with await SimulationRunner.from_config(base, run_id=run_id) as runner:
        assert runner.engine.lifecycle_channel_active is True
        assert runner.engine.dependency_care_channel_active is False
        await runner.run()


def test_ae_ah_schemas_unchanged_when_dependency_care_absent() -> None:
    ae = experiment_ae_generational_population(_base(agents=2), max_ticks=4)
    assert ae.experiment_id == "experiment-ae-generational-population"
    on = next(
        item
        for item in ae.conditions
        if item.condition_id == "ae-generational-on"
    ).runner_config
    assert on.schema_version == RUNNER_SCHEMA_VERSION_V24
    assert on.dependency_care is None

    ah = experiment_ah_kinship_genealogy(_base(agents=3), max_ticks=4)
    assert ah.experiment_id == "experiment-ah-kinship-genealogy"
    kinship_only = next(
        item
        for item in ah.conditions
        if item.condition_id == "ah-kinship-only-none"
    ).runner_config
    assert kinship_only.schema_version == RUNNER_SCHEMA_VERSION_V27
    assert kinship_only.dependency_care is None


def test_v28_dependency_care_round_trip() -> None:
    config = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(generational_population=True),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
    )
    restored = decode_runner_config(encode_runner_config(config))
    assert restored.schema_version == RUNNER_SCHEMA_VERSION_V28
    assert restored.dependency_care is not None
    assert (
        restored.dependency_care.enabled_needs
        == config.dependency_care.enabled_needs
    )


def test_dependency_care_without_lifecycle_flag_rejected() -> None:
    with pytest.raises(ValueError, match="dependency_care_without_lifecycle_flag"):
        replace(
            _base(),
            schema_version=RUNNER_SCHEMA_VERSION_V28,
            v3_capability_flags=V3CapabilityFlags(),
            new_agent_initialization=default_new_agent_initialization_spec(),
            dependency_care=example_dependency_care_spec(),
        )


@pytest.mark.asyncio
async def test_unowned_v3_flags_still_fail_closed() -> None:
    base = replace(
        _base(),
        schema_version=RUNNER_SCHEMA_VERSION_V28,
        mortality_mode=MortalityMode.DISABLED,
        v3_capability_flags=V3CapabilityFlags(
            generational_population=True,
            multi_polity_migration=True,
        ),
        population_lifecycle=example_population_lifecycle_spec(),
        new_agent_initialization=default_new_agent_initialization_spec(),
        dependency_care=example_dependency_care_spec(),
    )
    with pytest.raises(Exception) as exc_info:
        await SimulationRunner.from_config(base, run_id=RunId("run-unowned-dep"))
    message = str(exc_info.value).lower()
    assert "capability_unimplemented" in message or "unimplemented" in message
