"""Atomic filesystem store for v1/v2/v3 organization publications."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

import pytest

from experiments.organization_publication import build_organization_harvest_result
from persistence.organization_filesystem import (
    create_organization_publisher,
    create_organization_reader,
)
from simulation.organization_codec import (
    compute_organization_publication_id,
    encode_organization_snapshot,
)
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    OrganizationCoverage,
    OrganizationSnapshot,
)
from simulation.organization_ports import OrganizationPublication
from tests.unit.test_organization_agency_publication import RUN_ID, _harvest

pytestmark = pytest.mark.unit


def _publish(tmp_path: Path, snapshot: OrganizationSnapshot) -> OrganizationPublication:
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    from dataclasses import replace

    publication_id = compute_organization_publication_id(snapshot)
    snapshot = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(snapshot)
    publication = OrganizationPublication(
        run_id=snapshot.run_id,
        publication_id=publication_id,
        snapshot_digest=hashlib.sha256(payload).hexdigest(),
        payload=payload,
        generated_tick=snapshot.generated_tick,
    )
    publisher.publish(publication)
    return publication


def _empty(schema: str) -> OrganizationSnapshot:
    return OrganizationSnapshot(
        schema_version=schema,
        policy_version="organization-analysis.v1",
        run_id=RUN_ID,
        input_revision="revision-1",
        generated_tick=10,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
    )


def test_v3_publication_round_trips_with_digest_and_counts(tmp_path: Path) -> None:
    result = build_organization_harvest_result(_harvest())
    published = _publish(tmp_path, result.snapshot)
    reader = create_organization_reader(tmp_path)
    assert reader is not None
    summary = reader.summary(RUN_ID)
    assert summary is not None
    assert summary.snapshot_digest == hashlib.sha256(published.payload).hexdigest()
    assert summary.collective_decision_count == 1
    assert summary.collective_implementation_count == 1
    page = reader.collective_agency(RUN_ID, published.publication_id, 0, 10)
    assert len(page.rows) == 1
    assert cast(Any, page.rows[0]).decision_id.startswith("orgcpd-")


def test_v1_and_v2_publications_have_empty_agency_pages(tmp_path: Path) -> None:
    for schema in (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    ):
        root = tmp_path / schema
        published = _publish(root, _empty(schema))
        reader = create_organization_reader(root)
        assert reader is not None
        summary = reader.summary(RUN_ID)
        assert summary is not None
        assert summary.schema_version == schema
        assert summary.collective_decision_count == 0
        page = reader.collective_agency(RUN_ID, published.publication_id, 0, 10)
        assert page.rows == ()


def test_tampered_digest_fails_closed(tmp_path: Path) -> None:
    from simulation.organization_models import OrganizationArtifactError

    published = _publish(tmp_path, _empty(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2))
    reader = create_organization_reader(tmp_path)
    assert reader is not None
    snapshot_path = (
        tmp_path / RUN_ID / "publications" / published.publication_id / "snapshot.json"
    )
    snapshot_path.write_bytes(
        snapshot_path.read_bytes().replace(b"revision-1", b"revision-2")
    )
    with pytest.raises(OrganizationArtifactError):
        reader.summary(RUN_ID)


def test_duplicate_publication_is_idempotent_but_conflicting_bytes_fail(
    tmp_path: Path,
) -> None:
    from simulation.organization_models import OrganizationArtifactError

    published = _publish(tmp_path, _empty(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2))
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    publisher.publish(published)
    conflicting = OrganizationPublication(
        run_id=published.run_id,
        publication_id=published.publication_id,
        snapshot_digest=hashlib.sha256(b"different").hexdigest(),
        payload=b"different",
        generated_tick=published.generated_tick,
    )
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(conflicting)
    assert excinfo.value.code == "organization_publication_exists"
