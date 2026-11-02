"""Organization read/publication ports, cursors, and fingerprints."""

from __future__ import annotations

import pytest

from simulation.organization_models import OrganizationArtifactError
from simulation.organization_ports import (
    ORGANIZATION_CURSOR_PURPOSES,
    OrganizationCursor,
    OrganizationReadSession,
    organization_query_fingerprint,
    require_known_organization,
)
from tests.unit.organization_artifact_helpers import FIRST, example_snapshot

pytestmark = pytest.mark.unit


def test_cursor_purposes_are_closed() -> None:
    assert ORGANIZATION_CURSOR_PURPOSES == (
        "organization_summary",
        "organization_candidates",
        "organization_candidate",
        "organization_lineage",
        "organization_operations",
        "organization_collective_agency",
    )
    with pytest.raises(OrganizationArtifactError):
        OrganizationCursor(
            purpose="organization_everything",
            run_id="run-1",
            publication_id="org-edge-0123456789abcdef",
            snapshot_digest="a" * 64,
            offset=0,
            query_fingerprint="b" * 64,
        )


def test_fingerprint_binds_purpose_run_publication_and_filters() -> None:
    base = organization_query_fingerprint(
        "run-1",
        "org-edge-0123456789abcdef",
        "organization_candidates",
        {"status": "partial"},
    )
    assert len(base) == 64
    assert base == organization_query_fingerprint(
        "run-1",
        "org-edge-0123456789abcdef",
        "organization_candidates",
        {"status": "partial"},
    )
    for changed in (
        organization_query_fingerprint(
            "run-2",
            "org-edge-0123456789abcdef",
            "organization_candidates",
            {"status": "partial"},
        ),
        organization_query_fingerprint(
            "run-1",
            "org-edge-fedcba9876543210",
            "organization_candidates",
            {"status": "partial"},
        ),
        organization_query_fingerprint(
            "run-1",
            "org-edge-0123456789abcdef",
            "organization_lineage",
            {"status": "partial"},
        ),
        organization_query_fingerprint(
            "run-1",
            "org-edge-0123456789abcdef",
            "organization_candidates",
            {"status": "recognized"},
        ),
    ):
        assert changed != base


def test_read_session_enforces_the_response_budget() -> None:
    session = OrganizationReadSession(max_bytes=10)
    session.charge(4)
    session.charge(6)
    with pytest.raises(OrganizationArtifactError) as excinfo:
        session.charge(1)
    assert excinfo.value.code == "organization_response_limit"


def test_unknown_candidate_is_rejected() -> None:
    snapshot = example_snapshot()
    assert require_known_organization(snapshot, FIRST).organization_id == FIRST
    with pytest.raises(OrganizationArtifactError) as excinfo:
        require_known_organization(snapshot, "org-aaaaaaaaaaaaaaaa")
    assert excinfo.value.code == "organization_unknown_candidate"
