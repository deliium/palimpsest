"""Canonical organization snapshot v3 with collective-agency records."""

from __future__ import annotations

from typing import Any

import pytest

from simulation.organization_codec import (
    decode_organization_snapshot,
    encode_organization_snapshot,
)
from simulation.organization_models import (
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
    SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCollectiveDecisionRecord,
    OrganizationCoverage,
    OrganizationImplementationRecord,
    OrganizationObjectiveRow,
    OrganizationSnapshot,
    OrganizationWindowRecord,
    upgrade_organization_snapshot,
)

pytestmark = pytest.mark.unit

ORG = f"org-{'a' * 16}"
DECISION = f"orgcpd-{'b' * 16}"
IMPLEMENTATION = f"orgcpi-{'c' * 16}"


def _implementation(
    *,
    implementation_id: str = IMPLEMENTATION,
    decision_id: str = DECISION,
    actor_ref: str = "d" * 16,
    status: str = "implemented",
) -> OrganizationImplementationRecord:
    return OrganizationImplementationRecord(
        implementation_id=implementation_id,
        decision_id=decision_id,
        actor_ref=actor_ref,
        status=status,
        effect="give",
        observed_tick=7,
        provenance_code="observed_effect",
        resolved=True,
    )


def _decision(**overrides: Any) -> OrganizationCollectiveDecisionRecord:
    values: dict[str, Any] = {
        "decision_id": DECISION,
        "organization_id": ORG,
        "proposal_ref": "e" * 16,
        "revision": 1,
        "procedure_ref": "f" * 16,
        "recognition": "recognized",
        "authority_basis": "procedure_belief",
        "support_count": 1,
        "oppose_count": 0,
        "abstain_count": 0,
        "contest_count": 0,
        "implementation_mode": "physical",
        "effect": "give",
        "target_kind": "item",
        "target_ref": "0" * 16,
        "decided_tick": 6,
        "window_end_tick": 20,
        "implementation_status": "implemented",
        "provenance_code": "observed_effect",
        "resolved": True,
        "implementations": (_implementation(),),
    }
    values.update(overrides)
    return OrganizationCollectiveDecisionRecord(**values)


def _snapshot(
    schema: str = ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
) -> OrganizationSnapshot:
    decision = _decision()
    candidate = OrganizationCandidateRecord(
        organization_id=ORG,
        creation_tick=1,
        first_tick=1,
        last_tick=10,
        status="recognized",
        temporal_scope="ongoing",
        self_identified=True,
        window_indexes=(0,),
        collective_decisions=(decision,),
        collective_proposal_count=1,
        collective_support_count=1,
        collective_decision_count=1,
        collective_implementation_count=1,
    )
    window = OrganizationWindowRecord(
        window_index=0,
        start_tick=1,
        end_tick=10,
        candidate_ids=(ORG,),
        member_count=2,
        overlap_member_count=0,
        collective_decision_count=1,
        collective_implementation_count=1,
    )
    row = OrganizationObjectiveRow(
        window_index=0,
        tick=1,
        member_count=2,
        role_count=0,
        goal_count=0,
        resource_count=0,
        procedure_count=0,
        record_count=0,
        commitment_count=0,
        identity_count=0,
        resolved_anchor_count=0,
        unresolved_anchor_count=0,
        collective_decision_count=1,
        collective_implementation_count=1,
    )
    return OrganizationSnapshot(
        schema_version=schema,
        policy_version="organization-analysis.v1",
        run_id="run-agency-snapshot",
        input_revision="revision-1",
        generated_tick=10,
        publication_id="",
        coverage=OrganizationCoverage(observed=1, expected=1, ratio=1.0),
        windows=(window,),
        candidates=(candidate,),
        objective_rows=(row,),
    )


def test_supported_schemas_are_v1_v2_v3() -> None:
    assert SUPPORTED_ORGANIZATION_SNAPSHOT_SCHEMAS == (
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
        ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    )
    assert ORGANIZATION_SNAPSHOT_SCHEMA_VERSION == "organization-snapshot-v3"


def test_v3_round_trips_canonically() -> None:
    snapshot = _snapshot()
    payload = encode_organization_snapshot(snapshot)
    decoded = decode_organization_snapshot(payload)
    assert decoded == snapshot
    assert encode_organization_snapshot(decoded) == payload
    assert decoded.candidates[0].collective_decisions[0].decision_id == DECISION


def test_v2_still_round_trips() -> None:
    snapshot = _snapshot(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2)
    # v2 cannot carry v3-only fields.
    candidate = snapshot.candidates[0]
    bare = OrganizationCandidateRecord(
        organization_id=candidate.organization_id,
        creation_tick=1,
        first_tick=1,
        last_tick=10,
        status="recognized",
        temporal_scope="ongoing",
        self_identified=True,
        window_indexes=(0,),
    )
    snapshot = OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2,
        policy_version=snapshot.policy_version,
        run_id=snapshot.run_id,
        input_revision=snapshot.input_revision,
        generated_tick=10,
        publication_id="",
        coverage=snapshot.coverage,
        windows=(
            OrganizationWindowRecord(
                window_index=0,
                start_tick=1,
                end_tick=10,
                candidate_ids=(ORG,),
                member_count=2,
                overlap_member_count=0,
            ),
        ),
        candidates=(bare,),
        objective_rows=(
            OrganizationObjectiveRow(
                window_index=0,
                tick=1,
                member_count=2,
                role_count=0,
                goal_count=0,
                resource_count=0,
                procedure_count=0,
                record_count=0,
                commitment_count=0,
                identity_count=0,
                resolved_anchor_count=0,
                unresolved_anchor_count=0,
            ),
        ),
    )
    payload = encode_organization_snapshot(snapshot)
    assert decode_organization_snapshot(payload) == snapshot
    assert (
        encode_organization_snapshot(decode_organization_snapshot(payload)) == payload
    )


def test_upgrade_lifts_v1_and_v2_to_v3() -> None:
    upgraded = upgrade_organization_snapshot(
        _snapshot(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2)
    )
    assert upgraded.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert (
        upgraded.candidates
        == _snapshot(ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V2).candidates
    )


def test_unknown_schema_fails_closed() -> None:
    with pytest.raises(OrganizationArtifactError):
        OrganizationSnapshot(
            schema_version="organization-snapshot-v9",
            policy_version="organization-analysis.v1",
            run_id="run-agency-snapshot",
            input_revision="revision-1",
            generated_tick=10,
            publication_id="",
            coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
        )


def test_orphan_implementation_fails_closed() -> None:
    with pytest.raises(OrganizationArtifactError):
        _decision(implementations=(_implementation(decision_id=f"orgcpd-{'9' * 16}"),))


def test_caps_and_raw_ids_fail_closed() -> None:
    with pytest.raises(OrganizationArtifactError):
        _decision(
            implementations=tuple(
                _implementation(
                    implementation_id=f"orgcpi-{index:016x}",
                    actor_ref=f"{index:016x}",
                )
                for index in range(33)
            )
        )
    with pytest.raises(OrganizationArtifactError):
        _implementation(actor_ref="body-agent-1")


def test_missing_or_extra_candidate_keys_fail_closed() -> None:
    from simulation.organization_codec import (
        decode_organization_value,
        encode_organization_value,
    )

    payload = encode_organization_snapshot(_snapshot())
    decoded = decode_organization_value(payload)
    assert isinstance(decoded, dict)
    candidate = dict(decoded["candidates"][0])
    candidate.pop("collective_decisions")
    broken = dict(decoded)
    broken["candidates"] = [candidate]
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(encode_organization_value(broken))

    extra = dict(decoded["candidates"][0])
    extra["unexpected"] = 1
    broken_extra = dict(decoded)
    broken_extra["candidates"] = [extra]
    with pytest.raises(OrganizationArtifactError):
        decode_organization_snapshot(encode_organization_value(broken_extra))


def test_owner_local_token_in_a_published_decision_fails_closed() -> None:
    with pytest.raises(OrganizationArtifactError):
        _decision(proposal_ref="orgp-0000000000000001")


def test_candidate_decision_cap_is_enforced() -> None:
    from simulation.organization_models import (
        MAX_CANDIDATE_COLLECTIVE_DECISIONS,
    )

    decisions = tuple(
        _decision(
            decision_id=f"orgcpd-{index:016x}",
            implementations=(
                _implementation(
                    implementation_id=f"orgcpi-{index:016x}",
                    decision_id=f"orgcpd-{index:016x}",
                ),
            ),
        )
        for index in range(MAX_CANDIDATE_COLLECTIVE_DECISIONS + 1)
    )
    with pytest.raises(OrganizationArtifactError):
        OrganizationCandidateRecord(
            organization_id=ORG,
            creation_tick=1,
            first_tick=1,
            last_tick=10,
            status="recognized",
            temporal_scope="ongoing",
            self_identified=True,
            collective_decisions=decisions,
            collective_decision_count=len(decisions),
            collective_implementation_count=len(decisions),
        )


def test_v1_upgrade_adds_empty_agency_records() -> None:
    v1 = OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION_V1,
        policy_version="organization-analysis.v1",
        run_id="run-agency-snapshot",
        input_revision="revision-1",
        generated_tick=10,
        publication_id="",
        coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
    )
    upgraded = upgrade_organization_snapshot(v1)
    assert upgraded.schema_version == ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    assert upgraded.candidates == ()
    assert upgraded.windows == ()


def test_snapshot_decision_cap_is_enforced() -> None:
    from simulation.organization_models import (
        MAX_CANDIDATE_COLLECTIVE_DECISIONS,
        MAX_SNAPSHOT_COLLECTIVE_DECISIONS,
    )

    def _candidate(index: int, count: int) -> OrganizationCandidateRecord:
        organization_id = f"org-{index:016x}"
        decisions = tuple(
            _decision(
                decision_id=f"orgcpd-{(index * 100 + item):016x}",
                organization_id=organization_id,
                implementations=(),
            )
            for item in range(count)
        )
        return OrganizationCandidateRecord(
            organization_id=organization_id,
            creation_tick=1,
            first_tick=1,
            last_tick=10,
            status="recognized",
            temporal_scope="ongoing",
            self_identified=True,
            collective_decisions=decisions,
            collective_decision_count=len(decisions),
        )

    full_candidates = [
        _candidate(index, MAX_CANDIDATE_COLLECTIVE_DECISIONS)
        for index in range(MAX_SNAPSHOT_COLLECTIVE_DECISIONS // 64)
    ]
    total = sum(len(candidate.collective_decisions) for candidate in full_candidates)
    full_candidates.append(
        _candidate(
            len(full_candidates),
            MAX_SNAPSHOT_COLLECTIVE_DECISIONS - total + 1,
        )
    )
    with pytest.raises(OrganizationArtifactError):
        OrganizationSnapshot(
            schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
            policy_version="organization-analysis.v1",
            run_id="run-agency-snapshot",
            input_revision="revision-1",
            generated_tick=10,
            publication_id="",
            coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
            candidates=tuple(full_candidates),
        )
