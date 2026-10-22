"""Immutable generational recording-usage artifacts."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from experiments.generational_artifacts import (
    GenerationalArtifactError,
    GenerationalUsageStore,
    decode_recording_usage_row,
    encode_recording_usage_row,
)
from simulation.generational_control import RecordingUsageEvidence


def _evidence(*, tick: int = 1, request_id: str = "req-1") -> RecordingUsageEvidence:
    return RecordingUsageEvidence(
        agent_id="agent-1",
        tick=tick,
        component="reconstructive_memory",
        request_id=request_id,
        lookup_mode="by_cache_key",
        namespace="run-1",
        cache_key="cache-key",
        record_integrity_hash="a" * 64,
        prompt_identity={"name": "recall", "version": "v1", "digest": "b" * 64},
        response_schema_identity={"qualname": "memory.Out", "digest": "c" * 64},
    )


def test_usage_row_roundtrip_and_self_hash(tmp_path: Path) -> None:
    payload = encode_recording_usage_row(_evidence(), run_id="run-1")
    row = decode_recording_usage_row(payload, run_id="run-1")
    assert row["schema_version"] == "generational-recording-usage-v1"
    assert row["request_id"] == "req-1"
    store = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    store.put_usage(_evidence())
    assert store.count() == 1
    assert store.usage_index_digest()


def test_duplicate_same_bytes_is_idempotent_and_conflict_fails(
    tmp_path: Path,
) -> None:
    store = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    store.put_usage(_evidence())
    store.put_usage(_evidence())
    assert store.count() == 1
    conflicting = replace(_evidence(), cache_key="different-cache-key")
    with pytest.raises(GenerationalArtifactError, match="artifact_conflict"):
        store.put_usage(conflicting)


def test_digest_is_order_independent(tmp_path: Path) -> None:
    first = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    first.put_usage(_evidence(request_id="req-1"))
    first.put_usage(_evidence(request_id="req-2", tick=2))
    second = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    second.put_usage(_evidence(request_id="req-2", tick=2))
    second.put_usage(_evidence(request_id="req-1"))
    assert first.usage_index_digest() == second.usage_index_digest()


@pytest.mark.parametrize("segment", ["../escape", "a/b", ".", "", "a" * 65])
def test_unsafe_path_segments_rejected(tmp_path: Path, segment: str) -> None:
    with pytest.raises(GenerationalArtifactError, match="unsafe_path_segment"):
        GenerationalUsageStore(root=tmp_path, run_id=segment)


def test_tampered_payload_hash_is_rejected(tmp_path: Path) -> None:
    store = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    store.put_usage(_evidence())
    path = next(store.usage_dir.glob("*.json"))
    payload = path.read_bytes().replace(
        b'"request_id":"req-1"', b'"request_id":"req-x"'
    )
    path.write_bytes(payload)
    with pytest.raises(GenerationalArtifactError, match="payload_hash_mismatch"):
        store.row_refs()


def _manifest_payload() -> dict[str, object]:
    return {
        "attempt_id": "single",
        "assignment": {
            "cell_id": None,
            "condition_id": "bl-on",
            "condition_ordinal": 0,
            "experiment_id": "generational@1",
            "matrix_id": None,
            "replicate_index": 0,
            "seed_ordinal": 0,
        },
        "cognition_fingerprint": "a" * 64,
        "config_fingerprint": "b" * 64,
        "config_ref": {"path": "run-1/single/config.json", "sha256": "c" * 64},
        "environment_identity": {
            "dependency_versions": {"pytest": "9.1.1"},
            "package_version": "0.1.0",
            "platform": "linux",
            "python_implementation": "CPython",
            "python_version": "3.12.14",
        },
        "execution_recipe": {
            "intervention_id": None,
            "intervention_params": {},
            "intervention_version": None,
            "params": {"mode": "standalone"},
            "recipe_id": "generational-standalone",
            "version": "v1",
        },
        "history_policy": {
            "criterion_cadence_ticks": 1,
            "historical_checkpoint_cadence_ticks": None,
            "sample_on_generation_change": True,
        },
        "manifest_hash": "0" * 64,
        "provider_identity": {
            "adapter_kind": "deterministic_fake",
            "exact_reproducibility": "false",
            "lookup_mode": None,
            "model": None,
            "recording_artifact_id": None,
            "recording_namespace": None,
            "recording_policy": "deterministic_fake",
        },
        "run_id": "run-1",
        "scenario_fingerprint": "d" * 64,
        "schema_version": "generational-run-manifest-v1",
        "seed_manifest": {
            "channels": [
                {
                    "algorithm_version": "derivation-v3-stream-v1",
                    "draw_usage": "sampled",
                    "identity_selector": "stochastic_identity",
                    "name": "world",
                    "namespace": "objective",
                    "scope_fields": ["seed"],
                }
            ],
            "derivation_version": "derivation-v3",
            "initialization_identity": {
                "lifespan_distribution_hash": "e" * 64,
                "parameter_distributions_hash": "f" * 64,
                "profile_id": "species_default_v1",
            },
            "physical_rules_fingerprint": "1" * 64,
            "run_id": "run-1",
            "schedule_fingerprint": "2" * 64,
            "seed": 23,
            "stochastic_identity": "generational",
        },
        "source_identity": {
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
    }


def _history_payload() -> dict[str, object]:
    return {
        "boundary_tick": 4,
        "community_ref": None,
        "evidence_ref": None,
        "last_completed_tick": 3,
        "objective_commit_hash": "3" * 64,
        "payload_hash": "0" * 64,
        "population_progress": {"boundary_tick": 4},
        "revision": 4,
        "run_id": "run-1",
        "sample_reasons": ["cadence"],
        "schema_version": "generational-history-v1",
        "snapshot_ref": {
            "integrity_hash": "4" * 64,
            "next_tick": 4,
            "snapshot_id": "snap-4",
        },
        "stop_evidence": None,
    }


def _completion_payload() -> dict[str, object]:
    return {
        "completion_hash": "0" * 64,
        "execution_recipe_hash": "5" * 64,
        "final_progress": {"boundary_tick": 4},
        "history_refs": [],
        "manifest_hash": "6" * 64,
        "recording_usage_ref": {"count": 0, "row_refs": [], "sha256": "7" * 64},
        "result_document": {"schema_version": "runner-result-v3"},
        "run_id": "run-1",
        "schema_version": "generational-completion-v1",
        "seed_manifest_hash": "8" * 64,
        "source_identity": {
            "code_revision": "abc123",
            "source_artifact_digest": None,
            "source_clean": True,
        },
    }


def _failure_payload() -> dict[str, object]:
    return {
        "boundary_tick": 3,
        "failure_hash": "0" * 64,
        "manifest_hash": "a" * 64,
        "objective_committed": True,
        "owners_finalized": False,
        "reason_code": "observer_failure",
        "run_id": "run-1",
        "schema_version": "generational-failure-v1",
        "stage": "boundary_observer",
        "stop_evidence": None,
    }


def test_exact_document_self_hash_roundtrip_and_tamper() -> None:
    from experiments.generational_artifacts import (
        decode_generational_document,
        encode_generational_document,
    )

    encoded = encode_generational_document(
        _manifest_payload(), schema_version="generational-run-manifest-v1"
    )
    decoded = decode_generational_document(
        encoded, schema_version="generational-run-manifest-v1"
    )
    assert decoded["manifest_hash"] != "0" * 64
    tampered = encoded.replace(b'"attempt_id":"single"', b'"attempt_id":"other"')
    with pytest.raises(GenerationalArtifactError, match="payload_hash_mismatch"):
        decode_generational_document(
            tampered, schema_version="generational-run-manifest-v1"
        )


def test_manifest_rejects_unknown_and_incomplete_identity() -> None:
    from experiments.generational_artifacts import encode_generational_document

    payload = _manifest_payload()
    payload["unknown"] = 1
    with pytest.raises(GenerationalArtifactError, match="invalid_keys"):
        encode_generational_document(
            payload, schema_version="generational-run-manifest-v1"
        )
    payload = _manifest_payload()
    source = dict(payload["source_identity"])  # type: ignore[arg-type]
    source["source_clean"] = False
    payload["source_identity"] = source
    with pytest.raises(
        GenerationalArtifactError, match="source_identity_incomplete"
    ):
        encode_generational_document(
            payload, schema_version="generational-run-manifest-v1"
        )


def test_store_writes_history_and_completion_and_freezes_attempt(
    tmp_path: Path,
) -> None:
    from experiments.generational_artifacts import GenerationalRunArtifactStore

    store = GenerationalRunArtifactStore(root=tmp_path, run_id="run-1")
    store.write_config(b'{"schema_version":"runner-config-v55"}')
    store.write_manifest(_manifest_payload())
    store.write_history(4, _history_payload())
    assert store.history_refs()
    payload = _completion_payload()
    payload["history_refs"] = list(store.history_refs())
    store.write_completion(payload)
    assert store.read_completion()["run_id"] == "run-1"
    with pytest.raises(GenerationalArtifactError, match="completed_attempt_immutable"):
        store.write_manifest(_manifest_payload())


def test_store_writes_failure_and_rejects_conflicting_history(
    tmp_path: Path,
) -> None:
    from experiments.generational_artifacts import GenerationalRunArtifactStore

    store = GenerationalRunArtifactStore(root=tmp_path, run_id="run-1")
    store.write_failure(_failure_payload())
    assert store.read_failure()["reason_code"] == "observer_failure"
    store.write_history(1, _history_payload())
    conflicting = _history_payload()
    conflicting["sample_reasons"] = ["terminal"]
    with pytest.raises(GenerationalArtifactError, match="artifact_conflict"):
        store.write_history(1, conflicting)


def _boundary(tick: int = 4, generation: int = 1):
    from simulation.generational_models import (
        CohortPopulationRow,
        GenerationalBoundary,
        GenerationPopulationRow,
        PopulationProgress,
    )

    progress = PopulationProgress(
        boundary_tick=tick,
        living_population=2,
        total_admitted=3,
        total_deaths=1,
        max_generation_index_seen=generation,
        cohorts=(
            CohortPopulationRow(
                generation_index=generation,
                entry_tick=tick - 1,
                cohort_id=f"cohort-{tick}",
                admitted=1,
                living=1,
                dead=0,
            ),
            CohortPopulationRow(
                generation_index=0,
                entry_tick=0,
                cohort_id="founders",
                admitted=2,
                living=1,
                dead=1,
            ),
        ),
        generations=(
            GenerationPopulationRow(
                generation_index=0, admitted=2, living=1, dead=1
            ),
            GenerationPopulationRow(
                generation_index=generation, admitted=1, living=1, dead=0
            ),
        ),
    )
    return GenerationalBoundary(
        progress=progress,
        objective_revision=tick,
        last_completed_tick=None if tick == 0 else tick - 1,
    )


class _Reader:
    def __init__(self, next_tick: int) -> None:
        self.next_tick = next_tick

    async def reference(self, run_id: str, boundary_tick: int):
        from experiments.generational_artifacts import (
            HistoricalBoundaryReference,
            SnapshotReference,
        )

        return HistoricalBoundaryReference(
            revision=boundary_tick,
            objective_commit_hash=f"{boundary_tick:064d}",
            snapshot_ref=SnapshotReference(
                snapshot_id=f"snap-{self.next_tick}",
                integrity_hash=f"{self.next_tick:064d}",
                next_tick=self.next_tick,
            ),
        )


@pytest.mark.asyncio
async def test_observer_writes_cadence_generation_and_terminal(tmp_path: Path) -> None:
    from experiments.generational_artifacts import (
        GenerationalHistoryObserver,
        GenerationalRunArtifactStore,
    )

    store = GenerationalRunArtifactStore(root=tmp_path, run_id="run-1")
    observer = GenerationalHistoryObserver(
        store=store,
        reader=_Reader(next_tick=4),
        cadence_ticks=2,
        sample_on_generation_change=True,
    )
    await observer.observe(_boundary(tick=4, generation=1), None)
    refs = store.history_refs()
    assert len(refs) == 1
    document = __import__("json").loads(
        (tmp_path / refs[0]["path"]).read_bytes()
    )
    assert document["sample_reasons"] == ["cadence", "generation_change"]


@pytest.mark.asyncio
async def test_observer_rejects_cadence_without_exact_snapshot(tmp_path: Path) -> None:
    from experiments.generational_artifacts import (
        GenerationalHistoryObserver,
        GenerationalRunArtifactStore,
    )

    observer = GenerationalHistoryObserver(
        store=GenerationalRunArtifactStore(root=tmp_path, run_id="run-1"),
        reader=_Reader(next_tick=2),
        cadence_ticks=4,
        sample_on_generation_change=False,
    )
    with pytest.raises(
        GenerationalArtifactError, match="cadence_snapshot_missing"
    ):
        await observer.observe(_boundary(tick=4, generation=1), None)


def test_source_identity_preflight() -> None:
    from experiments.generational_artifacts import source_identity_preflight

    assert source_identity_preflight(
        code_revision="abc", source_clean=True, source_artifact_digest=None
    )["source_clean"] is True
    with pytest.raises(
        GenerationalArtifactError, match="clean_source_assertion_required"
    ):
        source_identity_preflight(
            code_revision="abc", source_clean=False, source_artifact_digest=None
        )


def test_completion_written_after_history_and_usage(tmp_path: Path) -> None:
    from experiments.generational_artifacts import (
        CompletionInputs,
        GenerationalRunArtifactStore,
        GenerationalUsageStore,
        write_completion,
    )

    store = GenerationalRunArtifactStore(root=tmp_path, run_id="run-1")
    usage = GenerationalUsageStore(root=tmp_path, run_id="run-1")
    usage.put_usage(_evidence())
    store.write_manifest(_manifest_payload())
    store.write_history(4, _history_payload())
    encoded = write_completion(
        store,
        CompletionInputs(
            run_id="run-1",
            manifest_hash="a" * 64,
            result_document={"schema_version": "runner-result-v3"},
            seed_manifest_hash="b" * 64,
            source_identity={
                "code_revision": "abc",
                "source_artifact_digest": None,
                "source_clean": True,
            },
            execution_recipe_hash="c" * 64,
            final_progress={"boundary_tick": 4},
            recording_usage_ref={
                "count": usage.count(),
                "row_refs": [list(row) for row in usage.row_refs()],
                "sha256": usage.usage_index_digest(),
            },
            history_refs=store.history_refs(),
        ),
    )
    assert encoded
    assert store.read_completion()["history_refs"]


def test_community_sample_artifact_roundtrip(tmp_path: Path) -> None:
    from experiments.generational_artifacts import GenerationalRunArtifactStore

    store = GenerationalRunArtifactStore(root=tmp_path, run_id="run-1")
    ref = store.write_community_sample(4, {"living_count": 2})
    assert ref["path"].endswith("community-samples/000000000004.json")
    payload = store.read_community_sample(4)
    assert payload["living_count"] == 2
    assert payload["schema_version"] == "generational-community-sample-v1"


def test_duplicate_json_keys_are_rejected() -> None:
    from experiments.generational_artifacts import decode_generational_document

    raw = (
        b'{"schema_version":"generational-history-v1",'
        b'"schema_version":"generational-history-v1"}'
    )
    with pytest.raises(GenerationalArtifactError, match="duplicate_json_key"):
        decode_generational_document(
            raw, schema_version="generational-history-v1"
        )


def test_symlinked_attempt_directory_is_rejected(tmp_path: Path) -> None:
    from experiments.generational_artifacts import GenerationalRunArtifactStore

    root = tmp_path / "root"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "run-1").symlink_to(elsewhere, target_is_directory=True)
    store = GenerationalRunArtifactStore(root=root, run_id="run-1")
    with pytest.raises(GenerationalArtifactError, match="unsafe_path"):
        store.write_config(b"{}")
