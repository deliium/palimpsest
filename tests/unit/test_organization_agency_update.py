"""V4-05 claim collection and owner-local collective decision materialization."""

from __future__ import annotations

import pytest

from agents.cognition import (
    ORGANIZATION_AGENCY_POLICY_VERSION,
    OrganizationAgencyAct,
    OrganizationAgencyClaim,
    OrganizationAgencyEffect,
    OrganizationAgencyError,
    OrganizationAgencyLedger,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyRecognition,
    OrganizationAgencyReportKind,
    OrganizationOperationDomain,
    OrganizationStatus,
    apply_organization_agency_update,
    organization_agency_claim_relation,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    concept_ledger,
    procedure_ref,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_REF = "d" * 16
_TERMS = "e" * 16


def _communication(
    claim: OrganizationAgencyClaim, *, speaker: str = "body-agent-2"
) -> object:
    from tests.unit.organization_agency_helpers import (
        FakeCommunication,
        FakeContent,
        FakeUtterance,
    )

    return FakeCommunication(
        speaker_id=EntityId(speaker),
        listener_id=EntityId("body-agent-1"),
        utterance=FakeUtterance(
            content=FakeContent(relations=(organization_agency_claim_relation(claim),))
        ),
    )


def _observation(
    claims: tuple[OrganizationAgencyClaim, ...] = (),
) -> object:
    from tests.unit.organization_agency_helpers import FakeObservation

    def speaker_for(claim: OrganizationAgencyClaim) -> str:
        if claim.act in (
            OrganizationAgencyAct.OPPOSE,
            OrganizationAgencyAct.ABSTAIN,
            OrganizationAgencyAct.AMEND,
        ):
            return "body-agent-3"
        return "body-agent-2"

    return FakeObservation(
        observer_id=EntityId("body-agent-1"),
        communications=tuple(
            _communication(claim, speaker=speaker_for(claim)) for claim in claims
        ),
    )


def _propose_claim(
    *,
    procedure: str | None = "procedure-alpha",
    ref: str = _REF,
    effect: OrganizationAgencyEffect = OrganizationAgencyEffect.NONE,
    domain: OrganizationOperationDomain = OrganizationOperationDomain.PROCEDURE_ACTION,
) -> OrganizationAgencyClaim:
    return OrganizationAgencyClaim(
        act=OrganizationAgencyAct.PROPOSE,
        proposal_ref=ref,
        procedure_ref=None if procedure is None else procedure_ref(procedure),
        domain=domain,
        effect=effect,
        revision=1,
        terms_ref=_TERMS,
    )


def _position_claim(
    act: OrganizationAgencyAct, *, revision: int = 1, ref: str = _REF
) -> OrganizationAgencyClaim:
    stance = {
        OrganizationAgencyAct.SUPPORT: "support",
        OrganizationAgencyAct.OPPOSE: "oppose",
        OrganizationAgencyAct.ABSTAIN: "abstain",
        OrganizationAgencyAct.WITHDRAW: "withdraw",
        OrganizationAgencyAct.REFUSE: "refuse",
    }[act]
    return OrganizationAgencyClaim(
        act=act, proposal_ref=ref, revision=revision, stance=stance
    )


def _run(
    *,
    tick: int,
    claims: tuple[OrganizationAgencyClaim, ...] = (),
    prior: OrganizationAgencyLedger | None = None,
    concepts: object | None = None,
) -> OrganizationAgencyLedger:
    return apply_organization_agency_update(
        owner_id=OWNER,
        tick=tick,
        observation=_observation(claims),
        prior=prior,
        organization_concepts=(
            concepts
            if concepts is not None
            else concept_ledger(member_ids=("agent-1", "agent-2", "agent-3"))
        ),
    )


def test_peer_proposal_is_owner_local_and_communicated() -> None:
    ledger = _run(tick=1, claims=(_propose_claim(),))
    concept = ledger.concepts[0]
    assert len(concept.proposals) == 1
    created = concept.proposals[0]
    assert created.authority_basis.value == "observation"
    assert created.provenance_code.value == "communicated"
    assert created.status is OrganizationAgencyProposalStatus.ACTIVE
    assert created.deadline_tick == 1 + 16
    assert created.proposal_id.startswith("orgp-")


def test_peer_proposal_without_concept_is_orphaned() -> None:
    from tests.unit.organization_agency_helpers import FakeObservation

    ledger = apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=FakeObservation(
            observer_id=EntityId("body-agent-1"),
            communications=(_communication(_propose_claim(), speaker="body-agent-9"),),
        ),
        prior=None,
        organization_concepts=concept_ledger(
            member_ids=("agent-1", "agent-2", "agent-3")
        ),
    )
    assert ledger.concepts[0].proposals == ()
    assert "orphaned_concept" in ledger.notices


def test_orphan_claim_without_matching_proposal_is_recorded() -> None:
    ledger = _run(tick=1, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),))
    assert ledger.concepts[0].proposals == ()
    assert "orphaned_concept" in ledger.notices


def test_unsupported_proposal_expires_without_decision() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    later = _run(tick=20, prior=first)
    proposal_record = later.concepts[0].proposals[0]
    assert proposal_record.status is OrganizationAgencyProposalStatus.EXPIRED
    assert later.concepts[0].decisions == ()
    assert "proposal_expired" in later.notices


def test_support_and_recognized_procedure_records_a_recognized_decision() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    supported = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),), prior=first
    )
    decided = _run(tick=17, prior=supported)
    decision = decided.concepts[0].decisions[0]
    assert decision.recognition is OrganizationAgencyRecognition.RECOGNIZED
    assert decision.support_count == 1
    assert decision.provenance_code.value == "procedure_recognized"
    assert decision.decision_id.startswith("orgcd-")


def test_support_without_recognized_procedure_still_records_a_decision() -> None:
    concepts = concept_ledger(procedure_status=OrganizationStatus.CANDIDATE)
    first = _run(tick=1, claims=(_propose_claim(),), concepts=concepts)
    supported = _run(
        tick=2,
        claims=(_position_claim(OrganizationAgencyAct.SUPPORT),),
        prior=first,
        concepts=concepts,
    )
    decided = _run(tick=17, prior=supported, concepts=concepts)
    decision = decided.concepts[0].decisions[0]
    assert decision.recognition is OrganizationAgencyRecognition.UNRECOGNIZED
    assert decision.provenance_code.value == "unrecognized"


def test_support_and_opposition_is_contested_and_retained() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    first = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),), prior=first
    )
    second = _run(
        tick=3, claims=(_position_claim(OrganizationAgencyAct.OPPOSE),), prior=first
    )
    decided = _run(tick=17, prior=second)
    decision = decided.concepts[0].decisions[0]
    assert decision.recognition is OrganizationAgencyRecognition.CONTESTED
    assert decision.support_count == 1
    assert decision.oppose_count == 1
    assert decision.contest_count == 1


def test_abstention_increments_and_does_not_block() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    first = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),), prior=first
    )
    second = _run(
        tick=3, claims=(_position_claim(OrganizationAgencyAct.ABSTAIN),), prior=first
    )
    decided = _run(tick=17, prior=second)
    decision = decided.concepts[0].decisions[0]
    assert decision.abstain_count == 1
    assert decision.recognition is OrganizationAgencyRecognition.RECOGNIZED


def test_amend_increments_revision_and_resets_counts() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    first = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),), prior=first
    )
    amended = _run(
        tick=3,
        claims=(
            OrganizationAgencyClaim(
                act=OrganizationAgencyAct.AMEND,
                proposal_ref=_REF,
                revision=2,
                terms_ref="f" * 16,
                domain=OrganizationOperationDomain.PROCEDURE_ACTION,
                effect=OrganizationAgencyEffect.NONE,
            ),
        ),
        prior=first,
    )
    concept = amended.concepts[0]
    assert concept.proposals[0].revision == 2
    assert concept.proposals[0].support_count == 0
    assert len(concept.amendments) == 1
    assert len(concept.positions) == 2


def test_out_of_order_amendment_keeps_revision() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    amended = _run(
        tick=2,
        claims=(
            OrganizationAgencyClaim(
                act=OrganizationAgencyAct.AMEND,
                proposal_ref=_REF,
                revision=3,
                terms_ref="f" * 16,
                domain=OrganizationOperationDomain.PROCEDURE_ACTION,
                effect=OrganizationAgencyEffect.NONE,
            ),
        ),
        prior=first,
    )
    assert amended.concepts[0].proposals[0].revision == 1
    assert "amendment_out_of_order" in amended.concepts[0].notices


def test_explicit_recognition_mints_before_deadline_and_reuses_id() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    recognize = OrganizationAgencyClaim(
        act=OrganizationAgencyAct.RECOGNIZE,
        proposal_ref=_REF,
        revision=1,
        procedure_ref=procedure_ref(),
        stance="recognized",
    )
    decided = _run(tick=2, claims=(recognize,), prior=first)
    decision = decided.concepts[0].decisions[0]
    assert decision.decided_tick == 2
    again = _run(tick=5, prior=decided)
    assert again.concepts[0].decisions[0].decision_id == decision.decision_id
    assert again.concepts[0].decisions[0].decided_tick == 2


def test_refusal_is_retained_as_a_position() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    refused = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.REFUSE),), prior=first
    )
    assert any(item.refused for item in refused.concepts[0].positions)


def test_report_is_evidence_only() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    report = OrganizationAgencyClaim(
        act=OrganizationAgencyAct.REPORT,
        proposal_ref=_REF,
        revision=1,
        report_kind=OrganizationAgencyReportKind.IMPLEMENTED,
    )
    reported = _run(tick=2, claims=(report,), prior=first)
    concept = reported.concepts[0]
    assert concept.positions == ()
    assert concept.proposals[0].evidence_refs


def test_evidence_refs_are_agency_ids_sorted_and_unique() -> None:
    first = _run(tick=1, claims=(_propose_claim(),))
    second = _run(
        tick=2, claims=(_position_claim(OrganizationAgencyAct.SUPPORT),), prior=first
    )
    refs = second.concepts[0].proposals[0].evidence_refs
    assert all(ref.startswith("orgcev-") for ref in refs)
    assert tuple(sorted(set(refs))) == refs


def test_foreign_owner_ledger_fails_closed() -> None:
    from tests.unit.organization_agency_helpers import OTHER

    with pytest.raises(OrganizationAgencyError) as excinfo:
        apply_organization_agency_update(
            owner_id=OWNER,
            tick=1,
            observation=_observation(),
            prior=OrganizationAgencyLedger(owner_id=OTHER),
            organization_concepts=concept_ledger(),
        )
    assert excinfo.value.code == "organization_agency_foreign_ledger"


def test_world_state_input_fails_closed() -> None:
    from world._state import WorldState

    with pytest.raises(OrganizationAgencyError):
        apply_organization_agency_update(
            owner_id=OWNER,
            tick=1,
            observation=object.__new__(WorldState),
            prior=None,
            organization_concepts=concept_ledger(),
        )


def test_policy_version_and_empty_ledger() -> None:
    empty = apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=_observation(),
        prior=None,
        organization_concepts=None,
    )
    assert empty.policy_version == ORGANIZATION_AGENCY_POLICY_VERSION
    assert empty.concepts == ()


def test_no_prior_concept_ledger_drops_the_prior_ledger() -> None:
    prior = _run(tick=1, claims=(_propose_claim(),))
    dropped = apply_organization_agency_update(
        owner_id=OWNER,
        tick=2,
        observation=_observation(),
        prior=prior,
        organization_concepts=None,
    )
    assert dropped.concepts == ()
