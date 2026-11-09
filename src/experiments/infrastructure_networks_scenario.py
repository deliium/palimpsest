"""Off-gate experiment ``infrastructure_networks@1``.

Composes runner-config-v56 with collective_projects (+ production cognition) and
an optional infrastructure_networks capability flag. Control keeps the channel
inert; treatment enables the owned flag. Does not own ``supply_chains``.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import (
    Goal,
    GoalHorizon,
    GoalId,
    GoalOutcome,
    GoalOutcomeKind,
    GoalStatus,
)
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.runner_models import (
    RUNNER_SCHEMA_VERSION_V56,
    CollectiveProjectsSpec,
    MortalityMode,
    RunnerStopPolicy,
    SimulationRunnerConfig,
    V3CapabilityFlags,
    V4CapabilityFlags,
    example_collective_projects_spec,
)
from world.production import ProductionCatalog, example_production_catalog

__all__ = [
    "INFRASTRUCTURE_NETWORKS_EXPERIMENT_ID",
    "infrastructure_networks_scenario",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.infrastructure_networks_scenario"
)

INFRASTRUCTURE_NETWORKS_EXPERIMENT_ID: Final[str] = "infrastructure_networks@1"


def _with_production(config: SimulationRunnerConfig) -> SimulationRunnerConfig:
    catalog: ProductionCatalog = example_production_catalog()
    agents = []
    for agent in config.agents:
        agents.append(
            replace(
                agent,
                cognition=replace(agent.cognition, production_catalog=catalog),
            )
        )
    return replace(config, agents=tuple(agents))


def infrastructure_networks_scenario(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
    max_ticks: int = 24,
) -> ExperimentDefinition:
    """Control (flag off) vs treatment (flag on) for infrastructure_networks@1."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    projects: CollectiveProjectsSpec = example_collective_projects_spec()

    def _v56(
        *,
        infrastructure_on: bool,
        collective: CollectiveProjectsSpec | None = projects,
    ) -> SimulationRunnerConfig:
        config = replace(
            base,
            schema_version=RUNNER_SCHEMA_VERSION_V56,
            mortality_mode=MortalityMode.DISABLED,
            stop_policy=RunnerStopPolicy(max_ticks=max_ticks),
            v3_capability_flags=V3CapabilityFlags(),
            v4_capability_flags=V4CapabilityFlags(
                infrastructure_networks=infrastructure_on
            ),
            collective_projects=collective,
            public_goods=None,
            subjective_valuation=None,
            resource_exchange_profile=None,
            population_lifecycle=None,
        )
        return _with_production(config)

    control = _v56(infrastructure_on=False)
    treatment = _v56(infrastructure_on=True)
    if treatment.agents:
        owner = treatment.agents[0]
        goal = Goal(
            goal_id=GoalId("goal-road"),
            owner_id=owner.agent_id,
            description="infrastructure-road",
            priority=0.5,
            status=GoalStatus.ACTIVE,
            outcome=GoalOutcome(
                kind=GoalOutcomeKind.ACHIEVE_CODE,
                outcome_code="collective_project:start:road",
            ),
            horizon=GoalHorizon.CURRENT_INTENTION,
        )
        treatment = replace(
            treatment,
            agents=(replace(owner, initial_goals=(goal,)), *treatment.agents[1:]),
        )

    conditions = (
        ExperimentCondition(
            condition_id="infra-channel-off",
            label_code="infrastructure_networks_channel_off",
            runner_config=control,
        ),
        ExperimentCondition(
            condition_id="infra-treatment",
            label_code="infrastructure_networks_treatment",
            runner_config=treatment,
        ),
    )
    _LOG.info(
        "experiment_registered experiment_id=%s arms=%s",
        INFRASTRUCTURE_NETWORKS_EXPERIMENT_ID,
        len(conditions),
    )
    return ExperimentDefinition(
        experiment_id=INFRASTRUCTURE_NETWORKS_EXPERIMENT_ID,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=conditions,
        paired_world_group=f"{INFRASTRUCTURE_NETWORKS_EXPERIMENT_ID}-world",
    )
