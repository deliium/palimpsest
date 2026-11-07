"""Completed-run border harvest composition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from analysis.borders_alignment import (
    align_border_interpretations,
    summarize_borders,
)
from analysis.borders_contract import (
    BorderAlignmentRow,
    BorderAnalysisSummary,
    BorderCandidate,
    BorderLineageEdge,
    BorderOverlapRow,
    BorderPatternRow,
)
from analysis.borders_detection import (
    BorderBoundaryState,
    detect_border_disputes,
    detect_border_overlaps,
    detect_boundary_recognitions,
    detect_control_patterns,
)
from analysis.borders_identity import (
    assign_border_identities,
    derive_border_lineage,
    join_border_identities,
)
from analysis.borders_layers import BorderLayerView, project_border_layers
from analysis.borders_policy import (
    BordersAnalysisPolicy,
    default_borders_analysis_policy,
)
from analysis.borders_rows import BorderHarvestRows, harvest_border_rows
from analysis.specifications import METRIC_CATALOG_VERSION

__all__ = ["BordersHarvest", "build_completed_run_borders_harvest"]

_LOG_FAMILIES: Final[tuple[str, ...]] = (
    "border_claim_structure",
    "border_overlap_contest",
    "border_agreement_recognition",
    "border_control_alignment",
)


@dataclass(frozen=True, slots=True)
class BordersHarvest:
    rows: BorderHarvestRows
    overlaps: tuple[BorderOverlapRow, ...]
    patterns: tuple[BorderPatternRow, ...]
    candidates: tuple[BorderCandidate, ...]
    lineage: tuple[BorderLineageEdge, ...]
    layers: BorderLayerView
    alignment: tuple[BorderAlignmentRow, ...]
    summary: BorderAnalysisSummary
    boundaries: tuple[BorderBoundaryState, ...] = ()
    notices: tuple[str, ...] = ()
    has_ledger: bool = False


def build_completed_run_borders_harvest(
    runner_result: object,
    committed_events: Sequence[object],
    policy: BordersAnalysisPolicy | None = None,
) -> BordersHarvest:
    """Compose one completed run's detached border analysis."""
    from simulation.borders_export import export_border_rows

    resolved = policy or default_borders_analysis_policy()
    ledgers = tuple(getattr(runner_result, "border_ledgers", ()) or ())
    exported = tuple(export_border_rows(ledger) for ledger in ledgers)
    rows = harvest_border_rows(exported, committed_events, policy=resolved)
    overlaps = detect_border_disputes(
        detect_border_overlaps(rows.claims, policy=resolved),
        rows.agreements,
        policy=resolved,
    )
    boundaries = detect_boundary_recognitions(rows.recognitions, rows.disputes)
    patterns = detect_control_patterns(
        rows.physical,
        rows.claims,
        rows.agreements,
        rows.disputes,
        policy=resolved,
    )
    candidates = assign_border_identities(rows.claims, patterns)
    lineage = derive_border_lineage(candidates)
    org_candidates = tuple(
        getattr(runner_result, "organization_candidates", ()) or ()
    )
    macro_candidates = tuple(
        getattr(
            getattr(runner_result, "macro_society_analysis", None),
            "candidates",
            (),
        )
        or ()
    )
    _ = join_border_identities(candidates, org_candidates, macro_candidates)
    layers = project_border_layers(rows, patterns)
    alignment = align_border_interpretations(
        rows.claims,
        rows.agreements,
        patterns,
        disputes=rows.disputes,
    )
    summary = summarize_borders(
        claims=rows.claims,
        agreements=rows.agreements,
        disputes=rows.disputes,
        physical_row_count=len(rows.physical),
        patterns=patterns,
        alignment=alignment,
        catalog_version=METRIC_CATALOG_VERSION,
        coverage=rows.coverage,
    )
    notices = tuple(sorted(set(rows.notices) | set(harvest_notices(rows))))
    return BordersHarvest(
        rows=rows,
        overlaps=overlaps,
        patterns=patterns,
        candidates=candidates,
        lineage=lineage,
        layers=layers,
        alignment=alignment,
        summary=summary,
        boundaries=boundaries,
        notices=notices,
        has_ledger=bool(ledgers),
    )


def harvest_notices(rows: BorderHarvestRows) -> tuple[str, ...]:
    notices: list[str] = []
    if rows.claims and not rows.physical:
        notices.append("insufficient_physical_evidence")
    if rows.agreements and not rows.claims:
        notices.append("agreement_without_claim")
    return tuple(notices)
