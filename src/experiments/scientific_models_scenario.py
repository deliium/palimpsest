"""Off-gate experiment ``scientific_models@1`` (four declared arms)."""

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
    BoundedExperimentationSpec,
    ExperimentLaw,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)
from world.environment import example_environmental_dynamics

__all__ = [
    "SCIENTIFIC_MODELS_EXPERIMENT_ID",
    "scientific_models_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_models_scenario"
)

SCIENTIFIC_MODELS_EXPERIMENT_ID: Final[str] = "scientific_models@1"
_MIN_TICKS: Final[int] = 96


def _science_laws() -> tuple[ExperimentLaw, ...]:
    return (
        example_experiment_law(
            operator="vary_process",
            operand_a_kind="item:tool",
            operand_b_kind="none",
            process_token="harvest",
            outcome_class="failure",
            delta="none",
        ),
    )


def scientific_models_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = _MIN_TICKS,
) -> ExperimentDefinition:
    """Four arms over the owned ``science`` flag; no preloaded models."""

    if max_ticks < _MIN_TICKS:
        _LOG.warning("scientific_models_scenario_invalid reason_code=min_ticks")
        raise ValueError("scientific_models_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    from experiments.measurement_scenario import measurement_instruments_scenario

    measurement_definition = measurement_instruments_scenario(
        base, seed_matrix=matrix, max_ticks=_MIN_TICKS
    )
    instrumented = next(
        row.runner_config
        for row in measurement_definition.conditions
        if row.condition_id == "measurement-unbiased"
    )
    measurement_spec = instrumented.measurement_instruments
    shared = replace(
        instrumented,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        measurement_instruments=None,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=BoundedExperimentationSpec(
            laws=_science_laws(),
            max_hypotheses=8,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
        v4_capability_flags=V4CapabilityFlags(science=True),
        environmental_dynamics=None,
    )
    off = replace(
        shared,
        bounded_experimentation=None,
        capability_flags=V2CapabilityFlags(),
        v4_capability_flags=V4CapabilityFlags(),
    )
    season_resource = replace(
        shared, environmental_dynamics=example_environmental_dynamics()
    )
    production = replace(shared)
    conditions = [
        ExperimentCondition(
            condition_id="models-science-off",
            label_code="scientific_models_off",
            runner_config=off,
        ),
        ExperimentCondition(
            condition_id="models-season-resource",
            label_code="scientific_models_season_resource",
            runner_config=season_resource,
        ),
        ExperimentCondition(
            condition_id="models-production",
            label_code="scientific_models_production",
            runner_config=production,
        ),
    ]
    coexistence = replace(
        shared,
        schema_version=RUNNER_SCHEMA_VERSION_V57,
        measurement_instruments=measurement_spec,
    )
    conditions.append(
        ExperimentCondition(
            condition_id="models-measurement-coexistence",
            label_code="scientific_models_measurement_coexistence",
            runner_config=coexistence,
        )
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        SCIENTIFIC_MODELS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=SCIENTIFIC_MODELS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=tuple(conditions),
        paired_world_group=f"{SCIENTIFIC_MODELS_EXPERIMENT_ID}-world",
    )
