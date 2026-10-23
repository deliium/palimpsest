"""Strict, atomic sibling artifacts for historical-contingency experiments.

The store owns only the path-dependence research recipe. It never widens a
runner schema, a generational archive manifest, or SQL branch lineage.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from experiments.path_dependence_identity import (
    assign_branch_arms,
    build_branch_slots,
)
from experiments.path_dependence_models import (
    MAX_EVIDENCE_CHUNKS_PER_BRANCH,
    MAX_SPEC_DOCUMENT_BYTES,
    MAX_SPEC_DOCUMENT_DEPTH,
    PathDependenceSpec,
)
from experiments.path_dependence_serialization import (
    encode_path_dependence_spec_document,
    path_dependence_spec_fingerprint,
)
from simulation.runner_serialization import runner_config_fingerprint

_LOG: Final[logging.Logger] = logging.getLogger("experiments.path_dependence_artifacts")

ENSEMBLE_SCHEMA_VERSION: Final[str] = "path-dependence-ensemble-v1"
PREFIX_SCHEMA_VERSION: Final[str] = "path-dependence-prefix-v1"
BRANCH_SCHEMA_VERSION: Final[str] = "path-dependence-branch-v1"
OUTCOMES_SCHEMA_VERSION: Final[str] = "path-dependence-outcomes-v1"
COMPARISON_SCHEMA_VERSION: Final[str] = "path-dependence-comparison-v1"

MAX_ARTIFACT_BYTES: Final[int] = MAX_SPEC_DOCUMENT_BYTES
MAX_ARTIFACT_DEPTH: Final[int] = MAX_SPEC_DOCUMENT_DEPTH
MAX_EVIDENCE_CHUNKS: Final[int] = MAX_EVIDENCE_CHUNKS_PER_BRANCH

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

_ENSEMBLE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "ensemble_id",
        "spec",
        "spec_fingerprint",
        "config_fingerprint",
        "source_revision",
        "source_artifact_digest",
        "slots",
        "assignment",
        "provider",
        "selectors",
        "windows",
        "blocks",
        "digest",
    }
)
_PREFIX_COMMON_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "kind",
        "ensemble_id",
        "parent_scientific_id",
        "parent_attempt_id",
        "fork_tick",
        "boundary_tick",
        "boundary_revision",
        "config_fingerprint",
        "source_revision",
        "provider_identity",
        "complete_state_digest",
        "checkpoint_format_version",
        "bootstrap_hash",
        "snapshot_hash",
        "objective_head_hash",
        "common_setup_digest",
        "eligibility",
        "digest",
    }
)
_BRANCH_BASE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "kind",
        "ensemble_id",
        "parent_scientific_id",
        "parent_attempt_id",
        "fork_tick",
        "child_scientific_id",
        "child_attempt_id",
        "slot_ordinal",
        "arm_id",
        "action_schedule_digest",
        "assignment_seed",
        "assignment_policy",
        "prefix_digest",
        "digest",
    }
)
_BRANCH_PREPARATION_KEYS: Final[frozenset[str]] = _BRANCH_BASE_KEYS | {
    "expected_checkpoint_digest"
}
_BRANCH_RESULT_KEYS: Final[frozenset[str]] = _BRANCH_BASE_KEYS | {
    "child_run_id",
    "requested_actions",
    "treatment_ledger",
    "stop_reason",
    "terminal_tick",
    "terminal_revision",
    "pre_treatment_state_digest",
    "channel_manifest",
    "outcomes_digest",
}
_BRANCH_COMPLETION_KEYS: Final[frozenset[str]] = _BRANCH_BASE_KEYS | {
    "result_digest",
    "outcomes_digest",
    "objective_head_hash",
    "terminal_tick",
    "terminal_revision",
}
_BRANCH_FAILURE_KEYS: Final[frozenset[str]] = _BRANCH_BASE_KEYS | {
    "last_durable_tick",
    "stage",
    "committed_status",
    "reason_code",
}
_OUTCOMES_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "ensemble_id",
        "child_scientific_id",
        "child_attempt_id",
        "slot_ordinal",
        "fork_tick",
        "rows",
        "coverage",
        "evidence_refs",
        "digest",
    }
)
_COMPARISON_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "comparison_id",
        "ensemble_id",
        "spec_fingerprint",
        "input_digests",
        "contrasts",
        "formula_versions",
        "missing_policy",
        "multiplicity_policy",
        "causal_claim",
        "digest",
    }
)

_BRANCH_FILENAMES: Final[Mapping[str, str]] = {
    "preparation": "preparation.json",
    "result": "branch.json",
    "completion": "completion.json",
    "failure": "failure.json",
}


class PathDependenceArtifactError(RuntimeError):
    """Fail-closed artifact error with a safe code only."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ObjectiveRunReader(Protocol):
    """Read-only objective presence needed by completion verification."""

    def exists(self, run_id: str) -> bool: ...

    def terminal(self, run_id: str) -> Mapping[str, object] | None: ...


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


def _safe(name: str, value: object) -> str:
    if type(value) is not str or _SAFE_SEGMENT.fullmatch(value) is None:
        raise PathDependenceArtifactError("artifact_path_unsafe")
    return value


def _digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise PathDependenceArtifactError("artifact_hash_mismatch")
    return value


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PathDependenceArtifactError("artifact_conflict")
        result[key] = value
    return result


def _depth(value: object, depth: int = 1) -> int:
    if depth > MAX_ARTIFACT_DEPTH:
        raise PathDependenceArtifactError("artifact_conflict")
    if isinstance(value, Mapping):
        return max((_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return max((_depth(item, depth + 1) for item in value), default=depth)
    return depth


def _document_bytes(payload: Mapping[str, object], keys: frozenset[str]) -> bytes:
    if set(payload) != keys:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    body = {key: value for key, value in payload.items() if key != "digest"}
    expected = _sha256(canonical_bytes(body))
    if payload.get("digest") != expected:
        raise PathDependenceArtifactError("artifact_hash_mismatch")
    _depth(payload)
    encoded = canonical_bytes(payload)
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise PathDependenceArtifactError("artifact_conflict")
    return encoded


def _seal(payload: dict[str, object]) -> dict[str, object]:
    body = {key: value for key, value in payload.items() if key != "digest"}
    payload["digest"] = _sha256(canonical_bytes(body))
    return payload


def _load(path: Path, keys: frozenset[str]) -> dict[str, object]:
    if path.is_symlink():
        raise PathDependenceArtifactError("artifact_path_unsafe")
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise PathDependenceArtifactError("branch_unsealed") from exc
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise PathDependenceArtifactError("artifact_conflict")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PathDependenceArtifactError("artifact_hash_mismatch") from exc
    if not isinstance(data, dict):
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    _document_bytes(data, keys)
    return data


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink():
            raise PathDependenceArtifactError("artifact_path_unsafe")
        if path.read_bytes() == payload:
            return
        raise PathDependenceArtifactError("artifact_conflict")
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
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


def build_ensemble_document(
    spec: PathDependenceSpec,
    *,
    source_revision: str,
    source_artifact_digest: str,
) -> dict[str, object]:
    """Seal the immutable design, slot table, and assignment."""
    if type(spec) is not PathDependenceSpec:
        raise TypeError("spec must be PathDependenceSpec")
    _safe("source_revision", source_revision)
    _digest(source_artifact_digest)
    fingerprint = path_dependence_spec_fingerprint(spec)
    parent_id = f"pd-parent-{fingerprint[:24]}"
    slots = tuple(
        slot
        for fork_tick in spec.fork_ticks
        for slot in build_branch_slots(spec, parent_id, fork_tick)
    )
    assignments = {
        item.slot_ordinal: item.arm_id
        for item in assign_branch_arms(spec, slots, parent_identity=parent_id)
    }
    blocks = tuple(
        {
            "fork_tick": fork_tick.value,
            "numeric_seed": seed,
            "seed_ordinal": ordinal,
            "replicate": replicate,
        }
        for fork_tick in spec.fork_ticks
        for ordinal, seed in enumerate(spec.seeds)
        for replicate in range(spec.replicates_per_seed)
    )
    payload: dict[str, object] = {
        "schema_version": ENSEMBLE_SCHEMA_VERSION,
        "ensemble_id": parent_id,
        "spec": encode_path_dependence_spec_document(spec),
        "spec_fingerprint": fingerprint,
        "config_fingerprint": runner_config_fingerprint(spec.base),
        "source_revision": source_revision,
        "source_artifact_digest": source_artifact_digest,
        "slots": [
            {
                "slot_ordinal": slot.slot_ordinal,
                "numeric_seed": slot.numeric_seed,
                "seed_ordinal": slot.seed_ordinal,
                "replicate": slot.replicate,
                "fork_tick": slot.fork_tick.value,
                "child_run_id": slot.child_run_id,
                "arm_id": assignments[slot.slot_ordinal],
            }
            for slot in slots
        ],
        "assignment": {
            "algorithm": "permuted-treatment-blind-slots-v1",
            "seed": spec.assignment_seed,
            "slot_design_fingerprint": fingerprint,
        },
        "provider": {
            "adapter_kind": spec.base.provider.adapter_kind.value,
            "recording_policy": spec.base.provider.recording_policy.value,
            "exact_reproducibility": spec.base.provider.exact_reproducibility.value,
        },
        "selectors": [
            {
                "selector_id": selector.selector_id,
                "domain": selector.domain.value,
                "window_id": selector.window_id,
            }
            for selector in spec.selectors
        ],
        "windows": [
            {
                "window_id": window.window_id,
                "fork_tick": window.fork_tick.value,
                "start_tick": window.start_tick.value,
                "end_tick": window.end_tick.value,
            }
            for window in spec.windows
        ],
        "blocks": list(blocks),
    }
    return _seal(payload)


def build_prefix_document(
    *,
    ensemble_id: str,
    parent_scientific_id: str,
    parent_attempt_id: str,
    fork_tick: int,
    boundary_revision: int,
    config_fingerprint: str,
    source_revision: str,
    provider_identity: str,
    complete_state_digest: str,
    checkpoint_format_version: str,
    bootstrap_hash: str,
    snapshot_hash: str,
    objective_head_hash: str,
    common_setup_digest: str,
    eligible: bool,
    eligibility_reason: str,
    eligibility_witness: Sequence[object] = (),
) -> dict[str, object]:
    _safe("ensemble_id", ensemble_id)
    _safe("parent_scientific_id", parent_scientific_id)
    _safe("parent_attempt_id", parent_attempt_id)
    _digest(complete_state_digest)
    _digest(bootstrap_hash)
    _digest(snapshot_hash)
    _digest(objective_head_hash)
    payload: dict[str, object] = {
        "schema_version": PREFIX_SCHEMA_VERSION,
        "kind": "eligible" if eligible else "ineligible",
        "ensemble_id": ensemble_id,
        "parent_scientific_id": parent_scientific_id,
        "parent_attempt_id": parent_attempt_id,
        "fork_tick": int(fork_tick),
        "boundary_tick": int(fork_tick),
        "boundary_revision": int(boundary_revision),
        "config_fingerprint": config_fingerprint,
        "source_revision": source_revision,
        "provider_identity": provider_identity,
        "complete_state_digest": complete_state_digest,
        "checkpoint_format_version": checkpoint_format_version,
        "bootstrap_hash": bootstrap_hash,
        "snapshot_hash": snapshot_hash,
        "objective_head_hash": objective_head_hash,
        "common_setup_digest": common_setup_digest,
        "eligibility": {
            "eligible": bool(eligible),
            "reason_code": eligibility_reason,
            "witness": list(eligibility_witness),
        },
    }
    return _seal(payload)


def build_branch_document(
    *,
    kind: str,
    ensemble_id: str,
    parent_scientific_id: str,
    parent_attempt_id: str,
    fork_tick: int,
    child_scientific_id: str,
    child_attempt_id: str,
    slot_ordinal: int,
    arm_id: str,
    action_schedule_digest: str,
    assignment_seed: int,
    assignment_policy: str,
    prefix_digest: str,
    details: Mapping[str, object],
) -> dict[str, object]:
    keys = {
        "preparation": _BRANCH_PREPARATION_KEYS,
        "result": _BRANCH_RESULT_KEYS,
        "completion": _BRANCH_COMPLETION_KEYS,
        "failure": _BRANCH_FAILURE_KEYS,
    }.get(kind)
    if keys is None:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    _safe("ensemble_id", ensemble_id)
    _safe("child_scientific_id", child_scientific_id)
    _safe("child_attempt_id", child_attempt_id)
    _digest(prefix_digest)
    _digest(action_schedule_digest)
    payload: dict[str, object] = {
        "schema_version": BRANCH_SCHEMA_VERSION,
        "kind": kind,
        "ensemble_id": ensemble_id,
        "parent_scientific_id": parent_scientific_id,
        "parent_attempt_id": parent_attempt_id,
        "fork_tick": int(fork_tick),
        "child_scientific_id": child_scientific_id,
        "child_attempt_id": child_attempt_id,
        "slot_ordinal": int(slot_ordinal),
        "arm_id": arm_id,
        "action_schedule_digest": action_schedule_digest,
        "assignment_seed": int(assignment_seed),
        "assignment_policy": assignment_policy,
        "prefix_digest": prefix_digest,
        **dict(details),
    }
    if set(payload) | {"digest"} != keys:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    return _seal(payload)


def build_outcomes_document(
    *,
    ensemble_id: str,
    child_scientific_id: str,
    child_attempt_id: str,
    slot_ordinal: int,
    fork_tick: int,
    rows: Sequence[Mapping[str, object]],
    coverage: Mapping[str, object],
    evidence_refs: Sequence[str],
) -> dict[str, object]:
    _safe("ensemble_id", ensemble_id)
    _safe("child_scientific_id", child_scientific_id)
    _safe("child_attempt_id", child_attempt_id)
    payload: dict[str, object] = {
        "schema_version": OUTCOMES_SCHEMA_VERSION,
        "ensemble_id": ensemble_id,
        "child_scientific_id": child_scientific_id,
        "child_attempt_id": child_attempt_id,
        "slot_ordinal": int(slot_ordinal),
        "fork_tick": int(fork_tick),
        "rows": [dict(row) for row in rows],
        "coverage": dict(coverage),
        "evidence_refs": list(evidence_refs),
    }
    return _seal(payload)


def build_comparison_document(
    *,
    comparison_id: str,
    ensemble_id: str,
    spec_fingerprint: str,
    input_digests: Sequence[str],
    contrasts: Sequence[Mapping[str, object]],
    formula_versions: Mapping[str, str],
) -> dict[str, object]:
    _safe("comparison_id", comparison_id)
    _safe("ensemble_id", ensemble_id)
    if not input_digests:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    for digest in input_digests:
        _digest(digest)
    payload: dict[str, object] = {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "comparison_id": comparison_id,
        "ensemble_id": ensemble_id,
        "spec_fingerprint": spec_fingerprint,
        "input_digests": list(input_digests),
        "contrasts": [dict(item) for item in contrasts],
        "formula_versions": dict(formula_versions),
        "missing_policy": "complete_pair_conditional_no_zero_fill",
        "multiplicity_policy": "pointwise_exploratory_no_familywise_claim",
        "causal_claim": False,
    }
    return _seal(payload)


@dataclass(frozen=True, slots=True)
class VerifiedPathDependenceBranch:
    ensemble_id: str
    child_scientific_id: str
    child_attempt_id: str
    prefix: dict[str, object]
    result: dict[str, object]
    outcomes: dict[str, object]
    completion: dict[str, object]


class PathDependenceArtifactStore:
    """Atomic immutable artifact store rooted at one research directory."""

    __slots__ = ("_root",)

    def __init__(self, root: Path | str) -> None:
        path = Path(root)
        if not path.is_absolute():
            raise PathDependenceArtifactError("artifact_path_unsafe")
        self._root = path

    @property
    def root(self) -> Path:
        return self._root

    def _ensemble_dir(self, ensemble_id: str) -> Path:
        _safe("ensemble_id", ensemble_id)
        return self._root / ensemble_id

    def _prefix_path(
        self,
        ensemble_id: str,
        parent_id: str,
        attempt_id: str,
        fork_tick: int,
    ) -> Path:
        _safe("parent_id", parent_id)
        _safe("attempt_id", attempt_id)
        return (
            self._ensemble_dir(ensemble_id)
            / "prefixes"
            / parent_id
            / attempt_id
            / f"fork-{int(fork_tick)}"
            / "prefix.json"
        )

    def _branch_path(
        self, ensemble_id: str, child_id: str, attempt_id: str, kind: str
    ) -> Path:
        _safe("child_id", child_id)
        _safe("attempt_id", attempt_id)
        filename = _BRANCH_FILENAMES.get(kind)
        if filename is None:
            raise PathDependenceArtifactError("artifact_identity_mismatch")
        return (
            self._ensemble_dir(ensemble_id)
            / "branches"
            / child_id
            / attempt_id
            / filename
        )

    def _comparison_path(self, ensemble_id: str, comparison_id: str) -> Path:
        _safe("comparison_id", comparison_id)
        return self._ensemble_dir(ensemble_id) / "comparisons" / f"{comparison_id}.json"

    def write_ensemble(self, document: Mapping[str, object]) -> Path:
        data = dict(document)
        encoded = _document_bytes(data, _ENSEMBLE_KEYS)
        path = self._ensemble_dir(str(data["ensemble_id"])) / "ensemble.json"
        _atomic_write(path, encoded)
        _LOG.info("path_dependence_ensemble_sealed ensemble_id=%s", data["ensemble_id"])
        return path

    def read_ensemble(self, ensemble_id: str) -> dict[str, object]:
        path = self._ensemble_dir(ensemble_id) / "ensemble.json"
        return _load(path, _ENSEMBLE_KEYS)

    def write_prefix(
        self,
        *,
        ensemble_id: str,
        parent_id: str,
        attempt_id: str,
        fork_tick: int,
        document: Mapping[str, object],
    ) -> Path:
        data = dict(document)
        encoded = _document_bytes(data, _PREFIX_COMMON_KEYS)
        path = self._prefix_path(ensemble_id, parent_id, attempt_id, fork_tick)
        _atomic_write(path, encoded)
        return path

    def read_prefix(
        self,
        *,
        ensemble_id: str,
        parent_id: str,
        attempt_id: str,
        fork_tick: int,
    ) -> dict[str, object]:
        return _load(
            self._prefix_path(ensemble_id, parent_id, attempt_id, fork_tick),
            _PREFIX_COMMON_KEYS,
        )

    def write_branch(
        self,
        *,
        ensemble_id: str,
        child_id: str,
        attempt_id: str,
        kind: str,
        document: Mapping[str, object],
    ) -> Path:
        keys = {
            "preparation": _BRANCH_PREPARATION_KEYS,
            "result": _BRANCH_RESULT_KEYS,
            "completion": _BRANCH_COMPLETION_KEYS,
            "failure": _BRANCH_FAILURE_KEYS,
        }[kind]
        data = dict(document)
        encoded = _document_bytes(data, keys)
        path = self._branch_path(ensemble_id, child_id, attempt_id, kind)
        _atomic_write(path, encoded)
        return path

    def read_branch(
        self,
        *,
        ensemble_id: str,
        child_id: str,
        attempt_id: str,
        kind: str,
    ) -> dict[str, object]:
        keys = {
            "preparation": _BRANCH_PREPARATION_KEYS,
            "result": _BRANCH_RESULT_KEYS,
            "completion": _BRANCH_COMPLETION_KEYS,
            "failure": _BRANCH_FAILURE_KEYS,
        }[kind]
        return _load(self._branch_path(ensemble_id, child_id, attempt_id, kind), keys)

    def write_outcomes(
        self,
        *,
        ensemble_id: str,
        child_id: str,
        attempt_id: str,
        document: Mapping[str, object],
    ) -> Path:
        data = dict(document)
        encoded = _document_bytes(data, _OUTCOMES_KEYS)
        path = (
            self._ensemble_dir(ensemble_id)
            / "branches"
            / _safe("child_id", child_id)
            / _safe("attempt_id", attempt_id)
            / "outcomes.json"
        )
        _atomic_write(path, encoded)
        return path

    def read_outcomes(
        self, *, ensemble_id: str, child_id: str, attempt_id: str
    ) -> dict[str, object]:
        return _load(
            self._ensemble_dir(ensemble_id)
            / "branches"
            / _safe("child_id", child_id)
            / _safe("attempt_id", attempt_id)
            / "outcomes.json",
            _OUTCOMES_KEYS,
        )

    def write_comparison(
        self, *, ensemble_id: str, comparison_id: str, document: Mapping[str, object]
    ) -> Path:
        data = dict(document)
        encoded = _document_bytes(data, _COMPARISON_KEYS)
        path = self._comparison_path(ensemble_id, comparison_id)
        _atomic_write(path, encoded)
        return path

    def read_comparison(
        self, *, ensemble_id: str, comparison_id: str
    ) -> dict[str, object]:
        return _load(
            self._comparison_path(ensemble_id, comparison_id), _COMPARISON_KEYS
        )


def verify_path_dependence_branch(
    *,
    expected: Mapping[str, object],
    store: PathDependenceArtifactStore,
    repositories: ObjectiveRunReader,
) -> VerifiedPathDependenceBranch:
    """Verify one completed branch against independently expected identities."""
    ensemble_id = _safe("ensemble_id", expected.get("ensemble_id"))
    parent_id = _safe("parent_id", expected.get("parent_id"))
    parent_attempt = _safe("parent_attempt", expected.get("parent_attempt"))
    child_id = _safe("child_id", expected.get("child_id"))
    child_attempt = _safe("child_attempt", expected.get("child_attempt"))
    fork_tick = expected.get("fork_tick")
    if isinstance(fork_tick, bool) or type(fork_tick) is not int:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    prefix = store.read_prefix(
        ensemble_id=ensemble_id,
        parent_id=parent_id,
        attempt_id=parent_attempt,
        fork_tick=fork_tick,
    )
    if prefix.get("kind") != "eligible":
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    preparation = store.read_branch(
        ensemble_id=ensemble_id,
        child_id=child_id,
        attempt_id=child_attempt,
        kind="preparation",
    )
    result = store.read_branch(
        ensemble_id=ensemble_id,
        child_id=child_id,
        attempt_id=child_attempt,
        kind="result",
    )
    outcomes = store.read_outcomes(
        ensemble_id=ensemble_id, child_id=child_id, attempt_id=child_attempt
    )
    completion = store.read_branch(
        ensemble_id=ensemble_id,
        child_id=child_id,
        attempt_id=child_attempt,
        kind="completion",
    )
    if completion.get("kind") != "completion":
        raise PathDependenceArtifactError("branch_unsealed")
    for document in (prefix, preparation, result, outcomes, completion):
        if document.get("ensemble_id") != ensemble_id:
            raise PathDependenceArtifactError("artifact_identity_mismatch")
    if (
        preparation.get("prefix_digest") != prefix.get("digest")
        or completion.get("result_digest") != result.get("digest")
        or completion.get("outcomes_digest") != outcomes.get("digest")
    ):
        raise PathDependenceArtifactError("artifact_hash_mismatch")
    child_run_id = result.get("child_run_id")
    if not isinstance(child_run_id, str) or not child_run_id:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    if child_run_id != child_id:
        raise PathDependenceArtifactError("artifact_identity_mismatch")
    terminal = repositories.terminal(child_run_id)
    if terminal is None:
        raise PathDependenceArtifactError("objective_completion_unverified")
    if (
        terminal.get("terminal_tick") != completion.get("terminal_tick")
        or terminal.get("terminal_revision") != completion.get("terminal_revision")
        or terminal.get("head_hash") != completion.get("objective_head_hash")
    ):
        raise PathDependenceArtifactError("objective_completion_unverified")
    if result.get("stop_reason") in {
        "finalization_failure",
        "historical_artifact_failure",
        "technical_failure",
    }:
        raise PathDependenceArtifactError("objective_completion_unverified")
    return VerifiedPathDependenceBranch(
        ensemble_id=ensemble_id,
        child_scientific_id=child_id,
        child_attempt_id=child_attempt,
        prefix=prefix,
        result=result,
        outcomes=outcomes,
        completion=completion,
    )


__all__ = [
    "BRANCH_SCHEMA_VERSION",
    "COMPARISON_SCHEMA_VERSION",
    "ENSEMBLE_SCHEMA_VERSION",
    "MAX_ARTIFACT_BYTES",
    "MAX_ARTIFACT_DEPTH",
    "MAX_EVIDENCE_CHUNKS",
    "OUTCOMES_SCHEMA_VERSION",
    "PREFIX_SCHEMA_VERSION",
    "ObjectiveRunReader",
    "PathDependenceArtifactError",
    "PathDependenceArtifactStore",
    "VerifiedPathDependenceBranch",
    "build_branch_document",
    "build_comparison_document",
    "build_ensemble_document",
    "build_outcomes_document",
    "build_prefix_document",
    "canonical_bytes",
    "verify_path_dependence_branch",
]
