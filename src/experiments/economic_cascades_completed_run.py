"""Completed-run economic-cascade analysis builder for trusted collectors."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final, cast

from analysis.economic_cascades_analysis import (
    EconomicCascadesAnalysis,
    harvest_economic_cascades_analysis,
)
from analysis.economic_cascades_policy import EconomicCascadesPolicy
from analysis.supply_chain_events import (
    SupplyRecipeSpec,
    SupplyStageObservation,
    supply_evidence_from_events,
)
from analysis.supply_chain_policy import default_supply_chain_analysis_policy
from experiments.supply_chain_completed_run import supply_chain_recipe_specs
from world.events import Died, RouteConditionChanged, WorldEvent
from world.identifiers import require_stable_id

__all__ = [
    "build_completed_run_economic_cascades_analysis",
    "cascade_infrastructure_facts",
    "cascade_labor_joins",
    "cascade_recipe_specs",
    "cascade_route_facts",
    "cascade_supply_stages",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_cascades_completed_run"
)


def cascade_recipe_specs(runner_result: object) -> tuple[SupplyRecipeSpec, ...]:
    """Read the run's declared catalog through the supply-chain bridge."""

    return supply_chain_recipe_specs(
        getattr(runner_result, "runner_config", None)
    )


def cascade_infrastructure_facts(
    runner_result: object,
) -> tuple[tuple[str, str, bool], ...]:
    """Map final infrastructure assets to detached location/kind facts."""

    facts: list[tuple[str, str, bool]] = []
    for asset in getattr(runner_result, "final_infrastructure_assets", ()) or ():
        location = getattr(asset, "location_id", None)
        location_token = getattr(location, "value", location)
        kind = getattr(asset, "kind", None)
        kind_token = getattr(kind, "value", kind)
        status = getattr(asset, "status", None)
        status_token = getattr(status, "value", status)
        if location_token in (None, "") or kind_token in (None, ""):
            continue
        facts.append(
            (
                str(location_token),
                str(kind_token),
                status_token == "operational",
            )
        )
    return tuple(sorted(facts))


def cascade_route_facts(
    committed_events: Sequence[WorldEvent],
) -> tuple[tuple[str, str, str], ...]:
    """Keep the latest committed status per ordered route edge."""

    latest: dict[tuple[str, str], str] = {}
    for event in committed_events:
        details = event.details
        if not isinstance(details, RouteConditionChanged):
            continue
        key = (
            details.origin_location_id.value,
            details.destination_location_id.value,
        )
        latest[key] = details.current_status
    return tuple(
        (origin, destination, status)
        for (origin, destination), status in sorted(latest.items())
    )


def cascade_labor_joins(
    committed_events: Sequence[WorldEvent],
    stages: Sequence[SupplyStageObservation],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Join objective actor tokens to the recipes they completed."""

    actor_tokens = {stage.actor_token for stage in stages if stage.actor_token}
    body_tokens = {
        event.details.body_id.value
        for event in committed_events
        if isinstance(event.details, Died)
    }
    if body_tokens and not (body_tokens & actor_tokens):
        _LOG.warning("economic_cascades_labor_token_space_mismatch")
    joined: dict[str, set[str]] = {}
    for stage in stages:
        if stage.completed and stage.actor_token in actor_tokens:
            joined.setdefault(stage.actor_token, set()).add(stage.recipe_id)
    return tuple(
        (actor, tuple(sorted(recipe_ids)))
        for actor, recipe_ids in sorted(joined.items())
    )


def cascade_supply_stages(
    committed_events: Sequence[WorldEvent],
    recipe_specs: Sequence[SupplyRecipeSpec],
) -> tuple[SupplyStageObservation, ...]:
    """Reconstruct detached stage observations from committed events."""

    harvest = supply_evidence_from_events(
        committed_events,
        policy=default_supply_chain_analysis_policy(),
        recipes=recipe_specs,
        skill_levels=(),
        infrastructure=(),
        organization_claims=(),
    )
    return harvest.rows


def build_completed_run_economic_cascades_analysis(
    runner_result: object = None,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    recipe_specs: Sequence[SupplyRecipeSpec] | None = None,
    stages: Sequence[SupplyStageObservation] | None = None,
    infrastructure: Sequence[tuple[str, str, bool]] | None = None,
    routes: Sequence[tuple[str, str, str]] | None = None,
    labor_joins: Sequence[tuple[str, tuple[str, ...]]] | None = None,
    policy: EconomicCascadesPolicy | None = None,
    window_end: int | None = None,
) -> EconomicCascadesAnalysis:
    """Build the bounded analysis from a completed run's detached inputs."""

    if committed_events is None:
        raise ValueError("economic_cascades_requires_events")
    require_stable_id("run_id", run_id)
    events = cast(tuple[WorldEvent, ...], tuple(committed_events))
    recipes = (
        tuple(recipe_specs)
        if recipe_specs is not None
        else cascade_recipe_specs(runner_result)
    )
    if not recipes:
        _LOG.warning("economic_cascades_recipe_catalog_mismatch")
    stage_rows = (
        tuple(stages)
        if stages is not None
        else cascade_supply_stages(events, recipes)
    )
    analysis = harvest_economic_cascades_analysis(
        events=events,
        recipe_specs=recipes,
        stages=stage_rows,
        infrastructure=(
            infrastructure
            if infrastructure is not None
            else cascade_infrastructure_facts(runner_result)
        ),
        routes=(
            routes
            if routes is not None
            else cascade_route_facts(events)
        ),
        labor_joins=(
            labor_joins
            if labor_joins is not None
            else cascade_labor_joins(events, stage_rows)
        ),
        policy=policy,
        window_end=window_end,
    )
    _LOG.info(
        "economic_cascades_completed_run windows=%s chains=%s",
        analysis.window_count,
        analysis.chain_count,
    )
    return analysis
