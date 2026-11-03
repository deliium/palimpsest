"""V4-06 formal-rule deliberation bias and speech injection."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from agents.cognition import (
    FormalRuleAct,
    FormalRuleAuthorityKind,
    FormalRuleClaim,
    FormalRuleConstraintKind,
    FormalRuleResponseKind,
    FormalRuleStage,
    apply_formal_rule_update,
    default_formal_rule_policy,
    formal_rule_communicate_utterance,
    formal_rule_direction_preference,
    formal_rule_response_penalties,
    select_formal_rule_response,
)
from agents.cognition.social_conventions import (
    ConventionBelief,
    ConventionContent,
    ConventionLedger,
    ConventionSituation,
    ConventionStatus,
    convention_belief_id,
)
from agents.models import AgentId
from world._rules import COMMAND_RULE_MATRIX
from world.actions import Talk
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

OWNER = AgentId("agent-1")
SCOPE_DIGEST = hashlib.sha256(b"scope").hexdigest()
SYSTEM_REF = "frs-0123456789abcdef"
RULE_REF = "frl-0123456789abcdef"


def _talk() -> Talk:
    return Talk(
        recipient_id=EntityId("body-2"),
        utterance=origin_utterance(
            text="hello",
            speaker_id=EntityId("body-1"),
            communication_id="talk-1",
            relations=(
                CommunicationRelation(
                    subject="greeting", predicate="hello", object="once"
                ),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _assert_claim() -> FormalRuleClaim:
    return FormalRuleClaim(
        act=FormalRuleAct.ASSERT,
        system_ref=SYSTEM_REF,
        rule_ref=RULE_REF,
        version_number=1,
        stage=FormalRuleStage.NORM,
        constraint_kind=FormalRuleConstraintKind.PROHIBITION,
        action_token="attack",
        scope_digest=SCOPE_DIGEST,
        authority_kind=FormalRuleAuthorityKind.CUSTOM,
    )


def _convention_ledger() -> object:
    content = ConventionContent(
        situation=ConventionSituation.COLOCATED_MEETING,
        usual_action="attack",
    )
    return ConventionLedger(
        owner_id=OWNER,
        beliefs=(
            ConventionBelief(
                belief_id=convention_belief_id(OWNER, content),
                owner_id=OWNER,
                content=content,
                status=ConventionStatus.ACTIVE,
                strength=0.6,
            ),
        ),
    )


def _observation() -> SimpleNamespace:
    return SimpleNamespace(tick=1, artifacts=(), communications=())


def test_direction_preference_only_biases_existing_candidates() -> None:
    ledger = apply_formal_rule_update(
        OWNER,
        1,
        _observation(),
        None,
        social_conventions=_convention_ledger(),
    )
    bias = formal_rule_direction_preference(ledger, action_token="attack")
    assert -0.25 <= bias <= 0.25
    assert formal_rule_direction_preference(ledger, action_token="wait") == 0.0


def test_response_penalties_do_not_create_commands() -> None:
    ledger = apply_formal_rule_update(
        OWNER,
        1,
        _observation(),
        None,
        social_conventions=_convention_ledger(),
    )
    _, response = select_formal_rule_response(
        ledger,
        tick=2,
        action_token="attack",
        policy=default_formal_rule_policy(),
    )
    assert response is not None
    assert response.kind is FormalRuleResponseKind.IGNORE
    penalties = formal_rule_response_penalties(ledger, tick=2)
    assert penalties == {}
    penalties_after = formal_rule_response_penalties(
        select_formal_rule_response(
            ledger,
            tick=2,
            action_token="attack",
            policy=default_formal_rule_policy(),
        )[0],
        tick=2,
    )
    assert all(0.0 <= value <= 0.25 for value in penalties_after.values())
    assert not any(
        isinstance(value, type) and value.__name__.endswith("Command")
        for value in penalties_after.values()
    )


def test_rule_speech_stamps_existing_talk_and_preserves_other_relations() -> None:
    talk = _talk()
    updated = formal_rule_communicate_utterance(talk, _assert_claim())
    assert type(updated) is Talk
    assert updated.recipient_id == talk.recipient_id
    assert updated.utterance.content.text == talk.utterance.content.text
    relations = updated.utterance.content.relations
    assert relations[0] == talk.utterance.content.relations[0]
    assert relations[1].subject == "fr_v1"
    assert len(relations) == 2


def test_no_formal_rule_command_kind_is_added() -> None:
    assert len(COMMAND_RULE_MATRIX) == 43
    assert not any(
        "FormalRule" in command.__name__ for command in COMMAND_RULE_MATRIX
    )
    from observer import SEMANTIC_EVENT_TYPES

    assert len(SEMANTIC_EVENT_TYPES) == 73
