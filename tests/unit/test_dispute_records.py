"""V4-07 dispute records, ledger invariants, and deterministic truncation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DISPUTE_FORBIDDEN_FIELD_NAMES,
    DisputeAuthorityKind,
    DisputeAuthorityReference,
    DisputeCase,
    DisputeClaim,
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeError,
    DisputeEvidence,
    DisputeEvidenceChannel,
    DisputeEvidenceReferenceKind,
    DisputeKind,
    DisputeLedger,
    DisputeMediationLinkStatus,
    DisputeMediationReference,
    DisputeProvenance,
    DisputeResolution,
    DisputeResolutionResponse,
    DisputeResolutionResponseKind,
    DisputeResolutionSource,
    DisputeResolutionStatus,
    DisputeResolutionTerm,
    DisputeResolutionTermKind,
    DisputeRuleApplicability,
    DisputeRuleInterpretation,
    DisputeRuleReference,
    DisputeRuleReferenceStatus,
    DisputeStatus,
    DisputeSubjectKind,
    DisputeTestimony,
    DisputeTestimonyChannel,
    dispute_authority_reference_id,
    dispute_case_id,
    dispute_case_ref,
    dispute_claim_id,
    dispute_claim_ref,
    dispute_evidence_id,
    dispute_ledger_digest,
    dispute_mediation_reference_id,
    dispute_resolution_id,
    dispute_resolution_ref,
    dispute_response_id,
    dispute_rule_reference_id,
    dispute_subject_digest,
    dispute_terms_digest,
    dispute_testimony_id,
    empty_dispute_ledger,
    enforce_dispute_limits,
    require_owner_disputes,
)

pytestmark = pytest.mark.unit

OWNER = "agent-1"
OTHER = "agent-2"
THIRD = "agent-3"
SUBJECT_TOKEN = "item-1"
SUBJECT_DIGEST = dispute_subject_digest(DisputeSubjectKind.ITEM, SUBJECT_TOKEN)
CASE_REF = dispute_case_ref(SUBJECT_TOKEN, (OWNER, OTHER))


def _code(call: Callable[[], object]) -> str:
    with pytest.raises(DisputeError) as error:
        call()
    return error.value.code


def _case(
    *,
    case_ref: str = CASE_REF,
    parties: tuple[str, ...] = (OWNER, OTHER),
    kind: DisputeKind = DisputeKind.OWNERSHIP_CLAIM,
    status: DisputeStatus = DisputeStatus.OPEN,
    first_tick: int = 1,
    last_tick: int = 1,
) -> DisputeCase:
    return DisputeCase(
        case_id=dispute_case_id(OWNER, case_ref),
        owner_id=OWNER,
        case_ref=case_ref,
        kind=kind,
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token=SUBJECT_TOKEN,
        subject_digest=SUBJECT_DIGEST,
        context_key="context-1",
        party_ids=parties,
        claimant_ids=(OWNER,),
        respondent_ids=tuple(party for party in parties if party != OWNER),
        status=status,
        first_tick=first_tick,
        last_tick=last_tick,
        window_first_tick=first_tick,
        window_last_tick=first_tick + 64,
    )


def _claim(
    *,
    claimant: str = OWNER,
    respondent: str = OTHER,
    role: DisputeClaimRole = DisputeClaimRole.CLAIM,
    polarity: DisputeClaimPolarity = DisputeClaimPolarity.AFFIRM,
    claim_kind: DisputeClaimKind = DisputeClaimKind.ITEM_OWNED,
    subject_token: str = SUBJECT_TOKEN,
    subject_digest: str = SUBJECT_DIGEST,
    counters: str | None = None,
    active: bool = True,
    tick: int = 1,
    quantity: int = 1,
    evidence_ids: tuple[str, ...] = (),
) -> DisputeClaim:
    ref = dispute_claim_ref(
        CASE_REF, claimant, role, claim_kind, polarity, subject_digest
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
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token=subject_token,
        subject_digest=subject_digest,
        action_token=None,
        item_token=subject_token,
        quantity=quantity,
        terms_digest=None,
        counters_claim_ref=counters,
        rule_reference_token=None,
        evidence_ids=evidence_ids,
        provenance=DisputeProvenance.SELF_ASSERTED,
        confidence=0.5,
        first_tick=tick,
        last_tick=tick,
        active=active,
    )


def _term(
    *,
    party: str = OWNER,
    counterparty: str = OTHER,
    item_token: str = SUBJECT_TOKEN,
) -> DisputeResolutionTerm:
    return DisputeResolutionTerm(
        term_kind=DisputeResolutionTermKind.TRANSFER_ITEM,
        party_id=party,
        counterparty_id=counterparty,
        item_token=item_token,
        quantity=1,
    )


def _resolution(
    *,
    proposer: str = OWNER,
    terms: tuple[DisputeResolutionTerm, ...] | None = None,
    status: DisputeResolutionStatus = DisputeResolutionStatus.PROPOSED,
    tick: int = 2,
    case_ref: str = CASE_REF,
) -> DisputeResolution:
    ordered = terms if terms is not None else (_term(),)
    digest = dispute_terms_digest(ordered)
    ref = dispute_resolution_ref(case_ref, proposer, digest)
    return DisputeResolution(
        resolution_id=dispute_resolution_id(OWNER, ref),
        resolution_ref=ref,
        case_ref=case_ref,
        owner_id=OWNER,
        proposer_id=proposer,
        source=DisputeResolutionSource.NEGOTIATED,
        terms=ordered,
        terms_digest=digest,
        status=status,
        first_tick=tick,
        last_tick=tick,
        expires_tick=tick + 64,
        provenance=DisputeProvenance.SELF_ASSERTED,
    )


def _testimony(claim: DisputeClaim, *, tick: int = 1) -> DisputeTestimony:
    return DisputeTestimony(
        testimony_id=dispute_testimony_id(
            OWNER,
            CASE_REF,
            claim.claim_ref,
            OTHER,
            DisputeTestimonyChannel.DIRECT,
            "root-1",
            tick,
        ),
        case_ref=CASE_REF,
        claim_ref=claim.claim_ref,
        owner_id=OWNER,
        speaker_id=OTHER,
        channel=DisputeTestimonyChannel.DIRECT,
        root_ref="root-1",
        independently_evidenced=True,
        evidence_id=None,
        tick=tick,
        provenance=DisputeProvenance.COMMUNICATED,
    )


def _evidence(claim: DisputeClaim, *, ordinal: int = 0) -> DisputeEvidence:
    reference_id = f"event-{ordinal}"
    return DisputeEvidence(
        evidence_id=dispute_evidence_id(
            OWNER,
            CASE_REF,
            claim.claim_ref,
            DisputeEvidenceChannel.OBSERVED,
            DisputeEvidenceReferenceKind.OBSERVED_OCCURRENCE,
            reference_id,
            ordinal,
        ),
        case_ref=CASE_REF,
        claim_ref=claim.claim_ref,
        owner_id=OWNER,
        channel=DisputeEvidenceChannel.OBSERVED,
        reference_kind=DisputeEvidenceReferenceKind.OBSERVED_OCCURRENCE,
        reference_id=reference_id,
        tick=1,
        actor_id=OTHER,
        independently_evidenced=True,
        provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
    )


def _rule_reference(
    claim: DisputeClaim,
    *,
    interpretation: DisputeRuleInterpretation = DisputeRuleInterpretation.LITERAL,
    version_number: int = 1,
) -> DisputeRuleReference:
    return DisputeRuleReference(
        rule_reference_id=dispute_rule_reference_id(
            OWNER,
            CASE_REF,
            "frs-0123456789abcdef",
            "frl-0123456789abcdef",
            version_number,
            interpretation,
        ),
        case_ref=CASE_REF,
        claim_ref=claim.claim_ref,
        owner_id=OWNER,
        system_ref="frs-0123456789abcdef",
        rule_id="frl-0123456789abcdef",
        version_number=version_number,
        constraint_kind="prohibition",
        scope_digest=SUBJECT_DIGEST,
        applicability=DisputeRuleApplicability.UNCERTAIN,
        interpretation=interpretation,
        status=DisputeRuleReferenceStatus.ORPHANED,
        provenance=DisputeProvenance.ORPHANED,
        first_tick=1,
        last_tick=1,
    )


def _authority(reference: str = "office-1") -> DisputeAuthorityReference:
    return DisputeAuthorityReference(
        authority_reference_id=dispute_authority_reference_id(
            OWNER, CASE_REF, DisputeAuthorityKind.OFFICE, reference
        ),
        case_ref=CASE_REF,
        owner_id=OWNER,
        authority_kind=DisputeAuthorityKind.OFFICE,
        reference_id=reference,
        strength=0.5,
        uncertainty=0.5,
        provenance=DisputeProvenance.DERIVED_FROM_OBSERVATION,
        dissenting=False,
        first_tick=1,
        last_tick=1,
    )


def _mediation(reference: str = "mediation-1") -> DisputeMediationReference:
    return DisputeMediationReference(
        mediation_reference_id=dispute_mediation_reference_id(
            OWNER, CASE_REF, reference, "none"
        ),
        case_ref=CASE_REF,
        owner_id=OWNER,
        mediation_case_ref=reference,
        recommendation_ref=None,
        response_ref=None,
        outcome_ref=None,
        link_status=DisputeMediationLinkStatus.ORPHANED,
        provenance=DisputeProvenance.ORPHANED,
        first_tick=1,
        last_tick=1,
    )


def _response(
    resolution: DisputeResolution,
    *,
    party: str = OTHER,
    kind: DisputeResolutionResponseKind = DisputeResolutionResponseKind.ACCEPT,
    tick: int = 3,
    active: bool = True,
) -> DisputeResolutionResponse:
    return DisputeResolutionResponse(
        response_id=dispute_response_id(
            OWNER, resolution.resolution_ref, party, kind, tick
        ),
        resolution_id=resolution.resolution_id,
        resolution_ref=resolution.resolution_ref,
        case_ref=CASE_REF,
        owner_id=OWNER,
        party_id=party,
        kind=kind,
        tick=tick,
        terms_digest=resolution.terms_digest,
        active=active,
        provenance=DisputeProvenance.COMMUNICATED,
    )


def test_empty_ledger_is_owner_scoped_and_disabled_without_content() -> None:
    ledger = empty_dispute_ledger(OWNER)
    assert ledger.enabled is True
    assert ledger.has_content is False
    assert ledger.coverage == "complete"
    assert ledger.open_cases == ()
    assert ledger.counterclaims == ()
    assert require_owner_disputes(ledger, OWNER, field_name="x") is ledger
    assert require_owner_disputes(None, OWNER, field_name="x") is None
    assert (
        _code(lambda: require_owner_disputes(ledger, OTHER, field_name="x"))
        == "dispute_owner_mismatch"
    )
    with pytest.raises(TypeError):
        require_owner_disputes(object(), OWNER, field_name="x")


def test_claim_and_counterclaim_are_separate_and_attributed() -> None:
    claim = _claim()
    counter = _claim(
        claimant=OTHER,
        respondent=OWNER,
        role=DisputeClaimRole.COUNTERCLAIM,
        polarity=DisputeClaimPolarity.DENY,
        counters=claim.claim_ref,
        tick=2,
    )
    ledger = DisputeLedger(
        owner_id=OWNER,
        cases=(_case(),),
        claims=(claim, counter),
        first_observed_tick=1,
        last_observed_tick=2,
        observation_count=2,
    )
    assert {row.claimant_id for row in ledger.claims} == {OWNER, OTHER}
    assert len(ledger.counterclaims) == 1
    assert ledger.counterclaims[0].counters_claim_ref == claim.claim_ref
    assert ledger.claims[0].claimant_id != ledger.claims[1].claimant_id
    assert not hasattr(ledger.claims[0], "verdict")
    assert not hasattr(ledger.cases[0], "winner")


def test_unknown_case_claim_or_resolution_reference_fails_closed() -> None:
    claim = _claim()
    assert (
        _code(lambda: DisputeLedger(owner_id=OWNER, claims=(claim,)))
        == "dispute_unknown_reference"
    )

    orphan_claim = _claim(
        subject_token="other-item",
        subject_digest=dispute_subject_digest(DisputeSubjectKind.ITEM, "other-item"),
    )
    orphan_claim = replace(
        orphan_claim,
        case_ref=dispute_case_ref("other-item", (OWNER, OTHER)),
    )
    assert (
        _code(
            lambda: DisputeLedger(
                owner_id=OWNER, cases=(_case(),), claims=(orphan_claim,)
            )
        )
        == "dispute_unknown_reference"
    )

    resolution = _resolution(case_ref=dispute_case_ref("other-item", (OWNER, OTHER)))
    assert (
        _code(
            lambda: DisputeLedger(
                owner_id=OWNER, cases=(_case(),), resolutions=(resolution,)
            )
        )
        == "dispute_unknown_reference"
    )


def test_party_and_quantity_bounds() -> None:
    too_many = tuple(f"agent-{index}" for index in range(9))
    assert (
        _code(lambda: dispute_case_ref(SUBJECT_TOKEN, too_many))
        == "dispute_party_limit"
    )
    assert _code(lambda: _claim(quantity=4)) == "dispute_invalid_ordinal"

    claim = _claim()
    with pytest.raises(DisputeError) as error:
        DisputeClaim(
            **{
                **{field.name: getattr(claim, field.name) for field in fields(claim)},
                "confidence": 1.5,
            }
        )
    assert error.value.code == "dispute_invalid_record"

    outsider = _claim(claimant=THIRD, respondent=OTHER)
    assert (
        _code(
            lambda: DisputeLedger(owner_id=OWNER, cases=(_case(),), claims=(outsider,))
        )
        == "dispute_unknown_reference"
    )


def test_forbidden_justice_fields_are_rejected_recursively() -> None:
    for model in (
        DisputeCase,
        DisputeClaim,
        DisputeTestimony,
        DisputeEvidence,
        DisputeRuleReference,
        DisputeAuthorityReference,
        DisputeMediationReference,
        DisputeResolutionTerm,
        DisputeResolution,
        DisputeResolutionResponse,
        DisputeLedger,
    ):
        names = {field.name for field in fields(model)}
        assert names.isdisjoint(DISPUTE_FORBIDDEN_FIELD_NAMES)

    assert (
        _code(
            lambda: DisputeLedger(
                owner_id=OWNER,
                cases=(SimpleNamespace(verdict="guilty"),),  # type: ignore[arg-type]
            )
        )
        == "dispute_forbidden_field"
    )
    assert (
        _code(
            lambda: DisputeLedger(
                owner_id=OWNER,
                cases=(SimpleNamespace(inner=SimpleNamespace(liable=True)),),  # type: ignore[arg-type]
            )
        )
        == "dispute_forbidden_field"
    )


def test_truncation_is_explicit_and_deterministic() -> None:
    cases = tuple(
        _case(case_ref=dispute_case_ref(f"item-{index}", (OWNER, OTHER)))
        for index in range(17)
    )
    ledger = DisputeLedger(owner_id=OWNER, cases=cases)
    first = enforce_dispute_limits(ledger)
    second = enforce_dispute_limits(ledger)
    assert first == second
    assert first.pruned_case_count == 1
    assert "dispute_truncated" in first.notices
    assert first.coverage == "partial"
    assert dispute_ledger_digest(first) == dispute_ledger_digest(second)


def test_each_ledger_cap_increments_its_pruned_count() -> None:
    claims = tuple(
        _claim(
            subject_token=f"item-{index}",
            subject_digest=dispute_subject_digest(
                DisputeSubjectKind.ITEM, f"item-{index}"
            ),
            tick=index,
        )
        for index in range(17)
    )
    claim_ledger = enforce_dispute_limits(
        DisputeLedger(owner_id=OWNER, cases=(_case(),), claims=claims)
    )
    assert claim_ledger.pruned_claim_count == 1

    base_claim = _claim()
    testimony = tuple(_testimony(base_claim, tick=index) for index in range(33))
    testimony_ledger = enforce_dispute_limits(
        DisputeLedger(
            owner_id=OWNER,
            cases=(_case(),),
            claims=(base_claim,),
            testimony=testimony,
        )
    )
    assert testimony_ledger.pruned_testimony_count == 1

    evidence = tuple(_evidence(base_claim, ordinal=index) for index in range(17))
    evidence_ledger = enforce_dispute_limits(
        DisputeLedger(
            owner_id=OWNER,
            cases=(_case(),),
            claims=(base_claim,),
            evidence=evidence,
        )
    )
    assert evidence_ledger.pruned_evidence_count == 1

    resolutions = tuple(
        _resolution(
            proposer=OWNER,
            terms=(_term(item_token=f"item-{index}"),),
            tick=2 + index,
        )
        for index in range(5)
    )
    resolution_ledger = enforce_dispute_limits(
        DisputeLedger(owner_id=OWNER, cases=(_case(),), resolutions=resolutions)
    )
    assert resolution_ledger.pruned_resolution_count >= 1

    rule_refs = tuple(
        _rule_reference(base_claim, version_number=index + 1) for index in range(9)
    )
    reference_ledger = enforce_dispute_limits(
        DisputeLedger(
            owner_id=OWNER,
            cases=(_case(),),
            claims=(base_claim,),
            rule_references=rule_refs,
        )
    )
    assert reference_ledger.pruned_reference_count >= 1

    response_resolution = _resolution()
    responses = tuple(
        _response(response_resolution, tick=3 + index, active=False)
        for index in range(9)
    )
    response_ledger = enforce_dispute_limits(
        DisputeLedger(
            owner_id=OWNER,
            cases=(_case(),),
            resolutions=(response_resolution,),
            resolution_responses=responses,
        )
    )
    assert response_ledger.pruned_resolution_count >= 1


def test_partial_coverage_when_any_pruned_count_is_nonzero() -> None:
    ledger = DisputeLedger(owner_id=OWNER, pruned_evidence_count=1)
    assert ledger.coverage == "partial"


def test_enabled_empty_ledger_is_complete_not_partial() -> None:
    ledger = empty_dispute_ledger(OWNER)
    assert ledger.has_content is False
    assert ledger.coverage == "complete"
    assert ledger.notices == ()


def test_ledger_digest_is_order_independent() -> None:
    claim = _claim()
    counter = _claim(
        claimant=OTHER,
        respondent=OWNER,
        role=DisputeClaimRole.COUNTERCLAIM,
        polarity=DisputeClaimPolarity.DENY,
        counters=claim.claim_ref,
        tick=2,
    )
    left = DisputeLedger(owner_id=OWNER, cases=(_case(),), claims=(claim, counter))
    right = DisputeLedger(owner_id=OWNER, cases=(_case(),), claims=(counter, claim))
    assert dispute_ledger_digest(left) == dispute_ledger_digest(right)


def test_authority_and_mediation_rows_are_owner_scoped() -> None:
    assert _code(lambda: _authority("x" * 129)) == "dispute_invalid_reference"
    foreign = DisputeLedger(
        owner_id=OWNER,
        cases=(_case(),),
        authority_references=(_authority(),),
    )
    assert foreign.authority_references[0].owner_id == OWNER
    assert _code(lambda: _mediation("")) == "dispute_invalid_reference"
