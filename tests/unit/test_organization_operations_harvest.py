"""Detached organization operation harvest: rows, ordering, and isolation."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from agents.cognition import (
    OrganizationActionRecord,
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAssignmentBelief,
    OrganizationAssignmentStance,
    OrganizationAuthorityBasis,
    OrganizationCommitmentOperationBelief,
    OrganizationCommitmentRole,
    OrganizationCommitmentStance,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationDecisionRecord,
    OrganizationDecisionStance,
    OrganizationDepartureBelief,
    OrganizationDepartureStance,
    OrganizationOperationAct,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
    OrganizationOperationOutcome,
    OrganizationOperationProvenance,
    OrganizationProcedureActionBelief,
    OrganizationTemporalScope,
    empty_organization_operation_ledger,
    organization_decision_id,
)
from agents.models import AgentId
from analysis import (
    OrganizationAnalysisError,
    harvest_organization_operation_rows,
    harvest_organization_operation_snapshot,
)

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "analysis" / "organization_operations.py"

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
ORG_A = f"orgc-{'a' * 16}"
ORG_B = f"orgc-{'b' * 16}"


def _decision(
    *,
    tick: int = 10,
    domain: OrganizationOperationDomain = (
        OrganizationOperationDomain.RESOURCE_CONTROL
    ),
) -> OrganizationDecisionRecord:
    act = OrganizationOperationAct.AUTHORIZE_CONTROL
    stance = OrganizationDecisionStance.SUPPORTED
    actor_id = OWNER.value
    anchor_kind = "repository"
    anchor_id = "repository-beta"
    return OrganizationDecisionRecord(
        decision_id=organization_decision_id(
            OWNER.value,
            ORG_A,
            domain,
            act,
            tick,
            actor_id,
            "",
            anchor_kind,
            anchor_id,
            stance,
        ),
        domain=domain,
        act=act,
        actor_id=actor_id,
        target_id=None,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
        stance=stance,
        support_count=2,
        oppose_count=1,
        provenance_code=OrganizationOperationProvenance.ROLE_AUTHORIZED,
        tick=tick,
        evidence_refs=("ev-1",),
    )


def _action(*, tick: int = 11) -> OrganizationActionRecord:
    return OrganizationActionRecord(
        action_id=f"orga-{'1' * 16}",
        decision_id=None,
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        act=OrganizationOperationAct.AUTHORIZE_CONTROL,
        actor_id=OWNER.value,
        command_kind="give",
        anchor_kind="item",
        anchor_id="item-1",
        outcome=OrganizationOperationOutcome.COMPLETED,
        provenance_code=OrganizationOperationProvenance.OBSERVED_EFFECT,
        tick=tick,
        evidence_refs=("ev-1",),
    )


def _concept(
    *,
    organization_id: str = ORG_A,
    owner_id: AgentId = OWNER,
    controls: tuple[OrganizationControlBelief, ...] = (),
    admissions: tuple[OrganizationAdmissionBelief, ...] = (),
    departures: tuple[OrganizationDepartureBelief, ...] = (),
    assignments: tuple[OrganizationAssignmentBelief, ...] = (),
    procedures: tuple[OrganizationProcedureActionBelief, ...] = (),
    commitments: tuple[OrganizationCommitmentOperationBelief, ...] = (),
    decisions: tuple[OrganizationDecisionRecord, ...] = (),
    actions: tuple[OrganizationActionRecord, ...] = (),
    notices: tuple[str, ...] = (),
) -> OrganizationOperationalConcept:
    return OrganizationOperationalConcept(
        organization_id=organization_id,
        owner_id=owner_id,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=12,
        controls=controls,
        admissions=admissions,
        departures=departures,
        assignments=assignments,
        procedures=procedures,
        commitments=commitments,
        decisions=decisions,
        actions=actions,
        notices=notices,
    )


def _family_concept(
    *, organization_id: str = ORG_A, owner_id: AgentId = OWNER
) -> OrganizationOperationalConcept:
    return _concept(
        organization_id=organization_id,
        owner_id=owner_id,
        controls=(
            OrganizationControlBelief(
                domain=OrganizationOperationDomain.RESOURCE_CONTROL,
                anchor_kind="repository",
                anchor_id="repository-beta",
                stance=OrganizationControlStance.DISPUTED,
                authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
                legitimacy_doctrine="role_trusteeship",
                decision_ref=None,
                role_ref=None,
                first_tick=2,
                last_tick=5,
                owner_support_count=2,
                contest_count=1,
            ),
        ),
        admissions=(
            OrganizationAdmissionBelief(
                member_id="agent-2",
                stance=OrganizationAdmissionStance.ADMITTED,
                authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
                role_ref=None,
                decision_ref=None,
                temporal_scope=OrganizationTemporalScope.ONGOING,
                expires_tick=None,
                first_tick=2,
                last_tick=3,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        departures=(
            OrganizationDepartureBelief(
                member_id="agent-3",
                stance=OrganizationDepartureStance.DEPARTED,
                authority_basis=OrganizationAuthorityBasis.OBSERVATION,
                decision_ref=None,
                first_tick=4,
                last_tick=4,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        assignments=(
            OrganizationAssignmentBelief(
                office_id="office-1",
                occupant_id="agent-2",
                stance=OrganizationAssignmentStance.ASSIGNED,
                authority_basis=OrganizationAuthorityBasis.DECISION_BELIEF,
                decision_ref=None,
                first_tick=3,
                last_tick=6,
                owner_support_count=2,
                contest_count=0,
            ),
        ),
        procedures=(
            OrganizationProcedureActionBelief(
                procedure_ref="procedure-1",
                command_kind="give",
                actor_id="agent-2",
                outcome=OrganizationOperationOutcome.COMPLETED,
                authority_basis=OrganizationAuthorityBasis.PROCEDURE_BELIEF,
                decision_ref=None,
                first_tick=5,
                last_tick=5,
                owner_support_count=1,
                contest_count=2,
            ),
        ),
        commitments=(
            OrganizationCommitmentOperationBelief(
                commitment_id="commitment-1",
                role=OrganizationCommitmentRole.DEBTOR,
                counterpart_id="agent-3",
                stance=OrganizationCommitmentStance.DECLARED,
                authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
                decision_ref=None,
                due_tick=20,
                first_tick=6,
                last_tick=6,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        decisions=(_decision(),),
        actions=(_action(),),
    )


def _ledger(
    *concepts: OrganizationOperationalConcept, owner: AgentId = OWNER
) -> OrganizationOperationLedger:
    return OrganizationOperationLedger(owner_id=owner, concepts=tuple(concepts))


def test_harvest_preserves_every_record_family() -> None:
    rows = harvest_organization_operation_rows((_ledger(_family_concept()),))
    assert len(rows) == 1
    harvest = rows[0]
    assert harvest.owner.owner_id == OWNER.value
    assert harvest.owner.policy_version == "organization-operations.v1"
    assert harvest.owner.concept_count == 1
    assert harvest.owner.control_count == 1
    assert harvest.owner.admission_count == 1
    assert harvest.owner.departure_count == 1
    assert harvest.owner.assignment_count == 1
    assert harvest.owner.procedure_count == 1
    assert harvest.owner.commitment_count == 1
    assert harvest.owner.decision_count == 1
    assert harvest.owner.action_count == 1
    assert harvest.owner.record_count == 8
    assert harvest.has_operations is True
    assert harvest.has_contest is True
    assert harvest.controls[0].organization_id == ORG_A
    assert harvest.controls[0].span == 3
    assert harvest.actions[0].command_kind == "give"
    assert str(harvest.decisions[0].decision_id).startswith("orgd-")
    assert str(harvest.actions[0].action_id).startswith("orga-")


def test_harvest_orders_owners_and_records_deterministically() -> None:
    first = harvest_organization_operation_rows(
        (
            _ledger(
                _family_concept(organization_id=ORG_B, owner_id=OTHER), owner=OTHER
            ),
            _ledger(_family_concept(organization_id=ORG_A)),
        )
    )
    second = harvest_organization_operation_rows(
        (
            _ledger(_family_concept(organization_id=ORG_A)),
            _ledger(
                _family_concept(organization_id=ORG_B, owner_id=OTHER), owner=OTHER
            ),
        )
    )
    assert [row.owner.owner_id for row in first] == [OWNER.value, OTHER.value]
    assert first == second
    assert first[1].controls[0].organization_id == ORG_B


def test_duplicate_owner_ledger_is_rejected() -> None:
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        harvest_organization_operation_rows(
            (_ledger(_family_concept()), _ledger(_family_concept()))
        )
    assert excinfo.value.reason_code == "organization_operation_row_invalid"


def test_foreign_owner_concept_is_rejected() -> None:
    ledger = _ledger(_family_concept())
    object.__setattr__(ledger.concepts[0], "owner_id", OTHER)
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        harvest_organization_operation_rows((ledger,))
    assert excinfo.value.reason_code == "organization_operation_row_invalid"


def test_empty_or_missing_operation_ledgers_yield_empty_rows() -> None:
    assert harvest_organization_operation_rows(None) == ()
    assert harvest_organization_operation_rows(()) == ()
    assert harvest_organization_operation_snapshot(object()) == ()
    empty = empty_organization_operation_ledger(OWNER)
    rows = harvest_organization_operation_rows((empty,))
    assert rows[0].controls == ()
    assert rows[0].owner.record_count == 0
    assert rows[0].has_operations is False
    assert rows[0].has_contest is False


def test_missing_optional_attributes_are_tolerated() -> None:
    stub = SimpleNamespace(
        organization_id=ORG_A,
        owner_id=OWNER,
        controls=(SimpleNamespace(stance="disputed", contest_count=1),),
    )
    ledger = SimpleNamespace(
        owner_id=OWNER,
        policy_version="organization-operations.v1",
        concepts=(stub,),
        notices=(),
    )
    rows = harvest_organization_operation_rows((ledger,))
    control = rows[0].controls[0]
    assert control.organization_id == ORG_A
    assert control.anchor_id is None
    assert control.first_tick is None
    assert control.span is None
    assert rows[0].has_contest is True


def test_operation_harvest_module_is_detached() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    forbidden = (
        "agents",
        "experiments",
        "api",
        "persistence",
        "infrastructure",
        "observer",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            assert not node.module.startswith(forbidden)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden)
