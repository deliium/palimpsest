"""Canonical encoding, digest, and strict decoding for credit snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.credit_relationships_models import (
    CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES,
    CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX,
    CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY,
    CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    CreditAlignmentRecord,
    CreditClaimRecord,
    CreditCounterpartyRecord,
    CreditDistributionRecord,
    CreditPerformanceRecord,
    CreditRelationshipRecord,
    CreditRelationshipsSnapshot,
    CreditSummaryRecord,
)

__all__ = [
    "credit_relationships_artifact_digest",
    "decode_credit_relationships_snapshot",
    "encode_credit_relationships_snapshot",
    "finalize_credit_relationships_snapshot",
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
        if hasattr(value, "value") and not isinstance(value, tuple):
            payload[name] = value.value
        elif isinstance(value, tuple):
            payload[name] = list(value)
        else:
            payload[name] = value
    return payload


def _payload(
    snapshot: CreditRelationshipsSnapshot,
    *,
    digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _row_payload(snapshot.summary),
        "relationships": [_row_payload(row) for row in snapshot.relationships],
        "claims": [_row_payload(row) for row in snapshot.claims],
        "performances": [_row_payload(row) for row in snapshot.performances],
        "distributions": [_row_payload(row) for row in snapshot.distributions],
        "counterparties": [_row_payload(row) for row in snapshot.counterparties],
        "alignments": [_row_payload(row) for row in snapshot.alignments],
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


def credit_relationships_artifact_digest(
    snapshot: CreditRelationshipsSnapshot,
) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not CreditRelationshipsSnapshot:
        raise ValueError("credit_relationships_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
        ).hexdigest()
    )


def finalize_credit_relationships_snapshot(
    snapshot: CreditRelationshipsSnapshot,
) -> CreditRelationshipsSnapshot:
    """Assign the canonical digest and publication id."""

    digest = credit_relationships_artifact_digest(snapshot)
    publication_id = (
        f"{CREDIT_RELATIONSHIPS_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:16]}"
    )
    return replace(snapshot, digest=digest, publication_id=publication_id)


def encode_credit_relationships_snapshot(
    snapshot: CreditRelationshipsSnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically."""

    if type(snapshot) is not CreditRelationshipsSnapshot:
        raise ValueError("credit_relationships_snapshot_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_credit_relationships_snapshot(snapshot)
    data = _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    )
    if len(data) > CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES:
        raise ValueError("credit_relationships_snapshot_oversize")
    return data


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("credit_relationships_snapshot_keys")
    return mapping


def _row_kwargs(row: object) -> dict[str, Any]:
    if type(row) is not dict:
        raise ValueError("credit_relationships_snapshot_corrupt")
    return dict(row)


def decode_credit_relationships_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> CreditRelationshipsSnapshot:
    """Strictly decode one canonical credit snapshot artifact."""

    if (
        type(payload) is not bytes
        or len(payload) > CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES
    ):
        raise ValueError("credit_relationships_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("credit_relationships_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "relationships",
            "claims",
            "performances",
            "distributions",
            "counterparties",
            "alignments",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION:
        raise ValueError("credit_relationships_snapshot_version")
    if top["policy_version"] != CREDIT_RELATIONSHIPS_SNAPSHOT_POLICY:
        raise ValueError("credit_relationships_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("credit_relationships_snapshot_run_mismatch")
    try:
        snapshot = CreditRelationshipsSnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=CreditSummaryRecord(**_row_kwargs(top["summary"])),
            relationships=tuple(
                CreditRelationshipRecord(**_row_kwargs(row))
                for row in top["relationships"]
            ),
            claims=tuple(
                CreditClaimRecord(**_row_kwargs(row)) for row in top["claims"]
            ),
            performances=tuple(
                CreditPerformanceRecord(**_row_kwargs(row))
                for row in top["performances"]
            ),
            distributions=tuple(
                CreditDistributionRecord(
                    **{
                        **_row_kwargs(row),
                        "bin_shares_milli": tuple(
                            _row_kwargs(row)["bin_shares_milli"]
                        ),
                    }
                )
                for row in top["distributions"]
            ),
            counterparties=tuple(
                CreditCounterpartyRecord(**_row_kwargs(row))
                for row in top["counterparties"]
            ),
            alignments=tuple(
                CreditAlignmentRecord(**_row_kwargs(row))
                for row in top["alignments"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("credit_relationships_snapshot_corrupt") from exc
    expected_digest = credit_relationships_artifact_digest(snapshot)
    if snapshot.digest != expected_digest:
        raise ValueError("credit_relationships_snapshot_digest_mismatch")
    if _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    ) != payload:
        raise ValueError("credit_relationships_snapshot_noncanonical")
    return snapshot
