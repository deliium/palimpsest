"""Bounded composition of the market-like institution analysis."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from analysis.market_institutions_analysis import (
    empty_market_institutions_analysis,
    harvest_market_institutions_analysis,
    market_institutions_analysis_digest,
)
from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketInstitutionsError,
)
from analysis.market_institutions_layers import project_market_layers
from analysis.market_institutions_policy import (
    MarketInstitutionsAnalysisPolicy,
)
from world.events import ExchangeCompleted
from world.identifiers import EntityId, EventId

pytestmark = pytest.mark.unit


def _event(
    token: str, *, tick: int, actor: str = "body-a", other: str = "body-b"
) -> SimpleNamespace:
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        details=ExchangeCompleted(
            actor_id=EntityId(actor),
            counterparty_id=EntityId(other),
            act="accept",
            give_item_ids=(EntityId("item-give"),),
            take_item_ids=(EntityId("item-take"),),
            give_item_kinds=("food",),
            take_item_kinds=("material",),
        ),
        occurrence=SimpleNamespace(origin_location_id=EntityId("loc-a")),
    )


def _events() -> tuple[object, ...]:
    rows = []
    for window in (0, 1, 2):
        rows.append(_event(f"evt-{window}-a", tick=window * 32))
        rows.append(
            _event(
                f"evt-{window}-b",
                tick=window * 32 + 1,
                actor="body-c",
                other="body-b",
            )
        )
    return tuple(rows)


def test_empty_analysis_is_missing() -> None:
    analysis = empty_market_institutions_analysis()
    assert analysis.coverage is MarketCoverage.MISSING
    assert analysis.venues == ()
    assert analysis.expectations == ()


def test_full_composition_has_rows_and_complete_coverage() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    assert analysis.exchange_count == 6
    assert analysis.venues
    assert analysis.gatherings
    assert analysis.participation
    assert analysis.markets
    assert analysis.lineage
    assert analysis.evidence_coverage is MarketCoverage.COMPLETE
    assert analysis.coverage is MarketCoverage.PARTIAL
    assert analysis.expectation_coverage is MarketCoverage.MISSING


def test_window_end_derivation_and_rejection() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    assert analysis.window_tick == 2 * 32
    with pytest.raises(MarketInstitutionsError):
        harvest_market_institutions_analysis(committed_events=_events(), window_end=1)
    extended = harvest_market_institutions_analysis(
        committed_events=_events(), window_end=4
    )
    assert extended.window_tick == 4 * 32


def test_owner_lanes_do_not_change_objective_rows() -> None:
    baseline = harvest_market_institutions_analysis(committed_events=_events())
    missing = harvest_market_institutions_analysis(
        committed_events=_events(), expectation_inputs=()
    )
    assert missing.venues == baseline.venues
    assert missing.expectation_coverage is MarketCoverage.MISSING


def test_digest_and_ordering_are_deterministic() -> None:
    first = harvest_market_institutions_analysis(committed_events=_events())
    second = harvest_market_institutions_analysis(committed_events=_events())
    assert first == second
    assert market_institutions_analysis_digest(first) == (
        market_institutions_analysis_digest(second)
    )


def test_layer_projection_is_separated() -> None:
    analysis = harvest_market_institutions_analysis(committed_events=_events())
    view = project_market_layers(analysis)
    assert view.objective == ()
    assert view.comparison == ()
    assert view.owner == ()
    assert view.analytical


def test_partial_policy_marks_partial() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_gathering_rows=1)
    analysis = harvest_market_institutions_analysis(
        committed_events=_events(), policy=policy
    )
    assert analysis.gatherings
    assert analysis.coverage is MarketCoverage.PARTIAL
