"""Pure payload ↔ DTO helpers for the persistence adapter.

Detached DTOs only; no session or commit logic. Silent on success.
May import only ``simulation`` contracts (and local ``persistence`` modules).
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from persistence.errors import PersistenceCorruptionError
from persistence.orm import SimulationRunOrm, TickCommitOrm, WorldEventOrm
from simulation.journal import decode_persistence, encode_persistence, hash_snapshot
from simulation.models import RunId, SimulationRunConfig
from simulation.persistence import (
    PERSISTENCE_CODEC_VERSION,
    RunManifest,
    TickCommit,
    WorldSnapshot,
)

__all__ = [
    "advisory_lock_keys",
    "canonical_payload_dict",
    "event_details_payload",
    "event_from_orm",
    "manifest_from_run_orm",
    "nonneg_int_from_numeric",
    "snapshot_from_canonical_payload",
    "tick_commit_from_orm",
]

_TYPE_WORLD_EVENT = "world_event"
_TYPE_TICK_COMMIT = "tick_commit"
_TYPE_RUN_MANIFEST = "run_manifest"


def advisory_lock_keys(run_id: str) -> tuple[int, int]:
    """Deterministic PostgreSQL advisory-lock key pair for one run."""
    digest = hashlib.sha256(run_id.encode("utf-8")).digest()
    key1 = int.from_bytes(digest[0:4], "big", signed=True)
    key2 = int.from_bytes(digest[4:8], "big", signed=True)
    return key1, key2


def nonneg_int_from_numeric(value: object, *, field: str) -> int:
    """Convert Numeric/Decimal/int values without 64-bit truncation."""
    if isinstance(value, bool):
        raise PersistenceCorruptionError("invalid_numeric", operation=field)
    if isinstance(value, int):
        if value < 0:
            raise PersistenceCorruptionError("invalid_numeric", operation=field)
        return value
    if isinstance(value, Decimal):
        if value != value.to_integral_value() or value < 0:
            raise PersistenceCorruptionError("invalid_numeric", operation=field)
        return int(value)
    raise PersistenceCorruptionError("invalid_numeric", operation=field)


def canonical_payload_dict(value: object) -> dict[str, Any]:
    """JSON object form of a canonical persistence envelope (for JSONB storage)."""
    document = json.loads(encode_persistence(value).decode("utf-8"))
    if not isinstance(document, dict):
        raise PersistenceCorruptionError("invalid_payload", operation="encode")
    return document


def _decode_envelope(
    type_tag: str, data: dict[str, Any], expected: type | str
) -> object:
    envelope = {
        "data": data,
        "persistence_codec_version": PERSISTENCE_CODEC_VERSION,
        "type": type_tag,
    }
    payload = json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return decode_persistence(payload, expected)


def event_details_payload(event: object) -> dict[str, Any]:
    """Encoded details object for the world_events.details JSONB column."""
    envelope = canonical_payload_dict(event)
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise PersistenceCorruptionError("invalid_payload", operation="event_details")
    details = data.get("details")
    if not isinstance(details, dict):
        raise PersistenceCorruptionError("invalid_payload", operation="event_details")
    return details


def event_from_orm(row: WorldEventOrm) -> object:
    """Rebuild a detached WorldEvent from a stored row via the journal codec."""
    data = {
        "actor_id": row.actor_id,
        "details": dict(row.details),
        "event_id": row.event_id,
        "event_type": row.event_type,
        "request_id": row.request_id,
        "resulting_revision": nonneg_int_from_numeric(
            row.resulting_revision, field="resulting_revision"
        ),
        "run_id": row.run_id,
        "schema_version": row.schema_version,
        "sequence": row.sequence,
        "target_id": row.target_id,
        "tick": nonneg_int_from_numeric(row.tick, field="tick"),
        "world_id": row.world_id,
    }
    return _decode_envelope(_TYPE_WORLD_EVENT, data, _TYPE_WORLD_EVENT)


def tick_commit_from_orm(row: TickCommitOrm) -> TickCommit:
    data = {
        "base_revision": nonneg_int_from_numeric(
            row.base_revision, field="base_revision"
        ),
        "commit_hash": row.commit_hash,
        "event_count": row.event_count,
        "idempotency_key": row.idempotency_key,
        "payload_hash": row.payload_hash,
        "predecessor_commit_hash": row.predecessor_commit_hash,
        "resulting_revision": nonneg_int_from_numeric(
            row.resulting_revision, field="resulting_revision"
        ),
        "resulting_tick": nonneg_int_from_numeric(
            row.resulting_tick, field="resulting_tick"
        ),
        "run_id": row.run_id,
        "snapshot_id": row.snapshot_id,
        "tick": nonneg_int_from_numeric(row.tick, field="tick"),
    }
    decoded = _decode_envelope(_TYPE_TICK_COMMIT, data, TickCommit)
    if type(decoded) is not TickCommit:
        raise PersistenceCorruptionError(
            "invalid_commit", operation="tick_commit_from_orm"
        )
    return decoded


def manifest_from_run_orm(row: SimulationRunOrm) -> RunManifest:
    seed = nonneg_int_from_numeric(row.seed, field="seed")
    data = {
        "config": {"seed": seed},
        "derivation_version": row.derivation_version,
        "event_schema_version": row.event_schema_version,
        "persistence_codec_version": row.persistence_codec_version,
        "projector_version": row.projector_version,
        "run_id": row.run_id,
        "seed": seed,
        "world_id": row.world_id,
    }
    decoded = _decode_envelope(_TYPE_RUN_MANIFEST, data, RunManifest)
    if type(decoded) is not RunManifest:
        raise PersistenceCorruptionError(
            "invalid_manifest", operation="manifest_from_run_orm"
        )
    # Keep seed/config alignment explicit for Numeric round-trips.
    if decoded.seed != seed or decoded.config != SimulationRunConfig(seed=seed):
        raise PersistenceCorruptionError(
            "seed_mismatch", operation="manifest_from_run_orm"
        )
    if type(decoded.run_id) is not RunId:
        raise PersistenceCorruptionError(
            "invalid_manifest", operation="manifest_from_run_orm"
        )
    return decoded


def _json_ready(value: object) -> object:
    """Normalize JSONB-loaded values (Decimal) back to codec-friendly forms."""
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            return float(value)
        return int(value)
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def snapshot_from_canonical_payload(
    payload: dict[str, Any],
    *,
    expected_integrity_hash: str | None = None,
) -> WorldSnapshot:
    """Decode a stored canonical snapshot envelope and verify integrity hash."""
    if not isinstance(payload, dict):
        raise PersistenceCorruptionError(
            "invalid_payload", operation="snapshot_from_canonical_payload"
        )
    normalized = _json_ready(payload)
    if not isinstance(normalized, dict):
        raise PersistenceCorruptionError(
            "invalid_payload", operation="snapshot_from_canonical_payload"
        )
    if set(normalized) != {"persistence_codec_version", "type", "data"}:
        raise PersistenceCorruptionError(
            "invalid_envelope", operation="snapshot_from_canonical_payload"
        )
    raw = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    decoded = decode_persistence(raw, WorldSnapshot)
    if type(decoded) is not WorldSnapshot:
        raise PersistenceCorruptionError(
            "invalid_snapshot", operation="snapshot_from_canonical_payload"
        )
    computed = hash_snapshot(decoded)
    if computed.value != decoded.integrity_hash.value:
        raise PersistenceCorruptionError(
            "integrity_mismatch", operation="snapshot_from_canonical_payload"
        )
    if (
        expected_integrity_hash is not None
        and computed.value != expected_integrity_hash
    ):
        raise PersistenceCorruptionError(
            "integrity_mismatch", operation="snapshot_from_canonical_payload"
        )
    return decoded
