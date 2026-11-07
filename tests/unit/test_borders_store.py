# mypy: ignore-errors
"""Atomic borders-store-v1 behaviour."""

from __future__ import annotations

import dataclasses
import json

import pytest

from persistence.borders_filesystem import (
    BORDERS_STORE_SCHEMA,
    BordersPublisherOptions,
    create_borders_publisher,
    create_borders_reader,
)
from simulation.borders_codec import finalize_borders_snapshot
from simulation.borders_models import empty_borders_snapshot


def _snapshot(run_id: str = "run-1", catalog: str = "metric-catalog-v1"):
    return finalize_borders_snapshot(
        empty_borders_snapshot(
            run_id,
            publication_id="bd-pub-pending",
            digest="0" * 64,
            catalog_version=catalog,
        )
    )


def test_store_schema_is_borders_store_v1() -> None:
    assert BORDERS_STORE_SCHEMA == "borders-store-v1"


def test_atomic_publish_and_read_round_trip(tmp_path) -> None:
    publisher = create_borders_publisher(tmp_path)
    reader = create_borders_reader(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    assert reader.snapshot("run-1") == snapshot
    summary = reader.read_summary("run-1")
    assert summary is not None
    assert summary.publication_id == snapshot.publication_id
    assert reader.read_claims("run-1", after=None, limit=10) == ()
    assert reader.read_control("run-1", layer="all", after=None, limit=10) == ()


def test_identical_duplicate_is_idempotent(tmp_path) -> None:
    publisher = create_borders_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    publisher.publish(snapshot)
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert len(state["publications"]) == 1


def test_changed_duplicate_is_rejected(tmp_path) -> None:
    publisher = create_borders_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    changed = dataclasses.replace(
        snapshot,
        digest="b" * 64,
        summary=dataclasses.replace(snapshot.summary, digest="b" * 64),
    )
    with pytest.raises(ValueError):
        publisher.publish(changed)


def test_publication_and_byte_quota(tmp_path) -> None:
    publisher = create_borders_publisher(
        tmp_path, BordersPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot())
    with pytest.raises(ValueError):
        publisher.publish(_snapshot(catalog="metric-catalog-v2"))
    small = create_borders_publisher(
        tmp_path / "bytes", BordersPublisherOptions(max_bytes=10)
    )
    with pytest.raises(ValueError):
        small.publish(_snapshot())


def test_corrupt_state_fails_closed(tmp_path) -> None:
    (tmp_path / "state.json").write_text("{not json", encoding="utf-8")
    reader = create_borders_reader(tmp_path)
    with pytest.raises(ValueError):
        reader.read_summary("run-1")


def test_reader_returns_none_for_unknown_run(tmp_path) -> None:
    reader = create_borders_reader(tmp_path)
    assert reader.read_summary("missing") is None
    assert reader.snapshot("missing") is None
