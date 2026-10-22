"""Immutable generational archive sidecars.

Task 10 owns the canonical recording-usage file. The remaining manifest,
history, completion, and failure schemas are added by Task 11 without changing
the usage row contract.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from simulation.generational_control import RecordingUsageEvidence

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.generational_artifacts"
)

GENERATIONAL_RECORDING_USAGE_SCHEMA_VERSION: Final[str] = (
    "generational-recording-usage-v1"
)
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_USAGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "agent_id",
        "cache_key",
        "component",
        "lookup_mode",
        "namespace",
        "payload_hash",
        "prompt_identity",
        "record_integrity_hash",
        "request_id",
        "response_schema_identity",
        "run_id",
        "schema_version",
        "tick",
    }
)


class GenerationalArtifactError(RuntimeError):
    """Fail-closed artifact error with a stable, payload-free code."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require_safe_segment(name: str, value: str) -> str:
    if type(value) is not str or _SAFE_SEGMENT.fullmatch(value) is None:
        raise GenerationalArtifactError("unsafe_path_segment", name)
    return value


def _payload_without_hash(row: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key != "payload_hash"}


def encode_recording_usage_row(
    evidence: RecordingUsageEvidence, *, run_id: str
) -> bytes:
    if type(evidence) is not RecordingUsageEvidence:
        raise TypeError("evidence must be RecordingUsageEvidence")
    require_safe_segment("run_id", run_id)
    payload: dict[str, object] = {
        "agent_id": evidence.agent_id,
        "cache_key": evidence.cache_key,
        "component": evidence.component,
        "lookup_mode": evidence.lookup_mode,
        "namespace": evidence.namespace,
        "prompt_identity": dict(evidence.prompt_identity),
        "record_integrity_hash": evidence.record_integrity_hash,
        "request_id": evidence.request_id,
        "response_schema_identity": dict(evidence.response_schema_identity),
        "run_id": run_id,
        "schema_version": GENERATIONAL_RECORDING_USAGE_SCHEMA_VERSION,
        "tick": evidence.tick,
    }
    payload["payload_hash"] = _sha256(canonical_bytes(payload))
    return canonical_bytes(payload)


def decode_recording_usage_row(
    payload: bytes, *, run_id: str
) -> dict[str, object]:
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationalArtifactError("invalid_json", "usage") from exc
    if not isinstance(data, dict):
        raise GenerationalArtifactError("invalid_object", "usage")
    if set(data) != _USAGE_KEYS:
        raise GenerationalArtifactError("invalid_keys", "usage")
    if data["schema_version"] != GENERATIONAL_RECORDING_USAGE_SCHEMA_VERSION:
        raise GenerationalArtifactError("unsupported_version", "usage")
    if data["run_id"] != run_id:
        raise GenerationalArtifactError("run_id_mismatch", "usage")
    expected = _sha256(canonical_bytes(_payload_without_hash(data)))
    if data["payload_hash"] != expected:
        raise GenerationalArtifactError("payload_hash_mismatch", "usage")
    return data


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing == payload:
            return
        raise GenerationalArtifactError("artifact_conflict", path.name)
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=".tmp-", suffix=".json"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


@dataclass(frozen=True, slots=True)
class GenerationalUsageStore:
    """Append-only canonical recording-usage rows for one run attempt."""

    root: Path
    run_id: str
    attempt_id: str = "single"

    def __post_init__(self) -> None:
        require_safe_segment("run_id", self.run_id)
        require_safe_segment("attempt_id", self.attempt_id)
        object.__setattr__(self, "root", Path(self.root))

    @property
    def usage_dir(self) -> Path:
        return self.root / self.run_id / self.attempt_id / "recording-usage"

    def path_for(self, evidence: RecordingUsageEvidence) -> Path:
        return self.usage_dir / f"{evidence.usage_key}.json"

    def put_usage(self, evidence: RecordingUsageEvidence) -> None:
        payload = encode_recording_usage_row(evidence, run_id=self.run_id)
        _atomic_write(self.path_for(evidence), payload)
        _LOG.info(
            "generational_usage_row_written run_id=%s attempt_id=%s",
            self.run_id,
            self.attempt_id,
        )

    def row_refs(self) -> tuple[tuple[str, str], ...]:
        if not self.usage_dir.exists():
            return ()
        rows: list[tuple[str, str]] = []
        for path in sorted(self.usage_dir.glob("*.json"), key=lambda item: item.name):
            row = decode_recording_usage_row(path.read_bytes(), run_id=self.run_id)
            rows.append((path.name, str(row["payload_hash"])))
        return tuple(rows)

    def usage_index_digest(self) -> str:
        return _sha256(canonical_bytes(list(self.row_refs())))

    def count(self) -> int:
        return len(self.row_refs())


__all__ = [
    "GENERATIONAL_RECORDING_USAGE_SCHEMA_VERSION",
    "GenerationalArtifactError",
    "GenerationalUsageStore",
    "canonical_bytes",
    "decode_recording_usage_row",
    "encode_recording_usage_row",
    "require_safe_segment",
]
