"""Owner-scoped office contracts, stable identity, and recognition policy."""

from __future__ import annotations

import pytest

from agents.cognition.offices import (
    FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES,
    OFFICE_CONCEPT_POLICY_VERSION,
    OfficeConcept,
    OfficeConceptLedger,
    OfficeConceptPolicy,
    OfficeConceptStatus,
    OfficeDutyBelief,
    OfficeDutyKind,
    OfficeEvidenceChannel,
    OfficeFunction,
    OfficeOccupantClaim,
    OfficeOccupantStatus,
    appraise_office_recognition,
    default_office_concept_policy,
    empty_office_concept_ledger,
    office_concept_id,
    office_inception_digest,
    office_role_signature,
    require_owner_offices,
)
from agents.models import AgentId

_CONTEXT = "a" * 16
_OTHER_CONTEXT = "b" * 16


def _agent(value: str = "alice") -> AgentId:
    return AgentId(value)


def _concept_id(
    owner: AgentId,
    *,
    context: str = _CONTEXT,
    collision: int = 0,
    lineage: str = "occurrence-1-0-help",
) -> str:
    inception = office_inception_digest(OfficeFunction.HELP, context, lineage)
    return office_concept_id(owner, inception, collision)


def _concept(
    owner: AgentId | None = None,
    *,
    context: str = _CONTEXT,
    status: OfficeConceptStatus = OfficeConceptStatus.RECOGNIZED,
    label: str | None = None,
    duty_kind: OfficeDutyKind = OfficeDutyKind.PERFORM,
    occupant: AgentId | None = None,
    collision: int = 0,
    pruned_evidence: int = 0,
) -> OfficeConcept:
    active = owner or _agent()
    inception = office_inception_digest(OfficeFunction.HELP, context, "inception-1")
    office_id = office_concept_id(active, inception, collision)
    duties = (
        OfficeDutyBelief(
            duty_id="d" * 64,
            kind=duty_kind,
            function=OfficeFunction.HELP,
            context_key=context,
            strength=0.6,
            first_tick=1,
            last_tick=2,
        ),
    )
    occupants: tuple[OfficeOccupantClaim, ...] = ()
    if occupant is not None:
        occupants = (
            OfficeOccupantClaim(
                claim_id="c" * 64,
                occupant_id=occupant,
                status=OfficeOccupantStatus.PREFERRED,
                support_strength=0.6,
                opposition_strength=0.0,
                first_tick=1,
                last_tick=2,
            ),
        )
    return OfficeConcept(
        office_id=office_id,
        owner_id=active,
        function=OfficeFunction.HELP,
        context_key=context,
        inception_digest=inception,
        collision_discriminator=collision,
        role_signature=office_role_signature(
            OfficeFunction.HELP, context, (duty_kind,)
        ),
        status=status,
        function_strength=0.7,
        expectation_strength=0.6,
        endorsement_strength=0.5,
        first_tick=1,
        last_tick=2,
        evidence_count=4,
        independent_root_count=2,
        label_token=label,
        duties=duties,
        occupants=occupants,
        pruned_evidence_count=pruned_evidence,
    )


def test_policy_locks_constants() -> None:
    policy = default_office_concept_policy()
    assert policy.version == OFFICE_CONCEPT_POLICY_VERSION == "offices-succession.v1"
    assert policy.recognition_floor == 0.45
    assert policy.channel_floor == 0.30
    assert policy.promotion_count == 3
    assert policy.promotion_roots == 2
    assert policy.preference_margin == 0.10
    assert policy.max_concepts == 16


def test_locked_policy_mutation_rejects() -> None:
    with pytest.raises(ValueError, match="unsupported_policy"):
        OfficeConceptPolicy(recognition_floor=0.1)
    with pytest.raises(ValueError, match="unsupported_policy"):
        OfficeConceptPolicy(version="offices-succession.v2")


def test_office_id_is_stable_under_growth_and_relabel() -> None:
    owner = _agent()
    base = _concept(owner, label="steward")
    grown = _concept(owner, label="elder")
    replaced = _concept(owner, label="elder", occupant=_agent("bob"))
    assert base.office_id == grown.office_id == replaced.office_id
    assert base.office_id != _concept(owner, context=_OTHER_CONTEXT).office_id


def test_minor_duty_revision_keeps_identity_but_changes_signature() -> None:
    owner = _agent()
    perform = _concept(owner, duty_kind=OfficeDutyKind.PERFORM)
    coordinate = _concept(owner, duty_kind=OfficeDutyKind.COORDINATE)
    assert perform.office_id == coordinate.office_id
    assert perform.role_signature != coordinate.role_signature


def test_office_id_is_process_stable_and_owner_scoped() -> None:
    alice = _agent("alice")
    bob = _agent("bob")
    assert _concept_id(alice) == _concept_id(alice)
    assert _concept_id(alice) != _concept_id(bob)
    assert _concept_id(alice, collision=1) != _concept_id(alice)


def test_empty_ledger_and_carry_validation() -> None:
    owner = _agent()
    ledger = empty_office_concept_ledger(owner)
    assert ledger.concepts == ()
    assert ledger.coverage == "complete"
    require_owner_offices(ledger, owner, field_name="x")
    require_owner_offices(None, owner, field_name="x")
    with pytest.raises(ValueError, match="owner_id mismatch"):
        require_owner_offices(
            OfficeConceptLedger(owner_id=_agent("bob")), owner, field_name="x"
        )
    with pytest.raises(TypeError):
        require_owner_offices(object(), owner, field_name="x")


def test_cross_owner_concept_rejects() -> None:
    owner = _agent()
    foreign = _concept(_agent("bob"))
    with pytest.raises(ValueError, match="owner_mismatch"):
        OfficeConceptLedger(owner_id=owner, concepts=(foreign,))


def test_caps_expose_partial_coverage() -> None:
    concept = _concept(pruned_evidence=3)
    assert concept.evidence_coverage == "partial"
    ledger = OfficeConceptLedger(
        owner_id=concept.owner_id, concepts=(concept,), pruned_concept_count=2
    )
    assert ledger.coverage == "partial"


def test_preferred_occupant_ties_stay_unresolved() -> None:
    owner = _agent()
    concept = _concept(owner, occupant=_agent("bob"))
    first = concept.occupants[0]
    rival = OfficeOccupantClaim(
        claim_id="e" * 64,
        occupant_id=_agent("carol"),
        status=OfficeOccupantStatus.CANDIDATE,
        support_strength=first.support_strength,
        opposition_strength=first.opposition_strength,
        first_tick=1,
        last_tick=2,
    )
    disputed = OfficeConcept(
        office_id=concept.office_id,
        owner_id=concept.owner_id,
        function=concept.function,
        context_key=concept.context_key,
        inception_digest=concept.inception_digest,
        collision_discriminator=concept.collision_discriminator,
        role_signature=concept.role_signature,
        status=OfficeConceptStatus.DISPUTED,
        function_strength=concept.function_strength,
        expectation_strength=concept.expectation_strength,
        endorsement_strength=concept.endorsement_strength,
        first_tick=1,
        last_tick=2,
        evidence_count=4,
        independent_root_count=2,
        duties=concept.duties,
        occupants=(first, rival),
    )
    assert disputed.preferred_occupant is None


def test_forbidden_office_vocabulary_includes_objective_occupant() -> None:
    assert "current_occupant" in FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES
    assert "office_type" in FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES
    assert "government" in FORBIDDEN_OFFICE_CONCEPT_FIELD_NAMES


def test_influence_only_evidence_never_recognizes() -> None:
    appraisal = appraise_office_recognition(
        function_strength=0.9,
        expectation_strength=0.0,
        endorsement_strength=0.0,
        independent_root_count=5,
        qualifying_evidence_count=6,
    )
    assert not appraisal.recognized
    assert appraisal.reason == "influence_only"


def test_same_root_repetition_cannot_promote() -> None:
    appraisal = appraise_office_recognition(
        function_strength=0.9,
        expectation_strength=0.6,
        endorsement_strength=0.6,
        independent_root_count=1,
        qualifying_evidence_count=6,
    )
    assert not appraisal.recognized
    assert appraisal.reason == "missing_independent_root"


def test_independent_role_directed_evidence_recognizes() -> None:
    appraisal = appraise_office_recognition(
        function_strength=0.6,
        expectation_strength=0.5,
        endorsement_strength=0.0,
        independent_root_count=2,
        qualifying_evidence_count=3,
    )
    assert appraisal.recognized
    assert appraisal.reason == "recognized"


def test_evidence_channel_is_closed() -> None:
    assert {item.value for item in OfficeEvidenceChannel} == {
        "observed",
        "communicated",
        "remembered",
    }
