"""Recipient-relative mediation authority appraisal from real source shapes."""

from __future__ import annotations

from agents.cognition.institution_concepts import (
    InstitutionConcept,
    InstitutionConceptLedger,
    InstitutionConceptStatus,
    InstitutionConceptualization,
    InstitutionPatternChannel,
    institution_concept_id,
    institution_evidence_id,
)
from agents.cognition.mediation import (
    MediationAuthorityChannel,
    appraise_mediation_authority,
)
from agents.cognition.offices import (
    OfficeConcept,
    OfficeConceptLedger,
    OfficeConceptStatus,
    OfficeFunction,
    OfficeOccupantClaim,
    OfficeOccupantStatus,
    office_concept_id,
    office_inception_digest,
    office_role_signature,
)
from agents.cognition.reputation import (
    ReputationDimensionState,
    ReputationLedger,
    ReputationProfile,
    reputation_profile_id,
)
from agents.cognition.social_norms import (
    NormBelief,
    NormContext,
    NormExpectation,
    NormLedger,
    NormPattern,
    NormStatus,
    norm_belief_id,
)
from agents.models import AgentId
from social import RelationshipId
from social.relationships import (
    DirectedRelationshipProfile,
    RelationshipActivationState,
    RelationshipConfidence,
    RelationshipDimension,
    RelationshipDimensionState,
    RelationshipPolicyRef,
    RelationshipRevisionId,
)

_OWNER = AgentId("ada")
_MEDIATOR = AgentId("carol")
_CONTEXT = "a" * 16


def _relationship(*, trust: float) -> DirectedRelationshipProfile:
    policy = RelationshipPolicyRef(policy_id="rel-v1", version="1")
    confidence = RelationshipConfidence(
        confidence=1.0, support_mass=1.0, contradiction_mass=0.0
    )
    dimensions = tuple(
        RelationshipDimensionState(
            dimension=dimension,
            value=value,
            confidence=confidence,
            evidence=(),
            logical_tick=1,
            policy=policy,
        )
        for dimension, value in (
            (RelationshipDimension.TRUST, trust),
            (RelationshipDimension.FAMILIARITY, trust),
            (RelationshipDimension.AFFECTION, trust),
        )
    )
    return DirectedRelationshipProfile(
        relationship_id=RelationshipId("rel-1"),
        source_id=_OWNER,
        target_id=_MEDIATOR,
        dimensions=dimensions,
        activation_state=RelationshipActivationState.ACTIVE,
        current_revision_id=RelationshipRevisionId("rrev-1"),
        revision_ordinal=1,
        created_tick=1,
        updated_tick=1,
        policy=policy,
    )


def _reputation(*, reliability: float, harm: float) -> ReputationLedger:
    def state(value: float) -> ReputationDimensionState:
        return ReputationDimensionState(
            value=value, support_mass=1.0, contradiction_mass=0.0
        )

    return ReputationLedger(
        owner_id=_OWNER,
        profiles=(
            ReputationProfile(
                profile_id=reputation_profile_id(_OWNER, _MEDIATOR),
                owner_id=_OWNER,
                target_id=_MEDIATOR,
                reliability=state(reliability),
                harm=state(harm),
                generosity=state(0.5),
                competence=state(0.5),
            ),
        ),
    )


_EXPECTATION = {
    NormPattern.RETURN_TRANSFER: NormExpectation.GIVE_BACK,
    NormPattern.SHARE_UNDER_SCARCITY: NormExpectation.GIVE,
    NormPattern.SPARE_AFTER_SLEEP: NormExpectation.WITHHOLD_ATTACK,
    NormPattern.RECIPROCAL_EXCHANGE: NormExpectation.GIVE_AGAIN,
    NormPattern.SHARED_UPKEEP: NormExpectation.MAINTAIN_STRUCTURE,
}


def _norm(*, pattern: NormPattern, counterpart: AgentId | None) -> NormLedger:
    return NormLedger(
        owner_id=_OWNER,
        beliefs=(
            NormBelief(
                belief_id=norm_belief_id(_OWNER, pattern, ()),
                owner_id=_OWNER,
                pattern=pattern,
                expectation=_EXPECTATION[pattern],
                context=NormContext(pattern=pattern, counterpart_id=counterpart),
                status=NormStatus.ACTIVE,
                confidence=0.8,
            ),
        ),
    )


def _office(*, mediator: AgentId, context: str) -> OfficeConceptLedger:
    inception = office_inception_digest(
        OfficeFunction.CONFLICT_MEDIATION, context, "inception"
    )
    return OfficeConceptLedger(
        owner_id=_OWNER,
        concepts=(
            OfficeConcept(
                office_id=office_concept_id(_OWNER, inception, 0),
                owner_id=_OWNER,
                function=OfficeFunction.CONFLICT_MEDIATION,
                context_key=context,
                inception_digest=inception,
                collision_discriminator=0,
                role_signature=office_role_signature(
                    OfficeFunction.CONFLICT_MEDIATION, context, ()
                ),
                status=OfficeConceptStatus.RECOGNIZED,
                function_strength=0.8,
                expectation_strength=0.7,
                endorsement_strength=0.7,
                first_tick=1,
                last_tick=5,
                evidence_count=4,
                independent_root_count=2,
                occupants=(
                    OfficeOccupantClaim(
                        claim_id="c" * 64,
                        occupant_id=mediator,
                        status=OfficeOccupantStatus.PREFERRED,
                        support_strength=0.8,
                        opposition_strength=0.0,
                        first_tick=1,
                        last_tick=5,
                    ),
                ),
            ),
        ),
    )


def _institution(*, anchor: str, mediator: AgentId) -> InstitutionConceptLedger:
    from agents.cognition.institution_concepts import (
        InstitutionConceptEvidence,
        InstitutionEvidenceChannel,
    )

    concept_id = institution_concept_id(_OWNER, (anchor,))
    channels = (
        InstitutionPatternChannel.ROLE_RECOGNITION,
        InstitutionPatternChannel.PROCEDURE_RECURRENCE,
        InstitutionPatternChannel.SOCIAL_EXPECTATION,
    )
    evidence = tuple(
        InstitutionConceptEvidence(
            evidence_id=institution_evidence_id(
                concept_id,
                ordinal,
                InstitutionEvidenceChannel.OBSERVED,
                channel,
                f"lineage-{ordinal}",
            ),
            ordinal=ordinal,
            channel=InstitutionEvidenceChannel.OBSERVED,
            pattern=channel,
            lineage_ref=f"lineage-{ordinal}",
            tick=1,
            anchor_digest=anchor,
        )
        for ordinal, channel in enumerate(channels)
    )
    return InstitutionConceptLedger(
        owner_id=_OWNER,
        concepts=(
            InstitutionConcept(
                concept_id=concept_id,
                owner_id=_OWNER,
                group_key="b" * 64,
                anchor_digests=(anchor,),
                status=InstitutionConceptStatus.RECOGNIZED,
                conceptualization=InstitutionConceptualization.NONE,
                role_recognition=0.5,
                procedure_recurrence=0.5,
                social_expectation=0.5,
                legitimacy_belief=0.7,
                succession_observed=0.0,
                generational_continuity=0.0,
                evidence_count=3,
                first_tick=1,
                last_tick=3,
                evidence=evidence,
            ),
        ),
    )


def test_all_five_sources_are_available_and_independent() -> None:
    appraisal = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        relationships=(_relationship(trust=0.8),),
        reputation=_reputation(reliability=0.7, harm=0.0),
        social_norms=_norm(
            pattern=NormPattern.RECIPROCAL_EXCHANGE, counterpart=_MEDIATOR
        ),
        office_concepts=_office(mediator=_MEDIATOR, context=_CONTEXT),
        institution_concepts=_institution(anchor=_CONTEXT, mediator=_MEDIATOR),
    )
    assert set(appraisal.available_channels) == {
        MediationAuthorityChannel.RELATIONSHIP,
        MediationAuthorityChannel.REPUTATION,
        MediationAuthorityChannel.ROLE,
        MediationAuthorityChannel.NORM,
        MediationAuthorityChannel.INSTITUTION,
    }
    assert appraisal.unavailable_channels == ()


def test_missing_sources_stay_unavailable() -> None:
    appraisal = appraise_mediation_authority(_OWNER, _MEDIATOR, _CONTEXT)
    assert appraisal.available_channels == ()
    assert len(appraisal.unavailable_channels) == 5


def test_unrelated_norm_and_office_do_not_increase_appraisal() -> None:
    unrelated_norm = _norm(pattern=NormPattern.SPARE_AFTER_SLEEP, counterpart=None)
    unrelated_office = _office(mediator=_MEDIATOR, context="c" * 16)
    appraisal = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        social_norms=unrelated_norm,
        office_concepts=unrelated_office,
    )
    assert appraisal.component(MediationAuthorityChannel.NORM).available is False
    assert appraisal.component(MediationAuthorityChannel.ROLE).available is False


def test_unlinked_institution_stays_unavailable() -> None:
    appraisal = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        institution_concepts=_institution(anchor="d" * 16, mediator=_MEDIATOR),
    )
    assert appraisal.component(MediationAuthorityChannel.INSTITUTION).available is False


def test_opposing_parties_appraise_the_same_mediator_differently() -> None:
    high = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        relationships=(_relationship(trust=0.9),),
        reputation=_reputation(reliability=0.9, harm=-0.5),
    )
    low = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        relationships=(_relationship(trust=-0.9),),
        reputation=_reputation(reliability=-0.9, harm=0.9),
    )
    assert (
        high.component(MediationAuthorityChannel.RELATIONSHIP).strength
        > low.component(MediationAuthorityChannel.RELATIONSHIP).strength
    )
    assert (
        high.component(MediationAuthorityChannel.REPUTATION).strength
        > low.component(MediationAuthorityChannel.REPUTATION).strength
    )


def test_high_appraisal_does_not_become_binding_authority() -> None:
    appraisal = appraise_mediation_authority(
        _OWNER,
        _MEDIATOR,
        _CONTEXT,
        relationships=(_relationship(trust=1.0),),
        reputation=_reputation(reliability=1.0, harm=-1.0),
    )
    for component in appraisal.components:
        if component.available:
            assert 0.0 <= component.strength <= 1.0
    assert "binding" not in repr(appraisal)
