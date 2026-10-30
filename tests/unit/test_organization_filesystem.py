"""Atomic organization filesystem store: quotas, locks, and immutable reads."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import pytest

from persistence.organization_filesystem import (
    create_organization_publisher,
    create_organization_reader,
)
from simulation.organization_codec import (
    compute_organization_publication_id,
    encode_organization_snapshot,
)
from simulation.organization_models import (
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationSnapshot,
)
from simulation.organization_ports import OrganizationPublication
from tests.unit.organization_artifact_helpers import example_snapshot

pytestmark = pytest.mark.unit


def _publication(
    snapshot: OrganizationSnapshot | None = None,
) -> OrganizationPublication:
    snapshot = example_snapshot() if snapshot is None else snapshot
    publication_id = compute_organization_publication_id(snapshot)
    from dataclasses import replace

    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
    return OrganizationPublication(
        run_id=published.run_id,
        publication_id=publication_id,
        snapshot_digest=hashlib.sha256(payload).hexdigest(),
        payload=payload,
        generated_tick=published.generated_tick,
    )


def test_publish_and_read_round_trip(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication()
    publisher.publish(publication)

    summary = reader.summary(publication.run_id)
    assert summary is not None
    assert summary.publication_id == publication.publication_id
    assert summary.candidate_count == 2
    assert summary.window_count == 1

    page = reader.candidates(publication.run_id, publication.publication_id, 0, 10)
    assert len(page.rows) == 2
    candidate = reader.candidate(
        publication.run_id,
        publication.publication_id,
        cast(OrganizationCandidateRecord, page.rows[0]).organization_id,
    )
    assert candidate is not None
    assert (
        candidate.organization_id
        == cast(OrganizationCandidateRecord, page.rows[0]).organization_id
    )
    lineage = reader.lineage(publication.run_id, publication.publication_id, 0, 10)
    assert len(lineage.rows) == 1
    assert (
        reader.candidate(
            publication.run_id, publication.publication_id, "org-aaaaaaaaaaaaaaaa"
        )
        is None
    )


def test_identical_bytes_are_idempotent_and_conflicts_are_rejected(
    tmp_path: Path,
) -> None:
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    publication = _publication()
    publisher.publish(publication)
    publisher.publish(publication)

    from dataclasses import replace

    conflicting = replace(publication, payload=publication.payload + b" ")
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(conflicting)
    assert excinfo.value.code == "organization_publication_exists"


def test_quota_is_enforced(tmp_path: Path) -> None:
    publisher = create_organization_publisher(
        tmp_path, max_publications=1, max_artifact_bytes=1_000_000
    )
    assert publisher is not None
    publisher.publish(_publication())
    from dataclasses import replace

    second = _publication()
    other = replace(second, publication_id="org-edge-fedcba9876543210")
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(other)
    assert excinfo.value.code == "organization_quota_exceeded"


def test_lock_blocks_concurrent_publish(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    run_dir = tmp_path / example_snapshot().run_id
    run_dir.mkdir(parents=True)
    (run_dir / "writer.lock").write_text("")
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(_publication())
    assert excinfo.value.code == "organization_store_locked"


def test_missing_publication_returns_none(tmp_path: Path) -> None:
    reader = create_organization_reader(tmp_path)
    assert reader is not None
    assert reader.summary("run-missing") is None
    assert not (tmp_path / "run-missing").exists()


def test_corrupt_state_is_rejected(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication()
    publisher.publish(publication)
    state = tmp_path / publication.run_id / "state.json"
    state.write_text("{not-json")
    with pytest.raises(OrganizationArtifactError):
        reader.summary(publication.run_id)


def test_tampered_snapshot_digest_is_rejected(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication()
    publisher.publish(publication)
    snapshot_path = (
        tmp_path
        / publication.run_id
        / "publications"
        / publication.publication_id
        / "snapshot.json"
    )
    snapshot_path.write_bytes(publication.payload.replace(b'"ok"', b'"ok" ').rstrip())
    with pytest.raises(OrganizationArtifactError):
        reader.summary(publication.run_id)


def test_disabled_root_returns_absent_adapters() -> None:
    assert create_organization_publisher(None) is None
    assert create_organization_reader(None) is None
