"""V4-07 filesystem publication store, quotas, and read ports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import persistence
from experiments.dispute_harvest import build_completed_run_dispute_harvest
from experiments.dispute_publication import (
    build_dispute_harvest_result,
    publish_dispute_snapshot,
)
from persistence import (
    FilesystemDisputePublisher,
    FilesystemDisputeReader,
    create_dispute_publisher,
    create_dispute_reader,
)
from simulation import (
    DisputeArtifactError,
    DisputePublication,
    encode_dispute_snapshot,
)
from tests.unit.test_dispute_publication import _ledgers, _result

pytestmark = pytest.mark.unit


def _built(run_id: str = "run-1", tick: int = 100) -> Any:
    harvest = build_completed_run_dispute_harvest(
        _result(*_ledgers()),
        run_id=run_id,
        input_revision="revision-1",
        generated_tick=tick,
    )
    return build_dispute_harvest_result(harvest)


def test_publisher_is_atomic_and_idempotent(tmp_path: Path) -> None:
    built = _built()
    publisher = create_dispute_publisher(tmp_path)
    assert publisher is not None
    assert publish_dispute_snapshot(built, publisher) is True
    assert publish_dispute_snapshot(built, publisher) is True
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["schema_version"] == "dispute-resolution-store-v1"
    assert list(state["publications"]) == [built.snapshot.ref.publication_id]
    assert not list((tmp_path / "publications").glob("*.tmp"))
    reader = create_dispute_reader(tmp_path)
    assert reader is not None
    summary = reader.summary("run-1")
    assert summary.publication_id == built.snapshot.ref.publication_id
    assert summary.candidate_count == 1
    assert summary.claim_count == 2
    assert summary.resolution_count == 1


def test_duplicate_id_with_different_bytes_fails(tmp_path: Path) -> None:
    built = _built()
    publisher = create_dispute_publisher(tmp_path)
    assert publisher is not None
    publish_dispute_snapshot(built, publisher)
    payload = encode_dispute_snapshot(built.snapshot)
    tampered = DisputePublication(
        run_id="run-1",
        publication_id=built.snapshot.ref.publication_id,
        snapshot_digest=built.snapshot.ref.snapshot_digest,
        payload=payload + b"\n",
        generated_tick=100,
    )
    with pytest.raises(DisputeArtifactError) as excinfo:
        publisher.publish(tampered)
    assert excinfo.value.code == "dispute_publication_exists"
    reader = create_dispute_reader(tmp_path)
    assert reader is not None
    assert reader.summary("run-1").snapshot_digest == (
        built.snapshot.ref.snapshot_digest
    )


def test_publication_and_byte_quotas(tmp_path: Path) -> None:
    publisher = create_dispute_publisher(tmp_path, max_publications=1)
    assert publisher is not None
    publish_dispute_snapshot(_built("run-1", 10), publisher)
    with pytest.raises(DisputeArtifactError) as excinfo:
        publish_dispute_snapshot(_built("run-2", 10), publisher)
    assert excinfo.value.code == "dispute_quota_exceeded"

    tiny = create_dispute_publisher(tmp_path / "tiny", max_artifact_bytes=10)
    assert tiny is not None
    with pytest.raises(DisputeArtifactError) as excinfo:
        publish_dispute_snapshot(_built(), tiny)
    assert excinfo.value.code == "dispute_quota_exceeded"


def test_reader_verifies_digest(tmp_path: Path) -> None:
    built = _built()
    publisher = create_dispute_publisher(tmp_path)
    assert publisher is not None
    publish_dispute_snapshot(built, publisher)
    path = tmp_path / "publications" / f"{built.snapshot.ref.publication_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["generated_tick"] = 999
    path.write_text(
        json.dumps(data, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    reader = create_dispute_reader(tmp_path)
    assert reader is not None
    with pytest.raises(DisputeArtifactError) as excinfo:
        reader.summary("run-1")
    assert excinfo.value.code == "dispute_digest_mismatch"


def test_reader_selects_latest_publication(tmp_path: Path) -> None:
    publisher = create_dispute_publisher(tmp_path)
    assert publisher is not None
    publish_dispute_snapshot(_built("run-1", 10), publisher)
    latest = _built("run-1", 20)
    publish_dispute_snapshot(latest, publisher)
    reader = create_dispute_reader(tmp_path)
    assert reader is not None
    summary = reader.summary("run-1")
    assert summary.generated_tick == 20
    assert summary.publication_id == latest.snapshot.ref.publication_id


def test_reader_and_publisher_are_separate() -> None:
    assert create_dispute_publisher(None) is None
    assert create_dispute_reader(None) is None
    publisher = create_dispute_publisher(Path("/tmp/dispute-store"))
    reader = create_dispute_reader(Path("/tmp/dispute-store"))
    assert isinstance(publisher, FilesystemDisputePublisher)
    assert isinstance(reader, FilesystemDisputeReader)
    assert not hasattr(FilesystemDisputePublisher, "summary")
    assert not hasattr(FilesystemDisputeReader, "publish")


def test_persistence_facade_exports_dispute_store() -> None:
    for name in (
        "FilesystemDisputePublisher",
        "FilesystemDisputeReader",
        "create_dispute_publisher",
        "create_dispute_reader",
    ):
        assert name in persistence.__all__
        assert hasattr(persistence, name)
    assert persistence.__all__ == sorted(
        persistence.__all__, key=lambda name: (name[0].islower(), name)
    )
