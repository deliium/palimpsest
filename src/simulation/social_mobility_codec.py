"""Canonical encoding, digest, and strict decoding for mobility snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.social_mobility_models import (
    MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES,
    SOCIAL_MOBILITY_POLICY_VERSION,
    SOCIAL_MOBILITY_PUBLICATION_PREFIX,
    SOCIAL_MOBILITY_SNAPSHOT_VERSION,
    SocialMobilityCoverageRecord,
    SocialMobilityDomainRecord,
    SocialMobilityGenerationRecord,
    SocialMobilityLagRecord,
    SocialMobilitySnapshot,
    SocialMobilitySummaryRecord,
)

__all__ = [
    "canonical_social_mobility_json",
    "compute_social_mobility_publication_id",
    "decode_social_mobility_snapshot",
    "encode_social_mobility_snapshot",
    "finalize_social_mobility_snapshot",
    "social_mobility_digest",
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
    snapshot: SocialMobilitySnapshot,
    *,
    digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _row_payload(snapshot.summary),
        "domains": [_row_payload(row) for row in snapshot.domains],
        "generations": [_row_payload(row) for row in snapshot.generations],
        "lags": [_row_payload(row) for row in snapshot.lags],
        "coverage": [_row_payload(row) for row in snapshot.coverage],
        "digest": digest,
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


def canonical_social_mobility_json(snapshot: SocialMobilitySnapshot) -> bytes:
    """Return canonical bytes with the snapshot's declared digest fields."""

    if type(snapshot) is not SocialMobilitySnapshot:
        raise ValueError("social_mobility_snapshot_invalid")
    return _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    )


def social_mobility_digest(snapshot: SocialMobilitySnapshot) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not SocialMobilitySnapshot:
        raise ValueError("social_mobility_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
        ).hexdigest()
    )


def compute_social_mobility_publication_id(digest: str) -> str:
    if type(digest) is not str or not digest.startswith("sha256:"):
        raise ValueError("social_mobility_snapshot_invalid")
    return f"{SOCIAL_MOBILITY_PUBLICATION_PREFIX}{digest.removeprefix('sha256:')[:16]}"


def finalize_social_mobility_snapshot(
    snapshot: SocialMobilitySnapshot,
) -> SocialMobilitySnapshot:
    """Assign the canonical digest and publication id."""

    digest = social_mobility_digest(snapshot)
    return replace(
        snapshot,
        digest=digest,
        publication_id=compute_social_mobility_publication_id(digest),
    )


def encode_social_mobility_snapshot(snapshot: SocialMobilitySnapshot) -> bytes:
    """Encode one finalized snapshot canonically and enforce the size cap."""

    if type(snapshot) is not SocialMobilitySnapshot:
        raise ValueError("social_mobility_snapshot_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_social_mobility_snapshot(snapshot)
    data = canonical_social_mobility_json(snapshot)
    if len(data) > MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES:
        raise ValueError("social_mobility_snapshot_oversize")
    return data


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("social_mobility_snapshot_keys")
    return mapping


def _summary(snapshot: SocialMobilitySnapshot) -> SocialMobilitySummaryRecord:
    current = snapshot.summary
    windows = {
        *(row.window_index for row in snapshot.domains),
        *(row.window_index for row in snapshot.generations),
        *(row.window_index for row in snapshot.lags),
        *(row.window_index for row in snapshot.coverage),
    }
    return SocialMobilitySummaryRecord(
        domain_row_count=len(snapshot.domains),
        generation_row_count=len(snapshot.generations),
        lag_row_count=len(snapshot.lags),
        window_count=len(windows),
        owner_count=current.owner_count,
        generation_count=current.generation_count,
        genealogy_edge_count=current.genealogy_edge_count,
        pair_count=current.pair_count,
        resolved_pair_count=current.resolved_pair_count,
        unresolved_pair_count=current.unresolved_pair_count,
        domain_available_count=current.domain_available_count,
        coverage=current.coverage,
        evidence_coverage=current.evidence_coverage,
        domain_coverage=current.domain_coverage,
        generation_coverage=current.generation_coverage,
        truncated=(
            current.truncated
            or current.coverage == "partial"
            or current.domain_coverage == "partial"
            or current.generation_coverage == "partial"
        ),
    )


def decode_social_mobility_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> SocialMobilitySnapshot:
    """Strictly decode one canonical social-mobility snapshot artifact."""

    if type(payload) is not bytes or len(payload) > MAX_SOCIAL_MOBILITY_SNAPSHOT_BYTES:
        raise ValueError("social_mobility_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("social_mobility_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "domains",
            "generations",
            "lags",
            "coverage",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != SOCIAL_MOBILITY_SNAPSHOT_VERSION:
        raise ValueError("social_mobility_snapshot_version")
    if top["policy_version"] != SOCIAL_MOBILITY_POLICY_VERSION:
        raise ValueError("social_mobility_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("social_mobility_snapshot_run_mismatch")
    try:
        snapshot = SocialMobilitySnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=SocialMobilitySummaryRecord(**top["summary"]),
            domains=tuple(SocialMobilityDomainRecord(**row) for row in top["domains"]),
            generations=tuple(
                SocialMobilityGenerationRecord(**row) for row in top["generations"]
            ),
            lags=tuple(SocialMobilityLagRecord(**row) for row in top["lags"]),
            coverage=tuple(
                SocialMobilityCoverageRecord(**row) for row in top["coverage"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("social_mobility_snapshot_corrupt") from exc
    if snapshot.digest != social_mobility_digest(snapshot):
        raise ValueError("social_mobility_snapshot_digest_mismatch")
    if snapshot.publication_id != compute_social_mobility_publication_id(
        snapshot.digest
    ):
        raise ValueError("social_mobility_snapshot_publication_mismatch")
    expected = _summary(snapshot)
    declared = snapshot.summary
    for name in (
        "domain_row_count",
        "generation_row_count",
        "lag_row_count",
        "window_count",
        "truncated",
    ):
        if getattr(declared, name) != getattr(expected, name):
            raise ValueError("social_mobility_snapshot_summary_mismatch")
    if encode_social_mobility_snapshot(snapshot) != payload:
        raise ValueError("social_mobility_snapshot_noncanonical")
    return snapshot
