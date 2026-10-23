"""Async experiment coordinator for sequential A-E arm execution."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from experiments.cultural_metric_artifacts import CulturalCaptureOptions
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

_RUN_ID_MAX = 64


def _assignment_run_id(raw: str) -> str:
    """Keep legacy ids; hash only ids that exceed the safe segment bound."""
    if len(raw) <= _RUN_ID_MAX:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    shortened = f"run-{digest}"
    _LOG.debug(
        "assignment_run_id_shortened raw_length=%s run_id_prefix=%s",
        len(raw),
        shortened,
    )
    return shortened


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
    cultural_evolution_evidence: object | None = None
    cultural_evolution_evidence_digest: str | None = None
    cultural_evolution_documents: tuple[object, ...] = ()
    cultural_evolution_capture_status: object | None = None


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
                    _assignment_run_id(
                        f"{definition.experiment_id}-{condition.condition_id}"
                        f"-s{seed_ordinal}-r{replicate_index}"
                    )
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

    __slots__ = (
        "_cultural_capture",
        "_definition",
        "_generational_contexts",
        "_intervention",
        "_source_revision",
    )

    def __init__(
        self,
        definition: ExperimentDefinition,
        *,
        intervention_arbiter: StoryInterventionArbiter | None = None,
        generational_contexts: Mapping[str, object] | None = None,
        cultural_capture: CulturalCaptureOptions | None = None,
        source_revision: str = "unknown",
    ) -> None:
        if type(definition) is not ExperimentDefinition:
            raise TypeError("definition must be ExperimentDefinition")
        self._definition = definition
        self._intervention = intervention_arbiter
        self._generational_contexts = dict(generational_contexts or {})
        self._cultural_capture = cultural_capture
        self._source_revision = source_revision

    async def run_all(self) -> tuple[ExperimentArmResult, ...]:
        from experiments.path_dependence_catalog import require_independent_execution

        require_independent_execution(self._definition.experiment_id)
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
            if assignment.runner_config.generational_run is not None:
                context = self._generational_contexts.get(
                    assignment.condition_id
                ) or self._generational_contexts.get("*")
                if context is None:
                    raise ValueError(
                        "generational assignment requires execution context"
                    )
                from experiments.generational_execution import (
                    GenerationalExecutionContext,
                    execute_generational_assignment,
                )

                if (
                    self._cultural_capture is not None
                    and type(context) is GenerationalExecutionContext
                ):
                    context = replace(context, cultural_capture=self._cultural_capture)
                results.append(
                    await execute_generational_assignment(assignment, context)  # type: ignore[arg-type]
                )
                continue
            recorder = None
            kinship_edges: tuple[tuple[str, str], ...] = ()
            async with await SimulationRunner.from_config(
                assignment.runner_config,
                run_id=assignment.run_id,
            ) as runner:
                from experiments.cultural_evidence import (
                    install_cultural_recorder,
                    kinship_parent_child_edges,
                )

                recorder = install_cultural_recorder(
                    runner,
                    self._cultural_capture,
                )
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
                if assignment.experiment_id == "generational_narratives@1":
                    from experiments.generational_narratives_scenario import (
                        generational_narrative_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        generational_narrative_arbiter(
                            assignment.condition_id, assignment.runner_config
                        )
                    )
                if assignment.experiment_id == "cross_cultural_translation@1":
                    from experiments.translation_scenario import (
                        translation_arbiter,
                    )

                    runner.set_intervention_arbiter(
                        translation_arbiter(
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
                if recorder is not None:
                    recorder.merge_capture_status(
                        runner.export_cultural_capture_status()
                    )
                committed_events = tuple(runner.engine.export_events().events)
                kinship_edges = kinship_parent_child_edges(runner.engine.kinship_graph)
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
            cultural_fields: dict[str, object] = {}
            if recorder is not None and self._cultural_capture is not None:
                from experiments.cultural_evidence import build_cultural_arm_fields

                cultural_fields = build_cultural_arm_fields(
                    recorder,
                    run_id=assignment.run_id.value,
                    config_fingerprint=fingerprint,
                    options=self._cultural_capture,
                    source_revision=self._source_revision,
                    parent_child_edges=kinship_edges,
                )
            arm = ExperimentArmResult(
                assignment=assignment,
                runner_result=runner_result,
                config_fingerprint=fingerprint,
                committed_events=committed_events,
                regional_destination_evidence=regional_destination_evidence,
                generation_index_by_owner=_generation_index_by_owner(runner_result),
                **cultural_fields,  # type: ignore[arg-type]
            )
            from experiments.collectors import collect_for_experiment

            arm = replace(arm, metrics=collect_for_experiment(arm))
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
                            getattr(item, "family", "unknown") for item in arm.metrics
                        ),
                    }
                },
            )
        return tuple(results)
