# mypy: ignore-errors
"""V4-11 ``trt_v1`` chunked treaty speech claims."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from agents.cognition import (
    DIPLOMACY_FRAME_FIELD_COUNT,
    DIPLOMACY_FRAME_MAX_CHARS,
    DIPLOMACY_FRAME_SUBJECT,
    TREATY_CHUNK_MAX_CHARS,
    TREATY_FRAME_FIELD_COUNT,
    TREATY_FRAME_MAX_CHARS,
    TREATY_FRAME_SUBJECT,
    TREATY_MAX_CHUNKS,
    DiplomacyError,
    DiplomaticPartyKind,
    DiplomaticProvenance,
    TreatyAct,
    TreatyChangeKind,
    TreatyFrame,
    TreatyProvisionKind,
    TreatyRecollectionBasis,
    TreatyRecollectionStance,
    TreatySubjectKind,
    encode_treaty_frame,
    encode_treaty_frame_chunks,
    parse_treaty_frame,
    parse_treaty_frame_relations,
    treaty_communicate_utterance,
    treaty_frame_party_matches,
    treaty_frame_relations,
    treaty_frames_from_observation,
)
from world.communications import CommunicationRelation

pytestmark = pytest.mark.unit


def _frame(**overrides) -> TreatyFrame:
    values = dict(
        act=TreatyAct.TREATY_PROPOSE,
        treaty_ref="dpg-" + "0" * 16,
        version_ref="dpv-" + "0" * 16,
        relation_ref="dpl-" + "0" * 16,
        participant_refs=("agent:alice", "agent:bob"),
        party_kind=DiplomaticPartyKind.AGENT,
        party_ref="alice",
        envoy_ref="alice",
        subject_kind=TreatySubjectKind.CEASEFIRE,
        change_kind=TreatyChangeKind.ORIGINAL,
        provision_kinds=(TreatyProvisionKind.NON_HOSTILITY,),
        terms_digest="a" * 64,
        effective_tick=1,
        provenance=DiplomaticProvenance.SELF_DECLARED,
    )
    values.update(overrides)
    return TreatyFrame(**values)


def test_constants_match_the_bounded_contract() -> None:
    assert TREATY_FRAME_FIELD_COUNT == 22
    assert TREATY_FRAME_MAX_CHARS == 832
    assert TREATY_CHUNK_MAX_CHARS == 240
    assert TREATY_MAX_CHUNKS == 4
    assert TREATY_FRAME_SUBJECT == "trt_v1"
    assert DIPLOMACY_FRAME_FIELD_COUNT == 15
    assert DIPLOMACY_FRAME_MAX_CHARS == 320
    assert DIPLOMACY_FRAME_SUBJECT == "dip_v1"


def test_frame_round_trips_byte_for_byte() -> None:
    frame = _frame()
    text = encode_treaty_frame(frame)
    assert text.split("|")[0] == TREATY_FRAME_SUBJECT
    assert len(text.split("|")) == TREATY_FRAME_FIELD_COUNT + 1
    assert parse_treaty_frame(text) == frame


@pytest.mark.parametrize("act", tuple(TreatyAct))
def test_every_act_round_trips_with_the_full_frame(act: TreatyAct) -> None:
    if act is TreatyAct.TREATY_RECOLLECT:
        frame = _frame(
            act=act,
            basis=TreatyRecollectionBasis.DURABLE_RECORD,
            stance=TreatyRecollectionStance.REMEMBER,
            confidence=0.5,
        )
    elif act in {
        TreatyAct.TREATY_ACCEPT,
        TreatyAct.TREATY_REJECT,
        TreatyAct.TREATY_INTERPRET,
        TreatyAct.TREATY_IGNORE,
    }:
        frame = _frame(act=act)
    else:
        frame = _frame(act=act)
    assert parse_treaty_frame(encode_treaty_frame(frame)) == frame


def test_long_frame_splits_into_at_most_four_chunks() -> None:
    frame = _frame(
        record_refs=tuple(f"record-{index}" + "x" * 60 for index in range(3)),
        institutional_memory_refs=tuple(f"{index:064x}" for index in range(4)),
    )
    chunks = encode_treaty_frame_chunks(frame)
    assert 1 <= len(chunks) <= TREATY_MAX_CHUNKS
    assert all(len(chunk) <= TREATY_CHUNK_MAX_CHARS for chunk in chunks)
    relations = treaty_frame_relations(frame)
    assert parse_treaty_frame_relations(relations) == frame


def test_missing_duplicate_and_out_of_order_chunks_fail_closed() -> None:
    frame = _frame()
    relations = treaty_frame_relations(frame)
    assert parse_treaty_frame_relations(relations[:1]) is None
    duplicate = (*relations, relations[0])
    assert parse_treaty_frame_relations(duplicate) is None
    if len(relations) > 1:
        reversed_relations = tuple(reversed(relations))
        assert parse_treaty_frame_relations(reversed_relations) is None


@pytest.mark.parametrize(
    "text",
    (
        "",
        "trt_v1",
        "dip_v1|dip_contact|" + "|".join("none" for _ in range(14)),
        encode_treaty_frame(_frame()) + " ",
        encode_treaty_frame(_frame()) + "x" * 900,
    ),
)
def test_malformed_frames_return_none(text: str) -> None:
    assert parse_treaty_frame(text) is None


def test_bad_digest_and_confidence_fail_closed() -> None:
    with pytest.raises(DiplomacyError):
        _frame(terms_digest="A" * 64)
    with pytest.raises(DiplomacyError):
        _frame(
            act=TreatyAct.TREATY_RECOLLECT,
            basis=TreatyRecollectionBasis.NARRATIVE,
            stance=TreatyRecollectionStance.REMEMBER,
            confidence=1.5,
        )


def test_speaker_binding_drops_mismatch_and_replaces_provenance() -> None:
    frame = _frame()
    relations = treaty_frame_relations(frame)
    communication = type(
        "Communication",
        (),
        {
            "speaker_id": type("Speaker", (), {"value": "mallory"})(),
            "utterance": type(
                "Utterance",
                (),
                {"content": type("Content", (), {"relations": relations})()},
            )(),
        },
    )()
    observation = type("Observation", (), {"communications": (communication,)})()
    assert treaty_frames_from_observation(observation, owner_id="alice") == ()
    assert not treaty_frame_party_matches(frame, "mallory")
    assert treaty_frame_party_matches(frame, "alice")


def test_peer_provenance_is_replaced_with_communicated() -> None:
    frame = _frame(provenance=DiplomaticProvenance.WITNESSED_CONTACT)
    relations = treaty_frame_relations(frame)
    communication = type(
        "Communication",
        (),
        {
            "speaker_id": type("Speaker", (), {"value": "alice"})(),
            "utterance": type(
                "Utterance",
                (),
                {"content": type("Content", (), {"relations": relations})()},
            )(),
        },
    )()
    observation = type("Observation", (), {"communications": (communication,)})()
    frames = treaty_frames_from_observation(observation, owner_id="bob")
    assert frames[0].provenance is DiplomaticProvenance.COMMUNICATED


def test_communicate_utterance_reserves_all_chunk_relations() -> None:
    from world.actions import Talk
    from world.communications import (
        CommunicationContent,
        CommunicationId,
        CommunicationSourceBasis,
        DeclaredTransmission,
        StructuredUtterance,
    )
    from world.identifiers import EntityId

    frame = _frame()
    chunks = encode_treaty_frame_chunks(frame)
    utterance = StructuredUtterance(
        content=CommunicationContent(
            text="hello",
            concepts=(),
            relations=(
                CommunicationRelation(subject="topic", predicate="p", object="o"),
            ),
        ),
        declared=DeclaredTransmission(
            communication_id=CommunicationId("communication-1"),
            immediate_source_id=EntityId("alice"),
            parent_communication_id=None,
            root_communication_id=CommunicationId("communication-1"),
            source_agent_chain=(EntityId("alice"),),
            hop_count=0,
            sender_confidence=1.0,
            source_basis=CommunicationSourceBasis.GOAL,
        ),
    )
    command = Talk(
        recipient_id=EntityId("bob"),
        utterance=utterance,
    )
    updated = treaty_communicate_utterance(command, frame)
    relations = updated.utterance.content.relations
    assert len(relations) == 1 + len(chunks)
    assert relations[1].subject == TREATY_FRAME_SUBJECT
    assert all(
        len(relation.object) <= TREATY_CHUNK_MAX_CHARS for relation in relations[1:]
    )


def test_communication_module_never_imports_agent_commands() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "agents"
        / "cognition"
        / "diplomacy_communication.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    imported |= {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "AgentCommand" not in imported
