# ruff: noqa: E501
# mypy: disable-error-code="arg-type,assignment,union-attr,index,call-overload,attr-defined,no-untyped-def,unused-ignore,type-arg,comparison-overlap"
"""Completed-run harvest bridge for organized conflict."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from analysis.organized_conflict_alignment import (
    ConflictAlignmentRow,
    ConflictAnalysisSummary,
    align_conflict_interpretations,
    summarize_organized_conflict,
)
from analysis.organized_conflict_detection import (
    ConflictEpisodeCandidate,
    detect_organized_conflict_episodes,
)
from analysis.organized_conflict_identity import (
    ConflictLineageEdge,
    assign_organized_conflict_identities,
    derive_organized_conflict_lineage,
    join_organized_conflict_identities,
)
from analysis.organized_conflict_layers import (
    ConflictLayerView,
    project_conflict_layers,
)
from analysis.organized_conflict_policy import (
    OrganizedConflictAnalysisPolicy,
    default_organized_conflict_analysis_policy,
)
from analysis.organized_conflict_rows import (
    OrganizedConflictHarvestRows,
    harvest_organized_conflict_rows,
)

__all__ = [
    "OrganizedConflictHarvest",
    "build_completed_run_organized_conflict_harvest",
]


@dataclass(frozen=True, slots=True)
class OrganizedConflictHarvest:
    rows: OrganizedConflictHarvestRows
    candidates: tuple[ConflictEpisodeCandidate, ...]
    lineage: tuple[ConflictLineageEdge, ...]
    layers: ConflictLayerView
    alignment: tuple[ConflictAlignmentRow, ...]
    summary: ConflictAnalysisSummary
    notices: tuple[str, ...] = ()
    has_ledger: bool = False


def build_completed_run_organized_conflict_harvest(
    runner_result: object,
    committed_events: Sequence[object],
    policy: OrganizedConflictAnalysisPolicy | None = None,
) -> OrganizedConflictHarvest:
    """Compose one completed run's conflict analysis without changing the result."""

    resolved_policy = policy or default_organized_conflict_analysis_policy()
    ledgers = tuple(getattr(runner_result, "organized_conflict_ledgers", ()) or ())
    rows = harvest_organized_conflict_rows(
        ledgers, committed_events, policy=resolved_policy
    )
    candidates = assign_organized_conflict_identities(
        detect_organized_conflict_episodes(
            rows.objective_events, policy=resolved_policy
        )
    )
    lineage = derive_organized_conflict_lineage(candidates)
    org_candidates = tuple(getattr(runner_result, "organization_candidates", ()) or ())
    macro_candidates = tuple(
        getattr(
            getattr(runner_result, "macro_society_analysis", None), "candidates", ()
        )
        or ()
    )
    candidates = join_organized_conflict_identities(
        candidates, org_candidates, macro_candidates
    )
    layers = project_conflict_layers(rows, candidates)
    alignment = align_conflict_interpretations(rows.owner_interpretations, candidates)
    summary = summarize_organized_conflict(rows, candidates, alignment)
    return OrganizedConflictHarvest(
        rows=rows,
        candidates=candidates,
        lineage=lineage,
        layers=layers,
        alignment=alignment,
        summary=summary,
        notices=rows.notices,
        has_ledger=bool(ledgers),
    )
