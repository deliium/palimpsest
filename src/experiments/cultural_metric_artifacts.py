"""Opt-in cultural evidence/metric sidecars with safe atomic persistence."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from analysis.cultural_evolution_evidence import CulturalAnalysisWindow
from analysis.models import MetricDocument
from analysis.serialization import decode_metric_document, encode_metric_document
from experiments.cultural_evidence_serialization import (
    CulturalEvidenceSerializationError,
    CulturalEvolutionEvidence,
    decode_cultural_evolution_evidence,
)

CULTURAL_CELL_METRICS_SCHEMA_VERSION: Final[str] = "cultural-cell-metrics-v1"
MAX_CULTURAL_ARTIFACT_BYTES: Final[int] = 64 * 1024 * 1024
MAX_CULTURAL_ARTIFACT_DEPTH: Final[int] = 32
_SAFE_CELL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$")
_CELL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "cell_id",
        "matrix_fingerprint",
        "cell_fingerprint",
        "config_fingerprint",
        "run_id",
        "capture_policy",
        "analysis_window",
        "evidence_digest",
        "documents",
        "digest",
    }
)

__all__ = [
    "CULTURAL_CELL_METRICS_SCHEMA_VERSION",
    "MAX_CULTURAL_ARTIFACT_BYTES",
    "CulturalArtifactError",
    "CulturalCaptureOptions",
    "CulturalCellMetrics",
    "VerifiedCulturalPair",
    "cultural_capture_policy",
    "decode_cultural_cell_metrics",
    "encode_cultural_cell_metrics",
    "read_cultural_pair",
    "verify_cultural_pair",
    "write_cultural_pair",
]


class CulturalArtifactError(RuntimeError):
    """Safe artifact failure code without payload fragments."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CulturalCaptureOptions:
    """Composition-only opt-in capture policy (never a runner config field)."""

    enabled: bool = False
    max_frames: int = 10_000
    max_rows: int = 1_000_000
    analysis_window: CulturalAnalysisWindow = field(
        default_factory=CulturalAnalysisWindow
    )

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("capture.enabled: invalid_type")
        for name in ("max_frames", "max_rows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"capture.{name}: must_be_positive_integer")
        if type(self.analysis_window) is not CulturalAnalysisWindow:
            raise ValueError("capture.analysis_window: invalid_type")


@dataclass(frozen=True, slots=True)
class CulturalCellMetrics:
    """Bound evidence/metric pair for one completed matrix cell."""

    cell_id: str
    matrix_fingerprint: str
    cell_fingerprint: str
    config_fingerprint: str
    run_id: str
    capture_policy: dict[str, object]
    analysis_window: CulturalAnalysisWindow
    evidence_digest: str
    documents: tuple[MetricDocument, ...]
    digest: str

    def __repr__(self) -> str:
        return (
            f"CulturalCellMetrics(cell_id={self.cell_id!r}, "
            f"run_id={self.run_id!r}, document_count={len(self.documents)}, "
            f"evidence_digest={self.evidence_digest[:12]!r})"
        )


@dataclass(frozen=True, slots=True)
class VerifiedCulturalPair:
    """Decoded evidence and metrics that agree on every bound identity."""

    evidence: CulturalEvolutionEvidence
    metrics: CulturalCellMetrics

    def __repr__(self) -> str:
        return (
            f"VerifiedCulturalPair(cell_id={self.metrics.cell_id!r}, "
            f"evidence_digest={self.metrics.evidence_digest[:12]!r})"
        )


def cultural_capture_policy(options: CulturalCaptureOptions) -> dict[str, object]:
    """Stable capture-policy identity persisted in both artifact envelopes."""
    if type(options) is not CulturalCaptureOptions:
        raise TypeError("options must be CulturalCaptureOptions")
    return {
        "enabled": bool(options.enabled),
        "max_frames": options.max_frames,
        "max_rows": options.max_rows,
    }


def verify_cultural_pair(
    evidence_bytes: bytes,
    cell_metrics_bytes: bytes,
    *,
    cell_id: str,
    matrix_fingerprint: str,
    cell_fingerprint: str,
    config_fingerprint: str,
    run_id: str,
    capture_options: CulturalCaptureOptions,
    source_revision: str | None = None,
) -> VerifiedCulturalPair:
    """Validate the complete bound pair before it may be reused or adopted."""
    try:
        evidence = decode_cultural_evolution_evidence(evidence_bytes)
    except CulturalEvidenceSerializationError as exc:
        raise CulturalArtifactError(exc.code) from exc
    metrics = decode_cultural_cell_metrics(cell_metrics_bytes)
    policy = cultural_capture_policy(capture_options)
    window = capture_options.analysis_window

    if (
        metrics.cell_id != cell_id
        or metrics.matrix_fingerprint != matrix_fingerprint
        or metrics.cell_fingerprint != cell_fingerprint
        or metrics.config_fingerprint != config_fingerprint
        or metrics.run_id != run_id
        or evidence.config_fingerprint != config_fingerprint
        or evidence.inputs.run_id != run_id
    ):
        raise CulturalArtifactError("capture_policy_mismatch")
    if (
        metrics.capture_policy != policy
        or dict(evidence.capture_options) != policy
        or metrics.analysis_window != window
        or evidence.inputs.window != window
    ):
        raise CulturalArtifactError("capture_policy_mismatch")
    if (
        source_revision is not None
        and evidence.inputs.source_revision != source_revision
    ):
        raise CulturalArtifactError("capture_policy_mismatch")
    if metrics.evidence_digest != evidence.digest:
        raise CulturalArtifactError("digest_mismatch")
    return VerifiedCulturalPair(evidence=evidence, metrics=metrics)


def _canonical(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CulturalArtifactError("duplicate_key")
        result[key] = value
    return result


def _depth_ok(data: bytes) -> bool:
    depth = 0
    quoted = False
    escaped = False
    for byte in data:
        char = chr(byte)
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in "{[":
            depth += 1
            if depth > MAX_CULTURAL_ARTIFACT_DEPTH:
                return False
        elif char in "}]":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def encode_cultural_cell_metrics(value: CulturalCellMetrics) -> bytes:
    if type(value) is not CulturalCellMetrics:
        raise TypeError("value must be CulturalCellMetrics")
    documents = [json.loads(encode_metric_document(doc)) for doc in value.documents]
    payload: dict[str, object] = {
        "schema_version": CULTURAL_CELL_METRICS_SCHEMA_VERSION,
        "cell_id": value.cell_id,
        "matrix_fingerprint": value.matrix_fingerprint,
        "cell_fingerprint": value.cell_fingerprint,
        "config_fingerprint": value.config_fingerprint,
        "run_id": value.run_id,
        "capture_policy": value.capture_policy,
        "analysis_window": {
            "baseline_boundary": value.analysis_window.baseline_boundary,
            "end_boundary": value.analysis_window.end_boundary,
        },
        "evidence_digest": value.evidence_digest,
        "documents": documents,
    }
    payload["digest"] = _sha256(_canonical(payload))
    data = _canonical(payload)
    if len(data) > MAX_CULTURAL_ARTIFACT_BYTES:
        raise CulturalArtifactError("too_large")
    return data


def decode_cultural_cell_metrics(data: bytes) -> CulturalCellMetrics:
    if not isinstance(data, bytes) or len(data) > MAX_CULTURAL_ARTIFACT_BYTES:
        raise CulturalArtifactError("too_large")
    if not _depth_ok(data):
        raise CulturalArtifactError("excessive_depth")
    try:
        payload = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                CulturalArtifactError("nonfinite_number")
            ),
        )
    except CulturalArtifactError:
        raise
    except Exception as exc:
        raise CulturalArtifactError("invalid_json") from exc
    if not isinstance(payload, dict) or set(payload) != _CELL_KEYS:
        raise CulturalArtifactError("key_set_mismatch")
    if payload.get("schema_version") != CULTURAL_CELL_METRICS_SCHEMA_VERSION:
        raise CulturalArtifactError("unsupported_schema")
    body = {key: value for key, value in payload.items() if key != "digest"}
    if payload.get("digest") != _sha256(_canonical(body)):
        raise CulturalArtifactError("digest_mismatch")
    window = payload["analysis_window"]
    if not isinstance(window, dict) or set(window) != {
        "baseline_boundary",
        "end_boundary",
    }:
        raise CulturalArtifactError("invalid_window")
    raw_documents = payload["documents"]
    if not isinstance(raw_documents, list):
        raise CulturalArtifactError("invalid_documents")
    documents = tuple(
        decode_metric_document(_canonical(item)) for item in raw_documents
    )
    return CulturalCellMetrics(
        cell_id=str(payload["cell_id"]),
        matrix_fingerprint=str(payload["matrix_fingerprint"]),
        cell_fingerprint=str(payload["cell_fingerprint"]),
        config_fingerprint=str(payload["config_fingerprint"]),
        run_id=str(payload["run_id"]),
        capture_policy=dict(payload["capture_policy"]),
        analysis_window=CulturalAnalysisWindow(
            baseline_boundary=int(window["baseline_boundary"]),
            end_boundary=(
                None if window["end_boundary"] is None else int(window["end_boundary"])
            ),
        ),
        evidence_digest=str(payload["evidence_digest"]),
        documents=documents,
        digest=str(payload["digest"]),
    )


def _safe_segment(cell_id: str) -> str:
    if type(cell_id) is not str or _SAFE_CELL.fullmatch(cell_id) is None:
        raise CulturalArtifactError("unsafe_cell_id")
    return cell_id


def _safe_root(root: Path) -> Path:
    root = Path(root)
    if root.is_symlink():
        raise CulturalArtifactError("symlink_root")
    cells = root / "cells"
    if cells.is_symlink():
        raise CulturalArtifactError("symlink_cells")
    return root


def _atomic_write(path: Path, data: bytes) -> None:
    if path.is_symlink():
        raise CulturalArtifactError("symlink_target")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise CulturalArtifactError("symlink_target")
    try:
        path.resolve().relative_to(path.parent.resolve())
    except ValueError as exc:
        raise CulturalArtifactError("path_escape") from exc
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() and path.read_bytes() != data:
            raise CulturalArtifactError("artifact_conflict")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _evidence_path(root: Path, cell_id: str) -> Path:
    return root / "cells" / f"{cell_id}.cultural-evidence.json"


def _metrics_path(root: Path, cell_id: str) -> Path:
    return root / "cells" / f"{cell_id}.cultural-metrics.json"


def write_cultural_pair(
    root: Path,
    cell_id: str,
    *,
    evidence_bytes: bytes,
    cell_metrics_bytes: bytes,
) -> None:
    """Write evidence first, then metrics; identical content is idempotent."""
    root = _safe_root(root)
    cell_id = _safe_segment(cell_id)
    if (
        len(evidence_bytes) > MAX_CULTURAL_ARTIFACT_BYTES
        or len(cell_metrics_bytes) > MAX_CULTURAL_ARTIFACT_BYTES
    ):
        raise CulturalArtifactError("too_large")
    evidence_path = _evidence_path(root, cell_id)
    metrics_path = _metrics_path(root, cell_id)
    cells_root = (root / "cells").resolve()
    for target in (evidence_path, metrics_path):
        if target.parent.resolve() != cells_root:
            raise CulturalArtifactError("path_escape")
    _atomic_write(evidence_path, evidence_bytes)
    _atomic_write(metrics_path, cell_metrics_bytes)


def read_cultural_pair(root: Path, cell_id: str) -> tuple[bytes, bytes] | None:
    root = _safe_root(root)
    cell_id = _safe_segment(cell_id)
    evidence_path = _evidence_path(root, cell_id)
    metrics_path = _metrics_path(root, cell_id)
    cells_root = (root / "cells").resolve()
    for target in (evidence_path, metrics_path):
        if target.parent.resolve() != cells_root:
            raise CulturalArtifactError("path_escape")
    if evidence_path.is_symlink() or metrics_path.is_symlink():
        raise CulturalArtifactError("symlink_target")
    if not evidence_path.exists() or not metrics_path.exists():
        return None
    evidence = evidence_path.read_bytes()
    metrics = metrics_path.read_bytes()
    if (
        len(evidence) > MAX_CULTURAL_ARTIFACT_BYTES
        or len(metrics) > MAX_CULTURAL_ARTIFACT_BYTES
    ):
        raise CulturalArtifactError("too_large")
    return evidence, metrics
