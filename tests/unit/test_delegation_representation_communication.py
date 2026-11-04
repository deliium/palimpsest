"""V4-09 bounded ``rep_v1`` frames and verified-speaker rules."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.delegation_representation import (
    RepresentationDurationKind,
    RepresentationError,
    RepresentationPrincipalKind,
    RepresentationProvenance,
    RepresentationScopeKind,
)
from agents.cognition.delegation_representation_communication import (
    REPRESENTATION_FRAME_MAX_CHARS,
    RepresentationAct,
    RepresentationFrame,
    encode_representation_frame,
    parse_representation_frame,
    parse_representation_frame_relation,
    representation_communicate_utterance,
    representation_frame_party_matches,
    representation_frame_relation,
    representation_frames_from_observation,
)
from world.actions import Talk
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_MANDATE = "rmd-" + "1" * 16


def _frame(
    act: RepresentationAct = RepresentationAct.CLAIM, **overrides: object
) -> RepresentationFrame:
    values: dict[str, object] = {
        "act": act,
        "mandate_ref": None
        if act in {RepresentationAct.CLAIM, RepresentationAct.DELEGATE}
        else _MANDATE,
        "principal_kind": RepresentationPrincipalKind.AGENT,
        "principal_ref": "agent-principal",
        "representative_ref": "agent-representative",
        "scope_kind": RepresentationScopeKind.SPEAK_FOR,
        "scope_subject": "border",
        "duration_kind": RepresentationDurationKind.UNTIL_REVOKED,
        "end_tick": None,
        "provenance": RepresentationProvenance.SELF_DECLARED,
        "revision": 0,
    }
    values.update(overrides)
    return RepresentationFrame(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("act", tuple(RepresentationAct))
def test_every_act_round_trips(act: RepresentationAct) -> None:
    frame = _frame(act)
    text = encode_representation_frame(frame)
    assert text.startswith(f"rep_v1:{act.value}:")
    assert parse_representation_frame(text) == frame
    relation = representation_frame_relation(frame)
    assert (
        parse_representation_frame_relation(
            relation.subject, relation.predicate, relation.object
        )
        == frame
    )


def test_optional_fields_serialize_as_none() -> None:
    frame = _frame(
        act=RepresentationAct.REPORT,
        principal_kind=RepresentationPrincipalKind.UNKNOWN,
        principal_ref=None,
        scope_kind=RepresentationScopeKind.UNKNOWN,
        scope_subject=None,
        duration_kind=RepresentationDurationKind.UNKNOWN,
        provenance=RepresentationProvenance.COMMUNICATED,
    )
    text = encode_representation_frame(frame)
    assert text.count("none") >= 3
    assert parse_representation_frame(text) == frame


def test_over_cap_and_malformed_frames_return_none() -> None:
    oversized = _frame(scope_subject="x" * 32)
    with pytest.raises(RepresentationError, match="representation_frame_too_large"):
        encode_representation_frame(
            _frame(
                act=RepresentationAct.ACCEPT,
                principal_ref="agent-" + "p" * 100,
                representative_ref="agent-" + "r" * 100,
            )
        )
    assert parse_representation_frame("rep_v1:rep_claim") is None
    assert (
        parse_representation_frame("rep_v2:rep_claim:" + ":".join(["none"] * 10))
        is None
    )
    assert (
        parse_representation_frame("x" * (REPRESENTATION_FRAME_MAX_CHARS + 1)) is None
    )
    assert (
        parse_representation_frame(
            "rep_v1:rep_claim:none:agent:a:b:speak_for:border:until_revoked:none:self_declared:not-int"
        )
        is None
    )
    assert representation_frame_relation(oversized) is not None


def test_party_match_rules() -> None:
    assert representation_frame_party_matches(_frame(), "agent-representative")
    assert not representation_frame_party_matches(_frame(), "agent-other")

    delegated = _frame(RepresentationAct.DELEGATE, representative_ref="agent-c")
    assert representation_frame_party_matches(delegated, "agent-principal")
    assert not representation_frame_party_matches(delegated, "agent-c")
    assert not representation_frame_party_matches(
        _frame(RepresentationAct.DELEGATE, principal_ref="agent-c"), "agent-principal"
    )
    assert not representation_frame_party_matches(
        _frame(RepresentationAct.DELEGATE, representative_ref="agent-principal"),
        "agent-principal",
    )

    accepted = _frame(RepresentationAct.ACCEPT)
    assert representation_frame_party_matches(accepted, "agent-principal")
    assert not representation_frame_party_matches(accepted, "agent-representative")
    assert not representation_frame_party_matches(
        _frame(
            RepresentationAct.ACCEPT,
            principal_kind=RepresentationPrincipalKind.ORGANIZATION,
            principal_ref="orgc-" + "1" * 16,
        ),
        "agent-principal",
    )

    revoked = _frame(RepresentationAct.REVOKE)
    assert representation_frame_party_matches(revoked, "agent-principal")
    assert representation_frame_party_matches(revoked, "agent-representative")
    assert not representation_frame_party_matches(revoked, "agent-other")

    assert representation_frame_party_matches(
        _frame(RepresentationAct.SUPPORT),
        "agent-other",
    )
    assert representation_frame_party_matches(
        _frame(RepresentationAct.RESIGN, representative_ref="agent-c"),
        "agent-c",
    )


def test_observation_collection_keeps_only_verified_speakers() -> None:
    accepted = _frame(RepresentationAct.ACCEPT)
    forged = _frame(RepresentationAct.ACCEPT, principal_ref="agent-other")
    observation = SimpleNamespace(
        communications=(
            SimpleNamespace(
                speaker_id=EntityId("agent-principal"),
                utterance=origin_utterance(
                    text="delegation",
                    speaker_id=EntityId("agent-principal"),
                    relations=(
                        representation_frame_relation(accepted),
                        representation_frame_relation(forged),
                        CommunicationRelation(
                            subject="other", predicate="x", object="y"
                        ),
                    ),
                ),
            ),
        )
    )
    frames = representation_frames_from_observation(observation, owner_id="agent-owner")
    assert frames == (replace(accepted, actor_ref="agent-principal"),)


def test_attach_frame_preserves_command_and_rejects_foreign_speaker() -> None:
    speaker = EntityId("agent-representative")
    command = Talk(
        recipient_id=EntityId("agent-principal"),
        utterance=origin_utterance(text="hello", speaker_id=speaker),
    )
    frame = _frame(RepresentationAct.CLAIM)
    attached = representation_communicate_utterance(command, frame)
    assert type(attached) is Talk
    assert attached.recipient_id == command.recipient_id
    assert len(attached.utterance.content.relations) == 1

    forged = _frame(RepresentationAct.CLAIM, representative_ref="agent-other")
    unchanged = representation_communicate_utterance(command, forged)
    assert unchanged is command


def test_relation_parser_rejects_foreign_subject_and_predicate() -> None:
    assert parse_representation_frame_relation("ev_v1", "rep_claim", "x") is None
    assert parse_representation_frame_relation("rep_v1", "other", "x") is None
