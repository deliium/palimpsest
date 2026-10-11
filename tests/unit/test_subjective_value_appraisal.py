"""Alice values one tool at 8 food and Bob values it at 3."""

from __future__ import annotations

from agents.cognition.scarcity_beliefs import empty_scarcity_beliefs
from agents.cognition.subjective_value import (
    appraise_reservation,
    bundle_acceptable,
    bundle_concession,
)
from agents.models import AgentId
from world.values import ItemKind


def test_alice_and_bob_disagree_about_one_tool() -> None:
    alice = appraise_reservation(
        item_kind=ItemKind.TOOL,
        held_count=1,
        others_visible_count=0,
        plan_names_kind=True,
    )
    bob = appraise_reservation(
        item_kind=ItemKind.TOOL,
        held_count=0,
        others_visible_count=1,
        plan_names_kind=False,
        expected_future_scarcity=False,
    )
    assert alice.reservation == 8
    assert bob.reservation == 3
    assert alice.reference_kind is ItemKind.FOOD
    food = appraise_reservation(
        item_kind=ItemKind.FOOD, held_count=8, others_visible_count=0
    )
    assert food.reservation == 1
    assert not bundle_acceptable(received=3, given=8, concession=bundle_concession())
    assert not bundle_acceptable(received=3, given=8, concession=0)


def test_scarcity_missing_is_not_zero_stock() -> None:
    missing = appraise_reservation(
        item_kind=ItemKind.TOOL, others_visible_count=None, plan_names_kind=False
    )
    zero = appraise_reservation(
        item_kind=ItemKind.TOOL, others_visible_count=0, plan_names_kind=False
    )
    one = appraise_reservation(
        item_kind=ItemKind.TOOL, others_visible_count=1, plan_names_kind=False
    )
    assert missing.reservation == 0
    assert zero.reservation == 4
    assert one.reservation == 3


def test_optional_modes_add_nothing_when_off() -> None:
    row = appraise_reservation(
        item_kind=ItemKind.FOOD,
        hunger=0,
        thirst=0,
        risk_active=False,
        expected_future_scarcity=False,
    )
    assert row.reservation == 1
    assert bundle_concession(debt=0, affection=0, obligation=False) == 0
    child = empty_scarcity_beliefs(AgentId("child-1"))
    assert child.rows == ()
