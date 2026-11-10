# mypy: ignore-errors
"""Completed-run trade analysis and collector injection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from experiments.catalog import EXPERIMENT_A_V1_CONDITION_IDS
from experiments.collectors import assemble_arm_metric_bundle
from experiments.trade_networks_completed_run import (
    build_completed_run_trade_networks_analysis,
    trade_network_macro_candidates,
)
from simulation.models import RunId
from world.events import Given, ItemCrafted
from world.identifiers import EntityId, EventId, RecipeId
from world.production import (
    HeldItemNameInput,
    ItemProduct,
    ProductionAction,
    ProductionCatalog,
    ProductionRecipe,
)
from world.values import ItemKind, ItemLoad

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


def _gift_events(tick: int = 0, ordinal: int = 0):
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
            origin="loc-a",
        ),
        _event(
            f"evt-g-{ordinal}",
            Given(
                recipient_id=EntityId("body-b"),
                item_id=EntityId(f"item-{ordinal}"),
            ),
            tick=tick + 1,
            origin="loc-b",
        ),
    )


def _runner_result(**kwargs):
    return SimpleNamespace(
        ticks_committed=2,
        final_infrastructure_assets=(),
        **kwargs,
    )


def test_completed_run_builder_uses_committed_events() -> None:
    analysis = build_completed_run_trade_networks_analysis(
        _runner_result(),
        committed_events=_gift_events(),
        run_id="run-1",
        recipe_item_kinds={"cook_food": ItemKind.FOOD},
    )
    assert analysis.transfer_count == 1
    assert analysis.corridor_count == 1


def test_builder_accepts_macro_society_analysis() -> None:
    record = SimpleNamespace(
        macro_society_id=SOC_A,
        member_ids=("body-a",),
        first_tick=0,
        last_tick=0,
    )
    record_b = SimpleNamespace(
        macro_society_id=SOC_B,
        member_ids=("body-b",),
        first_tick=0,
        last_tick=0,
    )
    result = _runner_result(
        macro_society_analysis=SimpleNamespace(records=(record, record_b))
    )
    analysis = build_completed_run_trade_networks_analysis(
        result,
        committed_events=_gift_events(),
        run_id="run-1",
    )
    assert analysis.cross_society_pair_count == 1


def test_macro_candidate_expands_across_overlapping_windows() -> None:
    record = SimpleNamespace(
        macro_society_id=SOC_A,
        member_ids=("body-a",),
        first_tick=0,
        last_tick=70,
    )
    result = _runner_result(macro_society_analysis=SimpleNamespace(records=(record,)))
    candidates = trade_network_macro_candidates(result)
    assert [candidate.window_tick for candidate in candidates] == [0, 32, 64]
    assert {candidate.society_id for candidate in candidates} == {SOC_A}


def test_builder_uses_production_catalog_recipe_kinds() -> None:
    recipe = ProductionRecipe(
        recipe_id=RecipeId("cook_food"),
        action=ProductionAction.CRAFT,
        duration_ticks=1,
        success_probability=1.0,
        inputs=(HeldItemNameInput(name="grain"),),
        output=ItemProduct(item_kind=ItemKind.FOOD, name="meal", load=ItemLoad(1)),
    )
    config = SimpleNamespace(
        agents=(
            SimpleNamespace(
                cognition=SimpleNamespace(
                    production_catalog=ProductionCatalog(recipes=(recipe,))
                )
            ),
        )
    )
    result = _runner_result(runner_config=config)
    analysis = build_completed_run_trade_networks_analysis(
        result,
        committed_events=_gift_events(),
        run_id="run-1",
    )
    assert analysis.transfers[0].flow_class.value == "food"


def test_builder_uses_operational_trade_posts() -> None:
    asset = SimpleNamespace(
        kind="trade_post",
        status="operational",
        location_id=EntityId("loc-b"),
    )
    result = _runner_result(
        infrastructure_networks_analysis=SimpleNamespace(assets=(asset,))
    )
    analysis = build_completed_run_trade_networks_analysis(
        result,
        committed_events=_gift_events(),
        run_id="run-1",
    )
    assert analysis.trade_post_location_count == 1


def test_builder_without_events_raises_safe_error() -> None:
    with pytest.raises(
        ValueError, match="trade_networks_completed_run_requires_events"
    ):
        build_completed_run_trade_networks_analysis(
            _runner_result(), committed_events=None, run_id="run-1"
        )


def _arm(events):
    config = SimpleNamespace(agents=())
    return SimpleNamespace(
        assignment=SimpleNamespace(run_id=RunId("run-1"), runner_config=config),
        runner_result=_runner_result(committed_events=events),
        config_fingerprint="a" * 64,
        committed_events=events,
    )


def test_collector_injects_trade_analysis() -> None:
    bundle = assemble_arm_metric_bundle(_arm(_gift_events()))
    families = {document.metric_family for document in bundle.documents}
    assert "trade_flow_composition" in families


def test_collector_missing_events_leaves_none() -> None:
    bundle = assemble_arm_metric_bundle(_arm(None))
    families = {document.metric_family for document in bundle.documents}
    assert "trade_flow_composition" not in families


def test_v1_gate_catalog_does_not_include_trade() -> None:
    assert not any("trade" in item for item in EXPERIMENT_A_V1_CONDITION_IDS)
