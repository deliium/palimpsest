"""Owner-scoped emergent price ledger folding and caps."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from agents.cognition.emergent_prices import (
    EmergentPriceError,
    PriceExpectationLevel,
    PriceQuoteDirection,
    PriceQuoteSource,
    PriceUnitSource,
    apply_emergent_price_update,
    canonical_exchange_pair,
    empty_emergent_prices,
    price_belief_id,
    quote_direction_for,
    require_owner_emergent_prices,
    validate_emergent_price_caps,
)
from simulation.emergent_prices_export import price_owner_export
from tests.unit.emergent_prices_helpers import (
    OWNER,
    PEER,
    acceptance,
    observation,
    quote,
    valuations,
)
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _update(
    *, tick: int = 5, observations=(), quotes=(), prior=None, vals=None, acc=None
):
    return apply_emergent_price_update(
        owner_id=OWNER,
        tick=tick,
        observations=tuple(observations),
        observed_quotes=tuple(quotes),
        prior=prior,
        valuations=vals,
        acceptance=acc,
    )


def test_one_observation_is_weak_and_two_are_expected() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    one = _update(observations=(observation(),), vals=vals)
    assert len(one.rows) == 1
    assert one.rows[0].level is PriceExpectationLevel.WEAK
    two = _update(
        observations=(observation(source_tick=1), observation(source_tick=2)),
        vals=vals,
    )
    assert len(two.rows) == 1
    assert two.rows[0].level is PriceExpectationLevel.EXPECTED
    assert 0 <= two.rows[0].confidence_milli <= 1_000


def test_four_agreeing_observations_are_strong() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    ledger = _update(
        observations=tuple(
            observation(source_tick=tick) for tick in range(1, 5)
        ),
        vals=vals,
    )
    assert ledger.rows[0].confidence_milli >= 750
    assert ledger.rows[0].level is PriceExpectationLevel.STRONG


def test_repeated_identical_fold_is_byte_identical() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    first = _update(observations=(observation(),), vals=vals)
    again = _update(observations=(observation(),), prior=first, vals=vals)
    assert again == first
    third = _update(prior=again, vals=vals)
    assert third == first


def test_valuation_only_row_uses_owner_reference() -> None:
    vals = valuations(
        (ItemKind.FOOD, ItemKind.FOOD, 1),
        (ItemKind.WATER, ItemKind.FOOD, 2),
    )
    ledger = _update(
        observations=(
            observation(
                item_kind=ItemKind.WATER, unit_kind=ItemKind.FOOD, ratio=None
            ),
        ),
        vals=vals,
    )
    row = next(row for row in ledger.rows if row.item_kind is ItemKind.WATER)
    assert row.unit_source is PriceUnitSource.OWNER_REFERENCE
    assert row.unit_kind is ItemKind.FOOD
    assert row.expected_ratio_milli == 2_000
    assert "price_evidence_unpaired" in ledger.notices


def test_acceptance_creates_observed_medium_unit() -> None:
    ledger = _update(
        observations=(observation(),),
        acc=acceptance((ItemKind.WATER, 2)),
    )
    row = next(row for row in ledger.rows if row.unit_kind is ItemKind.WATER)
    assert row.unit_source is PriceUnitSource.OBSERVED_MEDIUM


def test_low_confidence_quote_never_changes_expectation() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    base = _update(observations=(observation(),), vals=vals)
    with_low = _update(
        observations=(observation(),),
        quotes=(quote(ratio=9_000, confidence=100),),
        vals=vals,
    )
    assert with_low.rows[0].expected_ratio_milli == base.rows[0].expected_ratio_milli
    assert with_low.rows[0].confidence_milli == base.rows[0].confidence_milli


def test_observed_quote_uses_neutral_confidence_and_pairs_only_homogeneous() -> None:
    pair = canonical_exchange_pair(
        (ItemKind.FOOD,), (ItemKind.WATER,)
    )
    assert pair == (ItemKind.FOOD, ItemKind.WATER)
    assert canonical_exchange_pair(
        (ItemKind.FOOD, ItemKind.WATER), (ItemKind.TOOL,)
    ) is None
    assert canonical_exchange_pair((ItemKind.FOOD,), (ItemKind.FOOD,)) is None
    assert (
        quote_direction_for(
            item_kind=ItemKind.FOOD,
            unit_kind=ItemKind.WATER,
            give_kinds=(ItemKind.FOOD,),
        )
        is PriceQuoteDirection.GIVE_FOR_UNIT
    )
    ledger = _update(
        observations=(observation(),),
        quotes=(quote(confidence=500, source=PriceQuoteSource.OBSERVED_OFFER),),
    )
    assert ledger.rows[0].quote_count == 1


def test_duplicate_quote_folds_once() -> None:
    one = quote(source=PriceQuoteSource.COMMUNICATED)
    ledger = _update(observations=(observation(),), quotes=(one, one))
    assert ledger.rows[0].quote_count == 1


def test_stale_valuation_adds_exactly_one_notice() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1), tick=1)
    ledger = _update(tick=100, observations=(observation(),), vals=vals)
    assert ledger.notices.count("price_valuation_stale") == 1


def test_observation_cap_truncates_deterministically() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    observations = tuple(
        observation(source_tick=tick) for tick in range(1, 40)
    )
    ledger = _update(observations=observations, vals=vals)
    row = ledger.rows[0]
    assert len(row.observations) == 32
    assert "price_ledger_truncated" in ledger.notices
    assert row.observations[-1].source_tick == 39


def test_foreign_owner_and_cross_owner_export_are_rejected() -> None:
    other = empty_emergent_prices(PEER)
    with pytest.raises(EmergentPriceError):
        require_owner_emergent_prices(other, OWNER)
    with pytest.raises(EmergentPriceError):
        price_owner_export([other], allowed_owner_ids=(OWNER,))
    with pytest.raises(TypeError):
        require_owner_emergent_prices(object(), OWNER)


def test_caps_and_row_ids_are_valid() -> None:
    vals = valuations(
        (ItemKind.FOOD, ItemKind.FOOD, 1),
        (ItemKind.WATER, ItemKind.FOOD, 2),
        (ItemKind.MATERIAL, ItemKind.FOOD, 3),
    )
    ledger = _update(
        observations=(
            observation(item_kind=ItemKind.FOOD, unit_kind=ItemKind.WATER),
            observation(
                item_kind=ItemKind.MATERIAL, unit_kind=ItemKind.FOOD,
                source_tick=2,
            ),
        ),
        vals=vals,
    )
    validate_emergent_price_caps(ledger)
    assert tuple(
        (row.item_kind.value, row.unit_kind.value if row.unit_kind else "none")
        for row in ledger.rows
    ) == tuple(
        sorted(
            
                (row.item_kind.value, row.unit_kind.value if row.unit_kind else "none")
                for row in ledger.rows
            
        )
    )
    for row in ledger.rows:
        assert row.row_id == price_belief_id(
            OWNER,
            row.item_kind,
            "none" if row.unit_kind is None else row.unit_kind.value,
        )


def test_valuation_below_reference_never_invents_a_unit() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 2))
    ledger = _update(observations=(observation(),), vals=vals)
    row = ledger.rows[0]
    assert row.unit_kind is ItemKind.WATER
    assert row.valuation_reservation == 0


def test_owner_id_is_never_exported_as_an_agent_id() -> None:
    vals = valuations((ItemKind.WATER, ItemKind.FOOD, 1))
    ledger = _update(observations=(observation(),), vals=vals)
    rows = price_owner_export([ledger])
    assert rows
    for row in rows:
        assert type(row.owner_token) is str
        assert "AgentId" not in type(row).__name__


def test_foreign_prior_owner_is_rejected() -> None:
    with pytest.raises(EmergentPriceError):
        apply_emergent_price_update(
            owner_id=OWNER,
            tick=1,
            prior=empty_emergent_prices(PEER),
            valuations=None,
            acceptance=None,
        )
