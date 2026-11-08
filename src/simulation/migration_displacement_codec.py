# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap,redundant-cast,operator,misc,return-value,valid-type,override"
"""Canonical codec for ``migration-displacement-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, fields
from typing import Final

from simulation.migration_displacement_models import (
    MIGRATION_DISPLACEMENT_MAX_BYTES,
    MIGRATION_DISPLACEMENT_PUBLICATION_PREFIX,
    MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY,
    MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
    MigrationAlignmentSnapshotRow,
    MigrationCauseSnapshotRow,
    MigrationClusterSnapshotRow,
    MigrationDisplacementCandidateRow,
    MigrationDisplacementSnapshot,
    MigrationDisplacementSummaryRow,
    MigrationLineageSnapshotRow,
    MigrationMetricProvenanceRow,
    MigrationMovementRow,
    MigrationOutcomeSnapshotRow,
    MigrationRouteSnapshotRow,
    MigrationWaveSnapshotRow,
)

__all__ = [
    "MIGRATION_DISPLACEMENT_ROW_MAP",
    "MIGRATION_DISPLACEMENT_TOP_LEVEL_KEYS",
    "canonical_migration_displacement_json",
    "canonical_migration_displacement_payload",
    "decode_migration_displacement_snapshot",
    "encode_migration_displacement_snapshot",
    "finalize_migration_displacement_snapshot",
    "migration_displacement_publication_id",
    "migration_displacement_snapshot_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.migration_displacement.codec"
)

MIGRATION_DISPLACEMENT_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "summary",
        "candidates",
        "movements",
        "causes",
        "routes",
        "clusters",
        "waves",
        "outcomes",
        "lineage",
        "alignment",
        "metric_provenance",
        "digest",
        "publication_id",
        "schema_version",
        "policy_version",
    }
)
MIGRATION_DISPLACEMENT_ROW_MAP: Final[dict[str, type]] = {
    "candidates": MigrationDisplacementCandidateRow,
    "movements": MigrationMovementRow,
    "causes": MigrationCauseSnapshotRow,
    "routes": MigrationRouteSnapshotRow,
    "clusters": MigrationClusterSnapshotRow,
    "waves": MigrationWaveSnapshotRow,
    "outcomes": MigrationOutcomeSnapshotRow,
    "lineage": MigrationLineageSnapshotRow,
    "alignment": MigrationAlignmentSnapshotRow,
    "metric_provenance": MigrationMetricProvenanceRow,
}
_PUBLICATION_HEX_CHARS: Final[int] = 32


def canonical_migration_displacement_payload(
    snapshot: MigrationDisplacementSnapshot,
) -> dict[str, object]:
    """Stable payload with rows in their retained order."""
    if type(snapshot) is not MigrationDisplacementSnapshot:
        raise TypeError("snapshot must be MigrationDisplacementSnapshot")
    return asdict(snapshot)


def canonical_migration_displacement_json(
    snapshot: MigrationDisplacementSnapshot,
) -> str:
    """Canonical compact JSON. Trailing newline belongs only on the byte payload."""
    return json.dumps(
        canonical_migration_displacement_payload(snapshot),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def migration_displacement_snapshot_digest(
    snapshot: MigrationDisplacementSnapshot,
) -> str:
    """SHA-256 over the payload excluding publication fields."""
    payload = canonical_migration_displacement_payload(snapshot)
    payload["digest"] = ""
    payload["publication_id"] = ""
    summary = dict(payload["summary"])  # type: ignore[arg-type]
    summary["digest"] = ""
    summary["publication_id"] = ""
    payload["summary"] = summary
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def migration_displacement_publication_id(digest: str) -> str:
    """Publication ``md-pub-`` id from the first 32 hex characters of the digest."""
    if type(digest) is not str or len(digest) != 64:
        raise ValueError("migration_displacement_snapshot: invalid_digest")
    if any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("migration_displacement_snapshot: invalid_digest")
    return (
        f"{MIGRATION_DISPLACEMENT_PUBLICATION_PREFIX}"
        f"{digest[:_PUBLICATION_HEX_CHARS]}"
    )


def finalize_migration_displacement_snapshot(
    snapshot: MigrationDisplacementSnapshot,
) -> MigrationDisplacementSnapshot:
    """Install digest and publication id, then reject oversized payloads."""
    digest = migration_displacement_snapshot_digest(snapshot)
    publication_id = migration_displacement_publication_id(digest)
    summary = MigrationDisplacementSummaryRow(
        run_id=snapshot.summary.run_id,
        publication_id=publication_id,
        digest=digest,
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=snapshot.summary.policy_version,
        candidate_count=snapshot.summary.candidate_count,
        wave_count=snapshot.summary.wave_count,
        cluster_count=snapshot.summary.cluster_count,
        outcome_count=snapshot.summary.outcome_count,
        movement_count=snapshot.summary.movement_count,
        cause_count=snapshot.summary.cause_count,
        displacement_like_count=snapshot.summary.displacement_like_count,
        mixed_count=snapshot.summary.mixed_count,
        not_displacement_like_count=snapshot.summary.not_displacement_like_count,
        unknown_count=snapshot.summary.unknown_count,
        integration_settled_count=snapshot.summary.integration_settled_count,
        integration_transient_count=snapshot.summary.integration_transient_count,
        integration_returned_count=snapshot.summary.integration_returned_count,
        integration_onward_count=snapshot.summary.integration_onward_count,
        integration_unknown_count=snapshot.summary.integration_unknown_count,
        coverage=snapshot.summary.coverage,
        unresolved_anchor_count=snapshot.summary.unresolved_anchor_count,
        truncated=snapshot.summary.truncated,
    )
    finalized = MigrationDisplacementSnapshot(
        summary=summary,
        candidates=snapshot.candidates,
        movements=snapshot.movements,
        causes=snapshot.causes,
        routes=snapshot.routes,
        clusters=snapshot.clusters,
        waves=snapshot.waves,
        outcomes=snapshot.outcomes,
        lineage=snapshot.lineage,
        alignment=snapshot.alignment,
        metric_provenance=snapshot.metric_provenance,
        digest=digest,
        publication_id=publication_id,
        schema_version=MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION,
        policy_version=snapshot.policy_version,
    )
    encode_migration_displacement_snapshot(finalized)
    row_total = sum(
        len(getattr(finalized, name)) for name in MIGRATION_DISPLACEMENT_ROW_MAP
    )
    _LOG.debug(
        "migration_displacement_snapshot_finalized rows=%s digest_prefix=%s",
        row_total,
        digest[:8],
    )
    return finalized


def encode_migration_displacement_snapshot(
    snapshot: MigrationDisplacementSnapshot,
) -> bytes:
    """Encode to canonical UTF-8 JSON with exactly one trailing newline."""
    payload = f"{canonical_migration_displacement_json(snapshot)}\n".encode()
    if len(payload) > MIGRATION_DISPLACEMENT_MAX_BYTES:
        raise ValueError("migration_displacement_size_limit")
    return payload


def decode_migration_displacement_snapshot(
    payload: bytes | str,
) -> MigrationDisplacementSnapshot:
    """Decode and revalidate a canonical snapshot payload."""
    if isinstance(payload, str):
        raw = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        raw = payload
    else:
        raise TypeError("payload must be bytes or str")
    if len(raw) > MIGRATION_DISPLACEMENT_MAX_BYTES:
        raise ValueError("migration_displacement_size_limit")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("migration_displacement_snapshot: invalid_json") from exc
    if type(data) is not dict or set(data) != MIGRATION_DISPLACEMENT_TOP_LEVEL_KEYS:
        raise ValueError("migration_displacement_snapshot: unknown_key")
    if data["schema_version"] != MIGRATION_DISPLACEMENT_SNAPSHOT_VERSION:
        raise ValueError("migration_displacement_snapshot: unsupported_schema")
    if data["policy_version"] != MIGRATION_DISPLACEMENT_SNAPSHOT_POLICY:
        raise ValueError("migration_displacement_snapshot: unsupported_policy")
    summary_payload = data["summary"]
    if type(summary_payload) is not dict:
        raise ValueError("migration_displacement_snapshot: unknown_key")
    allowed_summary = {item.name for item in fields(MigrationDisplacementSummaryRow)}
    if set(summary_payload) != allowed_summary:
        raise ValueError("migration_displacement_snapshot: unknown_key")
    rows: dict[str, tuple[object, ...]] = {}
    for name, row_type in MIGRATION_DISPLACEMENT_ROW_MAP.items():
        values = data[name]
        if type(values) is not list:
            raise ValueError("migration_displacement_snapshot: unknown_key")
        allowed = {item.name for item in row_type.__dataclass_fields__.values()}
        rebuilt: list[object] = []
        for value in values:
            if type(value) is not dict or set(value) != allowed:
                raise ValueError("migration_displacement_snapshot: unknown_key")
            payload = dict(value)
            for key, item in tuple(payload.items()):
                if type(item) is list:
                    if key in {"cause_support_counts", "basis_counts"}:
                        payload[key] = tuple(tuple(entry) for entry in item)
                    else:
                        payload[key] = tuple(item)
            rebuilt.append(row_type(**payload))
        rows[name] = tuple(rebuilt)
    snapshot = MigrationDisplacementSnapshot(
        summary=MigrationDisplacementSummaryRow(**summary_payload),
        digest=data["digest"],
        publication_id=data["publication_id"],
        schema_version=data["schema_version"],
        policy_version=data["policy_version"],
        **rows,
    )
    if migration_displacement_snapshot_digest(snapshot) != snapshot.digest:
        raise ValueError("migration_displacement_snapshot: invalid_digest")
    if (
        migration_displacement_publication_id(snapshot.digest)
        != snapshot.publication_id
    ):
        raise ValueError("migration_displacement_snapshot: invalid_publication")
    return snapshot
