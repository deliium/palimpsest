"""Overlapping cross-owner organization candidate detection."""

from __future__ import annotations

import pytest

from agents.cognition import (
    OrganizationClaim,
    OrganizationConceptLedger,
    OrganizationIdentityStance,
    apply_organization_concept_update,
    default_organization_concept_policy,
    organization_claim_relation,
)
from analysis import (
    OrganizationCandidateStatus,
    OrganizationDetectionResult,
    OrganizationHarvestRows,
    OrganizationMembershipStatus,
    OrganizationTemporalScope,
    OrganizationWindowEvidence,
    build_organization_windows,
    detect_organization_candidates,
    harvest_organization_rows,
)
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCollectiveProject,
    ObservedCommunication,
    ObservedProjectContribution,
)

pytestmark = pytest.mark.unit

WINDOW_TICKS = 100


def _ledger(
    *,
    owner: str,
    body: str,
    projects: dict[str, tuple[str, ...]],
    claim: OrganizationClaim | None = None,
    claim_speaker: str | None = None,
    tick: int = 3,
) -> OrganizationConceptLedger:
    communications: tuple[ObservedCommunication, ...] = ()
    if claim is not None:
        utterance = origin_utterance(
            text="organization",
            speaker_id=EntityId(claim_speaker or body),
            communication_id="comm-1",
            relations=(organization_claim_relation(claim),),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        )
        communications = (
            ObservedCommunication(
                provenance=ObservationProvenance(
                    source_kind=ObservationSourceKind.COMMUNICATION,
                    source_tick=tick - 1,
                    source_event_id=EventId("evt-1"),
                ),
                speaker_id=EntityId(claim_speaker or body),
                listener_id=EntityId(body),
                utterance=utterance,
                action_kind="talk",
            ),
        )
    observation = Observation(
        world_id=WorldId("world-detection"),
        observer_id=EntityId(body),
        revision=WorldRevision(tick),
        tick=tick,
        collective_projects=tuple(
            ObservedCollectiveProject(
                project_id=EntityId(project_id),
                location_id=EntityId("clearing"),
                kind="store",
                status="active",
                labor_done=len(actors),
                materials_done=0,
                contributions=tuple(
                    ObservedProjectContribution(
                        actor_id=EntityId(actor),
                        tick=tick - 1,
                        accepted=True,
                        labor_delta=1,
                    )
                    for actor in actors
                ),
            )
            for project_id, actors in projects.items()
        ),
        communications=communications,
    )
    return apply_organization_concept_update(
        owner_id=owner,
        tick=tick,
        observation=observation,
        prior=None,
        institution_concepts=None,
        offices=None,
        group_formation=None,
        collective_decisions=None,
        structured_commitments=None,
        social_conventions=None,
        policy=default_organization_concept_policy(),
    )


def _detect(
    ledgers: tuple[object, ...],
) -> tuple[
    tuple[OrganizationHarvestRows, ...],
    tuple[OrganizationWindowEvidence, ...],
    OrganizationDetectionResult,
]:
    harvest = harvest_organization_rows(ledgers)
    windows = build_organization_windows(harvest, WINDOW_TICKS)
    return harvest, windows, detect_organization_candidates(windows)


def test_overlapping_person_is_retained_in_both_candidates() -> None:
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    ben = _ledger(
        owner="ben",
        body="body-ben",
        projects={"project-2": ("body-ben", "body-cy")},
    )
    _, _, detection = _detect((ada, ben))
    assert len(detection.candidates) == 2
    assert "body-ben" in detection.overlap_person_ids
    for candidate in detection.candidates:
        assert "body-ben" in candidate.member_ids
        assert "body-ben" in candidate.overlap_member_ids


def test_contradictory_owner_claims_are_disputed() -> None:
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    leave = OrganizationClaim(
        predicate="organization_leave", stance=OrganizationIdentityStance.OUTSIDE
    )
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
        claim=claim,
    )
    ben = _ledger(
        owner="ben",
        body="body-ben",
        projects={"project-1": ("body-ada", "body-ben")},
        claim=leave,
        claim_speaker="body-ada",
    )
    _, _, detection = _detect((ada, ben))
    assert len(detection.candidates) == 1
    candidate = detection.candidates[0]
    assert candidate.status is OrganizationCandidateStatus.DISPUTED
    assert any(
        claim.status is OrganizationMembershipStatus.DISPUTED
        for claim in candidate.member_claims
    )


def test_temporary_membership_is_reported() -> None:
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
        expires_tick=40,
    )
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
        claim=claim,
    )
    _, _, detection = _detect((ada,))
    candidate = detection.candidates[0]
    assert candidate.status is OrganizationCandidateStatus.TEMPORARY
    assert candidate.temporal_scope is OrganizationTemporalScope.TEMPORARY
    assert any(
        claim.temporal_scope is OrganizationTemporalScope.TEMPORARY
        for claim in candidate.member_claims
    )


def test_disconnected_evidence_stays_two_candidates() -> None:
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    ben = _ledger(
        owner="ben",
        body="body-ben",
        projects={"project-2": ("body-cy", "body-dee")},
    )
    _, _, detection = _detect((ada, ben))
    assert len(detection.candidates) == 2
    assert detection.overlap_person_ids == ()


def test_missing_self_identification_is_legal() -> None:
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    _, _, detection = _detect((ada,))
    candidate = detection.candidates[0]
    assert candidate.self_identified is False
    assert candidate.status is not OrganizationCandidateStatus.DISPUTED


def test_unknown_person_ids_are_rejected_when_a_universe_is_supplied() -> None:
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    harvest = harvest_organization_rows((ada,))
    windows = build_organization_windows(harvest, WINDOW_TICKS)
    with pytest.raises(ValueError):
        detect_organization_candidates(windows, known_person_ids=("body-ada",))


def test_detection_is_order_independent() -> None:
    ada = _ledger(
        owner="ada",
        body="body-ada",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    ben = _ledger(
        owner="ben",
        body="body-ben",
        projects={"project-1": ("body-ada", "body-ben")},
    )
    forward = _detect((ada, ben))[2]
    backward = _detect((ben, ada))[2]
    assert [item.candidate_key for item in forward.candidates] == [
        item.candidate_key for item in backward.candidates
    ]
