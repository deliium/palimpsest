# mypy: ignore-errors
"""V4-28 filesystem store is atomic, quota-bounded, and tamper-evident."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.replication_analysis import harvest_replication_analysis
from analysis.replication_rows import ReplicationFacts
from experiments.replication_publication import compose_replication_snapshot
from persistence.replication_filesystem import (
    STATE_FILE,
    replication_store_publisher,
    replication_store_reader,
)
from simulation.replication_ports import (
    ReplicationPublicationError,
    ReplicationPublicationOptions,
)

pytestmark = pytest.mark.unit

RUN = "run-replication-store"


def _snapshot(*, tick: int = 0, run_id: str = RUN):
    return compose_replication_snapshot(
        harvest_replication_analysis(ReplicationFacts()),
        run_id=run_id,
        generated_from_tick=tick,
    )


def _store(root: Path, **options):
    return replication_store_publisher(
        root, options=ReplicationPublicationOptions(enabled=True, **options)
    )


def test_publish_is_idempotent_for_identical_bytes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    first = store.publish(snapshot)
    second = store.publish(snapshot)
    assert first.stored is True
    assert first.reason == "published"
    assert second.stored is False
    assert second.reason == "published"
    assert replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    ).read_snapshot(RUN) == snapshot


def test_quota_is_cumulative_and_keeps_the_last_good_publication(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, max_publications=1)
    first = _snapshot(tick=0)
    second = _snapshot(tick=1)
    assert store.publish(first).stored is True
    rejected = store.publish(second)
    assert rejected.stored is False
    assert rejected.reason == "quota_exceeded"
    reader = replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    assert reader.read_snapshot(RUN).publication_id == first.publication_id
    assert reader.read_snapshot(RUN, first.publication_id) == first


def test_explicit_old_publication_stays_readable_after_a_newer_publish(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    first = _snapshot(tick=0)
    second = _snapshot(tick=1)
    assert store.publish(first).stored is True
    assert store.publish(second).stored is True
    reader = replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    assert reader.read_snapshot(RUN).publication_id == second.publication_id
    assert reader.read_snapshot(RUN, first.publication_id) == first


def test_missing_publication_and_missing_run_fail_closed(tmp_path: Path) -> None:
    reader = replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    with pytest.raises(ReplicationPublicationError) as excinfo:
        reader.read_snapshot(RUN)
    assert excinfo.value.code == "replication_store_missing"
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    with pytest.raises(ReplicationPublicationError) as excinfo:
        reader.read_snapshot(RUN, "srep-unknown")
    assert excinfo.value.code == "replication_store_missing"


def test_same_publication_id_with_different_bytes_is_corruption(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    snapshot = _snapshot()
    store.publish(snapshot)
    path = tmp_path / RUN / f"{snapshot.publication_id}.json"
    material = path.read_bytes()
    path.write_bytes(material.replace(b'"run_id":"', b'"run_id":"x', 1))
    with pytest.raises(ReplicationPublicationError) as excinfo:
        store.publish(snapshot)
    assert excinfo.value.code == "replication_store_corrupt"


def test_malformed_state_file_is_corrupt_not_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / RUN
    run_dir.mkdir(parents=True)
    (run_dir / STATE_FILE).write_text("{not json", encoding="utf-8")
    reader = replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    with pytest.raises(ReplicationPublicationError) as excinfo:
        reader.read_snapshot(RUN)
    assert excinfo.value.code == "replication_store_corrupt"


def test_unsupported_state_version_is_corrupt(tmp_path: Path) -> None:
    run_dir = tmp_path / RUN
    run_dir.mkdir(parents=True)
    (run_dir / STATE_FILE).write_text(
        json.dumps({"version": "other-store-v0", "publications": []}),
        encoding="utf-8",
    )
    reader = replication_store_reader(
        tmp_path, options=ReplicationPublicationOptions(enabled=True)
    )
    with pytest.raises(ReplicationPublicationError) as excinfo:
        reader.read_snapshot(RUN)
    assert excinfo.value.code == "replication_store_corrupt"


@pytest.mark.parametrize("run_id", ["..", ".", "a/b", "a\\b", ""])
def test_payload_paths_cannot_escape_the_configured_root(
    tmp_path: Path, run_id: str
) -> None:
    store = _store(tmp_path)
    with pytest.raises((ReplicationPublicationError, ValueError)):
        store.publish(_snapshot(run_id=run_id))
    assert not (tmp_path.parent / "escape").exists()


def test_disabled_store_reports_the_reason_without_writing(tmp_path: Path) -> None:
    store = replication_store_publisher(
        tmp_path, options=ReplicationPublicationOptions(enabled=False)
    )
    receipt = store.publish(_snapshot())
    assert receipt.stored is False
    assert receipt.reason == "disabled"
    assert list(tmp_path.iterdir()) == []
