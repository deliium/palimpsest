"""Canonical encoding for ``organization-snapshot-v1``/``v2`` artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Final

from simulation.organization_models import (
    MAX_SNAPSHOT_BYTES,
    ORGANIZATION_SNAPSHOT_POLICY_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationLineageEdgeRecord,
    OrganizationMemberRecord,
    OrganizationObjectiveRow,
    OrganizationOperationRecord,
    OrganizationSnapshot,
    OrganizationStructuralRecord,
    OrganizationWindowRecord,
    require_publication_id,
)

__all__ = [
    "compute_organization_publication_id",
    "decode_organization_snapshot",
    "decode_organization_value",
    "encode_organization_snapshot",
    "encode_organization_value",
    "organization_digest",
    "validate_organization_value",
]

_SNAPSHOT_KEYS_V1: Final[frozenset[str]] = frozenset(
    {
        "schema_version",
        "policy_version",
        "run_id",
        "input_revision",
        "generated_tick",
        "publication_id",
        "coverage",
        "windows",
        "candidates",
        "edges",
        "objective_rows",
        "provenance_code",
    }
)
_SNAPSHOT_KEYS_V2: Final[frozenset[str]] = _SNAPSHOT_KEYS_V1
_WINDOW_KEYS_V1: Final[frozenset[str]] = frozenset(
    {
        "window_index",
        "start_tick",
        "end_tick",
        "candidate_ids",
        "member_count",
        "overlap_member_count",
        "lane_presence",
    }
)
_WINDOW_KEYS_V2: Final[frozenset[str]] = _WINDOW_KEYS_V1 | frozenset(
    {"operation_count", "contested_operation_count"}
)
_CANDIDATE_KEYS_V1: Final[frozenset[str]] = frozenset(
    {
        "organization_id",
        "creation_tick",
        "first_tick",
        "last_tick",
        "status",
        "temporal_scope",
        "self_identified",
        "members",
        "structure",
        "window_indexes",
    }
)
_CANDIDATE_KEYS_V2: Final[frozenset[str]] = _CANDIDATE_KEYS_V1 | frozenset(
    {"operations"}
)
_MEMBER_KEYS: Final[frozenset[str]] = frozenset(
    {
        "member_id",
        "status",
        "basis",
        "temporal_scope",
        "first_tick",
        "last_tick",
        "expires_tick",
        "strength",
        "owner_support_count",
    }
)
_STRUCTURAL_KEYS: Final[frozenset[str]] = frozenset(
    {"kind", "anchor_id", "status", "first_tick", "last_tick", "resolved"}
)
_EDGE_KEYS: Final[frozenset[str]] = frozenset(
    {"kind", "tick", "from_id", "to_id", "jaccard", "containment"}
)
_OBJECTIVE_KEYS_V1: Final[frozenset[str]] = frozenset(
    {
        "window_index",
        "tick",
        "member_count",
        "role_count",
        "goal_count",
        "resource_count",
        "procedure_count",
        "record_count",
        "commitment_count",
        "identity_count",
        "resolved_anchor_count",
        "unresolved_anchor_count",
    }
)
_OBJECTIVE_KEYS_V2: Final[frozenset[str]] = _OBJECTIVE_KEYS_V1 | frozenset(
    {"operation_action_count"}
)
_OPERATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        "operation_id",
        "domain",
        "act",
        "stance",
        "authority_basis",
        "provenance_code",
        "outcome",
        "command_kind",
        "target_kind",
        "anchor_kind",
        "anchor_id",
        "tick",
        "first_tick",
        "last_tick",
        "support_count",
        "contest_count",
        "resolved",
    }
)
_COVERAGE_KEYS: Final[frozenset[str]] = frozenset({"observed", "expected", "ratio"})


def validate_organization_value(value: object) -> None:
    """Reject non-finite floats, non-string dict keys, and unsupported types."""
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise OrganizationArtifactError("organization_invalid_value")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            validate_organization_value(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise OrganizationArtifactError("organization_invalid_value")
            validate_organization_value(item)
        return
    raise OrganizationArtifactError("organization_invalid_value")


def encode_organization_value(value: object) -> bytes:
    """Canonical compact JSON with one trailing newline."""
    validate_organization_value(value)
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return f"{encoded}\n".encode()


def decode_organization_value(payload: bytes) -> object:
    """Strict JSON decode with duplicate-key and size rejection."""
    if not isinstance(payload, (bytes, bytearray)):
        raise OrganizationArtifactError("organization_invalid_value")
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise OrganizationArtifactError("organization_size_limit")
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OrganizationArtifactError("organization_invalid_value") from exc
    if "NaN" in text or "Infinity" in text:
        raise OrganizationArtifactError("organization_invalid_value")
    try:
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except json.JSONDecodeError as exc:
        raise OrganizationArtifactError("organization_invalid_value") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise OrganizationArtifactError("organization_duplicate_key")
        result[key] = value
    return result


def _dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _require_keys(value: object, keys: frozenset[str]) -> dict[str, object]:
    data = _dict(value)
    if set(data) != keys:
        raise OrganizationArtifactError("organization_invalid_value")
    return data


def _string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return _string(value)


def _int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _float(value: object) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _bool(value: object) -> bool:
    if type(value) is not bool:
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _string_list(value: object) -> tuple[str, ...]:
    return tuple(_string(item) for item in _list(value))


def _lane_pair(value: object) -> tuple[str, bool]:
    pair = _list(value)
    if len(pair) != 2:
        raise OrganizationArtifactError("organization_invalid_value")
    return _string(pair[0]), _bool(pair[1])


def _operation_to_value(operation: OrganizationOperationRecord) -> dict[str, object]:
    return {
        "operation_id": operation.operation_id,
        "domain": operation.domain,
        "act": operation.act,
        "stance": operation.stance,
        "authority_basis": operation.authority_basis,
        "provenance_code": operation.provenance_code,
        "outcome": operation.outcome,
        "command_kind": operation.command_kind,
        "target_kind": operation.target_kind,
        "anchor_kind": operation.anchor_kind,
        "anchor_id": operation.anchor_id,
        "tick": operation.tick,
        "first_tick": operation.first_tick,
        "last_tick": operation.last_tick,
        "support_count": operation.support_count,
        "contest_count": operation.contest_count,
        "resolved": operation.resolved,
    }


def _operation_from_value(raw: object) -> OrganizationOperationRecord:
    item = _require_keys(raw, _OPERATION_KEYS)
    return OrganizationOperationRecord(
        operation_id=_string(item["operation_id"]),
        domain=_string(item["domain"]),
        act=_string(item["act"]),
        stance=_string(item["stance"]),
        authority_basis=_string(item["authority_basis"]),
        provenance_code=_string(item["provenance_code"]),
        outcome=_string(item["outcome"]),
        command_kind=_string(item["command_kind"]),
        target_kind=_string(item["target_kind"]),
        anchor_kind=_string(item["anchor_kind"]),
        anchor_id=_optional_string(item["anchor_id"]),
        tick=_int(item["tick"]),
        first_tick=_int(item["first_tick"]),
        last_tick=_int(item["last_tick"]),
        support_count=_int(item["support_count"]),
        contest_count=_int(item["contest_count"]),
        resolved=_bool(item["resolved"]),
    )


def _snapshot_to_value_v1(snapshot: OrganizationSnapshot) -> dict[str, object]:
    return {
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "input_revision": snapshot.input_revision,
        "generated_tick": snapshot.generated_tick,
        "publication_id": snapshot.publication_id,
        "coverage": {
            "observed": snapshot.coverage.observed,
            "expected": snapshot.coverage.expected,
            "ratio": snapshot.coverage.ratio,
        },
        "windows": [
            {
                "window_index": window.window_index,
                "start_tick": window.start_tick,
                "end_tick": window.end_tick,
                "candidate_ids": list(window.candidate_ids),
                "member_count": window.member_count,
                "overlap_member_count": window.overlap_member_count,
                "lane_presence": [
                    [name, present] for name, present in window.lane_presence
                ],
            }
            for window in snapshot.windows
        ],
        "candidates": [
            {
                "organization_id": candidate.organization_id,
                "creation_tick": candidate.creation_tick,
                "first_tick": candidate.first_tick,
                "last_tick": candidate.last_tick,
                "status": candidate.status,
                "temporal_scope": candidate.temporal_scope,
                "self_identified": candidate.self_identified,
                "members": [
                    {
                        "member_id": member.member_id,
                        "status": member.status,
                        "basis": member.basis,
                        "temporal_scope": member.temporal_scope,
                        "first_tick": member.first_tick,
                        "last_tick": member.last_tick,
                        "expires_tick": member.expires_tick,
                        "strength": member.strength,
                        "owner_support_count": member.owner_support_count,
                    }
                    for member in candidate.members
                ],
                "structure": [
                    {
                        "kind": item.kind,
                        "anchor_id": item.anchor_id,
                        "status": item.status,
                        "first_tick": item.first_tick,
                        "last_tick": item.last_tick,
                        "resolved": item.resolved,
                    }
                    for item in candidate.structure
                ],
                "window_indexes": list(candidate.window_indexes),
            }
            for candidate in snapshot.candidates
        ],
        "edges": [
            {
                "kind": edge.kind,
                "tick": edge.tick,
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "jaccard": edge.jaccard,
                "containment": edge.containment,
            }
            for edge in snapshot.edges
        ],
        "objective_rows": [
            {
                "window_index": row.window_index,
                "tick": row.tick,
                "member_count": row.member_count,
                "role_count": row.role_count,
                "goal_count": row.goal_count,
                "resource_count": row.resource_count,
                "procedure_count": row.procedure_count,
                "record_count": row.record_count,
                "commitment_count": row.commitment_count,
                "identity_count": row.identity_count,
                "resolved_anchor_count": row.resolved_anchor_count,
                "unresolved_anchor_count": row.unresolved_anchor_count,
            }
            for row in snapshot.objective_rows
        ],
        "provenance_code": snapshot.provenance_code,
    }


def _snapshot_to_value_v2(snapshot: OrganizationSnapshot) -> dict[str, object]:
    value = _snapshot_to_value_v1(snapshot)
    for encoded, window in zip(
        _list(value["windows"]), snapshot.windows, strict=True
    ):
        _dict(encoded).update(
            {
                "operation_count": window.operation_count,
                "contested_operation_count": window.contested_operation_count,
            }
        )
    for encoded, candidate in zip(
        _list(value["candidates"]), snapshot.candidates, strict=True
    ):
        _dict(encoded)["operations"] = [
            _operation_to_value(operation) for operation in candidate.operations
        ]
    for encoded, row in zip(
        _list(value["objective_rows"]), snapshot.objective_rows, strict=True
    ):
        _dict(encoded)["operation_action_count"] = row.operation_action_count
    return value


def _snapshot_to_value(snapshot: OrganizationSnapshot) -> dict[str, object]:
    if snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1:
        return _snapshot_to_value_v1(snapshot)
    return _snapshot_to_value_v2(snapshot)


def encode_organization_snapshot(snapshot: OrganizationSnapshot) -> bytes:
    """Encode one snapshot canonically and enforce the byte cap."""
    if type(snapshot) is not OrganizationSnapshot:
        raise OrganizationArtifactError("organization_invalid_value")
    if snapshot.schema_version not in SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS:
        raise OrganizationArtifactError("organization_invalid_value")
    payload = encode_organization_value(_snapshot_to_value(snapshot))
    if len(payload) > MAX_SNAPSHOT_BYTES:
        raise OrganizationArtifactError("organization_size_limit")
    return payload


def _decode_windows(
    data: dict[str, object], keys: frozenset[str], *, v1: bool
) -> tuple[OrganizationWindowRecord, ...]:
    windows: list[OrganizationWindowRecord] = []
    for raw in _list(data["windows"]):
        item = _require_keys(raw, keys)
        windows.append(
            OrganizationWindowRecord(
                window_index=_int(item["window_index"]),
                start_tick=_int(item["start_tick"]),
                end_tick=_int(item["end_tick"]),
                candidate_ids=_string_list(item["candidate_ids"]),
                member_count=_int(item["member_count"]),
                overlap_member_count=_int(item["overlap_member_count"]),
                lane_presence=tuple(
                    _lane_pair(pair) for pair in _list(item["lane_presence"])
                ),
                operation_count=0 if v1 else _int(item["operation_count"]),
                contested_operation_count=(
                    0 if v1 else _int(item["contested_operation_count"])
                ),
            )
        )
    return tuple(windows)


def _decode_candidates(
    data: dict[str, object], keys: frozenset[str], *, v1: bool
) -> tuple[OrganizationCandidateRecord, ...]:
    candidates: list[OrganizationCandidateRecord] = []
    for raw in _list(data["candidates"]):
        item = _require_keys(raw, keys)
        candidates.append(
            OrganizationCandidateRecord(
                organization_id=_string(item["organization_id"]),
                creation_tick=_int(item["creation_tick"]),
                first_tick=_int(item["first_tick"]),
                last_tick=_int(item["last_tick"]),
                status=_string(item["status"]),
                temporal_scope=_string(item["temporal_scope"]),
                self_identified=_bool(item["self_identified"]),
                members=tuple(
                    OrganizationMemberRecord(
                        member_id=_string(entry["member_id"]),
                        status=_string(entry["status"]),
                        basis=_string(entry["basis"]),
                        temporal_scope=_string(entry["temporal_scope"]),
                        first_tick=_int(entry["first_tick"]),
                        last_tick=_int(entry["last_tick"]),
                        expires_tick=(
                            None
                            if entry["expires_tick"] is None
                            else _int(entry["expires_tick"])
                        ),
                        strength=_float(entry["strength"]),
                        owner_support_count=_int(entry["owner_support_count"]),
                    )
                    for entry in (
                        _require_keys(raw_member, _MEMBER_KEYS)
                        for raw_member in _list(item["members"])
                    )
                ),
                structure=tuple(
                    OrganizationStructuralRecord(
                        kind=_string(entry["kind"]),
                        anchor_id=_string(entry["anchor_id"]),
                        status=_string(entry["status"]),
                        first_tick=_int(entry["first_tick"]),
                        last_tick=_int(entry["last_tick"]),
                        resolved=_bool(entry["resolved"]),
                    )
                    for entry in (
                        _require_keys(raw_item, _STRUCTURAL_KEYS)
                        for raw_item in _list(item["structure"])
                    )
                ),
                window_indexes=tuple(
                    _int(entry) for entry in _list(item["window_indexes"])
                ),
                operations=(
                    ()
                    if v1
                    else tuple(
                        _operation_from_value(entry)
                        for entry in _list(item["operations"])
                    )
                ),
            )
        )
    return tuple(candidates)


def _decode_objective_rows(
    data: dict[str, object], keys: frozenset[str], *, v1: bool
) -> tuple[OrganizationObjectiveRow, ...]:
    rows: list[OrganizationObjectiveRow] = []
    for raw in _list(data["objective_rows"]):
        item = _require_keys(raw, keys)
        rows.append(
            OrganizationObjectiveRow(
                window_index=_int(item["window_index"]),
                tick=_int(item["tick"]),
                member_count=_int(item["member_count"]),
                role_count=_int(item["role_count"]),
                goal_count=_int(item["goal_count"]),
                resource_count=_int(item["resource_count"]),
                procedure_count=_int(item["procedure_count"]),
                record_count=_int(item["record_count"]),
                commitment_count=_int(item["commitment_count"]),
                identity_count=_int(item["identity_count"]),
                resolved_anchor_count=_int(item["resolved_anchor_count"]),
                unresolved_anchor_count=_int(item["unresolved_anchor_count"]),
                operation_action_count=(
                    0 if v1 else _int(item["operation_action_count"])
                ),
            )
        )
    return tuple(rows)


def decode_organization_snapshot(payload: bytes) -> OrganizationSnapshot:
    """Strictly decode v1 or v2 with exact key sets and byte equality."""
    decoded = decode_organization_value(payload)
    schema_version = _string(_dict(decoded).get("schema_version"))
    if schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1:
        data = _require_keys(decoded, _SNAPSHOT_KEYS_V1)
        window_keys = _WINDOW_KEYS_V1
        candidate_keys = _CANDIDATE_KEYS_V1
        objective_keys = _OBJECTIVE_KEYS_V1
        v1 = True
    elif schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION:
        data = _require_keys(decoded, _SNAPSHOT_KEYS_V2)
        window_keys = _WINDOW_KEYS_V2
        candidate_keys = _CANDIDATE_KEYS_V2
        objective_keys = _OBJECTIVE_KEYS_V2
        v1 = False
    else:
        raise OrganizationArtifactError("organization_invalid_value")
    coverage = _require_keys(data["coverage"], _COVERAGE_KEYS)
    edges = tuple(
        OrganizationLineageEdgeRecord(
            kind=_string(item["kind"]),
            tick=_int(item["tick"]),
            from_id=_optional_string(item["from_id"]),
            to_id=_optional_string(item["to_id"]),
            jaccard=None if item["jaccard"] is None else _float(item["jaccard"]),
            containment=(
                None if item["containment"] is None else _float(item["containment"])
            ),
        )
        for item in (_require_keys(raw, _EDGE_KEYS) for raw in _list(data["edges"]))
    )
    snapshot = OrganizationSnapshot(
        schema_version=schema_version,
        policy_version=_string(data["policy_version"]),
        run_id=_string(data["run_id"]),
        input_revision=_string(data["input_revision"]),
        generated_tick=_int(data["generated_tick"]),
        publication_id=(
            "" if data["publication_id"] == "" else _string(data["publication_id"])
        ),
        coverage=OrganizationCoverage(
            observed=_int(coverage["observed"]),
            expected=_int(coverage["expected"]),
            ratio=None if coverage["ratio"] is None else _float(coverage["ratio"]),
        ),
        windows=_decode_windows(data, window_keys, v1=v1),
        candidates=_decode_candidates(data, candidate_keys, v1=v1),
        edges=edges,
        objective_rows=_decode_objective_rows(data, objective_keys, v1=v1),
        provenance_code=_string(data["provenance_code"]),
    )
    if snapshot.policy_version != ORGANIZATION_SNAPSHOT_POLICY_VERSION:
        raise OrganizationArtifactError("organization_invalid_value")
    if encode_organization_snapshot(snapshot) != bytes(payload):
        raise OrganizationArtifactError("organization_digest_mismatch")
    return snapshot


def organization_digest(payload: bytes) -> str:
    """SHA-256 hex digest of one encoded artifact."""
    if not isinstance(payload, (bytes, bytearray)):
        raise OrganizationArtifactError("organization_invalid_value")
    return hashlib.sha256(bytes(payload)).hexdigest()


def compute_organization_publication_id(snapshot: OrganizationSnapshot) -> str:
    """Derive the run-bound ``org-edge-`` publication id."""
    if type(snapshot) is not OrganizationSnapshot:
        raise OrganizationArtifactError("organization_invalid_value")
    from dataclasses import replace

    normalized = replace(snapshot, publication_id="")
    encoded = encode_organization_snapshot(normalized)
    digest = hashlib.sha256(
        snapshot.run_id.encode("utf-8") + b"\x00" + encoded
    ).hexdigest()
    return require_publication_id(f"org-edge-{digest[:16]}")
