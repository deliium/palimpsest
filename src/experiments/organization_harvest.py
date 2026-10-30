"""Completed-run organization harvest for detached publication.

This module reads exported owner ledgers from a finished run and normalizes them
into analysis rows. It never runs inside simulation, API, or persistence and
never feeds cognition.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from analysis.organization_detection import detect_organization_candidates
from analysis.organization_evidence import (
    OrganizationObjectiveAnchorRow,
    build_organization_windows,
)
from analysis.organization_identity import (
    OrganizationIdentityAssignment,
    assign_organization_identities,
)
from analysis.organization_layers import (
    OrganizationLayerView,
    project_organization_layers,
)
from analysis.organization_lineage import (
    OrganizationAnalysis,
    derive_organization_lineage,
)
from analysis.organizations import (
    OrganizationHarvestRows,
    harvest_organization_rows,
)
from simulation.organization_models import OrganizationArtifactError
from world.identifiers import require_exact_nonneg_int, require_stable_id

__all__ = [
    "OrganizationHarvest",
    "build_completed_run_organization_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.organization_harvest")


@dataclass(frozen=True, slots=True)
class OrganizationHarvest:
    run_id: str
    input_revision: str
    generated_tick: int
    owner_rows: tuple[OrganizationHarvestRows, ...]
    objective_rows: tuple[OrganizationObjectiveAnchorRow, ...] = ()
    window_ticks: int = 100
    assignment: OrganizationIdentityAssignment | None = None
    layer_view: OrganizationLayerView | None = None
    analysis: OrganizationAnalysis | None = None
    provenance_code: str = "ok"
    truncated_history: bool = False

    def __post_init__(self) -> None:
        require_stable_id("run_id", self.run_id)
        require_stable_id("input_revision", self.input_revision)
        require_exact_nonneg_int("generated_tick", self.generated_tick)
        if type(self.window_ticks) is not int or self.window_ticks <= 0:
            raise OrganizationArtifactError("organization_harvest_invalid")


def build_completed_run_organization_harvest(
    runner_result: object,
    *,
    run_id: str,
    input_revision: str,
    generated_tick: int,
    window_ticks: int = 100,
) -> OrganizationHarvest:
    """Harvest one completed run's exported organization ledgers."""

    ledgers = getattr(runner_result, "organization_concept_ledgers", ()) or ()
    rows = harvest_organization_rows(ledgers)
    if not rows:
        return OrganizationHarvest(
            run_id=run_id,
            input_revision=input_revision,
            generated_tick=generated_tick,
            owner_rows=(),
            window_ticks=window_ticks,
        )
    windows = build_organization_windows(rows, window_ticks)
    detection = detect_organization_candidates(windows)
    assignment = assign_organization_identities(detection)
    layers = project_organization_layers(assignment, rows)
    analysis = derive_organization_lineage(assignment, layer_view=layers)
    anchors = tuple(anchor for window in windows for anchor in window.anchors)
    truncated_history = any(edge.kind.value == "dissolved" for edge in analysis.edges)
    _LOG.info(
        "organization_harvest_completed_run run_id=%s owners=%s candidates=%s",
        run_id,
        len(rows),
        len(analysis.records),
    )
    return OrganizationHarvest(
        run_id=run_id,
        input_revision=input_revision,
        generated_tick=generated_tick,
        owner_rows=rows,
        objective_rows=anchors,
        window_ticks=window_ticks,
        assignment=assignment,
        layer_view=layers,
        analysis=analysis,
        provenance_code="history_truncated" if truncated_history else "ok",
        truncated_history=truncated_history,
    )
