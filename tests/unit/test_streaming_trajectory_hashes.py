"""Byte-equivalent streamed trajectory hashes."""

from __future__ import annotations

import hashlib

import pytest

from simulation.runner import SimulationRunner
from simulation.runner_serialization import (
    _canonical_dumps,
    _encode_tick_receipt_for_hash,
    _iter_trajectory_hash_bytes,
    exact_trajectory_hash,
    replica_normalized_trajectory_hash,
)
from tests.unit.test_generational_population_runner import _v55_config


def _reference_exact(run_id: str, receipts) -> str:
    document = {
        "mode": "exact",
        "run_id": run_id,
        "ticks": [
            _encode_tick_receipt_for_hash(item, include_run_scoped_ids=True)
            for item in receipts
        ],
    }
    return hashlib.sha256(_canonical_dumps(document)).hexdigest()


def _reference_replica(receipts) -> str:
    document = {
        "mode": "replica",
        "ticks": [
            _encode_tick_receipt_for_hash(item, include_run_scoped_ids=False)
            for item in receipts
        ],
    }
    return hashlib.sha256(_canonical_dumps(document)).hexdigest()


@pytest.mark.asyncio
async def test_streamed_hashes_match_golden_documents() -> None:
    runner = await SimulationRunner.from_config(_v55_config())
    try:
        result = await runner.run()
    finally:
        await runner.aclose()
    receipts = result.finalized_tick_receipts
    assert receipts
    assert exact_trajectory_hash(
        run_id=result.run_id.value, tick_receipts=receipts
    ) == _reference_exact(result.run_id.value, receipts)
    assert replica_normalized_trajectory_hash(
        tick_receipts=receipts
    ) == _reference_replica(receipts)


def test_empty_and_unicode_run_id_are_byte_equivalent() -> None:
    assert exact_trajectory_hash(
        run_id="run-\u03bb", tick_receipts=()
    ) == _reference_exact("run-\u03bb", ())
    assert replica_normalized_trajectory_hash(
        tick_receipts=()
    ) == _reference_replica(())


def test_stream_yields_header_receipts_and_suffix() -> None:
    chunks = list(
        _iter_trajectory_hash_bytes(
            mode="exact",
            run_id="run-1",
            tick_receipts=(),
            include_run_scoped_ids=True,
        )
    )
    assert len(chunks) == 2
    assert b'"ticks":[' in chunks[0]
    assert chunks[1] == b"]}"
