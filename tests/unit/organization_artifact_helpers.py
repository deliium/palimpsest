"""Shared representative organization artifacts for unit tests."""

from __future__ import annotations

from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_POLICY_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationLineageEdgeRecord,
    OrganizationMemberRecord,
    OrganizationObjectiveRow,
    OrganizationSnapshot,
    OrganizationStructuralRecord,
    OrganizationWindowRecord,
)

FIRST = "org-0123456789abcdef"
SECOND = "org-fedcba9876543210"


def example_snapshot(publication_id: str = "") -> OrganizationSnapshot:
    first = OrganizationCandidateRecord(
        organization_id=FIRST,
        creation_tick=3,
        first_tick=3,
        last_tick=9,
        status="recognized",
        temporal_scope="ongoing",
        self_identified=True,
        members=(
            OrganizationMemberRecord(
                member_id="body-ada",
                status="explicit",
                basis="self_identification",
                temporal_scope="ongoing",
                first_tick=3,
                last_tick=9,
                strength=0.9,
                owner_support_count=1,
            ),
            OrganizationMemberRecord(
                member_id="body-ben",
                status="perceived",
                basis="participation",
                temporal_scope="ongoing",
                first_tick=3,
                last_tick=9,
                strength=0.5,
                owner_support_count=2,
            ),
        ),
        structure=(
            OrganizationStructuralRecord(
                kind="goal",
                anchor_id="project-1",
                status="recognized",
                first_tick=3,
                last_tick=9,
            ),
            OrganizationStructuralRecord(
                kind="role",
                anchor_id="office-1",
                status="recognized",
                first_tick=3,
                last_tick=9,
            ),
        ),
        window_indexes=(0,),
    )
    second = OrganizationCandidateRecord(
        organization_id=SECOND,
        creation_tick=9,
        first_tick=9,
        last_tick=9,
        status="partial",
        temporal_scope="ongoing",
        self_identified=False,
        members=(),
        structure=(),
        window_indexes=(0,),
    )
    return OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
        run_id="run-organization-1",
        input_revision="rev-1",
        generated_tick=9,
        publication_id=publication_id,
        coverage=OrganizationCoverage(observed=4, expected=7, ratio=None),
        windows=(
            OrganizationWindowRecord(
                window_index=0,
                start_tick=0,
                end_tick=99,
                candidate_ids=(FIRST, SECOND),
                member_count=2,
                overlap_member_count=0,
                lane_presence=(("goals", True), ("roles", True)),
            ),
        ),
        candidates=(first, second),
        edges=(
            OrganizationLineageEdgeRecord(
                kind="emerged",
                tick=0,
                from_id=None,
                to_id=FIRST,
                jaccard=None,
                containment=None,
            ),
        ),
        objective_rows=(
            OrganizationObjectiveRow(
                window_index=0,
                tick=0,
                member_count=2,
                role_count=1,
                goal_count=1,
                resource_count=0,
                procedure_count=0,
                record_count=0,
                commitment_count=0,
                identity_count=1,
                resolved_anchor_count=2,
                unresolved_anchor_count=0,
            ),
        ),
        provenance_code="ok",
    )
