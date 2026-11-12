"""Bounded ``prc_v1`` frames round-trip and stay testimony-only."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.emergent_prices import (
    PriceExpectationLevel,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
    apply_emergent_price_update,
)
from agents.cognition.emergent_prices_communication import (
    PRICE_FRAME_MAX_RELATIONS,
    PriceClaim,
    PriceCommunicationAct,
    encode_price_claim,
    parse_price_claim,
    parse_price_claim_relation,
    price_claim_relation,
    price_communicate_utterance,
)
from tests.unit.emergent_prices_helpers import (
    OWNER,
    OWNER_ENTITY,
    observation,
    valuations,
)
from world.actions import Give, NegotiateExchange, Talk, Tell, Wait
from world.communications import CommunicationRelation, origin_utterance
from world.identifiers import EntityId
from world.values import ItemKind

pytestmark = pytest.mark.unit

RECIPIENT = EntityId("body-2")


def _ledger(*, confidence_floor_only: bool = False):
    return apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=(
            observation(source_tick=1),
            observation(source_tick=2),
            observation(source_tick=3),
            observation(source_tick=4),
        ),
        observed_quotes=(),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )


@pytest.mark.parametrize(
    "act",
    (
        PriceCommunicationAct.QUOTE_OFFER,
        PriceCommunicationAct.QUOTE_COUNTER,
        PriceCommunicationAct.WITHDRAW_QUOTE,
        PriceCommunicationAct.CITE_EXPECTATION,
    ),
)
def test_every_act_round_trips(act: PriceCommunicationAct) -> None:
    claim = PriceClaim(
        act=act,
        item_kind_token="food",
        unit_token="water",
        unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
        direction=PriceQuoteDirection.GIVE_FOR_UNIT,
        ratio_milli=1_500,
        confidence_milli=600,
        anchor="record-1",
    )
    assert parse_price_claim(encode_price_claim(claim)) == claim


def test_frame_has_exactly_nine_parts() -> None:
    claim = PriceClaim(
        act=PriceCommunicationAct.QUOTE_OFFER,
        item_kind_token="food",
        unit_token="water",
        unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
        direction=PriceQuoteDirection.GIVE_FOR_UNIT,
        ratio_milli=1_000,
        confidence_milli=500,
    )
    assert len(encode_price_claim(claim).split(":")) == 9


@pytest.mark.parametrize(
    "text",
    (
        "prc_v1:prc_quote:food",
        "other:prc_quote:food:water:exchange_counterpart:give_for_unit:1:1:none",
        "prc_v1:prc_bad:food:water:exchange_counterpart:give_for_unit:1:1:none",
        "prc_v1:prc_quote:food:water:bad:give_for_unit:1:1:none",
        "prc_v1:prc_quote:food:water:exchange_counterpart:bad:1:1:none",
        "prc_v1:prc_quote:food:water:exchange_counterpart:give_for_unit:x:1:none",
        "prc_v1:prc_quote:food:none:exchange_counterpart:give_for_unit:1:1:none",
        "prc_v1:prc_quote:food water:water:exchange_counterpart:give_for_unit:1:1:none",
    ),
)
def test_malformed_frames_fail_closed(text: str) -> None:
    with pytest.raises(ValueError):
        parse_price_claim(text)


def test_oversize_frame_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_price_claim("prc_v1" + ":" * 300)


def test_unrelated_relation_returns_none() -> None:
    relation = CommunicationRelation(
        subject="mkt_v1", predicate="mkt_meeting", object="x"
    )
    assert parse_price_claim_relation(relation) is None


def test_claim_relation_is_bounded_atom() -> None:
    relation = price_claim_relation(
        PriceClaim(
            act=PriceCommunicationAct.QUOTE_OFFER,
            item_kind_token="food",
            unit_token="water",
            unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
            direction=PriceQuoteDirection.GIVE_FOR_UNIT,
            ratio_milli=1_000,
            confidence_milli=500,
        )
    )
    assert relation.subject == "prc_v1"
    assert relation.predicate == "prc_quote"
    assert parse_price_claim_relation(relation) is not None


def test_utterance_gains_exactly_one_relation() -> None:
    existing = CommunicationRelation(
        subject="org_v1", predicate="org_admit", object="x"
    )
    utterance = origin_utterance(
        text="hello", speaker_id=OWNER_ENTITY, relations=(existing,)
    )
    command = Talk(recipient_id=RECIPIENT, utterance=utterance)
    updated = price_communicate_utterance(
        command,
        owner_id=OWNER,
        ledger=_ledger(),
        counterparty_id=RECIPIENT,
    )
    assert type(updated) is Talk
    assert updated.recipient_id == RECIPIENT
    relations = updated.utterance.content.relations
    assert relations[0] == existing
    assert relations[-1].subject == "prc_v1"
    assert len([item for item in relations if item.subject == "prc_v1"]) == 1
    assert updated.utterance.content.text == "hello"


def test_only_talk_and_tell_are_expressible() -> None:
    ledger = _ledger()
    utterance = origin_utterance(text="hello", speaker_id=OWNER_ENTITY)
    tell = Tell(recipient_id=RECIPIENT, utterance=utterance)
    assert type(
        price_communicate_utterance(
            tell,
            owner_id=OWNER,
            ledger=ledger,
            counterparty_id=RECIPIENT,
        )
    ) is Tell
    for command in (
        Wait(),
        Give(recipient_id=RECIPIENT, item_id=EntityId("item-1")),
        NegotiateExchange(
            counterparty_id=RECIPIENT,
            act="offer",
            give_item_ids=(EntityId("item-1"),),
            take_item_ids=(EntityId("item-2"),),
        ),
    ):
        assert (
            price_communicate_utterance(
                command,
                owner_id=OWNER,
                ledger=ledger,
                counterparty_id=RECIPIENT,
            )
            is command
        )


def test_disabled_or_empty_ledger_is_a_noop() -> None:
    command = Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    assert (
        price_communicate_utterance(
            command, owner_id=OWNER, ledger=None, counterparty_id=RECIPIENT
        )
        is command
    )


def test_low_confidence_ledger_attaches_nothing() -> None:
    from agents.cognition.emergent_prices import empty_emergent_prices

    command = Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(text="hello", speaker_id=OWNER_ENTITY),
    )
    assert (
        price_communicate_utterance(
            command,
            owner_id=OWNER,
            ledger=empty_emergent_prices(OWNER),
            counterparty_id=RECIPIENT,
        )
        is command
    )


def test_relation_cap_is_respected() -> None:
    relations = tuple(
        CommunicationRelation(subject="s", predicate="p", object=str(index))
        for index in range(PRICE_FRAME_MAX_RELATIONS)
    )
    command = Talk(
        recipient_id=RECIPIENT,
        utterance=origin_utterance(
            text="hello", speaker_id=OWNER_ENTITY, relations=relations
        ),
    )
    assert (
        price_communicate_utterance(
            command,
            owner_id=OWNER,
            ledger=_ledger(),
            counterparty_id=RECIPIENT,
        )
        is command
    )


def test_peer_quote_never_mints_a_strong_expectation() -> None:
    from tests.unit.emergent_prices_helpers import quote

    ledger = apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=(),
        observed_quotes=(
            quote(
                source=PriceQuoteSource.COMMUNICATED,
                confidence=1_000,
                ratio=9_000,
            ),
        ),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )
    assert ledger.rows
    assert all(
        row.level is not PriceExpectationLevel.STRONG for row in ledger.rows
    )
    assert all(row.level is PriceExpectationLevel.NONE for row in ledger.rows)

    with_observations = apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=tuple(
            observation(source_tick=tick) for tick in range(1, 5)
        ),
        observed_quotes=(
            quote(
                source=PriceQuoteSource.COMMUNICATED,
                confidence=1_000,
                ratio=1_000,
            ),
        ),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )
    assert all(
        row.level is not PriceExpectationLevel.STRONG
        for row in with_observations.rows
    )
