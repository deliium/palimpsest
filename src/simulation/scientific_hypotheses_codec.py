"""Canonical encoding, digest, and strict decoding for hypothesis snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.scientific_hypotheses_models import (
    MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES,
    SCIENTIFIC_HYPOTHESES_POLICY_VERSION,
    SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX,
    SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION,
    ScientificHypothesesSnapshot,
    ScientificHypothesisCoverageRecord,
    ScientificHypothesisEvidenceRecord,
    ScientificHypothesisRecord,
    ScientificHypothesisRevisionRecord,
    ScientificHypothesisSourceRecord,
    ScientificHypothesisSummaryRecord,
    ScientificHypothesisTestRecord,
)

__all__ = [
    "canonical_scientific_hypotheses_json",
    "decode_scientific_hypotheses_snapshot",
    "encode_scientific_hypotheses_snapshot",
    "finalize_scientific_hypotheses_snapshot",
    "scientific_hypotheses_digest",
]

_TOP_KEYS = {
    "snapshot_version",
    "policy_version",
    "run_id",
    "generated_from_tick",
    "summary",
    "hypotheses",
    "evidence",
    "tests",
    "revisions",
    "sources",
    "coverage",
    "internal_digest",
    "publication_id",
}


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
        payload[name] = (
            [list(item) if isinstance(item, tuple) else item for item in value]
            if isinstance(value, tuple)
            else value
        )
    return payload


def _payload(
    snapshot: ScientificHypothesesSnapshot,
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
        "hypotheses": [_row_payload(row) for row in snapshot.hypotheses],
        "evidence": [_row_payload(row) for row in snapshot.evidence],
        "tests": [_row_payload(row) for row in snapshot.tests],
        "revisions": [_row_payload(row) for row in snapshot.revisions],
        "sources": [_row_payload(row) for row in snapshot.sources],
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


def canonical_scientific_hypotheses_json(
    snapshot: ScientificHypothesesSnapshot,
) -> bytes:
    """Return canonical bytes with the snapshot's declared digest fields."""

    if type(snapshot) is not ScientificHypothesesSnapshot:
        raise ValueError("scientific_hypotheses_snapshot_invalid")
    return _canonical_bytes(
        _payload(
            snapshot,
            internal_digest=snapshot.internal_digest,
            publication_id=snapshot.publication_id,
        )
    )


def scientific_hypotheses_digest(snapshot: ScientificHypothesesSnapshot) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not ScientificHypothesesSnapshot:
        raise ValueError("scientific_hypotheses_snapshot_invalid")
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
        raise ValueError("scientific_hypotheses_snapshot_invalid")
    return (
        f"{SCIENTIFIC_HYPOTHESES_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:16]}"
    )


def finalize_scientific_hypotheses_snapshot(
    snapshot: ScientificHypothesesSnapshot,
) -> ScientificHypothesesSnapshot:
    """Assign the canonical digest and publication id."""

    if type(snapshot) is not ScientificHypothesesSnapshot:
        raise ValueError("scientific_hypotheses_snapshot_invalid")
    blank = replace(snapshot, internal_digest="", publication_id="")
    digest = scientific_hypotheses_digest(blank)
    return replace(
        blank,
        internal_digest=digest,
        publication_id=_publication_id(digest),
    )


def encode_scientific_hypotheses_snapshot(
    snapshot: ScientificHypothesesSnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically and enforce the size cap."""

    if type(snapshot) is not ScientificHypothesesSnapshot:
        raise ValueError("scientific_hypotheses_snapshot_invalid")
    if not snapshot.internal_digest or not snapshot.publication_id:
        snapshot = finalize_scientific_hypotheses_snapshot(snapshot)
    data = canonical_scientific_hypotheses_json(snapshot)
    if len(data) > MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES:
        raise ValueError("scientific_hypotheses_snapshot_oversize")
    return data


def decode_scientific_hypotheses_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> ScientificHypothesesSnapshot:
    """Strictly decode one canonical scientific-hypothesis snapshot."""

    if (
        type(payload) is not bytes
        or len(payload) > MAX_SCIENTIFIC_HYPOTHESES_SNAPSHOT_BYTES
    ):
        raise ValueError("scientific_hypotheses_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("scientific_hypotheses_snapshot_corrupt") from exc
    if type(parsed) is not dict or set(parsed) != _TOP_KEYS:
        raise ValueError("scientific_hypotheses_snapshot_keys")
    if parsed["snapshot_version"] != SCIENTIFIC_HYPOTHESES_SNAPSHOT_VERSION:
        raise ValueError("scientific_hypotheses_snapshot_version")
    if parsed["policy_version"] != SCIENTIFIC_HYPOTHESES_POLICY_VERSION:
        raise ValueError("scientific_hypotheses_snapshot_version")
    if run_id is not None and parsed["run_id"] != run_id:
        raise ValueError("scientific_hypotheses_snapshot_run_mismatch")
    try:
        snapshot = ScientificHypothesesSnapshot(
            snapshot_version=parsed["snapshot_version"],
            policy_version=parsed["policy_version"],
            run_id=parsed["run_id"],
            generated_from_tick=parsed["generated_from_tick"],
            summary=ScientificHypothesisSummaryRecord(**parsed["summary"]),
            hypotheses=tuple(
                ScientificHypothesisRecord(
                    **{
                        **row,
                        "condition_pairs": tuple(
                            tuple(pair) for pair in row["condition_pairs"]
                        ),
                    }
                )
                for row in parsed["hypotheses"]
            ),
            evidence=tuple(
                ScientificHypothesisEvidenceRecord(**row)
                for row in parsed["evidence"]
            ),
            tests=tuple(
                ScientificHypothesisTestRecord(**row) for row in parsed["tests"]
            ),
            revisions=tuple(
                ScientificHypothesisRevisionRecord(
                    **{
                        **row,
                        "condition_pairs": tuple(
                            tuple(pair) for pair in row["condition_pairs"]
                        ),
                    }
                )
                for row in parsed["revisions"]
            ),
            sources=tuple(
                ScientificHypothesisSourceRecord(**row) for row in parsed["sources"]
            ),
            coverage=tuple(
                ScientificHypothesisCoverageRecord(**row)
                for row in parsed["coverage"]
            ),
            internal_digest=parsed["internal_digest"],
            publication_id=parsed["publication_id"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("scientific_hypotheses_snapshot_corrupt") from exc
    blank = replace(snapshot, internal_digest="", publication_id="")
    if snapshot.internal_digest != scientific_hypotheses_digest(blank):
        raise ValueError("scientific_hypotheses_snapshot_digest_mismatch")
    if encode_scientific_hypotheses_snapshot(snapshot) != payload:
        raise ValueError("scientific_hypotheses_snapshot_noncanonical")
    return snapshot
