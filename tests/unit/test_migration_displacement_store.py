# mypy: ignore-errors
"""Atomic migration-displacement-store-v1 behaviour."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from persistence.migration_displacement_filesystem import (
    MIGRATION_DISPLACEMENT_STORE_VERSION,
    MigrationDisplacementPublisherOptions,
    create_migration_displacement_publisher,
    create_migration_displacement_reader,
)
from simulation.migration_displacement_codec import finalize_migration_displacement_snapshot
from simulation.migration_displacement_models import empty_migration_displacement_snapshot


def _snapshot(run_id: str = "run-1", *, tag: str = "a"):
    base = empty_migration_displacement_snapshot(
        run_id, digest="", publication_id=""
    )
    # Vary unresolved_anchor_count via truncated flag so digests differ by tag.
    summary = replace(base.summary, truncated=(tag == "b"))
    return finalize_migration_displacement_snapshot(replace(base, summary=summary))


def test_publish_and_read_round_trip(tmp_path) -> None:
    assert MIGRATION_DISPLACEMENT_STORE_VERSION == "migration-displacement-store-v1"
    publisher = create_migration_displacement_publisher(tmp_path)
    reader = create_migration_displacement_reader(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    assert reader.read_snapshot("run-1") == snapshot
    summary = reader.read_summary("run-1")
    assert summary is not None
    assert summary.publication_id == snapshot.publication_id
    assert summary.digest == snapshot.digest
    listed = reader.list_publications("run-1")
    assert listed == (snapshot.publication_id,)


def test_duplicate_publication_id_does_not_overwrite(tmp_path) -> None:
    publisher = create_migration_displacement_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    publisher.publish(snapshot)
    state = json.loads(
        (tmp_path / "run-1" / "state.json").read_text(encoding="utf-8")
    )
    assert len(state["publications"]) == 1
    changed = finalize_migration_displacement_snapshot(
        replace(
            empty_migration_displacement_snapshot(
                "run-1", digest="", publication_id=""
            ),
            summary=replace(
                empty_migration_displacement_snapshot(
                    "run-1", digest="", publication_id=""
                ).summary,
                truncated=True,
            ),
        )
    )
    # Force same publication id with different bytes.
    colliding = replace(
        changed,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        summary=replace(
            changed.summary,
            publication_id=snapshot.publication_id,
            digest=snapshot.digest,
            truncated=True,
        ),
    )
    with pytest.raises(ValueError, match="migration_displacement_publication_exists"):
        publisher.publish(colliding)
    reread = create_migration_displacement_reader(tmp_path).read_snapshot("run-1")
    assert reread == snapshot


def test_publication_quota(tmp_path) -> None:
    publisher = create_migration_displacement_publisher(
        tmp_path, MigrationDisplacementPublisherOptions(max_publications=1)
    )
    publisher.publish(_snapshot(tag="a"))
    with pytest.raises(ValueError, match="migration_displacement_quota_exceeded"):
        publisher.publish(_snapshot(tag="b"))


def test_byte_quota(tmp_path) -> None:
    publisher = create_migration_displacement_publisher(
        tmp_path, MigrationDisplacementPublisherOptions(max_bytes=10)
    )
    with pytest.raises(ValueError, match="migration_displacement_quota_exceeded"):
        publisher.publish(_snapshot())


def test_corrupt_state_and_payload_are_store_corrupt(tmp_path) -> None:
    publisher = create_migration_displacement_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    (tmp_path / "run-1" / "state.json").write_text("{not json", encoding="utf-8")
    reader = create_migration_displacement_reader(tmp_path)
    with pytest.raises(ValueError, match="migration_displacement_store_corrupt"):
        reader.read_summary("run-1")
    # Restore state, corrupt payload.
    publisher = create_migration_displacement_publisher(tmp_path / "payload")
    snapshot = _snapshot()
    publisher.publish(snapshot)
    path = tmp_path / "payload" / "run-1" / f"{snapshot.publication_id}.json"
    path.write_text("{bad", encoding="utf-8")
    reader = create_migration_displacement_reader(tmp_path / "payload")
    with pytest.raises(ValueError, match="migration_displacement_store_corrupt"):
        reader.read_snapshot("run-1")


def test_reader_returns_none_for_unknown_run(tmp_path) -> None:
    reader = create_migration_displacement_reader(tmp_path)
    assert reader.read_summary("missing") is None
    assert reader.read_snapshot("missing") is None
    assert reader.list_publications("missing") == ()


def test_concurrent_publishers_commit_one_state(tmp_path) -> None:
    publisher = create_migration_displacement_publisher(tmp_path)
    snapshots = [_snapshot(tag=tag) for tag in ("a", "b", "a", "b")]

    def _publish(item):
        publisher.publish(item)
        return item.publication_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_publish, snapshots))
    state = json.loads(
        (tmp_path / "run-1" / "state.json").read_text(encoding="utf-8")
    )
    assert state["store_version"] == MIGRATION_DISPLACEMENT_STORE_VERSION
    assert len(state["publications"]) == 2
    reader = create_migration_displacement_reader(tmp_path)
    assert len(reader.list_publications("run-1")) == 2


def test_options_reject_non_positive() -> None:
    with pytest.raises(ValueError, match="migration_displacement_publications_range"):
        MigrationDisplacementPublisherOptions(max_publications=0)
    with pytest.raises(ValueError, match="migration_displacement_bytes_range"):
        MigrationDisplacementPublisherOptions(max_bytes=-1)
