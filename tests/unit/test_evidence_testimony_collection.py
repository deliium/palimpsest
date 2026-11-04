"""V4-08 deterministic collection of sources, testimony, and interpretations."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from agents.cognition import (
    EvidenceAct,
    EvidenceContradictionKind,
    EvidenceError,
    EvidenceFrame,
    EvidenceIntegrityBelief,
    EvidenceInterpretationKind,
    EvidenceItemStatus,
    EvidenceObservedReference,
    EvidenceOwnerContext,
    EvidencePriorAgreement,
    EvidenceProvenanceChannel,
    EvidenceReferenceKind,
    EvidenceRememberedReference,
    EvidenceReputationInput,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    EvidenceTrustBasis,
    apply_evidence_update,
    empty_evidence_ledger,
    evidence_frame_relation,
    evidence_ledger_digest,
    evidence_source_kind_for_reference,
    record_evidence_utterance,
)
from tests.unit.evidence_testimony_helpers import OTHER_OWNER, OWNER
from world.actions import Talk
from world.communications import (
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

MODULE = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agents"
    / "cognition"
    / "evidence_testimony.py"
)


def _talk(*, speaker: str, frame: EvidenceFrame) -> Talk:
    relation = evidence_frame_relation(frame)
    return Talk(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="evidence",
            speaker_id=EntityId(speaker),
            communication_id="talk-1",
            relations=(relation,),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def test_observed_artifact_is_a_direct_observation_source() -> None:
    ledger = empty_evidence_ledger(OWNER)
    updated = apply_evidence_update(
        ledger,
        owner_id=OWNER,
        tick=3,
        observed=(
            EvidenceObservedReference(
                reference_kind=EvidenceReferenceKind.ARTIFACT,
                reference_id="artifact-1",
                correlation_id="evt-1",
                tick=3,
                integrity=EvidenceIntegrityBelief.INTACT,
                holder_token="agent-2",
                owner_id=OWNER,
            ),
        ),
    )

    assert len(updated.sources) == 1
    source = updated.sources[0]
    assert source.source_kind is EvidenceSourceKind.ARTIFACT
    assert source.provenance is EvidenceProvenanceChannel.DIRECT_OBSERVATION
    assert source.reference_id == "artifact-1"
    assert source.correlation_id == "evt-1"
    assert source.integrity is EvidenceIntegrityBelief.INTACT
    assert updated.observation_count == 1
    assert updated.custody_links[0].role.value == "holder"
    assert updated.custody_links[0].holder_token == "agent-2"


def test_reference_and_correlation_stay_distinct_for_observed_occurrence() -> None:
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=1,
        observed=(
            EvidenceObservedReference(
                reference_kind=EvidenceReferenceKind.OBSERVED_OCCURRENCE,
                reference_id="occurrence-1",
                correlation_id="opaque-event-token",
                tick=1,
            ),
        ),
    )
    source = ledger.sources[0]
    assert source.source_kind is EvidenceSourceKind.PHYSICAL_STATE
    assert source.reference_id == "occurrence-1"
    assert source.correlation_id == "opaque-event-token"
    assert source.reference_id != source.correlation_id


def test_remembered_event_keeps_memory_and_opaque_correlation() -> None:
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=4,
        remembered=(
            EvidenceRememberedReference(
                memory_id="mem-1",
                source_event_id="evt-9",
                tick=4,
                confidence=0.6,
                reconstruction_id="rec-1",
            ),
        ),
    )
    source = ledger.sources[0]
    assert source.source_kind is EvidenceSourceKind.REMEMBERED_EVENT
    assert source.reference_kind is EvidenceReferenceKind.RECONSTRUCTED_MEMORY
    assert source.reference_id == "mem-1"
    assert source.correlation_id == "evt-9"
    assert source.provenance is EvidenceProvenanceChannel.REMEMBERED
    assert source.confidence == 0.6


def test_prior_agreement_and_reputation_use_owner_local_references() -> None:
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=2,
        prior_agreements=(
            EvidencePriorAgreement(
                local_ref="cmt-1",
                parties=(OWNER, OTHER_OWNER),
                tick=2,
                confidence=0.7,
            ),
        ),
        reputation=(
            EvidenceReputationInput(
                target_token="agent-2",
                band="trusted",
                confidence=0.4,
                tick=2,
            ),
        ),
    )
    agreement, reputation = ledger.sources
    assert agreement.source_kind is EvidenceSourceKind.PRIOR_AGREEMENT
    assert agreement.reference_kind is EvidenceReferenceKind.COMMITMENT
    assert agreement.reference_id == "cmt-1"
    assert reputation.source_kind is EvidenceSourceKind.REPUTATION
    assert reputation.reference_kind is EvidenceReferenceKind.REPUTATION_RECORD
    assert reputation.reference_id == "agent-2"
    assert reputation.provenance is EvidenceProvenanceChannel.INFERRED


def test_reference_kind_mapping_is_closed() -> None:
    assert (
        evidence_source_kind_for_reference(EvidenceReferenceKind.ARTIFACT)
        is EvidenceSourceKind.ARTIFACT
    )
    assert (
        evidence_source_kind_for_reference(EvidenceReferenceKind.DURABLE_RECORD)
        is EvidenceSourceKind.WRITTEN_RECORD
    )
    assert (
        evidence_source_kind_for_reference(EvidenceReferenceKind.REPOSITORY_ENTRY)
        is EvidenceSourceKind.WRITTEN_RECORD
    )
    assert (
        evidence_source_kind_for_reference(EvidenceReferenceKind.UNKNOWN)
        is EvidenceSourceKind.UNKNOWN
    )


def test_foreign_owner_input_is_rejected() -> None:
    ledger = empty_evidence_ledger(OWNER)
    with pytest.raises(EvidenceError) as error:
        apply_evidence_update(
            ledger,
            owner_id=OWNER,
            tick=1,
            observed=(
                EvidenceObservedReference(
                    reference_kind=EvidenceReferenceKind.ARTIFACT,
                    reference_id="artifact-1",
                    tick=1,
                    owner_id=OTHER_OWNER,
                ),
            ),
        )
    assert error.value.code == "evidence_owner_mismatch"

    with pytest.raises(EvidenceError) as error:
        apply_evidence_update(ledger, owner_id=OTHER_OWNER, tick=1)
    assert error.value.code == "evidence_owner_mismatch"


def test_unknown_reference_adds_a_notice_and_invents_no_row() -> None:
    frame = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token="item-1",
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        reference_id="missing-source",
        confidence_band="mid",
    )
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER), owner_id=OWNER, tick=1, frames=(frame,)
    )
    assert ledger.items == ()
    assert "evidence_reference_unknown" in ledger.notices

    observed = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=1,
        observed=(
            EvidenceObservedReference(
                reference_kind=EvidenceReferenceKind.UNKNOWN,
                reference_id="",
                tick=1,
            ),
        ),
    )
    assert observed.sources[0].source_kind is EvidenceSourceKind.UNKNOWN
    assert observed.sources[0].provenance is EvidenceProvenanceChannel.DERIVED
    assert "evidence_reference_unknown" in observed.notices


def test_frame_flow_creates_testimony_items_and_retraction() -> None:
    testify = EvidenceFrame(
        act=EvidenceAct.TESTIFY,
        subject_token="item-1",
        witness_id=OTHER_OWNER,
        testimony_channel=EvidenceTestimonyChannel.DIRECT,
        confidence_band="high",
    )
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER), owner_id=OWNER, tick=2, frames=(testify,)
    )
    assert len(ledger.testimony) == 1
    statement = ledger.testimony[0]
    assert statement.channel is EvidenceTestimonyChannel.DIRECT
    assert statement.root_ref is None
    assert statement.independently_evidenced is True

    interpret = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token="item-1",
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        reference_id=statement.testimony_id,
        confidence_band="mid",
    )
    ledger = apply_evidence_update(ledger, owner_id=OWNER, tick=2, frames=(interpret,))
    assert len(ledger.items) == 1
    item = ledger.items[0]
    assert item.testimony_id == statement.testimony_id
    assert item.source_id is None

    retract = EvidenceFrame(
        act=EvidenceAct.RETRACT,
        subject_token="item-1",
        reference_id=item.item_id,
        confidence_band="low",
    )
    ledger = apply_evidence_update(ledger, owner_id=OWNER, tick=3, frames=(retract,))
    assert ledger.items[0].status is EvidenceItemStatus.RETRACTED
    assert ledger.items[0].reason_code == "owner_retracted"
    assert "evidence_item_retracted" in ledger.notices
    assert ledger.active_items == ()


def test_assert_cite_contradict_frames() -> None:
    assert_source = EvidenceFrame(
        act=EvidenceAct.ASSERT_SOURCE,
        subject_token="subject-1",
        source_kind=EvidenceSourceKind.ARTIFACT,
        reference_kind=EvidenceReferenceKind.ARTIFACT,
        reference_id="artifact-1",
        confidence_band="high",
    )
    cite = EvidenceFrame(
        act=EvidenceAct.CITE_RECORD,
        subject_token="subject-1",
        reference_kind=EvidenceReferenceKind.DURABLE_RECORD,
        reference_id="record-1",
        confidence_band="mid",
    )
    ledger = apply_evidence_update(
        empty_evidence_ledger(OWNER),
        owner_id=OWNER,
        tick=1,
        frames=(assert_source, cite),
    )
    assert {source.source_kind for source in ledger.sources} == {
        EvidenceSourceKind.ARTIFACT,
        EvidenceSourceKind.WRITTEN_RECORD,
    }

    item = EvidenceFrame(
        act=EvidenceAct.INTERPRET,
        subject_token="subject-1",
        interpretation=EvidenceInterpretationKind.SUPPORTS,
        reference_id="artifact-1",
        confidence_band="mid",
    )
    ledger = apply_evidence_update(ledger, owner_id=OWNER, tick=1, frames=(item,))
    contradict = EvidenceFrame(
        act=EvidenceAct.CONTRADICT,
        subject_token="subject-1",
        contradiction_kind=EvidenceContradictionKind.INTERPRETATION_CONFLICT,
        first_ref=ledger.sources[0].source_id,
        second_ref=ledger.items[0].item_id,
        confidence_band="low",
    )
    ledger = apply_evidence_update(ledger, owner_id=OWNER, tick=2, frames=(contradict,))
    assert len(ledger.contradictions) == 1
    assert ledger.contradictions[0].status.value == "unresolved"


def test_repeated_application_is_deterministic() -> None:
    inputs = dict(
        owner_id=OWNER,
        tick=5,
        observed=(
            EvidenceObservedReference(
                reference_kind=EvidenceReferenceKind.ARTIFACT,
                reference_id="artifact-1",
                tick=5,
            ),
        ),
        remembered=(
            EvidenceRememberedReference(memory_id="mem-1", tick=5, confidence=0.3),
        ),
    )
    first = apply_evidence_update(empty_evidence_ledger(OWNER), **inputs)  # type: ignore[arg-type]
    second = apply_evidence_update(empty_evidence_ledger(OWNER), **inputs)  # type: ignore[arg-type]
    assert evidence_ledger_digest(first) == evidence_ledger_digest(second)
    assert first == second


def test_record_utterance_requires_the_owner_as_speaker() -> None:
    frame = EvidenceFrame(
        act=EvidenceAct.ASSERT_SOURCE,
        subject_token="subject-1",
        source_kind=EvidenceSourceKind.ARTIFACT,
        reference_kind=EvidenceReferenceKind.ARTIFACT,
        reference_id="artifact-1",
        confidence_band="high",
    )
    ledger = empty_evidence_ledger(OWNER)
    foreign = record_evidence_utterance(
        ledger,
        _talk(speaker=OTHER_OWNER, frame=frame),
        owner_id=OWNER,
        tick=1,
    )
    assert foreign is ledger

    own = record_evidence_utterance(
        ledger,
        _talk(speaker=OWNER, frame=frame),
        owner_id=OWNER,
        tick=1,
    )
    assert own is not ledger
    assert len(own.sources) == 1

    assert record_evidence_utterance(ledger, object(), owner_id=OWNER, tick=1) is ledger


def test_update_signature_has_no_world_event_or_peer_types() -> None:
    signature = inspect.signature(apply_evidence_update)
    rendered = " ".join(
        str(parameter.annotation) for parameter in signature.parameters.values()
    )
    for forbidden in (
        "Observation",
        "WorldState",
        "WorldEvent",
        "EventStore",
        "AgentCommand",
        "DisputeLedger",
    ):
        assert forbidden not in rendered

    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "apply_evidence_update":
            argument_names = {argument.arg for argument in node.args.args}
            assert "observation" not in argument_names
            assert "world" not in argument_names
            assert "command" not in argument_names


def test_owner_context_is_a_closed_dto() -> None:
    context = EvidenceOwnerContext(
        relationship_trust=(("agent-2", 0.7),),
        reputation_bands=(("agent-2", "trusted"),),
        governing_rule_ids=("frule-1",),
        office_refs=("office-1",),
        institution_refs=("institution-1",),
    )
    assert context.relationship_trust[0][1] == 0.7
    assert EvidenceTrustBasis.DIRECT_EXPERIENCE.value == "direct_experience"
    assert replace(context, office_refs=()).office_refs == ()
