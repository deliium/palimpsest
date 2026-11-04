"""V4-10 bounded ``dip_v1`` frame tests."""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from agents.cognition import (
    DIPLOMACY_FRAME_FIELD_COUNT,
    DIPLOMACY_FRAME_MAX_CHARS,
    DIPLOMACY_FRAME_SUBJECT,
    DIPLOMACY_FRAME_VERSION,
    DIPLOMACY_PREDICATES,
    DiplomacyFrame,
    DiplomaticAct,
    DiplomaticContactKind,
    DiplomaticPartyKind,
    DiplomaticProvenance,
    DiplomaticTermKind,
    diplomacy_contact_anchors_from_observation,
    diplomacy_frame_party_matches,
    diplomacy_frame_relation,
    diplomacy_frames_from_observation,
    encode_diplomacy_frame,
    parse_diplomacy_frame,
    parse_diplomacy_frame_relation,
)
from world.communications import CommunicationRelation

pytestmark = pytest.mark.unit


def _frame(act: DiplomaticAct, **overrides: object) -> DiplomacyFrame:
    values: dict[str, object] = {"act": act, "envoy_ref": "envoy-1"}
    if act in {
        DiplomaticAct.OPEN_NEGOTIATION,
        DiplomaticAct.PROPOSE,
        DiplomaticAct.PROMISE,
        DiplomaticAct.DISPUTE,
        DiplomaticAct.SHARED_PROJECT,
    }:
        values["topic_subject"] = "trade"
    if act in {
        DiplomaticAct.PROPOSE,
        DiplomaticAct.PROMISE,
        DiplomaticAct.DISPUTE,
        DiplomaticAct.SHARED_PROJECT,
    }:
        values["term_kind"] = DiplomaticTermKind.MATERIAL_EXCHANGE
    if act in {
        DiplomaticAct.ACCEPT,
        DiplomaticAct.REJECT,
        DiplomaticAct.WITHDRAW,
        DiplomaticAct.REPORT,
    }:
        values["instrument_ref"] = "dpi-" + "0" * 16
    values.update(overrides)
    return DiplomacyFrame(**values)  # type: ignore[arg-type]


ALL_ACTS = tuple(DiplomaticAct)


def test_frame_constants_and_predicates() -> None:
    assert DIPLOMACY_FRAME_VERSION == "dip_v1"
    assert DIPLOMACY_FRAME_SUBJECT == "dip_v1"
    assert DIPLOMACY_FRAME_MAX_CHARS == 320
    assert DIPLOMACY_FRAME_FIELD_COUNT == 15
    assert len(DiplomaticAct) == 12
    assert set(DIPLOMACY_PREDICATES) == set(DiplomaticAct)
    assert {DIPLOMACY_PREDICATES[act] for act in DiplomaticAct} == {
        act.value for act in DiplomaticAct
    }


@pytest.mark.parametrize("act", ALL_ACTS)
def test_every_act_round_trips(act: DiplomaticAct) -> None:
    frame = _frame(act)
    text = encode_diplomacy_frame(frame)
    assert parse_diplomacy_frame(text) == frame
    relation = diplomacy_frame_relation(frame)
    assert relation.subject == DIPLOMACY_FRAME_SUBJECT
    assert (
        parse_diplomacy_frame_relation(
            relation.subject, relation.predicate, relation.object
        )
        == frame
    )


def test_topic_subject_is_required_only_for_subject_acts() -> None:
    with pytest.raises(ValueError):
        DiplomacyFrame(act=DiplomaticAct.OPEN_NEGOTIATION, envoy_ref="envoy-1")
    with pytest.raises(ValueError):
        DiplomacyFrame(
            act=DiplomaticAct.ACCEPT,
            envoy_ref="envoy-1",
            instrument_ref="dpi-" + "0" * 16,
            topic_subject="trade",
        )


def test_unknown_keys_and_malformed_text_are_rejected() -> None:
    text = encode_diplomacy_frame(_frame(DiplomaticAct.CONTACT))
    assert parse_diplomacy_frame(text + "|extra") is None
    assert parse_diplomacy_frame("other" + text[6:]) is None
    assert (
        parse_diplomacy_frame("dip_v1|dip_unknown|" + "|".join(["none"] * 14)) is None
    )
    assert parse_diplomacy_frame("x" * (DIPLOMACY_FRAME_MAX_CHARS + 1)) is None
    assert parse_diplomacy_frame("") is None
    assert parse_diplomacy_frame(text.replace("|", " ")) is None


def test_oversize_and_token_caps_are_enforced() -> None:
    with pytest.raises(ValueError):
        DiplomacyFrame(act=DiplomaticAct.CONTACT, envoy_ref="x" * 200)
    frame = _frame(DiplomaticAct.CONTACT, declaration_ref="x" * 120)
    assert len(encode_diplomacy_frame(frame)) < DIPLOMACY_FRAME_MAX_CHARS
    assert parse_diplomacy_frame_relation("dip_v1", "nope", "x") is None
    assert parse_diplomacy_frame_relation("other", "dip_contact", "x") is None


def test_speaker_must_match_the_claimed_envoy() -> None:
    frame = _frame(DiplomaticAct.PROPOSE, actor_ref="envoy-1")
    assert diplomacy_frame_party_matches(frame, "envoy-1") is True
    assert diplomacy_frame_party_matches(frame, "other") is False
    assert diplomacy_frame_party_matches(frame, None) is False


def _observation(frame: DiplomacyFrame, *, speaker: str) -> SimpleNamespace:
    relation = diplomacy_frame_relation(frame)
    communication = SimpleNamespace(
        speaker_id=SimpleNamespace(value=speaker),
        utterance=SimpleNamespace(
            content=SimpleNamespace(relations=(relation,)),
            declared=SimpleNamespace(immediate_source_id=speaker),
        ),
    )
    return SimpleNamespace(communications=(communication,), occurrences=())


def test_observation_frames_are_receiver_attributed() -> None:
    frame = _frame(
        DiplomaticAct.PROPOSE,
        actor_ref="envoy-1",
        party_kind=DiplomaticPartyKind.ORGANIZATION,
        party_ref="orgc-" + "0" * 16,
        mandate_ref="rmd-" + "0" * 16,
        provenance=DiplomaticProvenance.PRINCIPAL_DECLARED,
    )
    frames = diplomacy_frames_from_observation(
        _observation(frame, speaker="envoy-1"), owner_id="owner-a"
    )
    assert len(frames) == 1
    received = frames[0]
    assert received.party_ref == "orgc-" + "0" * 16
    assert received.actor_ref == "envoy-1"
    assert received.provenance is DiplomaticProvenance.COMMUNICATED
    assert received.mandate_ref == "rmd-" + "0" * 16


def test_speaker_mismatch_drops_the_frame(caplog: pytest.LogCaptureFixture) -> None:
    frame = _frame(DiplomaticAct.ACCEPT, envoy_ref="envoy-1")
    with caplog.at_level(
        logging.WARNING, logger="agents.cognition.diplomacy_communication"
    ):
        frames = diplomacy_frames_from_observation(
            _observation(frame, speaker="someone-else"), owner_id="owner-a"
        )
    assert frames == ()
    assert "diplomacy_party_mismatch" in caplog.text


def test_contact_anchors_parse_and_malformed_entries_drop() -> None:
    observation = SimpleNamespace(
        occurrences=(
            SimpleNamespace(
                kind="contact_recorded",
                public_facts={
                    "contact_location_id": "region-1",
                    "contact_participant_ids": ["owner-a", "agent-b", "agent-c"],
                    "contact_present_ids": ["owner-a", "agent-b"],
                },
                provenance=SimpleNamespace(
                    source_event_id=SimpleNamespace(value="evt-1")
                ),
            ),
            SimpleNamespace(
                kind="contact_recorded",
                public_facts={"contact_participant_ids": "not-a-list"},
                provenance=SimpleNamespace(
                    source_event_id=SimpleNamespace(value="evt-2")
                ),
            ),
            SimpleNamespace(
                kind="other",
                public_facts={},
                provenance=SimpleNamespace(
                    source_event_id=SimpleNamespace(value="evt-3")
                ),
            ),
        )
    )
    anchors = diplomacy_contact_anchors_from_observation(
        observation, owner_id="owner-a"
    )
    assert len(anchors) == 1
    anchor = anchors[0]
    assert anchor.location_anchor == "region-1"
    assert anchor.participant_refs == ("agent-b", "agent-c")
    assert anchor.participant_count == 3
    assert anchor.contact_kind is DiplomaticContactKind.DIRECT_CO_PRESENCE
    assert anchor.source_ref == "evt-1"


def test_frame_logs_never_contain_the_body(caplog: pytest.LogCaptureFixture) -> None:
    frame = _frame(DiplomaticAct.PROPOSE, topic_subject="secret-subject")
    text = encode_diplomacy_frame(frame)
    with caplog.at_level(logging.DEBUG):
        assert parse_diplomacy_frame(text) is not None
        assert parse_diplomacy_frame("broken") is None
    assert "secret-subject" not in caplog.text
    assert text not in caplog.text


def test_communication_relation_subject_is_the_only_attach_point() -> None:
    frame = _frame(DiplomaticAct.CONTACT)
    relation = diplomacy_frame_relation(frame)
    assert type(relation) is CommunicationRelation
    assert relation.subject == DIPLOMACY_FRAME_SUBJECT
    assert relation.predicate == DiplomaticAct.CONTACT.value
