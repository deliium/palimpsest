"""Canonical codec for ``scientific-replication-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from simulation.replication_models import (
    REPLICATION_MAX_SNAPSHOT_BYTES,
    REPLICATION_PUBLICATION_PREFIX,
    REPLICATION_SNAPSHOT_POLICY_VERSION,
    REPLICATION_SNAPSHOT_VERSION,
    SNAPSHOT_KEYS,
    ReplicationSnapshotError,
    ScientificReplicationSnapshot,
)

_ROW_TYPES = frozenset(
    {
        "design",
        "attempt",
        "execution",
        "report",
        "comparison",
        "interpretation",
        "collaboration",
        "coverage",
    }
)


def _default(value: object) -> object:
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError("replication_snapshot_not_serializable")


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_default,
    )


def _top_body(snapshot: ScientificReplicationSnapshot) -> dict[str, Any]:
    return {
        "snapshot_version": snapshot.snapshot_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "generated_from_tick": snapshot.generated_from_tick,
        "summary": dict(snapshot.summary),
        "designs": [dict(row) for row in snapshot.designs],
        "attempts": [dict(row) for row in snapshot.attempts],
        "results": [dict(row) for row in snapshot.results],
        "comparisons": [dict(row) for row in snapshot.comparisons],
        "interpretations": [dict(row) for row in snapshot.interpretations],
        "collaborations": [dict(row) for row in snapshot.collaborations],
        "coverage": [dict(row) for row in snapshot.coverage],
        "internal_digest": "",
        "publication_id": "",
    }


def _digest(body: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical(body).encode("ascii")).hexdigest()


def finalize_replication_snapshot(
    snapshot: ScientificReplicationSnapshot,
) -> ScientificReplicationSnapshot:
    body = _top_body(snapshot)
    digest = _digest(body)
    return ScientificReplicationSnapshot(
        snapshot_version=snapshot.snapshot_version,
        policy_version=snapshot.policy_version,
        run_id=snapshot.run_id,
        generated_from_tick=snapshot.generated_from_tick,
        summary=snapshot.summary,
        designs=snapshot.designs,
        attempts=snapshot.attempts,
        results=snapshot.results,
        comparisons=snapshot.comparisons,
        interpretations=snapshot.interpretations,
        collaborations=snapshot.collaborations,
        coverage=snapshot.coverage,
        internal_digest=digest,
        publication_id=REPLICATION_PUBLICATION_PREFIX + digest[:16],
    )


def encode_replication_snapshot(snapshot: ScientificReplicationSnapshot) -> bytes:
    if not snapshot.internal_digest:
        snapshot = finalize_replication_snapshot(snapshot)
    body = _top_body(snapshot)
    body["internal_digest"] = snapshot.internal_digest
    body["publication_id"] = snapshot.publication_id
    material = (_canonical(body) + "\n").encode("ascii")
    if len(material) > REPLICATION_MAX_SNAPSHOT_BYTES:
        raise ReplicationSnapshotError("replication_snapshot_oversize")
    return material


def _row_token(record_type: str, row: Mapping[str, object]) -> str:
    payload = {
        "policy_version": REPLICATION_SNAPSHOT_POLICY_VERSION,
        "record_type": record_type,
        "row": {key: value for key, value in row.items() if key != "row_token"},
    }
    return "rrow-" + hashlib.sha256(_canonical(payload).encode("ascii")).hexdigest()


def replication_snapshot_row_token(
    record_type: str, row: Mapping[str, object]
) -> str:
    return _row_token(record_type, row)


def _validate_rows(
    rows: object, expected_types: frozenset[str]
) -> tuple[dict[str, object], ...]:
    if not isinstance(rows, list):
        raise ReplicationSnapshotError("replication_snapshot_invalid")
    seen: set[str] = set()
    result = []
    for item in rows:
        if not isinstance(item, dict):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        record_type = item.get("record_type")
        if record_type not in _ROW_TYPES or record_type not in expected_types:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        row_token = item.get("row_token")
        if type(row_token) is not str or not row_token.startswith("rrow-"):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if row_token != _row_token(record_type, item):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if row_token in seen:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        seen.add(row_token)
        if record_type == "execution" and item.get("row_kind") != "execution":
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        if record_type == "report" and item.get("row_kind") != "report":
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        result.append(item)
    return tuple(result)


def _pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReplicationSnapshotError("replication_snapshot_invalid")
        result[key] = value
    return result


def decode_replication_snapshot(payload: object) -> ScientificReplicationSnapshot:
    if isinstance(payload, (bytes, bytearray)):
        try:
            text = bytes(payload).decode("ascii")
            data = json.loads(text, object_pairs_hook=_pairs_hook)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReplicationSnapshotError("replication_snapshot_invalid") from exc
        if not text.endswith("\n") or text.endswith("\n\n"):
            raise ReplicationSnapshotError("replication_snapshot_invalid")
    elif isinstance(payload, Mapping):
        data = dict(payload)
    else:
        raise TypeError("decode_replication_snapshot requires mapping or bytes")
    if not isinstance(data, dict) or set(data) != SNAPSHOT_KEYS:
        raise ReplicationSnapshotError("replication_snapshot_invalid")
    if data["snapshot_version"] != REPLICATION_SNAPSHOT_VERSION:
        raise ReplicationSnapshotError("replication_snapshot_invalid")
    if data["policy_version"] != REPLICATION_SNAPSHOT_POLICY_VERSION:
        raise ReplicationSnapshotError("replication_snapshot_invalid")
    designs = _validate_rows(data["designs"], frozenset({"design"}))
    attempts = _validate_rows(data["attempts"], frozenset({"attempt"}))
    results = _validate_rows(
        data["results"], frozenset({"execution", "report"})
    )
    comparisons = _validate_rows(data["comparisons"], frozenset({"comparison"}))
    interpretations = _validate_rows(
        data["interpretations"], frozenset({"interpretation"})
    )
    collaborations = _validate_rows(
        data["collaborations"], frozenset({"collaboration"})
    )
    coverage = _validate_rows(data["coverage"], frozenset({"coverage"}))
    snapshot = ScientificReplicationSnapshot(
        snapshot_version=str(data["snapshot_version"]),
        policy_version=str(data["policy_version"]),
        run_id=str(data["run_id"]),
        generated_from_tick=data["generated_from_tick"],
        summary=data["summary"],
        designs=designs,
        attempts=attempts,
        results=results,
        comparisons=comparisons,
        interpretations=interpretations,
        collaborations=collaborations,
        coverage=coverage,
        internal_digest=str(data["internal_digest"]),
        publication_id=str(data["publication_id"]),
    )
    signed = encode_replication_snapshot(
        ScientificReplicationSnapshot(
            snapshot_version=snapshot.snapshot_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            generated_from_tick=snapshot.generated_from_tick,
            summary=snapshot.summary,
            designs=snapshot.designs,
            attempts=snapshot.attempts,
            results=snapshot.results,
            comparisons=snapshot.comparisons,
            interpretations=snapshot.interpretations,
            collaborations=snapshot.collaborations,
            coverage=snapshot.coverage,
            internal_digest=snapshot.internal_digest,
            publication_id=snapshot.publication_id,
        )
    )
    if isinstance(payload, (bytes, bytearray)) and signed != bytes(payload):
        raise ReplicationSnapshotError("replication_snapshot_digest_mismatch")
    expected = _digest(_top_body(snapshot))
    if expected != snapshot.internal_digest:
        raise ReplicationSnapshotError("replication_snapshot_digest_mismatch")
    if snapshot.publication_id != (
        REPLICATION_PUBLICATION_PREFIX + snapshot.internal_digest[:16]
    ):
        raise ReplicationSnapshotError("replication_snapshot_digest_mismatch")
    return snapshot


__all__ = [
    "decode_replication_snapshot",
    "encode_replication_snapshot",
    "finalize_replication_snapshot",
    "replication_snapshot_row_token",
]
