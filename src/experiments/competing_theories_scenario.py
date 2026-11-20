"""Off-gate experiment ``competing_theories@1`` (four declared arms)."""

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
    CommunicationStrategyMode,
    SimulationRunnerConfig,
    V4CapabilityFlags,
)

__all__ = [
    "COMPETING_THEORIES_EXPERIMENT_ID",
    "competing_theories_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.competing_theories_scenario"
)

COMPETING_THEORIES_EXPERIMENT_ID: Final[str] = "competing_theories@1"
_MIN_TICKS: Final[int] = 96


def _with_communication(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    communication_strategy_mode=(
                        CommunicationStrategyMode.DETERMINISTIC
                    ),
                ),
            )
            for agent in config.agents
        ),
    )


def competing_theories_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = _MIN_TICKS,
) -> ExperimentDefinition:
    """Four arms over owned science. No preloaded explanations or winners."""

    if max_ticks < _MIN_TICKS:
        _LOG.warning("competing_theories_scenario_invalid reason_code=min_ticks")
        raise ValueError("competing_theories_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    from experiments.scientific_models_scenario import scientific_models_scenario

    source = scientific_models_scenario(base, seed_matrix=matrix, max_ticks=max_ticks)
    by_id = {row.condition_id: row.runner_config for row in source.conditions}
    seasonal = by_id["models-season-resource"]
    off = by_id["models-science-off"]
    coexistence = by_id["models-measurement-coexistence"]
    observation = replace(
        seasonal,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    communication = _with_communication(observation)
    conditions = (
        ExperimentCondition(
            condition_id="theories-observation",
            label_code="competing_theories_observation",
            runner_config=observation,
        ),
        ExperimentCondition(
            condition_id="theories-science-off",
            label_code="competing_theories_science_off",
            runner_config=replace(off, schema_version=RUNNER_SCHEMA_VERSION_V56),
        ),
        ExperimentCondition(
            condition_id="theories-communication",
            label_code="competing_theories_communication",
            runner_config=communication,
        ),
        ExperimentCondition(
            condition_id="theories-measurement-coexistence",
            label_code="competing_theories_measurement_coexistence",
            runner_config=replace(
                coexistence,
                schema_version=RUNNER_SCHEMA_VERSION_V57,
                v4_capability_flags=V4CapabilityFlags(science=True),
            ),
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        COMPETING_THEORIES_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=COMPETING_THEORIES_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{COMPETING_THEORIES_EXPERIMENT_ID}-world",
    )
