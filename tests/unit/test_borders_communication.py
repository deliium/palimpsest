# mypy: ignore-errors
"""Bounded bdr_v1 frame encoding, grouping, and attachment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.borders import (
    AccessExpectationMode,
    AgreementAct,
    AgreementProvision,
    CounterpartyKind,
    domain_claim_token_id,
)
from agents.cognition.borders_communication import (
    BORDER_FRAME_MAX_CHARS,
    BORDER_FRAME_MAX_RELATIONS,
    BORDER_FRAME_SUBJECT,
    BorderFrame,
    BorderFrameError,
    attach_border_relation,
    border_claim_relation,
    border_frame_deliveries,
    border_frames_from_observation,
    encode_border_claim,
    parse_border_claim,
    parse_border_claim_relation,
)
from agents.models import AgentId
from world.actions import Ask, Talk, Tell
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
PEER = AgentId("agent-2")
OTHER = AgentId("agent-3")
OWNER_ENTITY = EntityId("body-1")
PEER_ENTITY = EntityId("body-2")

IDENTITY = SimpleNamespace(
    owner_id=OWNER,
    owner_entity_id=OWNER_ENTITY,
    counterparts=(SimpleNamespace(entity_id=PEER_ENTITY, agent_id=PEER),),
)


def _domain_id(tokens: tuple[str, ...], owner: AgentId = PEER) -> str:
    return domain_claim_token_id(owner, tokens)


def _frame(
    act: AgreementAct,
    *,
    locations: tuple[str, ...] = ("loc-a", "loc-b"),
    party_kind: CounterpartyKind = CounterpartyKind.AGENT,
    party_ref: str | None = "agent-1",
    expiry: int | None = None,
    access_mode: AccessExpectationMode | None = None,
    provision: AgreementProvision | None = None,
    owner: AgentId = PEER,
) -> BorderFrame:
    return BorderFrame(
        act=act,
        domain_id=_domain_id(locations, owner),
        party_kind=party_kind,
        party_ref=party_ref,
        locations=locations,
        expiry_tick=expiry,
        access_mode=access_mode,
        provision=provision,
    )


def _utterance(frame: BorderFrame, *, speaker: EntityId = PEER_ENTITY):
    return origin_utterance(
        text=BORDER_FRAME_SUBJECT,
        speaker_id=speaker,
        relations=border_claim_relation(frame),
    )


def _observation(*frames: BorderFrame):
    communications = tuple(
        SimpleNamespace(
            speaker_id=PEER_ENTITY,
            listener_id=OWNER_ENTITY,
            utterance=_utterance(frame),
        )
        for frame in frames
    )
    return SimpleNamespace(communications=communications)


def test_constants_and_field_order_are_frozen() -> None:
    assert BORDER_FRAME_SUBJECT == "bdr_v1"
    assert BORDER_FRAME_MAX_CHARS == 256
    assert BORDER_FRAME_MAX_RELATIONS == 8
    text = encode_border_claim(_frame(AgreementAct.CLAIM_DOMAIN))
    first = text.split("\n")[0]
    assert first.split(":")[0] == "bdr_v1"
    assert first.split(":")[1] == "claim_domain"


def test_encode_parse_round_trip_for_all_acts() -> None:
    for act in AgreementAct:
        frame = _frame(
            act,
            expiry=5,
            access_mode=AccessExpectationMode.OPEN,
            provision=AgreementProvision.PASSAGE,
        )
        parsed = parse_border_claim(encode_border_claim(frame))
        assert parsed == frame


def test_every_act_requires_one_to_eight_locations() -> None:
    with pytest.raises(ValueError):
        _frame(AgreementAct.CLAIM_DOMAIN, locations=())
    with pytest.raises(ValueError):
        _frame(
            AgreementAct.CLAIM_DOMAIN,
            locations=tuple(f"loc-{index}" for index in range(9)),
        )


def test_domain_id_must_match_the_speaker_location_set() -> None:
    valid = _frame(AgreementAct.CLAIM_DOMAIN)
    assert border_frames_from_observation(_observation(valid), identity=IDENTITY) == (
        valid,
    )
    wrong = BorderFrame(
        act=AgreementAct.CLAIM_DOMAIN,
        domain_id=_domain_id(("loc-a", "loc-b"), OTHER),
        party_kind=CounterpartyKind.AGENT,
        party_ref="agent-1",
        locations=("loc-a", "loc-b"),
    )
    assert border_frames_from_observation(_observation(wrong), identity=IDENTITY) == ()


def test_eight_locations_fit_and_nine_are_rejected() -> None:
    eight = _frame(
        AgreementAct.CLAIM_DOMAIN,
        locations=tuple(f"l{index}" for index in range(8)),
    )
    text = encode_border_claim(eight)
    assert parse_border_claim(text) == eight
    with pytest.raises(ValueError):
        _frame(
            AgreementAct.CLAIM_DOMAIN,
            locations=tuple(f"l{index}" for index in range(9)),
        )


def test_oversize_relation_is_dropped() -> None:
    long_locations = tuple("l" * 122 + f"{index:06d}" for index in range(8))
    frame = _frame(
        AgreementAct.CLAIM_DOMAIN,
        locations=long_locations,
        party_ref="p" * 128,
    )
    with pytest.raises(BorderFrameError):
        encode_border_claim(frame)
    fake_relation = SimpleNamespace(
        subject=BORDER_FRAME_SUBJECT,
        predicate="relation",
        object="x" * (BORDER_FRAME_MAX_CHARS + 1),
    )
    communication = SimpleNamespace(
        speaker_id=PEER_ENTITY,
        listener_id=OWNER_ENTITY,
        utterance=SimpleNamespace(content=SimpleNamespace(relations=(fake_relation,))),
    )
    frames = border_frames_from_observation(
        SimpleNamespace(communications=(communication,)), identity=IDENTITY
    )
    assert frames == ()


def _relations_with(lines: tuple[str, ...]) -> tuple[CommunicationRelation, ...]:
    return tuple(
        CommunicationRelation(
            subject=BORDER_FRAME_SUBJECT, predicate="relation", object=line
        )
        for line in lines
    )


def test_non_contiguous_missing_and_duplicate_indices_are_dropped() -> None:
    frame = _frame(AgreementAct.CLAIM_DOMAIN)
    lines = encode_border_claim(frame).split("\n")
    assert len(lines) == 2
    missing = (lines[0],)
    duplicate = (lines[0], lines[0])
    for lines_case in (missing, duplicate):
        communication = SimpleNamespace(
            speaker_id=PEER_ENTITY,
            listener_id=OWNER_ENTITY,
            utterance=origin_utterance(
                text=BORDER_FRAME_SUBJECT,
                speaker_id=PEER_ENTITY,
                relations=_relations_with(lines_case),
            ),
        )
        assert (
            border_frames_from_observation(
                SimpleNamespace(communications=(communication,)), identity=IDENTITY
            )
            == ()
        )
    parsed = parse_border_claim_relation(_relations_with(lines)[0])
    assert parsed == lines[0]


def test_speaker_cannot_accept_for_another_party() -> None:
    frame = _frame(
        AgreementAct.ACCEPT,
        party_kind=CounterpartyKind.AGENT,
        party_ref=PEER_ENTITY.value,
    )
    assert border_frames_from_observation(_observation(frame), identity=IDENTITY) == ()


def test_unknown_party_and_access_matrix() -> None:
    unknown = _frame(
        AgreementAct.EXPECT_ACCESS,
        party_kind=CounterpartyKind.UNKNOWN,
        party_ref=None,
        access_mode=AccessExpectationMode.UNKNOWN,
    )
    assert border_frames_from_observation(_observation(unknown), identity=IDENTITY) == (
        unknown,
    )
    with pytest.raises(BorderFrameError):
        _frame(
            AgreementAct.EXPECT_ACCESS,
            party_kind=CounterpartyKind.UNKNOWN,
            party_ref="agent-1",
        )
    with pytest.raises(BorderFrameError):
        _frame(
            AgreementAct.EXPECT_ACCESS,
            party_kind=CounterpartyKind.AGENT,
            party_ref=None,
        )


def test_attaching_preserves_command_type_recipient_and_relations() -> None:
    base = origin_utterance(
        text="hello",
        speaker_id=OWNER_ENTITY,
        relations=(CommunicationRelation(subject="s", predicate="p", object="o"),),
    )
    for command_type in (Talk, Ask, Tell):
        command = command_type(recipient_id=PEER_ENTITY, utterance=base)
        attached = attach_border_relation(command, _frame(AgreementAct.CLAIM_DOMAIN))
        assert type(attached) is command_type
        assert attached.recipient_id == PEER_ENTITY
        assert attached.utterance.content.relations[0].subject == "s"
        assert (
            sum(
                1
                for relation in attached.utterance.content.relations
                if relation.subject == BORDER_FRAME_SUBJECT
            )
            == 2
        )
        with pytest.raises(BorderFrameError):
            attach_border_relation(attached, _frame(AgreementAct.CLAIM_DOMAIN))


def test_no_new_wire_event_or_command_is_created() -> None:
    command = Talk(
        recipient_id=PEER_ENTITY,
        utterance=origin_utterance(text="x", speaker_id=OWNER_ENTITY),
    )
    attached = attach_border_relation(command, _frame(AgreementAct.CLAIM_DOMAIN))
    assert type(attached) is Talk
    assert attached.kind == "talk"
    with pytest.raises(TypeError):
        attach_border_relation(object(), _frame(AgreementAct.CLAIM_DOMAIN))


def test_deliveries_include_verified_speaker_token() -> None:
    frame = _frame(AgreementAct.CLAIM_DOMAIN)
    deliveries = border_frame_deliveries(_observation(frame), identity=IDENTITY)
    assert deliveries == ((PEER_ENTITY.value, frame),)
