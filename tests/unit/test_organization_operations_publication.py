"""Completed-run operation composition: v2 artifacts, ids, and receipts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from analysis import (
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationTemporalScope,
    OrganizationWindowResult,
    assign_organization_identities,
    derive_organization_lineage,
)
from analysis.organization_operations import (
    OrganizationAdmissionRow,
    OrganizationControlRow,
    OrganizationOperationHarvestRows,
    OrganizationOperationOwnerRow,
)
from experiments.organization_harvest import OrganizationHarvest
from experiments.organization_publication import (
    build_organization_harvest_result,
    organization_publication_document,
)
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
)
from simulation.runner_models import RunnerStopReasonCode

pytestmark = pytest.mark.unit

RUN = "run-operations"
OWNER = "owner-1"
ORG = f"orgc-{'a' * 16}"
MEMBERS = ("member-a", "member-b")

pytestmark = pytest.mark.unit


def _candidate() -> OrganizationCandidate:
    return OrganizationCandidate(
        candidate_key="w0",
        window_index=0,
        member_ids=MEMBERS,
        member_claims=(),
        role_anchor_ids=(),
        goal_anchor_ids=(),
        resource_anchor_ids=("repository-beta",),
        procedure_anchor_ids=(),
        record_anchor_ids=(),
        commitment_ids=(),
        identity_tokens=(),
        status=OrganizationCandidateStatus.PARTIAL,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        self_identified=False,
        owner_ids=(OWNER,),
        first_tick=0,
        last_tick=9,
    )


def _assignment():
    detection = OrganizationDetectionResult(
        windows=(
            OrganizationWindowResult(
                window_index=0,
                start_tick=0,
                end_tick=9,
                candidate_keys=("w0",),
                lane_presence=(("resources", True),),
            ),
        ),
        candidates=(_candidate(),),
        coverage=OrganizationCoverage.of(1, 7),
    )
    return assign_organization_identities(detection)


def _owner_row(*, admissions: tuple[OrganizationAdmissionRow, ...] = ()) -> (
    OrganizationOperationHarvestRows
):
    return OrganizationOperationHarvestRows(
        owner=OrganizationOperationOwnerRow(
            owner_id=OWNER,
            concept_count=1,
            notices=(),
            policy_version="organization-operations.v1",
            admission_count=len(admissions),
        ),
        admissions=admissions,
        concept_ticks=((ORG, 9),),
    )


def _admission(
    member: str = MEMBERS[0],
    *,
    support: int = 1,
    contest: int = 0,
    stance: str = "admitted",
) -> OrganizationAdmissionRow:
    return OrganizationAdmissionRow(
        organization_id=ORG,
        member_id=member,
        stance=stance,
        authority_basis="self_authored",
        temporal_scope="ongoing",
        first_tick=1,
        last_tick=9,
        owner_support_count=support,
        contest_count=contest,
    )


def _control(
    *, anchor_kind: str = "resource", anchor_id: str | None = "repository-beta"
) -> OrganizationControlRow:
    return OrganizationControlRow(
        organization_id=ORG,
        domain="resource_control",
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        stance="recognized",
        authority_basis="role_belief",
        legitimacy_doctrine="role_trusteeship",
        first_tick=1,
        last_tick=9,
        owner_support_count=2,
        contest_count=0,
    )


def _harvest(rows: OrganizationOperationHarvestRows) -> OrganizationHarvest:
    assignment = _assignment()
    analysis = derive_organization_lineage(assignment)
    return OrganizationHarvest(
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        owner_rows=(),
        operation_rows=(rows,),
        assignment=assignment,
        analysis=analysis,
    )


def test_completed_run_publishes_v2_with_operation_counts() -> None:
    rows = _owner_row(admissions=(_admission(),))
    rows = replace(rows, controls=(_control(),), concept_ticks=((ORG, 9),))
    result = build_organization_harvest_result(_harvest(rows))
    assert result.snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert result.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert result.operation_count == 2
    assert result.snapshot.candidates[0].operation_count == 2
    document = organization_publication_document(result)
    assert document["operation_count"] == 2
    assert document["schema_version"] == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION


def test_publication_bytes_have_no_owner_local_ids() -> None:
    rows = replace(
        _owner_row(admissions=(_admission(),)),
        controls=(_control(),),
    )
    result = build_organization_harvest_result(_harvest(rows))
    payload = result.snapshot_bytes.decode()
    for token in ("orgc-", "orgd-", "orga-", "owner_id", "office_id", "owner-1"):
        assert token not in payload


def test_operation_ids_are_stable_and_content_sensitive() -> None:
    base = replace(_owner_row(admissions=(_admission(),)), controls=(_control(),))
    first = build_organization_harvest_result(_harvest(base))
    second = build_organization_harvest_result(_harvest(base))
    assert first.publication_id == second.publication_id
    ids = [
        operation.operation_id
        for operation in first.snapshot.candidates[0].operations
    ]
    assert all(item.startswith("orgop-") for item in ids)

    changed = replace(
        _owner_row(admissions=(_admission(support=5),)),
        controls=(_control(),),
    )
    third = build_organization_harvest_result(_harvest(changed))
    assert third.publication_id != first.publication_id
    assert [
        operation.operation_id for operation in third.snapshot.candidates[0].operations
    ] != ids


def test_records_differing_only_in_support_stay_distinct() -> None:
    rows = replace(
        _owner_row(
            admissions=(
                _admission(support=1),
                _admission(stance="claimed", support=2),
            )
        ),
    )
    result = build_organization_harvest_result(_harvest(rows))
    operations = result.snapshot.candidates[0].operations
    assert len(operations) == 2
    assert len({operation.operation_id for operation in operations}) == 2


def test_one_candidate_truncates_at_64_with_explicit_provenance() -> None:
    members = tuple(f"member-{index:02d}" for index in range(65))
    rows = replace(
        _owner_row(
            admissions=tuple(
                _admission(members[0], support=index) for index in range(65)
            )
        ),
    )
    candidate = replace(_candidate(), member_ids=members)
    detection = OrganizationDetectionResult(
        windows=(
            OrganizationWindowResult(
                window_index=0,
                start_tick=0,
                end_tick=9,
                candidate_keys=("w0",),
                lane_presence=(("resources", True),),
            ),
        ),
        candidates=(candidate,),
        coverage=OrganizationCoverage.of(1, 7),
    )
    assignment = assign_organization_identities(detection)
    harvest = OrganizationHarvest(
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        owner_rows=(),
        operation_rows=(rows,),
        assignment=assignment,
        analysis=derive_organization_lineage(assignment),
    )
    result = build_organization_harvest_result(harvest)
    assert result.operation_count == 64
    assert result.provenance_code == "operations_truncated"
    assert result.snapshot.provenance_code == "operations_truncated"


def test_unresolved_anchor_publishes_without_anchor_id() -> None:
    rows = replace(
        _owner_row(admissions=(_admission(),)),
        controls=(
            _control(anchor_kind="unknown", anchor_id=None),
        ),
    )
    result = build_organization_harvest_result(_harvest(rows))
    operation = next(
        item
        for item in result.snapshot.candidates[0].operations
        if item.domain == "resource_control"
    )
    assert operation.anchor_kind == "unknown"
    assert operation.anchor_id is None
    assert operation.resolved is False


def test_operation_ids_do_not_collapse_on_anchor_only_difference() -> None:
    rows = replace(
        _owner_row(),
        controls=(
            _control(anchor_id="repository-beta"),
            _control(anchor_id="repository-gamma"),
        ),
    )
    result = build_organization_harvest_result(_harvest(rows))
    operations = result.snapshot.candidates[0].operations
    assert len(operations) == 2
    assert len({operation.operation_id for operation in operations}) == 2


def test_incomplete_run_stays_unavailable(tmp_path) -> None:
    from types import SimpleNamespace

    from research_runner.organization_composition import (
        OrganizationProducerOptions,
        publish_organization_harvest,
    )

    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=RunnerStopReasonCode.COGNITION_FAILURE),
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "unavailable"
    assert receipt["reason_code"] == "organization_run_incomplete"
    assert not (tmp_path / RUN).exists()


def test_storage_failure_changes_only_the_receipt(tmp_path) -> None:
    from types import SimpleNamespace

    from research_runner.organization_composition import (
        OrganizationProducerOptions,
        publish_organization_harvest,
    )

    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=RunnerStopReasonCode.MAX_TICKS),
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        options=OrganizationProducerOptions(root=blocked),
    )
    assert receipt["status"] == "failed"
    assert set(receipt) == {"status", "reason_code"}


def test_empty_completed_run_publishes_v2_receipt(tmp_path) -> None:
    from types import SimpleNamespace

    from research_runner.organization_composition import (
        OrganizationProducerOptions,
        publish_organization_harvest,
    )

    receipt = publish_organization_harvest(
        SimpleNamespace(stop_reason=RunnerStopReasonCode.MAX_TICKS),
        run_id=RUN,
        input_revision="rev-1",
        generated_tick=9,
        options=OrganizationProducerOptions(root=tmp_path),
    )
    assert receipt["status"] == "published"
    assert receipt["schema_version"] == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert receipt["operation_count"] == 0
    assert "orgc-" not in repr(receipt)
