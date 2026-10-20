"""Known-answer mediation metric families and role classification."""

from __future__ import annotations

from agents.cognition.mediation import empty_mediation_ledger
from agents.models import AgentId
from analysis.mediation import (
    MediationAttemptRow,
    MediationCaseRow,
    MediationEffectRow,
    MediationRecommendationRow,
    MediationResponseRow,
    MediationRoleClass,
    MediationRoleExpressionRow,
    MediationSnapshot,
    classify_mediation_roles,
    compute_conflict_mediation,
    compute_mediation_role_emergence,
    harvest_mediation_snapshot,
)
from analysis.models import METRIC_DOCUMENT_SCHEMA_VERSION

_CASE_A = "a" * 64
_CASE_B = "b" * 64
_CONTEXT = "c" * 16


def _case(ref: str, *, status: str = "unresolved") -> MediationCaseRow:
    return MediationCaseRow(
        owner_id="ada",
        case_ref=ref,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=status,
        origin_id="bob",
        party_ids=("bob", "dave"),
        evidence_count=1,
        pruned_evidence_count=0,
        first_tick=1,
        last_tick=2,
        window_first_tick=1,
        window_last_tick=8,
        evidence_coverage="complete",
    )


def _recommendation(
    ref: str, *, terms: tuple[str, ...] = ()
) -> MediationRecommendationRow:
    return MediationRecommendationRow(
        owner_id="ada",
        case_ref=ref,
        revision=0,
        proposed_actor_id="ada",
        action_token="give",
        item_token="bread",
        project_token=None,
        target_ids=("bob",),
        terms=terms,
        quantity=1,
        status="active",
        window_first_tick=1,
        window_last_tick=8,
    )


def _response(ref: str, kind: str) -> MediationResponseRow:
    return MediationResponseRow(
        owner_id="ada",
        actor_id="bob",
        case_ref=ref,
        kind=kind,
        recommendation_ref=None,
        recommendation_revision=None,
        direct=True,
        active=True,
        tick=2,
    )


def _snapshot(
    *,
    owner: str = "ada",
    cases: tuple[MediationCaseRow, ...] = (),
    recommendations: tuple[MediationRecommendationRow, ...] = (),
    responses: tuple[MediationResponseRow, ...] = (),
    role_expressions: tuple[MediationRoleExpressionRow, ...] = (),
    attempts: tuple[MediationAttemptRow, ...] = (),
    coverage: str = "complete",
) -> MediationSnapshot:
    return MediationSnapshot(
        owner_id=owner,
        enabled=True,
        coverage=coverage,
        first_observed_tick=1,
        last_observed_tick=2,
        observation_count=2,
        cases=cases,
        recommendations=recommendations,
        responses=responses,
        role_expressions=role_expressions,
        attempts=attempts,
    )


def test_distinct_cases_are_deduplicated_by_lineage() -> None:
    left = _snapshot(cases=(_case(_CASE_A),))
    right = _snapshot(owner="bea", cases=(_case(_CASE_A),))
    document = compute_conflict_mediation(
        (left, right), run_id="run-1", input_revision="rev-1", tick=3
    )
    assert document.metric_family == "conflict_mediation"
    assert document.schema_version == METRIC_DOCUMENT_SCHEMA_VERSION
    assert document.values["distinct_case_count"] == 1
    assert document.values["enabled_owner_count"] == 2


def test_genuinely_distinct_cases_and_responses() -> None:
    snapshot = _snapshot(
        cases=(_case(_CASE_A), _case(_CASE_B)),
        recommendations=(
            _recommendation(_CASE_A),
            _recommendation(_CASE_B, terms=("return_item",)),
        ),
        responses=(_response(_CASE_A, "accept"), _response(_CASE_B, "refuse")),
    )
    document = compute_conflict_mediation(
        (snapshot,), run_id="run-2", input_revision="rev-1", tick=3
    )
    values = document.values
    assert values["distinct_case_count"] == 2
    assert values["compromise_count"] == 1
    assert values["restitution_recommendation_count"] == 1
    assert values["accept_count"] == 1
    assert values["refuse_count"] == 1
    assert values["ignored_or_unknown_count"] == 0


def test_empty_and_disabled_inputs_are_absent() -> None:
    document = compute_conflict_mediation(
        (), run_id="run-empty", input_revision="rev-1"
    )
    assert document.availability.value == "absent"


def test_harvest_empty_ledger_reports_enabled_owner() -> None:
    snapshot = harvest_mediation_snapshot(empty_mediation_ledger(AgentId("ada")))
    assert snapshot.enabled is True
    assert snapshot.cases == ()
    document = compute_conflict_mediation(
        (snapshot,), run_id="run-harvest", input_revision="rev-1"
    )
    assert document.availability.value == "absent"


def test_repeated_activity_alone_is_not_stable_role() -> None:
    snapshot = _snapshot(cases=(_case(_CASE_A), _case(_CASE_B)))
    assessments = classify_mediation_roles((snapshot,))
    assert len(assessments) == 1
    assert assessments[0].role_class is MediationRoleClass.REPEATED


def test_independent_recognition_can_reach_candidate_role() -> None:
    expression = MediationRoleExpressionRow(
        owner_id="ada",
        actor_id="bob",
        kind="invite_mediator",
        context_key=_CONTEXT,
        active=True,
        first_tick=1,
        last_tick=2,
    )
    snapshot = _snapshot(
        cases=(_case(_CASE_A),),
        role_expressions=(expression,),
    )
    assessments = classify_mediation_roles((snapshot,))
    assert assessments[0].role_class is MediationRoleClass.CANDIDATE


def test_stable_role_requires_cases_supporters_and_span() -> None:
    first = MediationRoleExpressionRow(
        owner_id="ada",
        actor_id="bob",
        kind="invite_mediator",
        context_key=_CONTEXT,
        active=True,
        first_tick=1,
        last_tick=5,
    )
    second = MediationRoleExpressionRow(
        owner_id="bea",
        actor_id="dave",
        kind="endorse_role",
        context_key=_CONTEXT,
        active=True,
        first_tick=2,
        last_tick=6,
    )
    left = _snapshot(
        cases=(_case(_CASE_A), _case(_CASE_B), _case("d" * 64)),
        role_expressions=(first, second),
    )
    document = compute_mediation_role_emergence(
        (left,), run_id="run-role", input_revision="rev-1", tick=7
    )
    assert document.values["stable_role_count"] == 1
    assert document.values["candidate_role_count"] == 0


def test_partial_coverage_is_published() -> None:
    snapshot = _snapshot(cases=(_case(_CASE_A),), coverage="partial")
    document = compute_conflict_mediation(
        (snapshot,), run_id="run-partial", input_revision="rev-1"
    )
    assert document.availability.value == "partial"
    assert document.values["partial_coverage"] is True


def test_exact_effect_scope_and_ambiguity() -> None:
    attempt = MediationAttemptRow(
        owner_id="ada",
        actor_id="ada",
        case_ref=_CASE_A,
        recommendation_ref="e" * 64,
        recommendation_revision=0,
        status="attempted",
        action_token="give",
        item_token="bread",
        target_ids=("bob",),
        resulting_command_token="give",
        tick=3,
    )
    snapshot = _snapshot(cases=(_case(_CASE_A),), attempts=(attempt,))
    match = compute_conflict_mediation(
        (snapshot,),
        run_id="run-effect",
        input_revision="rev-1",
        tick=4,
        effects=(
            MediationEffectRow(
                case_ref=_CASE_A,
                actor_id="ada",
                recipient_id="bob",
                item_token="bread",
                tick=3,
            ),
        ),
    )
    assert match.values["effected_follow_through_count"] == 1
    wrong_item = compute_conflict_mediation(
        (snapshot,),
        run_id="run-effect",
        input_revision="rev-1",
        tick=4,
        effects=(
            MediationEffectRow(
                case_ref=_CASE_A,
                actor_id="ada",
                recipient_id="bob",
                item_token="stone",
                tick=3,
            ),
        ),
    )
    assert wrong_item.values["effected_follow_through_count"] == 0
