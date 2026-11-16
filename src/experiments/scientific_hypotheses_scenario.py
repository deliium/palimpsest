"""Off-gate experiment ``scientific_hypotheses@1``.

Three arms share the accepted ``runner-config-v56`` seam and one bounded
experimentation spec. The baseline keeps science off and is provably inert; the
enabled arm lets an owner intentionally test a hypothesis; the communicated arm
also asks for deterministic communication so one ``hyp_v1`` claim can be shared.
"""

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
    "SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID",
    "scientific_hypotheses_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.scientific_hypotheses_scenario"
)

SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID: Final[str] = "scientific_hypotheses@1"


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


def scientific_hypotheses_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 64,
) -> ExperimentDefinition:
    """Three arms over the owned ``science`` flag and experiment ledger."""

    if max_ticks < 64:
        _LOG.warning("scientific_hypotheses_scenario_invalid reason_code=min_ticks")
        raise ValueError("scientific_hypotheses_min_ticks")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    laws = (
        example_experiment_law(
            operator="vary_process",
            operand_a_kind="item:tool",
            operand_b_kind="none",
            process_token="harvest",
            outcome_class="failure",
            delta="none",
        ),
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
            laws=laws,
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
        v4_capability_flags=V4CapabilityFlags(),
    )
    enabled = replace(
        shared,
        capability_flags=V2CapabilityFlags(predictive_world_model=True),
        v4_capability_flags=V4CapabilityFlags(science=True),
    )
    communicated = _communication(enabled)
    conditions = (
        ExperimentCondition(
            condition_id="science-baseline",
            label_code="scientific_hypotheses_baseline",
            runner_config=baseline,
        ),
        ExperimentCondition(
            condition_id="science-enabled",
            label_code="scientific_hypotheses_enabled",
            runner_config=enabled,
        ),
        ExperimentCondition(
            condition_id="science-communicated",
            label_code="scientific_hypotheses_communicated",
            runner_config=communicated,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{SCIENTIFIC_HYPOTHESES_EXPERIMENT_ID}-world",
    )
