"""V4-07 owner-scoped collection of claims, testimony, and evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition import (
    DisputeAct,
    DisputeClaimKind,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeEvidenceChannel,
    DisputeEvidenceReferenceKind,
    DisputeFrame,
    DisputeKind,
    DisputeLedger,
    DisputeMediationLinkStatus,
    DisputeProvenance,
    DisputeResolutionTermKind,
    DisputeStatus,
    DisputeSubjectKind,
    apply_dispute_update,
    dispute_case_ref,
    dispute_frame_relation,
    dispute_ledger_digest,
    empty_dispute_ledger,
    parse_dispute_frame_relation,
    record_dispute_utterance,
)
from agents.cognition.models import (
    CounterpartBinding,
    OwnerSafeSocialIdentity,
)
from agents.models import AgentId
from memory.models import MemoryId
from world.actions import Talk
from world.communications import (
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, EventId, WorldId, WorldRevision
from world.observations import (
    Observation,
    ObservationAudienceRole,
    ObservationProvenance,
    ObservationSourceKind,
    ObservedCommunication,
    ObservedOccurrence,
)


def _frame(
    *,
    subject_token: str = "item-1",
    polarity: DisputeClaimPolarity = DisputeClaimPolarity.AFFIRM,
    party_ref: str = "body-1",
    act: DisputeAct = DisputeAct.CLAIM,
    claim_ref: str | None = None,
) -> DisputeFrame:
    return DisputeFrame(
        act=act,
        case_ref=dispute_case_ref("item-1", ("agent-1", "agent-2")),
        claim_ref=claim_ref,
        role=(
            DisputeClaimRole.CLAIM
            if act is DisputeAct.CLAIM
            else DisputeClaimRole.COUNTERCLAIM
        ),
        kind=DisputeKind.OWNERSHIP_CLAIM,
        polarity=polarity,
        party_ref=party_ref,
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token=subject_token,
    )


def _identity(
    owner: str, owner_entity: str, other: str, other_entity: str
) -> OwnerSafeSocialIdentity:
    return OwnerSafeSocialIdentity(
        owner_id=AgentId(owner),
        owner_entity_id=EntityId(owner_entity),
        counterparts=(
            CounterpartBinding(
                agent_id=AgentId(other), entity_id=EntityId(other_entity)
            ),
        ),
    )


def _communication(
    frame: DisputeFrame,
    *,
    speaker: str = "body-1",
    listener: str = "body-2",
    tick: int = 1,
    event: str = "event-1",
) -> ObservedCommunication:
    relation = dispute_frame_relation(frame)
    return ObservedCommunication(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.COMMUNICATION,
            source_tick=tick,
            source_event_id=EventId(event),
        ),
        speaker_id=EntityId(speaker),
        listener_id=EntityId(listener),
        utterance=origin_utterance(
            text="statement",
            speaker_id=EntityId(speaker),
            communication_id=f"comm-{event}",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
        action_kind="tell",
    )


def _observation(
    *,
    tick: int = 2,
    observer: str = "body-2",
    communications: tuple[ObservedCommunication, ...] = (),
    occurrences: tuple[ObservedOccurrence, ...] = (),
) -> Observation:
    return Observation(
        world_id=WorldId("world-1"),
        observer_id=EntityId(observer),
        revision=WorldRevision(tick),
        tick=tick,
        communications=communications,
        occurrences=occurrences,
    )


def _occurrence() -> ObservedOccurrence:
    return ObservedOccurrence(
        provenance=ObservationProvenance(
            source_kind=ObservationSourceKind.OCCURRENCE,
            source_tick=1,
            source_event_id=EventId("occurrence-1"),
        ),
        kind="give",
        audience_role=ObservationAudienceRole.WITNESS,
        actor_id=EntityId("body-1"),
        other_entity_id=EntityId("body-2"),
    )


def _talk(
    frame: DisputeFrame, *, speaker: str = "body-1", recipient: str = "body-2"
) -> Talk:
    relation = dispute_frame_relation(frame)
    return Talk(
        recipient_id=EntityId(recipient),
        utterance=origin_utterance(
            text="dispute",
            speaker_id=EntityId(speaker),
            communication_id="talk-1",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def test_observation_alone_does_not_create_a_claim() -> None:
    ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(occurrences=(_occurrence(),)),
        None,
        identity=_identity("agent-2", "body-2", "agent-1", "body-1"),
    )
    assert ledger.cases == ()
    assert ledger.claims == ()
    assert ledger.enabled is True


def test_own_claim_creates_case_and_claim() -> None:
    ledger = empty_dispute_ledger("agent-1")
    identity = _identity("agent-1", "body-1", "agent-2", "body-2")
    updated = record_dispute_utterance(
        ledger,
        owner_id="agent-1",
        tick=1,
        command=_talk(_frame(party_ref="body-1")),
        identity=identity,
    )
    assert len(updated.cases) == 1
    assert len(updated.claims) == 1
    claim = updated.claims[0]
    assert claim.claimant_id == "agent-1"
    assert claim.respondent_id == "agent-2"
    assert updated.cases[0].party_ids == ("agent-1", "agent-2")
    assert updated.cases[0].kind is DisputeKind.OWNERSHIP_CLAIM


def test_counterclaim_is_attributed_to_the_speaker() -> None:
    identity = _identity("agent-2", "body-2", "agent-1", "body-1")
    ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(_frame()),)),
        None,
        identity=identity,
    )
    assert len(ledger.claims) == 1
    original = ledger.claims[0]
    assert original.claimant_id == "agent-1"

    counter = DisputeFrame(
        act=DisputeAct.COUNTERCLAIM,
        case_ref=original.case_ref,
        claim_ref=original.claim_ref,
        role=DisputeClaimRole.COUNTERCLAIM,
        kind=DisputeKind.OWNERSHIP_CLAIM,
        polarity=DisputeClaimPolarity.DENY,
        party_ref="body-2",
        subject_kind=DisputeSubjectKind.ITEM,
        subject_token="item-1",
    )
    updated = record_dispute_utterance(
        ledger,
        owner_id="agent-2",
        tick=3,
        command=_talk(counter, speaker="body-2", recipient="body-1"),
        identity=identity,
    )
    assert len(updated.counterclaims) == 1
    assert updated.counterclaims[0].claimant_id == "agent-2"
    assert updated.counterclaims[0].counters_claim_ref == original.claim_ref
    assert updated.cases[0].status is DisputeStatus.CONTESTED


def test_two_owners_with_different_memories_retain_both_claims() -> None:
    left = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(_frame()),)),
        None,
        identity=_identity("agent-2", "body-2", "agent-1", "body-1"),
    )
    right = apply_dispute_update(
        "agent-1",
        2,
        _observation(
            observer="body-1",
            communications=(
                _communication(
                    _frame(party_ref="body-2"),
                    speaker="body-2",
                    listener="body-1",
                ),
            ),
        ),
        None,
        identity=_identity("agent-1", "body-1", "agent-2", "body-2"),
    )
    assert left.claims[0].claimant_id == "agent-1"
    assert right.claims[0].claimant_id == "agent-2"
    assert left.claims[0].owner_id != right.claims[0].owner_id
    assert len(left.claims) == 1
    assert len(right.claims) == 1


def _commitments(
    *,
    kind: str,
    status: str = "violated",
    memory_ids: tuple[str, ...] = (),
) -> SimpleNamespace:
    return SimpleNamespace(
        interpretations=(
            SimpleNamespace(
                local_id=1,
                parties=("agent-1", "agent-2"),
                debtor_id="agent-1",
                creditor_id="agent-2",
                kind=kind,
                status=status,
                confidence=0.6,
                item_kind="grain",
                memory_trace_ids=memory_ids,
            ),
        )
    )


def test_commitment_dispute_creates_contested_debt_or_broken_promise() -> None:
    debt = apply_dispute_update(
        "agent-1",
        2,
        _observation(),
        None,
        structured_commitments=_commitments(kind="debt"),
    )
    assert debt.cases[0].kind is DisputeKind.CONTESTED_DEBT
    assert debt.claims[0].claim_kind is DisputeClaimKind.DEBT_OWED
    assert debt.claims[0].claimant_id == "agent-1"
    assert debt.claims[0].respondent_id == "agent-2"

    promise = apply_dispute_update(
        "agent-1",
        2,
        _observation(),
        None,
        structured_commitments=_commitments(kind="promise", status="disputed"),
    )
    assert promise.cases[0].kind is DisputeKind.BROKEN_PROMISE
    assert promise.claims[0].claim_kind is DisputeClaimKind.PROMISE_BROKEN


def test_mediation_case_creates_case_without_binding_outcome() -> None:
    mediation = SimpleNamespace(
        cases=(
            SimpleNamespace(
                party_ids=(AgentId("agent-1"), AgentId("agent-2")),
                subject_token="item-1",
            ),
        )
    )
    ledger = apply_dispute_update(
        "agent-1",
        2,
        _observation(),
        None,
        mediation=mediation,
    )
    assert len(ledger.cases) == 1
    assert ledger.cases[0].kind is DisputeKind.OTHER
    assert ledger.cases[0].status is DisputeStatus.EVIDENCE_GATHERING
    assert ledger.claims == ()
    assert ledger.resolutions == ()
    assert ledger.mediation_references == ()


def test_evidence_references_are_typed_and_opaque() -> None:
    ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(_frame(), event="event-42"),)),
        None,
        identity=_identity("agent-2", "body-2", "agent-1", "body-1"),
    )
    assert len(ledger.evidence) == 1
    evidence = ledger.evidence[0]
    assert (
        evidence.reference_kind is DisputeEvidenceReferenceKind.OBSERVED_COMMUNICATION
    )
    assert evidence.reference_id == "event-42"
    assert evidence.channel is DisputeEvidenceChannel.COMMUNICATED
    assert evidence.independently_evidenced is False
    assert not hasattr(evidence, "event")
    assert not hasattr(evidence, "state")


def test_missing_memory_context_creates_no_remembered_evidence() -> None:
    without = apply_dispute_update(
        "agent-1",
        2,
        _observation(),
        None,
        structured_commitments=_commitments(kind="debt", memory_ids=("mem-1",)),
    )
    assert not any(
        row.reference_kind is DisputeEvidenceReferenceKind.MEMORY_TRACE
        for row in without.evidence
    )

    context = SimpleNamespace(
        owner_id=AgentId("agent-1"),
        memory_ids=(MemoryId("mem-1"),),
        reconstructions=(),
    )
    with_memory = apply_dispute_update(
        "agent-1",
        2,
        _observation(),
        None,
        structured_commitments=_commitments(kind="debt", memory_ids=("mem-1",)),
        retrieved_memory_context=context,
    )
    assert any(
        row.reference_kind is DisputeEvidenceReferenceKind.MEMORY_TRACE
        for row in with_memory.evidence
    )


def test_prior_claims_are_not_deleted_by_missing_later_evidence() -> None:
    first = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(_frame()),)),
        None,
        identity=_identity("agent-2", "body-2", "agent-1", "body-1"),
    )
    second = apply_dispute_update(
        "agent-2",
        3,
        _observation(tick=3),
        first,
        identity=_identity("agent-2", "body-2", "agent-1", "body-1"),
    )
    assert len(second.claims) == 1
    assert second.claims[0].claim_ref == first.claims[0].claim_ref
    assert second.claims[0].active is True


def test_shuffled_delivery_produces_identical_ledger() -> None:
    first = _communication(_frame(), event="event-1")
    second = _communication(
        _frame(
            subject_token="item-2",
            polarity=DisputeClaimPolarity.DENY,
        ),
        event="event-2",
    )
    identity = _identity("agent-2", "body-2", "agent-1", "body-1")
    forward = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(first, second)),
        None,
        identity=identity,
    )
    reversed_ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(second, first)),
        None,
        identity=identity,
    )
    assert dispute_ledger_digest(forward) == dispute_ledger_digest(reversed_ledger)
    assert forward == reversed_ledger


def test_testimony_is_direct_or_communicated() -> None:
    identity = _identity("agent-2", "body-2", "agent-1", "body-1")
    claim_frame = _frame()
    ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(claim_frame),)),
        None,
        identity=identity,
    )
    original = ledger.claims[0]
    testify = DisputeFrame(
        act=DisputeAct.TESTIFY,
        case_ref=original.case_ref,
        claim_ref=original.claim_ref,
        party_ref="body-1",
        direct=False,
        root_ref="root-1",
    )
    updated = apply_dispute_update(
        "agent-2",
        3,
        _observation(
            tick=3,
            communications=(_communication(testify, tick=2, event="event-2"),),
        ),
        ledger,
        identity=identity,
    )
    assert len(updated.testimony) == 1
    assert updated.testimony[0].independently_evidenced is False
    assert updated.testimony[0].channel.value == "communicated"


def test_mediation_reference_frame_is_only_a_link() -> None:
    identity = _identity("agent-2", "body-2", "agent-1", "body-1")
    claim_frame = _frame()
    ledger = apply_dispute_update(
        "agent-2",
        2,
        _observation(communications=(_communication(claim_frame),)),
        None,
        identity=identity,
    )
    original = ledger.claims[0]
    reference = DisputeFrame(
        act=DisputeAct.REFERENCE_MEDIATION,
        case_ref=original.case_ref,
        mediation_ref="mediation-1",
    )
    updated = apply_dispute_update(
        "agent-2",
        3,
        _observation(
            tick=3,
            communications=(_communication(reference, tick=2, event="event-2"),),
        ),
        ledger,
        identity=identity,
    )
    assert len(updated.mediation_references) == 1
    link = updated.mediation_references[0]
    assert link.link_status is DisputeMediationLinkStatus.ORPHANED
    assert link.provenance is DisputeProvenance.COMMUNICATED
    assert updated.resolutions == ()


def test_terms_kind_is_available_for_resolution_frames() -> None:
    assert DisputeResolutionTermKind.TRANSFER_ITEM.value == "transfer_item"


def test_parse_helper_reads_relation_atoms() -> None:
    from agents.cognition import dispute_frame_relation

    frame = _frame()
    assert parse_dispute_frame_relation(dispute_frame_relation(frame)) == frame


def test_ledger_type_is_enforced() -> None:
    with pytest.raises(TypeError):
        record_dispute_utterance(
            object(),  # type: ignore[arg-type]
            owner_id="agent-1",
            tick=1,
            command=object(),
        )


def test_empty_ledger_stays_empty_for_foreign_owner_prior() -> None:
    from agents.cognition import DisputeError

    with pytest.raises(DisputeError):
        apply_dispute_update(
            "agent-2",
            2,
            _observation(),
            DisputeLedger(owner_id="agent-1"),
        )
