"""Completed-run bridge for detached economic-inequality analysis."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.economic_inequality_analysis import (
    EconomicInequalityAnalysis,
    harvest_economic_inequality_analysis,
)
from analysis.economic_inequality_claims import (
    control_claim_rows_from_operations,
    credit_claim_rows_from_events,
)
from analysis.economic_inequality_contract import (
    EconomicInequalityError,
    economic_inequality_owner_token,
    economic_inequality_society_token,
)
from analysis.economic_inequality_events import (
    harvest_economic_inequality_evidence,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
)
from analysis.economic_inequality_rows import (
    EconomicCohortMembership,
    EconomicSocietyMembership,
)
from analysis.organization_operations import OrganizationOperationHarvestRows
from world.events import AgentCreated, WorldEvent
from world.production import (
    ItemProduct,
    ProductionCatalog,
    ShelterProduct,
    StoreProduct,
    production_catalog_digest,
)

__all__ = [
    "build_completed_run_economic_inequality_analysis",
    "economic_inequality_recipe_mappings",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.economic_inequality_completed_run"
)


def _catalogs(runner_config: object) -> tuple[ProductionCatalog, ...]:
    catalogs: list[ProductionCatalog] = []
    for agent in getattr(runner_config, "agents", ()) or ():
        catalog = getattr(getattr(agent, "cognition", None), "production_catalog", None)
        if type(catalog) is ProductionCatalog:
            catalogs.append(catalog)
    return tuple(catalogs)


def economic_inequality_recipe_mappings(
    runner_config: object,
) -> tuple[Mapping[str, str], Mapping[str, str]]:
    """Derive output/structure kind maps; mismatched catalogs yield nothing."""

    catalogs = _catalogs(runner_config)
    if not catalogs:
        return {}, {}
    digests = {
        production_catalog_digest(
            tuple(recipe.recipe_id.value for recipe in catalog.recipes)
        )
        for catalog in catalogs
    }
    if len(digests) != 1:
        _LOG.warning("economic_inequality_catalog_mismatch")
        return {}, {}
    output_kinds: dict[str, str] = {}
    structure_kinds: dict[str, str] = {}
    for recipe in catalogs[0].recipes:
        output = recipe.output
        if isinstance(output, ItemProduct):
            output_kinds[recipe.recipe_id.value] = output.item_kind.value
        elif isinstance(output, (ShelterProduct, StoreProduct)):
            if type(output) is StoreProduct:
                structure_kinds[recipe.recipe_id.value] = "store"
            elif type(output) is ShelterProduct:
                structure_kinds[recipe.recipe_id.value] = (
                    output.structure_kind.value
                )
    return output_kinds, structure_kinds


def _generation_memberships(
    events: Sequence[WorldEvent],
    owner_tokens: Sequence[str],
) -> tuple[EconomicCohortMembership, ...]:
    created: dict[str, tuple[int, int]] = {}
    for event in events:
        if type(event.details) is AgentCreated:
            created[economic_inequality_owner_token(event.details.body_id.value)] = (
                event.details.generation_index,
                event.tick,
            )
    memberships: list[EconomicCohortMembership] = []
    for token in sorted(set(owner_tokens)):
        generation, tick = created.get(token, (0, 0))
        memberships.append(
            EconomicCohortMembership(
                owner_token=token,
                generation_index=generation,
                first_tick=tick,
            )
        )
    return tuple(memberships)


def _society_memberships(
    macro_society_analysis: object | None,
) -> tuple[EconomicSocietyMembership, ...]:
    if macro_society_analysis is None:
        return ()
    records = getattr(macro_society_analysis, "records", ()) or ()
    memberships: list[EconomicSocietyMembership] = []
    for record in records:
        society_token = economic_inequality_society_token(
            record.macro_society_id
        )
        window_indexes = tuple(sorted(set(record.window_indexes)))
        if not window_indexes:
            continue
        for member in record.member_ids:
            memberships.append(
                EconomicSocietyMembership(
                    owner_token=economic_inequality_owner_token(member),
                    society_token=society_token,
                    window_indexes=window_indexes,
                )
            )
    return tuple(memberships)


def build_completed_run_economic_inequality_analysis(
    runner_result: object,
    *,
    runner_config: object,
    committed_events: Sequence[WorldEvent],
    run_id: str,
    macro_society_analysis: object | None = None,
    organization_operation_rows: Sequence[OrganizationOperationHarvestRows] = (),
    policy: EconomicInequalityAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> EconomicInequalityAnalysis:
    """Build one bounded completed-run analysis; never fails the run."""

    if type(run_id) is not str or not run_id:
        raise EconomicInequalityError("economic_inequality_invalid_input")
    if isinstance(committed_events, (str, bytes)) or not isinstance(
        committed_events, Sequence
    ):
        raise EconomicInequalityError("economic_inequality_invalid_input")
    events = tuple(committed_events)
    if any(type(event) is not WorldEvent for event in events):
        raise EconomicInequalityError("economic_inequality_invalid_input")

    output_kinds, structure_kinds = economic_inequality_recipe_mappings(
        runner_config
    )
    evidence = harvest_economic_inequality_evidence(
        events,
        policy=policy,
        recipe_output_kinds=output_kinds,
        recipe_structure_kinds=structure_kinds,
    )
    credit_rows = credit_claim_rows_from_events(events, policy=policy)
    control_rows = control_claim_rows_from_operations(
        organization_operation_rows, policy=policy
    )
    owner_tokens: list[str] = [
        row.owner_token  # type: ignore[attr-defined]
        for row in (
            *evidence.possession_rows,
            *evidence.access_rows,
            *credit_rows,
            *control_rows,
        )
    ]
    cohort_memberships = _generation_memberships(events, owner_tokens)
    society_memberships = _society_memberships(macro_society_analysis)
    analysis = harvest_economic_inequality_analysis(
        possession_rows=evidence.possession_rows,
        access_rows=evidence.access_rows,
        credit_rows=credit_rows,
        control_rows=control_rows,
        cohort_memberships=cohort_memberships,
        society_memberships=society_memberships,
        policy=policy,
        window_end=window_end,
    )
    _LOG.debug(
        "economic_inequality_completed_run events=%d owners=%d "
        "credit_rows=%d control_rows=%d",
        len(events),
        analysis.owner_count,
        len(credit_rows),
        len(control_rows),
    )
    return analysis
