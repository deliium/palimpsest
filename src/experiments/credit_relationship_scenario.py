"""Off-gate experiment ``credit_relationships@1``.

Four arms differ only by declared seams: ``markets_credit``, the V3-17
``structured_commitments`` spec, the V3-18 ``subjective_valuation`` spec, and an
optional deterministic communication strategy. No command, event, schema, or
credit object is added.
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
    STRUCTURED_COMMITMENTS_POLICY_ID,
    SUBJECTIVE_VALUATION_POLICY_ID,
    CommunicationStrategyMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    StructuredCommitmentsSpec,
    SubjectiveValuationSpec,
)

__all__ = [
    "CREDIT_RELATIONSHIPS_EXPERIMENT_ID",
    "credit_relationship_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.credit_relationship_scenario"
)

CREDIT_RELATIONSHIPS_EXPERIMENT_ID: Final[str] = "credit_relationships@1"


def _commitments(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        structured_commitments=(
            StructuredCommitmentsSpec(
                policy_id=STRUCTURED_COMMITMENTS_POLICY_ID,
                horizon_ticks=16,
                max_open_interpretations=8,
            )
            if enabled
            else None
        ),
        subjective_valuation=(
            SubjectiveValuationSpec(
                policy_id=SUBJECTIVE_VALUATION_POLICY_ID,
                horizon_ticks=16,
                max_bundle=8,
            )
            if enabled
            else None
        ),
    )


def _markets(
    config: SimulationRunnerConfig, *, enabled: bool
) -> SimulationRunnerConfig:
    return replace(
        config,
        v4_capability_flags=replace(
            config.v4_capability_flags, markets_credit=enabled
        ),
    )


def _dialogue(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
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


def credit_relationship_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Four arms over existing commitment, valuation, and market seams."""

    if max_ticks < 96:
        raise ValueError("credit_relationships_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    stop = RunnerStopPolicy(max_ticks=max_ticks)
    flag_off = replace(_commitments(base, enabled=False), stop_policy=stop)
    promises_only = replace(_commitments(base, enabled=True), stop_policy=stop)
    credit_on = replace(_markets(promises_only, enabled=True), stop_policy=stop)
    credit_dialogue = replace(_dialogue(credit_on), stop_policy=stop)
    conditions = (
        ExperimentCondition(
            condition_id="cr-flag-off",
            label_code="credit_relationships_flag_off",
            runner_config=flag_off,
        ),
        ExperimentCondition(
            condition_id="cr-promises-only",
            label_code="credit_relationships_promises_only",
            runner_config=promises_only,
        ),
        ExperimentCondition(
            condition_id="cr-credit-on",
            label_code="credit_relationships_on",
            runner_config=credit_on,
        ),
        ExperimentCondition(
            condition_id="cr-credit-dialogue",
            label_code="credit_relationships_dialogue",
            runner_config=credit_dialogue,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        CREDIT_RELATIONSHIPS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=CREDIT_RELATIONSHIPS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{CREDIT_RELATIONSHIPS_EXPERIMENT_ID}-world",
    )
