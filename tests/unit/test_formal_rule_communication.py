"""Bounded ``fr_v1`` formal-rule claims over existing Talk/Tell speech."""

from __future__ import annotations

import hashlib
from typing import Any, cast

import pytest

from agents.cognition import (
    FORMAL_RULE_COMMUNICATION_POLICY_VERSION,
    FORMAL_RULE_FRAME_SUBJECT,
    FORMAL_RULE_PREDICATES,
    FormalRuleAct,
    FormalRuleAuthorityKind,
    FormalRuleClaim,
    FormalRuleConstraintKind,
    FormalRuleError,
    FormalRuleReportKind,
    FormalRuleStage,
    encode_formal_rule_claim,
    formal_rule_claim_relation,
    formal_rule_communicate_utterance,
    parse_formal_rule_claim,
    parse_formal_rule_claim_relation,
)
from world.actions import Talk, Tell, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

SCOPE_DIGEST = hashlib.sha256(b"formal-rule-scope").hexdigest()
SYSTEM_REF = "frs-0123456789abcdef"
RULE_REF = "frl-0123456789abcdef"
BASE_RELATIONS = (
    CommunicationRelation(subject="greeting", predicate="hello", object="once"),
)


def _talk(relations: tuple[CommunicationRelation, ...] = BASE_RELATIONS) -> Talk:
    return Talk(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="talk-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _tell(relations: tuple[CommunicationRelation, ...] = BASE_RELATIONS) -> Tell:
    return Tell(
        recipient_id=EntityId("body-ben"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-ada"),
            communication_id="tell-1",
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _claim(act: FormalRuleAct) -> FormalRuleClaim:
    if act is FormalRuleAct.ASSERT:
        return FormalRuleClaim(
            act=act,
            system_ref=SYSTEM_REF,
            rule_ref=RULE_REF,
            version_number=1,
            stage=FormalRuleStage.NORM,
            constraint_kind=FormalRuleConstraintKind.PROHIBITION,
            action_token="attack",
            scope_digest=SCOPE_DIGEST,
            authority_kind=FormalRuleAuthorityKind.CUSTOM,
        )
    if act is FormalRuleAct.AMEND:
        return FormalRuleClaim(
            act=act,
            system_ref=SYSTEM_REF,
            rule_ref=RULE_REF,
            revision=2,
        )
    if act is FormalRuleAct.RECOGNIZE:
        return FormalRuleClaim(
            act=act,
            system_ref=SYSTEM_REF,
            rule_ref=RULE_REF,
            authority_kind=FormalRuleAuthorityKind.OFFICE,
        )
    if act is FormalRuleAct.REPORT:
        return FormalRuleClaim(
            act=act,
            rule_ref=RULE_REF,
            report_kind=FormalRuleReportKind.VIOLATION,
        )
    return FormalRuleClaim(
        act=act,
        system_ref=SYSTEM_REF,
        rule_ref=RULE_REF,
    )


def test_policy_subject_and_predicates_are_frozen() -> None:
    assert FORMAL_RULE_COMMUNICATION_POLICY_VERSION == (
        "formal-rule-communication.v1"
    )
    assert FORMAL_RULE_FRAME_SUBJECT == "fr_v1"
    assert tuple(FORMAL_RULE_PREDICATES.values()) == (
        "fr_assert",
        "fr_support",
        "fr_oppose",
        "fr_challenge",
        "fr_reinterpret",
        "fr_amend",
        "fr_withdraw",
        "fr_recognize",
        "fr_report",
    )


def test_every_act_round_trips_with_exact_arity() -> None:
    for act in FormalRuleAct:
        claim = _claim(act)
        frame = encode_formal_rule_claim(claim)
        assert frame.startswith(f"fr_v1:{FORMAL_RULE_PREDICATES[act]}:")
        assert len(frame.split(":")) == 16
        parsed = parse_formal_rule_claim(frame)
        assert parsed == claim
        assert parsed is not claim

        subject, predicate, body = formal_rule_claim_relation(claim)
        assert subject == FORMAL_RULE_FRAME_SUBJECT
        assert predicate == FORMAL_RULE_PREDICATES[act]
        assert parse_formal_rule_claim_relation(subject, predicate, body) == claim


def test_malformed_and_overlong_frames_are_rejected() -> None:
    good = encode_formal_rule_claim(_claim(FormalRuleAct.ASSERT))
    malformed = (
        "",
        "fr_v1:fr_assert:a:b",
        good.replace("fr_v1", "org_v1"),
        good.replace("fr_assert", "fr_unknown"),
        good.replace(":custom:", ":not_an_authority:"),
        good.replace(":1:", ":0:"),
        good.replace(SCOPE_DIGEST, "not-a-digest"),
        good + ":extra",
        "fr_v1:fr_assert:" + "a" * 400,
        good.replace(":", " :", 1),
    )
    for frame in malformed:
        with pytest.raises(FormalRuleError) as excinfo:
            parse_formal_rule_claim(frame)
        assert excinfo.value.code == "formal_rule_frame_invalid"

    with pytest.raises(FormalRuleError) as excinfo:
        FormalRuleClaim(act=FormalRuleAct.ASSERT, system_ref=SYSTEM_REF)
    assert excinfo.value.code == "formal_rule_frame_invalid"


def test_relational_parser_ignores_unrelated_frames() -> None:
    assert parse_formal_rule_claim_relation("org_v1", "org_claim", "body") is None
    assert (
        parse_formal_rule_claim_relation("org_ca_v1", "org_ca_propose", "body")
        is None
    )
    assert parse_formal_rule_claim_relation("fr_v1", "unknown", "body") is None

    with pytest.raises(FormalRuleError) as excinfo:
        parse_formal_rule_claim_relation("fr_v1", "fr_assert", "body")
    assert excinfo.value.code == "formal_rule_frame_invalid"


def test_only_talk_and_tell_accept_a_claim() -> None:
    claim = _claim(FormalRuleAct.SUPPORT)
    for command in (_talk(), _tell()):
        updated = formal_rule_communicate_utterance(command, claim)
        assert type(updated) is type(command)

    with pytest.raises(FormalRuleError) as excinfo:
        formal_rule_communicate_utterance(
            Wait(), claim
        )
    assert excinfo.value.code == "formal_rule_frame_unsupported_command"

    assert formal_rule_communicate_utterance(_talk(), None) is not None


def test_existing_relations_and_command_type_are_preserved() -> None:
    claim = _claim(FormalRuleAct.ASSERT)
    talk = _talk()
    updated = formal_rule_communicate_utterance(talk, claim)

    assert type(updated) is Talk
    assert updated is not talk
    assert updated.recipient_id == talk.recipient_id
    assert updated.utterance.content.text == talk.utterance.content.text
    relations = updated.utterance.content.relations
    assert relations[:1] == BASE_RELATIONS
    assert len(relations) == 2
    assert relations[1].subject == FORMAL_RULE_FRAME_SUBJECT
    assert (
        parse_formal_rule_claim_relation(
            relations[1].subject, relations[1].predicate, relations[1].object
        )
        == claim
    )

    repeated = cast(Any, formal_rule_communicate_utterance(updated, claim))
    assert repeated.utterance.content.relations == relations

    tell = _tell()
    updated_tell = formal_rule_communicate_utterance(tell, claim)
    assert type(updated_tell) is Tell
    assert len(updated_tell.utterance.content.relations) == 2


def test_receiver_forms_independent_evidence_without_copying() -> None:
    claim = _claim(FormalRuleAct.OPPOSE)
    parsed = parse_formal_rule_claim(encode_formal_rule_claim(claim))
    assert parsed == claim
    assert parsed is not claim
    assert not hasattr(parsed, "ledger")
    assert not hasattr(parsed, "owner_id")
    with pytest.raises(AttributeError):
        parsed.act = FormalRuleAct.SUPPORT  # type: ignore[misc]


def test_organization_agency_and_collective_decision_frames_are_unchanged() -> None:
    from agents.cognition import (
        COLLECTIVE_DECISION_PREDICATES,
        ORGANIZATION_AGENCY_FRAME_SUBJECT,
        ORGANIZATION_AGENCY_PREDICATES,
        ORGANIZATION_FRAME_SUBJECT,
        ORGANIZATION_OPERATION_FRAME_SUBJECT,
    )

    assert ORGANIZATION_FRAME_SUBJECT == "org_v1"
    assert ORGANIZATION_OPERATION_FRAME_SUBJECT == "org_op_v1"
    assert ORGANIZATION_AGENCY_FRAME_SUBJECT == "org_ca_v1"
    assert ORGANIZATION_AGENCY_PREDICATES
    assert COLLECTIVE_DECISION_PREDICATES
    assert FORMAL_RULE_FRAME_SUBJECT not in {
        ORGANIZATION_FRAME_SUBJECT,
        ORGANIZATION_OPERATION_FRAME_SUBJECT,
        ORGANIZATION_AGENCY_FRAME_SUBJECT,
    }
