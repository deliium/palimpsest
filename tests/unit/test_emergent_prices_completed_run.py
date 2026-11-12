"""Completed-run price analysis from runner ledgers and committed events."""

# mypy: ignore-errors


from __future__ import annotations

from types import SimpleNamespace

import pytest

from agents.cognition.emergent_prices import apply_emergent_price_update
from analysis.emergent_prices_contract import PriceCoverage
from experiments.emergent_prices_completed_run import (
    build_completed_run_emergent_prices_analysis,
)
from tests.unit.emergent_prices_analysis_helpers import completed
from tests.unit.emergent_prices_helpers import OWNER, observation, valuations
from world.values import ItemKind

pytestmark = pytest.mark.unit


def _ledger():
    return apply_emergent_price_update(
        owner_id=OWNER,
        tick=5,
        observations=(observation(source_tick=2),),
        observed_quotes=(),
        prior=None,
        valuations=valuations((ItemKind.WATER, ItemKind.FOOD, 1)),
        acceptance=None,
    )


def _events():
    return [completed(f"event-{index}", tick=index) for index in range(4)]


def test_owner_ledgers_project_to_inputs() -> None:
    result = SimpleNamespace(emergent_price_ledgers=(_ledger(),))
    analysis = build_completed_run_emergent_prices_analysis(
        result, committed_events=_events(), run_id="run-1"
    )
    assert analysis.expectations
    assert analysis.expectations[0].owner_token == OWNER.value
    assert analysis.distributions


def test_missing_ledgers_still_yields_objective_analysis() -> None:
    result = SimpleNamespace(emergent_price_ledgers=())
    analysis = build_completed_run_emergent_prices_analysis(
        result, committed_events=_events(), run_id="run-1"
    )
    assert analysis.distributions
    assert analysis.expectations == ()
    assert analysis.expectation_coverage is PriceCoverage.MISSING


def test_missing_events_raises() -> None:
    with pytest.raises(ValueError):
        build_completed_run_emergent_prices_analysis(
            SimpleNamespace(emergent_price_ledgers=()),
            committed_events=None,
            run_id="run-1",
        )


def test_membership_failure_is_contained() -> None:
    result = SimpleNamespace(
        emergent_price_ledgers=(),
        market_institution_ledgers=(object(),),
    )
    analysis = build_completed_run_emergent_prices_analysis(
        result, committed_events=_events(), run_id="run-1"
    )
    assert analysis.market_coverage is PriceCoverage.MISSING
    assert analysis.distributions
