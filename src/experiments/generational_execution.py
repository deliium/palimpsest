"""Per-assignment execution context for generational experiment cells."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.collectors import collect_for_experiment
from experiments.coordinator import ExperimentArmResult, ExperimentAssignment
from experiments.generational_artifacts import (
    HistoricalBoundaryReader,
    HistoricalBoundaryReference,
)
from experiments.generational_runner_scenario import generational_runner_arbiter
from research_runner.generational_composition import (
    GenerationalExecutionRecipe,
    open_generational_archive,
)
from simulation.runner import RunnerDependencyFactories, SimulationRunner
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_execution"
)

PLAIN_RECIPE_ID: Final[str] = "plain-generational"
BL_RECIPE_ID: Final[str] = "bl-diagnostic"
BL_TREATMENTS: Final[frozenset[str]] = frozenset(
    {"single_cohort", "unassisted", "contact"}
)


class GenerationalExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _validate_recipe(
    recipe: GenerationalExecutionRecipe, config: SimulationRunnerConfig
) -> None:
    if config.generational_run is None:
        raise GenerationalExecutionError("generational_config_required")
    lifecycle = config.population_lifecycle
    if lifecycle is None:
        raise GenerationalExecutionError("lifecycle_required")
    if recipe.recipe_id == PLAIN_RECIPE_ID:
        if recipe.version != "1" or recipe.params or recipe.intervention_id is not None:
            raise GenerationalExecutionError("recipe_descriptor_mismatch")
        return
    if recipe.recipe_id != BL_RECIPE_ID or recipe.version != "1":
        raise GenerationalExecutionError("unknown_execution_recipe")
    params = recipe.params or {}
    treatment = params.get("treatment")
    if type(treatment) is not str or treatment not in BL_TREATMENTS:
        raise GenerationalExecutionError("recipe_treatment_invalid")
    if (recipe.intervention_id is None) != (treatment != "contact"):
        raise GenerationalExecutionError("recipe_intervention_mismatch")
    if treatment == "single_cohort":
        if lifecycle.demographic_policy_id != "disabled":
            raise GenerationalExecutionError("single_cohort_requires_disabled")
    elif lifecycle.demographic_policy_id != "generational_interval_entry":
        raise GenerationalExecutionError(
            "generational_treatment_requires_schedule"
        )


@dataclass(frozen=True, slots=True)
class GenerationalExecutionContext:
    """Injected archival, reader, and factory context for one assignment."""

    artifact_root: Path
    source_identity: dict[str, object]
    recipe: GenerationalExecutionRecipe
    factories: RunnerDependencyFactories
    reader: HistoricalBoundaryReader | None = None
    attempt_id: str = "single"
    cadence_ticks: int | None = None
    sample_on_generation_change: bool = True
    configurator: Callable[[SimulationRunner], object] | None = None

    def preflight(self, config: SimulationRunnerConfig) -> None:
        _validate_recipe(self.recipe, config)
        if config.persistence.durable and self.factories.run_repository is None:
            raise GenerationalExecutionError("durable_repository_required")
        if self.cadence_ticks is not None and self.reader is None:
            raise GenerationalExecutionError("historical_reader_required")


class _BoundaryReader:
    def __init__(self) -> None:
        self._last = 0

    async def reference(
        self, run_id: str, boundary_tick: int
    ) -> HistoricalBoundaryReference:
        from experiments.generational_artifacts import SnapshotReference

        return HistoricalBoundaryReference(
            revision=boundary_tick,
            objective_commit_hash=f"{boundary_tick:064d}",
            snapshot_ref=SnapshotReference(
                snapshot_id=f"snapshot-{boundary_tick}",
                integrity_hash=f"{boundary_tick:064d}",
                next_tick=boundary_tick,
            ),
        )


async def execute_generational_assignment(
    assignment: ExperimentAssignment,
    context: GenerationalExecutionContext,
) -> ExperimentArmResult:
    """Execute one generational assignment and complete its archive."""
    config = assignment.runner_config
    context.preflight(config)
    session = open_generational_archive(
        config=config,
        run_id=assignment.run_id,
        root=context.artifact_root,
        attempt_id=context.attempt_id,
        code_revision=str(context.source_identity["code_revision"]),
        source_clean=bool(context.source_identity["source_clean"]),
        source_artifact_digest=context.source_identity.get(  # type: ignore[arg-type]
            "source_artifact_digest"
        ),
        recipe=context.recipe,
    )
    reader = context.reader if context.reader is not None else _BoundaryReader()
    factories = session.dependencies(
        reader=reader,
        cadence_ticks=context.cadence_ticks,
        sample_on_generation_change=context.sample_on_generation_change,
        base=context.factories,
    )
    try:
        async with await SimulationRunner.from_config(
            config, run_id=assignment.run_id, factories=factories
        ) as runner:
            if context.configurator is not None:
                context.configurator(runner)
            elif config.experiment is not None:
                arbiter = generational_runner_arbiter(
                    assignment.condition_id, config
                )
                if arbiter is not None:
                    runner.set_intervention_arbiter(arbiter)
            result = await runner.run()
            committed_events = tuple(runner.engine.export_events().events)
            traces = await runner.export_regional_destination_traces()
        from experiments.composition import (
            regional_destination_evidence_rows_from_traces,
        )

        evidence = (
            None
            if traces is None
            else regional_destination_evidence_rows_from_traces(traces)
        )
        session.write_completion(result)
    except Exception as exc:
        store = session.store
        try:
            store.write_failure(
                {
                    "boundary_tick": 0,
                    "failure_hash": "0" * 64,
                    "manifest_hash": session.manifest_hash,
                    "objective_committed": False,
                    "owners_finalized": False,
                    "reason_code": type(exc).__name__,
                    "run_id": assignment.run_id.value,
                    "schema_version": "generational-failure-v1",
                    "stage": "execution",
                    "stop_evidence": None,
                }
            )
        except Exception:
            pass
        raise
    fingerprint = runner_config_fingerprint(config)
    arm = ExperimentArmResult(
        assignment=assignment,
        runner_result=result,
        config_fingerprint=fingerprint,
        committed_events=committed_events,
        regional_destination_evidence=evidence,
    )
    metrics = collect_for_experiment(arm)
    return ExperimentArmResult(
        assignment=assignment,
        runner_result=result,
        config_fingerprint=fingerprint,
        metrics=metrics,
        committed_events=committed_events,
        regional_destination_evidence=evidence,
    )


__all__ = [
    "BL_RECIPE_ID",
    "BL_TREATMENTS",
    "PLAIN_RECIPE_ID",
    "GenerationalExecutionContext",
    "GenerationalExecutionError",
    "execute_generational_assignment",
]
