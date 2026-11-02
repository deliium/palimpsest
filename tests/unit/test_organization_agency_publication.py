"""V4-05 completed-run composition into organization-snapshot-v3."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    OrganizationAgencyConcept,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyLedger,
    OrganizationAgencyPositionStance,
    OrganizationAgencyRecognition,
    OrganizationStatus,
)
from experiments.organization_harvest import (
    OrganizationHarvest,
    build_completed_run_organization_harvest,
)
from experiments.organization_publication import (
    build_organization_harvest_result,
    organization_publication_document,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    concept_id,
    concept_ledger,
    decision,
    implementation,
    position,
    proposal,
)

pytestmark = pytest.mark.unit

RUN_ID = "run-agency-publication"


def _harvest() -> OrganizationHarvest:
    concepts = concept_ledger()
    first = proposal(organization_id=concept_id(concepts))
    decided = decision(
        first,
        recognition=OrganizationAgencyRecognition.RECOGNIZED,
        status=OrganizationAgencyImplementationStatus.IMPLEMENTED,
    )
    done = implementation(decided)
    stance = position(
        first.proposal_id,
        actor=OWNER,
        stance=OrganizationAgencyPositionStance.SUPPORT,
    )
    ledger = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept_id(concepts),
                owner_id=OWNER,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=10,
                proposals=(first,),
                positions=(stance,),
                decisions=(decided,),
                implementations=(done,),
            ),
        ),
    )
    result = SimpleNamespace(
        organization_concept_ledgers=(concepts,),
        organization_operation_ledgers=(),
        organization_agency_ledgers=(ledger,),
    )
    return build_completed_run_organization_harvest(
        result,
        run_id=RUN_ID,
        input_revision="revision-1",
        generated_tick=10,
    )


def test_composition_publishes_v3_with_agency_records() -> None:
    harvest = _harvest()
    result = build_organization_harvest_result(harvest)
    snapshot = result.snapshot
    assert snapshot.schema_version == "organization-snapshot-v3"
    assert result.collective_decision_count == 1
    assert result.collective_implementation_count == 1
    candidate = snapshot.candidates[0]
    assert candidate.collective_decision_count == 1
    assert candidate.collective_implementation_count == 1
    decision_record = candidate.collective_decisions[0]
    assert decision_record.decision_id.startswith("orgcpd-")
    assert decision_record.implementations[0].implementation_id.startswith("orgcpi-")


def test_published_records_strip_owner_local_and_raw_actor_ids() -> None:
    result = build_organization_harvest_result(_harvest())
    payload = result.snapshot_bytes
    for token in (b"orgc-", b"orgp-", b"orgpm-", b"orgcd-", b"orgci-", b"orgcev-"):
        assert token not in payload
    for candidate in result.snapshot.candidates:
        for decision_record in candidate.collective_decisions:
            assert "agent-1" not in decision_record.proposal_ref
            for record in decision_record.implementations:
                assert "agent-1" not in record.actor_ref
                assert record.actor_ref.isalnum() or "-" not in record.actor_ref


def test_receipt_counts_match_snapshot() -> None:
    result = build_organization_harvest_result(_harvest())
    receipt = organization_publication_document(result)
    assert receipt["collective_decision_count"] == 1
    assert receipt["collective_implementation_count"] == 1
    assert receipt["collective_agency_truncated"] is False
    assert "agent-1" not in repr(receipt)


def test_composition_is_deterministic() -> None:
    first = build_organization_harvest_result(_harvest())
    second = build_organization_harvest_result(_harvest())
    assert first.snapshot_bytes == second.snapshot_bytes
    assert first.publication_id == second.publication_id


def test_publication_failure_changes_only_the_receipt() -> None:
    from simulation.organization_models import OrganizationArtifactError
    from simulation.organization_ports import OrganizationPublicationPort

    result = build_organization_harvest_result(_harvest())
    before_bytes = result.snapshot_bytes
    before_digest = result.snapshot_digest
    before_counts = (
        result.collective_decision_count,
        result.collective_implementation_count,
    )

    class _FailingPort(OrganizationPublicationPort):
        def publish(self, publication: object) -> None:
            raise OrganizationArtifactError("organization_quota_exceeded")

    from experiments.organization_publication import publish_organization_snapshot

    with pytest.raises(OrganizationArtifactError):
        publish_organization_snapshot(result, _FailingPort())
    assert result.snapshot_bytes == before_bytes
    assert result.snapshot_digest == before_digest
    assert (
        result.collective_decision_count,
        result.collective_implementation_count,
    ) == before_counts
    receipt = organization_publication_document(result, status="failed")
    assert receipt["status"] == "failed"
    assert receipt["collective_decision_count"] == 1
