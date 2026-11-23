"""V4 scaffolding profiles: V4 flags off, V3 regression composition, fail closed."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from agents.models import AgentId
from experiments import v3_regression_profile, v4_scaffolding_profile
from experiments.catalog import base_runner_config_from_scenario
from simulation.ecological_resources_config import (
    ECOLOGICAL_RESOURCES_POLICY_ID,
    EcologicalResourceNodeSpec,
    EcologicalResourcesSpec,
)
from simulation.models import RunId
from simulation.runner import (
    RunnerConstructionError,
    RunnerConstructionErrorCode,
    SimulationRunner,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V4,
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V58,
    RUNNER_SCHEMA_VERSION_V60,
    AgentCognitionSpec,
    AgentRunnerSpec,
    BoundedExperimentationSpec,
    CognitionTraceSpec,
    CollectiveProjectsSpec,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    WorldScenarioSpec,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)
from simulation.runner_serialization import decode_runner_config, encode_runner_config
from tests.simulation_helpers import (
    alive_body,
    make_location,
    make_resource,
    make_weather,
)
from world.environment import example_environmental_dynamics
from world.identifiers import EntityId, WorldId, WorldRevision
from world.models import default_physical_rules
from world.production import example_production_catalog
from world.supply_chain import supply_chain_production_catalog

pytestmark = pytest.mark.unit

V4_FLAG_NAMES = (
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


def _base() -> SimulationRunnerConfig:
    body = alive_body("body-1")
    agent_id = AgentId("agent-1")
    return base_runner_config_from_scenario(
        seed=11,
        stochastic_identity="cmp-v4-scaffolding-gate",
        scenario=WorldScenarioSpec(
            world_id=WorldId("world-v4-gate"),
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


def _v56_config() -> SimulationRunnerConfig:
    return replace(_base(), schema_version=RUNNER_SCHEMA_VERSION_V56)


def test_base_v4_config_passes_both_profiles_unchanged() -> None:
    config = _base()
    assert v4_scaffolding_profile(config) is config
    assert v3_regression_profile(config) is config


def test_v56_all_flags_off_passes_both_profiles_unchanged() -> None:
    config = _v56_config()
    assert v4_scaffolding_profile(config) is config
    assert v3_regression_profile(config) is config


@pytest.mark.parametrize("flag_name", V4_FLAG_NAMES)
def test_each_enabled_flag_fails_the_profile(flag_name: str) -> None:
    extras: dict[str, Any] = {
        "v4_capability_flags": V4CapabilityFlags(**{flag_name: True}),
    }
    if flag_name == "infrastructure_networks":
        extras["collective_projects"] = CollectiveProjectsSpec()
    if flag_name == "science":
        extras["capability_flags"] = V2CapabilityFlags(predictive_world_model=True)
        extras["v3_capability_flags"] = V3CapabilityFlags(
            cultural_historical_memory=True
        )
        extras["cultural_feature_provenance"] = (
            example_cultural_feature_provenance_spec()
        )
        extras["bounded_experimentation"] = BoundedExperimentationSpec(
            laws=(example_experiment_law(),)
        )
    if flag_name == "epidemics":
        from simulation.disease_config import DISEASE_POLICY_ID, DiseaseMechanicsSpec

        extras["schema_version"] = RUNNER_SCHEMA_VERSION_V58
        extras["collective_projects"] = CollectiveProjectsSpec()
        extras["v4_capability_flags"] = V4CapabilityFlags(
            infrastructure_networks=True, epidemics=True
        )
        extras["disease_mechanics"] = DiseaseMechanicsSpec(
            policy_id=DISEASE_POLICY_ID,
            initial_latent_entity_ids=(),
            exposure_chance_milli=0,
            transmission_chance_milli=0,
            symptom_chance_milli=0,
            mortality_chance_milli=0,
            latent_ticks=1,
            active_ticks=1,
            immunity_after_recovery=False,
        )
    if flag_name == "ecological_feedback":
        food = make_resource(
            "res-food",
            quantity=4.0,
            maximum_quantity=4.0,
            regeneration_per_tick=1.0,
        )
        base = _v56_config()
        catalog = supply_chain_production_catalog(example_production_catalog())
        extras["schema_version"] = RUNNER_SCHEMA_VERSION_V60
        extras["scenario"] = replace(base.scenario, resources=(food,))
        extras["environmental_dynamics"] = example_environmental_dynamics()
        extras["ecological_resources"] = EcologicalResourcesSpec(
            policy_id=ECOLOGICAL_RESOURCES_POLICY_ID,
            nodes=(
                EcologicalResourceNodeSpec(
                    resource_id=EntityId("res-food"),
                    minimum_capacity_tenths=10,
                    withdrawal_allowance_tenths=0,
                    recovery_tenths_per_idle_tick=5,
                ),
            ),
        )
        extras["v4_capability_flags"] = V4CapabilityFlags(
            supply_chains=True,
            ecological_feedback=True,
        )
        extras["agents"] = tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in base.agents
        )
    config = replace(_v56_config(), **extras)
    decoded = decode_runner_config(encode_runner_config(config))
    assert getattr(decoded.v4_capability_flags, flag_name) is True

    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v3_regression_profile(config)


def test_v4_flag_on_a_v4_config_fails_before_the_profile() -> None:
    with pytest.raises(ValueError, match="code=v4_capability_requires_v56"):
        replace(_base(), v4_capability_flags=V4CapabilityFlags(science=True))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name",
    tuple(
        name
        for name in V4_FLAG_NAMES
        if name
        not in {
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
        }
    ),
)
async def test_each_unowned_enabled_flag_fails_closed_at_construction(
    flag_name: str,
) -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    with pytest.raises(RunnerConstructionError) as excinfo:
        await SimulationRunner.from_config(
            config, run_id=RunId(f"run-v4-profile-{flag_name}")
        )
    assert excinfo.value.code is RunnerConstructionErrorCode.CAPABILITY_UNIMPLEMENTED
    assert excinfo.value.stage == "v4_capability_flags"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag_name",
    (
        "organizations",
        "formal_rules",
        "legal_disputes",
        "diplomacy",
        "markets_credit",
    ),
)
async def test_owned_v4_flag_constructs_but_stays_scaffolding_off(
    flag_name: str,
) -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(**{flag_name: True}),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)

    runner = await SimulationRunner.from_config(
        config, run_id=RunId(f"run-v4-profile-{flag_name}")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == (flag_name,)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()


def test_v3_regression_profile_keeps_v1_rules() -> None:
    invalid = replace(_base(), cognition_trace=CognitionTraceSpec(enabled=True))
    assert invalid.schema_version == RUNNER_SCHEMA_VERSION_V4
    with pytest.raises(ValueError, match="code=v1_regression_trace_enabled"):
        v3_regression_profile(invalid)


@pytest.mark.asyncio
async def test_science_constructs_with_prerequisites() -> None:
    catalog = example_production_catalog()
    config = replace(
        _v56_config(),
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=BoundedExperimentationSpec(
            laws=(example_experiment_law(),)
        ),
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    config = replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
            for agent in config.agents
        ),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-profile-science")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == ("science",)
    assert runner.config.v4_capability_flags.unimplemented_enabled_names() == ()


@pytest.mark.asyncio
async def test_organized_conflict_constructs_with_diplomacy() -> None:
    config = replace(
        _v56_config(),
        v4_capability_flags=V4CapabilityFlags(
            diplomacy=True, organized_conflict=True
        ),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-profile-organized-conflict")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == (
        "diplomacy",
        "organized_conflict",
    )


@pytest.mark.asyncio
async def test_infrastructure_networks_constructs_with_collective_projects() -> None:
    config = replace(
        _v56_config(),
        collective_projects=CollectiveProjectsSpec(),
        v4_capability_flags=V4CapabilityFlags(infrastructure_networks=True),
    )
    with pytest.raises(ValueError, match="code=v4_scaffolding_flags_enabled"):
        v4_scaffolding_profile(config)
    runner = await SimulationRunner.from_config(
        config, run_id=RunId("run-v4-profile-infrastructure-networks")
    )
    assert runner.config.v4_capability_flags.owned_enabled_names() == (
        "infrastructure_networks",
    )
    assert runner.config.collective_projects is not None
