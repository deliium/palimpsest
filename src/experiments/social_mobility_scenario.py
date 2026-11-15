"""Off-gate experiment ``social_mobility@1``.

Three arms differ only by declared seams. The baseline arm keeps generation
lineage out of the run; the kinship arm adds durable records, repositories,
cultural provenance, and mentorship; the full arm adds the V4 economic and
institutional flags plus structured commitments and subjective valuation.
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
from simulation.new_agent_initialization import (
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    KinshipBootstrapEdgeSpec,
    KinshipSpec,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_collective_projects_spec,
    example_cultural_feature_provenance_spec,
    example_developmental_learning_spec,
    example_durable_records_spec,
    example_knowledge_repositories_spec,
    example_mentorship_spec,
    example_population_lifecycle_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)

__all__ = [
    "SOCIAL_MOBILITY_EXPERIMENT_ID",
    "social_mobility_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.social_mobility_scenario")

SOCIAL_MOBILITY_EXPERIMENT_ID: Final[str] = "social_mobility@1"


def _base(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        schema_version=RUNNER_SCHEMA_VERSION_V56,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            generational_population=True,
            kinship_inheritance=False,
            cultural_historical_memory=False,
        ),
        population_lifecycle=example_population_lifecycle_spec(
            lifespan_ticks=40,
            max_population=8,
            policy_id="fixed_interval_entry",
        ),
        new_agent_initialization=default_new_agent_initialization_spec(),
        kinship=None,
        cultural_feature_provenance=None,
        durable_records=None,
        knowledge_repositories=None,
        mentorship=None,
        developmental_learning=None,
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


def _kinship(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    agents = tuple(config.agents)
    kinship = (
        KinshipSpec(
            bootstrap_edges=(
                KinshipBootstrapEdgeSpec(
                    parent_agent_id=agents[0].agent_id,
                    child_agent_id=agents[1].agent_id,
                    established_tick=0,
                ),
            )
        )
        if len(agents) >= 2
        else None
    )
    return replace(
        config,
        v3_capability_flags=replace(
            config.v3_capability_flags,
            kinship_inheritance=True,
            cultural_historical_memory=True,
        ),
        kinship=kinship,
        cultural_feature_provenance=example_cultural_feature_provenance_spec(),
        durable_records=example_durable_records_spec(),
        knowledge_repositories=example_knowledge_repositories_spec(),
        mentorship=example_mentorship_spec(),
        developmental_learning=example_developmental_learning_spec(),
        agents=tuple(
            replace(
                agent,
                cognition=replace(
                    agent.cognition,
                    teaching_interaction_mode=(TeachingInteractionMode.DETERMINISTIC),
                    skill_learning_mode=SkillLearningMode.DETERMINISTIC,
                ),
            )
            for agent in config.agents
        ),
    )


def _full(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    return replace(
        config,
        collective_projects=example_collective_projects_spec(),
        structured_commitments=example_structured_commitments_spec(),
        subjective_valuation=example_subjective_valuation_spec(),
        v4_capability_flags=replace(
            config.v4_capability_flags,
            organizations=True,
            markets_credit=True,
            infrastructure_networks=True,
            supply_chains=True,
        ),
    )


def social_mobility_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 96,
) -> ExperimentDefinition:
    """Three arms over existing genealogical and economic evidence seams."""

    if max_ticks < 96:
        raise ValueError("social_mobility_requires_three_windows")
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    stop = RunnerStopPolicy(max_ticks=max_ticks)
    rooted = _base(base)
    baseline = replace(rooted, stop_policy=stop)
    kinship = replace(_kinship(rooted), stop_policy=stop)
    full = replace(_full(kinship), stop_policy=stop)
    conditions = (
        ExperimentCondition(
            condition_id="sm-baseline",
            label_code="social_mobility_baseline",
            runner_config=baseline,
        ),
        ExperimentCondition(
            condition_id="sm-kinship",
            label_code="social_mobility_kinship",
            runner_config=kinship,
        ),
        ExperimentCondition(
            condition_id="sm-full",
            label_code="social_mobility_full",
            runner_config=full,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s off_gate=true",
        SOCIAL_MOBILITY_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=SOCIAL_MOBILITY_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{SOCIAL_MOBILITY_EXPERIMENT_ID}-world",
    )
