"""Synthetic owner-scoped evidence rows shared by V4-08 unit tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agents.cognition import (
    EvidenceContradiction,
    EvidenceContradictionKind,
    EvidenceContradictionStatus,
    EvidenceCustodyLink,
    EvidenceCustodyRole,
    EvidenceEvaluation,
    EvidenceEvaluationKind,
    EvidenceIntegrityBelief,
    EvidenceInterpretationKind,
    EvidenceItem,
    EvidenceItemStatus,
    EvidenceLedger,
    EvidenceProvenanceChannel,
    EvidenceReferenceKind,
    EvidenceSource,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    EvidenceWitnessStatement,
    evidence_contradiction_id,
    evidence_custody_id,
    evidence_evaluation_id,
    evidence_item_id,
    evidence_source_id,
    evidence_testimony_id,
)

OWNER = "agent-1"
OTHER_OWNER = "agent-2"


def make_source(
    *,
    owner: str = OWNER,
    kind: EvidenceSourceKind = EvidenceSourceKind.ARTIFACT,
    reference_kind: EvidenceReferenceKind = EvidenceReferenceKind.ARTIFACT,
    reference_id: str = "artifact-1",
    provenance: EvidenceProvenanceChannel = (
        EvidenceProvenanceChannel.DIRECT_OBSERVATION
    ),
    tick: int = 1,
    ordinal: int = 0,
    confidence: float = 0.8,
    integrity: EvidenceIntegrityBelief = EvidenceIntegrityBelief.INTACT,
    correlation_id: str | None = "evt-0000000000000000",
    actor_id: str | None = None,
    root_ref: str | None = None,
    independently_evidenced: bool = False,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=evidence_source_id(
            owner, kind, reference_kind, reference_id, ordinal
        ),
        owner_id=owner,
        source_kind=kind,
        reference_kind=reference_kind,
        reference_id=reference_id,
        correlation_id=correlation_id,
        provenance=provenance,
        tick=tick,
        actor_id=actor_id,
        confidence=confidence,
        integrity=integrity,
        root_ref=root_ref,
        ordinal=ordinal,
        independently_evidenced=independently_evidenced,
    )


def make_testimony(
    *,
    owner: str = OWNER,
    speaker: str = OTHER_OWNER,
    subject: str = "subject-1",
    channel: EvidenceTestimonyChannel = EvidenceTestimonyChannel.DIRECT,
    root_ref: str | None = None,
    independently_evidenced: bool = False,
    provenance: EvidenceProvenanceChannel = EvidenceProvenanceChannel.COMMUNICATED,
    tick: int = 1,
    ordinal: int = 0,
    confidence: float = 0.7,
    source_id: str | None = None,
    context_ref: str | None = None,
) -> EvidenceWitnessStatement:
    return EvidenceWitnessStatement(
        testimony_id=evidence_testimony_id(
            owner, speaker, channel, root_ref or "-", ordinal
        ),
        owner_id=owner,
        speaker_id=speaker,
        subject_token=subject,
        channel=channel,
        root_ref=root_ref,
        independently_evidenced=independently_evidenced,
        confidence=confidence,
        provenance=provenance,
        tick=tick,
        source_id=source_id,
        context_ref=context_ref,
        ordinal=ordinal,
    )


def make_item(
    *,
    owner: str = OWNER,
    source_id: str | None = None,
    testimony_id: str | None = None,
    interpretation: EvidenceInterpretationKind = (EvidenceInterpretationKind.SUPPORTS),
    subject: str = "subject-1",
    confidence: float = 0.8,
    tick: int = 1,
    status: EvidenceItemStatus = EvidenceItemStatus.ACTIVE,
    provenance: EvidenceProvenanceChannel = (
        EvidenceProvenanceChannel.DIRECT_OBSERVATION
    ),
    contradiction_refs: Sequence[str] = (),
    context_ref: str | None = None,
    reason_code: str = "",
    ordinal: int = 0,
) -> EvidenceItem:
    anchor = source_id if source_id is not None else testimony_id
    if anchor is None:
        raise AssertionError("item needs an anchor")
    return EvidenceItem(
        item_id=evidence_item_id(owner, anchor, interpretation, ordinal),
        owner_id=owner,
        source_id=source_id,
        testimony_id=testimony_id,
        interpretation=interpretation,
        subject_token=subject,
        confidence=confidence,
        tick=tick,
        status=status,
        provenance=provenance,
        contradiction_refs=tuple(contradiction_refs),
        context_ref=context_ref,
        reason_code=reason_code,
        ordinal=ordinal,
    )


def make_custody(
    *,
    owner: str = OWNER,
    source_id: str,
    link_index: int = 0,
    role: EvidenceCustodyRole = EvidenceCustodyRole.HOLDER,
    subject: str = "artifact-1",
    holder_token: str | None = "agent-1",
    custodian_token: str | None = None,
    location_token: str | None = None,
    tick: int = 1,
    provenance: EvidenceProvenanceChannel = (
        EvidenceProvenanceChannel.DIRECT_OBSERVATION
    ),
    integrity: EvidenceIntegrityBelief = EvidenceIntegrityBelief.INTACT,
    witnessed: bool = False,
) -> EvidenceCustodyLink:
    return EvidenceCustodyLink(
        custody_id=evidence_custody_id(
            owner, source_id, link_index, role, subject, tick
        ),
        owner_id=owner,
        source_id=source_id,
        link_index=link_index,
        role=role,
        subject_token=subject,
        holder_token=holder_token,
        custodian_token=custodian_token,
        location_token=location_token,
        tick=tick,
        provenance=provenance,
        integrity=integrity,
        witnessed=witnessed,
    )


def make_contradiction(
    *,
    owner: str = OWNER,
    first_ref: str,
    second_ref: str,
    kind: EvidenceContradictionKind = EvidenceContradictionKind.INTERPRETATION_CONFLICT,
    status: EvidenceContradictionStatus = EvidenceContradictionStatus.UNRESOLVED,
    provenance: EvidenceProvenanceChannel = (EvidenceProvenanceChannel.DERIVED),
    tick: int = 1,
    ordinal: int = 0,
    context_ref: str | None = None,
) -> EvidenceContradiction:
    return EvidenceContradiction(
        contradiction_id=evidence_contradiction_id(
            owner, first_ref, second_ref, kind, ordinal
        ),
        owner_id=owner,
        first_ref=first_ref,
        second_ref=second_ref,
        kind=kind,
        status=status,
        provenance=provenance,
        tick=tick,
        context_ref=context_ref,
        ordinal=ordinal,
    )


def make_evaluation(
    *,
    owner: str = OWNER,
    item_id: str,
    bases: Sequence[EvidenceTrustBasis] = (EvidenceTrustBasis.DIRECT_EXPERIENCE,),
    confidence: float = 0.6,
    kind: EvidenceEvaluationKind = EvidenceEvaluationKind.CORROBORATED,
    provenance: EvidenceProvenanceChannel = (EvidenceProvenanceChannel.DERIVED),
    tick: int = 1,
    ordinal: int = 0,
    relationship_ref: str | None = None,
    reputation_ref: str | None = None,
    rule_ref: str | None = None,
    office_ref: str | None = None,
    institution_ref: str | None = None,
) -> EvidenceEvaluation:
    ordered = tuple(sorted(bases, key=lambda basis: basis.value))
    return EvidenceEvaluation(
        evaluation_id=evidence_evaluation_id(
            owner, item_id, ",".join(basis.value for basis in ordered), ordinal
        ),
        owner_id=owner,
        item_id=item_id,
        bases=ordered,
        confidence=confidence,
        kind=kind,
        provenance=provenance,
        tick=tick,
        relationship_ref=relationship_ref,
        reputation_ref=reputation_ref,
        rule_ref=rule_ref,
        office_ref=office_ref,
        institution_ref=institution_ref,
        ordinal=ordinal,
    )


@dataclass(frozen=True, slots=True)
class LedgerParts:
    """Convenience bundle used by record, provenance, and evaluation tests."""

    source: EvidenceSource
    testimony: EvidenceWitnessStatement
    item: EvidenceItem
    contradiction: EvidenceContradiction
    evaluation: EvidenceEvaluation
    custody: EvidenceCustodyLink

    def ledger(self, **overrides: object) -> EvidenceLedger:
        values: dict[str, object] = {
            "owner_id": self.source.owner_id,
            "sources": (self.source,),
            "custody_links": (self.custody,),
            "testimony": (self.testimony,),
            "items": (self.item,),
            "contradictions": (self.contradiction,),
            "evaluations": (self.evaluation,),
            "observation_start_tick": 1,
            "observation_end_tick": 1,
            "observation_count": 1,
        }
        values.update(overrides)
        return EvidenceLedger(**values)  # type: ignore[arg-type]


def make_parts(*, owner: str = OWNER) -> LedgerParts:
    source = make_source(owner=owner)
    testimony = make_testimony(
        owner=owner,
        channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        source_id=source.source_id,
    )
    item = make_item(owner=owner, source_id=source.source_id)
    contradiction = make_contradiction(
        owner=owner,
        first_ref=source.source_id,
        second_ref=item.item_id,
    )
    item = make_item(
        owner=owner,
        source_id=source.source_id,
        contradiction_refs=(contradiction.contradiction_id,),
    )
    evaluation = make_evaluation(owner=owner, item_id=item.item_id)
    custody = make_custody(owner=owner, source_id=source.source_id)
    return LedgerParts(
        source=source,
        testimony=testimony,
        item=item,
        contradiction=contradiction,
        evaluation=evaluation,
        custody=custody,
    )
