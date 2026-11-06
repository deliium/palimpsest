# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,attr-defined,no-untyped-def,no-untyped-call,call-overload,index,type-arg,unused-ignore"
from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.organized_conflict import (
    ConflictOperation,
    ConflictRole,
    ConflictTargetKind,
    OrganizedConflictError,
    conflict_target_token,
    default_organized_conflict_policy,
)
from agents.cognition.organized_conflict_communication import (
    CONFLICT_FRAME_FIELD_COUNT,
    CONFLICT_FRAME_MAX_CHARS,
    ConflictAct,
    ConflictFrame,
    conflict_communicate_utterance,
    conflict_frame_party_matches,
    conflict_frame_relation,
    conflict_frames_from_command,
    conflict_frames_from_observation,
    encode_conflict_frame,
    parse_conflict_frame,
    parse_conflict_frame_relation,
)
from world import EntityId
from world.actions import Tell
from world.communications import origin_utterance

SPEAKER = "body-ada"


def _frame(**overrides: object) -> ConflictFrame:
    payload = {
        "act": ConflictAct.PROPOSE,
        "plan_ref": "ocp-" + "a" * 16,
        "operation": ConflictOperation.COORDINATED_ATTACK,
        "target_kind": ConflictTargetKind.AGENT,
        "target_ref": "b" * 16,
        "role": ConflictRole.ATTACKER,
        "side_ref": conflict_target_token(SPEAKER),
        "window_start": 1,
        "window_end": 5,
        "participant_refs": (conflict_target_token(SPEAKER),),
    }
    payload.update(overrides)
    return ConflictFrame(**payload)  # type: ignore[arg-type]


def _utterance(frame: ConflictFrame, speaker: str = SPEAKER):
    return origin_utterance(
        text="ocf_v1",
        speaker_id=EntityId(speaker),
        relations=(conflict_frame_relation(frame),),
    )


def test_own_speech_is_recorded_into_the_owner_ledger() -> None:
    from agents.cognition.organized_conflict import (
        empty_organized_conflict_ledger,
        record_organized_conflict_utterance,
    )
    from agents.models import AgentId

    owner = AgentId(SPEAKER)
    frame = _frame()
    command = Tell(recipient_id=EntityId("body-b"), utterance=_utterance(frame))
    ledger = empty_organized_conflict_ledger(owner, tick=0)
    updated = record_organized_conflict_utterance(
        ledger,
        command,
        owner_id=owner,
        tick=1,
        policy=default_organized_conflict_policy(),
    )
    assert updated.plans
    assert updated.plans[0].provenance.value == "self_declared"
    assert updated.revision == 1


def test_frame_has_exactly_twelve_fields_and_256_char_bound() -> None:
    frame = _frame()
    text = encode_conflict_frame(frame)
    assert len(text.split("|")) == CONFLICT_FRAME_FIELD_COUNT == 12
    assert len(text) <= CONFLICT_FRAME_MAX_CHARS
    assert parse_conflict_frame(text) == frame


def test_parse_rejects_wrong_count_and_control_chars() -> None:
    text = encode_conflict_frame(_frame())
    assert parse_conflict_frame("|".join(text.split("|")[:-1])) is None
    assert parse_conflict_frame(text + "|extra") is None
    assert parse_conflict_frame(text.replace("propose", "pro pose")) is None
    assert parse_conflict_frame("x" * (CONFLICT_FRAME_MAX_CHARS + 1)) is None


def test_speaker_mismatch_is_dropped() -> None:
    frame = _frame()
    good = SimpleNamespace(
        speaker_id=EntityId(SPEAKER),
        utterance=_utterance(frame),
    )
    bad = SimpleNamespace(
        speaker_id=EntityId("body-ben"),
        utterance=_utterance(frame),
    )
    assert conflict_frames_from_observation(
        SimpleNamespace(communications=(good,))
    ) == (frame,)
    assert conflict_frames_from_observation(SimpleNamespace(communications=(bad,))) == (
        None,
    )
    assert conflict_frame_party_matches(frame, SPEAKER) is True
    assert conflict_frame_party_matches(frame, "body-ben") is False
    join = _frame(
        act=ConflictAct.JOIN,
        participant_refs=(conflict_target_token("body-ben"),),
    )
    assert conflict_frame_party_matches(join, "body-ben") is False


def test_attach_respects_relation_cap_and_duplicate_subject() -> None:
    frame = _frame()
    command = Tell(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(text="hello", speaker_id=EntityId(SPEAKER)),
    )
    attached = conflict_communicate_utterance(
        command, frame, owner_id=SimpleNamespace(value=SPEAKER), tick=1
    )
    assert any(
        relation.subject == "ocf_v1"
        for relation in attached.utterance.content.relations
    )
    with pytest.raises(OrganizedConflictError):
        conflict_communicate_utterance(
            attached, frame, owner_id=SimpleNamespace(value=SPEAKER), tick=1
        )
    with pytest.raises(OrganizedConflictError):
        conflict_communicate_utterance(
            command,
            _frame(side_ref=conflict_target_token("body-ben")),
            owner_id=SimpleNamespace(value=SPEAKER),
            tick=1,
        )


def test_frame_relation_round_trips_and_rejects_wrong_subject() -> None:
    frame = _frame()
    relation = conflict_frame_relation(frame)
    assert relation.subject == "ocf_v1"
    assert (
        parse_conflict_frame_relation(
            relation.subject, relation.predicate, relation.object
        )
        == frame
    )
    assert (
        parse_conflict_frame_relation("other", relation.predicate, relation.object)
        is None
    )


def test_own_command_requires_owner_side() -> None:
    frame = _frame()
    command = Tell(
        recipient_id=EntityId("body-ben"),
        utterance=_utterance(frame),
    )
    assert conflict_frames_from_command(command, SimpleNamespace(value=SPEAKER)) == (
        frame,
    )
    wrong = Tell(
        recipient_id=EntityId("body-ben"),
        utterance=_utterance(
            _frame(side_ref=conflict_target_token("body-ben")),
        ),
    )
    assert conflict_frames_from_command(wrong, SimpleNamespace(value=SPEAKER)) == ()
