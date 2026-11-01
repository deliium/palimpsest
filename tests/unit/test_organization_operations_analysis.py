"""Detached operation summaries: candidate join, disagreement, no new identity."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationActionRecord,
    OrganizationAdmissionBelief,
    OrganizationAdmissionStance,
    OrganizationAssignmentBelief,
    OrganizationAssignmentStance,
    OrganizationAuthorityBasis,
    OrganizationControlBelief,
    OrganizationControlStance,
    OrganizationDecisionRecord,
    OrganizationDecisionStance,
    OrganizationOperationAct,
    OrganizationOperationalConcept,
    OrganizationOperationalStatus,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
    OrganizationOperationOutcome,
    OrganizationOperationProvenance,
    OrganizationProcedureActionBelief,
    OrganizationTemporalScope,
    organization_decision_id,
)
from agents.models import AgentId
from analysis import (
    OrganizationAnalysisError,
    OrganizationCandidate,
    OrganizationCandidateStatus,
    OrganizationCoverage,
    OrganizationDetectionResult,
    OrganizationHarvestRows,
    OrganizationLayerView,
    OrganizationOperationHarvestRows,
    OrganizationOperationSummary,
    OrganizationWindowResult,
    assign_organization_identities,
    harvest_organization_operation_rows,
    summarize_organization_operations,
)
from analysis import (
    OrganizationTemporalScope as AnalysisTemporalScope,
)

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
ORG_A = f"orgc-{'a' * 16}"
ORG_B = f"orgc-{'b' * 16}"


def _candidate(
    key: str,
    *,
    window: int = 0,
    members: tuple[str, ...] = ("agent-1", "agent-2"),
    resources: tuple[str, ...] = ("repository-beta",),
    goals: tuple[str, ...] = (),
    owners: tuple[str, ...] = ("agent-1",),
) -> OrganizationCandidate:
    return OrganizationCandidate(
        candidate_key=key,
        window_index=window,
        member_ids=tuple(sorted(members)),
        member_claims=(),
        role_anchor_ids=(),
        goal_anchor_ids=tuple(sorted(goals)),
        resource_anchor_ids=tuple(sorted(resources)),
        procedure_anchor_ids=(),
        record_anchor_ids=(),
        commitment_ids=(),
        identity_tokens=(),
        status=OrganizationCandidateStatus.PARTIAL,
        temporal_scope=AnalysisTemporalScope.ONGOING,
        self_identified=False,
        owner_ids=tuple(sorted(owners)),
        first_tick=window * 10,
        last_tick=window * 10 + 9,
    )


def _detection(
    candidates: tuple[OrganizationCandidate, ...],
    windows: tuple[int, ...] = (0,),
) -> OrganizationDetectionResult:
    return OrganizationDetectionResult(
        windows=tuple(
            OrganizationWindowResult(
                window_index=index,
                start_tick=index * 10,
                end_tick=index * 10 + 9,
                candidate_keys=tuple(
                    candidate.candidate_key
                    for candidate in candidates
                    if candidate.window_index == index
                ),
                lane_presence=(("resources", True),),
            )
            for index in windows
        ),
        candidates=candidates,
        coverage=OrganizationCoverage.of(1, 7),
    )


def _control(
    *, stance: OrganizationControlStance = OrganizationControlStance.RECOGNIZED,
    contest_count: int = 0,
) -> OrganizationControlBelief:
    return OrganizationControlBelief(
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        anchor_kind="resource",
        anchor_id="repository-beta",
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.ROLE_BELIEF,
        legitimacy_doctrine="role_trusteeship",
        decision_ref=None,
        role_ref=None,
        first_tick=1,
        last_tick=5,
        owner_support_count=3,
        contest_count=contest_count,
    )


def _admission(
    *,
    member_id: str = "agent-2",
    stance: OrganizationAdmissionStance = OrganizationAdmissionStance.ADMITTED,
) -> OrganizationAdmissionBelief:
    return OrganizationAdmissionBelief(
        member_id=member_id,
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        role_ref=None,
        decision_ref=None,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        expires_tick=None,
        first_tick=1,
        last_tick=5,
        owner_support_count=2,
        contest_count=0,
    )


def _assignment(
    *, stance: OrganizationAssignmentStance = OrganizationAssignmentStance.ASSIGNED
) -> OrganizationAssignmentBelief:
    return OrganizationAssignmentBelief(
        office_id="office-1",
        occupant_id="agent-2",
        stance=stance,
        authority_basis=OrganizationAuthorityBasis.DECISION_BELIEF,
        decision_ref=None,
        first_tick=1,
        last_tick=5,
        owner_support_count=1,
        contest_count=0,
    )


def _procedure(
    *,
    outcome: OrganizationOperationOutcome = OrganizationOperationOutcome.COMPLETED,
    contest_count: int = 0,
) -> OrganizationProcedureActionBelief:
    return OrganizationProcedureActionBelief(
        procedure_ref="procedure-1",
        command_kind="give",
        actor_id="agent-2",
        outcome=outcome,
        authority_basis=OrganizationAuthorityBasis.PROCEDURE_BELIEF,
        decision_ref=None,
        first_tick=2,
        last_tick=4,
        owner_support_count=1,
        contest_count=contest_count,
    )


def _decision(
    *,
    owner: AgentId = OWNER,
    org: str = ORG_A,
    stance: OrganizationDecisionStance = OrganizationDecisionStance.SUPPORTED,
    oppose_count: int = 0,
) -> OrganizationDecisionRecord:
    return OrganizationDecisionRecord(
        decision_id=organization_decision_id(
            owner.value,
            org,
            OrganizationOperationDomain.RESOURCE_CONTROL,
            OrganizationOperationAct.AUTHORIZE_CONTROL,
            3,
            owner.value,
            "",
            "resource",
            "repository-beta",
            stance,
        ),
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        act=OrganizationOperationAct.AUTHORIZE_CONTROL,
        actor_id=owner.value,
        target_id=None,
        anchor_kind="resource",
        anchor_id="repository-beta",
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        stance=stance,
        support_count=1,
        oppose_count=oppose_count,
        provenance_code=OrganizationOperationProvenance.SELF_AUTHORED,
        tick=3,
    )


def _action(*, tick: int = 4) -> OrganizationActionRecord:
    return OrganizationActionRecord(
        action_id=f"orga-{'1' * 16}",
        decision_id=None,
        domain=OrganizationOperationDomain.RESOURCE_CONTROL,
        act=OrganizationOperationAct.AUTHORIZE_CONTROL,
        actor_id="agent-1",
        command_kind="give",
        anchor_kind="resource",
        anchor_id="repository-beta",
        outcome=OrganizationOperationOutcome.COMPLETED,
        provenance_code=OrganizationOperationProvenance.OBSERVED_EFFECT,
        tick=tick,
    )


def _concept(
    *,
    organization_id: str = ORG_A,
    owner: AgentId = OWNER,
    controls: tuple[OrganizationControlBelief, ...] = (),
    admissions: tuple[OrganizationAdmissionBelief, ...] = (),
    assignments: tuple[OrganizationAssignmentBelief, ...] = (),
    procedures: tuple[OrganizationProcedureActionBelief, ...] = (),
    decisions: tuple[OrganizationDecisionRecord, ...] = (),
    actions: tuple[OrganizationActionRecord, ...] = (),
) -> OrganizationOperationalConcept:
    return OrganizationOperationalConcept(
        organization_id=organization_id,
        owner_id=owner,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=6,
        controls=controls,
        admissions=admissions,
        assignments=assignments,
        procedures=procedures,
        decisions=decisions,
        actions=actions,
    )


def _rows(
    *ledgers: OrganizationOperationLedger,
) -> tuple[OrganizationOperationHarvestRows, ...]:
    return harvest_organization_operation_rows(ledgers)


def _ledger(*, owner: AgentId = OWNER) -> OrganizationOperationLedger:
    return OrganizationOperationLedger(
        owner_id=owner,
        concepts=(
            _concept(
                owner=owner,
                controls=(_control(),),
                admissions=(_admission(),),
                assignments=(_assignment(),),
                procedures=(_procedure(),),
                decisions=(_decision(owner=owner),),
                actions=(_action(),),
            ),
        ),
    )


def _summary(
    rows: tuple[OrganizationOperationHarvestRows, ...],
    candidates: tuple[OrganizationCandidate, ...],
) -> OrganizationOperationSummary | None:
    assignment = assign_organization_identities(_detection(candidates))
    return summarize_organization_operations(rows, assignment)


def test_single_concept_maps_to_exactly_one_candidate() -> None:
    candidate = _candidate("w0")
    summary = _summary(_rows(_ledger()), (candidate,))
    assert summary is not None
    assert summary.candidate_count == 1
    assert summary.candidates_with_operations == 1
    only = summary.candidates[0]
    assert only.organization_id.startswith("org-")
    assert only.control_counts == (("resource_control", 1),)
    assert only.admission_count == 1
    assert only.assignment_count == 1
    assert only.procedure_action_count == 1
    assert only.decision_count == 1
    assert only.action_count == 1
    assert only.operation_count == 6
    assert summary.coverage_ratio == 1.0


def test_ambiguous_overlap_uses_candidate_key_tie_break() -> None:
    summary = _summary(
        _rows(_ledger()),
        (_candidate("w1", goals=("goal-2",)), _candidate("w0", goals=("goal-1",))),
    )
    assert summary is not None
    assert summary.candidates[0].operation_count > 0
    assert summary.candidates[1].operation_count == 0
    assert summary.orphaned_count == 0
    assert summary.coverage_ratio == 0.5


def test_two_owners_map_deterministically() -> None:
    shared = _candidate(
        "w0",
        members=("agent-1", "agent-2"),
        owners=("agent-1", "agent-2"),
    )
    first = _summary(_rows(_ledger(owner=OTHER), _ledger()), (shared,))
    second = _summary(_rows(_ledger(), _ledger(owner=OTHER)), (shared,))
    assert first == second
    assert first is not None
    assert first.candidates[0].admission_count == 2


def test_unmatched_operations_are_orphaned() -> None:
    summary = _summary(
        _rows(_ledger()),
        (
            _candidate(
                "w0",
                members=("agent-9",),
                resources=("other",),
                owners=("agent-9",),
            ),
        ),
    )
    assert summary is not None
    assert summary.orphaned_count == 1
    assert summary.candidates[0].operation_count == 0
    assert summary.coverage_ratio == 0.0


def test_contested_records_map_to_operation_domains() -> None:
    ledger = OrganizationOperationLedger(
        owner_id=OWNER,
        concepts=(
            _concept(
                controls=(
                    _control(
                        stance=OrganizationControlStance.DISPUTED, contest_count=2
                    ),
                ),
                admissions=(
                    _admission(stance=OrganizationAdmissionStance.DISPUTED),
                ),
                assignments=(
                    _assignment(stance=OrganizationAssignmentStance.DISPUTED),
                ),
                procedures=(_procedure(contest_count=1),),
                decisions=(
                    _decision(stance=OrganizationDecisionStance.CONTESTED),
                ),
            ),
        ),
    )
    summary = _summary(_rows(ledger), (_candidate("w0"),))
    assert summary is not None
    assert summary.contested_domains == (
        "membership_admission",
        "procedure_action",
        "resource_control",
        "role_assignment",
    )
    assert summary.contested_operation_count == 5
    assert summary.candidates[0].has_contest is True


def test_empty_inputs_return_none() -> None:
    assert summarize_organization_operations((), None) is None
    assignment = assign_organization_identities(_detection((_candidate("w0"),)))
    assert summarize_organization_operations((), assignment) is None
    assert summarize_organization_operations(_rows(_ledger()), None) is None


def test_summary_never_changes_detection_identity_or_lineage() -> None:
    detection = _detection((_candidate("w0"),))
    assignment = assign_organization_identities(detection)
    before_windows = assignment.windows
    before_records = assignment.records
    before_transitions = assignment.transitions
    before_candidates = assignment.windows[-1].candidates
    summary = summarize_organization_operations(_rows(_ledger()), assignment)
    assert summary is not None
    assert assignment.windows is before_windows
    assert assignment.records is before_records
    assert assignment.transitions is before_transitions
    assert assignment.windows[-1].candidates is before_candidates
    assert assignment.windows[-1].candidates[0].status is (
        OrganizationCandidateStatus.PARTIAL
    )
    for candidate in summary.candidates:
        assert candidate.organization_id.startswith("org-")
        dumped = repr(candidate)
        assert "orgc-" not in dumped
        assert "orgd-" not in dumped
        assert "orga-" not in dumped


def test_stale_concepts_are_outside_the_summary_population() -> None:
    active = OrganizationOperationalConcept(
        organization_id=ORG_A,
        owner_id=OWNER,
        status=OrganizationOperationalStatus.ACTIVE,
        first_tick=1,
        last_tick=12,
        controls=(_control(),),
    )
    stale = OrganizationOperationalConcept(
        organization_id=ORG_B,
        owner_id=OWNER,
        status=OrganizationOperationalStatus.DISSOLVED,
        first_tick=1,
        last_tick=2,
        controls=(_control(),),
    )
    ledger = OrganizationOperationLedger(
        owner_id=OWNER,
        concepts=(active, stale),
    )
    assignment = assign_organization_identities(
        _detection((_candidate("w0", window=1),), windows=(0, 1))
    )
    summary = summarize_organization_operations(_rows(ledger), assignment)
    assert summary is not None
    assert summary.orphaned_count == 0
    assert summary.operation_count == 1
    assert summary.control_counts == (("resource_control", 1),)


def test_summary_rejects_a_foreign_assignment_type() -> None:
    with pytest.raises(OrganizationAnalysisError):
        summarize_organization_operations(_rows(_ledger()), object())  # type: ignore[arg-type]


def _owner_rows(
    *,
    organization_id: str = ORG_A,
    owner_id: str = "agent-1",
    last_tick: int = 20,
) -> OrganizationHarvestRows:
    from analysis import (
        OrganizationConceptRow,
        OrganizationHarvestRows,
        OrganizationOwnerRow,
    )

    return OrganizationHarvestRows(
        owner=OrganizationOwnerRow(
            owner_id=owner_id,
            concept_count=1,
            lineage_count=0,
            notices=(),
            policy_version="organization-concepts.v1",
        ),
        concepts=(
            OrganizationConceptRow(
                owner_id=owner_id,
                organization_id=organization_id,
                creation_tick=0,
                status="candidate",
                temporal_scope="ongoing",
                strength=0.5,
                member_evidence_count=2,
                structural_channel_count=1,
                first_tick=0,
                last_tick=last_tick,
                predecessor_ids=(),
                structural_signature="signature",
            ),
        ),
    )


def _layers(
    *, with_operations: bool = True
) -> tuple[OrganizationLayerView, OrganizationOperationSummary | None]:
    from analysis import project_organization_layers

    assignment = assign_organization_identities(_detection((_candidate("w0"),)))
    operation_rows = _rows(_ledger()) if with_operations else ()
    summary = summarize_organization_operations(operation_rows, assignment)
    view = project_organization_layers(
        assignment,
        (_owner_rows(),),
        operation_rows=operation_rows,
        operation_summary=summary,
    )
    return view, summary


def test_objective_rows_count_actions_without_any_ids() -> None:
    view, _ = _layers()
    assert view.objective
    assert view.objective[0].operation_action_count == 1
    for row in view.objective:
        for name in row.__dataclass_fields__:
            value = getattr(row, name)
            assert not isinstance(value, str)


def test_subjective_rows_count_owner_operations() -> None:
    view, _ = _layers()
    assert len(view.subjective) == 1
    row = view.subjective[0]
    assert row.organization_id.startswith("orgc-")
    assert row.operation_count == 6
    assert row.contested_operation_count == 0


def test_analytical_summary_uses_only_analytical_ids() -> None:
    view, summary = _layers()
    assert view.operations is summary
    assert summary is not None
    for candidate in summary.candidates:
        assert candidate.organization_id.startswith("org-")
        assert not candidate.organization_id.startswith("orgc-")


def test_leaked_owner_id_in_summary_raises_layer_leak() -> None:
    from analysis import (
        OrganizationCoverage,
        OrganizationLayerView,
        assert_organization_layer_separation,
    )

    _, summary = _layers()
    assert summary is not None
    object.__setattr__(summary.candidates[0], "organization_id", ORG_A)
    view = OrganizationLayerView(
        objective=(),
        subjective=(),
        analytical=(),
        coverage=OrganizationCoverage.of(1, 1),
        operations=summary,
    )
    with pytest.raises(OrganizationAnalysisError) as excinfo:
        assert_organization_layer_separation(view)
    assert excinfo.value.reason_code == "organization_layer_leak"


def test_empty_operation_summary_is_legal_and_zero_filled() -> None:
    view, summary = _layers(with_operations=False)
    assert summary is None
    assert view.operations is None
    assert view.objective[0].operation_action_count == 0
    assert view.subjective[0].operation_count == 0
    assert view.subjective[0].contested_operation_count == 0
