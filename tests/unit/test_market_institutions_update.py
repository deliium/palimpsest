"""Inbound ``mkt_v1`` frames update owner beliefs conservatively."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.market_institutions import (
    MarketCadence,
    MarketExpectation,
    MarketRoleBasis,
    MarketRoleKind,
    MarketScheduleSource,
    apply_market_institution_update,
)
from agents.cognition.market_institutions_communication import (
    MarketClaim,
    MarketCommunicationAct,
    market_claim_relation,
)
from tests.unit.market_institutions_helpers import (
    OWNER,
    OWNER_ENTITY,
    PEER_ENTITY,
    A,
    ledger,
    observation,
    role,
    schedule,
    venue,
)
from world.communications import origin_utterance

pytestmark = pytest.mark.unit


def _communication(
    label: str,
    *,
    speaker: object = PEER_ENTITY,
    listener: object = OWNER_ENTITY,
    **claim_fields: object,
) -> SimpleNamespace:
    claim = MarketClaim(label_token=label, **claim_fields)  # type: ignore[arg-type]
    utterance = origin_utterance(
        text="market",
        speaker_id=speaker,  # type: ignore[arg-type]
        relations=(market_claim_relation(claim),),
    )
    return SimpleNamespace(
        speaker_id=speaker,
        listener_id=listener,
        utterance=utterance,
    )


def test_peer_expectation_and_schedule_are_adopted() -> None:
    prepared = venue(location=A)
    message = _communication(
        prepared.label_token,
        act=MarketCommunicationAct.EXPECT_MEETING,
        expectation=MarketExpectation.EXPECTED,
        cadence=MarketCadence.RECURRING_INTERVAL,
        interval_ticks=5,
        phase_tick=1,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    belief = updated.venues[0]
    assert belief.schedules
    assert belief.schedules[0].source is MarketScheduleSource.COMMUNICATED
    assert belief.schedules[0].confidence_milli == 500
    assert belief.expectation.level is MarketExpectation.EXPECTED


def test_unknown_label_adds_a_notice_and_changes_nothing() -> None:
    prepared = venue(location=A)
    message = _communication(
        "venue-unknown",
        act=MarketCommunicationAct.ANNOUNCE_MEETING,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    assert "market_venue_unresolved" in updated.notices
    assert updated.venues[0].schedules == ()


def test_peer_role_claim_stays_claimed_and_unrecognized() -> None:
    prepared = venue(location=A)
    message = _communication(
        prepared.label_token,
        act=MarketCommunicationAct.CLAIM_ROLE,
        role_kind=MarketRoleKind.BROKER,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    claim = updated.venues[0].roles[0]
    assert claim.actor_id == PEER_ENTITY
    assert claim.basis is MarketRoleBasis.CLAIMED
    assert claim.recognized is False


def test_role_recognition_resolves_against_offices() -> None:
    office_ref = "b" * 16
    prepared = venue(
        location=A,
        roles=(role(basis=MarketRoleBasis.OFFICE, office_ref=office_ref),),
    )
    offices = SimpleNamespace(concepts=(SimpleNamespace(role_signature=office_ref),))
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A),
        prior=ledger(venues=(prepared,)),
        offices=offices,
    )
    assert updated.venues[0].roles[0].recognized is True


def test_self_authored_frame_uses_higher_confidence() -> None:
    prepared = venue(location=A)
    message = _communication(
        prepared.label_token,
        speaker=OWNER_ENTITY,
        listener=PEER_ENTITY,
        act=MarketCommunicationAct.EXPECT_MEETING,
        expectation=MarketExpectation.EXPECTED,
        cadence=MarketCadence.RECURRING_INTERVAL,
        interval_ticks=5,
        phase_tick=1,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    assert updated.venues[0].schedules[0].source is MarketScheduleSource.SELF_AUTHORED
    assert updated.venues[0].schedules[0].confidence_milli == 1000


def test_peer_cannot_manufacture_a_strong_expectation() -> None:
    prepared = venue(location=A)
    message = _communication(
        prepared.label_token,
        act=MarketCommunicationAct.EXPECT_MEETING,
        expectation=MarketExpectation.STRONG,
        cadence=MarketCadence.RECURRING_INTERVAL,
        interval_ticks=5,
        phase_tick=1,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    assert updated.venues[0].expectation.level is MarketExpectation.EXPECTED


def test_unrelated_communication_is_ignored() -> None:
    prepared = venue(location=A, schedules=(schedule(),))
    utterance = origin_utterance(text="hello", speaker_id=PEER_ENTITY)
    message = SimpleNamespace(
        speaker_id=PEER_ENTITY,
        listener_id=OWNER_ENTITY,
        utterance=utterance,
    )
    updated = apply_market_institution_update(
        owner_id=OWNER,
        tick=5,
        observation=observation(tick=5, location=A, communications=(message,)),
        prior=ledger(venues=(prepared,)),
    )
    assert updated.venues[0].schedules == prepared.schedules
