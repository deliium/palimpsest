"""Strict canonical codec for ``formal-rule-snapshot-v1``.

The artifact is independent of organization snapshots. Encoding is non-circular:
the digest is computed over the encoded bytes and the publication id is derived
from a normalized encoding with a placeholder publication id.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from typing import Final, cast

from simulation.formal_rule_models import (
    FORMAL_RULE_PUBLICATION_ID_PREFIX,
    MAX_FORMAL_RULE_SNAPSHOT_BYTES,
    FormalRuleArtifactError,
    FormalRuleCandidateRecord,
    FormalRuleCounts,
    FormalRuleCoverage,
    FormalRuleLineageEdgeRecord,
    FormalRuleObjectiveRow,
    FormalRuleRecord,
    FormalRuleSnapshot,
    FormalRuleSnapshotRef,
    FormalRuleVersionRecord,
    FormalRuleWindowRecord,
    FormalRuleWrittenRepresentationRecord,
)

__all__ = [
    "compute_formal_rule_publication_id",
    "decode_formal_rule_snapshot",
    "decode_formal_rule_value",
    "encode_formal_rule_snapshot",
    "encode_formal_rule_value",
    "formal_rule_digest",
    "validate_formal_rule_value",
]

_SNAPSHOT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "input_revision",
        "generated_tick",
        "publication_id",
        "candidates",
        "rules",
        "versions",
        "lineage",
        "objective_rows",
        "windows",
        "coverage",
        "counts",
        "provenance_code",
    }
)
_CANDIDATE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "candidate_id",
        "status",
        "scope_kind",
        "scope_digest",
        "action_token",
        "constraint_kinds",
        "stage",
        "authority_kinds",
        "system_count",
        "rule_count",
        "version_count",
        "competing_candidate_ids",
        "first_tick",
        "last_tick",
        "coverage",
    }
)
_RULE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "rule_id",
        "candidate_id",
        "stage",
        "constraint_kind",
        "scope_kind",
        "action_token",
        "authority_kind",
        "recognition",
        "written_representation",
        "sanction_kinds",
        "exception_count",
        "version_count",
        "latest_version",
        "proponent_count",
        "response_counts",
    }
)
_VERSION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "version_id",
        "rule_id",
        "version_number",
        "stage",
        "constraint_kind",
        "scope_kind",
        "scope_digest",
        "action_token",
        "authority_kind",
        "recognition",
        "written_representation",
        "sanction_kinds",
        "exception_count",
        "tick",
        "revision_kind",
        "supersedes_version_id",
    }
)
_WRITTEN_KEYS: Final[frozenset[str]] = frozenset(
    {"status", "artifact_present", "artifact_revision", "repository_present"}
)
_OBJECTIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "tick",
        "observed_artifact_count",
        "observed_repository_count",
        "observed_occurrence_count",
    }
)
_WINDOW_KEYS: Final[frozenset[str]] = frozenset(
    {"start_tick", "end_tick", "owner_count", "candidate_count"}
)
_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "edge_id",
        "source_candidate_id",
        "target_candidate_id",
        "kind",
        "tick",
        "jaccard",
        "containment",
    }
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset({"observed", "expected", "partial"})
_COUNTS_KEYS: Final[frozenset[str]] = frozenset(
    {"candidates", "rules", "versions", "objective_rows", "windows"}
)


def _fail(code: str = "formal_rule_invalid_value") -> None:
    raise FormalRuleArtifactError(code)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    _ = value
    _fail()
    return None


def validate_formal_rule_value(value: object) -> object:
    """Require a JSON-safe finite value tree."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            _fail()
        return value
    if type(value) is list:
        return [validate_formal_rule_value(item) for item in value]
    if type(value) is dict:
        checked: dict[str, object] = {}
        for key, item in value.items():
            if type(key) is not str:
                _fail()
            checked[key] = validate_formal_rule_value(item)
        return checked
    _fail()
    return None


def encode_formal_rule_value(value: object) -> bytes:
    checked = validate_formal_rule_value(value)
    return json.dumps(
        checked,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def decode_formal_rule_value(payload: bytes) -> object:
    if not isinstance(payload, (bytes, bytearray)):
        _fail()
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError:
        _fail()
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        _fail()
    return None


def _require_keys(value: object, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        _fail()
    mapping = cast(dict[str, object], value)
    if set(mapping) != keys:
        _fail()
    return mapping


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail()
    return cast(str, value)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value)


def _int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail()
    return cast(int, value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return _int(value)


def _float(value: object) -> float:
    if type(value) not in (float, int) or isinstance(value, bool):
        _fail()
    number = float(cast(float, value))
    if not math.isfinite(number):
        _fail()
    return number


def _bool(value: object) -> bool:
    if type(value) is not bool:
        _fail()
    return cast(bool, value)


def _list(value: object) -> list[object]:
    if type(value) is not list:
        _fail()
    return cast(list[object], value)


def _string_list(value: object) -> list[str]:
    return [_string(item) for item in _list(value)]


def _coverage_value(coverage: FormalRuleCoverage) -> dict[str, object]:
    return {
        "observed": coverage.observed,
        "expected": coverage.expected,
        "partial": coverage.partial,
    }


def _written_value(
    written: FormalRuleWrittenRepresentationRecord,
) -> dict[str, object]:
    return {
        "status": written.status,
        "artifact_present": written.artifact_present,
        "artifact_revision": written.artifact_revision,
        "repository_present": written.repository_present,
    }


def _snapshot_to_value(snapshot: FormalRuleSnapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.ref.run_id,
        "input_revision": snapshot.ref.input_revision,
        "generated_tick": snapshot.ref.generated_tick,
        "publication_id": snapshot.ref.publication_id,
        "candidates": [
            {
                "candidate_id": item.candidate_id,
                "status": item.status,
                "scope_kind": item.scope_kind,
                "scope_digest": item.scope_digest,
                "action_token": item.action_token,
                "constraint_kinds": list(item.constraint_kinds),
                "stage": item.stage,
                "authority_kinds": list(item.authority_kinds),
                "system_count": item.system_count,
                "rule_count": item.rule_count,
                "version_count": item.version_count,
                "competing_candidate_ids": list(item.competing_candidate_ids),
                "first_tick": item.first_tick,
                "last_tick": item.last_tick,
                "coverage": _coverage_value(item.coverage),
            }
            for item in snapshot.candidates
        ],
        "rules": [
            {
                "rule_id": item.rule_id,
                "candidate_id": item.candidate_id,
                "stage": item.stage,
                "constraint_kind": item.constraint_kind,
                "scope_kind": item.scope_kind,
                "action_token": item.action_token,
                "authority_kind": item.authority_kind,
                "recognition": item.recognition,
                "written_representation": _written_value(item.written_representation),
                "sanction_kinds": list(item.sanction_kinds),
                "exception_count": item.exception_count,
                "version_count": item.version_count,
                "latest_version": item.latest_version,
                "proponent_count": item.proponent_count,
                "response_counts": [
                    [kind, count] for kind, count in item.response_counts
                ],
            }
            for item in snapshot.rules
        ],
        "versions": [
            {
                "version_id": item.version_id,
                "rule_id": item.rule_id,
                "version_number": item.version_number,
                "stage": item.stage,
                "constraint_kind": item.constraint_kind,
                "scope_kind": item.scope_kind,
                "scope_digest": item.scope_digest,
                "action_token": item.action_token,
                "authority_kind": item.authority_kind,
                "recognition": item.recognition,
                "written_representation": _written_value(item.written_representation),
                "sanction_kinds": list(item.sanction_kinds),
                "exception_count": item.exception_count,
                "tick": item.tick,
                "revision_kind": item.revision_kind,
                "supersedes_version_id": item.supersedes_version_id,
            }
            for item in snapshot.versions
        ],
        "lineage": [
            {
                "edge_id": item.edge_id,
                "source_candidate_id": item.source_candidate_id,
                "target_candidate_id": item.target_candidate_id,
                "kind": item.kind,
                "tick": item.tick,
                "jaccard": item.jaccard,
                "containment": item.containment,
            }
            for item in snapshot.lineage
        ],
        "objective_rows": [
            {
                "tick": item.tick,
                "observed_artifact_count": item.observed_artifact_count,
                "observed_repository_count": item.observed_repository_count,
                "observed_occurrence_count": item.observed_occurrence_count,
            }
            for item in snapshot.objective_rows
        ],
        "windows": [
            {
                "start_tick": item.start_tick,
                "end_tick": item.end_tick,
                "owner_count": item.owner_count,
                "candidate_count": item.candidate_count,
            }
            for item in snapshot.windows
        ],
        "coverage": _coverage_value(snapshot.coverage),
        "counts": {
            "candidates": snapshot.counts.candidates,
            "rules": snapshot.counts.rules,
            "versions": snapshot.counts.versions,
            "objective_rows": snapshot.counts.objective_rows,
            "windows": snapshot.counts.windows,
        },
        "provenance_code": snapshot.provenance_code,
    }


def encode_formal_rule_snapshot(snapshot: FormalRuleSnapshot) -> bytes:
    """Encode one snapshot into canonical bytes with a size bound."""
    if type(snapshot) is not FormalRuleSnapshot:
        raise TypeError("snapshot must be FormalRuleSnapshot")
    payload = encode_formal_rule_value(_snapshot_to_value(snapshot))
    if len(payload) > MAX_FORMAL_RULE_SNAPSHOT_BYTES:
        raise FormalRuleArtifactError("formal_rule_size_limit")
    return payload


def _decode_written(value: object) -> FormalRuleWrittenRepresentationRecord:
    data = _require_keys(value, _WRITTEN_KEYS)
    return FormalRuleWrittenRepresentationRecord(
        status=_string(data["status"]),
        artifact_present=_bool(data["artifact_present"]),
        artifact_revision=_optional_int(data["artifact_revision"]),
        repository_present=_bool(data["repository_present"]),
    )


def _decode_coverage(value: object) -> FormalRuleCoverage:
    data = _require_keys(value, _COVERAGE_KEYS)
    return FormalRuleCoverage(
        observed=_int(data["observed"]),
        expected=_int(data["expected"]),
        partial=_bool(data["partial"]),
    )


def decode_formal_rule_snapshot(payload: bytes) -> FormalRuleSnapshot:
    """Strictly decode one snapshot, then re-encode for byte equality."""
    data = _require_keys(decode_formal_rule_value(payload), _SNAPSHOT_KEYS)
    counts = _require_keys(data["counts"], _COUNTS_KEYS)
    snapshot = FormalRuleSnapshot(
        ref=FormalRuleSnapshotRef(
            run_id=_string(data["run_id"]),
            input_revision=_string(data["input_revision"]),
            generated_tick=_int(data["generated_tick"]),
            publication_id=_string(data["publication_id"]),
        ),
        schema_version=_string(data["schema_version"]),
        policy_version=_string(data["policy_version"]),
        candidates=tuple(
            FormalRuleCandidateRecord(
                candidate_id=_string(item["candidate_id"]),
                status=_string(item["status"]),
                scope_kind=_string(item["scope_kind"]),
                scope_digest=_string(item["scope_digest"]),
                action_token=_string(item["action_token"]),
                constraint_kinds=tuple(_string_list(item["constraint_kinds"])),
                stage=_string(item["stage"]),
                authority_kinds=tuple(_string_list(item["authority_kinds"])),
                system_count=_int(item["system_count"]),
                rule_count=_int(item["rule_count"]),
                version_count=_int(item["version_count"]),
                competing_candidate_ids=tuple(
                    _string_list(item["competing_candidate_ids"])
                ),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                coverage=_decode_coverage(item["coverage"]),
            )
            for item in (
                _require_keys(raw, _CANDIDATE_KEYS) for raw in _list(data["candidates"])
            )
        ),
        rules=tuple(
            FormalRuleRecord(
                rule_id=_string(item["rule_id"]),
                candidate_id=_string(item["candidate_id"]),
                stage=_string(item["stage"]),
                constraint_kind=_string(item["constraint_kind"]),
                scope_kind=_string(item["scope_kind"]),
                action_token=_string(item["action_token"]),
                authority_kind=_string(item["authority_kind"]),
                recognition=_string(item["recognition"]),
                written_representation=_decode_written(item["written_representation"]),
                sanction_kinds=tuple(_string_list(item["sanction_kinds"])),
                exception_count=_int(item["exception_count"]),
                version_count=_int(item["version_count"]),
                latest_version=_int(item["latest_version"]),
                proponent_count=_int(item["proponent_count"]),
                response_counts=tuple(
                    (_string(pair[0]), _int(pair[1]))
                    for pair in (_list(raw) for raw in _list(item["response_counts"]))
                ),
            )
            for item in (_require_keys(raw, _RULE_KEYS) for raw in _list(data["rules"]))
        ),
        versions=tuple(
            FormalRuleVersionRecord(
                version_id=_string(item["version_id"]),
                rule_id=_string(item["rule_id"]),
                version_number=_int(item["version_number"]),
                stage=_string(item["stage"]),
                constraint_kind=_string(item["constraint_kind"]),
                scope_kind=_string(item["scope_kind"]),
                scope_digest=_string(item["scope_digest"]),
                action_token=_string(item["action_token"]),
                authority_kind=_string(item["authority_kind"]),
                recognition=_string(item["recognition"]),
                written_representation=_decode_written(item["written_representation"]),
                sanction_kinds=tuple(_string_list(item["sanction_kinds"])),
                exception_count=_int(item["exception_count"]),
                tick=_int(item["tick"]),
                revision_kind=_string(item["revision_kind"]),
                supersedes_version_id=_optional_string(item["supersedes_version_id"]),
            )
            for item in (
                _require_keys(raw, _VERSION_KEYS) for raw in _list(data["versions"])
            )
        ),
        lineage=tuple(
            FormalRuleLineageEdgeRecord(
                edge_id=_string(item["edge_id"]),
                source_candidate_id=_string(item["source_candidate_id"]),
                target_candidate_id=_string(item["target_candidate_id"]),
                kind=_string(item["kind"]),
                tick=_int(item["tick"]),
                jaccard=_float(item["jaccard"]),
                containment=_float(item["containment"]),
            )
            for item in (
                _require_keys(raw, _EDGE_KEYS) for raw in _list(data["lineage"])
            )
        ),
        objective_rows=tuple(
            FormalRuleObjectiveRow(
                tick=_int(item["tick"]),
                observed_artifact_count=_int(item["observed_artifact_count"]),
                observed_repository_count=_int(item["observed_repository_count"]),
                observed_occurrence_count=_int(item["observed_occurrence_count"]),
            )
            for item in (
                _require_keys(raw, _OBJECTIVE_KEYS)
                for raw in _list(data["objective_rows"])
            )
        ),
        windows=tuple(
            FormalRuleWindowRecord(
                start_tick=_int(item["start_tick"]),
                end_tick=_int(item["end_tick"]),
                owner_count=_int(item["owner_count"]),
                candidate_count=_int(item["candidate_count"]),
            )
            for item in (
                _require_keys(raw, _WINDOW_KEYS) for raw in _list(data["windows"])
            )
        ),
        coverage=_decode_coverage(data["coverage"]),
        counts=FormalRuleCounts(
            candidates=_int(counts["candidates"]),
            rules=_int(counts["rules"]),
            versions=_int(counts["versions"]),
            objective_rows=_int(counts["objective_rows"]),
            windows=_int(counts["windows"]),
        ),
        provenance_code=_string(data["provenance_code"]),
    )
    if encode_formal_rule_snapshot(snapshot) != bytes(payload):
        raise FormalRuleArtifactError("formal_rule_digest_mismatch")
    return snapshot


def formal_rule_digest(payload: bytes) -> str:
    """Return the SHA-256 hex digest over encoded artifact bytes."""
    if not isinstance(payload, (bytes, bytearray)):
        _fail()
    return hashlib.sha256(bytes(payload)).hexdigest()


def compute_formal_rule_publication_id(snapshot: FormalRuleSnapshot) -> str:
    """Derive a content-addressed ``frule-pub-`` id, non-circularly."""
    if type(snapshot) is not FormalRuleSnapshot:
        raise TypeError("snapshot must be FormalRuleSnapshot")
    placeholder = f"{FORMAL_RULE_PUBLICATION_ID_PREFIX}{'0' * 16}"
    normalized = replace(
        snapshot, ref=replace(snapshot.ref, publication_id=placeholder)
    )
    encoded = encode_formal_rule_snapshot(normalized)
    body = hashlib.sha256(
        f"{snapshot.ref.run_id}\x00".encode() + encoded
    ).hexdigest()[:16]
    return f"{FORMAL_RULE_PUBLICATION_ID_PREFIX}{body}"
