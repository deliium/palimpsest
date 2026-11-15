"""Canonical encoding, digest, and strict decoding for cascade snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.economic_cascades_models import (
    ECONOMIC_CASCADES_POLICY_VERSION,
    ECONOMIC_CASCADES_PUBLICATION_PREFIX,
    ECONOMIC_CASCADES_SNAPSHOT_VERSION,
    MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES,
    EconomicCascadeChainRecord,
    EconomicCascadeCoverageRecord,
    EconomicCascadeDependencyRecord,
    EconomicCascadeDisruptionRecord,
    EconomicCascadePropagationRecord,
    EconomicCascadesSnapshot,
    EconomicCascadeSummaryRecord,
)

__all__ = [
    "canonical_economic_cascades_json",
    "decode_economic_cascades_snapshot",
    "economic_cascades_digest",
    "encode_economic_cascades_snapshot",
    "finalize_economic_cascades_snapshot",
]


class _DuplicateKeyError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _row_payload(row: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for name in type(row).__dataclass_fields__:
        value = getattr(row, name)
        payload[name] = list(value) if isinstance(value, tuple) else value
    return payload


def _payload(
    snapshot: EconomicCascadesSnapshot,
    *,
    internal_digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "snapshot_version": snapshot.snapshot_version,
        "policy_version": snapshot.policy_version,
        "run_id": snapshot.run_id,
        "generated_from_tick": snapshot.generated_from_tick,
        "summary": _row_payload(snapshot.summary),
        "disruptions": [_row_payload(row) for row in snapshot.disruptions],
        "dependencies": [_row_payload(row) for row in snapshot.dependencies],
        "chains": [_row_payload(row) for row in snapshot.chains],
        "propagation": [_row_payload(row) for row in snapshot.propagation],
        "coverage": [_row_payload(row) for row in snapshot.coverage],
        "internal_digest": internal_digest,
        "publication_id": publication_id,
    }


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def canonical_economic_cascades_json(
    snapshot: EconomicCascadesSnapshot,
) -> bytes:
    """Return canonical bytes with the snapshot's declared digest fields."""

    if type(snapshot) is not EconomicCascadesSnapshot:
        raise ValueError("economic_cascades_snapshot_invalid")
    return _canonical_bytes(
        _payload(
            snapshot,
            internal_digest=snapshot.internal_digest,
            publication_id=snapshot.publication_id,
        )
    )


def economic_cascades_digest(snapshot: EconomicCascadesSnapshot) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not EconomicCascadesSnapshot:
        raise ValueError("economic_cascades_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(
                _payload(snapshot, internal_digest="", publication_id="")
            )
        ).hexdigest()
    )


def _publication_id(digest: str) -> str:
    if type(digest) is not str or not digest.startswith("sha256:"):
        raise ValueError("economic_cascades_snapshot_invalid")
    return (
        f"{ECONOMIC_CASCADES_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:16]}"
    )


def finalize_economic_cascades_snapshot(
    snapshot: EconomicCascadesSnapshot,
) -> EconomicCascadesSnapshot:
    """Assign the canonical digest and publication id."""

    if type(snapshot) is not EconomicCascadesSnapshot:
        raise ValueError("economic_cascades_snapshot_invalid")
    blank = replace(snapshot, internal_digest="", publication_id="")
    digest = economic_cascades_digest(blank)
    return replace(
        blank,
        internal_digest=digest,
        publication_id=_publication_id(digest),
    )


def encode_economic_cascades_snapshot(
    snapshot: EconomicCascadesSnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically and enforce the size cap."""

    if type(snapshot) is not EconomicCascadesSnapshot:
        raise ValueError("economic_cascades_snapshot_invalid")
    if not snapshot.internal_digest or not snapshot.publication_id:
        snapshot = finalize_economic_cascades_snapshot(snapshot)
    data = canonical_economic_cascades_json(snapshot)
    if len(data) > MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES:
        raise ValueError("economic_cascades_snapshot_oversize")
    return data


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("economic_cascades_snapshot_keys")
    return mapping


def decode_economic_cascades_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> EconomicCascadesSnapshot:
    """Strictly decode one canonical economic-cascade snapshot artifact."""

    if (
        type(payload) is not bytes
        or len(payload) > MAX_ECONOMIC_CASCADES_SNAPSHOT_BYTES
    ):
        raise ValueError("economic_cascades_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("economic_cascades_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "snapshot_version",
            "policy_version",
            "run_id",
            "generated_from_tick",
            "summary",
            "disruptions",
            "dependencies",
            "chains",
            "propagation",
            "coverage",
            "internal_digest",
            "publication_id",
        },
    )
    if top["snapshot_version"] != ECONOMIC_CASCADES_SNAPSHOT_VERSION:
        raise ValueError("economic_cascades_snapshot_version")
    if top["policy_version"] != ECONOMIC_CASCADES_POLICY_VERSION:
        raise ValueError("economic_cascades_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("economic_cascades_snapshot_run_mismatch")
    try:
        snapshot = EconomicCascadesSnapshot(
            snapshot_version=top["snapshot_version"],
            policy_version=top["policy_version"],
            run_id=top["run_id"],
            generated_from_tick=top["generated_from_tick"],
            summary=EconomicCascadeSummaryRecord(**top["summary"]),
            disruptions=tuple(
                EconomicCascadeDisruptionRecord(**row)
                for row in top["disruptions"]
            ),
            dependencies=tuple(
                EconomicCascadeDependencyRecord(**row)
                for row in top["dependencies"]
            ),
            chains=tuple(
                EconomicCascadeChainRecord(**row) for row in top["chains"]
            ),
            propagation=tuple(
                EconomicCascadePropagationRecord(**row)
                for row in top["propagation"]
            ),
            coverage=tuple(
                EconomicCascadeCoverageRecord(**row)
                for row in top["coverage"]
            ),
            internal_digest=top["internal_digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("economic_cascades_snapshot_corrupt") from exc
    blank = replace(snapshot, internal_digest="", publication_id="")
    if snapshot.internal_digest != economic_cascades_digest(blank):
        raise ValueError("economic_cascades_snapshot_digest_mismatch")
    if encode_economic_cascades_snapshot(snapshot) != payload:
        raise ValueError("economic_cascades_snapshot_noncanonical")
    return snapshot
