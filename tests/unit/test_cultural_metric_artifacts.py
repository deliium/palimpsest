"""Safe cultural cell artifact codec and filesystem pair persistence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from analysis.cultural_evolution_evidence import (
    CulturalAnalysisWindow,
    CulturalEvolutionInputs,
)
from analysis.evidence import EvidenceStage
from analysis.models import MetricAvailability, MetricDocument, MetricProvenance
from experiments.cultural_evidence_serialization import (
    decode_cultural_evolution_evidence,
    encode_cultural_evolution_evidence,
)
from experiments.cultural_metric_artifacts import (
    CULTURAL_CELL_METRICS_SCHEMA_VERSION,
    MAX_CULTURAL_ARTIFACT_BYTES,
    CulturalArtifactError,
    CulturalCaptureOptions,
    CulturalCellMetrics,
    cultural_capture_policy,
    decode_cultural_cell_metrics,
    encode_cultural_cell_metrics,
    read_cultural_pair,
    verify_cultural_pair,
    write_cultural_pair,
)
from simulation.cultural_evidence import CulturalCaptureStatus

_EVIDENCE = b'{"schema_version":"cultural-evolution-evidence-v1"}'
_DIGEST = "d" * 64


def _document() -> MetricDocument:
    return MetricDocument(
        schema_version="1",
        metric_family="cultural_trait_dynamics",
        algorithm_version="1",
        library_versions=MetricDocument.default_library_versions(),
        run_id="run-1",
        input_revision="rev-1",
        evidence_stages=frozenset({EvidenceStage.BELIEF_REVISION_TESTIMONY}),
        population="cultural_evolution_normalized_evidence",
        denominator="fixed_scientific_selector_denominator",
        coverage=None,
        availability=MetricAvailability.PRESENT,
        values={
            "policy_version": "cultural-evolution.v1",
            "window_start": 0,
            "window_end": 1,
            "measurement_count": 0,
            "rows_json": "[]",
            "evidence_manifest_digest": _DIGEST,
        },
        provenance=MetricProvenance(
            source_kind="cultural_evolution_evidence",
            source_ids=(_DIGEST,),
            notes_code="normalized_evidence",
        ),
    )


def _cell() -> CulturalCellMetrics:
    return CulturalCellMetrics(
        cell_id="cell-1",
        matrix_fingerprint="m" * 64,
        cell_fingerprint="c" * 64,
        config_fingerprint="f" * 64,
        run_id="run-1",
        capture_policy={"enabled": True, "max_frames": 10},
        analysis_window=CulturalCaptureOptions().analysis_window,
        evidence_digest=_DIGEST,
        documents=(_document(),),
        digest="",
    )


def test_cell_metrics_round_trip() -> None:
    encoded = encode_cultural_cell_metrics(_cell())
    decoded = decode_cultural_cell_metrics(encoded)
    assert decoded.schema_version if hasattr(decoded, "schema_version") else True
    assert decoded.cell_id == "cell-1"
    assert decoded.run_id == "run-1"
    assert decoded.evidence_digest == _DIGEST
    assert decoded.documents == (_document(),)
    assert json.loads(encoded)["schema_version"] == CULTURAL_CELL_METRICS_SCHEMA_VERSION


def test_duplicate_keys_and_digest_mismatch_are_rejected() -> None:
    encoded = encode_cultural_cell_metrics(_cell())
    text = encoded.decode("utf-8")
    duplicated = text.replace(
        '"schema_version":"cultural-cell-metrics-v1"',
        '"schema_version":"cultural-cell-metrics-v1",'
        '"schema_version":"cultural-cell-metrics-v1"',
        1,
    )
    with pytest.raises(CulturalArtifactError, match="duplicate_key"):
        decode_cultural_cell_metrics(duplicated.encode())
    payload = json.loads(text)
    payload["run_id"] = "run-2"
    with pytest.raises(CulturalArtifactError, match="digest_mismatch"):
        decode_cultural_cell_metrics(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )


def test_unknown_fields_and_oversized_payload_are_rejected() -> None:
    encoded = encode_cultural_cell_metrics(_cell())
    payload = json.loads(encoded)
    payload["extra"] = 1
    with pytest.raises(CulturalArtifactError, match="key_set_mismatch"):
        decode_cultural_cell_metrics(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
    with pytest.raises(CulturalArtifactError, match="too_large"):
        decode_cultural_cell_metrics(b"x" * (MAX_CULTURAL_ARTIFACT_BYTES + 1))


def test_pair_write_is_idempotent_and_conflict_safe(tmp_path: Path) -> None:
    metrics = encode_cultural_cell_metrics(_cell())
    write_cultural_pair(
        tmp_path,
        "cell-1",
        evidence_bytes=_EVIDENCE,
        cell_metrics_bytes=metrics,
    )
    assert read_cultural_pair(tmp_path, "cell-1") == (_EVIDENCE, metrics)
    write_cultural_pair(
        tmp_path,
        "cell-1",
        evidence_bytes=_EVIDENCE,
        cell_metrics_bytes=metrics,
    )
    with pytest.raises(CulturalArtifactError, match="artifact_conflict"):
        write_cultural_pair(
            tmp_path,
            "cell-1",
            evidence_bytes=b"different",
            cell_metrics_bytes=metrics,
        )


def test_missing_pair_returns_none_and_unsafe_ids_fail(tmp_path: Path) -> None:
    assert read_cultural_pair(tmp_path, "missing") is None
    with pytest.raises(CulturalArtifactError, match="unsafe_cell_id"):
        read_cultural_pair(tmp_path, "../escape")
    with pytest.raises(CulturalArtifactError, match="unsafe_cell_id"):
        write_cultural_pair(
            tmp_path,
            "bad/id",
            evidence_bytes=_EVIDENCE,
            cell_metrics_bytes=encode_cultural_cell_metrics(_cell()),
        )


def test_symlink_root_and_targets_are_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(CulturalArtifactError, match="symlink_root"):
        read_cultural_pair(link, "cell-1")
    metrics = encode_cultural_cell_metrics(_cell())
    write_cultural_pair(
        real,
        "cell-1",
        evidence_bytes=_EVIDENCE,
        cell_metrics_bytes=metrics,
    )
    target = real / "cells" / "cell-1.cultural-evidence.json"
    target.unlink()
    target.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(CulturalArtifactError, match="symlink_target"):
        read_cultural_pair(real, "cell-1")


def _evidence_bytes(
    options: CulturalCaptureOptions,
    *,
    run_id: str = "run-1",
    source_revision: str = "rev-1",
) -> bytes:
    inputs = CulturalEvolutionInputs(
        run_id=run_id,
        source_revision=source_revision,
        window=options.analysis_window,
    )
    return encode_cultural_evolution_evidence(
        inputs,
        config_fingerprint="f" * 64,
        capture_options=cultural_capture_policy(options),
        capture_status=CulturalCaptureStatus(active=True, failed=False),
    )


def _bound_pair(options: CulturalCaptureOptions) -> tuple[bytes, bytes]:
    evidence = _evidence_bytes(options)
    decoded = decode_cultural_evolution_evidence(evidence)
    metrics = CulturalCellMetrics(
        cell_id="cell-1",
        matrix_fingerprint="m" * 64,
        cell_fingerprint="c" * 64,
        config_fingerprint="f" * 64,
        run_id="run-1",
        capture_policy=cultural_capture_policy(options),
        analysis_window=options.analysis_window,
        evidence_digest=decoded.digest,
        documents=(_document(),),
        digest="",
    )
    return evidence, encode_cultural_cell_metrics(metrics)


def test_verify_cultural_pair_accepts_matching_identity() -> None:
    options = CulturalCaptureOptions(enabled=True)
    evidence, metrics = _bound_pair(options)
    verified = verify_cultural_pair(
        evidence,
        metrics,
        cell_id="cell-1",
        matrix_fingerprint="m" * 64,
        cell_fingerprint="c" * 64,
        config_fingerprint="f" * 64,
        run_id="run-1",
        capture_options=options,
        source_revision="rev-1",
    )
    assert verified.metrics.cell_id == "cell-1"
    assert verified.metrics.evidence_digest == verified.evidence.digest


def test_verify_cultural_pair_rejects_identity_window_and_digest_mismatch() -> None:
    options = CulturalCaptureOptions(enabled=True)
    evidence, metrics = _bound_pair(options)
    with pytest.raises(CulturalArtifactError, match="capture_policy_mismatch"):
        verify_cultural_pair(
            evidence,
            metrics,
            cell_id="cell-1",
            matrix_fingerprint="m" * 64,
            cell_fingerprint="c" * 64,
            config_fingerprint="f" * 64,
            run_id="run-2",
            capture_options=options,
        )
    other_window = CulturalCaptureOptions(
        enabled=True,
        analysis_window=CulturalAnalysisWindow(baseline_boundary=1),
    )
    with pytest.raises(CulturalArtifactError, match="capture_policy_mismatch"):
        verify_cultural_pair(
            evidence,
            metrics,
            cell_id="cell-1",
            matrix_fingerprint="m" * 64,
            cell_fingerprint="c" * 64,
            config_fingerprint="f" * 64,
            run_id="run-1",
            capture_options=other_window,
        )
    decoded = decode_cultural_cell_metrics(metrics)
    divergent = CulturalCellMetrics(
        cell_id=decoded.cell_id,
        matrix_fingerprint=decoded.matrix_fingerprint,
        cell_fingerprint=decoded.cell_fingerprint,
        config_fingerprint=decoded.config_fingerprint,
        run_id=decoded.run_id,
        capture_policy=decoded.capture_policy,
        analysis_window=decoded.analysis_window,
        evidence_digest="d" * 64,
        documents=decoded.documents,
        digest="",
    )
    with pytest.raises(CulturalArtifactError, match="digest_mismatch"):
        verify_cultural_pair(
            evidence,
            encode_cultural_cell_metrics(divergent),
            cell_id="cell-1",
            matrix_fingerprint="m" * 64,
            cell_fingerprint="c" * 64,
            config_fingerprint="f" * 64,
            run_id="run-1",
            capture_options=options,
        )


def test_evidence_decoder_rejects_duplicate_nested_nan_and_depth() -> None:
    options = CulturalCaptureOptions(enabled=True)
    evidence = _evidence_bytes(options)
    text = evidence.decode("utf-8")
    duplicated = text.replace(
        '"active":true',
        '"active":true,"active":true',
        1,
    )
    with pytest.raises(Exception, match="duplicate_key"):
        decode_cultural_evolution_evidence(duplicated.encode())
    nonfinite = text.replace('"failed":false', '"failed":NaN', 1)
    with pytest.raises(Exception, match="nonfinite_number"):
        decode_cultural_evolution_evidence(nonfinite.encode())
    with pytest.raises(Exception, match="excessive_depth"):
        decode_cultural_evolution_evidence(("[" * 40 + "]" * 40).encode())
    payload = json.loads(text)
    payload["capture_status"]["extra"] = 1
    payload.pop("digest")
    payload["digest"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(Exception, match="invalid_capture_status"):
        decode_cultural_evolution_evidence(
            json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )
