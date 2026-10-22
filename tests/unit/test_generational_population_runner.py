"""Generational interval entry through atomic tick admission."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.models import DriveKind
from experiments.institutionalization_scenario import institutionalization_scenario
from simulation.generational_models import GenerationalRunSpec
from simulation.new_agent_initialization import (
    ParameterDistributionSpec,
    creation_config_fingerprint,
    default_new_agent_initialization_spec,
)
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V24,
    RUNNER_SCHEMA_VERSION_V25,
    RUNNER_SCHEMA_VERSION_V35,
    RUNNER_SCHEMA_VERSION_V36,
    RUNNER_SCHEMA_VERSION_V44,
    RUNNER_SCHEMA_VERSION_V54,
    RUNNER_SCHEMA_VERSION_V55,
    CollectiveDecisionMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    LifecycleStageId,
    LifecycleStageThreshold,
    MediationMode,
    OfficeSuccessionMode,
    PopulationLifecycleSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    schema_supports_explicit_new_agent_initialization,
)
from world.events import AgentInitializationRecorded


def _init_spec():
    return replace(
        default_new_agent_initialization_spec(),
        parameter_distributions=ParameterDistributionSpec(
            distribution_id="uniform_drive_delta",
            params={
                "drive_kind": DriveKind.CURIOSITY.value,
                "min_delta": 0.1,
                "max_delta": 0.2,
            },
        ),
    )


def _lifecycle() -> PopulationLifecycleSpec:
    return PopulationLifecycleSpec(
        lifespan_ticks=30,
        stage_thresholds=(
            LifecycleStageThreshold(LifecycleStageId("infant"), 2),
            LifecycleStageThreshold(LifecycleStageId("juvenile"), 5),
            LifecycleStageThreshold(LifecycleStageId("adult"), 29),
        ),
        dependent_until_stage=LifecycleStageId("juvenile"),
        demographic_policy_id="generational_interval_entry",
        demographic_policy_params={
            "interval_ticks": 2,
            "entries_per_interval": 1,
            "generation_length_ticks": 4,
            "name_prefix": "entrant",
            "cohort_id_prefix": "cohort",
            "spawn_location_ids": ["loc-clearing"],
        },
        max_population=8,
        natural_death_on_lifespan=True,
    )


def _v55_config() -> SimulationRunnerConfig:
    definition = institutionalization_scenario(seed=23, max_ticks=6)
    config = next(
        condition.runner_config
        for condition in definition.conditions
        if condition.condition_id == "bf-institution-on"
    )
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                institution_concept_mode=InstitutionConceptMode.DISABLED,
                office_succession_mode=OfficeSuccessionMode.DISABLED,
                institutional_memory_mode=InstitutionalMemoryMode.DISABLED,
                institutional_decay_mode=InstitutionalDecayMode.DISABLED,
                collective_decision_mode=CollectiveDecisionMode.DISABLED,
                mediation_mode=MediationMode.DISABLED,
            ),
        )
        for agent in config.agents
    )
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V55,
        agents=agents,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        mentorship=None,
        developmental_learning=None,
        dependency_care=None,
        kinship=None,
        cultural_feature_provenance=None,
        collective_projects=None,
        public_goods=None,
        structured_commitments=None,
        subjective_valuation=None,
        resource_exchange_profile=None,
        generational_narratives=None,
        stop_policy=RunnerStopPolicy(
            max_ticks=6, stop_on_all_agents_terminal=False
        ),
        generational_run=GenerationalRunSpec(max_generation_index=2),
        population_lifecycle=_lifecycle(),
        new_agent_initialization=_init_spec(),
    )


def test_explicit_initialization_versions_cover_current_families() -> None:
    for schema_version in (
        RUNNER_SCHEMA_VERSION_V25,
        RUNNER_SCHEMA_VERSION_V35,
        RUNNER_SCHEMA_VERSION_V36,
        RUNNER_SCHEMA_VERSION_V44,
        RUNNER_SCHEMA_VERSION_V54,
        RUNNER_SCHEMA_VERSION_V55,
    ):
        assert schema_supports_explicit_new_agent_initialization(schema_version)
    assert not schema_supports_explicit_new_agent_initialization(
        RUNNER_SCHEMA_VERSION_V24
    )


@pytest.mark.asyncio
async def test_entrant_uses_forwarded_initialization_and_acts_next_tick() -> None:
    config = _v55_config()
    runner = await SimulationRunner.from_config(config)
    try:
        initial_runtime_count = len(runner._runtimes)
        for _ in range(3):
            await runner.run_tick()
        tick_result = runner._engine.last_tick_result
        assert tick_result is not None
        events = [
            record.event
            for record in tick_result.events
            if type(record.event.details) is AgentInitializationRecorded
        ]
        assert events
        expected = creation_config_fingerprint(
            config.new_agent_initialization,
            demographic_policy_id="generational_interval_entry",
        )
        details = events[0].details
        assert details.creation_config_id == expected
        assert details.creation_reason == "demographic_policy"
        assert details.initial_conditions["location_id"] == "loc-clearing"
        # Entrants are bound after the admitting tick and act on the next one.
        assert len(runner._runtimes) == initial_runtime_count + 1
        tick_value = runner._engine.tick.value
        await runner.run_tick()
        assert runner._engine.tick.value == tick_value + 1
    finally:
        await runner.aclose()
