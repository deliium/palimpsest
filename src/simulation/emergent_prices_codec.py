"""Canonical encoding, digest, and strict decoding for price snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.emergent_prices_models import (
    EMERGENT_PRICES_ARTIFACT_MAX_BYTES,
    EMERGENT_PRICES_PUBLICATION_PREFIX,
    EMERGENT_PRICES_SNAPSHOT_POLICY,
    EMERGENT_PRICES_SNAPSHOT_VERSION,
    EmergentPricesSnapshot,
    EmergentPricesSummaryRecord,
    PriceDistributionRecord,
    PriceExpectationRecord,
    PriceMarketRecord,
    PriceQuoteRecord,
    PriceRelationRecord,
    PriceUnitRecord,
)

__all__ = [
    "decode_emergent_prices_snapshot",
    "emergent_prices_artifact_digest",
    "encode_emergent_prices_snapshot",
    "finalize_emergent_prices_snapshot",
]

Row = (
    PriceUnitRecord
    | PriceExpectationRecord
    | PriceQuoteRecord
    | PriceDistributionRecord
    | PriceMarketRecord
    | PriceRelationRecord
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
    snapshot: EmergentPricesSnapshot, *, digest: str, publication_id: str
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _row_payload(snapshot.summary),
        "units": [_row_payload(row) for row in snapshot.units],
        "expectations": [_row_payload(row) for row in snapshot.expectations],
        "quotes": [_row_payload(row) for row in snapshot.quotes],
        "distributions": [_row_payload(row) for row in snapshot.distributions],
        "markets": [_row_payload(row) for row in snapshot.markets],
        "relations": [_row_payload(row) for row in snapshot.relations],
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


def emergent_prices_artifact_digest(snapshot: EmergentPricesSnapshot) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not EmergentPricesSnapshot:
        raise ValueError("emergent_prices_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
        ).hexdigest()
    )


def finalize_emergent_prices_snapshot(
    snapshot: EmergentPricesSnapshot,
) -> EmergentPricesSnapshot:
    """Assign the canonical digest and publication id."""

    digest = emergent_prices_artifact_digest(snapshot)
    publication_id = (
        f"{EMERGENT_PRICES_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:32]}"
    )
    return replace(snapshot, digest=digest, publication_id=publication_id)


def encode_emergent_prices_snapshot(snapshot: EmergentPricesSnapshot) -> bytes:
    """Encode one finalized snapshot canonically."""

    if type(snapshot) is not EmergentPricesSnapshot:
        raise ValueError("emergent_prices_snapshot_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_emergent_prices_snapshot(snapshot)
    return _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    )


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("emergent_prices_snapshot_keys")
    return mapping


def _row_kwargs(row: object) -> dict[str, Any]:
    if type(row) is not dict:
        raise ValueError("emergent_prices_snapshot_corrupt")
    return dict(row)


def decode_emergent_prices_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> EmergentPricesSnapshot:
    """Strictly decode one canonical snapshot artifact."""

    if type(payload) is not bytes or len(payload) > EMERGENT_PRICES_ARTIFACT_MAX_BYTES:
        raise ValueError("emergent_prices_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("emergent_prices_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "units",
            "expectations",
            "quotes",
            "distributions",
            "markets",
            "relations",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != EMERGENT_PRICES_SNAPSHOT_VERSION:
        raise ValueError("emergent_prices_snapshot_version")
    if top["policy_version"] != EMERGENT_PRICES_SNAPSHOT_POLICY:
        raise ValueError("emergent_prices_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("emergent_prices_snapshot_run_mismatch")
    try:
        snapshot = EmergentPricesSnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=EmergentPricesSummaryRecord(**top["summary"]),
            units=tuple(
                PriceUnitRecord(**_row_kwargs(row)) for row in top["units"]
            ),
            expectations=tuple(
                PriceExpectationRecord(**_row_kwargs(row))
                for row in top["expectations"]
            ),
            quotes=tuple(
                PriceQuoteRecord(**_row_kwargs(row)) for row in top["quotes"]
            ),
            distributions=tuple(
                PriceDistributionRecord(**_row_kwargs(row))
                for row in top["distributions"]
            ),
            markets=tuple(
                PriceMarketRecord(**_row_kwargs(row)) for row in top["markets"]
            ),
            relations=tuple(
                PriceRelationRecord(**_row_kwargs(row))
                for row in top["relations"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("emergent_prices_snapshot_corrupt") from exc
    expected_digest = emergent_prices_artifact_digest(snapshot)
    if snapshot.digest != expected_digest:
        raise ValueError("emergent_prices_snapshot_digest_mismatch")
    if _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    ) != payload:
        raise ValueError("emergent_prices_snapshot_noncanonical")
    return snapshot
