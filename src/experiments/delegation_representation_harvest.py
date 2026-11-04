"""Completed-run representation harvest bridge (read-only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from analysis.delegation_representation_alignment import (
    RepresentationAnalysisSummary,
    summarize_representation,
)
from analysis.delegation_representation_identity import (
    RepresentationAnalysis,
    derive_representation_lineage,
)
from analysis.delegation_representation_layers import (
    RepresentationLayerView,
    project_representation_layers,
)
from analysis.delegation_representation_objective import (
    RepresentationObjectiveAnchorRow,
    RepresentationWindowEvidence,
    build_representation_windows,
    representation_objective_anchor_rows_from_events,
)
from analysis.delegation_representation_rows import (
    RepresentationHarvestRows,
    harvest_representation_rows,
)

__all__ = [
    "RepresentationHarvest",
    "build_completed_run_representation_harvest",
]


@dataclass(frozen=True, slots=True)
class RepresentationHarvest:
    run_id: str
    generated_tick: int
    rows: RepresentationHarvestRows
    analysis: RepresentationAnalysis
    summary: RepresentationAnalysisSummary
    layers: RepresentationLayerView
    objective_rows: tuple[RepresentationObjectiveAnchorRow, ...]
    windows: tuple[RepresentationWindowEvidence, ...]


def _run_id(runner_result: object) -> str:
    value = getattr(getattr(runner_result, "run_id", None), "value", None)
    return value if type(value) is str and value else "run-unknown"


def build_completed_run_representation_harvest(
    runner_result: object,
    *,
    committed_events: Sequence[object] = (),
    entity_to_agent: Mapping[str, str] | None = None,
    window_ticks: int = 100,
) -> RepresentationHarvest:
    """Harvest exported representation ledgers and committed speech anchors."""

    mapping = dict(entity_to_agent or {})
    ledgers = tuple(getattr(runner_result, "representation_ledgers", ()))
    rows = harvest_representation_rows(ledgers, entity_to_agent=mapping)
    anchors = representation_objective_anchor_rows_from_events(
        committed_events, mapping
    )
    windows = build_representation_windows(
        rows, window_ticks=window_ticks, objective_rows=anchors
    )
    analysis = derive_representation_lineage(
        rows, objective_rows=anchors, window_ticks=window_ticks
    )
    summary = summarize_representation(rows, analysis, anchors=anchors, windows=windows)
    layers = project_representation_layers(
        rows,
        analysis,
        summary,
        windows=windows,
        objective_rows=anchors,
    )
    tick = getattr(runner_result, "ticks_committed", 0)
    generated_tick = tick if type(tick) is int and tick >= 0 else 0
    return RepresentationHarvest(
        run_id=_run_id(runner_result),
        generated_tick=generated_tick,
        rows=rows,
        analysis=analysis,
        summary=summary,
        layers=layers,
        objective_rows=anchors,
        windows=windows,
    )
