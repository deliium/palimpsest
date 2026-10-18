"""Async experiment coordinator for sequential A-E arm execution."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
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
    metrics: tuple[object, ...] = ()
    committed_events: tuple[object, ...] | None = None
    regional_destination_evidence: tuple[object, ...] | None = None
    generation_index_by_owner: Mapping[str, int] | None = None


def materialize_assignments(
    definition: ExperimentDefinition,
) -> tuple[ExperimentAssignment, ...]:
    """Expand conditions x seeds x replicates in deterministic order."""
    if type(definition) is not ExperimentDefinition:
        raise TypeError("definition must be ExperimentDefinition")
    assignments: list[ExperimentAssignment] = []
    for condition_ordinal, condition in enumerate(definition.conditions):
        for seed_ordinal, seed in enumerate(definition.seed_matrix.seeds):
            for replicate_index in range(definition.seed_matrix.replicates_per_seed):
                config = replace(condition.runner_config, seed=seed)
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


def _generation_index_by_owner(
    runner_result: SimulationRunnerResult,
) -> dict[str, int] | None:
    derived: dict[str, int] = {}
    for record in runner_result.initial_lifecycle_records:
        owner = getattr(record, "agent_id", None)
        generation = getattr(record, "generation_index", None)
        if isinstance(owner, str) and owner and isinstance(generation, int):
            if not isinstance(generation, bool) and generation >= 0:
                derived[owner] = generation
    return derived or None


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
                if assignment.experiment_id == "regional_migration@1":
                    from experiments.regional_migration_scenario import (
                        regional_migration_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        regional_migration_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if assignment.experiment_id == "cultural_contact@1":
                    from experiments.cultural_contact_scenario import (
                        cultural_contact_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        cultural_contact_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if assignment.experiment_id == "compositional_symbols@1":
                    from experiments.symbolic_language_scenario import (
                        symbolic_language_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        symbolic_language_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if assignment.experiment_id == "semantic_drift@1":
                    from experiments.semantic_drift_scenario import (
                        semantic_drift_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        semantic_drift_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if assignment.experiment_id == "multiple_societies@1":
                    from experiments.multiple_societies_scenario import (
                        multiple_societies_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        multiple_societies_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if self._intervention is not None and assignment.condition_id.endswith(
                    "intervention"
                ):
                    runner.set_intervention_arbiter(self._intervention)
                runner_result = await runner.run()
                committed_events = tuple(runner.engine.export_events().events)
                regional_destination_traces = (
                    await runner.export_regional_destination_traces()
                )
                if regional_destination_traces is None:
                    regional_destination_evidence = None
                else:
                    from experiments.composition import (
                        regional_destination_evidence_rows_from_traces,
                    )

                    regional_destination_evidence = (
                        regional_destination_evidence_rows_from_traces(
                            regional_destination_traces
                        )
                    )
            fingerprint = runner_config_fingerprint(assignment.runner_config)
            arm = ExperimentArmResult(
                assignment=assignment,
                runner_result=runner_result,
                config_fingerprint=fingerprint,
                committed_events=committed_events,
                regional_destination_evidence=regional_destination_evidence,
                generation_index_by_owner=_generation_index_by_owner(runner_result),
            )
            from experiments.collectors import collect_for_experiment

            metrics = collect_for_experiment(arm)
            arm = ExperimentArmResult(
                assignment=assignment,
                runner_result=runner_result,
                config_fingerprint=fingerprint,
                metrics=metrics,
                committed_events=committed_events,
                regional_destination_evidence=regional_destination_evidence,
                generation_index_by_owner=_generation_index_by_owner(runner_result),
            )
            results.append(arm)
            _LOG.info(
                "experiment_arm_complete",
                extra={
                    "experiment": {
                        "run_id": assignment.run_id.value,
                        "stop_reason": runner_result.stop_reason.value,
                        "ticks_committed": runner_result.ticks_committed,
                        "committed_event_count": len(committed_events),
                        "regional_destination_trace_count": (
                            None
                            if regional_destination_evidence is None
                            else len(regional_destination_evidence)
                        ),
                        "config_fingerprint_prefix": fingerprint[:12],
                        "metric_families": tuple(
                            getattr(item, "family", "unknown") for item in metrics
                        ),
                    }
                },
            )
        return tuple(results)
