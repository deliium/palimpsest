# mypy: ignore-errors

"""Pure ecological stock-damage transition invariants."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from world._ecological_resources import (
    EcologicalInvariantError,
    EcologicalStockRow,
    advance_stock_damage,
    effective_capacity_tenths,
)
from world.events import EcologicalResourceChanged
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

_RESOURCE = EntityId("res-food")


def _row(*, floor: int = 10, damage: int = 0) -> EcologicalStockRow:
    return EcologicalStockRow(
        resource_id=_RESOURCE,
        minimum_capacity_tenths=floor,
        damage_tenths=damage,
    )


@pytest.mark.parametrize(
    (
        "damage",
        "start",
        "post",
        "allowance",
        "recovery",
        "expected_damage",
    ),
    [
        # Full stock 4.0, floor 1.0, allowance 0, recovery 0.5, withdraw 2.0
        (0, 40, 20, 0, 5, 20),
        # Rest tick after damage 20 recovers 5 → 15 (capacity 2.5)
        (20, 20, 20, 0, 5, 15),
        # Withdrawal within allowance preserves damage
        (10, 30, 25, 10, 5, 10),
        # Withdrawal above allowance adds excess only
        (10, 30, 15, 5, 5, 20),
        # Saturation at floor (base 40, floor 10 → span 30)
        (25, 15, 5, 0, 5, 30),
        # Recovery saturates at zero
        (3, 37, 37, 0, 5, 0),
        # Recovery without stock growth (stock stays below new capacity)
        (20, 10, 10, 0, 5, 15),
        # Repeated pressure from prior damage
        (10, 25, 15, 0, 5, 20),
    ],
)
def test_advance_table_cases(
    damage: int,
    start: int,
    post: int,
    allowance: int,
    recovery: int,
    expected_damage: int,
) -> None:
    row = _row(floor=10, damage=damage)
    next_row = advance_stock_damage(
        row,
        baseline_tenths=40,
        start_quantity_tenths=start,
        post_command_quantity_tenths=post,
        allowance_tenths=allowance,
        recovery_tenths=recovery,
    )
    assert next_row.damage_tenths == expected_damage
    assert next_row.resource_id is _RESOURCE
    assert next_row.minimum_capacity_tenths == 10
    capacity = effective_capacity_tenths(next_row, baseline_tenths=40)
    assert post <= capacity
    assert capacity == 40 - expected_damage


def test_acceptance_withdrawal_then_rest() -> None:
    """base 4.0, floor 1.0, allowance 0, recovery 0.5: withdraw 2.0 then rest."""
    row = _row(floor=10, damage=0)
    after_withdraw = advance_stock_damage(
        row,
        baseline_tenths=40,
        start_quantity_tenths=40,
        post_command_quantity_tenths=20,
        allowance_tenths=0,
        recovery_tenths=5,
    )
    assert after_withdraw.damage_tenths == 20
    assert effective_capacity_tenths(after_withdraw, baseline_tenths=40) == 20
    after_rest = advance_stock_damage(
        after_withdraw,
        baseline_tenths=40,
        start_quantity_tenths=20,
        post_command_quantity_tenths=20,
        allowance_tenths=0,
        recovery_tenths=5,
    )
    assert after_rest.damage_tenths == 15
    assert effective_capacity_tenths(after_rest, baseline_tenths=40) == 25


def test_rejects_subunit_and_noop_event() -> None:
    with pytest.raises(EcologicalInvariantError):
        advance_stock_damage(
            _row(),
            baseline_tenths=40,
            start_quantity_tenths=40,
            post_command_quantity_tenths=20,
            allowance_tenths=0,
            recovery_tenths=True,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError, match="ecological_resource_changed_no_change"):
        EcologicalResourceChanged(
            resource_id=_RESOURCE,
            before_damage_tenths=5,
            after_damage_tenths=5,
        )
    with pytest.raises(ValueError, match="ecological_resource_changed_before_invalid"):
        EcologicalResourceChanged(
            resource_id=_RESOURCE,
            before_damage_tenths=True,  # type: ignore[arg-type]
            after_damage_tenths=1,
        )


@settings(max_examples=80, deadline=None)
@given(
    data=st.data(),
)
def test_invariants_hypothesis(data: st.DataObject) -> None:
    base = data.draw(st.integers(min_value=2, max_value=100))
    floor = data.draw(st.integers(min_value=1, max_value=base - 1))
    span = base - floor
    damage = data.draw(st.integers(min_value=0, max_value=span))
    capacity = base - damage
    start = data.draw(st.integers(min_value=0, max_value=capacity))
    post = data.draw(st.integers(min_value=0, max_value=start))
    allowance = data.draw(st.integers(min_value=0, max_value=10000))
    recovery = data.draw(st.integers(min_value=1, max_value=10000))
    row = _row(floor=floor, damage=damage)
    next_row = advance_stock_damage(
        row,
        baseline_tenths=base,
        start_quantity_tenths=start,
        post_command_quantity_tenths=post,
        allowance_tenths=allowance,
        recovery_tenths=recovery,
    )
    next_capacity = effective_capacity_tenths(next_row, baseline_tenths=base)
    assert 0 <= next_row.damage_tenths <= span
    assert floor <= next_capacity <= base
    assert 0 <= post <= next_capacity <= base
    # Deterministic equality
    again = advance_stock_damage(
        row,
        baseline_tenths=base,
        start_quantity_tenths=start,
        post_command_quantity_tenths=post,
        allowance_tenths=allowance,
        recovery_tenths=recovery,
    )
    assert again == next_row
    # No stock creation in the pure step (post unchanged by function)
    assert post <= start
    # Monotonic damage with increasing withdrawal at fixed prior damage
    if start > 0:
        lower_post = data.draw(st.integers(min_value=0, max_value=post))
        heavier = advance_stock_damage(
            row,
            baseline_tenths=base,
            start_quantity_tenths=start,
            post_command_quantity_tenths=lower_post,
            allowance_tenths=allowance,
            recovery_tenths=recovery,
        )
        if start - lower_post > 0 and start - post > 0:
            assert heavier.damage_tenths >= next_row.damage_tenths
        if start - post == 0 and start - lower_post == 0:
            assert heavier.damage_tenths == next_row.damage_tenths
