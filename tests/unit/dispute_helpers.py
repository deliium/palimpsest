"""Synthetic detached dispute ledgers and candidates for analysis tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

OWNER = "agent-1"
OTHER = "agent-2"
THIRD = "agent-3"
SUBJECT = "commitment-1"


def case_ref(subject: str = SUBJECT, parties: tuple[str, ...] = (OWNER, OTHER)) -> str:
    return f"case-{subject}-{'-'.join(sorted(parties))}"


def claim_ref(
    case: str,
    claimant: str,
    role: str,
    claim_kind: str,
    polarity: str,
) -> str:
    return f"claim-{case}-{claimant}-{role}-{claim_kind}-{polarity}"


def make_case(
    *,
    owner: str = OWNER,
    subject: str = SUBJECT,
    parties: tuple[str, ...] = (OWNER, OTHER),
    kind: str = "contested_debt",
    subject_kind: str = "commitment",
    status: str = "open",
    first_tick: int = 2,
    last_tick: int = 2,
) -> Any:
    return SimpleNamespace(
        case_ref=case_ref(subject, parties),
        owner_id=owner,
        kind=kind,
        subject_kind=subject_kind,
        subject_token=subject,
        status=status,
        party_ids=tuple(sorted(parties)),
        first_tick=first_tick,
        last_tick=last_tick,
    )


def make_claim(
    *,
    owner: str = OWNER,
    case: Any | None = None,
    subject: str = SUBJECT,
    claimant: str = OWNER,
    respondent: str = OTHER,
    role: str = "claim",
    claim_kind: str = "debt_owed",
    polarity: str = "affirm",
    evidence_ids: tuple[str, ...] = (),
    counters: str | None = None,
    first_tick: int = 2,
    last_tick: int = 2,
) -> Any:
    case_obj = case if case is not None else make_case(subject=subject)
    reference = claim_ref(case_obj.case_ref, claimant, role, claim_kind, polarity)
    return SimpleNamespace(
        claim_ref=reference,
        case_ref=case_obj.case_ref,
        owner_id=owner,
        claimant_id=claimant,
        respondent_id=respondent,
        role=role,
        claim_kind=claim_kind,
        polarity=polarity,
        subject_token=subject,
        counters_claim_ref=counters,
        evidence_ids=evidence_ids,
        first_tick=first_tick,
        last_tick=last_tick,
    )


def make_testimony(
    *,
    owner: str = OWNER,
    claim: Any,
    speaker: str = OWNER,
    channel: str = "direct",
    root: str | None = None,
    independently_evidenced: bool = False,
    tick: int = 2,
) -> Any:
    root_ref = root or f"root-{claim.claim_ref}"
    return SimpleNamespace(
        testimony_id=f"testimony-{claim.claim_ref}-{speaker}-{channel}-{tick}",
        case_ref=claim.case_ref,
        claim_ref=claim.claim_ref,
        owner_id=owner,
        speaker_id=speaker,
        channel=channel,
        root_ref=root_ref,
        independently_evidenced=independently_evidenced,
        tick=tick,
    )


def make_evidence(
    *,
    owner: str = OWNER,
    claim: Any,
    reference_kind: str = "observed_occurrence",
    reference_id: str = "event-1",
    channel: str = "observed",
    independently_evidenced: bool = False,
    tick: int = 2,
) -> Any:
    return SimpleNamespace(
        evidence_id=f"evidence-{claim.claim_ref}-{reference_id}",
        case_ref=claim.case_ref,
        claim_ref=claim.claim_ref,
        owner_id=owner,
        channel=channel,
        reference_kind=reference_kind,
        reference_id=reference_id,
        independently_evidenced=independently_evidenced,
        tick=tick,
    )


def make_resolution(
    *,
    owner: str = OWNER,
    case: Any | None = None,
    proposer: str = OWNER,
    source: str = "negotiated",
    terms_digest: str = "terms-1",
    status: str = "proposed",
    first_tick: int = 2,
    last_tick: int = 2,
    expires_tick: int | None = 66,
) -> Any:
    case_obj = case if case is not None else make_case()
    return SimpleNamespace(
        resolution_ref=f"resolution-{case_obj.case_ref}-{proposer}-{terms_digest}",
        case_ref=case_obj.case_ref,
        owner_id=owner,
        proposer_id=proposer,
        source=source,
        terms_digest=terms_digest,
        status=status,
        first_tick=first_tick,
        last_tick=last_tick,
        expires_tick=expires_tick,
    )


def make_response(
    *,
    owner: str = OWNER,
    resolution: Any,
    party: str = OWNER,
    kind: str = "accept",
    tick: int = 3,
    active: bool = True,
) -> Any:
    return SimpleNamespace(
        response_id=f"response-{resolution.resolution_ref}-{party}-{kind}-{tick}",
        resolution_ref=resolution.resolution_ref,
        case_ref=resolution.case_ref,
        owner_id=owner,
        party_id=party,
        kind=kind,
        tick=tick,
        terms_digest=resolution.terms_digest,
        active=active,
    )


def make_rule_reference(
    *,
    owner: str = OWNER,
    claim: Any,
    status: str = "resolved",
) -> Any:
    return SimpleNamespace(
        rule_reference_id=f"rule-ref-{claim.claim_ref}",
        case_ref=claim.case_ref,
        claim_ref=claim.claim_ref,
        owner_id=owner,
        system_ref="system-1",
        rule_id="frule-0123456789abcdef",
        version_number=1,
        constraint_kind="obligation",
        scope_digest=None,
        applicability="applies",
        interpretation="literal",
        status=status,
    )


def make_mediation_reference(
    *,
    owner: str = OWNER,
    case: Any | None = None,
    link_status: str = "linked",
) -> Any:
    case_obj = case if case is not None else make_case()
    return SimpleNamespace(
        mediation_reference_id=f"mediation-ref-{case_obj.case_ref}",
        case_ref=case_obj.case_ref,
        owner_id=owner,
        mediation_case_ref="mediation-case-1",
        recommendation_ref="recommendation-1",
        response_ref=None,
        outcome_ref=None,
        link_status=link_status,
    )


def make_ledger(
    *,
    owner: str = OWNER,
    cases: tuple[Any, ...] = (),
    claims: tuple[Any, ...] = (),
    testimony: tuple[Any, ...] = (),
    evidence: tuple[Any, ...] = (),
    rule_references: tuple[Any, ...] = (),
    authority_references: tuple[Any, ...] = (),
    mediation_references: tuple[Any, ...] = (),
    resolutions: tuple[Any, ...] = (),
    responses: tuple[Any, ...] = (),
    pruned: int = 0,
    first_tick: int | None = 2,
    last_tick: int | None = 2,
) -> Any:
    return SimpleNamespace(
        owner_id=owner,
        cases=cases,
        claims=claims,
        testimony=testimony,
        evidence=evidence,
        rule_references=rule_references,
        authority_references=authority_references,
        mediation_references=mediation_references,
        resolutions=resolutions,
        resolution_responses=responses,
        pruned_case_count=pruned,
        pruned_claim_count=0,
        pruned_testimony_count=0,
        pruned_evidence_count=0,
        pruned_resolution_count=0,
        pruned_reference_count=0,
        first_observed_tick=first_tick,
        last_observed_tick=last_tick,
    )


def make_candidate(
    *,
    subject: str = SUBJECT,
    parties: tuple[str, ...] = (OWNER, OTHER),
    kind: str = "contested_debt",
    owners: tuple[str, ...] = (OWNER,),
    cases: tuple[str, ...] | None = None,
    claims: tuple[str, ...] = (),
    status: str = "active",
    first_tick: int = 0,
    last_tick: int = 99,
    disagreement: int = 1,
    resolutions: int = 0,
) -> Any:
    from analysis.dispute_contract import (
        DisputeCandidateStatus,
        DisputeCoverage,
    )
    from analysis.dispute_detection import DisputeCandidate, party_set_digest

    digest = party_set_digest(parties)
    case_refs = cases if cases is not None else (case_ref(subject, parties),)
    return DisputeCandidate(
        candidate_key=f"candidate-{subject}-{digest[:8]}-{kind}-{first_tick}",
        kind=kind,
        subject_token=subject,
        party_ids=tuple(sorted(parties)),
        owner_ids=owners,
        case_refs=case_refs,
        claim_refs=claims,
        status=DisputeCandidateStatus(status),
        first_tick=first_tick,
        last_tick=last_tick,
        disagreement_count=disagreement,
        resolution_count=resolutions,
        coverage=DisputeCoverage(observed=1, expected=1),
        party_digest=digest,
    )
