"""V4-08 bounded ``ev_v1`` evidence speech frames."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    EVIDENCE_CONFIDENCE_BANDS,
    EVIDENCE_FRAME_FIELD_COUNT,
    EVIDENCE_FRAME_SUBJECT,
    EVIDENCE_PREDICATES,
    EvidenceAct,
    EvidenceContradictionKind,
    EvidenceCustodyRole,
    EvidenceError,
    EvidenceFrame,
    EvidenceInterpretationKind,
    EvidenceReferenceKind,
    EvidenceSourceKind,
    EvidenceTestimonyChannel,
    encode_evidence_frame,
    evidence_communicate_utterance,
    evidence_frame_party_matches,
    evidence_frame_relation,
    parse_evidence_frame,
    parse_evidence_frame_relation,
)
from world.actions import Talk, Tell
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

SPEAKER = "agent-1"
_FRAME_KEYS_AFTER_ACT = (
    "subject_token",
    "source_kind",
    "reference_kind",
    "reference_id",
    "witness_id",
    "testimony_channel",
    "root_ref",
    "confidence_band",
    "interpretation",
    "contradiction_kind",
    "first_ref",
    "second_ref",
    "custody_role",
    "counterparty_token",
    "location_token",
    "custodian_token",
)


def _frames() -> tuple[EvidenceFrame, ...]:
    return (
        EvidenceFrame(
            act=EvidenceAct.ASSERT_SOURCE,
            subject_token="item-1",
            source_kind=EvidenceSourceKind.ARTIFACT,
            reference_kind=EvidenceReferenceKind.ARTIFACT,
            reference_id="artifact-1",
            confidence_band="high",
        ),
        EvidenceFrame(
            act=EvidenceAct.CITE_RECORD,
            subject_token="item-1",
            reference_kind=EvidenceReferenceKind.DURABLE_RECORD,
            reference_id="record-1",
            confidence_band="mid",
        ),
        EvidenceFrame(
            act=EvidenceAct.TESTIFY,
            subject_token="item-1",
            witness_id=SPEAKER,
            testimony_channel=EvidenceTestimonyChannel.DIRECT,
            confidence_band="high",
        ),
        EvidenceFrame(
            act=EvidenceAct.TESTIFY,
            subject_token="item-1",
            witness_id=SPEAKER,
            testimony_channel=EvidenceTestimonyChannel.COMMUNICATED,
            root_ref="root-1",
            confidence_band="low",
        ),
        EvidenceFrame(
            act=EvidenceAct.CLAIM_CUSTODY,
            subject_token="item-1",
            custody_role=EvidenceCustodyRole.HOLDER,
            counterparty_token="agent-2",
            reference_id="artifact-1",
            confidence_band="mid",
        ),
        EvidenceFrame(
            act=EvidenceAct.INTERPRET,
            subject_token="item-1",
            interpretation=EvidenceInterpretationKind.SUPPORTS,
            reference_id="artifact-1",
            confidence_band="high",
        ),
        EvidenceFrame(
            act=EvidenceAct.CONTRADICT,
            subject_token="item-1",
            contradiction_kind=EvidenceContradictionKind.INTERPRETATION_CONFLICT,
            first_ref="artifact-1",
            second_ref="record-1",
            confidence_band="low",
        ),
        EvidenceFrame(
            act=EvidenceAct.RETRACT,
            subject_token="item-1",
            reference_id="item-1",
            confidence_band="mid",
        ),
    )


def _talk(*, relations: tuple[CommunicationRelation, ...] = ()) -> Talk:
    return Talk(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId(SPEAKER),
            communication_id="talk-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _tamper(text: str, index: int, value: str) -> str:
    parts = text.split(":")
    parts[index] = value
    return ":".join(parts)


def test_every_act_round_trips_with_seventeen_fields() -> None:
    frames = _frames()
    assert {frame.act for frame in frames} == set(EvidenceAct)
    for frame in frames:
        text = encode_evidence_frame(frame)
        assert text.startswith(f"{EVIDENCE_FRAME_SUBJECT}:")
        assert len(text.split(":")) == EVIDENCE_FRAME_FIELD_COUNT + 1
        assert parse_evidence_frame(text) == frame

        relation = evidence_frame_relation(frame)
        assert relation.subject == EVIDENCE_FRAME_SUBJECT
        assert relation.predicate == EVIDENCE_PREDICATES[frame.act]
        assert parse_evidence_frame_relation(relation) == frame
        assert (
            parse_evidence_frame_relation(
                CommunicationRelation(
                    subject=EVIDENCE_FRAME_SUBJECT,
                    predicate="ev_unknown",
                    object=relation.object,
                )
            )
            is None
        )

    assert EVIDENCE_CONFIDENCE_BANDS == {"low": 0.25, "mid": 0.55, "high": 0.85}


def test_missing_required_fields_and_extra_fields_are_rejected() -> None:
    source = _frames()[0]
    with pytest.raises(EvidenceError) as error:
        replace(source, subject_token=None)
    assert error.value.code == "evidence_untrusted_frame"

    for missing in ("source_kind", "reference_kind", "reference_id"):
        with pytest.raises(EvidenceError):
            replace(source, **{missing: None})

    text = encode_evidence_frame(source)
    reference_index = 2 + _FRAME_KEYS_AFTER_ACT.index("reference_id")
    missing_text = _tamper(text, reference_index, "none")
    assert parse_evidence_frame(missing_text) is None

    extra_text = text + ":truth"
    assert parse_evidence_frame(extra_text) is None


def test_direct_and_communicated_testimony_roots_are_exact() -> None:
    direct = EvidenceFrame(
        act=EvidenceAct.TESTIFY,
        subject_token="item-1",
        witness_id=SPEAKER,
        testimony_channel=EvidenceTestimonyChannel.DIRECT,
        confidence_band="high",
    )
    communicated = EvidenceFrame(
        act=EvidenceAct.TESTIFY,
        subject_token="item-1",
        witness_id=SPEAKER,
        testimony_channel=EvidenceTestimonyChannel.COMMUNICATED,
        root_ref="root-1",
        confidence_band="high",
    )

    with pytest.raises(EvidenceError):
        replace(direct, root_ref="root-1")
    with pytest.raises(EvidenceError):
        replace(communicated, root_ref=None)
    with pytest.raises(EvidenceError):
        replace(direct, testimony_channel=None)
    with pytest.raises(EvidenceError):
        replace(direct, witness_id=None)


def test_cite_record_forces_written_record_and_custody_role_tokens() -> None:
    record = _frames()[1]
    assert record.source_kind is EvidenceSourceKind.WRITTEN_RECORD

    with pytest.raises(EvidenceError):
        replace(record, source_kind=EvidenceSourceKind.ARTIFACT)

    custody = _frames()[4]
    with pytest.raises(EvidenceError):
        replace(custody, counterparty_token=None)
    with pytest.raises(EvidenceError):
        replace(custody, location_token="location-1")
    observer = replace(
        custody,
        custody_role=EvidenceCustodyRole.OBSERVER,
        counterparty_token=None,
    )
    assert observer.custody_role is EvidenceCustodyRole.OBSERVER
    with pytest.raises(EvidenceError):
        replace(observer, location_token="location-1")
    assert (
        replace(
            custody,
            custody_role=EvidenceCustodyRole.REPOSITORY_CUSTODIAN,
            counterparty_token=None,
            custodian_token="archive-1",
        ).custodian_token
        == "archive-1"
    )


def test_frame_party_matching_rejects_a_foreign_witness() -> None:
    testify = _frames()[2]
    assert evidence_frame_party_matches(testify, SPEAKER) is True
    assert evidence_frame_party_matches(testify, "agent-2") is False
    assert evidence_frame_party_matches(testify, EntityId(SPEAKER)) is True
    assert evidence_frame_party_matches(_frames()[0], SPEAKER) is True
    assert evidence_frame_party_matches(object(), SPEAKER) is False

    command = _talk()
    foreign = replace(testify, witness_id="agent-2")
    assert evidence_communicate_utterance(command, foreign) is command
    attached = evidence_communicate_utterance(command, testify)
    assert attached is not command
    assert attached.recipient_id == command.recipient_id


def test_oversized_and_malformed_frames_return_none() -> None:
    assert parse_evidence_frame("x" * 769) is None
    assert parse_evidence_frame(f"{EVIDENCE_FRAME_SUBJECT}:ev_source:{{}}") is None
    assert parse_evidence_frame("ev_v2:ev_source:{}") is None
    assert parse_evidence_frame(f"{EVIDENCE_FRAME_SUBJECT}:ev_source:{{") is None
    assert parse_evidence_frame("") is None
    assert parse_evidence_frame_relation(object()) is None


def test_command_at_relation_limit_is_returned_unchanged() -> None:
    relations = tuple(
        CommunicationRelation(
            subject="other",
            predicate="rel",
            object=f"value-{index}",
        )
        for index in range(32)
    )
    command = _talk(relations=relations)
    assert evidence_communicate_utterance(command, _frames()[0]) is command

    attached = evidence_communicate_utterance(_talk(), _frames()[0])
    contents = attached.utterance.content.relations
    assert len(contents) == 1
    assert contents[0].subject == EVIDENCE_FRAME_SUBJECT

    twice = evidence_communicate_utterance(attached, _frames()[1])
    assert twice is attached

    tell = Tell(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId(SPEAKER),
            communication_id="tell-1",
            relations=(),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )
    assert evidence_communicate_utterance(tell, _frames()[0]) is not tell
    sentinel = object()
    assert evidence_communicate_utterance(sentinel, _frames()[0]) is sentinel
