"""Organization operation paging, filters, and purpose-bound cursors."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from persistence.organization_filesystem import (
    FilesystemOrganizationPublisher,
    FilesystemOrganizationReader,
)
from simulation import (
    ORGANIZATION_CURSOR_PURPOSES,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationCursor,
    OrganizationOperationRecord,
    OrganizationPublication,
    OrganizationSnapshot,
    compute_organization_publication_id,
    encode_organization_snapshot,
    organization_digest,
    organization_query_fingerprint,
    select_organization_rows,
)

pytestmark = pytest.mark.unit

RUN = "run-operations"
ORG_A = f"org-{'a' * 16}"
ORG_B = f"org-{'b' * 16}"


def _operation(
    index: int,
    *,
    domain: str = "resource_control",
    tick: int = 3,
) -> OrganizationOperationRecord:
    return OrganizationOperationRecord(
        operation_id=f"orgop-{index:016x}",
        domain=domain,
        act="authorize_control",
        stance="recognized",
        authority_basis="observation",
        provenance_code="observed_effect",
        outcome="completed",
        command_kind="give",
        target_kind="anchor",
        anchor_kind="item",
        anchor_id=f"item-{index}",
        tick=tick,
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


def _snapshot() -> OrganizationSnapshot:
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version="organization-analysis.v1",
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
        candidates=(
            _candidate(ORG_A, (_operation(1), _operation(2, tick=4))),
            _candidate(ORG_B, (_operation(3, domain="storage"),)),
        ),
    )


def _published(
    tmp_path: Path,
) -> tuple[FilesystemOrganizationReader, str]:
    snapshot = _snapshot()
    publication_id = compute_organization_publication_id(snapshot)
    payload = encode_organization_snapshot(
        replace(snapshot, publication_id=publication_id)
    )
    publisher = FilesystemOrganizationPublisher(tmp_path)
    publisher.publish(
        OrganizationPublication(
            run_id=RUN,
            publication_id=publication_id,
            snapshot_digest=organization_digest(payload),
            payload=payload,
            generated_tick=9,
        )
    )
    return FilesystemOrganizationReader(tmp_path), publication_id


def test_operations_page_filters_by_domain_and_organization(
    tmp_path: Path,
) -> None:
    reader, publication_id = _published(tmp_path)
    page = reader.operations(RUN, publication_id, 0, 10)
    assert [row.operation_id for row in page.rows] == [
        "orgop-0000000000000001",
        "orgop-0000000000000003",
        "orgop-0000000000000002",
    ]
    assert all(type(row) is OrganizationOperationRecord for row in page.rows)

    storage = reader.operations(RUN, publication_id, 0, 10, domain="storage")
    assert [row.operation_id for row in storage.rows] == [
        "orgop-0000000000000003"
    ]

    owned = reader.operations(RUN, publication_id, 0, 10, organization_id=ORG_A)
    assert len(owned.rows) == 2

    unknown = f"org-{'f' * 16}"
    empty = reader.operations(RUN, publication_id, 0, 10, organization_id=unknown)
    assert empty.rows == ()


def test_summary_includes_operation_count(tmp_path: Path) -> None:
    reader, _ = _published(tmp_path)
    summary = reader.summary(RUN)
    assert summary is not None
    assert summary.operation_count == 3
    assert summary.candidate_count == 2


def test_cursor_is_bound_to_purpose_and_filters() -> None:
    assert "organization_operations" in ORGANIZATION_CURSOR_PURPOSES
    base = organization_query_fingerprint(
        RUN,
        f"org-edge-{'a' * 16}",
        "organization_operations",
        {"domain": None, "organization_id": None},
    )
    changed = organization_query_fingerprint(
        RUN,
        f"org-edge-{'a' * 16}",
        "organization_operations",
        {"domain": "storage", "organization_id": None},
    )
    assert base != changed
    cursor = OrganizationCursor(
        purpose="organization_operations",
        run_id=RUN,
        publication_id=f"org-edge-{'a' * 16}",
        snapshot_digest="b" * 64,
        offset=0,
        query_fingerprint=base,
    )
    assert cursor.purpose == "organization_operations"
    with pytest.raises(OrganizationArtifactError):
        OrganizationCursor(
            purpose="organization_membership",
            run_id=RUN,
            publication_id=f"org-edge-{'a' * 16}",
            snapshot_digest="b" * 64,
            offset=0,
            query_fingerprint=base,
        )


def test_page_limits_and_byte_budget_are_bounded() -> None:
    rows = tuple(_operation(index) for index in range(600))
    with pytest.raises(OrganizationArtifactError):
        select_organization_rows(rows, offset=0, limit=501, max_bytes=4 * 1024 * 1024)
    page = select_organization_rows(
        rows, offset=0, limit=500, max_bytes=4 * 1024 * 1024
    )
    assert len(page.rows) == 500
    assert page.truncated is True
    assert page.next_offset == 500

    tiny = select_organization_rows(rows, offset=0, limit=500, max_bytes=10)
    assert tiny.rows == ()
    assert tiny.truncated is True
    assert tiny.encoded_bytes == 0
