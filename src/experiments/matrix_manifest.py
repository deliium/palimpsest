"""Filesystem matrix manifest store with crash recovery (framework-free ports)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from experiments.matrix_models import (
    DEFAULT_SUCCESS_STOP_REASONS,
    EXPERIMENT_MATRIX_SCHEMA_VERSION,
    MatrixCell,
    MatrixCellState,
    MatrixValidationError,
    RunVersionIdentity,
)
from experiments.matrix_serialization import (
    MatrixSerializationError,
    decode_run_version_identity,
    encode_run_version_identity,
)
from simulation.runner_models import RunnerStopReasonCode

_LOG: Final[logging.Logger] = logging.getLogger("experiments.matrix_manifest")

MATRIX_MANIFEST_SCHEMA_VERSION: Final[str] = "matrix-manifest-v1"


@dataclass(frozen=True, slots=True)
class MatrixManifestHeader:
    """Top-level manifest.json identity (no cell runtime payloads)."""

    matrix_id: str
    matrix_fingerprint: str
    schema_version: str = MATRIX_MANIFEST_SCHEMA_VERSION
    matrix_schema_version: str = EXPERIMENT_MATRIX_SCHEMA_VERSION
    cell_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != MATRIX_MANIFEST_SCHEMA_VERSION:
            raise MatrixValidationError(
                "unsupported_manifest_schema",
                "unsupported matrix manifest schema_version",
            )
        if self.matrix_schema_version != EXPERIMENT_MATRIX_SCHEMA_VERSION:
            raise MatrixValidationError(
                "unsupported_matrix_schema",
                "manifest matrix_schema_version mismatch",
            )
        if (
            type(self.matrix_fingerprint) is not str
            or len(self.matrix_fingerprint) != 64
        ):
            raise MatrixValidationError(
                "invalid_matrix_fingerprint",
                "matrix_fingerprint must be sha256 hex",
            )


@dataclass(frozen=True, slots=True)
class MatrixCellRecord:
    """Per-cell manifest sidecar (state + optional completion identity)."""

    cell_id: str
    condition_id: str
    cell_fingerprint: str
    config_fingerprint: str
    state: MatrixCellState
    seed: int
    seed_ordinal: int
    replicate_index: int
    attempt_count: int = 0
    last_error_code: str = ""
    run_id: str = ""
    stop_reason: str = ""
    version_identity: RunVersionIdentity | None = None

    def __post_init__(self) -> None:
        if type(self.state) is not MatrixCellState:
            raise TypeError("state must be MatrixCellState")
        if type(self.attempt_count) is not int or self.attempt_count < 0:
            raise MatrixValidationError(
                "invalid_attempt_count",
                "attempt_count must be non-negative int",
            )


@dataclass(frozen=True, slots=True)
class MatrixCompletionRecord:
    """Valid completion sidecar identity for resume checks."""

    cell_id: str
    run_id: str
    stop_reason: RunnerStopReasonCode
    version_identity: RunVersionIdentity
    result_payload_hash: str = ""


class MatrixManifestStore(Protocol):
    """Port for create/open, cell transitions, and completion validity."""

    def create(
        self,
        header: MatrixManifestHeader,
        cells: tuple[MatrixCell, ...],
    ) -> None: ...

    def open(self) -> MatrixManifestHeader: ...

    def list_cells(self) -> tuple[MatrixCellRecord, ...]: ...

    def get_cell(self, cell_id: str) -> MatrixCellRecord: ...

    def transition(
        self,
        cell_id: str,
        *,
        state: MatrixCellState,
        attempt_count: int | None = None,
        last_error_code: str | None = None,
        run_id: str | None = None,
        stop_reason: str | None = None,
        version_identity: RunVersionIdentity | None = None,
    ) -> MatrixCellRecord: ...

    def write_completion(self, completion: MatrixCompletionRecord) -> None: ...

    def write_metric_documents(
        self, cell_id: str, documents: tuple[object, ...]
    ) -> None: ...

    def read_metric_documents(self, cell_id: str) -> tuple[object, ...] | None: ...

    def has_valid_completion(
        self,
        cell: MatrixCell,
        *,
        matrix_fingerprint: str,
    ) -> bool: ...

    def has_valid_completion_fingerprints(
        self,
        *,
        cell_id: str,
        cell_fingerprint: str,
        config_fingerprint: str,
        matrix_fingerprint: str,
    ) -> bool: ...


def _canonical_dumps(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _header_document(header: MatrixManifestHeader) -> dict[str, object]:
    return {
        "schema_version": header.schema_version,
        "matrix_schema_version": header.matrix_schema_version,
        "matrix_id": header.matrix_id,
        "matrix_fingerprint": header.matrix_fingerprint,
        "cell_ids": list(header.cell_ids),
    }


def _cell_document(record: MatrixCellRecord) -> dict[str, object]:
    document: dict[str, object] = {
        "cell_id": record.cell_id,
        "condition_id": record.condition_id,
        "cell_fingerprint": record.cell_fingerprint,
        "config_fingerprint": record.config_fingerprint,
        "state": record.state.value,
        "seed": record.seed,
        "seed_ordinal": record.seed_ordinal,
        "replicate_index": record.replicate_index,
        "attempt_count": record.attempt_count,
        "last_error_code": record.last_error_code,
        "run_id": record.run_id,
        "stop_reason": record.stop_reason,
        "version_identity": None,
    }
    if record.version_identity is not None:
        document["version_identity"] = json.loads(
            encode_run_version_identity(record.version_identity).decode("utf-8")
        )
    return document


def _decode_cell(data: Mapping[str, object]) -> MatrixCellRecord:
    identity_raw = data.get("version_identity")
    identity: RunVersionIdentity | None = None
    if identity_raw is not None:
        if not isinstance(identity_raw, dict):
            raise MatrixValidationError(
                "invalid_version_identity",
                "version_identity must be object or null",
            )
        identity = decode_run_version_identity(_canonical_dumps(identity_raw))
    return MatrixCellRecord(
        cell_id=str(data["cell_id"]),
        condition_id=str(data["condition_id"]),
        cell_fingerprint=str(data["cell_fingerprint"]),
        config_fingerprint=str(data["config_fingerprint"]),
        state=MatrixCellState(str(data["state"])),
        seed=int(data["seed"]),  # type: ignore[arg-type]
        seed_ordinal=int(data["seed_ordinal"]),  # type: ignore[arg-type]
        replicate_index=int(data["replicate_index"]),  # type: ignore[arg-type]
        attempt_count=int(data.get("attempt_count", 0)),  # type: ignore[arg-type]
        last_error_code=str(data.get("last_error_code", "")),
        run_id=str(data.get("run_id", "")),
        stop_reason=str(data.get("stop_reason", "")),
        version_identity=identity,
    )


class FilesystemMatrixManifestStore:
    """root/manifest.json + root/cells/<cell_id>.json with atomic replace."""

    __slots__ = ("_header", "_root")

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._header: MatrixManifestHeader | None = None

    @property
    def root(self) -> Path:
        return self._root

    def _manifest_path(self) -> Path:
        return self._root / "manifest.json"

    def _cell_path(self, cell_id: str) -> Path:
        return self._root / "cells" / f"{cell_id}.json"

    def _completion_path(self, cell_id: str) -> Path:
        return self._root / "cells" / f"{cell_id}.completion.json"

    def _metrics_path(self, cell_id: str) -> Path:
        return self._root / "cells" / f"{cell_id}.metrics.json"

    def create(
        self,
        header: MatrixManifestHeader,
        cells: tuple[MatrixCell, ...],
    ) -> None:
        if type(header) is not MatrixManifestHeader:
            raise TypeError("header must be MatrixManifestHeader")
        if self._manifest_path().exists():
            existing = self.open()
            if existing.matrix_fingerprint != header.matrix_fingerprint:
                _LOG.error(
                    "matrix_manifest_divergent_rewrite",
                    extra={
                        "experiment": {
                            "matrix_id": header.matrix_id,
                            "reason_code": "divergent_manifest_rewrite",
                        }
                    },
                )
                raise MatrixValidationError(
                    "divergent_manifest_rewrite",
                    "refusing divergent rewrite of existing matrix manifest",
                )
            _LOG.info(
                "matrix_manifest_reopen",
                extra={
                    "experiment": {
                        "matrix_id": header.matrix_id,
                        "fingerprint_prefix": header.matrix_fingerprint[:12],
                    }
                },
            )
            return
        cell_ids = tuple(cell.cell_id for cell in cells)
        stored = MatrixManifestHeader(
            matrix_id=header.matrix_id,
            matrix_fingerprint=header.matrix_fingerprint,
            schema_version=header.schema_version,
            matrix_schema_version=header.matrix_schema_version,
            cell_ids=cell_ids,
        )
        self._root.mkdir(parents=True, exist_ok=True)
        _atomic_write(self._manifest_path(), _canonical_dumps(_header_document(stored)))
        for cell in cells:
            record = MatrixCellRecord(
                cell_id=cell.cell_id,
                condition_id=cell.condition_id,
                cell_fingerprint=cell.cell_fingerprint,
                config_fingerprint=cell.config_fingerprint,
                state=MatrixCellState.PENDING,
                seed=cell.seed,
                seed_ordinal=cell.seed_ordinal,
                replicate_index=cell.replicate_index,
            )
            _atomic_write(
                self._cell_path(cell.cell_id),
                _canonical_dumps(_cell_document(record)),
            )
        self._header = stored
        _LOG.info(
            "matrix_manifest_created",
            extra={
                "experiment": {
                    "matrix_id": stored.matrix_id,
                    "fingerprint_prefix": stored.matrix_fingerprint[:12],
                    "cell_count": len(cell_ids),
                }
            },
        )

    def open(self) -> MatrixManifestHeader:
        path = self._manifest_path()
        if not path.exists():
            raise MatrixValidationError(
                "manifest_missing",
                "matrix manifest.json not found",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        header = MatrixManifestHeader(
            matrix_id=str(data["matrix_id"]),
            matrix_fingerprint=str(data["matrix_fingerprint"]),
            schema_version=str(data["schema_version"]),
            matrix_schema_version=str(data["matrix_schema_version"]),
            cell_ids=tuple(str(item) for item in data["cell_ids"]),
        )
        self._header = header
        # Crash recovery: running without valid completion → pending.
        for cell_id in header.cell_ids:
            record = self.get_cell(cell_id)
            if record.state is MatrixCellState.RUNNING:
                valid = self.has_valid_completion_fingerprints(
                    cell_id=record.cell_id,
                    cell_fingerprint=record.cell_fingerprint,
                    config_fingerprint=record.config_fingerprint,
                    matrix_fingerprint=header.matrix_fingerprint,
                )
                if not valid:
                    reset = self.transition(
                        cell_id,
                        state=MatrixCellState.PENDING,
                        last_error_code="crash_reset",
                    )
                    _LOG.debug(
                        "matrix_cell_crash_reset",
                        extra={
                            "experiment": {
                                "cell_id": reset.cell_id,
                                "state": reset.state.value,
                            }
                        },
                    )
        _LOG.info(
            "matrix_manifest_opened",
            extra={
                "experiment": {
                    "matrix_id": header.matrix_id,
                    "fingerprint_prefix": header.matrix_fingerprint[:12],
                }
            },
        )
        return header

    def list_cells(self) -> tuple[MatrixCellRecord, ...]:
        header = self._header or self.open()
        return tuple(self.get_cell(cell_id) for cell_id in header.cell_ids)

    def get_cell(self, cell_id: str) -> MatrixCellRecord:
        path = self._cell_path(cell_id)
        if not path.exists():
            raise MatrixValidationError(
                "cell_missing",
                f"cell sidecar missing: {cell_id}",
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return _decode_cell(data)

    def transition(
        self,
        cell_id: str,
        *,
        state: MatrixCellState,
        attempt_count: int | None = None,
        last_error_code: str | None = None,
        run_id: str | None = None,
        stop_reason: str | None = None,
        version_identity: RunVersionIdentity | None = None,
    ) -> MatrixCellRecord:
        current = self.get_cell(cell_id)
        record = MatrixCellRecord(
            cell_id=current.cell_id,
            condition_id=current.condition_id,
            cell_fingerprint=current.cell_fingerprint,
            config_fingerprint=current.config_fingerprint,
            state=state,
            seed=current.seed,
            seed_ordinal=current.seed_ordinal,
            replicate_index=current.replicate_index,
            attempt_count=(
                current.attempt_count if attempt_count is None else attempt_count
            ),
            last_error_code=(
                current.last_error_code if last_error_code is None else last_error_code
            ),
            run_id=current.run_id if run_id is None else run_id,
            stop_reason=current.stop_reason if stop_reason is None else stop_reason,
            version_identity=(
                current.version_identity
                if version_identity is None
                else version_identity
            ),
        )
        _atomic_write(
            self._cell_path(cell_id),
            _canonical_dumps(_cell_document(record)),
        )
        _LOG.debug(
            "matrix_cell_transition",
            extra={
                "experiment": {
                    "cell_id": cell_id,
                    "state": state.value,
                    "attempt_count": record.attempt_count,
                }
            },
        )
        return record

    def write_completion(self, completion: MatrixCompletionRecord) -> None:
        if type(completion) is not MatrixCompletionRecord:
            raise TypeError("completion must be MatrixCompletionRecord")
        document = {
            "cell_id": completion.cell_id,
            "run_id": completion.run_id,
            "stop_reason": completion.stop_reason.value,
            "result_payload_hash": completion.result_payload_hash,
            "version_identity": json.loads(
                encode_run_version_identity(completion.version_identity).decode("utf-8")
            ),
        }
        _atomic_write(
            self._completion_path(completion.cell_id),
            _canonical_dumps(document),
        )
        self.transition(
            completion.cell_id,
            state=MatrixCellState.COMPLETED,
            run_id=completion.run_id,
            stop_reason=completion.stop_reason.value,
            version_identity=completion.version_identity,
        )

    def write_metric_documents(
        self, cell_id: str, documents: tuple[object, ...]
    ) -> None:
        """Persist optional encoded MetricDocument sidecars for matrix summaries."""
        from analysis.models import MetricAvailability, MetricDocument
        from analysis.serialization import encode_metric_document

        cell_id = str(cell_id)
        if not isinstance(documents, tuple):
            raise TypeError("documents: not_tuple")
        presentable = [
            doc
            for doc in documents
            if type(doc) is MetricDocument
            and doc.availability
            in (MetricAvailability.PRESENT, MetricAvailability.PARTIAL)
        ]
        if not presentable:
            return
        ordered = sorted(presentable, key=lambda doc: doc.metric_family)
        payload = [
            json.loads(encode_metric_document(doc).decode("utf-8")) for doc in ordered
        ]
        _atomic_write(self._metrics_path(cell_id), _canonical_dumps(payload))
        _LOG.info(
            "matrix_metric_sidecar_written",
            extra={
                "experiment": {
                    "cell_id_prefix": cell_id[:12],
                    "document_count": len(ordered),
                }
            },
        )
        _LOG.debug(
            "matrix_metric_sidecar_families",
            extra={
                "experiment": {
                    "cell_id_prefix": cell_id[:12],
                    "families": [doc.metric_family for doc in ordered],
                }
            },
        )

    def read_metric_documents(self, cell_id: str) -> tuple[object, ...] | None:
        """Load metric sidecars; missing file yields ``None`` (not zeros)."""
        from analysis.serialization import decode_metric_document

        path = self._metrics_path(str(cell_id))
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, list):
            return None
        documents = []
        for item in raw:
            documents.append(decode_metric_document(_canonical_dumps(item)))
        return tuple(documents)

    def has_valid_completion(
        self,
        cell: MatrixCell,
        *,
        matrix_fingerprint: str,
    ) -> bool:
        return self.has_valid_completion_fingerprints(
            cell_id=cell.cell_id,
            cell_fingerprint=cell.cell_fingerprint,
            config_fingerprint=cell.config_fingerprint,
            matrix_fingerprint=matrix_fingerprint,
        )

    def has_valid_completion_fingerprints(
        self,
        *,
        cell_id: str,
        cell_fingerprint: str,
        config_fingerprint: str,
        matrix_fingerprint: str,
    ) -> bool:
        path = self._completion_path(cell_id)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            identity = decode_run_version_identity(
                _canonical_dumps(data["version_identity"])
            )
            stop_reason = RunnerStopReasonCode(str(data["stop_reason"]))
        except (
            KeyError,
            ValueError,
            TypeError,
            MatrixSerializationError,
            json.JSONDecodeError,
        ):
            return False
        if identity.matrix_fingerprint != matrix_fingerprint:
            return False
        if identity.cell_fingerprint != cell_fingerprint:
            return False
        if identity.config_fingerprint != config_fingerprint:
            return False
        if stop_reason not in DEFAULT_SUCCESS_STOP_REASONS:
            return False
        if not data.get("run_id"):
            return False
        return True


__all__ = [
    "MATRIX_MANIFEST_SCHEMA_VERSION",
    "FilesystemMatrixManifestStore",
    "MatrixCellRecord",
    "MatrixCompletionRecord",
    "MatrixManifestHeader",
    "MatrixManifestStore",
]
