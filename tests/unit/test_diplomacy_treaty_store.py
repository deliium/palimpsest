# mypy: ignore-errors
"""V4-11 v1/v2 diplomacy store coexistence and quotas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from persistence.diplomacy_filesystem import (
    FilesystemDiplomacyPublisher,
    FilesystemDiplomacyReader,
)
from simulation.diplomacy_codec import finalize_diplomacy_snapshot
from simulation.diplomacy_models import (
    DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1,
    DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2,
    DiplomacyArtifactError,
    empty_diplomacy_snapshot,
)
from simulation.diplomacy_ports import DiplomacyPublication

pytestmark = pytest.mark.unit


def _publication(
    run_id: str,
    *,
    revision: str = "rev-1",
    schema_version: str = DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2,
) -> DiplomacyPublication:
    snapshot = finalize_diplomacy_snapshot(
        empty_diplomacy_snapshot(
            run_id,
            revision=revision,
            window_end=1,
            schema_version=schema_version,
        )
    )
    return DiplomacyPublication(
        run_id=run_id,
        publication_id=snapshot.publication_id,
        snapshot_digest=snapshot.digest,
        snapshot=snapshot,
    )


def test_v2_publication_round_trips(tmp_path: Path) -> None:
    publisher = FilesystemDiplomacyPublisher(tmp_path / "store")
    reader = FilesystemDiplomacyReader(tmp_path / "store")
    publication = _publication("run-v2")
    publisher.publish(publication)
    snapshot = reader._snapshot("run-v2")
    assert snapshot.schema_version == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2
    assert snapshot.digest == publication.snapshot_digest
    assert reader.read_summary("run-v2").publication_id == publication.publication_id


def test_v1_and_v2_coexist_under_one_root(tmp_path: Path) -> None:
    publisher = FilesystemDiplomacyPublisher(tmp_path / "store")
    reader = FilesystemDiplomacyReader(tmp_path / "store")
    publisher.publish(
        _publication("run-v1", schema_version=DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1)
    )
    publisher.publish(_publication("run-v2"))
    assert (
        reader._snapshot("run-v1").schema_version
        == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V1
    )
    assert (
        reader._snapshot("run-v2").schema_version
        == DIPLOMACY_SNAPSHOT_SCHEMA_VERSION_V2
    )
    assert reader.read_treaties("run-v1") == ()


def test_identical_bytes_are_idempotent_and_changed_bytes_fail(
    tmp_path: Path,
) -> None:
    publisher = FilesystemDiplomacyPublisher(tmp_path / "store")
    publication = _publication("run-1")
    publisher.publish(publication)
    publisher.publish(publication)
    path = tmp_path / "store" / "publications" / f"{publication.publication_id}.json"
    path.write_bytes(b"{}")
    with pytest.raises(DiplomacyArtifactError, match="diplomacy_publication_exists"):
        publisher.publish(publication)


def test_cumulative_publication_and_byte_quotas(tmp_path: Path) -> None:
    publication_quota = FilesystemDiplomacyPublisher(
        tmp_path / "publication-quota", max_publications=1
    )
    publication_quota.publish(_publication("run-1", revision="rev-1"))
    with pytest.raises(DiplomacyArtifactError, match="diplomacy_quota_exceeded"):
        publication_quota.publish(_publication("run-1", revision="rev-2"))

    byte_quota = FilesystemDiplomacyPublisher(
        tmp_path / "byte-quota", max_bytes=1
    )
    with pytest.raises(DiplomacyArtifactError, match="diplomacy_quota_exceeded"):
        byte_quota.publish(_publication("run-1"))


def test_failed_publication_leaves_no_partial_state(tmp_path: Path) -> None:
    publisher = FilesystemDiplomacyPublisher(
        tmp_path / "store", max_publications=1
    )
    publisher.publish(_publication("run-1", revision="rev-1"))
    with pytest.raises(DiplomacyArtifactError):
        publisher.publish(_publication("run-1", revision="rev-2"))
    state = json.loads((tmp_path / "store" / "state.json").read_text(encoding="utf-8"))
    assert len(state["publications"]) == 1
    assert not list((tmp_path / "store" / "publications").glob("*.tmp"))
