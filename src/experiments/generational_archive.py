"""Immutable generational archive construction and completion."""

from __future__ import annotations

import importlib.metadata
import json
import logging
import platform
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.generational_artifacts import (
    CompletionInputs,
    GenerationalHistoryObserver,
    GenerationalRunArtifactStore,
    GenerationalUsageStore,
    HistoricalBoundaryReader,
    source_identity_preflight,
    write_completion,
)
from simulation.generational_control import (
    RecordingUsageEvidence,
    RecordingUsageSink,
)
from simulation.generational_seeds import (
    GenerationalSeedManifest,
    build_generational_seed_manifest,
    canonical_sha256,
)
from simulation.models import RunId
from simulation.runner import RunnerDependencyFactories
from simulation.runner_models import (
    SimulationRunnerConfig,
    SimulationRunnerResult,
)
from simulation.runner_serialization import (
    cognition_fingerprint,
    runner_config_fingerprint,
)
from world.models import physical_rules_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_archive"
)


def _resolve_package_version() -> str:
    try:
        return importlib.metadata.version("palimpsest")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0+local"


@dataclass(frozen=True, slots=True)
class GenerationalExecutionRecipe:
    recipe_id: str = "generational-standalone"
    version: str = "v1"
    params: dict[str, object] | None = None
    intervention_id: str | None = None
    intervention_version: str | None = None
    intervention_params: dict[str, object] | None = None

    def canonical_payload(self) -> dict[str, object]:
        return {
            "intervention_id": self.intervention_id,
            "intervention_params": (
                self.intervention_params
                if self.intervention_params is not None
                else {}
            ),
            "intervention_version": self.intervention_version,
            "params": self.params if self.params is not None else {},
            "recipe_id": self.recipe_id,
            "version": self.version,
        }

    @property
    def recipe_hash(self) -> str:
        return canonical_sha256(self.canonical_payload())


def build_environment_identity() -> dict[str, object]:
    return {
        "dependency_versions": {},
        "package_version": _resolve_package_version(),
        "platform": platform.platform(),
        "python_implementation": platform.python_implementation(),
        "python_version": sys.version.split()[0],
    }


def build_provider_identity(
    config: SimulationRunnerConfig,
    recording_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    provider = config.provider
    identity = recording_identity or {}
    return {
        "adapter_kind": provider.adapter_kind.value,
        "exact_reproducibility": provider.exact_reproducibility.value,
        "lookup_mode": identity.get("lookup_mode"),
        "model": provider.model,
        "recording_artifact_id": identity.get("recording_artifact_id"),
        "recording_namespace": identity.get("recording_namespace"),
        "recording_policy": provider.recording_policy.value,
    }


def build_assignment_identity(
    config: SimulationRunnerConfig,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    experiment = config.experiment
    if experiment is None:
        identity: dict[str, object] = {
            "cell_id": None,
            "condition_id": "standalone",
            "condition_ordinal": 0,
            "experiment_id": "standalone",
            "matrix_id": None,
            "replicate_index": 0,
            "seed_ordinal": 0,
        }
    else:
        identity = {
            "cell_id": None,
            "condition_id": experiment.condition_id,
            "condition_ordinal": 0,
            "experiment_id": experiment.experiment_id,
            "matrix_id": None,
            "replicate_index": experiment.replicate_index,
            "seed_ordinal": experiment.seed_ordinal,
        }
    if overrides:
        for key in identity:
            if key in overrides and overrides[key] is not None:
                identity[key] = overrides[key]
    return identity


def build_manifest_payload(
    *,
    config: SimulationRunnerConfig,
    run_id: RunId,
    attempt_id: str,
    seed_manifest: GenerationalSeedManifest,
    config_ref: dict[str, str],
    source_identity: dict[str, object],
    recipe: GenerationalExecutionRecipe,
    recording_identity: dict[str, object] | None = None,
    assignment_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    generational = config.generational_run
    if generational is None:
        raise ValueError("manifest requires generational_run")
    return {
        "assignment": build_assignment_identity(config, assignment_overrides),
        "attempt_id": attempt_id,
        "cognition_fingerprint": cognition_fingerprint(config),
        "config_fingerprint": runner_config_fingerprint(config),
        "config_ref": config_ref,
        "environment_identity": build_environment_identity(),
        "execution_recipe": recipe.canonical_payload(),
        "history_policy": {
            "criterion_cadence_ticks": generational.criterion_cadence_ticks,
            "historical_checkpoint_cadence_ticks": (
                generational.historical_checkpoint_cadence_ticks
            ),
            "sample_on_generation_change": (
                generational.sample_on_generation_change
            ),
        },
        "manifest_hash": "0" * 64,
        "provider_identity": build_provider_identity(config, recording_identity),
        "run_id": run_id.value,
        "scenario_fingerprint": canonical_sha256(
            {
                "physical_rules": physical_rules_fingerprint(
                    config.scenario.physical_rules
                ),
                "world_id": config.scenario.world_id.value,
            }
        ),
        "schema_version": "generational-run-manifest-v1",
        "seed_manifest": seed_manifest.canonical_payload(),
        "source_identity": source_identity,
    }


class _UsageSink(RecordingUsageSink):
    def __init__(self, store: GenerationalUsageStore) -> None:
        self._store = store

    def put_usage(self, evidence: RecordingUsageEvidence) -> None:
        self._store.put_usage(evidence)


@dataclass(frozen=True, slots=True)
class GenerationalArchiveSession:
    run_id: RunId
    config: SimulationRunnerConfig
    store: GenerationalRunArtifactStore
    usage_store: GenerationalUsageStore
    seed_manifest: GenerationalSeedManifest
    manifest_hash: str
    source_identity: dict[str, object]
    recipe: GenerationalExecutionRecipe

    def dependencies(
        self,
        *,
        reader: HistoricalBoundaryReader,
        cadence_ticks: int | None,
        sample_on_generation_change: bool,
        base: RunnerDependencyFactories | None = None,
        community_sampler: Callable[[object], object] | None = None,
    ) -> RunnerDependencyFactories:
        observer = GenerationalHistoryObserver(
            store=self.store,
            reader=reader,
            cadence_ticks=cadence_ticks,
            sample_on_generation_change=sample_on_generation_change,
            community_sampler=community_sampler,
        )
        if base is None:
            return RunnerDependencyFactories(
                boundary_observer=observer,
                recording_usage_sink=_UsageSink(self.usage_store),
            )
        return base.with_generational_control(
            boundary_observer=observer,
            recording_usage_sink=_UsageSink(self.usage_store),
        )

    def write_completion(self, result: SimulationRunnerResult) -> bytes:
        from simulation.generational_serialization import (
            encode_population_progress,
        )
        from simulation.runner_models import runner_stop_is_failure
        from simulation.runner_serialization import (
            build_runner_result_document,
            encode_runner_result_document,
        )

        if runner_stop_is_failure(result.stop_reason):
            raise ValueError("completion requires a successful stop reason")
        if result.generational_progress is None:
            raise ValueError("completion requires generational progress")
        result_document = build_runner_result_document(
            result=result, config=self.config
        )
        progress = result.generational_progress
        refs = self.store.history_refs()
        return write_completion(
            self.store,
            CompletionInputs(
                run_id=self.run_id.value,
                manifest_hash=self.manifest_hash,
                result_document=json.loads(
                    encode_runner_result_document(result_document)
                ),
                seed_manifest_hash=self.seed_manifest.manifest_hash,
                source_identity=self.source_identity,
                execution_recipe_hash=self.recipe.recipe_hash,
                final_progress=encode_population_progress(progress),
                recording_usage_ref={
                    "count": self.usage_store.count(),
                    "row_refs": [list(row) for row in self.usage_store.row_refs()],
                    "sha256": self.usage_store.usage_index_digest(),
                },
                history_refs=refs,
            ),
        )


def open_generational_archive(
    *,
    config: SimulationRunnerConfig,
    run_id: RunId,
    root: Path | str,
    attempt_id: str = "single",
    code_revision: str,
    source_clean: bool,
    source_artifact_digest: str | None = None,
    recipe: GenerationalExecutionRecipe | None = None,
    recording_identity: dict[str, object] | None = None,
    assignment_overrides: dict[str, object] | None = None,
) -> GenerationalArchiveSession:
    if config.generational_run is None:
        raise ValueError("generational archive requires generational_run")
    source_identity = source_identity_preflight(
        code_revision=code_revision,
        source_clean=source_clean,
        source_artifact_digest=source_artifact_digest,
    )
    store = GenerationalRunArtifactStore(
        root=Path(root), run_id=run_id.value, attempt_id=attempt_id
    )
    config_bytes = __import__(
        "simulation.runner_serialization", fromlist=["encode_runner_config"]
    ).encode_runner_config(config)
    config_ref = dict(
        zip(
            ("path", "sha256"),
            store.write_config(config_bytes),
            strict=True,
        )
    )
    seed_manifest = build_generational_seed_manifest(config, run_id)
    active_recipe = recipe if recipe is not None else GenerationalExecutionRecipe()
    payload = build_manifest_payload(
        config=config,
        run_id=run_id,
        attempt_id=attempt_id,
        seed_manifest=seed_manifest,
        config_ref=config_ref,
        source_identity=source_identity,
        recipe=active_recipe,
        recording_identity=recording_identity,
        assignment_overrides=assignment_overrides,
    )
    store.write_manifest(payload)
    manifest_hash = store.read_manifest()["manifest_hash"]
    if not isinstance(manifest_hash, str):
        raise ValueError("manifest_hash must be str")
    session = GenerationalArchiveSession(
        run_id=run_id,
        config=config,
        store=store,
        usage_store=GenerationalUsageStore(
            root=Path(root), run_id=run_id.value, attempt_id=attempt_id
        ),
        seed_manifest=seed_manifest,
        manifest_hash=manifest_hash,
        source_identity=source_identity,
        recipe=active_recipe,
    )
    _LOG.info(
        "generational_archive_opened run_id=%s attempt_id=%s",
        run_id.value,
        attempt_id,
    )
    return session


__all__ = [
    "GenerationalArchiveSession",
    "GenerationalExecutionRecipe",
    "build_assignment_identity",
    "build_environment_identity",
    "build_manifest_payload",
    "build_provider_identity",
    "open_generational_archive",
]
