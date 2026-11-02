"""V4-05 deterministic proposal generation and implementation tracking."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationAgencyAct,
    OrganizationAgencyClaim,
    OrganizationAgencyConcept,
    OrganizationAgencyEffect,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyLedger,
    OrganizationAgencyPositionStance,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyReportKind,
    OrganizationOperationDomain,
    OrganizationStatus,
    apply_organization_agency_update,
    appraise_organization_agency_position,
    generate_organization_agency_proposal,
    organization_agency_claim_relation,
    organization_agency_ref,
    track_organization_agency_implementation,
)
from tests.unit.organization_agency_helpers import (
    OWNER,
    FakeCommunication,
    FakeContent,
    FakeObservation,
    FakeOccurrence,
    FakeUtterance,
    concept_id,
    concept_ledger,
    decision,
    position,
    proposal,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _empty_ledger() -> OrganizationAgencyLedger:
    return apply_organization_agency_update(
        owner_id=OWNER,
        tick=1,
        observation=FakeObservation(),
        prior=None,
        organization_concepts=concept_ledger(),
    )


def test_generation_creates_one_self_authored_proposal() -> None:
    concepts = concept_ledger(resource_anchor="repository-alpha")
    ledger = _empty_ledger()
    generated = generate_organization_agency_proposal(
        ledger,
        FakeObservation(tick=2),
        None,
        concepts,
    )
    proposals = generated.concepts[0].proposals
    assert len(proposals) == 1
    assert proposals[0].authority_basis.value == "self_authored"
    assert proposals[0].status is OrganizationAgencyProposalStatus.ACTIVE
    assert proposals[0].domain is OrganizationOperationDomain.RESOURCE_CONTROL


def test_generation_skips_dissolved_concepts() -> None:
    concepts = concept_ledger(status=OrganizationStatus.DISSOLVED)
    generated = generate_organization_agency_proposal(
        _empty_ledger(), FakeObservation(tick=2), None, concepts
    )
    assert generated.concepts[0].proposals == ()


def test_generation_skips_when_active_proposal_exists() -> None:
    concepts = concept_ledger(resource_anchor="repository-alpha")
    first = generate_organization_agency_proposal(
        _empty_ledger(), FakeObservation(tick=2), None, concepts
    )
    second = generate_organization_agency_proposal(
        first, FakeObservation(tick=3), None, concepts
    )
    assert len(second.concepts[0].proposals) == 1


def test_appraisal_supports_with_recognized_procedure() -> None:
    concepts = concept_ledger()
    ledger = _empty_ledger()
    generated = generate_organization_agency_proposal(
        ledger, FakeObservation(tick=2), None, concepts
    )
    appraised = appraise_organization_agency_position(
        generated, FakeObservation(tick=3), None, concepts
    )
    positions = appraised.concepts[0].positions
    assert len(positions) == 1
    assert positions[0].actor_id == OWNER
    assert positions[0].stance is OrganizationAgencyPositionStance.SUPPORT


def test_appraisal_abstains_without_recognized_procedure() -> None:
    concepts = concept_ledger(procedure_status=OrganizationStatus.CANDIDATE)
    generated = generate_organization_agency_proposal(
        _empty_ledger(), FakeObservation(tick=2), None, concepts
    )
    appraised = appraise_organization_agency_position(
        generated, FakeObservation(tick=3), None, concepts
    )
    assert (
        appraised.concepts[0].positions[0].stance
        is OrganizationAgencyPositionStance.ABSTAIN
    )


def _tracking_ledger(
    *,
    effect: OrganizationAgencyEffect = OrganizationAgencyEffect.GIVE,
    window_end: int = 20,
) -> OrganizationAgencyLedger:
    concepts = concept_ledger()
    built = proposal(
        organization_id=concept_id(concepts),
        effect=effect,
        target_kind="none",
        expected_actors=(OWNER,),
    )
    decided = decision(built, decided_tick=6, window_end_tick=window_end)
    concept = OrganizationAgencyConcept(
        organization_id=concept_id(concepts),
        owner_id=OWNER,
        status=OrganizationStatus.RECOGNIZED,
        first_tick=1,
        last_tick=6,
        proposals=(built,),
        decisions=(decided,),
    )
    return OrganizationAgencyLedger(owner_id=OWNER, concepts=(concept,))


def test_physical_implementation_from_matching_effect() -> None:
    tracked = track_organization_agency_implementation(
        _tracking_ledger(),
        FakeObservation(
            tick=7,
            occurrences=(
                FakeOccurrence(kind="give", public_facts={"give_item_ids": ("i",)}),
            ),
        ),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.IMPLEMENTED
    )
    assert (
        tracked.concepts[0].decisions[0].implementation_status
        is OrganizationAgencyImplementationStatus.IMPLEMENTED
    )


def test_unimplemented_after_closed_window_with_observed_actor() -> None:
    tracked = track_organization_agency_implementation(
        _tracking_ledger(window_end=10),
        FakeObservation(
            tick=12,
            occurrences=(FakeOccurrence(kind="move", success=True),),
        ),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.UNIMPLEMENTED
    )


def test_unobserved_actor_remains_unknown() -> None:
    tracked = track_organization_agency_implementation(
        _tracking_ledger(window_end=10),
        FakeObservation(tick=12),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.UNKNOWN
    )


def test_explicit_refusal_is_recorded() -> None:
    claim = OrganizationAgencyClaim(
        act=OrganizationAgencyAct.REFUSE,
        proposal_ref=organization_agency_ref("proposal-material", namespace="proposal"),
        revision=1,
        stance="refuse",
    )
    tracked = track_organization_agency_implementation(
        _tracking_ledger(),
        FakeObservation(
            tick=7,
            communications=(
                FakeCommunication(
                    speaker_id=EntityId("body-agent-1"),
                    listener_id=EntityId("body-agent-2"),
                    utterance=FakeUtterance(
                        content=FakeContent(
                            relations=(organization_agency_claim_relation(claim),)
                        )
                    ),
                ),
            ),
        ),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.REFUSED
    )


def test_contrary_alone_is_not_sabotage() -> None:
    tracked = track_organization_agency_implementation(
        _tracking_ledger(),
        FakeObservation(
            tick=7, occurrences=(FakeOccurrence(kind="attack", success=True),)
        ),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.CONTRARY
    )


def test_contrary_with_prior_opposition_is_sabotage_attribution() -> None:
    ledger = _tracking_ledger()
    concept = ledger.concepts[0]
    opposed = position(
        concept.proposals[0].proposal_id,
        actor=OWNER,
        stance=OrganizationAgencyPositionStance.OPPOSE,
        tick=6,
    )
    ledger = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept.organization_id,
                owner_id=OWNER,
                status=OrganizationStatus.RECOGNIZED,
                first_tick=1,
                last_tick=6,
                proposals=concept.proposals,
                positions=(opposed,),
                decisions=concept.decisions,
            ),
        ),
    )
    tracked = track_organization_agency_implementation(
        ledger,
        FakeObservation(
            tick=7, occurrences=(FakeOccurrence(kind="attack", success=True),)
        ),
        None,
    )
    record = tracked.concepts[0].implementations[0]
    assert record.status is OrganizationAgencyImplementationStatus.SABOTAGED
    assert record.provenance_code.value == "declared_sabotage"


def test_testimonial_report_implements() -> None:
    claim = OrganizationAgencyClaim(
        act=OrganizationAgencyAct.REPORT,
        proposal_ref=organization_agency_ref("proposal-material", namespace="proposal"),
        revision=1,
        report_kind=OrganizationAgencyReportKind.IMPLEMENTED,
    )
    tracked = track_organization_agency_implementation(
        _tracking_ledger(effect=OrganizationAgencyEffect.NONE),
        FakeObservation(
            tick=7,
            communications=(
                FakeCommunication(
                    speaker_id=EntityId("body-agent-1"),
                    listener_id=EntityId("body-agent-2"),
                    utterance=FakeUtterance(
                        content=FakeContent(
                            relations=(organization_agency_claim_relation(claim),)
                        )
                    ),
                ),
            ),
        ),
        None,
    )
    assert (
        tracked.concepts[0].implementations[0].status
        is OrganizationAgencyImplementationStatus.IMPLEMENTED
    )


def test_dissolved_concept_expires_implementation() -> None:
    ledger = _tracking_ledger()
    concept = ledger.concepts[0]
    dissolved = OrganizationAgencyLedger(
        owner_id=OWNER,
        concepts=(
            OrganizationAgencyConcept(
                organization_id=concept.organization_id,
                owner_id=OWNER,
                status=OrganizationStatus.DISSOLVED,
                first_tick=1,
                last_tick=7,
                proposals=concept.proposals,
                decisions=concept.decisions,
            ),
        ),
    )
    tracked = track_organization_agency_implementation(
        dissolved, FakeObservation(tick=7), None
    )
    assert (
        tracked.concepts[0].decisions[0].implementation_status
        is OrganizationAgencyImplementationStatus.EXPIRED
    )
