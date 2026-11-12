"""Token-only owner export for detached price analysis."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.emergent_prices import apply_emergent_price_update
from simulation.emergent_prices_export import (
    EmergentPriceOwnerQuoteRow,
    EmergentPriceOwnerRow,
    price_owner_export,
)
from tests.unit.emergent_prices_helpers import OWNER, observation, quote, valuations
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _ledger():
    return apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=(observation(source_tick=2),),
        observed_quotes=(quote(source_tick=3),),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )


def test_export_is_token_only_and_stable() -> None:
    rows = price_owner_export([_ledger()])
    assert rows == price_owner_export([_ledger()])
    assert any(type(row) is EmergentPriceOwnerRow for row in rows)
    assert any(type(row) is EmergentPriceOwnerQuoteRow for row in rows)
    expectation = next(row for row in rows if type(row) is EmergentPriceOwnerRow)
    assert expectation.owner_token == OWNER.value
    assert expectation.item_kind_token == ItemKind.FOOD.value
    assert expectation.unit_token == ItemKind.WATER.value
    assert expectation.window_index == expectation.last_tick // 32
    quote_row = next(row for row in rows if type(row) is EmergentPriceOwnerQuoteRow)
    assert quote_row.direction in {"give_for_unit", "unit_for_give"}
    assert quote_row.source_tick == 3


def test_export_contains_no_private_identifiers() -> None:
    rows = price_owner_export([_ledger()])
    names = {field for row in rows for field in type(row).__dataclass_fields__}
    assert "counterparty_id" not in names
    assert "item_id" not in names
    assert "agent_id" not in names
    assert "digest" not in names
    assert "valuation_components" not in names


def test_export_rejects_non_ledgers() -> None:
    from agents.cognition.emergent_prices import EmergentPriceError

    with pytest.raises(EmergentPriceError):
        price_owner_export([object()])
