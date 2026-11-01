"""V4-04 operational records and ledger invariants."""

from __future__ import annotations

import ast
from dataclasses import make_dataclass
from pathlib import Path

import pytest

from agents.cognition import (
    FORBIDDEN_OPERATION_FIELD_NAMES,
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
    OrganizationOperationError,
    OrganizationOperationEvidence,
    OrganizationOperationEvidenceSource,
    OrganizationOperationLedger,
    OrganizationOperationOutcome,
    OrganizationOperationProvenance,
    OrganizationProcedureActionBelief,
    OrganizationTemporalScope,
    empty_organization_operation_ledger,
    organization_decision_id,
    require_owner_organization_operations,
)
from agents.cognition.organization_operations import (
    _reject_operation_forbidden_fields,
)
from agents.models import AgentId

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src" / "agents" / "cognition" / "organization_operations.py"

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
ORG = f"orgc-{'a' * 16}"


def _decision(
    *,
    tick: int = 10,
    domain: OrganizationOperationDomain = (
        OrganizationOperationDomain.RESOURCE_CONTROL
    ),
    act: OrganizationOperationAct = OrganizationOperationAct.AUTHORIZE_CONTROL,
    decision_id: str | None = None,
    actor_id: str = "agent-1",
    target_id: str | None = "agent-2",
    anchor_kind: str = "repository",
    anchor_id: str = "repository-beta",
    stance: OrganizationDecisionStance = OrganizationDecisionStance.SUPPORTED,
    provenance: OrganizationOperationProvenance = (
        OrganizationOperationProvenance.SELF_AUTHORED
    ),
) -> OrganizationDecisionRecord:
    return OrganizationDecisionRecord(
        decision_id=decision_id
        or organization_decision_id(
            OWNER.value,
            ORG,
            domain,
            act,
            tick,
            actor_id,
            target_id or "",
            anchor_kind,
            anchor_id,
            stance,
        ),
        domain=domain,
        act=act,
        actor_id=actor_id,
        target_id=target_id,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        stance=stance,
        support_count=0,
        oppose_count=0,
        provenance_code=provenance,
        tick=tick,
        evidence_refs=("ev-1",),
    )


def _action(
    *,
    index: int = 0,
    decision_id: str | None = None,
    tick: int = 10,
) -> OrganizationActionRecord:
    return OrganizationActionRecord(
        action_id=f"orga-{index:016x}",
        decision_id=decision_id,
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        act=OrganizationOperationAct.AUTHORIZE_CONTROL,
        actor_id="agent-1",
        command_kind="give",
        anchor_kind="item",
        anchor_id=f"item-{index}",
        outcome=OrganizationOperationOutcome.COMPLETED,
        provenance_code=OrganizationOperationProvenance.OBSERVED_EFFECT,
        tick=tick,
        evidence_refs=("ev-1",),
    )


def _control(index: int = 0) -> OrganizationControlBelief:
    return OrganizationControlBelief(
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        anchor_kind="repository",
        anchor_id=f"repository-{index}",
        stance=OrganizationControlStance.RECOGNIZED,
        authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
        legitimacy_doctrine="role_trusteeship",
        decision_ref=None,
        role_ref=None,
        first_tick=1,
        last_tick=2,
        owner_support_count=1,
        contest_count=0,
        evidence_refs=("ev-1",),
    )


def _admission(
    *, stance: OrganizationAdmissionStance = OrganizationAdmissionStance.ADMITTED
) -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id="agent-2",
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        expires_tick=None,
        first_tick=1,
        last_tick=1,
        owner_support_count=1,
        contest_count=0,
        evidence_refs=("ev-1",),
    )


def _concept(
    *,
    organization_id: str = ORG,
    owner_id: AgentId = OWNER,
    controls: tuple[OrganizationControlBelief, ...] = (),
    admissions: tuple[OrganizationAdmissionBelief, ...] = (),
    departures: tuple[OrganizationDepartureBelief, ...] = (),
    assignments: tuple[OrganizationAssignmentBelief, ...] = (),
    procedures: tuple[OrganizationProcedureActionBelief, ...] = (),
    commitments: tuple[OrganizationCommitmentOperationBelief, ...] = (),
    decisions: tuple[OrganizationDecisionRecord, ...] = (),
    actions: tuple[OrganizationActionRecord, ...] = (),
    status: OrganizationOperationalStatus = OrganizationOperationalStatus.ACTIVE,
    notices: tuple[str, ...] = (),
) -> OrganizationOperationalConcept:
    return OrganizationOperationalConcept(
        organization_id=organization_id,
        owner_id=owner_id,
        status=status,
        first_tick=1,
        last_tick=10,
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


def test_record_families_validate_closed_vocabularies() -> None:
    with pytest.raises(OrganizationOperationError):
        OrganizationControlBelief(
            domain=OrganizationOperationDomain.MEMBERSHIP_ADMISSION,
            anchor_kind="repository",
            anchor_id="repository-beta",
            stance=OrganizationControlStance.RECOGNIZED,
            authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
            legitimacy_doctrine="none",
            decision_ref=None,
            role_ref=None,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationAdmissionBelief(
            member_id="agent-2",
            stance=OrganizationDepartureStance.RESIGNED,  # type: ignore[arg-type]
            authority_basis=OrganizationAuthorityBasis.UNKNOWN,
            role_ref=None,
            decision_ref=None,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            expires_tick=None,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationControlBelief(
            domain=OrganizationOperationDomain.RESOURCE_CONTROL,
            anchor_kind="repository",
            anchor_id="repository-beta",
            stance=OrganizationControlStance.RECOGNIZED,
            authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
            legitimacy_doctrine="legal_title",
            decision_ref=None,
            role_ref=None,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
        )


def test_evidence_validates_source_and_digest() -> None:
    evidence = OrganizationOperationEvidence(
        evidence_id=f"orgev-{'a' * 16}",
        ordinal=0,
        source=OrganizationOperationEvidenceSource.OBSERVATION,
        ref="ref-1",
        tick=1,
        anchor_digest="a" * 64,
    )
    assert evidence.source is OrganizationOperationEvidenceSource.OBSERVATION

    with pytest.raises(OrganizationOperationError):
        OrganizationOperationEvidence(
            evidence_id=f"orgev-{'a' * 16}",
            ordinal=0,
            source="peer_ledger",  # type: ignore[arg-type]
            ref="ref-1",
            tick=1,
            anchor_digest="a" * 64,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationOperationEvidence(
            evidence_id=f"orgev-{'a' * 16}",
            ordinal=0,
            source=OrganizationOperationEvidenceSource.OBSERVATION,
            ref="ref-1",
            tick=1,
            anchor_digest="not-hex",
        )


def test_records_reject_forbidden_fields() -> None:
    for name in (
        "truth",
        "verified",
        "owner",
        "property",
        "title",
        "deed",
        "permission",
    ):
        fake = make_dataclass("Fake", [(name, object)])
        with pytest.raises(OrganizationOperationError):
            _reject_operation_forbidden_fields(fake)
    assert "truth" in FORBIDDEN_OPERATION_FIELD_NAMES
    assert "permission" in FORBIDDEN_OPERATION_FIELD_NAMES


def test_temporary_admission_requires_expiry_and_ongoing_forbids_it() -> None:
    with pytest.raises(OrganizationOperationError):
        OrganizationAdmissionBelief(
            member_id="agent-2",
            stance=OrganizationAdmissionStance.ADMITTED,
            authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
            role_ref=None,
            decision_ref=None,
            temporal_scope=OrganizationTemporalScope.TEMPORARY,
            expires_tick=None,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
        )

    with pytest.raises(OrganizationOperationError):
        OrganizationAdmissionBelief(
            member_id="agent-2",
            stance=OrganizationAdmissionStance.ADMITTED,
            authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
            role_ref=None,
            decision_ref=None,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            expires_tick=4,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
        )

    temporary = OrganizationAdmissionBelief(
        member_id="agent-2",
        stance=OrganizationAdmissionStance.ADMITTED,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.TEMPORARY,
        expires_tick=4,
        first_tick=1,
        last_tick=1,
        owner_support_count=1,
        contest_count=0,
    )
    assert temporary.expires_tick == 4


def test_decision_and_action_references_must_resolve() -> None:
    decision = _decision()
    action = _action(decision_id=decision.decision_id)
    concept = _concept(decisions=(decision,), actions=(action,))
    assert concept.actions[0].decision_id == decision.decision_id

    dangling = _action(decision_id=f"orgd-{'b' * 16}")
    with pytest.raises(OrganizationOperationError):
        _concept(actions=(dangling,))

    duplicate = _decision()
    with pytest.raises(OrganizationOperationError):
        _concept(decisions=(duplicate, duplicate))


def test_ledger_rejects_unsorted_or_foreign_concepts() -> None:
    first = _concept(organization_id=f"orgc-{'a' * 16}", controls=(_control(),))
    second = _concept(organization_id=f"orgc-{'b' * 16}", controls=(_control(),))
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationLedger(owner_id=OWNER, concepts=(second, first))

    foreign = _concept(owner_id=OTHER, controls=(_control(),))
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationLedger(owner_id=OWNER, concepts=(foreign,))


def test_ledger_rejects_tick_regression_and_duplicate_ids() -> None:
    with pytest.raises(OrganizationOperationError):
        _concept(decisions=(_decision(tick=10), _decision(tick=9)))

    decision = _decision()
    with pytest.raises(OrganizationOperationError):
        OrganizationOperationLedger(
            owner_id=OWNER,
            concepts=(
                _concept(decisions=(decision,)),
                _concept(
                    organization_id=f"orgc-{'b' * 16}",
                    decisions=(decision,),
                ),
            ),
        )


def test_caps_reject_oversized_families() -> None:
    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationOperationLedger(
            owner_id=OWNER,
            concepts=(_concept(controls=tuple(_control(i) for i in range(33))),),
        )
    assert excinfo.value.code == "organization_operation_cap_exceeded"

    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationOperationLedger(
            owner_id=OWNER,
            concepts=(
                _concept(
                    assignments=tuple(
                        OrganizationAssignmentBelief(
                            office_id="office-1",
                            occupant_id=f"agent-{i}",
                            stance=OrganizationAssignmentStance.ASSIGNED,
                            authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
                            decision_ref=None,
                            first_tick=1,
                            last_tick=1,
                            owner_support_count=1,
                            contest_count=0,
                        )
                        for i in range(17)
                    )
                ),
            ),
        )
    assert excinfo.value.code == "organization_operation_cap_exceeded"

    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationOperationLedger(
            owner_id=OWNER,
            concepts=(
                _concept(actions=tuple(_action(index=i) for i in range(65))),
            ),
        )
    assert excinfo.value.code == "organization_operation_cap_exceeded"


def test_evidence_refs_cap_is_per_record() -> None:
    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationAdmissionBelief(
            member_id="agent-2",
            stance=OrganizationAdmissionStance.ADMITTED,
            authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
            role_ref=None,
            decision_ref=None,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            expires_tick=None,
            first_tick=1,
            last_tick=1,
            owner_support_count=1,
            contest_count=0,
            evidence_refs=tuple(f"ev-{i}" for i in range(9)),
        )
    assert excinfo.value.code == "organization_operation_cap_exceeded"


def test_total_record_cap_spans_concepts() -> None:
    concepts = tuple(
        _concept(
            organization_id=f"orgc-{index:016x}",
            actions=tuple(_action(index=index * 64 + offset) for offset in range(64)),
        )
        for index in range(5)
    )
    with pytest.raises(OrganizationOperationError) as excinfo:
        OrganizationOperationLedger(owner_id=OWNER, concepts=concepts)
    assert excinfo.value.code == "organization_operation_cap_exceeded"


def test_notices_are_closed_and_include_expiry() -> None:
    ledger = OrganizationOperationLedger(
        owner_id=OWNER,
        concepts=(_concept(notices=("operation_expired",)),),
        notices=("operations_truncated",),
    )
    assert ledger.notices == ("operations_truncated",)

    with pytest.raises(OrganizationOperationError):
        OrganizationOperationLedger(
            owner_id=OWNER,
            concepts=(_concept(),),
            notices=("invented_notice",),
        )


def test_empty_ledger_and_owner_requirement() -> None:
    ledger = empty_organization_operation_ledger(OWNER)
    assert ledger.owner_id == OWNER
    assert ledger.concepts == ()
    require_owner_organization_operations(
        ledger, OWNER, field_name="organization_operations"
    )
    with pytest.raises(OrganizationOperationError) as excinfo:
        require_owner_organization_operations(
            ledger, OTHER, field_name="organization_operations"
        )
    assert excinfo.value.code == "organization_operation_foreign_ledger"


def test_all_record_families_construct() -> None:
    decision = _decision()
    concept = _concept(
        controls=(_control(),),
        admissions=(_admission(),),
        departures=(
            OrganizationDepartureBelief(
                member_id="agent-2",
                stance=OrganizationDepartureStance.RESIGNED,
                authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
                decision_ref=None,
                first_tick=1,
                last_tick=1,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        assignments=(
            OrganizationAssignmentBelief(
                office_id="office-1",
                occupant_id="agent-2",
                stance=OrganizationAssignmentStance.ASSIGNED,
                authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
                decision_ref=None,
                first_tick=1,
                last_tick=1,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        procedures=(
            OrganizationProcedureActionBelief(
                procedure_ref="procedure-1",
                command_kind="maintain_repository",
                actor_id="agent-1",
                outcome=OrganizationOperationOutcome.COMPLETED,
                authority_basis=OrganizationAuthorityBasis.PROCEDURE_BELIEF,
                decision_ref=None,
                first_tick=1,
                last_tick=1,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        commitments=(
            OrganizationCommitmentOperationBelief(
                commitment_id="commitment-1",
                role=OrganizationCommitmentRole.DEBTOR,
                counterpart_id="agent-2",
                stance=OrganizationCommitmentStance.DECLARED,
                authority_basis=OrganizationAuthorityBasis.UNKNOWN,
                decision_ref=None,
                due_tick=12,
                first_tick=1,
                last_tick=1,
                owner_support_count=1,
                contest_count=0,
            ),
        ),
        decisions=(decision,),
        actions=(_action(decision_id=decision.decision_id),),
    )
    ledger = OrganizationOperationLedger(owner_id=OWNER, concepts=(concept,))
    assert len(ledger.concepts[0].actions) == 1


def test_module_adds_no_command_or_event_class() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert not {name for name in names if name.endswith(("Command", "Event"))}
