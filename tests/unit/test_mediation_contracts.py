"""Owner-scoped mediation contracts, identity, and locked policy."""

from __future__ import annotations

import pytest

from agents.cognition.mediation import (
    FORBIDDEN_MEDIATION_FIELD_NAMES,
    MEDIATION_POLICY_VERSION,
    MediationAccount,
    MediationAct,
    MediationAttempt,
    MediationAttemptStatus,
    MediationAuthorityAppraisal,
    MediationAuthorityChannel,
    MediationAuthorityComponent,
    MediationCase,
    MediationCaseStatus,
    MediationEvidence,
    MediationEvidenceChannel,
    MediationLedger,
    MediationOutcome,
    MediationOutcomeKind,
    MediationPolicy,
    MediationRecommendation,
    MediationResponse,
    MediationResponseKind,
    MediationRoleExpression,
    MediationRoleExpressionKind,
    default_mediation_policy,
    empty_mediation_ledger,
    mediation_case_id,
    mediation_case_ref,
    mediation_evidence_id,
    mediation_recommendation_id,
    mediation_response_id,
    mediation_role_expression_id,
    require_owner_mediation,
)
from agents.models import AgentId

_OWNER = AgentId("alice")
_MEDIATOR = AgentId("carol")
_PARTY_A = AgentId("bob")
_PARTY_B = AgentId("dave")
_CONTEXT = "a" * 16
_TICK = 3


def _case_ref(owner: AgentId = _OWNER, lineage: str = "first-dispute") -> str:
    return mediation_case_ref(
        owner,
        origin_id=_PARTY_A,
        subject_token="item_share",
        context_key=_CONTEXT,
        inception_tick=_TICK,
        inception_lineage=lineage,
    )


def _evidence(case_ref: str, *, ordinal: int = 0) -> MediationEvidence:
    channel = MediationEvidenceChannel.OBSERVED
    return MediationEvidence(
        evidence_id=mediation_evidence_id(
            case_ref, ordinal, channel, f"lineage-{ordinal}"
        ),
        ordinal=ordinal,
        channel=channel,
        lineage_ref=f"lineage-{ordinal}",
        root_ref=f"root-{ordinal}",
        tick=_TICK + ordinal,
    )


def _case(
    *,
    owner: AgentId = _OWNER,
    status: MediationCaseStatus = MediationCaseStatus.UNRESOLVED,
    parties: tuple[AgentId, ...] = (_PARTY_A, _PARTY_B),
    window_last: int = _TICK + 8,
    evidence: tuple[MediationEvidence, ...] | None = None,
) -> MediationCase:
    ref = _case_ref(owner)
    return MediationCase(
        case_id=mediation_case_id(owner, ref),
        owner_id=owner,
        case_ref=ref,
        subject_token="item_share",
        context_key=_CONTEXT,
        status=status,
        first_tick=_TICK,
        last_tick=_TICK,
        window_first_tick=_TICK,
        window_last_tick=window_last,
        origin_id=_PARTY_A,
        party_ids=parties,
        evidence=(_evidence(ref),) if evidence is None else evidence,
    )


def _recommendation(
    *,
    owner: AgentId = _OWNER,
    revision: int = 0,
    case_ref: str | None = None,
    action_token: str = "give",
    item_token: str | None = "bread",
    terms: tuple[str, ...] = ("return_item",),
    window_last: int = _TICK + 8,
) -> MediationRecommendation:
    ref = _case_ref(owner) if case_ref is None else case_ref
    return MediationRecommendation(
        recommendation_id=mediation_recommendation_id(owner, ref, revision),
        owner_id=owner,
        case_ref=ref,
        revision=revision,
        proposed_actor_id=_PARTY_A,
        action_token=action_token,
        first_tick=_TICK,
        last_tick=_TICK,
        window_first_tick=_TICK,
        window_last_tick=window_last,
        originator_id=_OWNER,
        target_ids=(_PARTY_B,),
        item_token=item_token,
        terms=terms,
    )


def _account(*, owner: AgentId = _OWNER) -> MediationAccount:
    return MediationAccount(
        account_id="a" * 64,
        owner_id=owner,
        actor_id=_PARTY_A,
        case_ref=_case_ref(owner),
        subject_token="item_share",
        claim_token="i_had_it_first",
        direct=True,
        channel=MediationEvidenceChannel.COMMUNICATED,
        root_ref="communication|one",
        first_tick=_TICK,
        last_tick=_TICK,
        evidence_id="b" * 64,
    )


def test_policy_is_locked() -> None:
    policy = default_mediation_policy()
    assert policy.version == MEDIATION_POLICY_VERSION
    assert policy.max_action_window == 32
    assert policy.max_terms == 8
    with pytest.raises(ValueError):
        MediationPolicy(version="mediation.v2")
    with pytest.raises(ValueError):
        MediationPolicy(default_action_window=9)
    with pytest.raises(ValueError):
        MediationPolicy(max_cases=99)


def test_empty_ledger_is_enabled_but_content_free() -> None:
    ledger = empty_mediation_ledger(_OWNER)
    assert ledger.enabled is True
    assert ledger.has_content is False
    assert ledger.coverage == "complete"
    assert ledger.actionable_cases == ()
    assert MEDIATION_POLICY_VERSION in repr(ledger) or "MediationLedger" in repr(ledger)


def test_case_identity_is_stable_and_owner_scoped() -> None:
    first = _case()
    second = _case()
    assert first.case_id == second.case_id
    assert first.case_ref == second.case_ref
    other_owner = mediation_case_id(_PARTY_A, first.case_ref)
    assert other_owner != first.case_id


def test_materially_distinct_lineages_produce_distinct_references() -> None:
    assert _case_ref(lineage="first") != _case_ref(lineage="second")
    left = mediation_case_ref(
        _OWNER,
        origin_id=_PARTY_A,
        subject_token="item_share",
        context_key=_CONTEXT,
        inception_tick=_TICK,
        inception_lineage="same",
    )
    right = mediation_case_ref(
        _OWNER,
        origin_id=_PARTY_B,
        subject_token="item_share",
        context_key=_CONTEXT,
        inception_tick=_TICK,
        inception_lineage="same",
    )
    assert left != right


def test_recommendation_revisions_are_materially_distinct() -> None:
    first = _recommendation(revision=0)
    second = _recommendation(revision=1)
    assert first.recommendation_id != second.recommendation_id
    assert second.revision == 1


def test_forged_owner_is_rejected() -> None:
    with pytest.raises(ValueError, match="owner_mismatch"):
        MediationLedger(owner_id=_OWNER, cases=(_case(owner=_PARTY_A),))
    with pytest.raises(ValueError, match="id_mismatch"):
        MediationCase(
            case_id=mediation_case_id(
                _OWNER,
                mediation_case_ref(
                    _OWNER,
                    origin_id=_PARTY_A,
                    subject_token="item_share",
                    context_key=_CONTEXT,
                    inception_tick=_TICK,
                    inception_lineage="first-dispute",
                ),
            ),
            owner_id=_OWNER,
            case_ref=_case_ref(lineage="other"),
            subject_token="item_share",
            context_key=_CONTEXT,
            status=MediationCaseStatus.UNRESOLVED,
            first_tick=_TICK,
            last_tick=_TICK,
            window_first_tick=_TICK,
            window_last_tick=_TICK + 1,
        )
    with pytest.raises(TypeError):
        require_owner_mediation(object(), _OWNER, field_name="mediation")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_mediation(
            empty_mediation_ledger(_PARTY_A), _OWNER, field_name="mediation"
        )


def test_repr_redacts_account_terms_and_claims() -> None:
    account = _account()
    text = repr(account)
    assert "i_had_it_first" not in text
    assert "item_share" not in text
    recommendation = _recommendation()
    text = repr(recommendation)
    assert "return_item" not in text
    assert "bread" not in text
    ledger = MediationLedger(owner_id=_OWNER, accounts=(account,))
    assert "i_had_it_first" not in repr(ledger)


def test_invalid_windows_are_rejected() -> None:
    with pytest.raises(ValueError, match="before_first_tick"):
        _case(window_last=_TICK - 1)
    with pytest.raises(ValueError, match="before_first_tick"):
        _recommendation(window_last=_TICK - 1)


def test_term_cap_is_enforced() -> None:
    with pytest.raises(ValueError, match="cap_exceeded"):
        _recommendation(terms=tuple(f"term_{index}" for index in range(9)))


def test_unknown_actor_and_party_validation() -> None:
    with pytest.raises(ValueError, match="invalid_type"):
        MediationResponse(
            response_id="c" * 64,
            owner_id=_OWNER,
            actor_id="bob",  # type: ignore[arg-type]
            case_ref=_case_ref(),
            kind=MediationResponseKind.REFUSE,
            tick=_TICK,
            evidence_id="d" * 64,
        )
    with pytest.raises(ValueError, match="duplicate_id"):
        _case(parties=(_PARTY_A, _PARTY_A))
    with pytest.raises(ValueError, match="cap_exceeded"):
        _case(parties=tuple(AgentId(f"party{index}") for index in range(9)))


def test_response_scope_rules() -> None:
    case_ref = _case_ref()
    with pytest.raises(ValueError, match="required_for_acceptance"):
        MediationResponse(
            response_id=mediation_response_id(
                _OWNER, case_ref, _PARTY_A, MediationResponseKind.ACCEPT, 0
            ),
            owner_id=_OWNER,
            actor_id=_PARTY_A,
            case_ref=case_ref,
            kind=MediationResponseKind.ACCEPT,
            tick=_TICK,
            evidence_id="d" * 64,
        )
    accepted = MediationResponse(
        response_id=mediation_response_id(
            _OWNER, case_ref, _PARTY_A, MediationResponseKind.ACCEPT, 0
        ),
        owner_id=_OWNER,
        actor_id=_PARTY_A,
        case_ref=case_ref,
        kind=MediationResponseKind.ACCEPT,
        tick=_TICK,
        evidence_id="d" * 64,
        recommendation_ref=_recommendation().recommendation_id,
        recommendation_revision=0,
        undertaking_token="give_bread",
    )
    assert accepted.direct is True
    with pytest.raises(ValueError, match="required_for_withdrawal"):
        MediationResponse(
            response_id="e" * 64,
            owner_id=_OWNER,
            actor_id=_PARTY_A,
            case_ref=case_ref,
            kind=MediationResponseKind.WITHDRAW,
            tick=_TICK,
            evidence_id="f" * 64,
        )
    with pytest.raises(ValueError, match="required_for_counterproposal"):
        MediationResponse(
            response_id="e" * 64,
            owner_id=_OWNER,
            actor_id=_PARTY_A,
            case_ref=case_ref,
            kind=MediationResponseKind.COUNTERPROPOSE,
            tick=_TICK,
            evidence_id="f" * 64,
        )


def test_role_expressions_are_separate_from_responses() -> None:
    with pytest.raises(ValueError, match="required_for_withdrawal"):
        MediationRoleExpression(
            expression_id="a" * 64,
            owner_id=_OWNER,
            actor_id=_PARTY_A,
            kind=MediationRoleExpressionKind.WITHDRAW_ROLE_ENDORSEMENT,
            context_key=_CONTEXT,
            first_tick=_TICK,
            last_tick=_TICK,
            evidence_id="b" * 64,
        )
    expression = MediationRoleExpression(
        expression_id=mediation_role_expression_id(
            _OWNER, _PARTY_A, MediationRoleExpressionKind.INVITE_MEDIATOR, _CONTEXT, 0
        ),
        owner_id=_OWNER,
        actor_id=_PARTY_A,
        kind=MediationRoleExpressionKind.INVITE_MEDIATOR,
        context_key=_CONTEXT,
        first_tick=_TICK,
        last_tick=_TICK,
        evidence_id="b" * 64,
        function_token="conflict_mediation",
    )
    assert expression.function_token == "conflict_mediation"
    assert {item.value for item in MediationAct} == {
        "hear_dispute",
        "request_accounts",
        "propose_compromise",
        "vouch",
        "mediate",
        "recommend_restitution",
    }


def test_attempt_and_outcome_are_claim_scoped() -> None:
    attempt = MediationAttempt(
        attempt_id="a" * 64,
        owner_id=_OWNER,
        case_ref=_case_ref(),
        actor_id=_OWNER,
        status=MediationAttemptStatus.ATTEMPTED,
        tick=_TICK,
        recommendation_ref=_recommendation().recommendation_id,
        recommendation_revision=0,
        action_token="give",
        target_ids=(_PARTY_B,),
        item_token="bread",
    )
    assert attempt.status is MediationAttemptStatus.ATTEMPTED
    outcome = MediationOutcome(
        outcome_id="b" * 64,
        owner_id=_OWNER,
        case_ref=_case_ref(),
        kind=MediationOutcomeKind.CLAIMED,
        claimed=True,
        first_tick=_TICK,
        last_tick=_TICK,
    )
    assert outcome.claimed is True


def test_authority_components_keep_unavailable_sources_absent() -> None:
    available = MediationAuthorityComponent(
        channel=MediationAuthorityChannel.RELATIONSHIP,
        available=True,
        strength=0.4,
        uncertainty=0.2,
        provenance=("trust",),
    )
    unavailable = MediationAuthorityComponent(
        channel=MediationAuthorityChannel.INSTITUTION,
        available=False,
        strength=0.0,
        uncertainty=1.0,
    )
    appraisal = MediationAuthorityAppraisal(
        owner_id=_OWNER,
        mediator_id=_MEDIATOR,
        context_key=_CONTEXT,
        components=(available, unavailable),
    )
    assert appraisal.available_channels == (MediationAuthorityChannel.RELATIONSHIP,)
    assert appraisal.unavailable_channels == (MediationAuthorityChannel.INSTITUTION,)
    with pytest.raises(ValueError, match="unavailable_nonzero"):
        MediationAuthorityComponent(
            channel=MediationAuthorityChannel.NORM,
            available=False,
            strength=0.5,
            uncertainty=0.0,
        )


def test_forbidden_mediation_field_names_are_declared() -> None:
    assert "verdict" in FORBIDDEN_MEDIATION_FIELD_NAMES
    assert "binding" in FORBIDDEN_MEDIATION_FIELD_NAMES
    assert "dispute_registry" in FORBIDDEN_MEDIATION_FIELD_NAMES


def test_case_actionability_requires_two_known_others() -> None:
    actionable = _case(parties=(_PARTY_A, _PARTY_B))
    assert actionable.actionable is True
    assert actionable.third_party_actionable is True
    partial = _case(parties=(_PARTY_A,))
    assert partial.actionable is False
    with pytest.raises(ValueError, match="duplicate_id"):
        _case(parties=(_PARTY_A, _PARTY_A))
