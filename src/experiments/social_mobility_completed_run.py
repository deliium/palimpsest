"""Completed-run bridge for detached social-mobility analysis."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Final

from analysis.organization_operations import (
    OrganizationOperationHarvestRows,
    harvest_organization_operation_rows,
)
from analysis.social_mobility_analysis import (
    SocialMobilityAnalysis,
    harvest_social_mobility_analysis,
)
from analysis.social_mobility_contract import (
    SocialMobilityError,
    build_social_mobility_identity_map,
)
from analysis.social_mobility_genealogy import (
    harvest_social_mobility_genealogy,
)
from analysis.social_mobility_outcomes import (
    harvest_social_mobility_outcomes,
)
from analysis.social_mobility_policy import SocialMobilityAnalysisPolicy
from experiments.economic_inequality_completed_run import (
    economic_inequality_recipe_mappings,
)
from world.events import WorldEvent

__all__ = [
    "build_completed_run_social_mobility_analysis",
    "social_mobility_recipe_mappings",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.social_mobility_completed_run"
)


def social_mobility_recipe_mappings(
    runner_config: object,
) -> tuple[Mapping[str, str], Mapping[str, str]]:
    """Reuse the production catalog mappings; mismatch yields nothing."""

    return economic_inequality_recipe_mappings(runner_config)


def build_completed_run_social_mobility_analysis(
    runner_result: object,
    *,
    runner_config: object,
    committed_events: Sequence[WorldEvent],
    run_id: str,
    organization_operation_rows: Sequence[OrganizationOperationHarvestRows] = (),
    policy: SocialMobilityAnalysisPolicy | None = None,
    window_end: int | None = None,
) -> SocialMobilityAnalysis:
    """Build one bounded completed-run analysis from committed evidence."""

    if type(run_id) is not str or not run_id:
        raise SocialMobilityError("social_mobility_invalid_input")
    if isinstance(committed_events, (str, bytes)) or not isinstance(
        committed_events, Sequence
    ):
        raise SocialMobilityError("social_mobility_invalid_input")
    events = tuple(committed_events)
    if not events or any(type(event) is not WorldEvent for event in events):
        raise SocialMobilityError("social_mobility_invalid_input")

    identity_map = build_social_mobility_identity_map(
        runner_config=runner_config, events=events
    )
    genealogy = harvest_social_mobility_genealogy(
        events, identity_map=identity_map, policy=policy
    )
    rows = tuple(organization_operation_rows)
    if not rows:
        ledgers = getattr(runner_result, "organization_operation_ledgers", None)
        if ledgers:
            rows = harvest_organization_operation_rows(ledgers)
    output_kinds, structure_kinds = social_mobility_recipe_mappings(runner_config)
    outcomes = harvest_social_mobility_outcomes(
        events,
        identity_map=identity_map,
        practical_knowledge_audits=tuple(
            getattr(runner_result, "practical_knowledge_audits", ()) or ()
        ),
        teaching_audits=tuple(getattr(runner_result, "teaching_audits", ()) or ()),
        organization_operation_rows=rows,
        recipe_output_kinds=output_kinds,
        recipe_structure_kinds=structure_kinds,
        policy=policy,
    )
    analysis = harvest_social_mobility_analysis(
        genealogy=genealogy,
        outcomes=outcomes,
        policy=policy,
        window_end=window_end,
    )
    _LOG.debug(
        "social_mobility_completed_run events=%d owners=%d edges=%d rows=%d",
        len(events),
        analysis.owner_count,
        analysis.genealogy_edge_count,
        analysis.row_count,
    )
    return analysis
