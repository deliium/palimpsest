"""Unit tests for canonical benchmark sibling artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.civilization_benchmark_artifacts import (
    RUN_SCHEMA_ID,
    SUITE_SCHEMA_ID,
    BenchmarkArtifactError,
    BenchmarkArtifactStore,
    BenchmarkRunReference,
    build_run_document,
    decode_document,
    encode_document,
    run_passes,
)
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkExecutionStatus,
    V3BenchmarkLane,
    V3BenchmarkPhenomenon,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE

_SOURCE = {
    "code_revision": "deadbeef",
    "source_clean": True,
    "source_artifact_digest": None,
}


def _result(
    *,
    passing: bool = True,
    scenario_id: str = V3_BENCH_01_BLANK_SLATE,
) -> V3BenchmarkRunResult:
    check = V3BenchmarkCheck(
        selector_id="new_agent_initialization_evidence",
        selector_version=1,
        status=(
            V3BenchmarkCheckStatus.PASS
            if passing
            else V3BenchmarkCheckStatus.UNEXECUTED
        ),
        reason_code=("blank_slate_measured" if passing else "probe_unavailable"),
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if passing
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            V3BenchmarkSourceReference(
                source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
                reference_id="agent-entrant-1",
                owner_id="agent-entrant-1",
            ),
        )
        if passing
        else (),
        boundary_start_tick=0,
        boundary_end_tick=4,
        numerator=1,
        denominator=1,
    )
    return V3BenchmarkRunResult(
        scenario_id=scenario_id,
        lane=V3BenchmarkLane.RESEARCH,
        execution_status=V3BenchmarkExecutionStatus.COMPLETED,
        declared_horizon=4,
        ticks_committed=4,
        coverage=V3BenchmarkCoverage.EXERCISED,
        evidence=(
            V3BenchmarkEvidenceAvailability.COMPLETE
            if passing
            else V3BenchmarkEvidenceAvailability.PARTIAL
        ),
        phenomenon=V3BenchmarkPhenomenon.NOT_DETECTED if passing else (
            V3BenchmarkPhenomenon.UNKNOWN
        ),
        checks=(check,),
    )


def _document(passing: bool = True) -> dict[str, object]:
    return build_run_document(
        scenario_id=V3_BENCH_01_BLANK_SLATE,
        lane=V3BenchmarkLane.RESEARCH,
        profile=V3BenchmarkProfile.SMOKE,
        arm_id="observation",
        seed=23,
        source_identity=_SOURCE,
        config_fingerprint="a" * 64,
        recipe={"recipe_id": "v3-benchmark", "version": "1"},
        run_id="run-1",
        result=_result(passing=passing),
    )


def test_document_serialization_is_deterministic() -> None:
    first = _document()
    second = _document()
    assert encode_document(first) == encode_document(second)
    decoded = decode_document(encode_document(first), schema_id=RUN_SCHEMA_ID)
    assert decoded["scenario_id"] == V3_BENCH_01_BLANK_SLATE
    assert decoded["artifact_hash"] == first["artifact_hash"]
    assert run_passes(decoded) is True


def test_tampered_bytes_are_rejected() -> None:
    payload = encode_document(_document())
    data = json.loads(payload)
    data["execution"]["ticks_committed"] = 3
    tampered = json.dumps(data).encode("utf-8")
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        decode_document(tampered, schema_id=RUN_SCHEMA_ID)
    assert excinfo.value.code == "artifact_hash_mismatch"


def test_unknown_fields_and_missing_fields_are_rejected() -> None:
    document = _document()
    document["unexpected"] = True
    document.pop("artifact_hash")
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        decode_document(encode_document(document), schema_id=RUN_SCHEMA_ID)
    assert excinfo.value.code == "unknown_fields"


def test_incomplete_run_fails_the_passing_gate() -> None:
    incomplete = _document(passing=False)
    assert run_passes(incomplete) is False
    decoded = decode_document(encode_document(incomplete), schema_id=RUN_SCHEMA_ID)
    assert decoded["outcome"]["evidence"] == "partial"


def test_publish_and_verify_round_trip(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    document = _document()
    reference = store.publish_run(document)
    assert isinstance(reference, BenchmarkRunReference)
    suite = store.publish_suite(
        source_identity=_SOURCE,
        run_references=(reference,),
        required=((V3_BENCH_01_BLANK_SLATE, "research"),),
    )
    assert suite["complete"] is True
    assert suite["status"] == "complete"
    assert store.verify(source_identity=_SOURCE, require_complete=True)["complete"]

    # Re-publishing identical bytes is idempotent; different bytes collide.
    assert store.publish_run(document) == reference
    other = _document(passing=False)
    with pytest.raises(BenchmarkArtifactError):
        decode_document(
            encode_document(
                {
                    **other,
                    "artifact_hash": reference.artifact_hash,
                }
            ),
            schema_id=RUN_SCHEMA_ID,
        )


def test_missing_required_gate_marks_suite_incomplete(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    reference = store.publish_run(_document(passing=False))
    suite = store.publish_suite(
        source_identity=_SOURCE,
        run_references=(reference,),
        required=((V3_BENCH_01_BLANK_SLATE, "research"),),
    )
    assert suite["complete"] is False
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        store.verify(source_identity=_SOURCE, require_complete=True)
    assert excinfo.value.code == "incomplete_suite"


def test_missing_reference_blocks_suite_publication(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    reference = BenchmarkRunReference(
        scenario_id=V3_BENCH_01_BLANK_SLATE,
        lane="research",
        arm_id="observation",
        relative_path="runs/missing.json",
        artifact_hash="a" * 64,
    )
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        store.publish_suite(
            source_identity=_SOURCE,
            run_references=(reference,),
            required=((V3_BENCH_01_BLANK_SLATE, "research"),),
        )
    assert excinfo.value.code == "missing_reference"


def test_path_escape_and_symlink_are_rejected(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        store.verify(
            source_identity=_SOURCE,
            require_complete=False,
        )
    assert excinfo.value.code == "missing_suite"

    outside = tmp_path.parent / "outside-suite.json"
    outside.write_text("{}")
    link = tmp_path / "suite.json"
    link.symlink_to(outside)
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        store.verify(source_identity=_SOURCE, require_complete=False)
    assert excinfo.value.code == "path_escape"

    from experiments.civilization_benchmark_artifacts import _safe_child

    with pytest.raises(BenchmarkArtifactError):
        _safe_child(tmp_path.resolve(), "../escape.json")


def test_source_identity_mismatch_is_rejected(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    reference = store.publish_run(_document())
    store.publish_suite(
        source_identity=_SOURCE,
        run_references=(reference,),
        required=((V3_BENCH_01_BLANK_SLATE, "research"),),
    )
    with pytest.raises(BenchmarkArtifactError) as excinfo:
        store.verify(
            source_identity={**_SOURCE, "code_revision": "other"},
            require_complete=False,
        )
    assert excinfo.value.code == "source_identity_mismatch"


def test_suite_schema_round_trip(tmp_path: Path) -> None:
    store = BenchmarkArtifactStore(tmp_path, profile=V3BenchmarkProfile.SMOKE)
    reference = store.publish_run(_document())
    suite = store.publish_suite(
        source_identity=_SOURCE,
        run_references=(reference,),
        required=((V3_BENCH_01_BLANK_SLATE, "research"),),
    )
    encoded = (tmp_path / "suite.json").read_bytes()
    decoded = decode_document(encoded, schema_id=SUITE_SCHEMA_ID)
    assert decoded["artifact_hash"] == suite["artifact_hash"]
