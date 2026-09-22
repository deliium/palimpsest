"""Async experiment coordinator for sequential A–E arm execution."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from experiments.interventions import StoryInterventionArbiter
from experiments.models import ExperimentDefinition
from simulation.models import RunId
from simulation.runner import SimulationRunner
from simulation.runner_models import (
    SimulationRunnerConfig,
    SimulationRunnerResult,
)
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger("experiments.coordinator")


@dataclass(frozen=True, slots=True)
class ExperimentAssignment:
    """One materialized condition/seed/replicate run assignment."""

    experiment_id: str
    condition_id: str
    condition_ordinal: int
    seed: int
    seed_ordinal: int
    replicate_index: int
    run_id: RunId
    runner_config: SimulationRunnerConfig


@dataclass(frozen=True, slots=True)
class ExperimentArmResult:
    """Structured result for one assignment."""

    assignment: ExperimentAssignment
    runner_result: SimulationRunnerResult
    config_fingerprint: str


def materialize_assignments(
    definition: ExperimentDefinition,
) -> tuple[ExperimentAssignment, ...]:
    """Expand conditions × seeds × replicates in deterministic order."""
    if type(definition) is not ExperimentDefinition:
        raise TypeError("definition must be ExperimentDefinition")
    assignments: list[ExperimentAssignment] = []
    for condition_ordinal, condition in enumerate(definition.conditions):
        for seed_ordinal, seed in enumerate(definition.seed_matrix.seeds):
            for replicate_index in range(definition.seed_matrix.replicates_per_seed):
                config = SimulationRunnerConfig(
                    seed=seed,
                    stochastic_identity=condition.runner_config.stochastic_identity,
                    scenario=condition.runner_config.scenario,
                    agents=condition.runner_config.agents,
                    stop_policy=condition.runner_config.stop_policy,
                    mortality_mode=condition.runner_config.mortality_mode,
                    cognition_failure_policy=(
                        condition.runner_config.cognition_failure_policy
                    ),
                    provider=condition.runner_config.provider,
                    persistence=condition.runner_config.persistence,
                )
                run_id = RunId(
                    f"{definition.experiment_id}-{condition.condition_id}"
                    f"-s{seed_ordinal}-r{replicate_index}"
                )
                assignments.append(
                    ExperimentAssignment(
                        experiment_id=definition.experiment_id,
                        condition_id=condition.condition_id,
                        condition_ordinal=condition_ordinal,
                        seed=seed,
                        seed_ordinal=seed_ordinal,
                        replicate_index=replicate_index,
                        run_id=run_id,
                        runner_config=config,
                    )
                )
    return tuple(assignments)


class ExperimentCoordinator:
    """Sequential V1 coordinator: one fresh runner per assignment."""

    __slots__ = ("_definition", "_intervention")

    def __init__(
        self,
        definition: ExperimentDefinition,
        *,
        intervention_arbiter: StoryInterventionArbiter | None = None,
    ) -> None:
        if type(definition) is not ExperimentDefinition:
            raise TypeError("definition must be ExperimentDefinition")
        self._definition = definition
        self._intervention = intervention_arbiter

    async def run_all(self) -> tuple[ExperimentArmResult, ...]:
        results: list[ExperimentArmResult] = []
        for assignment in materialize_assignments(self._definition):
            _LOG.info(
                "experiment_arm_start",
                extra={
                    "experiment": {
                        "experiment_id": assignment.experiment_id,
                        "condition_id": assignment.condition_id,
                        "condition_ordinal": assignment.condition_ordinal,
                        "seed_ordinal": assignment.seed_ordinal,
                        "replicate_index": assignment.replicate_index,
                        "run_id": assignment.run_id.value,
                    }
                },
            )
            async with await SimulationRunner.from_config(
                assignment.runner_config,
                run_id=assignment.run_id,
            ) as runner:
                if (
                    self._intervention is not None
                    and assignment.condition_id.endswith("intervention")
                ):
                    runner.set_intervention_arbiter(self._intervention)
                runner_result = await runner.run()
            fingerprint = runner_config_fingerprint(assignment.runner_config)
            results.append(
                ExperimentArmResult(
                    assignment=assignment,
                    runner_result=runner_result,
                    config_fingerprint=fingerprint,
                )
            )
            _LOG.info(
                "experiment_arm_complete",
                extra={
                    "experiment": {
                        "run_id": assignment.run_id.value,
                        "stop_reason": runner_result.stop_reason.value,
                        "ticks_committed": runner_result.ticks_committed,
                        "config_fingerprint_prefix": fingerprint[:12],
                    }
                },
            )
        return tuple(results)
