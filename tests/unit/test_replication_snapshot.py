# mypy: ignore-errors
"""V4-28 canonical replication snapshots."""

from __future__ import annotations

import pytest

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import ReplicationFacts
from experiments.replication_publication import compose_replication_snapshot
from simulation.replication_codec import (
    decode_replication_snapshot,
    encode_replication_snapshot,
)
from simulation.replication_models import (
    SNAPSHOT_KEYS,
    ReplicationSnapshotError,
)
from simulation.replication_paging import page_replication_rows
from simulation.replication_ports import (
    ReplicationPublicationError,
    ReplicationPublicationOptions,
)

pytestmark = pytest.mark.unit


def _snapshot():
    analysis = harvest_replication_analysis(ReplicationFacts())
    return compose_replication_snapshot(
        analysis, run_id="run-1", generated_from_tick=0
    )


def test_snapshot_round_trips_and_has_exact_top_keys() -> None:
    snapshot = _snapshot()
    material = encode_replication_snapshot(snapshot)
    assert material.endswith(b"\n") and not material.endswith(b"\n\n")
    decoded = decode_replication_snapshot(material)
    assert decoded == snapshot
    assert set(decode_replication_snapshot(material).summary) == {
        "design_count",
        "attempt_count",
        "execution_count",
        "report_count",
        "comparison_count",
        "interpretation_count",
        "collaboration_count",
        "participant_count",
        "first_tick",
        "last_tick",
        "coverage",
        "availability",
        "reason_codes",
    }
    assert len(SNAPSHOT_KEYS) == 14


def test_tampering_and_noncanonical_bytes_fail_closed() -> None:
    material = encode_replication_snapshot(_snapshot())
    tampered = material.replace(b'"design_count":0', b'"design_count":1', 1)
    with pytest.raises(ReplicationSnapshotError):
        decode_replication_snapshot(tampered)
    with pytest.raises(ReplicationSnapshotError):
        decode_replication_snapshot(material.rstrip(b"\n"))


def test_paging_is_snapshot_bound_and_signed() -> None:
    rows = tuple({"row_token": f"rrow-{index:032d}"} for index in range(5))
    first = page_replication_rows(
        rows,
        run_id="run-1",
        publication_id="srep-abc",
        query_fingerprint="q",
        limit=2,
        cursor=None,
        cursor_key=b"k" * 32,
    )
    assert len(first.rows) == 2
    assert first.next_cursor is not None
    second = page_replication_rows(
        rows,
        run_id="run-1",
        publication_id="srep-abc",
        query_fingerprint="q",
        limit=2,
        cursor=first.next_cursor,
        cursor_key=b"k" * 32,
    )
    assert second.rows[0]["row_token"] != first.rows[0]["row_token"]
    with pytest.raises(ReplicationPublicationError):
        page_replication_rows(
            rows,
            run_id="run-2",
            publication_id="srep-abc",
            query_fingerprint="q",
            limit=2,
            cursor=first.next_cursor,
            cursor_key=b"k" * 32,
        )
    with pytest.raises(ReplicationPublicationError):
        page_replication_rows(
            rows,
            run_id="run-1",
            publication_id="srep-abc",
            query_fingerprint="q",
            limit=2,
            cursor=first.next_cursor,
            cursor_key=b"wrong" * 8,
        )


def test_store_publishes_immutably_and_reads_latest(tmp_path) -> None:
    from persistence.replication_filesystem import replication_store_publisher

    store = replication_store_publisher(
        tmp_path,
        options=ReplicationPublicationOptions(
            enabled=True, max_publications=2, max_bytes=1_000_000
        ),
    )
    snapshot = _snapshot()
    receipt = store.publish(snapshot)
    assert receipt.stored is True
    again = store.publish(snapshot)
    assert again.stored is False
    assert store.read_snapshot("run-1").publication_id == snapshot.publication_id
