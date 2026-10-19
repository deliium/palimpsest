"""Owner-scoped institution-concept contracts and validation."""

from __future__ import annotations

import pytest

from agents.cognition.configuration import CognitionInstitutionConceptMode
from agents.cognition.institution_concepts import (
    FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES,
    INSTITUTION_CONCEPT_POLICY_VERSION,
    InstitutionConcept,
    InstitutionConceptEvidence,
    InstitutionConceptLedger,
    InstitutionConceptPolicy,
    InstitutionConceptStatus,
    InstitutionConceptualization,
    InstitutionEvidenceChannel,
    InstitutionPatternChannel,
    default_institution_concept_policy,
    empty_institution_concept_ledger,
    institution_concept_id,
    institution_evidence_id,
    require_owner_institution_concepts,
)
from agents.models import AgentId


def _agent(value: str = "alice") -> AgentId:
    return AgentId(value)


def _ledger(owner: AgentId, *concepts: InstitutionConcept) -> InstitutionConceptLedger:
    return InstitutionConceptLedger(owner_id=owner, concepts=tuple(concepts))


def _evidence(
    concept_id: str,
    ordinal: int,
    anchor: str,
    *,
    tick: int = 1,
    channel: InstitutionPatternChannel = InstitutionPatternChannel.ROLE_RECOGNITION,
) -> InstitutionConceptEvidence:
    return InstitutionConceptEvidence(
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
        tick=tick,
        anchor_digest=anchor,
    )


def _concept(owner: AgentId, *, recognized: bool = False) -> InstitutionConcept:
    anchor = "a" * 16
    concept_id = institution_concept_id(owner, (anchor,))
    return InstitutionConcept(
        concept_id=concept_id,
        owner_id=owner,
        group_key="b" * 64,
        anchor_digests=(anchor,),
        status=(
            InstitutionConceptStatus.RECOGNIZED
            if recognized
            else InstitutionConceptStatus.CANDIDATE
        ),
        conceptualization=InstitutionConceptualization.NONE,
        evidence_count=3,
        first_tick=1,
        last_tick=3,
        evidence=(
            _evidence(
                concept_id,
                0,
                anchor,
                channel=InstitutionPatternChannel.ROLE_RECOGNITION,
            ),
            _evidence(
                concept_id,
                1,
                anchor,
                channel=InstitutionPatternChannel.PROCEDURE_RECURRENCE,
            ),
            _evidence(
                concept_id,
                2,
                anchor,
                channel=InstitutionPatternChannel.SOCIAL_EXPECTATION,
            ),
        ),
        role_recognition=0.5,
        procedure_recurrence=0.5,
        social_expectation=0.5,
        legitimacy_belief=0.0,
        succession_observed=0.0,
        generational_continuity=0.0,
    )


def test_policy_locks_constants_and_modes_match() -> None:
    policy = default_institution_concept_policy()
    assert policy.version == INSTITUTION_CONCEPT_POLICY_VERSION
    assert policy.version == "institution-concepts.v1"
    assert policy.recognition_floor == 0.45
    assert policy.channel_floor == 0.30
    assert policy.promotion_count == 3
    assert policy.promotion_channels == 3
    assert CognitionInstitutionConceptMode.DISABLED.value == "disabled"
    assert CognitionInstitutionConceptMode.DETERMINISTIC.value == "deterministic"


def test_locked_policy_mutation_rejects() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionConceptPolicy(recognition_floor=0.2)
    with pytest.raises(ValueError, match="unsupported_policy"):
        InstitutionConceptPolicy(version="institution-concepts.v2")


def test_concept_id_is_process_stable_and_owner_scoped() -> None:
    alice = _agent("alice")
    bob = _agent("bob")
    first = institution_concept_id(alice, ("a" * 16,))
    assert first == institution_concept_id(alice, ("a" * 16,))
    assert first != institution_concept_id(bob, ("a" * 16,))
    assert first != institution_concept_id(alice, ("a" * 16, "b" * 16))
    assert len(first) == 64


def test_empty_ledger_and_carry_validation() -> None:
    owner = _agent()
    ledger = empty_institution_concept_ledger(owner)
    assert ledger.owner_id == owner
    assert ledger.concepts == ()
    require_owner_institution_concepts(ledger, owner, field_name="x")
    require_owner_institution_concepts(None, owner, field_name="x")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_institution_concepts(
            _ledger(_agent("bob")), owner, field_name="x"
        )
    with pytest.raises(TypeError):
        require_owner_institution_concepts(object(), owner, field_name="x")


def test_concept_validates_strengths_and_evidence() -> None:
    owner = _agent()
    concept = _concept(owner)
    assert concept.evidence_count == 3
    assert concept.active_channels == (
        InstitutionPatternChannel.ROLE_RECOGNITION,
        InstitutionPatternChannel.PROCEDURE_RECURRENCE,
        InstitutionPatternChannel.SOCIAL_EXPECTATION,
    )
    with pytest.raises(ValueError, match="out_of_range"):
        InstitutionConcept(
            concept_id=concept.concept_id,
            owner_id=owner,
            group_key=concept.group_key,
            anchor_digests=concept.anchor_digests,
            status=concept.status,
            conceptualization=concept.conceptualization,
            role_recognition=1.5,
            procedure_recurrence=0.0,
            social_expectation=0.0,
            legitimacy_belief=0.0,
            succession_observed=0.0,
            generational_continuity=0.0,
            evidence_count=0,
            first_tick=1,
            last_tick=1,
        )


def test_cross_owner_concepts_reject() -> None:
    owner = _agent()
    with pytest.raises(ValueError, match="owner_mismatch"):
        InstitutionConceptLedger(owner_id=owner, concepts=(_concept(_agent("bob")),))


def test_named_custom_requires_token() -> None:
    owner = _agent()
    concept = _concept(owner)
    with pytest.raises(ValueError, match="named_custom_requires_token"):
        InstitutionConcept(
            concept_id=concept.concept_id,
            owner_id=owner,
            group_key=concept.group_key,
            anchor_digests=concept.anchor_digests,
            status=concept.status,
            conceptualization=InstitutionConceptualization.NAMED_CUSTOM,
            role_recognition=0.0,
            procedure_recurrence=0.0,
            social_expectation=0.0,
            legitimacy_belief=0.0,
            succession_observed=0.0,
            generational_continuity=0.0,
            evidence_count=0,
            first_tick=1,
            last_tick=1,
        )


def test_forbidden_institution_field_names_are_blocked() -> None:
    assert "government" in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    assert "corporation" in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    assert "political_party" in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    assert "office" in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    assert "role_recognition" not in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
    assert "procedure_recurrence" not in FORBIDDEN_INSTITUTION_CONCEPT_FIELD_NAMES
