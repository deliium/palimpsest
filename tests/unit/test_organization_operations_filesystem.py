"""Filesystem store: v1/v2 publications, operation counts, and pages."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import replace
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
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationOperationRecord,
    OrganizationSnapshot,
)
from simulation.organization_ports import OrganizationPublication

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "src" / "persistence" / "organization_filesystem.py"

RUN = "run-store"
ORG_A = f"org-{'a' * 16}"
ORG_B = f"org-{'b' * 16}"


def _operation(index: int, *, domain: str = "resource_control") -> (
    OrganizationOperationRecord
):
    return OrganizationOperationRecord(
        operation_id=f"orgop-{index:016x}",
        domain=domain,
        act="authorize_control",
        stance="recognized",
        authority_basis="role_belief",
        provenance_code="role_authorized",
        outcome="observed",
        command_kind="none",
        target_kind="anchor",
        anchor_kind="item",
        anchor_id=f"item-{index}",
        tick=3,
        first_tick=1,
        last_tick=9,
        support_count=1,
        contest_count=0,
        resolved=True,
    )


def _candidate(
    organization_id: str, operations: tuple[OrganizationOperationRecord, ...]
) -> OrganizationCandidateRecord:
    return OrganizationCandidateRecord(
        organization_id=organization_id,
        creation_tick=0,
        first_tick=0,
        last_tick=9,
        status="partial",
        temporal_scope="ongoing",
        self_identified=False,
        operations=operations,
    )


def _snapshot(
    schema_version: str = ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
) -> OrganizationSnapshot:
    return OrganizationSnapshot(
        schema_version=schema_version,
        policy_version="organization-analysis.v1",
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
        candidates=(
            _candidate(ORG_A, (_operation(1), _operation(2, domain="storage"))),
            _candidate(ORG_B, (_operation(3),)),
        )
        if schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
        else (
            _candidate(ORG_A, ()),
            _candidate(ORG_B, ()),
        ),
    )


def _publication(snapshot: OrganizationSnapshot) -> OrganizationPublication:
    publication_id = compute_organization_publication_id(snapshot)
    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
    return OrganizationPublication(
        run_id=published.run_id,
        publication_id=publication_id,
        snapshot_digest=hashlib.sha256(payload).hexdigest(),
        payload=payload,
        generated_tick=published.generated_tick,
    )


def test_v2_publication_round_trips_with_operation_counts(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication(_snapshot())
    publisher.publish(publication)

    summary = reader.summary(RUN)
    assert summary is not None
    assert summary.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert summary.operation_count == 3

    page = reader.operations(
        RUN, publication.publication_id, 0, 10, domain="storage"
    )
    rows = cast(tuple[OrganizationOperationRecord, ...], page.rows)
    assert [row.operation_id for row in rows] == [
        "orgop-0000000000000002"
    ]


def test_v1_publication_remains_readable_with_zero_operations(
    tmp_path: Path,
) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    publication = _publication(
        _snapshot(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1)
    )
    publisher.publish(publication)
    summary = reader.summary(RUN)
    assert summary is not None
    assert summary.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1
    assert summary.operation_count == 0
    page = reader.operations(RUN, publication.publication_id, 0, 10)
    assert page.rows == ()


def test_unknown_schema_fails_closed(tmp_path: Path) -> None:
    publisher = create_organization_publisher(tmp_path)
    reader = create_organization_reader(tmp_path)
    assert publisher is not None and reader is not None
    snapshot = _snapshot()
    publication = _publication(snapshot)
    payload = publication.payload.replace(
        b'"organization-snapshot-v3"', b'"organization-snapshot-v9"'
    )
    broken = replace(
        publication,
        payload=payload,
        snapshot_digest=hashlib.sha256(payload).hexdigest(),
    )
    publisher.publish(broken)
    with pytest.raises(OrganizationArtifactError):
        reader.summary(RUN)


def test_duplicate_id_is_idempotent_but_conflicting_bytes_fail(
    tmp_path: Path,
) -> None:
    publisher = create_organization_publisher(tmp_path)
    assert publisher is not None
    publication = _publication(_snapshot())
    publisher.publish(publication)
    publisher.publish(publication)
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(replace(publication, payload=publication.payload + b" "))
    assert excinfo.value.code == "organization_publication_exists"


def test_quota_still_counts_payload_bytes(tmp_path: Path) -> None:
    publisher = create_organization_publisher(
        tmp_path, max_publications=1, max_artifact_bytes=2_000_000
    )
    assert publisher is not None
    publisher.publish(_publication(_snapshot()))
    second = _publication(_snapshot(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1))
    with pytest.raises(OrganizationArtifactError) as excinfo:
        publisher.publish(replace(second, publication_id="org-edge-fedcba9876543210"))
    assert excinfo.value.code == "organization_quota_exceeded"


def test_store_imports_no_analysis_or_agents() -> None:
    tree = ast.parse(STORE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(("analysis", "agents"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(("analysis", "agents"))
