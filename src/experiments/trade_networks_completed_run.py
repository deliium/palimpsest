"""Completed-run trade-network analysis builder for trusted collectors."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final, cast

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
)
from analysis.trade_networks_analysis import (
    TradeNetworksAnalysis,
    harvest_trade_networks_analysis,
)
from analysis.trade_networks_contract import TradeNetworksError
from analysis.trade_networks_policy import (
    TradeNetworksAnalysisPolicy,
)
from world.events import WorldEvent
from world.identifiers import require_stable_id
from world.values import ItemKind

__all__ = [
    "build_completed_run_trade_networks_analysis",
    "trade_network_macro_candidates",
    "trade_network_recipe_item_kinds",
    "trade_network_trade_post_locations",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.trade_networks_completed_run"
)

_WINDOW_TICKS: Final[int] = 32


def _recipe_kinds_from_config(config: object) -> dict[str, ItemKind]:
    from world.production import ItemProduct

    kinds: dict[str, ItemKind] = {}
    for agent in getattr(config, "agents", ()) or ():
        cognition = getattr(agent, "cognition", None)
        catalog = getattr(cognition, "production_catalog", None)
        for recipe in getattr(catalog, "recipes", ()) or ():
            output = getattr(recipe, "output", None)
            if type(output) is not ItemProduct:
                continue
            recipe_id = getattr(recipe, "recipe_id", None)
            token = getattr(recipe_id, "value", None)
            if not isinstance(token, str) or not token:
                continue
            existing = kinds.get(token)
            if existing is not None and existing is not output.item_kind:
                _LOG.warning(
                    "trade_networks_conflicting_recipe_kind recipe_token=%s",
                    token,
                )
                continue
            kinds[token] = output.item_kind
    return kinds


def _kind_token(value: object) -> str:
    token = getattr(value, "value", value)
    return token if isinstance(token, str) else str(token)


def _trade_post_locations_from_result(runner_result: object) -> tuple[str, ...]:
    locations: set[str] = set()
    analysis = getattr(runner_result, "infrastructure_networks_analysis", None)
    for row in getattr(analysis, "assets", ()) or ():
        if _kind_token(getattr(row, "kind", "")) != "trade_post":
            continue
        if _kind_token(getattr(row, "status", "")) != "operational":
            continue
        location = getattr(getattr(row, "location_id", None), "value", None)
        if isinstance(location, str) and location:
            locations.add(location)
    for asset in getattr(runner_result, "final_infrastructure_assets", ()) or ():
        if _kind_token(getattr(asset, "kind", "")) != "trade_post":
            continue
        if _kind_token(getattr(asset, "status", "")) != "operational":
            continue
        location = getattr(getattr(asset, "location_id", None), "value", None)
        if isinstance(location, str) and location:
            locations.add(location)
    return tuple(sorted(locations))


def _macro_candidates_from_result(
    runner_result: object,
) -> tuple[InterSocietyMacroCandidate, ...]:
    analysis = getattr(runner_result, "macro_society_analysis", None)
    candidates: dict[tuple[str, int], InterSocietyMacroCandidate] = {}
    for record in getattr(analysis, "records", ()) or ():
        society = getattr(record, "macro_society_id", None)
        members = getattr(record, "member_ids", ()) or ()
        if not isinstance(society, str) or not society:
            continue
        first_tick = int(getattr(record, "first_tick", 0) or 0)
        last_tick = int(getattr(record, "last_tick", first_tick) or first_tick)
        first_window = first_tick // _WINDOW_TICKS
        last_window = last_tick // _WINDOW_TICKS
        for window in range(first_window, last_window + 1):
            tick = window * _WINDOW_TICKS
            key = (society, tick)
            if key in candidates:
                continue
            candidates[key] = InterSocietyMacroCandidate(
                society_id=society,
                member_ids=tuple(str(member) for member in members),
                window_tick=tick,
            )
    return tuple(candidates[key] for key in sorted(candidates))


def build_completed_run_trade_networks_analysis(
    runner_result: object = None,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    macro_candidates: Sequence[InterSocietyMacroCandidate] = (),
    policy: TradeNetworksAnalysisPolicy | None = None,
    window_tick: int | None = None,
    recipe_item_kinds: Mapping[str, ItemKind] | None = None,
    item_kind_by_id: Mapping[str, ItemKind] | None = None,
    trade_post_locations: Sequence[str] = (),
) -> TradeNetworksAnalysis:
    """Build one completed run's trade analysis from committed events only."""
    if committed_events is None:
        raise ValueError("trade_networks_completed_run_requires_events")
    require_stable_id("run_id", run_id)
    resolved_recipes = (
        dict(recipe_item_kinds)
        if recipe_item_kinds is not None
        else _recipe_kinds_from_config(getattr(runner_result, "runner_config", None))
    )
    resolved_posts = (
        tuple(trade_post_locations)
        if trade_post_locations
        else _trade_post_locations_from_result(runner_result)
    )
    resolved_candidates = (
        tuple(macro_candidates)
        if macro_candidates
        else _macro_candidates_from_result(runner_result)
    )
    try:
        analysis = harvest_trade_networks_analysis(
            events=cast(tuple[WorldEvent, ...], tuple(committed_events)),
            macro_candidates=resolved_candidates,
            policy=policy,
            window_tick=window_tick,
            recipe_item_kinds=resolved_recipes,
            item_kind_by_id=item_kind_by_id,
            trade_post_locations=resolved_posts,
        )
    except TradeNetworksError:
        raise
    _LOG.info(
        "trade_networks_completed_run transfers=%s corridors=%s networks=%s "
        "coverage=%s",
        analysis.transfer_count,
        analysis.corridor_count,
        analysis.network_count,
        analysis.coverage.value,
    )
    return analysis


def trade_network_recipe_item_kinds(config: object) -> dict[str, ItemKind]:
    """Public helper for collectors extracting ItemProduct recipe outputs."""
    return _recipe_kinds_from_config(config)


def trade_network_trade_post_locations(runner_result: object) -> tuple[str, ...]:
    """Public helper for collectors extracting operational trade posts."""
    return _trade_post_locations_from_result(runner_result)


def trade_network_macro_candidates(
    runner_result: object,
) -> tuple[InterSocietyMacroCandidate, ...]:
    """Public helper for collectors expanding contemporaneous societies."""
    return _macro_candidates_from_result(runner_result)
