"""Immutable sibling artifacts for V3 civilization benchmark attempts.

These documents are canonical, hash-addressed research sidecars. They never
replace runner/result/archive schemas, never duplicate private payloads, and
fail closed on tampering, unknown fields, path escapes or identity collisions.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from experiments.civilization_benchmark_models import (
    V3_BENCHMARK_ID_PREFIX,
    V3_BENCHMARK_SUITE_ID,
    V3_VISUAL_BENCHMARK_ID,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkRunResult,
)
from simulation.generational_seeds import canonical_sha256
from world.identifiers import require_stable_id

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_artifacts"
)

RUN_SCHEMA_ID: Final[str] = "civilization-benchmark-run-v1"
SUITE_SCHEMA_ID: Final[str] = "civilization-benchmark-suite-v1"

_RUN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_id",
        "suite_id",
        "scenario_id",
        "lane",
        "profile",
        "arm_id",
        "seed",
        "source_identity",
        "config_fingerprint",
        "recipe",
        "run_id",
        "execution",
        "checks",
        "outcome",
        "publication",
        "comparison",
        "intervention_receipts",
        "artifact_hash",
    }
)
_SUITE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_id",
        "suite_id",
        "profile",
        "source_identity",
        "runs",
        "required",
        "complete",
        "status",
        "artifact_hash",
    }
)


class BenchmarkArtifactError(ValueError):
    """Fail-closed artifact validation with a stable code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)
        _LOG.error("benchmark_artifact_invalid reason_code=%s", code)


def _require_exact_keys(
    data: Mapping[str, object], expected: frozenset[str], path: str
) -> None:
    actual = frozenset(data)
    if actual != expected:
        raise BenchmarkArtifactError(
            "unknown_fields" if actual - expected else "missing_fields",
            f"{path} expected={sorted(expected)!r} actual={sorted(actual)!r}",
        )


def _canonical_dumps(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def encode_document(document: Mapping[str, object]) -> bytes:
    """Encode a document, recomputing and validating its canonical hash."""
    payload = {key: value for key, value in document.items() if key != "artifact_hash"}
    digest = canonical_sha256(payload)
    supplied = document.get("artifact_hash")
    if supplied is not None and supplied != digest:
        raise BenchmarkArtifactError("artifact_hash_mismatch", "document digest")
    enriched = dict(payload)
    enriched["artifact_hash"] = digest
    return _canonical_dumps(enriched)


def decode_document(
    payload: bytes, *, schema_id: str
) -> dict[str, object]:
    """Strictly decode one artifact document and verify its digest."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BenchmarkArtifactError("invalid_json", "artifact") from exc
    if not isinstance(data, dict):
        raise BenchmarkArtifactError("invalid_object", "artifact")
    if data.get("schema_id") != schema_id:
        raise BenchmarkArtifactError("unknown_schema", str(data.get("schema_id")))
    expected = _RUN_KEYS if schema_id == RUN_SCHEMA_ID else _SUITE_KEYS
    _require_exact_keys(data, expected, "$")
    supplied = data.get("artifact_hash")
    if type(supplied) is not str:
        raise BenchmarkArtifactError("missing_artifact_hash", "$")
    recomputed = canonical_sha256(
        {key: value for key, value in data.items() if key != "artifact_hash"}
    )
    if supplied != recomputed:
        raise BenchmarkArtifactError("artifact_hash_mismatch", "$")
    return data


def build_run_document(
    *,
    scenario_id: str,
    lane: V3BenchmarkLane,
    profile: V3BenchmarkProfile,
    arm_id: str,
    seed: int,
    source_identity: Mapping[str, object],
    config_fingerprint: str,
    recipe: Mapping[str, object],
    run_id: str,
    result: V3BenchmarkRunResult,
) -> dict[str, object]:
    """Build the canonical per-attempt sibling document."""
    if result.scenario_id != scenario_id:
        raise BenchmarkArtifactError("result_mismatch", "scenario_id")
    if result.lane is not lane:
        raise BenchmarkArtifactError("result_mismatch", "lane")
    checks = [
        {
            "selector_id": check.selector_id,
            "selector_version": check.selector_version,
            "status": check.status.value,
            "reason_code": check.reason_code,
            "evidence": check.evidence.value,
            "coverage": check.coverage.value,
            "boundary_start_tick": check.boundary_start_tick,
            "boundary_end_tick": check.boundary_end_tick,
            "numerator": check.numerator,
            "denominator": check.denominator,
            "source_references": [
                {
                    "source_kind": item.source_kind.value,
                    "reference_id": item.reference_id,
                    "owner_id": item.owner_id,
                    "tick": item.tick,
                }
                for item in check.source_references
            ],
        }
        for check in result.checks
    ]
    receipts = [
        {
            "milestone_id": receipt.milestone_id,
            "status": receipt.status,
            "proposed_command_kind": receipt.proposed_command_kind,
            "effective_command_kind": receipt.effective_command_kind,
            "resolution_status": receipt.resolution_status,
        }
        for receipt in result.intervention_receipts
    ]
    document: dict[str, object] = {
        "schema_id": RUN_SCHEMA_ID,
        "suite_id": V3_BENCHMARK_SUITE_ID,
        "scenario_id": require_stable_id("scenario_id", scenario_id),
        "lane": lane.value,
        "profile": profile.value,
        "arm_id": require_stable_id("arm_id", arm_id),
        "seed": seed,
        "source_identity": dict(source_identity),
        "config_fingerprint": config_fingerprint,
        "recipe": dict(recipe),
        "run_id": run_id,
        "execution": {
            "status": result.execution_status.value,
            "ticks_committed": result.ticks_committed,
            "declared_horizon": result.declared_horizon,
        },
        "checks": checks,
        "outcome": {
            "phenomenon": result.phenomenon.value,
            "evidence": result.evidence.value,
            "coverage": result.coverage.value,
        },
        "publication": {
            "status": result.publication_status,
            "receipts": [],
        },
        "comparison": (
            None
            if result.comparison_id is None
            else {"comparison_id": result.comparison_id}
        ),
        "intervention_receipts": receipts,
    }
    document["artifact_hash"] = canonical_sha256(document)
    encode_document(document)
    return document


def run_passes(document: Mapping[str, object]) -> bool:
    """A run is eligible only when every required gate actually passed."""
    execution = document.get("execution")
    outcome = document.get("outcome")
    checks = document.get("checks")
    if not isinstance(execution, Mapping) or not isinstance(outcome, Mapping):
        return False
    if execution.get("status") != "completed":
        return False
    if execution.get("ticks_committed") != execution.get("declared_horizon"):
        return False
    if outcome.get("evidence") != "complete":
        return False
    if not isinstance(checks, list) or not checks:
        return False
    return all(
        isinstance(check, Mapping) and check.get("status") == "pass"
        for check in checks
    )


def _safe_root(root: Path | str) -> Path:
    path = Path(root)
    if path.is_symlink():
        raise BenchmarkArtifactError("path_escape", "root is a symlink")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _safe_child(root: Path, relative: str) -> Path:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise BenchmarkArtifactError("path_escape", relative)
    candidate = root / relative
    resolved = candidate.resolve()
    if root != resolved and root not in resolved.parents:
        raise BenchmarkArtifactError("path_escape", relative)
    for parent in candidate.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise BenchmarkArtifactError("path_escape", relative)
    if candidate.is_symlink():
        raise BenchmarkArtifactError("path_escape", relative)
    return candidate


def _atomic_write(path: Path, payload: bytes) -> None:
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


@dataclass(frozen=True, slots=True)
class BenchmarkRunReference:
    """Relative path plus digest of one published run document."""

    scenario_id: str
    lane: str
    arm_id: str
    relative_path: str
    artifact_hash: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "lane": self.lane,
            "arm_id": self.arm_id,
            "path": self.relative_path,
            "artifact_hash": self.artifact_hash,
        }


class BenchmarkArtifactStore:
    """Atomic, immutable publisher and verifier for benchmark siblings."""

    def __init__(self, root: Path | str, *, profile: V3BenchmarkProfile) -> None:
        if type(profile) is not V3BenchmarkProfile:
            raise BenchmarkArtifactError("invalid_profile", "profile")
        self._root = _safe_root(root)
        self._profile = profile

    @property
    def root(self) -> Path:
        return self._root

    def publish_run(self, document: Mapping[str, object]) -> BenchmarkRunReference:
        scenario_id = document["scenario_id"]
        lane = document["lane"]
        arm_id = document["arm_id"]
        assert type(scenario_id) is str and type(lane) is str and type(arm_id) is str
        if not scenario_id.startswith(V3_BENCHMARK_ID_PREFIX):
            if scenario_id != V3_VISUAL_BENCHMARK_ID:
                raise BenchmarkArtifactError("invalid_scenario_id", scenario_id)
        digest = document["artifact_hash"]
        assert type(digest) is str
        relative = f"runs/{scenario_id}--{lane}--{arm_id}--{digest[:16]}.json"
        path = _safe_child(self._root, relative)
        payload = encode_document(document)
        if path.exists():
            if path.read_bytes() != payload:
                raise BenchmarkArtifactError("identity_collision", relative)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, payload)
        _LOG.info(
            "benchmark_run_artifact_published scenario_id=%s lane=%s path=%s",
            scenario_id,
            lane,
            relative,
        )
        return BenchmarkRunReference(
            scenario_id=scenario_id,
            lane=lane,
            arm_id=arm_id,
            relative_path=relative,
            artifact_hash=digest,
        )

    def publish_suite(
        self,
        *,
        source_identity: Mapping[str, object],
        run_references: Sequence[BenchmarkRunReference],
        required: Sequence[tuple[str, str]],
    ) -> dict[str, object]:
        for reference in run_references:
            path = _safe_child(self._root, reference.relative_path)
            if not path.exists():
                raise BenchmarkArtifactError(
                    "missing_reference", reference.relative_path
                )
            decode_document(path.read_bytes(), schema_id=RUN_SCHEMA_ID)
        covered = {(item.scenario_id, item.lane) for item in run_references}
        missing = [pair for pair in required if pair not in covered]
        passing = {"complete": True}
        for reference in run_references:
            document = decode_document(
                _safe_child(self._root, reference.relative_path).read_bytes(),
                schema_id=RUN_SCHEMA_ID,
            )
            if not run_passes(document):
                passing = {"complete": False}
                break
        complete = not missing and passing["complete"]
        suite: dict[str, object] = {
            "schema_id": SUITE_SCHEMA_ID,
            "suite_id": V3_BENCHMARK_SUITE_ID,
            "profile": self._profile.value,
            "source_identity": dict(source_identity),
            "runs": [item.canonical_payload() for item in run_references],
            "required": [
                {"scenario_id": scenario_id, "lane": lane}
                for scenario_id, lane in required
            ],
            "complete": complete,
            "status": "complete" if complete else "incomplete",
        }
        suite["artifact_hash"] = canonical_sha256(suite)
        payload = encode_document(suite)
        path = _safe_child(self._root, "suite.json")
        if path.exists() and path.read_bytes() != payload:
            raise BenchmarkArtifactError("suite_overwrite", "suite.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, payload)
        _LOG.info(
            "benchmark_suite_published run_count=%s complete=%s",
            len(run_references),
            complete,
        )
        return suite

    def verify(
        self,
        *,
        source_identity: Mapping[str, object],
        require_complete: bool = False,
    ) -> dict[str, object]:
        suite_path = _safe_child(self._root, "suite.json")
        if not suite_path.exists():
            raise BenchmarkArtifactError("missing_suite", "suite.json")
        if suite_path.is_symlink():
            raise BenchmarkArtifactError("path_escape", "suite.json")
        suite = decode_document(suite_path.read_bytes(), schema_id=SUITE_SCHEMA_ID)
        if suite.get("source_identity") != dict(source_identity):
            raise BenchmarkArtifactError("source_identity_mismatch", "suite")
        runs = suite.get("runs")
        if not isinstance(runs, list):
            raise BenchmarkArtifactError("invalid_runs", "suite")
        for entry in runs:
            if not isinstance(entry, Mapping):
                raise BenchmarkArtifactError("invalid_runs", "suite")
            relative = entry.get("path")
            digest = entry.get("artifact_hash")
            if type(relative) is not str or type(digest) is not str:
                raise BenchmarkArtifactError("invalid_runs", "suite")
            path = _safe_child(self._root, relative)
            if not path.exists() or path.is_symlink():
                raise BenchmarkArtifactError("missing_reference", relative)
            document = decode_document(path.read_bytes(), schema_id=RUN_SCHEMA_ID)
            if document.get("artifact_hash") != digest:
                raise BenchmarkArtifactError("reference_hash_mismatch", relative)
        if require_complete and suite.get("complete") is not True:
            raise BenchmarkArtifactError("incomplete_suite", "required gates")
        return suite


__all__ = [
    "RUN_SCHEMA_ID",
    "SUITE_SCHEMA_ID",
    "BenchmarkArtifactError",
    "BenchmarkArtifactStore",
    "BenchmarkRunReference",
    "build_run_document",
    "decode_document",
    "encode_document",
    "run_passes",
]
