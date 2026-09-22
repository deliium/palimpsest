"""Evidence Manifest contracts: immutable high-water marks and hashing."""

from __future__ import annotations

import pytest

from simulation.evidence import (
    EVIDENCE_MANIFEST_SCHEMA_VERSION,
    EvidenceHighWaterMarks,
    EvidenceManifest,
    EvidenceManifestError,
    build_evidence_manifest,
    clamp_sequence_to_high_water,
    manifest_hash_prefix,
    manifest_idempotency_material,
)


def _marks(**overrides: int) -> EvidenceHighWaterMarks:
    base = {
        "direct_memories": 2,
        "communicated_memories": 1,
        "reconstructions": 0,
        "beliefs": 0,
        "relationships": 0,
        "goals": 0,
        "resolutions": 0,
        "truth_specs": 1,
    }
    base.update(overrides)
    return EvidenceHighWaterMarks(**base)


def test_build_evidence_manifest_is_deterministic() -> None:
    first = build_evidence_manifest(
        run_id="run-1",
        objective_commit_hash="a" * 64,
        high_water=_marks(),
    )
    second = build_evidence_manifest(
        run_id="run-1",
        objective_commit_hash="a" * 64,
        high_water=_marks(),
    )
    assert first == second
    assert first.schema_version == EVIDENCE_MANIFEST_SCHEMA_VERSION
    assert len(first.manifest_hash) == 64
    assert manifest_idempotency_material(first) == first.manifest_hash
    assert manifest_hash_prefix(first) == first.manifest_hash[:12]


def test_manifest_hash_changes_with_high_water() -> None:
    a = build_evidence_manifest(
        run_id="run-1",
        objective_commit_hash="b" * 64,
        high_water=_marks(direct_memories=1),
    )
    b = build_evidence_manifest(
        run_id="run-1",
        objective_commit_hash="b" * 64,
        high_water=_marks(direct_memories=2),
    )
    assert a.manifest_hash != b.manifest_hash


def test_manifest_rejects_tampered_hash() -> None:
    with pytest.raises(EvidenceManifestError) as exc:
        EvidenceManifest(
            schema_version=EVIDENCE_MANIFEST_SCHEMA_VERSION,
            run_id="run-1",
            objective_commit_hash="c" * 64,
            high_water=_marks(),
            manifest_hash="d" * 64,
        )
    assert exc.value.code == "manifest_hash_mismatch"


def test_manifest_rejects_unsupported_version() -> None:
    with pytest.raises(EvidenceManifestError) as exc:
        EvidenceManifest(
            schema_version="evidence-manifest-v0",
            run_id="run-1",
            objective_commit_hash="e" * 64,
            high_water=_marks(),
            manifest_hash="f" * 64,
        )
    assert exc.value.code == "unsupported_manifest_version"


def test_clamp_sequence_to_high_water() -> None:
    items = ("a", "b", "c", "d")
    assert clamp_sequence_to_high_water(items, 2, source_label="traces") == (
        "a",
        "b",
    )
    assert clamp_sequence_to_high_water(items, 10, source_label="traces") == items
    assert clamp_sequence_to_high_water(items, 0, source_label="traces") == ()


def test_high_water_rejects_negative() -> None:
    with pytest.raises(ValueError):
        EvidenceHighWaterMarks(
            direct_memories=-1,
            communicated_memories=0,
            reconstructions=0,
            beliefs=0,
            relationships=0,
            goals=0,
            resolutions=0,
            truth_specs=0,
        )
