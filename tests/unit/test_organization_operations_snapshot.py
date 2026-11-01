"""Organization snapshot v2: operations, caps, and v1 compatibility."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from simulation import (
    MAX_CANDIDATE_OPERATIONS,
    MAX_SNAPSHOT_OPERATIONS,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationObjectiveRow,
    OrganizationOperationRecord,
    OrganizationSnapshot,
    OrganizationWindowRecord,
    compute_organization_publication_id,
    decode_organization_snapshot,
    empty_organization_snapshot,
    encode_organization_snapshot,
    upgrade_organization_snapshot,
)
from tests.unit.organization_artifact_helpers import example_snapshot

pytestmark = pytest.mark.unit


def _operation(index: int, *, tick: int = 3) -> OrganizationOperationRecord:
    return OrganizationOperationRecord(
        operation_id=f"orgop-{index:016x}",
        domain="resource_control",
        act="authorize_control",
        stance="recognized",
        authority_basis="role_belief",
        provenance_code="role_authorized",
        outcome="completed",
        command_kind="give",
        target_kind="anchor",
        anchor_kind="item",
        anchor_id="item-1",
        tick=tick,
        first_tick=1,
        last_tick=5,
        support_count=2,
        contest_count=0,
        resolved=True,
    )


def _v2_snapshot(
    *, operations: tuple[OrganizationOperationRecord, ...] = ()
) -> OrganizationSnapshot:
    snapshot = example_snapshot()
    candidate = replace(snapshot.candidates[0], operations=operations)
    return replace(
        snapshot,
        candidates=(candidate, snapshot.candidates[1]),
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    )


def _v1_snapshot() -> OrganizationSnapshot:
    return replace(
        example_snapshot(), schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1
    )


def test_v2_round_trip_is_canonical_and_byte_identical() -> None:
    snapshot = _v2_snapshot(operations=(_operation(1), _operation(2, tick=4)))
    payload = encode_organization_snapshot(snapshot)
    decoded = decode_organization_snapshot(payload)
    assert decoded == snapshot
    assert encode_organization_snapshot(decoded) == payload
    assert payload.endswith(b"\n")
    assert payload.count(b"\n") == 1
    assert b'"operations"' in payload


def test_v1_artifacts_remain_decodable_and_byte_identical() -> None:
    snapshot = _v1_snapshot()
    payload = encode_organization_snapshot(snapshot)
    assert b"operations" not in payload
    decoded = decode_organization_snapshot(payload)
    assert decoded.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1
    assert decoded.candidates[0].operations == ()
    assert encode_organization_snapshot(decoded) == payload


def test_upgrade_lifts_v1_with_empty_operations() -> None:
    snapshot = _v1_snapshot()
    upgraded = upgrade_organization_snapshot(snapshot)
    assert upgraded.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert upgraded is not snapshot
    assert snapshot.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1
    for candidate in upgraded.candidates:
        assert candidate.operations == ()
    for window in upgraded.windows:
        assert window.operation_count == 0
    for row in upgraded.objective_rows:
        assert row.operation_action_count == 0
    assert upgrade_organization_snapshot(upgraded) is upgraded


def test_exact_v2_key_sets_reject_extra_and_missing_fields() -> None:
    payload = encode_organization_snapshot(_v2_snapshot(operations=(_operation(1),)))
    data = json.loads(payload)

    extra = json.loads(payload)
    extra["candidates"][0]["operations"][0]["extra"] = 1
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(extra).encode() + b"\n")

    missing = json.loads(payload)
    missing["candidates"][0].pop("operations")
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(missing).encode() + b"\n")

    missing_window = json.loads(payload)
    missing_window["windows"][0].pop("operation_count")
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(missing_window).encode() + b"\n")

    assert data["schema_version"] == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION


def test_candidate_operation_cap_is_enforced() -> None:
    assert MAX_CANDIDATE_OPERATIONS == 64
    operations = tuple(_operation(index) for index in range(65))
    with pytest.raises(OrganizationArtifactError) as excinfo:
        _v2_snapshot(operations=operations)
    assert excinfo.value.code == "organization_size_limit"


def test_snapshot_operation_cap_is_enforced() -> None:
    assert MAX_SNAPSHOT_OPERATIONS == 4096
    candidates: list[OrganizationCandidateRecord] = []
    next_index = 0
    while next_index < MAX_SNAPSHOT_OPERATIONS + 1:
        chunk = tuple(
            _operation(index)
            for index in range(
                next_index,
                min(next_index + MAX_CANDIDATE_OPERATIONS, MAX_SNAPSHOT_OPERATIONS + 1),
            )
        )
        candidates.append(
            OrganizationCandidateRecord(
                organization_id=f"org-{len(candidates):016x}",
                creation_tick=0,
                first_tick=0,
                last_tick=9,
                status="partial",
                temporal_scope="ongoing",
                self_identified=False,
                operations=chunk,
            )
        )
        next_index += len(chunk)
    with pytest.raises(OrganizationArtifactError) as excinfo:
        OrganizationSnapshot(
            schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
            policy_version=empty_organization_snapshot("r", "v", 0).policy_version,
            run_id="run-1",
            input_revision="rev-1",
            generated_tick=9,
            publication_id="",
            coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
            candidates=tuple(candidates),
        )
    assert excinfo.value.code == "organization_size_limit"


def test_duplicate_operation_ids_fail_closed() -> None:
    duplicated = (_operation(1), _operation(1))
    with pytest.raises(OrganizationArtifactError) as excinfo:
        _v2_snapshot(operations=duplicated)
    assert excinfo.value.code == "organization_duplicate_operation"


def test_encoded_artifact_has_no_owner_local_ids() -> None:
    payload = encode_organization_snapshot(
        _v2_snapshot(operations=(_operation(1),))
    ).decode()
    for token in ("orgc-", "orgd-", "orga-", "owner_id", "office_id", "target_id"):
        assert token not in payload


def test_publication_id_differs_between_v1_and_v2() -> None:
    v1 = _v1_snapshot()
    v2 = upgrade_organization_snapshot(v1)
    assert compute_organization_publication_id(v1) == (
        compute_organization_publication_id(v1)
    )
    assert compute_organization_publication_id(v2) == (
        compute_organization_publication_id(v2)
    )
    assert compute_organization_publication_id(v1) != (
        compute_organization_publication_id(v2)
    )


def test_unknown_schema_fails_closed() -> None:
    payload = encode_organization_snapshot(_v2_snapshot())
    data = json.loads(payload)
    data["schema_version"] = "organization-snapshot-v9"
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(json.dumps(data).encode() + b"\n")


def test_operation_record_rejects_owner_local_anchor_kinds() -> None:
    with pytest.raises(OrganizationArtifactError):
        replace(_operation(1), anchor_kind="owner_local", anchor_id="orgc-abc")
    with pytest.raises(OrganizationArtifactError):
        replace(_operation(1), anchor_kind="unknown", anchor_id="item-1")
    assert replace(
        _operation(1), anchor_kind="unknown", anchor_id=None, resolved=False
    ).resolved is False


def test_window_and_objective_operation_counts_round_trip() -> None:
    snapshot = _v2_snapshot(operations=(_operation(1), _operation(2, tick=4)))
    window = OrganizationWindowRecord(
        window_index=0,
        start_tick=0,
        end_tick=9,
        candidate_ids=(snapshot.candidates[0].organization_id,),
        member_count=2,
        overlap_member_count=0,
        lane_presence=(("resources", True),),
        operation_count=2,
        contested_operation_count=1,
    )
    row = OrganizationObjectiveRow(
        window_index=0,
        tick=0,
        member_count=2,
        role_count=1,
        goal_count=0,
        resource_count=1,
        procedure_count=0,
        record_count=0,
        commitment_count=0,
        identity_count=0,
        resolved_anchor_count=1,
        unresolved_anchor_count=0,
        operation_action_count=1,
    )
    updated = replace(snapshot, windows=(window,), objective_rows=(row,))
    decoded = decode_organization_snapshot(
        encode_organization_snapshot(updated)
    )
    assert decoded.windows[0].operation_count == 2
    assert decoded.windows[0].contested_operation_count == 1
    assert decoded.objective_rows[0].operation_action_count == 1
