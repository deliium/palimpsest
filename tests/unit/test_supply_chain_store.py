# mypy: ignore-errors

"""Atomic supply-chain store and dual-gated settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from persistence.supply_chain_filesystem import (
    SupplyChainPublisherOptions,
    SupplyChainStoreCorrupt,
    create_supply_chain_publisher,
    create_supply_chain_reader,
)
from simulation.supply_chain_codec import finalize_supply_chain_snapshot
from simulation.supply_chain_models import empty_supply_chain_snapshot

pytestmark = pytest.mark.unit


def _snapshot(run_id: str = "run-1"):
    return finalize_supply_chain_snapshot(empty_supply_chain_snapshot(run_id))


def test_publish_then_read(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    reader = create_supply_chain_reader(tmp_path)
    assert reader.read_snapshot("run-1") == snapshot
    assert reader.read_summary("run-1") is not None


def test_duplicate_publish_is_idempotent(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    publisher.publish(snapshot)
    assert create_supply_chain_reader(tmp_path).list_publications("run-1") == (
        snapshot.publication_id,
    )


def test_publication_quota(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(
        tmp_path, SupplyChainPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot())
    with pytest.raises(ValueError, match="quota"):
        publisher.publish(
            finalize_supply_chain_snapshot(
                empty_supply_chain_snapshot("run-1", window_tick=1)
            )
        )


def test_corrupt_payload_fails_closed(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    path = tmp_path / "run-1" / f"{snapshot.publication_id}.json"
    path.write_text("{not-json", encoding="utf-8")
    with pytest.raises(SupplyChainStoreCorrupt):
        create_supply_chain_reader(tmp_path).read_snapshot("run-1")


def test_list_publications_is_ordered(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(tmp_path)
    first = _snapshot("run-1")
    publisher.publish(first)
    assert create_supply_chain_reader(tmp_path).list_publications("run-1") == (
        first.publication_id,
    )


def test_byte_quota(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(
        tmp_path, SupplyChainPublisherOptions(max_bytes=8)
    )
    with pytest.raises(ValueError, match="quota"):
        publisher.publish(_snapshot())


def test_atomic_write_replaces_state(tmp_path: Path) -> None:
    publisher = create_supply_chain_publisher(tmp_path)
    first = _snapshot("run-1")
    second = finalize_supply_chain_snapshot(
        empty_supply_chain_snapshot("run-1", window_tick=1)
    )
    publisher.publish(first)
    publisher.publish(second)
    reader = create_supply_chain_reader(tmp_path)
    assert reader.read_snapshot("run-1", second.publication_id) == second
    assert set(reader.list_publications("run-1")) == {
        first.publication_id,
        second.publication_id,
    }
