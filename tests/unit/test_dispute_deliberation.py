"""V4-07 deliberation hooks stay bounded and command-free."""

from __future__ import annotations

from dataclasses import replace

import pytest

from agents.cognition import (
    dispute_direction_preference,
    dispute_response_penalties,
    empty_dispute_ledger,
)
from tests.unit.test_dispute_reasoning import OWNER, _ledger
from world._rules import COMMAND_RULE_MATRIX

pytestmark = pytest.mark.unit


def test_open_claim_produces_bounded_direction_hint() -> None:
    hint = dispute_direction_preference(_ledger(), owner_id=OWNER, tick=3)
    assert hint
    assert set(hint) <= {"ask", "communicate", "tell"}
    assert all(type(value) is float for value in hint.values())
    assert all(0.0 < value <= 0.25 for value in hint.values())
    assert (
        dispute_direction_preference(
            empty_dispute_ledger(OWNER), owner_id=OWNER, tick=200
        )
        == {}
    )


def test_accepting_unknown_resolution_is_penalized() -> None:
    penalties = dispute_response_penalties(
        _ledger(), owner_id=OWNER, resolution_ref="a" * 64, tick=3
    )
    assert penalties == {"accept": -0.2}
    assert all(-0.25 <= value <= 0.0 for value in penalties.values())
    assert (
        dispute_response_penalties(
            _ledger(), owner_id=OWNER, resolution_ref=None, tick=3
        )
        == {}
    )


def test_hooks_do_not_construct_commands() -> None:
    for output in (
        dispute_direction_preference(_ledger(), owner_id=OWNER, tick=3),
        dispute_response_penalties(
            _ledger(), owner_id=OWNER, resolution_ref="a" * 64, tick=3
        ),
    ):
        assert isinstance(output, dict)
        assert not any(
            isinstance(value, type) and value.__name__.endswith("Command")
            for value in output.values()
        )
    assert not any("Dispute" in command.__name__ for command in COMMAND_RULE_MATRIX)


def test_hooks_do_not_change_world_state() -> None:
    ledger = _ledger()
    before = replace(ledger)
    dispute_direction_preference(ledger, owner_id=OWNER, tick=3)
    dispute_response_penalties(ledger, owner_id=OWNER, resolution_ref="a" * 64, tick=3)
    assert ledger == before
    assert not hasattr(ledger, "world_state")
    assert not hasattr(ledger, "events")
