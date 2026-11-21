"""Off-gate ``science_diffusion@1`` experiment (paired science arms)."""

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
    RUNNER_SCHEMA_VERSION_V57,
    ArtifactInterpretationMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_knowledge_genealogy_spec,
)

__all__ = [
    "SCIENCE_DIFFUSION_EXPERIMENT_ID",
    "science_diffusion_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_scenario"
)

SCIENCE_DIFFUSION_EXPERIMENT_ID: Final[str] = "science_diffusion@1"
_MIN_TICKS: Final[int] = 128


def science_diffusion_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = _MIN_TICKS,
) -> ExperimentDefinition:
    """Compose V4-32 science/records with V3 genealogy and teaching."""

    if max_ticks < _MIN_TICKS:
        _LOG.warning("science_diffusion_scenario_invalid reason_code=min_ticks")
        raise ValueError("science_diffusion_min_ticks")
    from experiments.measurement_scenario import measurement_instruments_scenario
    from experiments.scientific_institutions_scenario import (
        scientific_institutions_scenario,
    )

    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    institutions = scientific_institutions_scenario(base, max_ticks=max_ticks)
    shared = next(
        row.runner_config
        for row in institutions.conditions
        if row.condition_id == "institutions-combined-v56"
    )
    genealogy = example_knowledge_genealogy_spec(teaching=True)
    genealogy = replace(
        genealogy,
        uptake_compose=replace(
            genealogy.uptake_compose,
            written_record=True,
        ),
    )
    shared = replace(
        shared,
        v3_capability_flags=replace(
            shared.v3_capability_flags, cultural_historical_memory=True
        ),
        knowledge_genealogy=genealogy,
        artifacts_enabled=True,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    artifact_interpretation_mode=(
                        ArtifactInterpretationMode.DETERMINISTIC
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
    science_off = replace(
        shared,
        v4_capability_flags=replace(
            shared.v4_capability_flags, science=False
        ),
    )
    instrumented = measurement_instruments_scenario(base, max_ticks=max_ticks)
    instruments = next(
        row.runner_config
        for row in instrumented.conditions
        if row.condition_id == "measurement-unbiased"
    )
    instruments = replace(
        shared,
        schema_version=RUNNER_SCHEMA_VERSION_V57,
        measurement_instruments=instruments.measurement_instruments,
    )
    conditions = (
        ExperimentCondition(
            condition_id="diffusion-science",
            label_code="science_diffusion_science",
            runner_config=shared,
        ),
        ExperimentCondition(
            condition_id="diffusion-science-off",
            label_code="science_diffusion_science_off",
            runner_config=science_off,
        ),
        ExperimentCondition(
            condition_id="diffusion-instruments-v57",
            label_code="science_diffusion_instruments",
            runner_config=instruments,
        ),
    )
    _LOG.info(
        "science_diffusion_scenario_built arms=%s max_ticks=%s",
        len(conditions),
        max_ticks,
    )
    return ExperimentDefinition(
        experiment_id=SCIENCE_DIFFUSION_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group="science-diffusion-paired-v1",
    )
