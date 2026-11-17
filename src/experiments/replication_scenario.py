"""Off-gate experiment ``scientific_replication@1`` (four declared arms)."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Final, cast

from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    BoundedExperimentationSpec,
    CommunicationStrategyMode,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V2CapabilityFlags,
    V3CapabilityFlags,
    V4CapabilityFlags,
    example_cultural_feature_provenance_spec,
    example_experiment_law,
)

__all__ = [
    "SCIENTIFIC_REPLICATION_EXPERIMENT_ID",
    "scientific_replication_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.replication_scenario"
)

SCIENTIFIC_REPLICATION_EXPERIMENT_ID: Final[str] = "scientific_replication@1"


def _communication(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
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


def scientific_replication_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 64,
) -> ExperimentDefinition:
    """Four arms over existing science/bounded-experimentation seams."""

    if (
        isinstance(max_ticks, bool)
        or type(max_ticks) is not int
        or max_ticks < 64
    ):
        _LOG.warning("scientific_replication_scenario_invalid reason_code=min_ticks")
        raise ValueError("scientific_replication_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    tool_law = example_experiment_law(
        operator="vary_process",
        operand_a_kind="item:tool",
        operand_b_kind="none",
        process_token="harvest",
        outcome_class="failure",
        delta="none",
    )
    material_law = example_experiment_law(
        operator="vary_process",
        operand_a_kind="item:material",
        operand_b_kind="none",
        process_token="craft",
        outcome_class="failure",
        delta="none",
    )
    shared = replace(
        base,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        mortality_mode=MortalityMode.DISABLED,
        stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
        capability_flags=V2CapabilityFlags(),
        v3_capability_flags=V3CapabilityFlags(cultural_historical_memory=True),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        bounded_experimentation=BoundedExperimentationSpec(
            laws=(tool_law,),
            max_hypotheses=8,
            max_trials_per_tick=1,
            repeat_threshold=2,
            learn_into_genealogy=False,
            allow_provider=False,
        ),
        v4_capability_flags=V4CapabilityFlags(),
    )
    baseline = replace(
        shared,
        capability_flags=V2CapabilityFlags(predictive_world_model=False),
    )
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    community = _communication(enabled)
    conflicting = _communication(
        replace(
            enabled,
            bounded_experimentation=replace(
                cast(Any, enabled.bounded_experimentation),
                laws=(tool_law, material_law),
            ),
        )
    )
    conditions = (
        ExperimentCondition(
            condition_id="replication-baseline",
            label_code="scientific_replication_baseline",
            runner_config=baseline,
        ),
        ExperimentCondition(
            condition_id="replication-individual",
            label_code="scientific_replication_individual",
            runner_config=enabled,
        ),
        ExperimentCondition(
            condition_id="replication-community",
            label_code="scientific_replication_community",
            runner_config=community,
        ),
        ExperimentCondition(
            condition_id="replication-conflicting-conditions",
            label_code="scientific_replication_conflicting_conditions",
            runner_config=conflicting,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        SCIENTIFIC_REPLICATION_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=SCIENTIFIC_REPLICATION_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{SCIENTIFIC_REPLICATION_EXPERIMENT_ID}-world",
    )
