"""Organization snapshot DTO invariants and identity grammar."""

from __future__ import annotations

import pytest

from simulation.organization_models import (
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationLineageEdgeRecord,
    OrganizationMemberRecord,
    OrganizationSnapshot,
    OrganizationSnapshotRef,
    empty_organization_snapshot,
    require_organization_id,
    require_publication_id,
)
from tests.unit.organization_artifact_helpers import SECOND, example_snapshot

pytestmark = pytest.mark.unit


def test_identity_grammars_are_exact() -> None:
    assert require_organization_id("org-0123456789abcdef") == "org-0123456789abcdef"
    assert (
        require_publication_id("org-edge-0123456789abcdef")
        == "org-edge-0123456789abcdef"
    )
    for value in ("orgc-0123456789abcdef", "org-XYZ", "org-0123456789ABCDEF"):
        with pytest.raises(OrganizationArtifactError):
            require_organization_id(value)


def test_duplicate_candidate_is_rejected() -> None:
    snapshot = example_snapshot()
    with pytest.raises(OrganizationArtifactError):
        OrganizationSnapshot(
            schema_version=snapshot.schema_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            input_revision=snapshot.input_revision,
            generated_tick=snapshot.generated_tick,
            publication_id="",
            coverage=snapshot.coverage,
            candidates=(snapshot.candidates[0], snapshot.candidates[0]),
        )


def test_unknown_edge_endpoint_is_rejected() -> None:
    snapshot = example_snapshot()
    with pytest.raises(OrganizationArtifactError):
        OrganizationSnapshot(
            schema_version=snapshot.schema_version,
            policy_version=snapshot.policy_version,
            run_id=snapshot.run_id,
            input_revision=snapshot.input_revision,
            generated_tick=snapshot.generated_tick,
            publication_id="",
            coverage=snapshot.coverage,
            candidates=snapshot.candidates,
            edges=(
                OrganizationLineageEdgeRecord(
                    kind="continued",
                    tick=1,
                    from_id=SECOND,
                    to_id="org-aaaaaaaaaaaaaaaa",
                ),
            ),
        )


def test_coverage_rejects_impossible_ratios() -> None:
    with pytest.raises(OrganizationArtifactError):
        OrganizationCoverage(observed=3, expected=2, ratio=None)
    with pytest.raises(OrganizationArtifactError):
        OrganizationCoverage(observed=1, expected=2, ratio=0.9)
    assert OrganizationCoverage(observed=0, expected=0, ratio=None).ratio is None


def test_member_counts_are_derived_from_rows() -> None:
    snapshot = example_snapshot()
    candidate = snapshot.candidates[0]
    assert candidate.member_count == 2
    assert candidate.count("goal") if False else candidate.structural_channel_count == 2
    with pytest.raises(OrganizationArtifactError):
        OrganizationMemberRecord(
            member_id="body-ada",
            status="explicit",
            basis="self_identification",
            temporal_scope="ongoing",
            first_tick=9,
            last_tick=3,
            strength=0.5,
            owner_support_count=1,
        )


def test_empty_snapshot_is_valid_and_unpublished() -> None:
    snapshot = empty_organization_snapshot("run-1", "rev-1", 4)
    assert snapshot.candidates == ()
    assert snapshot.publication_id == ""
    assert snapshot.provenance_code == "ok"


def test_snapshot_ref_binds_publication_and_digest() -> None:
    ref = OrganizationSnapshotRef(
        publication_id="org-edge-0123456789abcdef",
        snapshot_digest="a" * 64,
        schema_version="organization-snapshot-v1",
        run_id="run-1",
        generated_tick=4,
    )
    assert ref.run_id == "run-1"
    with pytest.raises(OrganizationArtifactError):
        OrganizationSnapshotRef(
            publication_id="org-0123456789abcdef",
            snapshot_digest="a" * 64,
            schema_version="organization-snapshot-v1",
            run_id="run-1",
            generated_tick=4,
        )


def test_candidate_rejects_wrong_status() -> None:
    with pytest.raises(OrganizationArtifactError):
        OrganizationCandidateRecord(
            organization_id=SECOND,
            creation_tick=0,
            first_tick=0,
            last_tick=1,
            status="government",
            temporal_scope="ongoing",
            self_identified=True,
        )
