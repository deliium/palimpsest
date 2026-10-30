"""Deterministic owner-local organization formation and membership states."""

from __future__ import annotations

import hashlib

import pytest

from agents.cognition import (
    ORGANIZATION_CONCEPT_POLICY_VERSION,
    OrganizationClaim,
    OrganizationConceptError,
    OrganizationConceptLedger,
    OrganizationEvidenceChannel,
    OrganizationIdentityStance,
    OrganizationMembershipStatus,
    OrganizationStatus,
    OrganizationTemporalScope,
    apply_organization_concept_update,
    default_organization_concept_policy,
    organization_claim_relation,
    organization_concept_digest,
)
from agents.models import AgentId
from world.communications import CommunicationSourceBasis, origin_utterance
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCollectiveProject,
    ObservedCommunication,
    ObservedProjectContribution,
    ObservedRepository,
)

pytestmark = pytest.mark.unit

OWNER = "ada"
OBSERVER = EntityId("body-ada")
POLICY = default_organization_concept_policy()


def _project(
    project_id: str, actors: tuple[str, ...], tick: int
) -> ObservedCollectiveProject:
    return ObservedCollectiveProject(
        project_id=EntityId(project_id),
        location_id=EntityId("clearing"),
        kind="store",
        status="active",
        labor_done=len(actors),
        materials_done=0,
        contributions=tuple(
            ObservedProjectContribution(
                actor_id=EntityId(actor), tick=tick, accepted=True, labor_delta=1
            )
            for actor in actors
        ),
    )


def _communication(
    *,
    speaker: str,
    listener: str,
    claims: tuple[OrganizationClaim, ...],
    tick: int,
    event_id: str,
) -> ObservedCommunication:
    utterance = origin_utterance(
        text="organization",
        speaker_id=EntityId(speaker),
        communication_id=f"comm-{event_id}",
        relations=tuple(organization_claim_relation(claim) for claim in claims),
        source_basis=CommunicationSourceBasis.UNREFERENCED,
    )
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick - 1,
            source_event_id=EventId(event_id),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId(listener),
        utterance=utterance,
        action_kind="talk",
    )


def _observation(
    *,
    tick: int,
    projects: tuple[ObservedCollectiveProject, ...] = (),
    communications: tuple[ObservedCommunication, ...] = (),
    repositories: tuple[ObservedRepository, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-orgs"),
        observer_id=OBSERVER,
        revision=WorldRevision(tick),
        tick=tick,
        collective_projects=projects,
        communications=communications,
        repositories=repositories,
    )


def _update(
    *,
    tick: int,
    observation: Observation,
    prior: OrganizationConceptLedger | None = None,
    offices: object | None = None,
    institution_concepts: object | None = None,
    group_formation: object | None = None,
    collective_decisions: object | None = None,
    structured_commitments: object | None = None,
    social_conventions: object | None = None,
) -> OrganizationConceptLedger:
    return apply_organization_concept_update(
        owner_id=OWNER,
        tick=tick,
        observation=observation,
        prior=prior,
        institution_concepts=institution_concepts,
        offices=offices,
        group_formation=group_formation,
        collective_decisions=collective_decisions,
        structured_commitments=structured_commitments,
        social_conventions=social_conventions,
        policy=POLICY,
    )


def test_formation_is_deterministic_under_permutation() -> None:
    first = _project("project-1", ("body-ada", "body-ben"), 2)
    second = _project("project-2", ("body-ada", "body-cy"), 2)
    forward = _update(
        tick=3, observation=_observation(tick=3, projects=(first, second))
    )
    backward = _update(
        tick=3, observation=_observation(tick=3, projects=(second, first))
    )
    assert [item.organization_id for item in forward.concepts] == [
        item.organization_id for item in backward.concepts
    ]
    assert [organization_concept_digest(item) for item in forward.concepts] == [
        organization_concept_digest(item) for item in backward.concepts
    ]


def test_repeated_evidence_is_idempotent() -> None:
    project = _project("project-1", ("body-ada", "body-ben"), 2)
    first = _update(tick=3, observation=_observation(tick=3, projects=(project,)))
    concept_id = first.concepts[0].organization_id
    second = _update(
        tick=4,
        observation=_observation(
            tick=4, projects=(_project("project-1", ("body-ada", "body-ben"), 3),)
        ),
        prior=first,
    )
    assert len(second.concepts) == 1
    assert second.concepts[0].organization_id == concept_id
    assert len(second.concepts[0].revisions) == 0
    assert [record.kind.value for record in second.concepts[0].lineage] == ["emerged"]


def test_explicit_self_claim_and_contradiction_yield_dispute() -> None:
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    dispute = OrganizationClaim(
        predicate="organization_dispute",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    ledger = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-1", ("body-ada", "body-ben"), 2),),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(claim, dispute),
                    tick=3,
                    event_id="evt-1",
                ),
            ),
        ),
    )
    concept = ledger.concepts[0]
    assert concept.status is OrganizationStatus.DISPUTED
    assert any(
        member.status is OrganizationMembershipStatus.DISPUTED
        for member in concept.members
    )


def test_explicit_claim_is_reached_through_the_update_path() -> None:
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
        expires_tick=9,
    )
    ledger = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-1", ("body-ada", "body-ben"), 2),),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(claim,),
                    tick=3,
                    event_id="evt-1",
                ),
            ),
        ),
    )
    concept = ledger.concepts[0]
    owner = next(member for member in concept.members if member.member_id == "body-ada")
    assert owner.status is OrganizationMembershipStatus.EXPLICIT
    assert owner.temporal_scope is OrganizationTemporalScope.TEMPORARY
    assert owner.expires_tick == 9
    assert concept.identities[0].label_token == "water-carriers"


def test_overlapping_membership_is_retained() -> None:
    first = _update(
        tick=3,
        observation=_observation(
            tick=3, projects=(_project("project-1", ("body-ada", "body-ben"), 2),)
        ),
    )
    ledger = _update(
        tick=4,
        observation=_observation(
            tick=4, projects=(_project("project-2", ("body-ben", "body-cy"), 3),)
        ),
        prior=first,
    )
    assert len(ledger.concepts) == 2
    owners = [
        {member.member_id for member in concept.members} for concept in ledger.concepts
    ]
    assert any("body-ben" in members for members in owners)
    assert sum(1 for members in owners if "body-ben" in members) == 2


def test_temporary_membership_expires_then_dissolves() -> None:
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
        expires_tick=5,
    )
    first = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-1", ("body-ada",), 2),),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(claim,),
                    tick=3,
                    event_id="evt-1",
                ),
            ),
        ),
    )
    assert first.concepts[0].status is not OrganizationStatus.DISSOLVED

    expired = _update(tick=5, observation=_observation(tick=5), prior=first)
    concept = expired.concepts[0]
    assert any(
        member.status is OrganizationMembershipStatus.FORMER
        for member in concept.members
    )
    assert concept.status is OrganizationStatus.DISSOLVED
    assert "temporary_expired" in expired.notices


def test_leave_claim_yields_former_not_deletion() -> None:
    leave = OrganizationClaim(
        predicate="organization_leave", stance=OrganizationIdentityStance.OUTSIDE
    )
    ledger = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-1", ("body-ada", "body-ben"), 2),),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(leave,),
                    tick=3,
                    event_id="evt-1",
                ),
            ),
        ),
    )
    concept = ledger.concepts[0]
    owner = next(member for member in concept.members if member.member_id == "body-ada")
    assert owner.status is OrganizationMembershipStatus.FORMER
    assert "body-ada" in concept.member_ids


def test_every_membership_status_is_reachable() -> None:
    statuses: set[OrganizationMembershipStatus] = set()
    project = _project("project-1", ("body-ada", "body-ben"), 2)
    claim = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
        expires_tick=4,
    )
    ledger = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-2", ("body-cy",), 2), project),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(claim,),
                    tick=3,
                    event_id="evt-1",
                ),
            ),
        ),
    )
    for concept in ledger.concepts:
        statuses.update(member.status for member in concept.members)

    former = _update(tick=4, observation=_observation(tick=4), prior=ledger)
    for concept in former.concepts:
        statuses.update(member.status for member in concept.members)

    # Unknown/former/disputed need targeted claims; exercise them directly.
    dispute = OrganizationClaim(
        predicate="organization_dispute",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    fresh = OrganizationClaim(
        predicate="organization_claim",
        stance=OrganizationIdentityStance.MEMBER,
        label_token="water-carriers",
    )
    disputed = _update(
        tick=5,
        observation=_observation(
            tick=5,
            projects=(project,),
            communications=(
                _communication(
                    speaker="body-ada",
                    listener="body-ada",
                    claims=(fresh, dispute),
                    tick=5,
                    event_id="evt-2",
                ),
            ),
        ),
        prior=former,
    )
    for concept in disputed.concepts:
        statuses.update(member.status for member in concept.members)

    assert {
        OrganizationMembershipStatus.EXPLICIT,
        OrganizationMembershipStatus.PERCEIVED,
        OrganizationMembershipStatus.DISPUTED,
        OrganizationMembershipStatus.FORMER,
    } <= statuses
    assert (
        OrganizationEvidenceChannel.OBSERVED in ledger.concepts[0].members[0].channels
    )


def test_every_structural_family_is_reachable() -> None:
    from types import SimpleNamespace

    offices = SimpleNamespace(
        owner_id=AgentId(OWNER),
        concepts=(
            SimpleNamespace(
                office_id="a" * 64,
                function=SimpleNamespace(value="coordination"),
                context_key="b" * 64,
                status=SimpleNamespace(value="recognized"),
                first_tick=1,
                occupants=(
                    SimpleNamespace(
                        occupant_id=AgentId("agent-9"),
                        status=SimpleNamespace(value="active"),
                    ),
                ),
            ),
        ),
    )
    institutions = SimpleNamespace(
        concepts=(
            SimpleNamespace(
                concept_id="c" * 64,
                procedure_recurrence=0.7,
                role_recognition=0.5,
                status=SimpleNamespace(value="recognized"),
                first_tick=1,
                label_token="water-carriers",
            ),
        )
    )
    commitments = SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                local_id=1,
                debtor_id=OWNER,
                creditor_id="agent-9",
                kind="deliver",
                status="open",
                due_tick=9,
                created_tick=1,
            ),
        )
    )
    conventions = SimpleNamespace(
        beliefs=(
            SimpleNamespace(
                belief_id="d" * 64,
                repetition_count=3,
                first_tick=1,
            ),
        )
    )
    repository = ObservedRepository(
        repository_id=EntityId("repository-1"),
        location_id=EntityId("clearing"),
        status="active",
        member_count=1,
    )
    ledger = _update(
        tick=3,
        observation=_observation(
            tick=3,
            projects=(_project("project-1", ("agent-9",), 2),),
            repositories=(repository,),
        ),
        offices=offices,
        institution_concepts=institutions,
        structured_commitments=commitments,
        social_conventions=conventions,
    )
    concept = ledger.concepts[0]
    assert concept.roles
    assert concept.goals
    assert concept.resources
    assert concept.procedures
    assert concept.commitments
    assert concept.identities
    assert concept.structural_channel_count >= 6


def test_foreign_owner_and_policy_are_rejected() -> None:
    with pytest.raises(OrganizationConceptError) as excinfo:
        apply_organization_concept_update(
            owner_id="ada",
            tick=3,
            observation=_observation(tick=3),
            prior=OrganizationConceptLedger(owner_id=AgentId("ben")),
            institution_concepts=None,
            offices=None,
            group_formation=None,
            collective_decisions=None,
            structured_commitments=None,
            social_conventions=None,
            policy=POLICY,
        )
    assert excinfo.value.code == "organization_foreign_ledger"

    with pytest.raises(OrganizationConceptError) as excinfo:
        apply_organization_concept_update(
            owner_id="ada",
            tick=3,
            observation=_observation(tick=3),
            prior=None,
            institution_concepts=None,
            offices=None,
            group_formation=None,
            collective_decisions=None,
            structured_commitments=None,
            social_conventions=None,
            policy=object(),  # type: ignore[arg-type]
        )
    assert excinfo.value.code == "organization_policy_mismatch"


def test_empty_evidence_creates_no_fabricated_organization() -> None:
    ledger = _update(tick=3, observation=_observation(tick=3))
    assert ledger.concepts == ()
    assert ledger.owner_id == AgentId(OWNER)
    assert ledger.policy_version == ORGANIZATION_CONCEPT_POLICY_VERSION
    assert "missing_office" in ledger.notices
    assert "missing_institution" in ledger.notices


def test_digest_does_not_depend_on_member_order() -> None:
    first = _update(
        tick=3,
        observation=_observation(
            tick=3, projects=(_project("project-1", ("body-ada", "body-ben"), 2),)
        ),
    )
    second = _update(
        tick=3,
        observation=_observation(
            tick=3, projects=(_project("project-1", ("body-ben", "body-ada"), 2),)
        ),
    )
    assert [item.organization_id for item in first.concepts] == [
        item.organization_id for item in second.concepts
    ]
    assert (
        hashlib.sha256(
            organization_concept_digest(first.concepts[0]).encode()
        ).hexdigest()
        == hashlib.sha256(
            organization_concept_digest(second.concepts[0]).encode()
        ).hexdigest()
    )
