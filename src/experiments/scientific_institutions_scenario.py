"""Off-gate ``scientific_institutions@1`` experiment (four declared arms)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    RUNNER_SCHEMA_VERSION_V57,
    CollectiveProjectsSpec,
    CommunicationStrategyMode,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
)

__all__ = [
    "SCIENTIFIC_INSTITUTIONS_EXPERIMENT_ID",
    "scientific_institutions_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_institutions_scenario"
)

SCIENTIFIC_INSTITUTIONS_EXPERIMENT_ID: Final[str] = "scientific_institutions@1"
_MIN_TICKS: Final[int] = 96


def _combined(
    base: SimulationRunnerConfig, *, max_ticks: int
) -> SimulationRunnerConfig:
    from experiments.scientific_models_scenario import scientific_models_scenario

    definition = scientific_models_scenario(base, max_ticks=max_ticks)
    shared = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "models-production"
    )
    flags = replace(
        shared.v4_capability_flags,
        organizations=True,
        science=True,
    )
    return replace(
        shared,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        v4_capability_flags=flags,
        collective_projects=CollectiveProjectsSpec(idle_ticks=64),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DETERMINISTIC
                    ),
                    teaching_interaction_mode=(
                        TeachingInteractionMode.DETERMINISTIC
                    ),
                    skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                ),
            )
            for agent in shared.agents
        ),
    )


def _instrumented(
    base: SimulationRunnerConfig,
    shared: SimulationRunnerConfig,
    *,
    max_ticks: int,
) -> SimulationRunnerConfig:
    from experiments.measurement_scenario import measurement_instruments_scenario

    definition = measurement_instruments_scenario(
        base, max_ticks=max_ticks
    )
    instrumented = next(
        row.runner_config
        for row in definition.conditions
        if row.condition_id == "measurement-unbiased"
    )
    return replace(
        shared,
        schema_version=RUNNER_SCHEMA_VERSION_V57,
        measurement_instruments=instrumented.measurement_instruments,
    )


def scientific_institutions_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = _MIN_TICKS,
) -> ExperimentDefinition:
    """Compose existing science, organization, record and archive channels."""

    if max_ticks < _MIN_TICKS:
        _LOG.warning(
            "scientific_institutions_scenario_invalid reason_code=min_ticks"
        )
        raise ValueError("scientific_institutions_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    shared = _combined(base, max_ticks=max_ticks)
    if shared.new_agent_initialization is not None:
        shared = replace(shared, new_agent_initialization=None)
    org_off = replace(
        shared,
        v4_capability_flags=replace(
            shared.v4_capability_flags, organizations=False
        ),
    )
    science_off = replace(
        shared,
        v4_capability_flags=replace(
            shared.v4_capability_flags, science=False
        ),
    )
    instruments = _instrumented(base, shared, max_ticks=max_ticks)
    conditions = (
        ExperimentCondition(
            condition_id="institutions-combined-v56",
            label_code="scientific_institutions_combined",
            runner_config=shared,
        ),
        ExperimentCondition(
            condition_id="institutions-org-off",
            label_code="scientific_institutions_org_off",
            runner_config=org_off,
        ),
        ExperimentCondition(
            condition_id="institutions-science-off",
            label_code="scientific_institutions_science_off",
            runner_config=science_off,
        ),
        ExperimentCondition(
            condition_id="institutions-instruments-v57",
            label_code="scientific_institutions_instruments",
            runner_config=instruments,
        ),
    )
    _LOG.info(
        "scientific_institutions_scenario_built arms=%s max_ticks=%s",
        len(conditions),
        max_ticks,
    )
    return ExperimentDefinition(
        experiment_id=SCIENTIFIC_INSTITUTIONS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group="scientific-institutions-paired-v1",
    )
