"""observed_acceptance joins the clamp and leaves the reference kind at 1."""

from __future__ import annotations

import pytest

from agents.cognition.subjective_value import appraise_reservation
from world.values import ItemKind


def test_acceptance_component_map_and_clamp() -> None:
    low = appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=2)
    mid = appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=3)
    high = appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=8)
    assert low.reservation == 1
    assert mid.reservation == 2
    assert high.reservation == 3
    assert high.components[-1].token == "observed_acceptance"
    clamped = appraise_reservation(
        item_kind=ItemKind.TOOL,
        held_count=1,
        others_visible_count=0,
        plan_names_kind=True,
        observed_acceptance=64,
    )
    assert clamped.reservation == 11


def test_missing_acceptance_omits_the_token() -> None:
    row = appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=None)
    assert row.reservation == 0
    assert all(component.token != "observed_acceptance" for component in row.components)


def test_reference_kind_ignores_acceptance() -> None:
    food = appraise_reservation(
        item_kind=ItemKind.FOOD, observed_acceptance=8, held_count=4
    )
    assert food.reservation == 1
    assert food.components == ()


def test_acceptance_rejects_bool_and_out_of_range() -> None:
    with pytest.raises(ValueError, match="observed_acceptance"):
        appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="observed_acceptance"):
        appraise_reservation(item_kind=ItemKind.GENERIC, observed_acceptance=65)
