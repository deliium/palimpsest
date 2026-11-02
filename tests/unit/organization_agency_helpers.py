"""Deterministic builders for organization collective-agency tests."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from agents.cognition import (
    OrganizationAgencyEffect,
    OrganizationAgencyImplementationMode,
    OrganizationAgencyImplementationStatus,
    OrganizationAgencyPositionStance,
    OrganizationAgencyProposalStatus,
    OrganizationAgencyProvenance,
    OrganizationAgencyRecognition,
    OrganizationAgencyTopic,
    OrganizationAmendment,
    OrganizationAuthorityBasis,
    OrganizationCollectiveDecision,
    OrganizationConcept,
    OrganizationConceptLedger,
    OrganizationConceptualization,
    OrganizationEvidenceChannel,
    OrganizationIdentityBelief,
    OrganizationIdentityStance,
    OrganizationImplementation,
    OrganizationLineageKind,
    OrganizationLineageRecord,
    OrganizationMemberBelief,
    OrganizationMembershipBasis,
    OrganizationMembershipStatus,
    OrganizationOperationDomain,
    OrganizationPosition,
    OrganizationProcedureBelief,
    OrganizationProcedureKind,
    OrganizationProposal,
    OrganizationRecordBelief,
    OrganizationRecordKind,
    OrganizationResourceBelief,
    OrganizationResourceKind,
    OrganizationStatus,
    OrganizationTemporalScope,
    organization_agency_ref,
    organization_amendment_id,
    organization_collective_decision_id,
    organization_concept_digest,
    organization_concept_id,
    organization_implementation_id,
    organization_lineage_id,
    organization_proposal_id,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
OTHER = AgentId("agent-2")
ORG = f"orgc-{'a' * 16}"
DIGEST = hashlib.sha256(b"organization-agency").hexdigest()


def concept_ledger(
    *,
    owner: AgentId = OWNER,
    organization_id: str = ORG,
    status: OrganizationStatus = OrganizationStatus.RECOGNIZED,
    member_ids: tuple[str, ...] = ("agent-1", "agent-2"),
    procedure_anchor: str | None = "procedure-alpha",
    procedure_recurrence: int = 2,
    procedure_status: OrganizationStatus = OrganizationStatus.RECOGNIZED,
    resource_anchor: str | None = None,
    record_anchor: str | None = None,
    tick: int = 5,
) -> OrganizationConceptLedger:
    members = tuple(
        OrganizationMemberBelief(
            member_id=member_id,
            status=OrganizationMembershipStatus.EXPLICIT,
            basis=OrganizationMembershipBasis.PARTICIPATION,
            temporal_scope=OrganizationTemporalScope.ONGOING,
            first_tick=1,
            last_tick=tick,
            strength=0.6,
            channels=(OrganizationEvidenceChannel.OBSERVED,),
            independently_evidenced=True,
        )
        for member_id in member_ids
    )
    organization_id = organization_concept_id(
        owner.value, 1, member_ids, (procedure_anchor or "anchor-1",)
    )
    lineage = OrganizationLineageRecord(
        lineage_id=organization_lineage_id(
            owner.value, "emerged", 1, (organization_id,), (organization_id,)
        ),
        kind=OrganizationLineageKind.EMERGED,
        tick=1,
        from_ids=(organization_id,),
        to_ids=(organization_id,),
        evidence_digest=DIGEST,
    )
    procedures = (
        ()
        if procedure_anchor is None
        else (
            OrganizationProcedureBelief(
                procedure_kind=OrganizationProcedureKind.INSTITUTION_CONCEPT,
                anchor_id=procedure_anchor,
                recurrence=procedure_recurrence,
                status=procedure_status,
                first_tick=1,
                last_tick=tick,
            ),
        )
    )
    resources = (
        ()
        if resource_anchor is None
        else (
            OrganizationResourceBelief(
                resource_kind=OrganizationResourceKind.REPOSITORY,
                anchor_id=resource_anchor,
                access_belief="shared_use",
                first_tick=1,
                last_tick=tick,
            ),
        )
    )
    records = (
        ()
        if record_anchor is None
        else (
            OrganizationRecordBelief(
                record_kind=OrganizationRecordKind.ARTIFACT,
                anchor_id=record_anchor,
                integrity=1.0,
                custody_belief="claimed",
                first_tick=1,
                last_tick=tick,
            ),
        )
    )
    concept = OrganizationConcept(
        organization_id=organization_id,
        owner_id=owner,
        creation_tick=1,
        inception_digest=DIGEST,
        status=status,
        temporal_scope=OrganizationTemporalScope.ONGOING,
        strength=0.6,
        member_evidence_count=3,
        structural_channel_count=2,
        first_tick=1,
        last_tick=tick,
        members=members,
        procedures=procedures,
        resources=resources,
        records=records,
        identities=(
            OrganizationIdentityBelief(
                label_token="water-carriers",
                conceptualization=OrganizationConceptualization.NAMED_CUSTOM,
                stance=OrganizationIdentityStance.MEMBER,
                first_tick=1,
                last_tick=tick,
            ),
        ),
        lineage=(lineage,),
    )
    return OrganizationConceptLedger(owner_id=owner, concepts=(concept,))


def procedure_ref(anchor: str = "procedure-alpha") -> str:
    return organization_agency_ref(anchor, namespace="procedure")


def proposal(
    *,
    owner: AgentId = OWNER,
    organization_id: str = ORG,
    proposal_ref_value: str | None = None,
    topic: OrganizationAgencyTopic = OrganizationAgencyTopic.PROCEDURE,
    domain: OrganizationOperationDomain = OrganizationOperationDomain.PROCEDURE_ACTION,
    effect: OrganizationAgencyEffect = OrganizationAgencyEffect.NONE,
    target_kind: str = "none",
    target_ref: str | None = None,
    procedure: str | None = "procedure-alpha",
    expected_actors: tuple[AgentId, ...] = (OWNER,),
    quantity: int = 1,
    revision: int = 1,
    status: OrganizationAgencyProposalStatus = OrganizationAgencyProposalStatus.ACTIVE,
    opened_tick: int = 1,
    deadline_tick: int = 10,
    tick: int = 1,
    support_count: int = 0,
    oppose_count: int = 0,
    abstain_count: int = 0,
    contest_count: int = 0,
) -> OrganizationProposal:
    ref = (
        proposal_ref_value
        if proposal_ref_value is not None
        else organization_agency_ref("proposal-material", namespace="proposal")
    )
    pid = organization_proposal_id(owner.value, organization_id, ref)
    return OrganizationProposal(
        proposal_id=pid,
        organization_id=organization_id,
        proposal_ref=ref,
        topic=topic,
        domain=domain,
        effect=effect,
        implementation_mode=(
            OrganizationAgencyImplementationMode.TESTIMONIAL
            if effect is OrganizationAgencyEffect.NONE
            else OrganizationAgencyImplementationMode.PHYSICAL
        ),
        target_kind=target_kind,
        target_ref=target_ref,
        procedure_ref=None if procedure is None else procedure_ref(procedure),
        expected_actors=expected_actors,
        quantity=quantity,
        revision=revision,
        terms_ref=organization_agency_ref("terms-material", namespace="terms"),
        status=status,
        opened_tick=opened_tick,
        deadline_tick=deadline_tick,
        first_tick=tick,
        last_tick=tick,
        support_count=support_count,
        oppose_count=oppose_count,
        abstain_count=abstain_count,
        contest_count=contest_count,
    )


def position(
    proposal_id: str,
    *,
    actor: AgentId = OWNER,
    stance: OrganizationAgencyPositionStance = (
        OrganizationAgencyPositionStance.SUPPORT
    ),
    revision: int = 1,
    tick: int = 2,
    authority: OrganizationAuthorityBasis = OrganizationAuthorityBasis.SELF_AUTHORED,
    disputed: bool = False,
) -> OrganizationPosition:
    return OrganizationPosition(
        proposal_id=proposal_id,
        revision=revision,
        actor_id=actor,
        stance=stance,
        authority_basis=authority,
        disputed=disputed,
        tick=tick,
    )


def amendment(
    proposal_id: str,
    *,
    from_revision: int = 1,
    revision: int = 2,
    amended_tick: int = 3,
    effect: OrganizationAgencyEffect = OrganizationAgencyEffect.NONE,
    domain: OrganizationOperationDomain = OrganizationOperationDomain.PROCEDURE_ACTION,
) -> OrganizationAmendment:
    return OrganizationAmendment(
        amendment_id=organization_amendment_id(
            OWNER.value,
            ORG,
            proposal_id,
            revision,
            organization_agency_ref(f"terms-{revision}", namespace="terms"),
        ),
        proposal_id=proposal_id,
        from_revision=from_revision,
        to_revision=revision,
        terms_ref=organization_agency_ref(f"terms-{revision}", namespace="terms"),
        domain=domain,
        effect=effect,
        target_kind="none",
        target_ref=None,
        procedure_ref=procedure_ref(),
        amended_tick=amended_tick,
    )


def decision(
    proposal: OrganizationProposal,
    *,
    owner: AgentId = OWNER,
    recognition: OrganizationAgencyRecognition = (
        OrganizationAgencyRecognition.RECOGNIZED
    ),
    decided_tick: int = 6,
    window_end_tick: int = 20,
    support_count: int = 1,
    oppose_count: int = 0,
    abstain_count: int = 0,
    contest_count: int = 0,
    status: OrganizationAgencyImplementationStatus = (
        OrganizationAgencyImplementationStatus.PENDING
    ),
) -> OrganizationCollectiveDecision:
    return OrganizationCollectiveDecision(
        decision_id=organization_collective_decision_id(
            owner.value,
            proposal.organization_id,
            proposal.proposal_id,
            proposal.revision,
            recognition,
            decided_tick,
        ),
        organization_id=proposal.organization_id,
        proposal_id=proposal.proposal_id,
        revision=proposal.revision,
        procedure_ref=proposal.procedure_ref,
        recognition=recognition,
        authority_basis=OrganizationAuthorityBasis.SELF_AUTHORED,
        support_count=support_count,
        oppose_count=oppose_count,
        abstain_count=abstain_count,
        contest_count=contest_count,
        implementation_mode=proposal.implementation_mode,
        effect=proposal.effect,
        target_kind=proposal.target_kind,
        target_ref=proposal.target_ref,
        expected_actors=proposal.expected_actors,
        quantity=proposal.quantity,
        decided_tick=decided_tick,
        window_end_tick=window_end_tick,
        implementation_status=status,
        provenance_code=OrganizationAgencyProvenance.PROCEDURE_RECOGNIZED,
        resolved=proposal.target_kind not in ("none", "unknown"),
    )


def implementation(
    decision_record: OrganizationCollectiveDecision,
    *,
    owner: AgentId = OWNER,
    actor: AgentId = OWNER,
    status: OrganizationAgencyImplementationStatus = (
        OrganizationAgencyImplementationStatus.IMPLEMENTED
    ),
    observed_tick: int = 7,
    provenance: OrganizationAgencyProvenance = (
        OrganizationAgencyProvenance.OBSERVED_EFFECT
    ),
) -> OrganizationImplementation:
    return OrganizationImplementation(
        implementation_id=organization_implementation_id(
            owner.value,
            ORG,
            decision_record.decision_id,
            actor.value,
            decision_record.implementation_mode,
            observed_tick,
        ),
        decision_id=decision_record.decision_id,
        actor_id=actor,
        status=status,
        effect=decision_record.effect,
        observed_tick=observed_tick,
        provenance_code=provenance,
        resolved=status
        in (
            OrganizationAgencyImplementationStatus.IMPLEMENTED,
            OrganizationAgencyImplementationStatus.PARTIAL,
            OrganizationAgencyImplementationStatus.REFUSED,
            OrganizationAgencyImplementationStatus.SABOTAGED,
            OrganizationAgencyImplementationStatus.CONTRARY,
            OrganizationAgencyImplementationStatus.UNIMPLEMENTED,
        ),
    )


@dataclass
class FakeContent:
    relations: tuple[object, ...] = ()


@dataclass
class FakeUtterance:
    content: FakeContent = field(default_factory=FakeContent)


@dataclass
class FakeCommunication:
    speaker_id: object
    listener_id: object
    utterance: FakeUtterance = field(default_factory=FakeUtterance)


@dataclass
class FakeOccurrence:
    kind: str
    actor_id: object = EntityId("body-agent-1")
    other_entity_id: object | None = None
    destination_id: object | None = None
    success: bool | None = None
    public_facts: dict[str, object] = field(default_factory=dict)
    audience_role: str = "actor"
    source_tick: int = 0


@dataclass
class FakeObservation:
    observer_id: EntityId = field(default_factory=lambda: EntityId("body-agent-1"))
    occurrences: tuple[object, ...] = ()
    communications: tuple[object, ...] = ()
    tick: int = 0


def concept_digest(ledger: OrganizationConceptLedger) -> str:
    return organization_concept_digest(ledger.concepts[0])


def concept_id(ledger: OrganizationConceptLedger) -> str:
    return ledger.concepts[0].organization_id


__all__ = [
    "DIGEST",
    "ORG",
    "OTHER",
    "OWNER",
    "FakeCommunication",
    "FakeContent",
    "FakeObservation",
    "FakeOccurrence",
    "FakeUtterance",
    "amendment",
    "concept_digest",
    "concept_id",
    "concept_ledger",
    "decision",
    "implementation",
    "position",
    "procedure_ref",
    "proposal",
]
