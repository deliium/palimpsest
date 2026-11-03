"""V4-07 rule, authority, mediation references, and deliberation hooks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DisputeAuthorityKind,
    DisputeCase,
    DisputeClaim,
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeKind,
    DisputeLedger,
    DisputeMediationLinkStatus,
    DisputeProvenance,
    DisputeResolutionSource,
    DisputeResolutionStatus,
    DisputeRuleApplicability,
    DisputeRuleReferenceStatus,
    DisputeStatus,
    DisputeSubjectKind,
    DisputeTestimonyChannel,
    derive_authority_references,
    derive_case_status,
    derive_rule_references,
    dispute_case_id,
    dispute_case_ref,
    dispute_case_summary,
    dispute_claim_id,
    dispute_claim_ref,
    dispute_direction_preference,
    dispute_response_penalties,
    dispute_subject_digest,
    link_mediation_references,
)
from agents.cognition.formal_rules import FormalRuleConstraintKind
from agents.models import AgentId
from tests.unit.formal_rule_helpers import make_ledger
from world._rules import COMMAND_RULE_MATRIX

pytestmark = pytest.mark.unit

OWNER = "agent-1"
OTHER = "agent-2"
SUBJECT_TOKEN = "commitment-1"
SUBJECT_DIGEST = dispute_subject_digest(DisputeSubjectKind.COMMITMENT, SUBJECT_TOKEN)
CASE_REF = dispute_case_ref(SUBJECT_TOKEN, (OWNER, OTHER))


def _case(
    *,
    context_key: str = "context-1",
    status: DisputeStatus = DisputeStatus.OPEN,
) -> DisputeCase:
    return DisputeCase(
        case_id=dispute_case_id(OWNER, CASE_REF),
        owner_id=OWNER,
        case_ref=CASE_REF,
        kind=DisputeKind.CONTESTED_DEBT,
        subject_kind=DisputeSubjectKind.COMMITMENT,
        subject_token=SUBJECT_TOKEN,
        subject_digest=SUBJECT_DIGEST,
        context_key=context_key,
        party_ids=(OWNER, OTHER),
        claimant_ids=(OWNER,),
        respondent_ids=(OTHER,),
        status=status,
        first_tick=2,
        last_tick=2,
        window_first_tick=2,
        window_last_tick=66,
    )


def _claim(
    *,
    claimant: str = OWNER,
    respondent: str = OTHER,
    role: DisputeClaimRole = DisputeClaimRole.CLAIM,
    polarity: DisputeClaimPolarity = DisputeClaimPolarity.AFFIRM,
    claim_kind: DisputeClaimKind = DisputeClaimKind.DEBT_OWED,
    action: str | None = "give",
    rule_token: str | None = None,
    counters: str | None = None,
    tick: int = 2,
) -> DisputeClaim:
    ref = dispute_claim_ref(
        CASE_REF, claimant, role, claim_kind, polarity, SUBJECT_DIGEST
    )
    return DisputeClaim(
        claim_id=dispute_claim_id(OWNER, ref),
        claim_ref=ref,
        case_ref=CASE_REF,
        owner_id=OWNER,
        claimant_id=claimant,
        respondent_id=respondent,
        role=role,
        claim_kind=claim_kind,
        polarity=polarity,
        subject_kind=DisputeSubjectKind.COMMITMENT,
        subject_token=SUBJECT_TOKEN,
        subject_digest=SUBJECT_DIGEST,
        action_token=action,
        item_token=None,
        quantity=0,
        terms_digest=None,
        counters_claim_ref=counters,
        rule_reference_token=rule_token,
        evidence_ids=(),
        provenance=DisputeProvenance.SELF_ASSERTED,
        confidence=0.7,
        first_tick=tick,
        last_tick=tick,
    )


def _ledger(
    *,
    rule_token: str | None = None,
    claim_kind: DisputeClaimKind = DisputeClaimKind.DEBT_OWED,
    action: str | None = "give",
    competing: bool = False,
) -> DisputeLedger:
    claim = _claim(claim_kind=claim_kind, action=action, rule_token=rule_token)
    claims: tuple[DisputeClaim, ...] = (claim,)
    if competing:
        claims = (
            claim,
            _claim(
                claimant=OTHER,
                respondent=OWNER,
                role=DisputeClaimRole.COUNTERCLAIM,
                polarity=DisputeClaimPolarity.DENY,
                claim_kind=claim_kind,
                action=action,
                counters=claim.claim_ref,
                tick=3,
            ),
        )
    return DisputeLedger(
        owner_id=OWNER,
        cases=(_case(),),
        claims=claims,
        first_observed_tick=2,
        last_observed_tick=3,
        observation_count=2,
    )


def test_rule_reference_resolves_against_owner_formal_rules() -> None:
    formal = make_ledger(
        owner=OWNER,
        action="give",
        constraint=FormalRuleConstraintKind.OBLIGATION,
        ticks=(0, 1),
    )
    rule = formal.rules[0]
    ledger = _ledger(rule_token=f"{rule.rule_id}@2")
    updated = derive_rule_references(ledger, formal_rules=formal, owner_id=OWNER)
    assert len(updated.rule_references) == 1
    reference = updated.rule_references[0]
    assert reference.status is DisputeRuleReferenceStatus.RESOLVED
    assert reference.version_number == 2
    assert reference.system_ref == rule.system_id
    assert reference.constraint_kind == "obligation"
    assert reference.applicability is DisputeRuleApplicability.APPLIES


def test_rule_version_lookup_requires_exact_contiguous_version() -> None:
    formal = make_ledger(owner=OWNER, action="give", ticks=(0,))
    rule = formal.rules[0]
    ledger = _ledger(rule_token=f"{rule.rule_id}@3")
    updated = derive_rule_references(ledger, formal_rules=formal, owner_id=OWNER)
    assert (
        updated.rule_references[0].status is DisputeRuleReferenceStatus.VERSION_MISMATCH
    )
    assert updated.rule_references[0].version_number == 3


def test_self_mediator_uses_self_authority_without_calling_appraisal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mediation = SimpleNamespace(
        recommendations=(
            SimpleNamespace(
                case_ref="mediation-1",
                revision=0,
                originator_id=AgentId(OWNER),
                proposed_actor_id=AgentId(OWNER),
                action_token="give",
                target_ids=(AgentId(OTHER),),
            ),
        )
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("self appraisal must not run")

    monkeypatch.setattr("agents.cognition.mediation.appraise_mediation_authority", fail)
    updated = derive_authority_references(
        _ledger(),
        owner_id=OWNER,
        offices=None,
        institution_concepts=None,
        organization_concepts=None,
        collective_decisions=None,
        mediation=mediation,
        tick=3,
    )
    assert len(updated.authority_references) == 1
    reference = updated.authority_references[0]
    assert reference.authority_kind is DisputeAuthorityKind.SELF
    assert reference.strength == 1.0
    assert reference.uncertainty == 0.0


def test_missing_rule_is_orphaned_and_claim_survives() -> None:
    ledger = _ledger(rule_token="frl-0123456789abcdef@1")
    updated = derive_rule_references(ledger, formal_rules=None, owner_id=OWNER)
    assert updated.claims[0].claim_ref == ledger.claims[0].claim_ref
    assert updated.rule_references[0].status is DisputeRuleReferenceStatus.ORPHANED
    assert updated.rule_references[0].provenance is DisputeProvenance.ORPHANED


def test_version_mismatch_is_not_silently_upgraded() -> None:
    formal = make_ledger(owner=OWNER, action="give", ticks=(0, 1))
    rule = formal.rules[0]
    ledger = _ledger(rule_token=f"{rule.rule_id}@99")
    updated = derive_rule_references(ledger, formal_rules=formal, owner_id=OWNER)
    reference = updated.rule_references[0]
    assert reference.status is DisputeRuleReferenceStatus.VERSION_MISMATCH
    assert reference.version_number == 99


def test_office_institution_and_organization_authority_refs_are_beliefs() -> None:
    case = _case()
    offices = SimpleNamespace(
        concepts=(
            SimpleNamespace(
                office_id="office-1",
                function=SimpleNamespace(value="conflict_mediation"),
                context_key=case.context_key,
                endorsement_strength=0.8,
                expectation_strength=0.6,
                status=SimpleNamespace(value="recognized"),
                occupants=(),
            ),
        )
    )
    institutions = SimpleNamespace(
        concepts=(
            SimpleNamespace(
                concept_id="institution-1",
                status=SimpleNamespace(value="recognized"),
                anchor_digests=(case.subject_digest,),
                legitimacy_belief=0.8,
                social_expectation=0.6,
            ),
        )
    )
    organizations = SimpleNamespace(
        concepts=(
            SimpleNamespace(
                organization_id="org-1",
                strength=0.7,
                procedures=(object(),),
                records=(),
                roles=(),
            ),
        )
    )
    decisions = SimpleNamespace(
        proposals=(SimpleNamespace(action_token="give", proposal_ref="proposal-1"),)
    )
    updated = derive_authority_references(
        _ledger(),
        owner_id=OWNER,
        offices=offices,
        institution_concepts=institutions,
        organization_concepts=organizations,
        collective_decisions=decisions,
        mediation=None,
        tick=3,
    )
    kinds = {row.authority_kind for row in updated.authority_references}
    assert {
        DisputeAuthorityKind.OFFICE,
        DisputeAuthorityKind.INSTITUTION,
        DisputeAuthorityKind.ORGANIZATION,
        DisputeAuthorityKind.COLLECTIVE_DECISION,
    } <= kinds
    assert all(0.0 <= row.strength <= 1.0 for row in updated.authority_references)
    assert not any(hasattr(row, "binding") for row in updated.authority_references)


def test_mediation_recommendation_becomes_dispute_resolution_belief() -> None:
    mediation = SimpleNamespace(
        cases=(
            SimpleNamespace(
                case_ref="mediation-1",
                subject_token=SUBJECT_TOKEN,
                party_ids=(AgentId(OWNER), AgentId(OTHER)),
                status=SimpleNamespace(value="unresolved"),
            ),
        ),
        recommendations=(
            SimpleNamespace(
                case_ref="mediation-1",
                revision=0,
                recommendation_id="recommendation-1",
                originator_id=AgentId(OTHER),
                proposed_actor_id=AgentId(OWNER),
                action_token="give",
                target_ids=(AgentId(OTHER),),
                item_token="item-1",
                quantity=1,
            ),
        ),
        responses=(),
        outcomes=(),
    )
    updated = link_mediation_references(
        _ledger(), mediation=mediation, owner_id=OWNER, tick=3
    )
    assert len(updated.mediation_references) == 1
    link = updated.mediation_references[0]
    assert link.link_status is DisputeMediationLinkStatus.LINKED
    assert link.recommendation_ref == "recommendation-1"
    assert len(updated.resolutions) == 1
    resolution = updated.resolutions[0]
    assert resolution.source is DisputeResolutionSource.MEDIATOR
    assert resolution.proposer_id == OTHER
    assert resolution.status is DisputeResolutionStatus.PROPOSED


def test_competing_claims_are_not_reconciled() -> None:
    formal = make_ledger(owner=OWNER, action="give", ticks=(0,))
    rule = formal.rules[0]
    ledger = _ledger(rule_token=f"{rule.rule_id}@1", competing=True)
    updated = derive_rule_references(ledger, formal_rules=formal, owner_id=OWNER)
    assert len(updated.claims) == 2
    assert {claim.claimant_id for claim in updated.claims} == {OWNER, OTHER}
    assert len(updated.counterclaims) == 1


def test_case_status_never_reports_unhedged_resolution() -> None:
    ledger = _ledger()
    status = derive_case_status(
        ledger.cases[0],
        ledger.claims,
        ledger.resolutions,
        ledger.resolution_responses,
        3,
    )
    assert status is not DisputeStatus.APPARENTLY_RESOLVED
    assert "resolved" != status.value
    assert status.value != "resolved"


def test_deliberation_hooks_do_not_construct_commands() -> None:
    ledger = _ledger()
    direction = dispute_direction_preference(ledger, owner_id=OWNER, tick=3)
    assert direction
    assert all(0.0 < value <= 0.25 for value in direction.values())
    assert all(type(value) is float for value in direction.values())
    assert not any(
        isinstance(value, type) and value.__name__.endswith("Command")
        for value in direction.values()
    )

    penalties = dispute_response_penalties(
        ledger, owner_id=OWNER, resolution_ref="unknown", tick=3
    )
    assert penalties == {"accept": -0.2}
    assert not any(
        isinstance(value, type) and value.__name__.endswith("Command")
        for value in penalties.values()
    )
    assert not any("Dispute" in command.__name__ for command in COMMAND_RULE_MATRIX)


def test_case_summary_is_counts_only() -> None:
    ledger = _ledger()
    summary = dispute_case_summary(ledger.cases[0], ledger.claims, ledger.resolutions)
    assert summary == {
        "active_claim_count": 1,
        "active_resolution_count": 0,
        "claim_count": 1,
        "counterclaim_count": 0,
        "resolution_count": 0,
    }


def test_testimony_channel_remains_independent() -> None:
    assert DisputeTestimonyChannel.DIRECT.value == "direct"
    assert DisputeTestimonyChannel.COMMUNICATED.value == "communicated"
