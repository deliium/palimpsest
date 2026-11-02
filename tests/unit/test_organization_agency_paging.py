"""Collective-agency paging and cursor-digest plumbing."""

from __future__ import annotations

from typing import Any, cast

import pytest

from simulation.organization_codec import encode_organization_value
from simulation.organization_models import (
    OrganizationArtifactError,
    OrganizationCoverage,
)
from simulation.organization_paging import (
    row_encoded_bytes,
    select_organization_collective_decision_rows,
)
from simulation.organization_ports import (
    ORGANIZATION_CURSOR_PURPOSES,
    OrganizationCursor,
    OrganizationSummary,
    organization_cursor_matches,
    organization_query_fingerprint,
)
from tests.unit.test_organization_agency_snapshot import (
    DECISION,
    ORG,
    _decision,
    _implementation,
)

pytestmark = pytest.mark.unit

DIGEST = "a" * 64


def test_cursor_purposes_are_exactly_six() -> None:
    assert ORGANIZATION_CURSOR_PURPOSES == (
        "organization_summary",
        "organization_candidates",
        "organization_candidate",
        "organization_lineage",
        "organization_operations",
        "organization_collective_agency",
    )


def test_summary_requires_a_real_digest() -> None:
    summary = OrganizationSummary(
        run_id="run-agency-paging",
        publication_id=f"org-edge-{'b' * 16}",
        schema_version="organization-snapshot-v3",
        generated_tick=10,
        candidate_count=1,
        edge_count=0,
        window_count=1,
        coverage=OrganizationCoverage(observed=1, expected=1, ratio=1.0),
        provenance_code="ok",
        snapshot_digest=DIGEST,
        collective_decision_count=1,
    )
    assert summary.snapshot_digest == DIGEST
    with pytest.raises(OrganizationArtifactError):
        OrganizationSummary(
            run_id="run-agency-paging",
            publication_id=f"org-edge-{'b' * 16}",
            schema_version="organization-snapshot-v3",
            generated_tick=10,
            candidate_count=1,
            edge_count=0,
            window_count=1,
            coverage=OrganizationCoverage(observed=1, expected=1, ratio=1.0),
            provenance_code="ok",
            snapshot_digest="",
        )


def _summary() -> OrganizationSummary:
    return OrganizationSummary(
        run_id="run-agency-paging",
        publication_id=f"org-edge-{'b' * 16}",
        schema_version="organization-snapshot-v3",
        generated_tick=10,
        candidate_count=1,
        edge_count=0,
        window_count=1,
        coverage=OrganizationCoverage(observed=1, expected=1, ratio=1.0),
        provenance_code="ok",
        snapshot_digest=DIGEST,
    )


def test_cursor_matches_only_the_committed_digest() -> None:
    summary = _summary()
    fingerprint = organization_query_fingerprint(
        summary.run_id, summary.publication_id, "organization_collective_agency"
    )
    cursor = OrganizationCursor(
        purpose="organization_collective_agency",
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest=DIGEST,
        offset=0,
        query_fingerprint=fingerprint,
    )
    assert organization_cursor_matches(
        cursor, summary, "organization_collective_agency", fingerprint
    )
    empty = OrganizationCursor(
        purpose="organization_collective_agency",
        run_id=summary.run_id,
        publication_id=summary.publication_id,
        snapshot_digest="0" * 64,
        offset=0,
        query_fingerprint=fingerprint,
    )
    assert not organization_cursor_matches(
        empty, summary, "organization_collective_agency", fingerprint
    )


def test_decision_paging_keeps_nested_implementations_whole() -> None:
    rows = tuple(
        _decision(
            decision_id=f"orgcpd-{index:016x}",
            implementations=(
                _implementation(
                    implementation_id=f"orgcpi-{index:016x}",
                    decision_id=f"orgcpd-{index:016x}",
                    actor_ref=f"{index + 1:016x}",
                ),
            ),
        )
        for index in range(3)
    )
    selection = select_organization_collective_decision_rows(
        rows, offset=0, limit=2, max_bytes=10_000
    )
    assert len(selection.rows) == 2
    assert selection.next_offset == 2
    assert selection.truncated
    assert all(
        len(cast(Any, row).implementations) == 1 for row in selection.rows
    )


def test_byte_guard_never_splits_a_decision() -> None:
    rows = (_decision(),)
    size = row_encoded_bytes(rows[0])
    selection = select_organization_collective_decision_rows(
        rows, offset=0, limit=1, max_bytes=size
    )
    assert len(selection.rows) == 1
    empty = select_organization_collective_decision_rows(
        rows, offset=0, limit=1, max_bytes=size - 1
    )
    assert empty.rows == ()
    assert empty.truncated


def test_row_bytes_use_the_canonical_encode_path() -> None:
    row = _decision()
    assert row_encoded_bytes(row) == (
        len(
            encode_organization_value(
                {
                    "decision_id": row.decision_id,
                    "organization_id": row.organization_id,
                    "proposal_ref": row.proposal_ref,
                    "revision": row.revision,
                    "procedure_ref": row.procedure_ref,
                    "recognition": row.recognition,
                    "authority_basis": row.authority_basis,
                    "support_count": row.support_count,
                    "oppose_count": row.oppose_count,
                    "abstain_count": row.abstain_count,
                    "contest_count": row.contest_count,
                    "implementation_mode": row.implementation_mode,
                    "effect": row.effect,
                    "target_kind": row.target_kind,
                    "target_ref": row.target_ref,
                    "decided_tick": row.decided_tick,
                    "window_end_tick": row.window_end_tick,
                    "implementation_status": row.implementation_status,
                    "provenance_code": row.provenance_code,
                    "resolved": row.resolved,
                    "implementations": [
                        {
                            "implementation_id": row.implementations[
                                0
                            ].implementation_id,
                            "decision_id": row.implementations[0].decision_id,
                            "actor_ref": row.implementations[0].actor_ref,
                            "status": row.implementations[0].status,
                            "effect": row.implementations[0].effect,
                            "observed_tick": row.implementations[0].observed_tick,
                            "provenance_code": (row.implementations[0].provenance_code),
                            "resolved": row.implementations[0].resolved,
                        }
                    ],
                }
            )
        )
    )
    assert ORG.endswith("a" * 16)
    assert DECISION.startswith("orgcpd-")
