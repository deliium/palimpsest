"""Bounded read-only access to cultural research artifacts.

Filesystem work is offloaded from the event loop. The reader never writes,
repairs, recovers or opens a matrix manifest store, and it never imports
``analysis`` or ``experiments``.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from api.errors import ApiError, bad_request, conflict, not_found, too_large
from api.research_cultural_schemas import (
    MAX_OUTER_ARTIFACT_BYTES,
    CulturalArtifactSchemaError,
    depth_ok,
    duplicate_aware_pairs,
    reject_nonfinite,
    validate_cell_metrics,
    validate_comparison,
    validate_cultural_evidence,
)
from infrastructure.logging import get_logger

_LOGGER = get_logger("api.research_cultural_service")

_MATRIX_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CELL_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_RUNTIME_MANIFEST_SCHEMA: Final[str] = "matrix-manifest-v1"
_LEGACY_MANIFEST_SCHEMA: Final[str] = "experiment-matrix-v1"
_MATRIX_SCHEMA_VERSION: Final[str] = "experiment-matrix-v1"
_SUCCESS_STOP_REASONS: Final[frozenset[str]] = frozenset(
    {
        "max_ticks",
        "all_agents_terminal",
        "injected_stop",
        "generation_horizon",
        "population_extinction",
        "population_threshold",
        "experiment_criterion",
    }
)
_LEGACY_SIDEcar_SUFFIXES: Final[tuple[str, ...]] = (
    ".completion.json",
    ".metrics.json",
    ".cultural-evidence.json",
    ".cultural-metrics.json",
)


@dataclass(frozen=True, slots=True)
class ArtifactDocument:
    payload: dict[str, object]
    raw: bytes
    binding: str


@dataclass(frozen=True, slots=True)
class CulturalEvidencePair:
    evidence: dict[str, object]
    metrics: dict[str, object]
    evidence_raw: bytes
    metrics_raw: bytes
    evidence_identity: dict[str, object]
    metrics_identity: dict[str, str]
    binding: str


def manifest_kind(payload: object) -> str:
    """Return ``runtime`` or ``legacy`` for a supported manifest document."""
    if not isinstance(payload, dict):
        raise bad_request(code="unsupported_matrix_schema")
    schema = payload.get("schema_version")
    if schema == _RUNTIME_MANIFEST_SCHEMA:
        if payload.get("matrix_schema_version") != _MATRIX_SCHEMA_VERSION:
            raise bad_request(code="unsupported_matrix_schema")
        return "runtime"
    if schema == _LEGACY_MANIFEST_SCHEMA:
        return "legacy"
    raise bad_request(code="unsupported_matrix_schema")


def is_runtime_manifest(payload: object) -> bool:
    return manifest_kind(payload) == "runtime"


class ResearchCulturalService:
    """Read verified cultural artifacts under a fixed matrix root."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._resolved_root = self._root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    def _matrix_dir(self, matrix_id: str) -> Path:
        if _MATRIX_ID_RE.fullmatch(matrix_id) is None:
            raise bad_request(code="invalid_matrix_id")
        path = self._resolve(self._root / matrix_id)
        if not path.is_dir():
            raise not_found(code="matrix_not_found")
        return path

    def _resolve(self, path: Path) -> Path:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            raise not_found(code="matrix_file_missing") from None
        except OSError:
            raise bad_request(code="path_traversal") from None
        if resolved != self._resolved_root and not resolved.is_relative_to(
            self._resolved_root
        ):
            _LOGGER.warning("research_cultural_rejected reason_code=path_traversal")
            raise bad_request(code="path_traversal")
        return resolved

    async def read_bytes(self, path: Path) -> bytes:
        resolved = self._resolve(path)
        if not resolved.is_file():
            raise not_found(code="matrix_file_missing")
        return await asyncio.to_thread(self._read_bytes_sync, resolved)

    def _read_bytes_sync(self, path: Path) -> bytes:
        try:
            size = path.stat().st_size
        except OSError:
            raise not_found(code="matrix_file_missing") from None
        if size > MAX_OUTER_ARTIFACT_BYTES:
            _LOGGER.warning(
                "research_cultural_rejected reason_code=research_artifact_too_large"
            )
            raise too_large(code="research_artifact_too_large")
        try:
            with path.open("rb") as handle:
                data = handle.read(MAX_OUTER_ARTIFACT_BYTES + 1)
        except OSError:
            raise not_found(code="matrix_file_missing") from None
        if len(data) > MAX_OUTER_ARTIFACT_BYTES:
            raise too_large(code="research_artifact_too_large")
        return data

    async def read_json(self, path: Path) -> tuple[dict[str, object], bytes]:
        raw = await self.read_bytes(path)
        return await asyncio.to_thread(_decode_json, raw), raw

    async def read_manifest(
        self, matrix_id: str
    ) -> tuple[dict[str, object], bytes, str]:
        matrix_dir = self._matrix_dir(matrix_id)
        payload, raw = await self.read_json(matrix_dir / "manifest.json")
        try:
            kind = manifest_kind(payload)
        except ApiError as exc:
            _LOGGER.warning("research_cultural_rejected reason_code=%s", exc.code)
            raise
        return payload, raw, kind

    async def read_comparison(self, matrix_id: str) -> ArtifactDocument:
        matrix_dir = self._matrix_dir(matrix_id)
        path = matrix_dir / "cultural-metric-comparison.json"
        payload, raw = await self.read_json(path)
        try:
            fingerprint = validate_comparison(payload)
        except CulturalArtifactSchemaError as exc:
            _logger_schema_failure(exc.code)
            raise bad_request(code=exc.code) from None
        manifest, _, kind = await self.read_manifest(matrix_id)
        if kind == "runtime":
            runtime_fp = manifest.get("matrix_fingerprint")
            if runtime_fp != fingerprint:
                _logger_schema_failure("matrix_fingerprint_mismatch")
                raise bad_request(code="matrix_fingerprint_mismatch")
            binding = "runtime_bound"
        else:
            binding = "legacy_unverified"
        _LOGGER.info(
            "research_cultural_comparison_read",
            matrix_id=matrix_id,
            binding=binding,
        )
        return ArtifactDocument(payload=payload, raw=raw, binding=binding)

    async def read_cell_metrics(self, matrix_id: str, cell_id: str) -> ArtifactDocument:
        if _CELL_ID_RE.fullmatch(cell_id) is None:
            raise bad_request(code="invalid_cell_id")
        matrix_dir = self._matrix_dir(matrix_id)
        path = matrix_dir / "cells" / f"{cell_id}.cultural-metrics.json"
        payload, raw = await self.read_json(path)
        try:
            identity = validate_cell_metrics(payload)
        except CulturalArtifactSchemaError as exc:
            _logger_schema_failure(exc.code)
            raise bad_request(code=exc.code) from None
        if identity["cell_id"] != cell_id:
            raise bad_request(code="cell_identity_mismatch")
        manifest, _, kind = await self.read_manifest(matrix_id)
        if kind == "runtime":
            await self._verify_runtime_cell(matrix_dir, manifest, cell_id, identity)
            binding = "runtime_bound"
        else:
            binding = "legacy_unverified"
        _LOGGER.info(
            "research_cultural_cell_metrics_read",
            matrix_id=matrix_id,
            binding=binding,
        )
        return ArtifactDocument(payload=payload, raw=raw, binding=binding)

    async def read_evidence_pair(
        self, matrix_id: str, cell_id: str
    ) -> CulturalEvidencePair:
        if _CELL_ID_RE.fullmatch(cell_id) is None:
            raise bad_request(code="invalid_cell_id")
        matrix_dir = self._matrix_dir(matrix_id)
        evidence_path = matrix_dir / "cells" / f"{cell_id}.cultural-evidence.json"
        metrics_path = matrix_dir / "cells" / f"{cell_id}.cultural-metrics.json"
        evidence, evidence_raw = await self.read_json(evidence_path)
        metrics, metrics_raw = await self.read_json(metrics_path)
        try:
            evidence_identity = validate_cultural_evidence(evidence)
            metrics_identity = validate_cell_metrics(metrics)
        except CulturalArtifactSchemaError as exc:
            _logger_schema_failure(exc.code)
            raise bad_request(code=exc.code) from None
        if metrics_identity["cell_id"] != cell_id:
            raise bad_request(code="cell_identity_mismatch")
        if (
            evidence_identity["run_id"] != metrics_identity["run_id"]
            or evidence_identity["config_fingerprint"]
            != metrics_identity["config_fingerprint"]
            or evidence_identity["digest"] != metrics_identity["evidence_digest"]
        ):
            raise bad_request(code="capture_policy_mismatch")
        if evidence_identity["analysis_window"] != metrics["analysis_window"]:
            raise bad_request(code="capture_policy_mismatch")
        if evidence_identity["capture_options"] != metrics["capture_policy"]:
            raise bad_request(code="capture_policy_mismatch")
        manifest, _, kind = await self.read_manifest(matrix_id)
        if kind == "runtime":
            await self._verify_runtime_cell(
                matrix_dir, manifest, cell_id, metrics_identity
            )
            binding = "runtime_bound"
        else:
            binding = "legacy_unverified"
        _LOGGER.info(
            "research_cultural_evidence_pair_read",
            matrix_id=matrix_id,
            binding=binding,
        )
        return CulturalEvidencePair(
            evidence=evidence,
            metrics=metrics,
            evidence_raw=evidence_raw,
            metrics_raw=metrics_raw,
            evidence_identity=evidence_identity,
            metrics_identity=metrics_identity,
            binding=binding,
        )

    async def _verify_runtime_cell(
        self,
        matrix_dir: Path,
        manifest: dict[str, object],
        cell_id: str,
        identity: dict[str, str],
    ) -> None:
        declared = manifest.get("cell_ids")
        if not isinstance(declared, list) or cell_id not in declared:
            raise not_found(code="matrix_file_missing")
        runtime_fp = manifest.get("matrix_fingerprint")
        if runtime_fp != identity["matrix_fingerprint"]:
            raise bad_request(code="matrix_fingerprint_mismatch")
        try:
            state_payload, _ = await self.read_json(
                matrix_dir / "cells" / f"{cell_id}.json"
            )
        except ApiError as exc:
            if exc.status == 404:
                raise conflict(code="research_cell_incomplete") from None
            raise
        if (
            state_payload.get("cell_id") != cell_id
            or state_payload.get("state") != "completed"
        ):
            raise conflict(code="research_cell_incomplete")
        if (
            state_payload.get("cell_fingerprint") != identity["cell_fingerprint"]
            or state_payload.get("config_fingerprint") != identity["config_fingerprint"]
            or state_payload.get("run_id") != identity["run_id"]
        ):
            raise conflict(code="research_cell_incomplete")
        completion_path = matrix_dir / "cells" / f"{cell_id}.completion.json"
        try:
            completion, _ = await self.read_json(completion_path)
        except ApiError as exc:
            if exc.status == 404:
                raise conflict(code="research_cell_incomplete") from None
            raise
        version = completion.get("version_identity")
        if not isinstance(version, dict):
            raise conflict(code="research_cell_incomplete")
        if (
            completion.get("cell_id") != cell_id
            or completion.get("run_id") != identity["run_id"]
            or completion.get("stop_reason") not in _SUCCESS_STOP_REASONS
            or version.get("matrix_fingerprint") != runtime_fp
            or version.get("cell_fingerprint") != identity["cell_fingerprint"]
            or version.get("config_fingerprint") != identity["config_fingerprint"]
        ):
            raise conflict(code="research_cell_incomplete")

    async def list_cells(self, matrix_id: str) -> tuple[str, ...]:
        matrix_dir = self._matrix_dir(matrix_id)
        manifest, _, kind = await self.read_manifest(matrix_id)
        if kind == "runtime":
            declared = manifest.get("cell_ids")
            if not isinstance(declared, list):
                raise bad_request(code="invalid_manifest")
            result: list[str] = []
            for raw in declared:
                if not isinstance(raw, str) or _CELL_ID_RE.fullmatch(raw) is None:
                    continue
                if (matrix_dir / "cells" / f"{raw}.json").is_file():
                    result.append(raw)
            return tuple(result)
        return await asyncio.to_thread(self._discover_legacy_cells, matrix_dir)

    def _discover_legacy_cells(self, matrix_dir: Path) -> tuple[str, ...]:
        cells_dir = matrix_dir / "cells"
        if not cells_dir.is_dir():
            return ()
        result: list[str] = []
        for path in sorted(cells_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file():
                continue
            name = path.name
            if not name.endswith(".json"):
                continue
            if any(name.endswith(suffix) for suffix in _LEGACY_SIDEcar_SUFFIXES):
                continue
            cell_id = name[: -len(".json")]
            if _CELL_ID_RE.fullmatch(cell_id) is None:
                continue
            result.append(cell_id)
        return tuple(result)


def _decode_json(raw: bytes) -> dict[str, object]:
    if not depth_ok(raw):
        _logger_schema_failure("excessive_depth")
        raise bad_request(code="excessive_depth")
    try:
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=duplicate_aware_pairs,
            parse_constant=reject_nonfinite,
        )
    except CulturalArtifactSchemaError as exc:
        _logger_schema_failure(exc.code)
        raise bad_request(code=exc.code) from None
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        _logger_schema_failure("invalid_json")
        raise bad_request(code="invalid_json") from None
    if not isinstance(payload, dict):
        _logger_schema_failure("invalid_json")
        raise bad_request(code="invalid_json")
    return payload


def _logger_schema_failure(code: str) -> None:
    _LOGGER.warning("research_cultural_rejected reason_code=%s", code)


__all__ = [
    "ArtifactDocument",
    "CulturalEvidencePair",
    "ResearchCulturalService",
    "is_runtime_manifest",
    "manifest_kind",
]
