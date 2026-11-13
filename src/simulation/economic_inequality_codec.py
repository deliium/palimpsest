"""Canonical encoding, digest, and strict decoding for inequality snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.economic_inequality_models import (
    ECONOMIC_INEQUALITY_POLICY_VERSION,
    ECONOMIC_INEQUALITY_PUBLICATION_PREFIX,
    ECONOMIC_INEQUALITY_SNAPSHOT_VERSION,
    MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES,
    EconomicCohortRecord,
    EconomicDimensionRecord,
    EconomicInequalitySnapshot,
    EconomicInequalitySummaryRecord,
    EconomicSocietyRecord,
)

__all__ = [
    "canonical_economic_inequality_json",
    "decode_economic_inequality_snapshot",
    "economic_inequality_digest",
    "encode_economic_inequality_snapshot",
    "finalize_economic_inequality_snapshot",
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
    snapshot: EconomicInequalitySnapshot,
    *,
    digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _row_payload(snapshot.summary),
        "dimensions": [_row_payload(row) for row in snapshot.dimensions],
        "cohorts": [_row_payload(row) for row in snapshot.cohorts],
        "societies": [_row_payload(row) for row in snapshot.societies],
        "digest": digest,
        "publication_id": publication_id,
    }


def canonical_economic_inequality_json(
    snapshot: EconomicInequalitySnapshot,
) -> bytes:
    """Return canonical bytes with the snapshot's declared digest fields."""

    if type(snapshot) is not EconomicInequalitySnapshot:
        raise ValueError("economic_inequality_snapshot_invalid")
    return _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    )


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


def economic_inequality_digest(snapshot: EconomicInequalitySnapshot) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not EconomicInequalitySnapshot:
        raise ValueError("economic_inequality_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
        ).hexdigest()
    )


def compute_economic_inequality_publication_id(digest: str) -> str:
    if type(digest) is not str or not digest.startswith("sha256:"):
        raise ValueError("economic_inequality_snapshot_invalid")
    return (
        f"{ECONOMIC_INEQUALITY_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:16]}"
    )


def finalize_economic_inequality_snapshot(
    snapshot: EconomicInequalitySnapshot,
) -> EconomicInequalitySnapshot:
    """Assign the canonical digest and publication id."""

    digest = economic_inequality_digest(snapshot)
    return replace(
        snapshot,
        digest=digest,
        publication_id=compute_economic_inequality_publication_id(digest),
    )


def encode_economic_inequality_snapshot(
    snapshot: EconomicInequalitySnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically and enforce the size cap."""

    if type(snapshot) is not EconomicInequalitySnapshot:
        raise ValueError("economic_inequality_snapshot_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_economic_inequality_snapshot(snapshot)
    data = canonical_economic_inequality_json(snapshot)
    if len(data) > MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES:
        raise ValueError("economic_inequality_snapshot_oversize")
    return data


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("economic_inequality_snapshot_keys")
    return mapping


def _summary(
    snapshot: EconomicInequalitySnapshot,
) -> EconomicInequalitySummaryRecord:
    current = snapshot.summary
    windows = {
        *(row.window_index for row in snapshot.dimensions),
        *(row.window_index for row in snapshot.cohorts),
        *(row.window_index for row in snapshot.societies),
    }
    return EconomicInequalitySummaryRecord(
        dimension_row_count=len(snapshot.dimensions),
        cohort_row_count=len(snapshot.cohorts),
        society_row_count=len(snapshot.societies),
        window_count=len(windows),
        owner_count=current.owner_count,
        observed_owner_count=current.observed_owner_count,
        overlap_member_count=current.overlap_member_count,
        coverage=current.coverage,
        evidence_coverage=current.evidence_coverage,
        dimension_coverage=current.dimension_coverage,
        comparison_coverage=current.comparison_coverage,
        truncated=(
            current.truncated
            or current.coverage == "partial"
            or current.dimension_coverage == "partial"
            or current.comparison_coverage == "partial"
        ),
    )


def decode_economic_inequality_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> EconomicInequalitySnapshot:
    """Strictly decode one canonical inequality snapshot artifact."""

    if (
        type(payload) is not bytes
        or len(payload) > MAX_ECONOMIC_INEQUALITY_SNAPSHOT_BYTES
    ):
        raise ValueError("economic_inequality_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("economic_inequality_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "dimensions",
            "cohorts",
            "societies",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != ECONOMIC_INEQUALITY_SNAPSHOT_VERSION:
        raise ValueError("economic_inequality_snapshot_version")
    if top["policy_version"] != ECONOMIC_INEQUALITY_POLICY_VERSION:
        raise ValueError("economic_inequality_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("economic_inequality_snapshot_run_mismatch")
    try:
        snapshot = EconomicInequalitySnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=EconomicInequalitySummaryRecord(**top["summary"]),
            dimensions=tuple(
                EconomicDimensionRecord(
                    **{
                        **row,
                        "bin_shares_milli": tuple(
                            row.get("bin_shares_milli", ())
                        ),
                    }
                )
                for row in top["dimensions"]
            ),
            cohorts=tuple(
                EconomicCohortRecord(**row) for row in top["cohorts"]
            ),
            societies=tuple(
                EconomicSocietyRecord(**row) for row in top["societies"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("economic_inequality_snapshot_corrupt") from exc
    if snapshot.digest != economic_inequality_digest(snapshot):
        raise ValueError("economic_inequality_snapshot_digest_mismatch")
    expected = _summary(snapshot)
    declared = snapshot.summary
    for name in (
        "dimension_row_count",
        "cohort_row_count",
        "society_row_count",
        "window_count",
        "truncated",
    ):
        if getattr(declared, name) != getattr(expected, name):
            raise ValueError("economic_inequality_snapshot_summary_mismatch")
    if encode_economic_inequality_snapshot(snapshot) != payload:
        raise ValueError("economic_inequality_snapshot_noncanonical")
    return snapshot
