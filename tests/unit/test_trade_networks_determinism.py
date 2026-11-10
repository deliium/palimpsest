# mypy: ignore-errors
"""Trade-network determinism and canonical ordering."""

from __future__ import annotations

import random
from types import SimpleNamespace

from hypothesis import given
from hypothesis import strategies as st

from analysis.trade_networks_analysis import harvest_trade_networks_analysis
from analysis.trade_networks_identity import mint_corridor_token
from world.events import Given, ItemCrafted, ResourceHarvested
from world.identifiers import EntityId, EventId, RecipeId
from world.values import ItemKind


def _event(token: str, details: object, *, tick: int = 0, origin: str = "loc-a"):
    return SimpleNamespace(
        event_id=EventId(token),
        tick=tick,
        sequence=0,
        actor_id=EntityId("body-a"),
        details=details,
        occurrence=SimpleNamespace(origin_location_id=EntityId(origin)),
    )


def _events():
    return (
        _event(
            "evt-c1",
            ItemCrafted(
                recipe_id=RecipeId("cook_food"),
                created_item_id=EntityId("item-1"),
                resulting_holder_id=EntityId("body-a"),
                duration_ticks=1,
            ),
            tick=1,
            origin="loc-a",
        ),
        _event(
            "evt-g1",
            Given(recipient_id=EntityId("body-b"), item_id=EntityId("item-1")),
            tick=2,
            origin="loc-b",
        ),
        _event(
            "evt-h1",
            ResourceHarvested(
                recipe_id=RecipeId("gather_material"),
                resource_id=EntityId("res-1"),
                success=True,
                duration_ticks=1,
                resulting_resource_quantity=1.0,
                created_item_id=EntityId("item-2"),
            ),
            tick=33,
            origin="loc-b",
        ),
        _event(
            "evt-g2",
            Given(recipient_id=EntityId("body-c"), item_id=EntityId("item-2")),
            tick=34,
            origin="loc-a",
        ),
    )


def _harvest(events):
    return harvest_trade_networks_analysis(
        events=tuple(events),
        recipe_item_kinds={
            "cook_food": ItemKind.FOOD,
            "gather_material": ItemKind.MATERIAL,
        },
    )


def test_two_runs_are_row_level_identical() -> None:
    first = _harvest(_events())
    second = _harvest(_events())
    assert first.transfers == second.transfers
    assert first.supplies == second.supplies
    assert first.corridors == second.corridors
    assert first.flows == second.flows
    assert first.locations == second.locations
    assert first.dependence == second.dependence
    assert first.networks == second.networks
    assert first.lineage == second.lineage
    assert first.notices == second.notices
    assert first.coverage is second.coverage
    assert first.evidence_coverage is second.evidence_coverage


def test_reversed_event_order_is_canonical() -> None:
    events = list(_events())
    random.Random(3).shuffle(events)
    assert _harvest(events).transfers == _harvest(_events()).transfers


def test_empty_window_dissolves_then_reemerges() -> None:
    analysis = _harvest(_events())
    relations = [row.relation for row in analysis.lineage]
    assert relations == ["dissolved", "emerged"]
    assert "continued" not in relations


def test_sustained_counts_are_stable_and_never_score_like() -> None:
    first = _harvest(_events())
    second = _harvest(_events())
    assert sum(1 for row in first.lineage if row.sustained) == sum(
        1 for row in second.lineage if row.sustained
    )
    for row in first.lineage:
        assert type(row.sustained) is bool
        assert not hasattr(row, "score")


corridor_strategy = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126),
    min_size=1,
    max_size=24,
)


@given(
    left=corridor_strategy,
    right=corridor_strategy,
)
def test_ids_are_stable_for_generated_corridor_pairs(left: str, right: str) -> None:
    assert mint_corridor_token(left, right) == mint_corridor_token(left, right)
    if left != right:
        assert mint_corridor_token(left, right) != mint_corridor_token(right, left)
