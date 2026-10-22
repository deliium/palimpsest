"""Verify and adopt completed generational archives for matrix resume."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.generational_artifacts import (
    GENERATIONAL_COMPLETION_SCHEMA_VERSION,
    GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION,
    GenerationalArtifactError,
    GenerationalRunArtifactStore,
    GenerationalUsageStore,
)
from simulation.models import RunId
from simulation.runner_models import SimulationRunnerConfig
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_adoption"
)


@dataclass(frozen=True, slots=True)
class VerifiedGenerationalArchive:
    run_id: RunId
    attempt_id: str
    manifest: dict[str, object]
    completion: dict[str, object]


def _matching_attempt_dirs(root: Path, run_id: str) -> tuple[str, ...]:
    run_dir = root / run_id
    if not run_dir.exists():
        return ()
    attempts = tuple(
        sorted(
            (
                path.name
                for path in run_dir.iterdir()
                if path.is_dir()
                and (path / "manifest.json").exists()
                and (path / "completion.json").exists()
            ),
            key=lambda name: (name != "single", name),
        )
    )
    return attempts


def verify_completed_archive(
    *,
    root: Path,
    run_id: RunId,
    expected_config: SimulationRunnerConfig,
    expected_attempt_id: str | None = None,
    expected_code_revision: str | None = None,
) -> VerifiedGenerationalArchive | None:
    """Return a fully verified archive, or None when absent/incomplete."""
    attempts = (
        (expected_attempt_id,)
        if expected_attempt_id is not None
        else _matching_attempt_dirs(root, run_id.value)
    )
    for attempt_id in attempts:
        if attempt_id is None:
            continue
        store = GenerationalRunArtifactStore(
            root=root, run_id=run_id.value, attempt_id=attempt_id
        )
        try:
            manifest = store.read_manifest()
            completion = store.read_completion()
            _verify(manifest, completion, store, expected_config, run_id)
            if expected_code_revision is not None:
                source = manifest["source_identity"]
                if not isinstance(source, dict) or (
                    source.get("code_revision") != expected_code_revision
                ):
                    raise GenerationalArtifactError(
                        "archive_source_identity_drift", "source_identity"
                    )
        except (GenerationalArtifactError, FileNotFoundError, ValueError) as exc:
            _LOG.warning(
                "generational_archive_rejected run_id=%s attempt_id=%s code=%s",
                run_id.value,
                attempt_id,
                getattr(exc, "code", type(exc).__name__),
            )
            continue
        return VerifiedGenerationalArchive(
            run_id=run_id,
            attempt_id=attempt_id,
            manifest=manifest,
            completion=completion,
        )
    return None


def _verify(
    manifest: dict[str, object],
    completion: dict[str, object],
    store: GenerationalRunArtifactStore,
    expected_config: SimulationRunnerConfig,
    run_id: RunId,
) -> None:
    if manifest["schema_version"] != GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION:
        raise GenerationalArtifactError("archive_schema_mismatch", "manifest")
    if completion["schema_version"] != GENERATIONAL_COMPLETION_SCHEMA_VERSION:
        raise GenerationalArtifactError("archive_schema_mismatch", "completion")
    if manifest["run_id"] != run_id.value or completion["run_id"] != run_id.value:
        raise GenerationalArtifactError("archive_run_id_mismatch", "run_id")
    if completion["manifest_hash"] != manifest["manifest_hash"]:
        raise GenerationalArtifactError("archive_manifest_mismatch", "completion")
    if manifest["config_fingerprint"] != runner_config_fingerprint(expected_config):
        raise GenerationalArtifactError(
            "archive_config_fingerprint_drift", "config_fingerprint"
        )
    seed = manifest["seed_manifest"]
    if not isinstance(seed, dict) or seed.get("run_id") != run_id.value:
        raise GenerationalArtifactError("archive_seed_drift", "seed_manifest")
    assignment = manifest["assignment"]
    experiment = expected_config.experiment
    if not isinstance(assignment, dict):
        raise GenerationalArtifactError("archive_assignment_drift", "assignment")
    if experiment is not None:
        if (
            assignment.get("experiment_id") != experiment.experiment_id
            or assignment.get("condition_id") != experiment.condition_id
            or assignment.get("replicate_index") != experiment.replicate_index
            or assignment.get("seed_ordinal") != experiment.seed_ordinal
        ):
            raise GenerationalArtifactError(
                "archive_assignment_drift", "assignment"
            )
    history_refs = completion["history_refs"]
    if not isinstance(history_refs, list):
        raise GenerationalArtifactError("archive_history_drift", "history_refs")
    actual_refs = list(store.history_refs())
    if history_refs != actual_refs:
        raise GenerationalArtifactError("archive_history_drift", "history_refs")
    usage_ref = completion["recording_usage_ref"]
    if not isinstance(usage_ref, dict):
        raise GenerationalArtifactError("archive_usage_drift", "recording_usage_ref")
    usage_store = GenerationalUsageStore(
        root=store.root, run_id=store.run_id, attempt_id=store.attempt_id
    )
    if usage_ref.get("sha256") != usage_store.usage_index_digest():
        raise GenerationalArtifactError("archive_usage_drift", "recording_usage_ref")
    if usage_ref.get("count") != usage_store.count():
        raise GenerationalArtifactError("archive_usage_drift", "recording_usage_ref")


__all__ = [
    "VerifiedGenerationalArchive",
    "verify_completed_archive",
]
