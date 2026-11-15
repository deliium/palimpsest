# mypy: ignore-errors
"""Atomic filesystem store for economic-cascade snapshots."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from persistence.economic_cascades_filesystem import (
    ECONOMIC_CASCADES_STORE_VERSION,
    EconomicCascadesPublisherOptions,
    economic_cascades_store_publisher,
    economic_cascades_store_reader,
)
from simulation.economic_cascades_codec import finalize_economic_cascades_snapshot
from simulation.economic_cascades_models import empty_economic_cascades_snapshot

pytestmark = pytest.mark.unit


def _snapshot(run_id: str = "run-1"):
    return finalize_economic_cascades_snapshot(
        empty_economic_cascades_snapshot(run_id)
    )


def test_store_version_is_locked() -> None:
    assert ECONOMIC_CASCADES_STORE_VERSION == "economic-cascades-store-v1"


def test_publish_read_and_idempotent_republish(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(tmp_path)
    reader = economic_cascades_store_reader(tmp_path)
    snapshot = _snapshot()
    first = publisher.publish(snapshot)
    second = publisher.publish(snapshot)
    assert first.stored is True
    assert second.stored is False
    assert reader.read_snapshot("run-1") == snapshot


def test_conflicting_publication_id_is_rejected(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    state_path = tmp_path / "run-1" / "state.json"
    state = json.loads(state_path.read_text())
    state["publications"][snapshot.publication_id]["digest"] = "sha256:other"
    state_path.write_text(json.dumps(state))
    with pytest.raises(ValueError):
        publisher.publish(snapshot)


def test_publication_count_quota(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(
        tmp_path, options=EconomicCascadesPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot("run-1"))
    second = finalize_economic_cascades_snapshot(
        dataclasses.replace(
            empty_economic_cascades_snapshot("run-1"),
            generated_from_tick=10,
        )
    )
    with pytest.raises(ValueError):
        publisher.publish(second)


def test_byte_quota(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(
        tmp_path, options=EconomicCascadesPublisherOptions(max_bytes=1)
    )
    with pytest.raises(ValueError):
        publisher.publish(_snapshot())


def test_corrupt_state_fails_closed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "state.json").write_text("{not-json")
    reader = economic_cascades_store_reader(tmp_path)
    with pytest.raises(ValueError):
        reader.read_snapshot("run-1")


def test_missing_run_fails_closed(tmp_path: Path) -> None:
    reader = economic_cascades_store_reader(tmp_path)
    with pytest.raises(ValueError):
        reader.read_snapshot("missing")


def test_latest_publication_is_selected(tmp_path: Path) -> None:
    publisher = economic_cascades_store_publisher(tmp_path)
    reader = economic_cascades_store_reader(tmp_path)
    first = _snapshot("run-1")
    publisher.publish(first)
    second = finalize_economic_cascades_snapshot(
        dataclasses.replace(
            empty_economic_cascades_snapshot("run-1"),
            generated_from_tick=10,
        )
    )
    publisher.publish(second)
    assert reader.read_snapshot("run-1").generated_from_tick == 10
