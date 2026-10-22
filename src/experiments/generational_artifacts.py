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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

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
    "GENERATIONAL_COMPLETION_SCHEMA_VERSION",
    "GENERATIONAL_FAILURE_SCHEMA_VERSION",
    "GENERATIONAL_HISTORY_SCHEMA_VERSION",
    "GENERATIONAL_RECORDING_USAGE_SCHEMA_VERSION",
    "GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION",
    "CompletionInputs",
    "GenerationalArtifactError",
    "GenerationalHistoryObserver",
    "GenerationalRunArtifactStore",
    "GenerationalUsageStore",
    "HistoricalBoundaryReader",
    "HistoricalBoundaryReference",
    "SnapshotReference",
    "canonical_bytes",
    "decode_generational_document",
    "decode_recording_usage_row",
    "encode_generational_document",
    "encode_recording_usage_row",
    "require_safe_segment",
    "source_identity_preflight",
    "write_completion",
]


GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION: Final[str] = (
    "generational-run-manifest-v1"
)
GENERATIONAL_HISTORY_SCHEMA_VERSION: Final[str] = "generational-history-v1"
GENERATIONAL_COMPLETION_SCHEMA_VERSION: Final[str] = (
    "generational-completion-v1"
)
GENERATIONAL_FAILURE_SCHEMA_VERSION: Final[str] = "generational-failure-v1"

_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "assignment",
        "cognition_fingerprint",
        "config_fingerprint",
        "config_ref",
        "environment_identity",
        "execution_recipe",
        "history_policy",
        "manifest_hash",
        "provider_identity",
        "run_id",
        "scenario_fingerprint",
        "schema_version",
        "seed_manifest",
        "source_identity",
        "attempt_id",
    }
)
_HISTORY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "community_ref",
        "evidence_ref",
        "last_completed_tick",
        "objective_commit_hash",
        "payload_hash",
        "population_progress",
        "revision",
        "run_id",
        "sample_reasons",
        "schema_version",
        "snapshot_ref",
        "stop_evidence",
    }
)
_COMPLETION_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "completion_hash",
        "execution_recipe_hash",
        "final_progress",
        "history_refs",
        "manifest_hash",
        "recording_usage_ref",
        "result_document",
        "run_id",
        "schema_version",
        "seed_manifest_hash",
        "source_identity",
    }
)
_FAILURE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "boundary_tick",
        "failure_hash",
        "manifest_hash",
        "objective_committed",
        "owners_finalized",
        "reason_code",
        "run_id",
        "schema_version",
        "stage",
        "stop_evidence",
    }
)
_ASSIGNMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "cell_id",
        "condition_id",
        "condition_ordinal",
        "experiment_id",
        "matrix_id",
        "replicate_index",
        "seed_ordinal",
    }
)
_RECIPE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "intervention_id",
        "intervention_params",
        "intervention_version",
        "params",
        "recipe_id",
        "version",
    }
)
_SOURCE_FIELDS: Final[frozenset[str]] = frozenset(
    {"code_revision", "source_artifact_digest", "source_clean"}
)
_ENVIRONMENT_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "dependency_versions",
        "package_version",
        "platform",
        "python_implementation",
        "python_version",
    }
)
_PROVIDER_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "adapter_kind",
        "exact_reproducibility",
        "lookup_mode",
        "model",
        "recording_artifact_id",
        "recording_namespace",
        "recording_policy",
    }
)
_SEED_MANIFEST_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "channels",
        "derivation_version",
        "initialization_identity",
        "physical_rules_fingerprint",
        "run_id",
        "schedule_fingerprint",
        "seed",
        "stochastic_identity",
    }
)
_SEED_CHANNEL_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "algorithm_version",
        "draw_usage",
        "identity_selector",
        "name",
        "namespace",
        "scope_fields",
    }
)
_INIT_IDENTITY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "lifespan_distribution_hash",
        "parameter_distributions_hash",
        "profile_id",
    }
)
_REF_FIELDS: Final[frozenset[str]] = frozenset({"path", "sha256"})
_SNAPSHOT_FIELDS: Final[frozenset[str]] = frozenset(
    {"integrity_hash", "next_tick", "snapshot_id"}
)
_USAGE_REF_FIELDS: Final[frozenset[str]] = frozenset(
    {"count", "row_refs", "sha256"}
)
_HISTORY_POLICY_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "criterion_cadence_ticks",
        "historical_checkpoint_cadence_ticks",
        "sample_on_generation_change",
    }
)


def _exact_mapping(
    value: object, fields: frozenset[str], *, name: str
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GenerationalArtifactError("invalid_object", name)
    if set(value) != fields:
        raise GenerationalArtifactError("invalid_keys", name)
    return value


def _require_str(value: object, *, name: str) -> str:
    if type(value) is not str or not value:
        raise GenerationalArtifactError("invalid_string", name)
    return value


def _validate_seed_manifest(value: object) -> None:
    seed = _exact_mapping(value, _SEED_MANIFEST_FIELDS, name="seed_manifest")
    for key in (
        "derivation_version",
        "physical_rules_fingerprint",
        "run_id",
        "schedule_fingerprint",
        "stochastic_identity",
    ):
        _require_str(seed[key], name=f"seed_manifest.{key}")
    if isinstance(seed["seed"], bool) or not isinstance(seed["seed"], int):
        raise GenerationalArtifactError("invalid_int", "seed_manifest.seed")
    _exact_mapping(
        seed["initialization_identity"],
        _INIT_IDENTITY_FIELDS,
        name="seed_manifest.initialization_identity",
    )
    channels = seed["channels"]
    if not isinstance(channels, list):
        raise GenerationalArtifactError("invalid_array", "seed_manifest.channels")
    names: set[str] = set()
    for channel in channels:
        row = _exact_mapping(
            channel, _SEED_CHANNEL_FIELDS, name="seed_manifest.channel"
        )
        name = _require_str(row["name"], name="seed_manifest.channel.name")
        if name in names:
            raise GenerationalArtifactError(
                "duplicate_channel", "seed_manifest.channels"
            )
        names.add(name)
        if row["draw_usage"] not in {
            "absent",
            "reserved_ignored",
            "deterministic_hash",
            "sampled",
        }:
            raise GenerationalArtifactError(
                "invalid_draw_usage", "seed_manifest.channel"
            )


def _validate_manifest_nested(payload: dict[str, object]) -> None:
    _exact_mapping(payload["assignment"], _ASSIGNMENT_FIELDS, name="assignment")
    recipe = _exact_mapping(
        payload["execution_recipe"], _RECIPE_FIELDS, name="execution_recipe"
    )
    if (recipe["intervention_id"] is None) != (
        recipe["intervention_version"] is None
    ):
        raise GenerationalArtifactError(
            "intervention_pair_mismatch", "execution_recipe"
        )
    _exact_mapping(
        payload["source_identity"], _SOURCE_FIELDS, name="source_identity"
    )
    source = payload["source_identity"]
    assert isinstance(source, dict)
    _require_str(source["code_revision"], name="source_identity.code_revision")
    if type(source["source_clean"]) is not bool:
        raise GenerationalArtifactError(
            "invalid_boolean", "source_identity.source_clean"
        )
    if source["source_clean"] is False and source["source_artifact_digest"] is None:
        raise GenerationalArtifactError(
            "source_identity_incomplete", "source_identity"
        )
    _exact_mapping(
        payload["environment_identity"],
        _ENVIRONMENT_FIELDS,
        name="environment_identity",
    )
    _exact_mapping(
        payload["provider_identity"], _PROVIDER_FIELDS, name="provider_identity"
    )
    provider = payload["provider_identity"]
    assert isinstance(provider, dict)
    if provider["recording_policy"] == "replay":
        for key in ("recording_artifact_id", "recording_namespace", "lookup_mode"):
            if provider[key] is None:
                raise GenerationalArtifactError(
                    "replay_provider_incomplete", f"provider_identity.{key}"
                )
    _exact_mapping(payload["config_ref"], _REF_FIELDS, name="config_ref")
    _exact_mapping(
        payload["history_policy"], _HISTORY_POLICY_FIELDS, name="history_policy"
    )
    _validate_seed_manifest(payload["seed_manifest"])


def _validate_history_nested(payload: dict[str, object]) -> None:
    reasons = payload["sample_reasons"]
    if not isinstance(reasons, list) or any(type(item) is not str for item in reasons):
        raise GenerationalArtifactError("invalid_array", "sample_reasons")
    if reasons != sorted(set(reasons)):
        raise GenerationalArtifactError("unsorted_sample_reasons", "sample_reasons")
    _exact_mapping(payload["snapshot_ref"], _SNAPSHOT_FIELDS, name="snapshot_ref")
    if payload["community_ref"] is not None:
        _exact_mapping(payload["community_ref"], _REF_FIELDS, name="community_ref")
    if not isinstance(payload["population_progress"], dict):
        raise GenerationalArtifactError("invalid_object", "population_progress")


def _validate_completion_nested(payload: dict[str, object]) -> None:
    _exact_mapping(
        payload["recording_usage_ref"], _USAGE_REF_FIELDS, name="recording_usage_ref"
    )
    refs = payload["history_refs"]
    if not isinstance(refs, list):
        raise GenerationalArtifactError("invalid_array", "history_refs")
    for ref in refs:
        _exact_mapping(ref, _REF_FIELDS, name="history_ref")
    _exact_mapping(
        payload["source_identity"], _SOURCE_FIELDS, name="source_identity"
    )


self_hash_fields: Final[Mapping[str, str]] = {
    GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION: "manifest_hash",
    GENERATIONAL_HISTORY_SCHEMA_VERSION: "payload_hash",
    GENERATIONAL_COMPLETION_SCHEMA_VERSION: "completion_hash",
    GENERATIONAL_FAILURE_SCHEMA_VERSION: "failure_hash",
}
_schema_fields: Final[Mapping[str, frozenset[str]]] = {
    GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION: _MANIFEST_FIELDS,
    GENERATIONAL_HISTORY_SCHEMA_VERSION: _HISTORY_FIELDS,
    GENERATIONAL_COMPLETION_SCHEMA_VERSION: _COMPLETION_FIELDS,
    GENERATIONAL_FAILURE_SCHEMA_VERSION: _FAILURE_FIELDS,
}
def _validate_failure_nested(payload: dict[str, object]) -> None:
    del payload


_nested_validators: Mapping[str, Callable[[dict[str, object]], None]] = {
    GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION: _validate_manifest_nested,
    GENERATIONAL_HISTORY_SCHEMA_VERSION: _validate_history_nested,
    GENERATIONAL_COMPLETION_SCHEMA_VERSION: _validate_completion_nested,
    GENERATIONAL_FAILURE_SCHEMA_VERSION: _validate_failure_nested,
}


def encode_generational_document(
    payload: Mapping[str, object], *, schema_version: str
) -> bytes:
    if schema_version not in _schema_fields:
        raise GenerationalArtifactError("unsupported_version", schema_version)
    expected = _schema_fields[schema_version]
    document = dict(payload)
    hash_field = self_hash_fields[schema_version]
    if set(document) != expected:
        raise GenerationalArtifactError("invalid_keys", schema_version)
    if document.get("schema_version") != schema_version:
        raise GenerationalArtifactError("schema_version_mismatch", schema_version)
    document.pop(hash_field, None)
    document[hash_field] = _sha256(canonical_bytes(document))
    _nested_validators[schema_version](document)
    return canonical_bytes(document)


def decode_generational_document(
    payload: bytes, *, schema_version: str
) -> dict[str, object]:
    if schema_version not in _schema_fields:
        raise GenerationalArtifactError("unsupported_version", schema_version)
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GenerationalArtifactError("invalid_json", schema_version) from exc
    if not isinstance(document, dict):
        raise GenerationalArtifactError("invalid_object", schema_version)
    if set(document) != _schema_fields[schema_version]:
        raise GenerationalArtifactError("invalid_keys", schema_version)
    hash_field = self_hash_fields[schema_version]
    expected_hash = document[hash_field]
    without_hash = {key: value for key, value in document.items() if key != hash_field}
    if expected_hash != _sha256(canonical_bytes(without_hash)):
        raise GenerationalArtifactError("payload_hash_mismatch", schema_version)
    if document.get("schema_version") != schema_version:
        raise GenerationalArtifactError("schema_version_mismatch", schema_version)
    _nested_validators[schema_version](document)
    return document


@dataclass(frozen=True, slots=True)
class GenerationalRunArtifactStore:
    """Append-only archive tree for one run attempt."""

    root: Path
    run_id: str
    attempt_id: str = "single"

    def __post_init__(self) -> None:
        require_safe_segment("run_id", self.run_id)
        require_safe_segment("attempt_id", self.attempt_id)
        object.__setattr__(self, "root", Path(self.root))

    @property
    def attempt_dir(self) -> Path:
        return self.root / self.run_id / self.attempt_id

    @property
    def history_dir(self) -> Path:
        return self.attempt_dir / "history"

    def write_config(self, payload: bytes) -> tuple[str, str]:
        path = self.attempt_dir / "config.json"
        _atomic_write(path, payload)
        relative = str(path.relative_to(self.root))
        return relative, _sha256(payload)

    def write_manifest(self, payload: Mapping[str, object]) -> bytes:
        if (self.attempt_dir / "completion.json").exists() or (
            self.attempt_dir / "failure.json"
        ).exists():
            raise GenerationalArtifactError("completed_attempt_immutable", "manifest")
        encoded = encode_generational_document(
            payload, schema_version=GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION
        )
        _atomic_write(self.attempt_dir / "manifest.json", encoded)
        return encoded

    def write_history(
        self, boundary_tick: int, payload: Mapping[str, object]
    ) -> bytes:
        encoded = encode_generational_document(
            payload, schema_version=GENERATIONAL_HISTORY_SCHEMA_VERSION
        )
        path = self.history_dir / f"{boundary_tick:012d}.json"
        _atomic_write(path, encoded)
        return encoded

    def write_completion(self, payload: Mapping[str, object]) -> bytes:
        encoded = encode_generational_document(
            payload, schema_version=GENERATIONAL_COMPLETION_SCHEMA_VERSION
        )
        _atomic_write(self.attempt_dir / "completion.json", encoded)
        return encoded

    def write_failure(self, payload: Mapping[str, object]) -> bytes:
        encoded = encode_generational_document(
            payload, schema_version=GENERATIONAL_FAILURE_SCHEMA_VERSION
        )
        _atomic_write(self.attempt_dir / "failure.json", encoded)
        return encoded

    def read_manifest(self) -> dict[str, object]:
        return decode_generational_document(
            (self.attempt_dir / "manifest.json").read_bytes(),
            schema_version=GENERATIONAL_RUN_MANIFEST_SCHEMA_VERSION,
        )

    def read_completion(self) -> dict[str, object]:
        return decode_generational_document(
            (self.attempt_dir / "completion.json").read_bytes(),
            schema_version=GENERATIONAL_COMPLETION_SCHEMA_VERSION,
        )

    def read_failure(self) -> dict[str, object]:
        return decode_generational_document(
            (self.attempt_dir / "failure.json").read_bytes(),
            schema_version=GENERATIONAL_FAILURE_SCHEMA_VERSION,
        )

    def history_refs(self) -> tuple[dict[str, str], ...]:
        if not self.history_dir.exists():
            return ()
        refs: list[dict[str, str]] = []
        for path in sorted(self.history_dir.glob("*.json"), key=lambda item: item.name):
            payload = path.read_bytes()
            decode_generational_document(
                payload, schema_version=GENERATIONAL_HISTORY_SCHEMA_VERSION
            )
            refs.append(
                {
                    "path": str(path.relative_to(self.root)),
                    "sha256": _sha256(payload),
                }
            )
        return tuple(refs)


@dataclass(frozen=True, slots=True)
class SnapshotReference:
    snapshot_id: str
    integrity_hash: str
    next_tick: int

    def canonical_payload(self) -> dict[str, object]:
        return {
            "integrity_hash": self.integrity_hash,
            "next_tick": self.next_tick,
            "snapshot_id": self.snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class HistoricalBoundaryReference:
    revision: int
    objective_commit_hash: str
    snapshot_ref: SnapshotReference
    evidence_ref: dict[str, object] | None = None
    community_ref: dict[str, str] | None = None


class HistoricalBoundaryReader(Protocol):
    async def reference(
        self, run_id: str, boundary_tick: int
    ) -> HistoricalBoundaryReference: ...


class GenerationalHistoryObserver:
    """Write detached generational history sidecars after finalization."""

    def __init__(
        self,
        *,
        store: GenerationalRunArtifactStore,
        reader: HistoricalBoundaryReader,
        cadence_ticks: int | None,
        sample_on_generation_change: bool,
    ) -> None:
        if cadence_ticks is not None and (
            isinstance(cadence_ticks, bool)
            or not isinstance(cadence_ticks, int)
            or cadence_ticks < 1
        ):
            raise GenerationalArtifactError("invalid_cadence", "history")
        self._store = store
        self._reader = reader
        self._cadence = cadence_ticks
        self._sample_on_generation_change = sample_on_generation_change
        self._last_generation = 0

    def _reasons(
        self, boundary: object, stop_evidence: object
    ) -> tuple[str, ...]:
        from simulation.generational_models import GenerationalBoundary

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        reasons: list[str] = []
        tick = boundary.progress.boundary_tick
        if self._cadence is not None and tick % self._cadence == 0:
            reasons.append("cadence")
        generation = boundary.progress.max_generation_index_seen
        if self._sample_on_generation_change and generation > self._last_generation:
            reasons.append("generation_change")
            self._last_generation = generation
        if stop_evidence is not None:
            reasons.append("terminal")
        return tuple(sorted(set(reasons)))

    async def observe(self, boundary: object, stop_evidence: object) -> None:
        from simulation.generational_models import GenerationalBoundary, StopEvidence

        if type(boundary) is not GenerationalBoundary:
            raise TypeError("boundary must be GenerationalBoundary")
        if stop_evidence is not None and type(stop_evidence) is not StopEvidence:
            raise TypeError("stop_evidence must be StopEvidence or None")
        reasons = self._reasons(boundary, stop_evidence)
        if not reasons:
            return
        tick = boundary.progress.boundary_tick
        reference = await self._reader.reference(self._store.run_id, tick)
        if reference.snapshot_ref.next_tick > tick:
            raise GenerationalArtifactError("snapshot_after_boundary", "history")
        if "cadence" in reasons and reference.snapshot_ref.next_tick != tick:
            raise GenerationalArtifactError("cadence_snapshot_missing", "history")
        from simulation.generational_serialization import (
            encode_population_progress,
            encode_stop_evidence,
        )

        payload: dict[str, object] = {
            "boundary_tick": tick,
            "community_ref": reference.community_ref,
            "evidence_ref": reference.evidence_ref,
            "last_completed_tick": (
                None if tick == 0 else tick - 1
            ),
            "objective_commit_hash": reference.objective_commit_hash,
            "payload_hash": "0" * 64,
            "population_progress": encode_population_progress(boundary.progress),
            "revision": reference.revision,
            "run_id": self._store.run_id,
            "sample_reasons": list(reasons),
            "schema_version": GENERATIONAL_HISTORY_SCHEMA_VERSION,
            "snapshot_ref": reference.snapshot_ref.canonical_payload(),
            "stop_evidence": (
                None if stop_evidence is None else encode_stop_evidence(stop_evidence)
            ),
        }
        self._store.write_history(tick, payload)
        _LOG.info(
            "generational_history_written run_id=%s boundary=%s reasons=%s",
            self._store.run_id,
            tick,
            list(reasons),
        )


def source_identity_preflight(
    *,
    code_revision: str,
    source_clean: bool,
    source_artifact_digest: str | None,
) -> dict[str, object]:
    """Validate the exact-archive source identity contract."""
    if not code_revision:
        raise GenerationalArtifactError("missing_source_revision", "source_identity")
    if type(source_clean) is not bool:
        raise GenerationalArtifactError("invalid_boolean", "source_clean")
    if not source_clean and not source_artifact_digest:
        raise GenerationalArtifactError(
            "clean_source_assertion_required", "source_identity"
        )
    return {
        "code_revision": code_revision,
        "source_artifact_digest": source_artifact_digest,
        "source_clean": source_clean,
    }


@dataclass(frozen=True, slots=True)
class CompletionInputs:
    run_id: str
    manifest_hash: str
    result_document: dict[str, object]
    seed_manifest_hash: str
    source_identity: dict[str, object]
    execution_recipe_hash: str
    final_progress: dict[str, object]
    recording_usage_ref: dict[str, object]
    history_refs: tuple[dict[str, str], ...]


def write_completion(
    store: GenerationalRunArtifactStore, inputs: CompletionInputs
) -> bytes:
    payload: dict[str, object] = {
        "completion_hash": "0" * 64,
        "execution_recipe_hash": inputs.execution_recipe_hash,
        "final_progress": inputs.final_progress,
        "history_refs": list(inputs.history_refs),
        "manifest_hash": inputs.manifest_hash,
        "recording_usage_ref": inputs.recording_usage_ref,
        "result_document": inputs.result_document,
        "run_id": inputs.run_id,
        "schema_version": GENERATIONAL_COMPLETION_SCHEMA_VERSION,
        "seed_manifest_hash": inputs.seed_manifest_hash,
        "source_identity": inputs.source_identity,
    }
    return store.write_completion(payload)
