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
