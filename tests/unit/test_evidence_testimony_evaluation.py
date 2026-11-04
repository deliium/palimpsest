"""V4-08 owner-relative evaluation and retained contradictions."""

from __future__ import annotations

import pytest

from agents.cognition import (
    EvidenceContradictionKind,
    EvidenceContradictionStatus,
    EvidenceError,
    EvidenceInterpretationKind,
    EvidenceLedger,
    EvidenceOwnerContext,
    EvidenceProvenanceChannel,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    detect_evidence_contradictions,
    evaluate_evidence,
    evidence_case_summary,
    evidence_confidence_bias,
    evidence_contradiction_penalty,
    evidence_ledger_digest,
    set_contradiction_preference,
)
from tests.unit.evidence_testimony_helpers import (
    OTHER_OWNER,
    OWNER,
    make_item,
    make_source,
    make_testimony,
)

pytestmark = pytest.mark.unit


def _direct_ledger(*, actor: str | None = None) -> EvidenceLedger:
    source = make_source(actor_id=actor)
    item = make_item(source_id=source.source_id, confidence=0.8)
    return EvidenceLedger(owner_id=OWNER, sources=(source,), items=(item,))


def test_direct_observation_uses_direct_experience() -> None:
    ledger = evaluate_evidence(
        _direct_ledger(),
        owner_id=OWNER,
        tick=2,
        context=EvidenceOwnerContext(),
    )
    evaluation = ledger.evaluations[0]
    assert evaluation.bases == (EvidenceTrustBasis.DIRECT_EXPERIENCE,)
    assert evaluation.confidence == 0.8
    assert evaluation.kind.value == "uncorroborated"
    assert "evidence_trust_basis_missing" not in ledger.notices


def test_relationship_and_reputation_are_bounded_and_idempotent() -> None:
    ledger = _direct_ledger(actor=OTHER_OWNER)
    context = EvidenceOwnerContext(
        relationship_trust=((OTHER_OWNER, 0.9),),
        reputation_bands=((OTHER_OWNER, "trusted"),),
    )
    evaluated = evaluate_evidence(ledger, owner_id=OWNER, tick=2, context=context)
    evaluation = evaluated.evaluations[0]
    assert evaluation.bases == (
        EvidenceTrustBasis.DIRECT_EXPERIENCE,
        EvidenceTrustBasis.RELATIONSHIP_TRUST,
        EvidenceTrustBasis.REPUTATION,
    )
    assert 0.0 <= evaluation.confidence <= 1.0
    assert evaluation.relationship_ref == OTHER_OWNER
    assert evaluation.reputation_ref == OTHER_OWNER

    repeated = evaluate_evidence(evaluated, owner_id=OWNER, tick=2, context=context)
    assert evidence_ledger_digest(repeated) == evidence_ledger_digest(evaluated)
    assert len(repeated.evaluations) == 1


def test_missing_trust_yields_none_and_neutral_confidence() -> None:
    ledger = evaluate_evidence(
        _direct_ledger(),
        owner_id=OWNER,
        tick=2,
        context=EvidenceOwnerContext(),
    )
    assert ledger.evaluations[0].bases == (EvidenceTrustBasis.DIRECT_EXPERIENCE,)

    source = make_source(
        provenance=EvidenceProvenanceChannel.COMMUNICATED,
        actor_id=None,
    )
    item = make_item(
        source_id=source.source_id,
        provenance=EvidenceProvenanceChannel.COMMUNICATED,
    )
    ledger = EvidenceLedger(owner_id=OWNER, sources=(source,), items=(item,))
    evaluated = evaluate_evidence(
        ledger, owner_id=OWNER, tick=2, context=EvidenceOwnerContext()
    )
    assert evaluated.evaluations[0].bases == (EvidenceTrustBasis.NONE,)
    assert evaluated.evaluations[0].confidence == 0.5
    assert "evidence_trust_basis_missing" in evaluated.notices


def test_shared_roots_are_not_corroboration() -> None:
    first = make_testimony(
        channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        subject="subject-1",
        ordinal=0,
    )
    second = make_testimony(
        channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        subject="subject-1",
        ordinal=1,
        speaker="agent-3",
    )
    first_item = make_item(testimony_id=first.testimony_id, subject="subject-1")
    second_item = make_item(
        testimony_id=second.testimony_id, subject="subject-1", ordinal=1
    )
    ledger = EvidenceLedger(
        owner_id=OWNER,
        testimony=(first, second),
        items=(first_item, second_item),
    )
    evaluated = evaluate_evidence(
        ledger, owner_id=OWNER, tick=2, context=EvidenceOwnerContext()
    )
    assert {row.kind.value for row in evaluated.evaluations} == {"uncorroborated"}


def test_distinct_roots_corroborate() -> None:
    first = make_source(reference_id="artifact-1", ordinal=0)
    second = make_source(reference_id="artifact-2", ordinal=1)
    first_item = make_item(source_id=first.source_id, subject="subject-1")
    second_item = make_item(source_id=second.source_id, subject="subject-1", ordinal=1)
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(first, second), items=(first_item, second_item)
    )
    evaluated = evaluate_evidence(
        ledger, owner_id=OWNER, tick=2, context=EvidenceOwnerContext()
    )
    assert {row.kind.value for row in evaluated.evaluations} == {"corroborated"}


def test_opposing_interpretations_are_retained_and_can_be_preferred() -> None:
    source = make_source()
    supports = make_item(
        source_id=source.source_id,
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        ordinal=0,
    )
    contradicts = make_item(
        source_id=source.source_id,
        interpretation=EvidenceInterpretationKind.CONTRADICTS,
        ordinal=1,
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), items=(supports, contradicts)
    )
    detected = detect_evidence_contradictions(ledger, owner_id=OWNER, tick=3)
    assert len(detected.contradictions) == 1
    contradiction = detected.contradictions[0]
    assert contradiction.kind is EvidenceContradictionKind.INTERPRETATION_CONFLICT
    assert contradiction.status is EvidenceContradictionStatus.UNRESOLVED
    assert "evidence_contradiction_retained" in detected.notices
    assert contradiction.contradiction_id in detected.items[0].contradiction_refs

    first = set_contradiction_preference(
        detected,
        contradiction.contradiction_id,
        EvidenceContradictionStatus.OWNER_PREFERS_FIRST,
        owner_id=OWNER,
    )
    assert first.contradictions[0].status is (
        EvidenceContradictionStatus.OWNER_PREFERS_FIRST
    )
    assert {row.first_ref for row in first.contradictions} == {contradiction.first_ref}
    assert {row.second_ref for row in first.contradictions} == {
        contradiction.second_ref
    }

    second = set_contradiction_preference(
        first,
        contradiction.contradiction_id,
        EvidenceContradictionStatus.OWNER_PREFERS_SECOND,
        owner_id=OWNER,
    )
    assert second.contradictions[0].status is (
        EvidenceContradictionStatus.OWNER_PREFERS_SECOND
    )
    assert second.contradictions[0].first_ref == contradiction.first_ref
    assert second.contradictions[0].second_ref == contradiction.second_ref

    unresolved = set_contradiction_preference(
        second,
        contradiction.contradiction_id,
        EvidenceContradictionStatus.UNRESOLVED,
        owner_id=OWNER,
    )
    assert unresolved.contradictions[0].status is (
        EvidenceContradictionStatus.UNRESOLVED
    )

    with pytest.raises(EvidenceError) as error:
        set_contradiction_preference(
            detected,
            "evx-" + "0" * 16,
            EvidenceContradictionStatus.WITHDRAWN,
            owner_id=OWNER,
        )
    assert error.value.code == "evidence_unknown_reference"


def test_custody_disagreement_is_a_custody_conflict() -> None:
    source = make_source()
    from tests.unit.evidence_testimony_helpers import make_custody

    first = make_custody(
        source_id=source.source_id, link_index=0, tick=2, holder_token="agent-2"
    )
    second = make_custody(
        source_id=source.source_id, link_index=1, tick=2, holder_token="agent-3"
    )
    ledger = EvidenceLedger(
        owner_id=OWNER, sources=(source,), custody_links=(first, second)
    )
    detected = detect_evidence_contradictions(ledger, owner_id=OWNER, tick=3)
    assert len(detected.contradictions) == 1
    assert detected.contradictions[0].kind is (
        EvidenceContradictionKind.CUSTODY_CONFLICT
    )


def test_hooks_are_bounded_and_never_construct_commands() -> None:
    ledger = _direct_ledger()
    evaluated = evaluate_evidence(
        ledger, owner_id=OWNER, tick=1, context=EvidenceOwnerContext()
    )
    bias = evidence_confidence_bias(evaluated, "subject-1")
    penalty = evidence_contradiction_penalty(evaluated, "subject-1")
    assert -0.25 <= bias <= 0.25
    assert 0.0 <= penalty <= 0.5
    assert bias == 0.15
    assert penalty == 0.0
    assert evidence_confidence_bias(evaluated, "unknown-subject") == 0.0
    assert evidence_case_summary(evaluated).startswith("sources=1 testimony=0")
    assert "verdict" not in evidence_case_summary(evaluated)

    assert "AgentCommand" not in evidence_case_summary(evaluated)
