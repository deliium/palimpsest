# mypy: ignore-errors
"""Atomic quota-bounded store tests for economic-inequality snapshots."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from persistence.economic_inequality_filesystem import (
    EconomicInequalityPublisherOptions,
    create_economic_inequality_publisher,
    create_economic_inequality_reader,
)
from simulation.economic_inequality_codec import (
    encode_economic_inequality_snapshot,
    finalize_economic_inequality_snapshot,
)
from simulation.economic_inequality_models import EconomicInequalitySnapshot
from tests.unit.test_economic_inequality_snapshot import _snapshot


def _publication(window: int) -> EconomicInequalitySnapshot:
    snapshot = _snapshot()
    return finalize_economic_inequality_snapshot(
        replace(
            snapshot,
            dimensions=tuple(
                replace(row, window_index=window, window_tick=window * 32)
                for row in snapshot.dimensions
            ),
            cohorts=tuple(
                replace(row, window_index=window) for row in snapshot.cohorts
            ),
            societies=tuple(
                replace(row, window_index=window) for row in snapshot.societies
            ),
        )
    )


def test_publish_and_read_round_trip(tmp_path: Path) -> None:
    snapshot = _publication(0)
    publisher = create_economic_inequality_publisher(tmp_path)
    receipt = publisher.publish(snapshot)
    assert receipt.stored is True
    reader = create_economic_inequality_reader(tmp_path)
    assert reader.read_snapshot("run-1") == snapshot


def test_identical_republish_is_idempotent(tmp_path: Path) -> None:
    snapshot = _publication(0)
    publisher = create_economic_inequality_publisher(tmp_path)
    assert publisher.publish(snapshot).stored is True
    assert publisher.publish(snapshot).stored is False


def test_cumulative_byte_quota_is_enforced(tmp_path: Path) -> None:
    first = _publication(0)
    size = len(encode_economic_inequality_snapshot(first))
    publisher = create_economic_inequality_publisher(
        tmp_path,
        options=EconomicInequalityPublisherOptions(
            max_publications=16, max_bytes=size * 2 + 32
        ),
    )
    publisher.publish(first)
    publisher.publish(_publication(1))
    with pytest.raises(ValueError, match="quota"):
        publisher.publish(_publication(2))


def test_publication_count_quota_is_enforced(tmp_path: Path) -> None:
    publisher = create_economic_inequality_publisher(
        tmp_path,
        options=EconomicInequalityPublisherOptions(max_publications=1),
    )
    publisher.publish(_publication(0))
    with pytest.raises(ValueError, match="quota"):
        publisher.publish(_publication(1))


def test_oversize_payload_is_rejected(tmp_path: Path) -> None:
    publisher = create_economic_inequality_publisher(
        tmp_path,
        options=EconomicInequalityPublisherOptions(max_bytes=10),
    )
    with pytest.raises(ValueError, match="quota"):
        publisher.publish(_publication(0))


def test_corrupt_state_fails_closed(tmp_path: Path) -> None:
    publisher = create_economic_inequality_publisher(tmp_path)
    publisher.publish(_publication(0))
    state = tmp_path / "run-1" / "state.json"
    state.write_text("{not-json", encoding="utf-8")
    reader = create_economic_inequality_reader(tmp_path)
    with pytest.raises(ValueError, match="corrupt"):
        reader.read_snapshot("run-1")


def test_missing_publication_fails_closed(tmp_path: Path) -> None:
    reader = create_economic_inequality_reader(tmp_path)
    with pytest.raises(ValueError, match="missing"):
        reader.read_snapshot("run-1")


def test_invalid_options_fail_closed() -> None:
    with pytest.raises(ValueError, match="publications_range"):
        EconomicInequalityPublisherOptions(max_publications=0)
    with pytest.raises(ValueError, match="bytes_range"):
        EconomicInequalityPublisherOptions(max_bytes=0)
