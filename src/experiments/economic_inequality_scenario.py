"""Off-gate experiment ``economic_inequality@1``.

Three arms differ only by declared seams: baseline has no economic channel,
access enables infrastructure, collective projects, durable records, and
knowledge repositories, and full adds organizations, markets/credit,
structured commitments, and subjective valuation. No command, event, runner
schema, or metric family is added by the scenario.
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
    RunnerStopPolicy,
    SimulationRunnerConfig,
    example_collective_projects_spec,
    example_cultural_feature_provenance_spec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)

__all__ = [
    "ECONOMIC_INEQUALITY_EXPERIMENT_ID",
    "economic_inequality_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_inequality_scenario"
)

ECONOMIC_INEQUALITY_EXPERIMENT_ID: Final[str] = "economic_inequality@1"


def _base(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=replace(
            config.v3_capability_flags, cultural_historical_memory=True
        ),
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=None,
        knowledge_repositories=None,
        collective_projects=None,
        structured_commitments=None,
        subjective_valuation=None,
        v4_capability_flags=replace(
            config.v4_capability_flags,
            organizations=False,
            markets_credit=False,
            infrastructure_networks=False,
            supply_chains=False,
        ),
    )


def _access(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        collective_projects=example_collective_projects_spec(),
        v4_capability_flags=replace(
            config.v4_capability_flags, infrastructure_networks=True
        ),
    )


def _full(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        structured_commitments=example_structured_commitments_spec(),
        subjective_valuation=example_subjective_valuation_spec(),
        v4_capability_flags=replace(
            config.v4_capability_flags,
            organizations=True,
            markets_credit=True,
            infrastructure_networks=True,
        ),
    )


def economic_inequality_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Three arms over existing economic evidence seams."""

    if max_ticks < 96:
        raise ValueError("economic_inequality_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    stop = RunnerStopPolicy(max_ticks=max_ticks)
    rooted = _base(base)
    baseline = replace(rooted, stop_policy=stop)
    access = replace(_access(rooted), stop_policy=stop)
    full = replace(_full(access), stop_policy=stop)
    conditions = (
        ExperimentCondition(
            condition_id="ei-baseline",
            label_code="economic_inequality_baseline",
            runner_config=baseline,
        ),
        ExperimentCondition(
            condition_id="ei-access",
            label_code="economic_inequality_access",
            runner_config=access,
        ),
        ExperimentCondition(
            condition_id="ei-full",
            label_code="economic_inequality_full",
            runner_config=full,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        ECONOMIC_INEQUALITY_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=ECONOMIC_INEQUALITY_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{ECONOMIC_INEQUALITY_EXPERIMENT_ID}-world",
    )
