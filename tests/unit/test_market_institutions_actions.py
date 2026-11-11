"""One-hop attendance replaces only ``Wait`` with one observed ``Move``."""

from __future__ import annotations

import pytest

from agents.cognition.market_institutions import (
    MarketInstitutionLedger,
    MarketVenueStatus,
)
from agents.cognition.market_institutions_actions import market_attendance_command
from tests.unit.market_institutions_helpers import (
    OWNER,
    OWNER_ENTITY,
    PEER,
    A,
    B,
    ledger,
    observation,
    schedule,
    venue,
)
from world.actions import Move, Talk, Wait
from world.communications import origin_utterance
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _ledger(
    *, status: MarketVenueStatus = MarketVenueStatus.EXPECTED
) -> MarketInstitutionLedger:
    return ledger(
        venues=(
            venue(
                location=B,
                status=status,
                schedules=(schedule(interval_ticks=5, phase_tick=3),),
            ),
        )
    )


def test_wait_is_replaced_by_one_observed_move() -> None:
    command = Wait()
    observation_value = observation(tick=3, location=A, exits=(B,))
    updated = market_attendance_command(
        command,
        owner_id=OWNER,
        tick=3,
        observation=observation_value,
        ledger=_ledger(),
    )
    assert updated is not command
    assert isinstance(updated, Move)
    assert updated.destination_id == B


def test_no_observed_exit_returns_the_same_wait() -> None:
    command = Wait()
    updated = market_attendance_command(
        command,
        owner_id=OWNER,
        tick=3,
        observation=observation(tick=3, location=A, exits=()),
        ledger=_ledger(),
    )
    assert updated is command


def test_only_wait_is_replaceable() -> None:
    utterance = origin_utterance(text="hello", speaker_id=OWNER_ENTITY)
    command = Talk(recipient_id=EntityId("body-2"), utterance=utterance)
    updated = market_attendance_command(
        command,
        owner_id=OWNER,
        tick=3,
        observation=observation(tick=3, location=A, exits=(B,)),
        ledger=_ledger(),
    )
    assert updated is command


def test_status_and_schedule_gate_attendance() -> None:
    observation_value = observation(tick=3, location=A, exits=(B,))
    dormant = market_attendance_command(
        Wait(),
        owner_id=OWNER,
        tick=3,
        observation=observation_value,
        ledger=_ledger(status=MarketVenueStatus.DORMANT),
    )
    assert type(dormant) is Wait
    inactive = market_attendance_command(
        Wait(),
        owner_id=OWNER,
        tick=4,
        observation=observation_value,
        ledger=_ledger(),
    )
    assert type(inactive) is Wait


def test_owner_mismatch_returns_the_same_command() -> None:
    command = Wait()
    updated = market_attendance_command(
        command,
        owner_id=PEER,
        tick=3,
        observation=observation(tick=3, location=A, exits=(B,)),
        ledger=_ledger(),
    )
    assert updated is command


def test_helper_does_not_mutate_the_ledger() -> None:
    prepared = _ledger()
    before = tuple(prepared.venues)
    market_attendance_command(
        Wait(),
        owner_id=OWNER,
        tick=3,
        observation=observation(tick=3, location=A, exits=(B,)),
        ledger=prepared,
    )
    assert tuple(prepared.venues) == before
