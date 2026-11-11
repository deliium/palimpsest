"""Canonical codec for ``market-institutions-snapshot-v1`` artifacts."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from typing import Any, Final

from simulation.market_institutions_models import (
    MARKET_INSTITUTIONS_ARTIFACT_MAX_BYTES,
    MARKET_INSTITUTIONS_PUBLICATION_PREFIX,
    MARKET_INSTITUTIONS_SNAPSHOT_POLICY,
    MARKET_INSTITUTIONS_SNAPSHOT_VERSION,
    MarketCandidateRecord,
    MarketExpectationRecord,
    MarketGatheringRecord,
    MarketInstitutionsSnapshot,
    MarketInstitutionsSummaryRecord,
    MarketLineageRecord,
    MarketRecordAnchorRecord,
    MarketRoleRecord,
    MarketVenueRecord,
)

__all__ = [
    "decode_market_institutions_snapshot",
    "encode_market_institutions_snapshot",
    "finalize_market_institutions_snapshot",
    "market_institutions_artifact_digest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "simulation.market_institutions_codec"
)


class _DuplicateKeyError(ValueError):
    pass


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _summary_payload(summary: MarketInstitutionsSummaryRecord) -> dict[str, Any]:
    return {
        "window_tick": summary.window_tick,
        "venue_count": summary.venue_count,
        "gathering_count": summary.gathering_count,
        "market_like_venue_count": summary.market_like_venue_count,
        "recurring_venue_count": summary.recurring_venue_count,
        "expected_venue_count": summary.expected_venue_count,
        "market_count": summary.market_count,
        "expectation_row_count": summary.expectation_row_count,
        "role_row_count": summary.role_row_count,
        "record_anchor_count": summary.record_anchor_count,
        "emerged_count": summary.emerged_count,
        "continued_count": summary.continued_count,
        "transformed_count": summary.transformed_count,
        "split_count": summary.split_count,
        "merge_count": summary.merge_count,
        "dissolved_count": summary.dissolved_count,
        "sustained_market_count": summary.sustained_market_count,
        "lineage_edge_count": summary.lineage_edge_count,
        "coverage": str(summary.coverage),
        "truncated": summary.truncated,
    }


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
    snapshot: MarketInstitutionsSnapshot,
    *,
    digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _summary_payload(snapshot.summary),
        "venues": [_row_payload(row) for row in snapshot.venues],
        "gatherings": [_row_payload(row) for row in snapshot.gatherings],
        "expectations": [_row_payload(row) for row in snapshot.expectations],
        "roles": [_row_payload(row) for row in snapshot.roles],
        "records": [_row_payload(row) for row in snapshot.records],
        "markets": [_row_payload(row) for row in snapshot.markets],
        "lineage": [_row_payload(row) for row in snapshot.lineage],
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


def market_institutions_artifact_digest(
    snapshot: MarketInstitutionsSnapshot,
) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not MarketInstitutionsSnapshot:
        raise ValueError("market_institutions_artifact_invalid")
    return hashlib.sha256(
        _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
    ).hexdigest()


def finalize_market_institutions_snapshot(
    snapshot: MarketInstitutionsSnapshot,
) -> MarketInstitutionsSnapshot:
    """Assign the canonical digest and publication id."""

    digest = market_institutions_artifact_digest(snapshot)
    publication_id = (
        f"{MARKET_INSTITUTIONS_PUBLICATION_PREFIX}"
        f"{hashlib.sha256(f'market-institutions-pub|{snapshot.run_id}|{digest}'.encode()).hexdigest()[:32]}"
    )
    return replace(snapshot, digest=digest, publication_id=publication_id)


def encode_market_institutions_snapshot(
    snapshot: MarketInstitutionsSnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically."""

    if type(snapshot) is not MarketInstitutionsSnapshot:
        raise ValueError("market_institutions_artifact_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_market_institutions_snapshot(snapshot)
    payload = _payload(
        snapshot, digest=snapshot.digest, publication_id=snapshot.publication_id
    )
    return _canonical_bytes(payload)


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("market_institutions_artifact_keys")
    return mapping


def _row_kwargs(row: object) -> dict[str, Any]:
    if type(row) is not dict:
        raise ValueError("market_institutions_artifact_corrupt")
    return dict(row)


def decode_market_institutions_snapshot(
    payload: bytes,
    *,
    run_id: str | None = None,
) -> MarketInstitutionsSnapshot:
    """Strictly decode one canonical snapshot artifact."""

    if (
        type(payload) is not bytes
        or len(payload) > MARKET_INSTITUTIONS_ARTIFACT_MAX_BYTES
    ):
        raise ValueError("market_institutions_artifact_too_large")
    try:
        parsed = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_pairs
        )
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("market_institutions_artifact_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "venues",
            "gatherings",
            "expectations",
            "roles",
            "records",
            "markets",
            "lineage",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != MARKET_INSTITUTIONS_SNAPSHOT_VERSION:
        raise ValueError("market_institutions_artifact_version")
    if top["policy_version"] != MARKET_INSTITUTIONS_SNAPSHOT_POLICY:
        raise ValueError("market_institutions_artifact_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("market_institutions_artifact_run_mismatch")
    try:
        summary = MarketInstitutionsSummaryRecord(**top["summary"])
        snapshot = MarketInstitutionsSnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=summary,
            venues=tuple(
                MarketVenueRecord(**_row_kwargs(row)) for row in top["venues"]
            ),
            gatherings=tuple(
                MarketGatheringRecord(**_row_kwargs(row))
                for row in top["gatherings"]
            ),
            expectations=tuple(
                MarketExpectationRecord(**_row_kwargs(row))
                for row in top["expectations"]
            ),
            roles=tuple(
                MarketRoleRecord(**_row_kwargs(row)) for row in top["roles"]
            ),
            records=tuple(
                MarketRecordAnchorRecord(**_row_kwargs(row))
                for row in top["records"]
            ),
            markets=tuple(
                MarketCandidateRecord(**_row_kwargs(row))
                for row in top["markets"]
            ),
            lineage=tuple(
                MarketLineageRecord(**_row_kwargs(row))
                for row in top["lineage"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("market_institutions_artifact_corrupt") from exc
    expected_digest = market_institutions_artifact_digest(snapshot)
    if snapshot.digest != expected_digest:
        raise ValueError("market_institutions_artifact_digest_mismatch")
    if _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    ) != payload:
        raise ValueError("market_institutions_artifact_noncanonical")
    return snapshot
