"""Shuffled inputs produce identical analysis bytes and digest."""

# mypy: ignore-errors


from __future__ import annotations

import random

import pytest

from analysis.emergent_prices_analysis import (
    emergent_prices_analysis_digest,
    harvest_emergent_prices_analysis,
)
from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceUnitSource,
)
from analysis.emergent_prices_rows import PriceOwnerExpectationInput
from tests.unit.emergent_prices_analysis_helpers import completed

pytestmark = pytest.mark.unit


def _inputs():
    events = [
        completed(f"event-{index}", tick=index, origin="loc-a")
        for index in range(4)
    ]
    expectations = [
        PriceOwnerExpectationInput(
            owner_token=f"owner-{index}",
            window_index=0,
            item_kind="food",
            unit_kind="water",
            unit_source=PriceUnitSource.EXCHANGE_COUNTERPART,
            expected_ratio_milli=1_000,
            confidence_milli=600,
            level="expected",
            valuation_reservation=1,
            observation_count=4,
            quote_count=0,
            first_tick=0,
            last_tick=3,
            coverage=PriceCoverage.COMPLETE,
        )
        for index in range(2)
    ]
    return events, expectations


def test_shuffled_inputs_are_digest_identical() -> None:
    events, expectations = _inputs()
    first = harvest_emergent_prices_analysis(
        committed_events=events, expectation_inputs=expectations
    )
    shuffled_events = list(events)
    shuffled_expectations = list(expectations)
    random.Random(7).shuffle(shuffled_events)
    random.Random(9).shuffle(shuffled_expectations)
    second = harvest_emergent_prices_analysis(
        committed_events=shuffled_events,
        expectation_inputs=shuffled_expectations,
    )
    assert first == second
    assert emergent_prices_analysis_digest(first) == (
        emergent_prices_analysis_digest(second)
    )
