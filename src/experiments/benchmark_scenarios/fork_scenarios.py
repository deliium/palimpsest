"""Benchmark builder for scenario 16 (forked COMMUNICATION_REMOVE intervention)."""

from __future__ import annotations

import logging
from typing import Final

from experiments.benchmark_scenarios._common import with_seed_matrix
from experiments.benchmark_suite import BENCH_16_FORKED_INTERVENTION
from experiments.models import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentCondition,
    ExperimentDefinition,
    ExperimentSeedMatrix,
)
from simulation.branching import (
    CommunicationRemoveTarget,
    ResearchIntervention,
    ResearchInterventionKind,
)
from simulation.runner_models import SimulationRunnerConfig

from . import BenchmarkBuildResult, register_benchmark_builder

_LOG: Final[logging.Logger] = logging.getLogger("experiments.benchmark_scenarios")

FORK_PARENT_CONDITION_ID: Final[str] = "fork-parent"
FORK_CHILD_CONDITION_ID: Final[str] = "fork-child-comm-remove"


def communication_remove_intervention(
    *,
    event_id: str | None = None,
    tick: int | None = None,
    sequence: int | None = None,
) -> ResearchIntervention:
    """Build the locked COMMUNICATION_REMOVE intervention for suite tests."""
    if event_id is not None:
        target = CommunicationRemoveTarget(event_id=event_id)
    else:
        target = CommunicationRemoveTarget(tick=tick, sequence=sequence)
    return ResearchIntervention(
        kind=ResearchInterventionKind.COMMUNICATION_REMOVE,
        communication_remove=target,
    )


def build_bench_16_forked_intervention(
    base: SimulationRunnerConfig,
    *,
    seed_matrix: ExperimentSeedMatrix | None = None,
) -> BenchmarkBuildResult:
    """Parent/child template arms sharing one world; fork applied via branch APIs."""
    matrix = seed_matrix or ExperimentSeedMatrix(seeds=(base.seed,))
    definition = ExperimentDefinition(
        experiment_id=BENCH_16_FORKED_INTERVENTION,
        schema_version=EXPERIMENT_SCHEMA_VERSION,
        seed_matrix=matrix,
        conditions=(
            ExperimentCondition(
                condition_id=FORK_PARENT_CONDITION_ID,
                label_code="fork_parent_immutable",
                runner_config=base,
            ),
            ExperimentCondition(
                condition_id=FORK_CHILD_CONDITION_ID,
                label_code="fork_child_communication_remove",
                runner_config=base,
            ),
        ),
        paired_world_group=f"{BENCH_16_FORKED_INTERVENTION}-world",
    )
    definition = with_seed_matrix(definition, seed_matrix)
    _LOG.debug(
        "bench_16_modes intervention_kind=%s",
        ResearchInterventionKind.COMMUNICATION_REMOVE.value,
    )
    return BenchmarkBuildResult(
        scenario_id=BENCH_16_FORKED_INTERVENTION,
        definition=definition,
        matrix_factors=("research_fork",),
    )


def register_fork_scenario_builders() -> None:
    register_benchmark_builder(
        BENCH_16_FORKED_INTERVENTION, build_bench_16_forked_intervention
    )


register_fork_scenario_builders()
