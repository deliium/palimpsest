"""Bounded ``mkt_v1`` frames round-trip and preserve existing relations."""

from __future__ import annotations

import pytest

from agents.cognition.market_institutions import (
    MarketCadence,
    MarketExpectation,
    MarketInstitutionError,
    MarketRoleKind,
)
from agents.cognition.market_institutions_communication import (
    MARKET_FRAME_MAX_RELATIONS,
    MarketClaim,
    MarketCommunicationAct,
    encode_market_claim,
    market_claim_relation,
    market_communicate_utterance,
    parse_market_claim,
    parse_market_claim_relation,
)
from tests.unit.market_institutions_helpers import (
    OWNER_ENTITY,
    ledger,
    record,
    schedule,
    venue,
)
from world.actions import Talk, Wait
from world.communications import (
    CommunicationRelation,
    origin_utterance,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

RECIPIENT = EntityId("body-2")


@pytest.mark.parametrize(
    "act",
    (
        MarketCommunicationAct.ANNOUNCE_MEETING,
        MarketCommunicationAct.EXPECT_MEETING,
        MarketCommunicationAct.DECLINE_MEETING,
        MarketCommunicationAct.CLAIM_ROLE,
        MarketCommunicationAct.CITE_RECORD,
    ),
)
def test_every_act_round_trips(act: MarketCommunicationAct) -> None:
    claim = MarketClaim(act=act, label_token="venue-abc")
    assert parse_market_claim(encode_market_claim(claim)) == claim


def test_schedule_and_role_round_trip() -> None:
    claim = MarketClaim(
        act=MarketCommunicationAct.EXPECT_MEETING,
        label_token="venue-abc",
        expectation=MarketExpectation.EXPECTED,
        cadence=MarketCadence.RECURRING_INTERVAL,
        interval_ticks=5,
        phase_tick=1,
        role_kind=MarketRoleKind.BROKER,
        role_ref="a" * 16,
        anchor="record-1",
    )
    assert parse_market_claim(encode_market_claim(claim)) == claim


@pytest.mark.parametrize(
    "text",
    (
        "mkt_v1:mkt_meeting:venue-abc",
        "other:mkt_meeting:venue-abc:none:unknown:none:none:unknown:none:none",
        "mkt_v1:not_an_act:venue-abc:none:unknown:none:none:unknown:none:none",
        "mkt_v1:mkt_meeting:venue-abc:bad:unknown:none:none:unknown:none:none",
        "mkt_v1:mkt_meeting:venue-abc:none:recurring_interval:none:none:unknown:none:none",
        "mkt_v1:mkt_meeting:venue-abc:none:unknown:none:none:unknown:bad%20ref:none",
        "mkt_v1:mkt_meeting:venue abc:none:unknown:none:none:unknown:none:none",
    ),
)
def test_malformed_frames_fail_closed(text: str) -> None:
    with pytest.raises(MarketInstitutionError):
        parse_market_claim(text)


def test_unrelated_relation_returns_none() -> None:
    relation = CommunicationRelation(
        subject="org_v1", predicate="org_admit", object="x"
    )
    assert parse_market_claim_relation(relation) is None


def test_claim_relation_is_bounded_atom() -> None:
    relation = market_claim_relation(
        MarketClaim(
            act=MarketCommunicationAct.EXPECT_MEETING,
            label_token="venue-abc",
        )
    )
    assert relation.subject == "mkt_v1"
    assert relation.predicate == "mkt_expect"
    parsed = parse_market_claim_relation(relation)
    assert parsed is not None
    assert parsed.label_token == "venue-abc"


def test_decorator_preserves_class_recipient_and_relations() -> None:
    existing = CommunicationRelation(
        subject="org_v1", predicate="org_admit", object="x"
    )
    utterance = origin_utterance(
        text="hello",
        speaker_id=OWNER_ENTITY,
        relations=(existing,),
    )
    command = Talk(recipient_id=RECIPIENT, utterance=utterance)
    prepared = ledger(
        venues=(
            venue(
                schedules=(schedule(),),
            ),
        )
    )
    updated = market_communicate_utterance(command, prepared)
    assert type(updated) is Talk
    assert updated.recipient_id == RECIPIENT
    relations = updated.utterance.content.relations
    assert relations[0] == existing
    assert relations[-1].subject == "mkt_v1"
    assert updated.utterance.content.text == "hello"


def test_decorator_noops_on_wait_and_disabled_ledger() -> None:
    command = Wait()
    assert market_communicate_utterance(command, None) is command
    assert market_communicate_utterance(command, ledger()) is command


def test_decorator_does_not_duplicate_a_market_relation() -> None:
    relation = market_claim_relation(
        MarketClaim(
            act=MarketCommunicationAct.ANNOUNCE_MEETING, label_token="venue-abc"
        )
    )
    utterance = origin_utterance(
        text="hello", speaker_id=OWNER_ENTITY, relations=(relation,)
    )
    command = Talk(recipient_id=RECIPIENT, utterance=utterance)
    assert market_communicate_utterance(command, ledger(venues=(venue(),))) == command


def test_decorator_respects_relation_cap() -> None:
    relations = tuple(
        CommunicationRelation(subject="s", predicate="p", object=str(index))
        for index in range(MARKET_FRAME_MAX_RELATIONS)
    )
    utterance = origin_utterance(
        text="hello", speaker_id=OWNER_ENTITY, relations=relations
    )
    command = Talk(recipient_id=RECIPIENT, utterance=utterance)
    assert market_communicate_utterance(command, ledger(venues=(venue(),))) == command


def test_record_claims_are_cited() -> None:
    prepared = ledger(
        venues=(
            venue(
                records=(record(anchor="record-1"),),
                expectation=MarketExpectation.NONE,
            ),
        )
    )
    utterance = origin_utterance(text="hello", speaker_id=OWNER_ENTITY)
    command = Talk(recipient_id=RECIPIENT, utterance=utterance)
    updated = market_communicate_utterance(command, prepared)
    assert isinstance(updated, Talk)
    assert updated.utterance.content.relations[-1].predicate == "mkt_record"
