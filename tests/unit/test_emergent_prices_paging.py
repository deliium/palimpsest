"""Purpose-bound paging over price snapshot rows."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.emergent_prices_analysis import harvest_emergent_prices_analysis
from analysis.emergent_prices_contract import (
    PriceCoverage,
    PriceQuoteDirection,
    PriceQuoteSource,
)
from analysis.emergent_prices_rows import PriceOwnerQuoteInput
from experiments.emergent_prices_publication import (
    compose_emergent_prices_snapshot,
)
from simulation import page_emergent_prices
from tests.unit.emergent_prices_analysis_helpers import completed, proposed

pytestmark = pytest.mark.unit

_SORT_KEYS = {
    "units": ("unit_token", "unit_source"),
    "expectations": ("window_index", "expectation_id"),
    "quotes": ("window_index", "venue_id", "quote_id"),
    "distributions": ("window_index", "distribution_id"),
    "markets": ("window_index", "market_token"),
    "relations": ("window_index", "relation_id"),
}


def _snapshot():
    analysis = harvest_emergent_prices_analysis(
        committed_events=[
            completed(f"event-{index}", tick=index) for index in range(4)
        ]
    )
    return compose_emergent_prices_snapshot(analysis, run_id="run-1")


def _multi_source_snapshot():
    events = [
        completed(f"event-a-{index}", tick=index, origin="loc-a")
        for index in range(4)
    ]
    events += [
        completed(f"event-b-{index}", tick=20 + index, origin="loc-b")
        for index in range(4)
    ]
    events += [
        proposed(
            f"quote-a-{index}",
            give_ids=("give-event-a-0-0",),
            take_ids=("take-event-a-0-0",),
            tick=10 + index,
            origin="loc-a",
        )
        for index in range(4)
    ]
    events += [
        proposed(
            f"quote-b-{index}",
            give_ids=("give-event-b-0-0",),
            take_ids=("take-event-b-0-0",),
            tick=30 + index,
            origin="loc-b",
        )
        for index in range(4)
    ]
    quote_inputs = tuple(
        PriceOwnerQuoteInput(
            owner_token="owner-1",
            venue_id="mkt-ven-" + "a" * 16,
            window_index=0,
            item_kind="food",
            unit_kind="water",
            direction=PriceQuoteDirection.GIVE_FOR_UNIT,
            ratio_milli=1_000 + index,
            confidence_milli=500,
            source=PriceQuoteSource.OBSERVED_OFFER,
            source_tick=index,
            first_tick=index,
            last_tick=index,
            coverage=PriceCoverage.COMPLETE,
        )
        for index in range(3)
    )
    analysis = harvest_emergent_prices_analysis(
        committed_events=events, quote_inputs=quote_inputs
    )
    return compose_emergent_prices_snapshot(analysis, run_id="run-1")


def test_each_purpose_pages_without_duplicates_or_omissions() -> None:
    snapshot = _multi_source_snapshot()
    for purpose, rows in (
        ("units", snapshot.units),
        ("expectations", snapshot.expectations),
        ("quotes", snapshot.quotes),
        ("distributions", snapshot.distributions),
        ("markets", snapshot.markets),
        ("relations", snapshot.relations),
    ):
        keys = _SORT_KEYS[purpose]
        expected = sorted(
            rows, key=lambda row: tuple(getattr(row, name) for name in keys)
        )
        seen = []
        after_key = None
        while True:
            page = page_emergent_prices(
                rows, purpose=purpose, limit=1, after_key=after_key
            )
            if not page:
                break
            seen.extend(page)
            after_key = tuple(getattr(page[-1], name) for name in keys)
            assert len(seen) <= len(expected)
        assert seen == expected, purpose


def test_multi_source_ids_are_unique() -> None:
    snapshot = _multi_source_snapshot()
    assert len({row.quote_id for row in snapshot.quotes}) == len(snapshot.quotes)
    assert len({row.distribution_id for row in snapshot.distributions}) == len(
        snapshot.distributions
    )
    assert len({row.relation_id for row in snapshot.relations}) == len(
        snapshot.relations
    )
    assert {row.sample_source for row in snapshot.distributions} == {
        "completed",
        "quoted",
    }


def test_limit_and_window_bounds_fail_closed() -> None:
    rows = _snapshot().distributions
    with pytest.raises(ValueError):
        page_emergent_prices(rows, purpose="distributions", limit=0)
    with pytest.raises(ValueError):
        page_emergent_prices(rows, purpose="distributions", limit=501)
    with pytest.raises(ValueError):
        page_emergent_prices(rows, purpose="distributions", window_index=512)
    with pytest.raises(ValueError):
        page_emergent_prices(rows, purpose="unknown")


def test_window_filter_and_cursor() -> None:
    rows = _snapshot().distributions
    key = (
        rows[0].window_index,
        rows[0].distribution_id,
    )
    after = page_emergent_prices(
        rows, purpose="distributions", after_key=key, window_index=0
    )
    assert all(row.window_index == 0 for row in after)
    assert all(
        (row.window_index, row.distribution_id) > key for row in after
    )
