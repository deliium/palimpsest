# mypy: ignore-errors
"""Bounded trade-network analysis harvest composition."""

from __future__ import annotations

import random
from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_analysis import (
    empty_trade_networks_analysis,
    harvest_trade_networks_analysis,
)
from analysis.trade_networks_contract import TradeCoverage
from analysis.trade_networks_policy import default_trade_networks_analysis_policy
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId

POLICY = default_trade_networks_analysis_policy()
SOC_A = "msoc-aaaaaaaaaaaaaaaa"
SOC_B = "msoc-bbbbbbbbbbbbbbbb"


def _event(token: str, details: object, *, tick: int = 0, origin: str = "loc-a"):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(origin_location_id=EntityId(origin)),
    )


def _pair(
    ordinal: int,
    *,
    tick: int,
    origin: str = "loc-a",
    destination: str = "loc-b",
    recipient: str = "body-b",
):
    return (
        _event(
            f"evt-c-{ordinal}",
            ItemCrafted(
                recipe_id=RecipeId("cook_food"),
                created_item_id=EntityId(f"item-{ordinal}"),
                resulting_holder_id=EntityId("body-a"),
                duration_ticks=1,
            ),
            tick=tick,
            origin=origin,
        ),
        _event(
            f"evt-g-{ordinal}",
            Given(
                recipient_id=EntityId(recipient),
                item_id=EntityId(f"item-{ordinal}"),
            ),
            tick=tick + 1,
            origin=destination,
        ),
    )


def _harvest(events, **kwargs):
    return harvest_trade_networks_analysis(
        events=tuple(events),
        policy=kwargs.pop("policy", POLICY),
        recipe_item_kinds=kwargs.pop("recipe_item_kinds", {"cook_food": "food"}),
        **kwargs,
    )


def test_empty_harvest_is_missing_and_bounded() -> None:
    analysis = empty_trade_networks_analysis()
    assert analysis.coverage is TradeCoverage.MISSING
    assert analysis.evidence_coverage is TradeCoverage.MISSING
    assert analysis.cross_society_coverage is TradeCoverage.MISSING
    assert analysis.lineage_coverage is TradeCoverage.MISSING
    assert analysis.transfer_count == 0
    assert analysis.corridor_count == 0
    assert analysis.network_count == 0
    assert analysis.window_tick == 0


def test_harvest_combines_evidence_detection_and_lineage() -> None:
    analysis = _harvest((*_pair(0, tick=0), *_pair(1, tick=32)))
    assert analysis.transfer_count == 2
    assert analysis.corridor_count == 2
    assert analysis.network_count == 2
    assert analysis.evidence_coverage is TradeCoverage.COMPLETE
    assert analysis.lineage_coverage is TradeCoverage.COMPLETE
    assert analysis.cross_society_coverage is TradeCoverage.MISSING
    assert [row.relation for row in analysis.lineage] == ["continued"]
    assert analysis.lineage[0].sustained is True
    assert analysis.coverage is TradeCoverage.PARTIAL


def test_missing_macro_candidates_leave_evidence_coverage_complete() -> None:
    analysis = _harvest(_pair(0, tick=0))
    assert analysis.evidence_coverage is TradeCoverage.COMPLETE
    assert analysis.cross_society_coverage is TradeCoverage.MISSING


def test_harvest_retains_per_family_coverage() -> None:
    candidates = (
        InterSocietyMacroCandidate(
            society_id=SOC_A, member_ids=("body-a",), window_tick=0
        ),
        InterSocietyMacroCandidate(
            society_id=SOC_B, member_ids=("body-b",), window_tick=0
        ),
    )
    analysis = _harvest(_pair(0, tick=0), macro_candidates=candidates)
    assert analysis.evidence_coverage is TradeCoverage.COMPLETE
    assert analysis.cross_society_coverage is TradeCoverage.COMPLETE
    assert analysis.lineage_coverage is TradeCoverage.COMPLETE
    assert analysis.coverage is TradeCoverage.COMPLETE
    assert analysis.cross_society_pair_count == 1


def test_harvest_feeds_empty_windows_to_lineage() -> None:
    analysis = _harvest((*_pair(0, tick=0), *_pair(1, tick=64)))
    relations = [row.relation for row in analysis.lineage]
    assert relations == ["dissolved", "emerged"]
    assert analysis.network_count == 2


def test_harvest_is_deterministic_across_event_order() -> None:
    events = [*_pair(0, tick=0), *_pair(1, tick=32)]
    first = _harvest(events)
    shuffled = list(events)
    random.Random(7).shuffle(shuffled)
    second = _harvest(shuffled)
    assert first.transfers == second.transfers
    assert first.corridors == second.corridors
    assert first.networks == second.networks
    assert first.lineage == second.lineage
    assert first.notices == second.notices


def test_harvest_notices_are_sorted_and_deduplicated() -> None:
    analysis = _harvest(
        (
            _event(
                "evt-1",
                Given(
                    recipient_id=EntityId("body-b"),
                    item_id=EntityId("unknown-item"),
                ),
            ),
        )
    )
    assert analysis.notices == tuple(sorted(set(analysis.notices)))
    assert "trade_networks_unknown_item_kind" in analysis.notices


tick_strategy = st.integers(min_value=0, max_value=200)


@given(ticks=st.lists(tick_strategy, min_size=0, max_size=8))
def test_harvest_never_exceeds_caps(ticks) -> None:
    events = []
    for ordinal, tick in enumerate(ticks):
        events.extend(_pair(ordinal, tick=tick))
    policy = type(POLICY)(
        max_transfer_rows=4,
        max_corridors=2,
        max_networks=1,
        max_lineage_edges=2,
        max_cross_society_pairs=1,
    )
    analysis = _harvest(events, policy=policy)
    assert analysis.transfer_count <= 4
    assert analysis.corridor_count <= 2
    assert analysis.network_count <= 1
    assert len(analysis.lineage) <= 2
    assert analysis.cross_society_pair_count <= 1
