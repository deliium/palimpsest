# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from pathlib import Path

import pytest

from persistence.organized_conflict_filesystem import (
    OrganizedConflictPublisherOptions,
    create_organized_conflict_publisher,
    create_organized_conflict_reader,
)
from simulation.organized_conflict_codec import finalize_organized_conflict_snapshot
from simulation.organized_conflict_models import (
    ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
    OrganizedConflictSnapshot,
    OrganizedConflictSummaryRow,
)


def _snapshot(run_id: str = "run-store") -> OrganizedConflictSnapshot:
    return finalize_organized_conflict_snapshot(
        OrganizedConflictSnapshot(
            schema_version=ORGANIZED_CONFLICT_SNAPSHOT_SCHEMA,
            policy_version="organized-conflict-snapshot.v1",
            run_id=run_id,
            publication_id="oc-pub-" + "0" * 16,
            digest="0" * 64,
            summary=OrganizedConflictSummaryRow(),
        )
    )


def test_publish_then_read_round_trip(tmp_path: Path) -> None:
    publisher = create_organized_conflict_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    reader = create_organized_conflict_reader(tmp_path)
    assert reader.snapshot("run-store") == snapshot
    assert reader.summary("run-store").publication_id == snapshot.publication_id


def test_duplicate_identical_is_idempotent(tmp_path: Path) -> None:
    publisher = create_organized_conflict_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    publisher.publish(snapshot)
    assert create_organized_conflict_reader(tmp_path).snapshot("run-store") == snapshot


def test_changed_bytes_are_rejected(tmp_path: Path) -> None:
    publisher = create_organized_conflict_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    changed = OrganizedConflictSnapshot(
        schema_version=snapshot.schema_version,
        policy_version=snapshot.policy_version,
        run_id=snapshot.run_id,
        publication_id=snapshot.publication_id,
        digest=snapshot.digest,
        summary=OrganizedConflictSummaryRow(episode_count=1),
    )
    with pytest.raises(ValueError, match="organized_conflict_publication_exists"):
        publisher.publish(changed)


def test_quota_preserves_prior_publication(tmp_path: Path) -> None:
    publisher = create_organized_conflict_publisher(
        tmp_path, OrganizedConflictPublisherOptions(max_publications=1)
    )
    first = _snapshot("run-a")
    publisher.publish(first)
    second = finalize_organized_conflict_snapshot(
        OrganizedConflictSnapshot(
            schema_version=first.schema_version,
            policy_version=first.policy_version,
            run_id="run-a",
            publication_id="oc-pub-" + "0" * 16,
            digest="0" * 64,
            summary=OrganizedConflictSummaryRow(episode_count=2),
        )
    )
    with pytest.raises(ValueError, match="organized_conflict_quota_exceeded"):
        publisher.publish(second)
    assert create_organized_conflict_reader(tmp_path).snapshot("run-a") == first


def test_failed_publish_leaves_no_partial_state(tmp_path: Path) -> None:
    publisher = create_organized_conflict_publisher(tmp_path)
    with pytest.raises((TypeError, ValueError)):
        publisher.publish(object())
    assert create_organized_conflict_reader(tmp_path).snapshot("run-store") is None
