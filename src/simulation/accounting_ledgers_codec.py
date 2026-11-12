"""Canonical encoding, digest, and strict decoding for accounting snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from simulation.accounting_ledgers_models import (
    ACCOUNTING_LEDGERS_ARTIFACT_MAX_BYTES,
    ACCOUNTING_LEDGERS_POLICY_VERSION,
    ACCOUNTING_LEDGERS_PUBLICATION_PREFIX,
    ACCOUNTING_LEDGERS_SNAPSHOT_VERSION,
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotAlignment,
    AccountingSnapshotCondition,
    AccountingSnapshotCounterparty,
    AccountingSnapshotEntry,
    AccountingSnapshotFlow,
    AccountingSnapshotRecord,
)

__all__ = [
    "accounting_ledgers_artifact_digest",
    "decode_accounting_ledgers_snapshot",
    "encode_accounting_ledgers_snapshot",
    "finalize_accounting_ledgers_snapshot",
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
        if isinstance(value, tuple):
            payload[name] = list(value)
        else:
            payload[name] = value
    return payload


def _payload(
    snapshot: AccountingLedgersSnapshot,
    *,
    digest: str,
    publication_id: str,
) -> dict[str, Any]:
    return {
        "run_id": snapshot.run_id,
        "schema_version": snapshot.schema_version,
        "policy_version": snapshot.policy_version,
        "summary": _row_payload(snapshot.summary),
        "entries": [_row_payload(row) for row in snapshot.entries],
        "records": [_row_payload(row) for row in snapshot.records],
        "conditions": [_row_payload(row) for row in snapshot.conditions],
        "flows": [_row_payload(row) for row in snapshot.flows],
        "counterparties": [
            _row_payload(row) for row in snapshot.counterparties
        ],
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


def accounting_ledgers_artifact_digest(
    snapshot: AccountingLedgersSnapshot,
) -> str:
    """Digest over the payload with blank digest and publication id."""

    if type(snapshot) is not AccountingLedgersSnapshot:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    return (
        "sha256:"
        + hashlib.sha256(
            _canonical_bytes(_payload(snapshot, digest="", publication_id=""))
        ).hexdigest()
    )


def finalize_accounting_ledgers_snapshot(
    snapshot: AccountingLedgersSnapshot,
) -> AccountingLedgersSnapshot:
    """Assign the canonical digest and publication id."""

    digest = accounting_ledgers_artifact_digest(snapshot)
    publication_id = (
        f"{ACCOUNTING_LEDGERS_PUBLICATION_PREFIX}"
        f"{digest.removeprefix('sha256:')[:16]}"
    )
    return replace(snapshot, digest=digest, publication_id=publication_id)


def encode_accounting_ledgers_snapshot(
    snapshot: AccountingLedgersSnapshot,
) -> bytes:
    """Encode one finalized snapshot canonically."""

    if type(snapshot) is not AccountingLedgersSnapshot:
        raise ValueError("accounting_ledgers_snapshot_invalid")
    if not snapshot.digest or not snapshot.publication_id:
        snapshot = finalize_accounting_ledgers_snapshot(snapshot)
    data = _canonical_bytes(
        _payload(
            snapshot,
            digest=snapshot.digest,
            publication_id=snapshot.publication_id,
        )
    )
    if len(data) > ACCOUNTING_LEDGERS_ARTIFACT_MAX_BYTES:
        raise ValueError("accounting_ledgers_snapshot_oversize")
    return data


def _require_keys(mapping: object, expected: set[str]) -> dict[str, Any]:
    if type(mapping) is not dict or set(mapping) != expected:
        raise ValueError("accounting_ledgers_snapshot_keys")
    return mapping


def _summary(snapshot: AccountingLedgersSnapshot) -> AccountingLedgersSummary:
    current = snapshot.summary
    return AccountingLedgersSummary(
        entry_count=len(snapshot.entries),
        record_count=len(snapshot.records),
        condition_count=len(snapshot.conditions),
        flow_count=len(snapshot.flows),
        counterparty_count=len(snapshot.counterparties),
        alignment_count=len(snapshot.alignments),
        window_count=len(
            {
                *(row.window_index for row in snapshot.entries),
                *(row.window_index for row in snapshot.records),
                *(row.window_index for row in snapshot.conditions),
                *(row.window_index for row in snapshot.flows),
                *(row.window_index for row in snapshot.counterparties),
                *(row.window_index for row in snapshot.alignments),
            }
        ),
        entry_coverage=current.entry_coverage,
        record_coverage=current.record_coverage,
        alignment_coverage=current.alignment_coverage,
        condition_coverage=current.condition_coverage,
        flow_coverage=current.flow_coverage,
        counterparty_coverage=current.counterparty_coverage,
        truncated=(
            current.entry_coverage == "partial"
            or current.record_coverage == "partial"
            or current.alignment_coverage == "partial"
            or current.condition_coverage == "partial"
            or current.flow_coverage == "partial"
            or current.counterparty_coverage == "partial"
        ),
    )


def decode_accounting_ledgers_snapshot(
    payload: bytes, *, run_id: str | None = None
) -> AccountingLedgersSnapshot:
    """Strictly decode one canonical accounting snapshot artifact."""

    if (
        type(payload) is not bytes
        or len(payload) > ACCOUNTING_LEDGERS_ARTIFACT_MAX_BYTES
    ):
        raise ValueError("accounting_ledgers_snapshot_oversize")
    try:
        parsed = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (_DuplicateKeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("accounting_ledgers_snapshot_corrupt") from exc
    top = _require_keys(
        parsed,
        {
            "run_id",
            "schema_version",
            "policy_version",
            "summary",
            "entries",
            "records",
            "conditions",
            "flows",
            "counterparties",
            "alignments",
            "digest",
            "publication_id",
        },
    )
    if top["schema_version"] != ACCOUNTING_LEDGERS_SNAPSHOT_VERSION:
        raise ValueError("accounting_ledgers_snapshot_version")
    if top["policy_version"] != ACCOUNTING_LEDGERS_POLICY_VERSION:
        raise ValueError("accounting_ledgers_snapshot_version")
    if run_id is not None and top["run_id"] != run_id:
        raise ValueError("accounting_ledgers_snapshot_run_mismatch")
    try:
        snapshot = AccountingLedgersSnapshot(
            run_id=top["run_id"],
            schema_version=top["schema_version"],
            policy_version=top["policy_version"],
            summary=AccountingLedgersSummary(**top["summary"]),
            entries=tuple(
                AccountingSnapshotEntry(**row) for row in top["entries"]
            ),
            records=tuple(
                AccountingSnapshotRecord(**row) for row in top["records"]
            ),
            conditions=tuple(
                AccountingSnapshotCondition(**row) for row in top["conditions"]
            ),
            flows=tuple(AccountingSnapshotFlow(**row) for row in top["flows"]),
            counterparties=tuple(
                AccountingSnapshotCounterparty(
                    **{**row, "kinds": tuple(row.get("kinds", ()))}
                )
                for row in top["counterparties"]
            ),
            alignments=tuple(
                AccountingSnapshotAlignment(**row) for row in top["alignments"]
            ),
            digest=top["digest"],
            publication_id=top["publication_id"],
        )
    except (TypeError, KeyError) as exc:
        raise ValueError("accounting_ledgers_snapshot_corrupt") from exc
    if snapshot.digest != accounting_ledgers_artifact_digest(snapshot):
        raise ValueError("accounting_ledgers_snapshot_digest_mismatch")
    expected = _summary(snapshot)
    declared = snapshot.summary
    for name in (
        "entry_count",
        "record_count",
        "condition_count",
        "flow_count",
        "counterparty_count",
        "alignment_count",
        "window_count",
        "truncated",
    ):
        if getattr(declared, name) != getattr(expected, name):
            raise ValueError("accounting_ledgers_snapshot_summary_mismatch")
    if encode_accounting_ledgers_snapshot(snapshot) != payload:
        raise ValueError("accounting_ledgers_snapshot_noncanonical")
    return snapshot
