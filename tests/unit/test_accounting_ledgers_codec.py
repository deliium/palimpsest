"""Canonical accounting snapshot codec tests."""

# mypy: ignore-errors

from __future__ import annotations

import json

import pytest

from simulation.accounting_ledgers_codec import (
    accounting_ledgers_artifact_digest,
    decode_accounting_ledgers_snapshot,
    encode_accounting_ledgers_snapshot,
    finalize_accounting_ledgers_snapshot,
)
from simulation.accounting_ledgers_models import (
    AccountingLedgersSnapshot,
    AccountingLedgersSummary,
    AccountingSnapshotEntry,
)


def _snapshot() -> AccountingLedgersSnapshot:
    entry = AccountingSnapshotEntry(
        entry_token="acce-0000000000000001",
        record_token="accrec-0000000000000001",
        entry_kind="exchange",
        direction="inflow",
        item_kind="food",
        quantity=2,
        assessment="consistent",
        confidence_milli=700,
        first_tick=1,
        last_tick=2,
        window_index=0,
    )
    return AccountingLedgersSnapshot(
        run_id="run-1",
        schema_version="accounting-ledgers-snapshot-v1",
        policy_version="accounting-ledgers.v1",
        summary=AccountingLedgersSummary(
            entry_count=1,
            record_count=0,
            condition_count=0,
            flow_count=0,
            counterparty_count=0,
            alignment_count=0,
            window_count=1,
            entry_coverage="complete",
            record_coverage="missing",
            alignment_coverage="missing",
            truncated=False,
        ),
        entries=(entry,),
    )


def test_canonical_round_trip_and_digest_stability() -> None:
    final = finalize_accounting_ledgers_snapshot(_snapshot())
    payload = encode_accounting_ledgers_snapshot(final)
    assert payload.endswith(b"\n")
    decoded = decode_accounting_ledgers_snapshot(payload, run_id="run-1")
    assert decoded == final
    assert encode_accounting_ledgers_snapshot(decoded) == payload
    assert accounting_ledgers_artifact_digest(final) == final.digest
    assert final.publication_id.startswith("acct-pub-")


def test_duplicate_keys_wrong_schema_and_digest_mismatch_rejected() -> None:
    final = finalize_accounting_ledgers_snapshot(_snapshot())
    payload = encode_accounting_ledgers_snapshot(final)
    duplicated = payload.replace(
        b'{"alignments":', b'{"alignments":[],"alignments":', 1
    )
    with pytest.raises(ValueError) as duplicate:
        decode_accounting_ledgers_snapshot(duplicated)
    assert "duplicate" in str(duplicate.value) or "corrupt" in str(duplicate.value)
    wrong = payload.replace(b"accounting-ledgers-snapshot-v1", b"other-version")
    with pytest.raises(ValueError) as schema:
        decode_accounting_ledgers_snapshot(wrong)
    assert "version" in str(schema.value)
    parsed = json.loads(payload)
    parsed["digest"] = "sha256:" + "0" * 64
    tampered = (
        json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with pytest.raises(ValueError) as digest:
        decode_accounting_ledgers_snapshot(tampered)
    assert "digest" in str(digest.value)


def test_noncanonical_and_summary_mismatch_rejected() -> None:
    final = finalize_accounting_ledgers_snapshot(_snapshot())
    payload = encode_accounting_ledgers_snapshot(final)
    parsed = json.loads(payload)
    parsed["summary"]["entry_count"] = 2
    parsed["digest"] = accounting_ledgers_artifact_digest(
        AccountingLedgersSnapshot(
            **{
                **{
                    name: getattr(final, name)
                    for name in final.__dataclass_fields__
                    if name not in {"summary", "digest", "publication_id"}
                },
                "summary": AccountingLedgersSummary(
                    **{**parsed["summary"], "entry_count": 2}
                ),
            }
        )
    )
    tampered = (
        json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with pytest.raises(ValueError) as mismatch:
        decode_accounting_ledgers_snapshot(tampered)
    assert "summary" in str(mismatch.value) or "noncanonical" in str(mismatch.value)
    with pytest.raises(ValueError):
        decode_accounting_ledgers_snapshot(payload + b" ")


def test_oversize_rejected() -> None:
    with pytest.raises(ValueError):
        decode_accounting_ledgers_snapshot(b"x" * 8_388_609)
