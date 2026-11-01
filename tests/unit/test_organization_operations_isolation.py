"""Owner-only operation updates: no peer ledger, world state, or batch input."""

from __future__ import annotations

import inspect

import pytest

from agents.cognition import (
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAuthorityBasis,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationError,
    OrganizationOperationLedger,
    OrganizationTemporalScope,
    apply_organization_operation_update,
    empty_organization_operation_ledger,
    require_owner_organization_operations,
)
from agents.models import AgentId
from analysis.organization_operations import harvest_organization_operation_rows

pytestmark = pytest.mark.unit

OWNER = AgentId("owner-1")
OTHER = AgentId("owner-2")
ORG = f"orgc-{'a' * 16}"


def _admission() -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id="member-a",
        stance=OrganizationAdmissionStance.ADMITTED,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        expires_tick=None,
        first_tick=1,
        last_tick=9,
        owner_support_count=1,
        contest_count=0,
    )


def _concept(
    owner: AgentId = OWNER, organization_id: str = ORG
) -> OrganizationOperationalConcept:
    return OrganizationOperationalConcept(
        organization_id=organization_id,
        owner_id=owner,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=9,
        admissions=(_admission(),),
    )


def test_update_accepts_only_owner_scoped_inputs() -> None:
    parameters = set(inspect.signature(apply_organization_operation_update).parameters)
    assert parameters == {
        "owner_id",
        "tick",
        "observation",
        "prior",
        "organization_concepts",
        "offices",
        "collective_decisions",
        "structured_commitments",
        "possession_legitimacy",
        "policy",
    }
    with pytest.raises(TypeError):
        apply_organization_operation_update(  # type: ignore[call-arg]
            owner_id=OWNER,
            tick=1,
            observation=object(),
            prior=None,
            organization_concepts=None,
            offices=None,
            collective_decisions=None,
            structured_commitments=None,
            possession_legitimacy=None,
            peer=None,
        )


def test_ledger_rejects_a_foreign_owner_concept() -> None:
    concept = _concept()
    object.__setattr__(concept, "owner_id", OTHER)
    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationOperationLedger(owner_id=OWNER, concepts=(concept,))
    assert excinfo.value.code == "organization_operation_foreign_ledger"


def test_foreign_owner_ledger_is_rejected_at_carry_boundaries() -> None:
    ledger = OrganizationOperationLedger(owner_id=OWNER, concepts=(_concept(),))
    require_owner_organization_operations(ledger, OWNER, field_name="prior")
    with pytest.raises(OrganizationOperationError):
        require_owner_organization_operations(ledger, OTHER, field_name="prior")


def test_empty_ledger_is_owner_scoped() -> None:
    ledger = empty_organization_operation_ledger(OWNER)
    assert ledger.owner_id == OWNER
    assert ledger.concepts == ()
    rows = harvest_organization_operation_rows((ledger,))
    assert rows[0].owner.owner_id == OWNER.value
    assert rows[0].has_operations is False


def test_another_owners_records_never_appear_in_harvest() -> None:
    other_org = f"orgc-{'b' * 16}"
    own = OrganizationOperationLedger(owner_id=OWNER, concepts=(_concept(),))
    other = OrganizationOperationLedger(
        owner_id=OTHER,
        concepts=(_concept(owner=OTHER, organization_id=other_org),),
    )
    rows = harvest_organization_operation_rows((other, own))
    by_owner = {row.owner.owner_id: row for row in rows}
    assert set(by_owner) == {OWNER.value, OTHER.value}
    for row in rows:
        for record in (*row.controls, *row.admissions, *row.commitments):
            assert record.organization_id in {ORG, other_org}
    assert all(
        record.organization_id == ORG for record in by_owner[OWNER.value].admissions
    )
    assert all(
        record.organization_id == other_org
        for record in by_owner[OTHER.value].admissions
    )
