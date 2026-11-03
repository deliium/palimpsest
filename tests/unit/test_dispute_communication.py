"""V4-07 bounded ``dsp_v1`` dispute speech frames."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    DISPUTE_FRAME_SUBJECT,
    DISPUTE_PREDICATES,
    DisputeAct,
    DisputeClaimPolarity,
    DisputeClaimRole,
    DisputeError,
    DisputeFrame,
    DisputeKind,
    DisputeResolutionTerm,
    DisputeResolutionTermKind,
    DisputeSubjectKind,
    dispute_communicate_utterance,
    dispute_frame_party_matches,
    dispute_frame_relation,
    dispute_terms_digest,
    encode_dispute_frame,
    parse_dispute_frame,
    parse_dispute_frame_relation,
)
from world.actions import Talk, Tell
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

CASE_REF = "a" * 64
CLAIM_REF = "b" * 64
RESOLUTION_REF = "c" * 64
TERMS_DIGEST = "d" * 64


def _term() -> DisputeResolutionTerm:
    return DisputeResolutionTerm(
        term_kind=DisputeResolutionTermKind.TRANSFER_ITEM,
        party_id="agent-1",
        counterparty_id="agent-2",
        item_token="item-1",
        quantity=1,
    )


def _frames() -> tuple[DisputeFrame, ...]:
    terms = (_term(),)
    return (
        DisputeFrame(
            act=DisputeAct.CLAIM,
            case_ref=CASE_REF,
            role=DisputeClaimRole.CLAIM,
            kind=DisputeKind.OWNERSHIP_CLAIM,
            polarity=DisputeClaimPolarity.AFFIRM,
            party_ref="body-1",
            subject_kind=DisputeSubjectKind.ITEM,
            subject_token="item-1",
        ),
        DisputeFrame(
            act=DisputeAct.COUNTERCLAIM,
            case_ref=CASE_REF,
            claim_ref=CLAIM_REF,
            role=DisputeClaimRole.COUNTERCLAIM,
            kind=DisputeKind.OWNERSHIP_CLAIM,
            polarity=DisputeClaimPolarity.DENY,
            party_ref="body-1",
            subject_kind=DisputeSubjectKind.ITEM,
            subject_token="item-1",
        ),
        DisputeFrame(
            act=DisputeAct.TESTIFY,
            case_ref=CASE_REF,
            claim_ref=CLAIM_REF,
            party_ref="body-1",
            direct=True,
            root_ref="root-1",
        ),
        DisputeFrame(
            act=DisputeAct.CITE_EVIDENCE,
            case_ref=CASE_REF,
            claim_ref=CLAIM_REF,
            evidence_ref="observed_occurrence@event-1",
        ),
        DisputeFrame(
            act=DisputeAct.CITE_RULE,
            case_ref=CASE_REF,
            claim_ref=CLAIM_REF,
            rule_ref="frl-0123456789abcdef@2",
        ),
        DisputeFrame(
            act=DisputeAct.REFERENCE_MEDIATION,
            case_ref=CASE_REF,
            mediation_ref="mediation-1",
        ),
        DisputeFrame(
            act=DisputeAct.PROPOSE_RESOLUTION,
            case_ref=CASE_REF,
            resolution_ref=RESOLUTION_REF,
            terms_digest=dispute_terms_digest(terms),
            terms=terms,
        ),
        DisputeFrame(
            act=DisputeAct.ACCEPT_RESOLUTION,
            case_ref=CASE_REF,
            resolution_ref=RESOLUTION_REF,
            party_ref="body-1",
            terms_digest=TERMS_DIGEST,
        ),
        DisputeFrame(
            act=DisputeAct.REJECT_RESOLUTION,
            case_ref=CASE_REF,
            resolution_ref=RESOLUTION_REF,
            party_ref="body-1",
            terms_digest=TERMS_DIGEST,
        ),
        DisputeFrame(
            act=DisputeAct.WITHDRAW_CLAIM,
            case_ref=CASE_REF,
            claim_ref=CLAIM_REF,
            party_ref="body-1",
        ),
    )


def _talk(*, relations: tuple[CommunicationRelation, ...] = ()) -> Talk:
    return Talk(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-1"),
            communication_id="talk-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def test_each_act_round_trips_and_rejects_missing_fields() -> None:
    frames = _frames()
    assert {frame.act for frame in frames} == set(DisputeAct)
    for frame in frames:
        text = encode_dispute_frame(frame)
        assert text.startswith(f"{DISPUTE_FRAME_SUBJECT}:")
        assert len(text.split(":")) == 19
        assert parse_dispute_frame(text) == frame
        relation = dispute_frame_relation(frame)
        assert relation.subject == DISPUTE_FRAME_SUBJECT
        assert relation.predicate == DISPUTE_PREDICATES[frame.act]
        assert parse_dispute_frame_relation(relation) == frame

    for frame in frames:
        required = {
            DisputeAct.CLAIM: ("case_ref", "role", "kind", "polarity", "party_ref"),
            DisputeAct.COUNTERCLAIM: ("claim_ref", "party_ref"),
            DisputeAct.TESTIFY: ("claim_ref", "party_ref", "direct", "root_ref"),
            DisputeAct.CITE_EVIDENCE: ("evidence_ref",),
            DisputeAct.CITE_RULE: ("rule_ref",),
            DisputeAct.REFERENCE_MEDIATION: ("mediation_ref",),
            DisputeAct.PROPOSE_RESOLUTION: ("resolution_ref", "terms_digest"),
            DisputeAct.ACCEPT_RESOLUTION: ("resolution_ref", "terms_digest"),
            DisputeAct.REJECT_RESOLUTION: ("resolution_ref", "terms_digest"),
            DisputeAct.WITHDRAW_CLAIM: ("claim_ref", "party_ref"),
        }[frame.act]
        for field_name in required:
            with pytest.raises(DisputeError):
                replace(frame, **{field_name: None})  # type: ignore[arg-type]


def test_party_must_equal_verified_speaker() -> None:
    claim = _frames()[0]
    assert dispute_frame_party_matches(claim, "body-1") is True
    assert dispute_frame_party_matches(claim, "body-2") is False
    assert dispute_frame_party_matches(claim, None) is False

    forged = DisputeFrame(
        act=DisputeAct.ACCEPT_RESOLUTION,
        case_ref=CASE_REF,
        resolution_ref=RESOLUTION_REF,
        party_ref="body-2",
        terms_digest=TERMS_DIGEST,
    )
    assert dispute_frame_party_matches(forged, "body-1") is False


def test_direct_and_root_are_testimony_only() -> None:
    frames = {frame.act: frame for frame in _frames()}
    testify = frames[DisputeAct.TESTIFY]
    parsed = parse_dispute_frame(encode_dispute_frame(testify))
    assert parsed is not None
    assert parsed.direct is True

    with pytest.raises(DisputeError):
        replace(frames[DisputeAct.CLAIM], direct=True)
    with pytest.raises(DisputeError):
        replace(frames[DisputeAct.CLAIM], root_ref="root-1")
    with pytest.raises(DisputeError):
        replace(frames[DisputeAct.TESTIFY], direct=None)


def test_frame_rejects_free_text_and_control_characters() -> None:
    text = encode_dispute_frame(_frames()[0])
    assert parse_dispute_frame(text + " free text") is None
    assert parse_dispute_frame(text.replace(":", ":\n", 1)) is None
    assert parse_dispute_frame(text + "x" * 769) is None
    assert parse_dispute_frame("not-a-dispute-frame") is None
    assert (
        parse_dispute_frame_relation(
            CommunicationRelation(subject="fr_v1", predicate="fr_assert", object="x")
        )
        is None
    )


def test_decorator_preserves_command_type_and_other_relations() -> None:
    existing = CommunicationRelation(
        subject="greeting", predicate="hello", object="once"
    )
    talk = _talk(relations=(existing,))
    updated = dispute_communicate_utterance(talk, _frames()[0])
    assert type(updated) is Talk
    assert updated.recipient_id == talk.recipient_id
    assert updated.utterance.content.relations[0] == existing
    assert updated.utterance.content.relations[-1].subject == DISPUTE_FRAME_SUBJECT
    assert updated.utterance.content.text == "dispute"
    assert updated.utterance.declared.hop_count == 0
    assert (
        updated.utterance.declared.source_basis is CommunicationSourceBasis.UNREFERENCED
    )

    tell = Tell(
        recipient_id=EntityId("body-2"),
        utterance=talk.utterance,
    )
    decorated_tell = dispute_communicate_utterance(tell, _frames()[1])
    assert type(decorated_tell) is Tell


def test_decorator_returns_original_on_relation_limit() -> None:
    relations = tuple(
        CommunicationRelation(subject="concept", predicate=f"p{index}", object="value")
        for index in range(32)
    )
    talk = _talk(relations=relations)
    assert dispute_communicate_utterance(talk, _frames()[0]) is talk
    assert len(talk.utterance.content.relations) == 32

    decorated = _talk()
    twice = dispute_communicate_utterance(decorated, _frames()[0])
    assert dispute_communicate_utterance(twice, _frames()[0]) is twice


def test_no_new_command_or_event_is_created() -> None:
    from observer import SEMANTIC_EVENT_TYPES
    from world._rules import COMMAND_RULE_MATRIX

    assert len(COMMAND_RULE_MATRIX) == 43
    assert len(SEMANTIC_EVENT_TYPES) == 73
    assert not any("Dispute" in command.__name__ for command in COMMAND_RULE_MATRIX)
