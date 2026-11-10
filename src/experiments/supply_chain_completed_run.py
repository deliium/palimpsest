"""Completed-run supply-chain analysis builder for trusted collectors."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, cast

from analysis.organization_operations import harvest_organization_operation_rows
from analysis.supply_chain_analysis import (
    SupplyChainAnalysis,
    harvest_supply_chain_analysis,
)
from analysis.supply_chain_events import (
    SupplyInfrastructureFact,
    SupplyOrganizationClaim,
    SupplyRecipeSpec,
    SupplySkillLevel,
)
from analysis.supply_chain_policy import SupplyChainAnalysisPolicy
from world.events import WorldEvent
from world.identifiers import require_stable_id
from world.production import ProductionCatalog, production_catalog_digest
from world.supply_chain import production_chain_stages

__all__ = [
    "build_completed_run_supply_chain_analysis",
    "supply_chain_infrastructure",
    "supply_chain_organization_claims",
    "supply_chain_recipe_specs",
    "supply_chain_skill_levels",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.supply_chain_completed_run"
)


def _catalog(config: object) -> ProductionCatalog | None:
    agents = getattr(config, "agents", ()) or ()
    for agent in agents:
        cognition = getattr(agent, "cognition", None)
        catalog = getattr(cognition, "production_catalog", None)
        if type(catalog) is ProductionCatalog and catalog.recipe_count > 0:
            return catalog
    return None


def supply_chain_recipe_specs(config: object) -> tuple[SupplyRecipeSpec, ...]:
    """Read the run's own catalog and map stages to detached recipe specs."""
    catalog = _catalog(config)
    if catalog is None:
        return ()
    digests = {
        production_catalog_digest(
            tuple(recipe.recipe_id.value for recipe in catalog.recipes)
        )
    }
    for agent in getattr(config, "agents", ()) or ():
        other = getattr(getattr(agent, "cognition", None), "production_catalog", None)
        if type(other) is ProductionCatalog and other.recipe_count > 0:
            digests.add(
                production_catalog_digest(
                    tuple(recipe.recipe_id.value for recipe in other.recipes)
                )
            )
    if len(digests) > 1:
        _LOG.warning("supply_chain_recipe_catalog_mismatch")
    return tuple(
        SupplyRecipeSpec(
            recipe_id=stage.recipe_id,
            action=stage.action,
            resource_input_names=stage.resource_input_names,
            item_input_names=stage.item_input_names,
            input_kinds=stage.input_kinds,
            output_name=stage.output_name,
            output_kind=stage.output_kind,
            skill_domain=stage.skill_domain,
            tool_role=stage.tool_role,
        )
        for stage in production_chain_stages(catalog)
    )


def supply_chain_skill_levels(
    runner_result: object,
) -> tuple[SupplySkillLevel, ...]:
    levels: list[SupplySkillLevel] = []
    for row in getattr(runner_result, "skill_audits", ()) or ():
        side = getattr(row, "side", None)
        if getattr(side, "value", side) != "objective":
            continue
        agent = getattr(row, "agent_id", None)
        token = getattr(agent, "value", agent)
        domain = getattr(row, "domain", None)
        level = getattr(row, "level", None)
        if token is None or domain is None or level is None:
            continue
        levels.append(
            SupplySkillLevel(
                agent_token=str(token), domain=str(domain), level=float(level)
            )
        )
    deduped: dict[tuple[str, str], SupplySkillLevel] = {}
    for level in levels:
        deduped[(level.agent_token, level.domain)] = level
    return tuple(deduped[key] for key in sorted(deduped))


def supply_chain_infrastructure(
    runner_result: object,
) -> tuple[SupplyInfrastructureFact, ...]:
    grouped: dict[str, set[str]] = {}
    for asset in getattr(runner_result, "final_infrastructure_assets", ()) or ():
        status = getattr(asset, "status", None)
        if getattr(status, "value", status) != "operational":
            continue
        location = getattr(asset, "location_id", None)
        token = getattr(location, "value", location)
        kind = getattr(asset, "kind", None)
        kind_token = getattr(kind, "value", kind)
        if token is None or kind_token in (None, ""):
            continue
        grouped.setdefault(str(token), set()).add(str(kind_token))
    return tuple(
        SupplyInfrastructureFact(location_token=location, kinds=tuple(sorted(kinds)))
        for location, kinds in sorted(grouped.items())
        if kinds
    )


@dataclass(slots=True)
class _ClaimAccumulator:
    commands: set[str] = field(default_factory=set)
    actors: set[str] = field(default_factory=set)
    first: int | None = None
    last: int | None = None
    count: int = 0


def supply_chain_organization_claims(
    runner_result: object,
) -> tuple[SupplyOrganizationClaim, ...]:
    ledgers = getattr(runner_result, "organization_operation_ledgers", ()) or ()
    grouped: dict[str, _ClaimAccumulator] = {}
    for bundle in harvest_organization_operation_rows(ledgers):
        for row in bundle.procedures:
            organization = getattr(row, "organization_id", None)
            if not isinstance(organization, str) or not organization:
                continue
            entry = grouped.setdefault(organization, _ClaimAccumulator())
            command = getattr(row, "command_kind", None)
            if isinstance(command, str) and command:
                entry.commands.add(command)
            actor = getattr(row, "actor_id", None)
            if isinstance(actor, str) and actor:
                entry.actors.add(actor)
            first = getattr(row, "first_tick", None)
            last = getattr(row, "last_tick", None)
            if isinstance(first, int) and not isinstance(first, bool):
                entry.first = first if entry.first is None else min(entry.first, first)
            if isinstance(last, int) and not isinstance(last, bool):
                entry.last = last if entry.last is None else max(entry.last, last)
            entry.count += 1
    claims: list[SupplyOrganizationClaim] = []
    for organization, entry in sorted(grouped.items()):
        claims.append(
            SupplyOrganizationClaim(
                organization_token=organization,
                command_kinds=tuple(sorted(entry.commands)),
                actor_tokens=tuple(sorted(entry.actors)),
                first_tick=entry.first,
                last_tick=entry.last,
                claim_count=entry.count,
            )
        )
    return tuple(claims)


def build_completed_run_supply_chain_analysis(
    runner_result: object = None,
    *,
    committed_events: Sequence[object] | None,
    run_id: str,
    recipe_specs: Sequence[SupplyRecipeSpec] | None = None,
    policy: SupplyChainAnalysisPolicy | None = None,
    window_tick: int | None = None,
    skill_levels: object | None = None,
    infrastructure: object | None = None,
    organization_claims: object | None = None,
) -> SupplyChainAnalysis:
    if committed_events is None:
        raise ValueError("supply_chain_requires_events")
    require_stable_id("run_id", run_id)
    recipes = (
        tuple(recipe_specs)
        if recipe_specs is not None
        else supply_chain_recipe_specs(getattr(runner_result, "runner_config", None))
    )
    analysis = harvest_supply_chain_analysis(
        cast(tuple[WorldEvent, ...], tuple(committed_events)),
        recipes=recipes,
        policy=policy,
        window_tick=window_tick,
        skill_levels=(
            skill_levels
            if skill_levels is not None
            else supply_chain_skill_levels(runner_result)
        ),
        infrastructure=(
            infrastructure
            if infrastructure is not None
            else supply_chain_infrastructure(runner_result)
        ),
        organization_claims=(
            organization_claims
            if organization_claims is not None
            else supply_chain_organization_claims(runner_result)
        ),
    )
    _LOG.info(
        "supply_chain_completed_run stages=%s edges=%s coverage=%s",
        analysis.stage_count,
        analysis.edge_count,
        analysis.coverage.value,
    )
    return analysis
