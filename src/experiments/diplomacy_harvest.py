"""Completed-run diplomacy harvest bridge (read-only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from analysis.diplomacy_alignment import (
    DiplomacyAnalysisSummary,
    DiplomacyEnvoyAlignmentRow,
    TreatyRecollectionAlignmentRow,
    classify_diplomacy_envoy_alignment,
    classify_treaty_recollection_alignment,
    summarize_diplomacy,
)
from analysis.diplomacy_detection import (
    DiplomaticRelationCandidate,
    detect_diplomacy_candidates,
)
from analysis.diplomacy_identity import (
    DiplomacyAnalysis,
    TreatyVersionLineageEdge,
    assign_diplomacy_identities,
    derive_treaty_version_lineage,
)
from analysis.diplomacy_lanes import InterSocietyRelationRow
from analysis.diplomacy_layers import DiplomacyLayerView, project_diplomacy_layers
from analysis.diplomacy_objective import (
    DiplomacyObjectiveAnchorRow,
    diplomacy_objective_anchor_rows_from_events,
)
from analysis.diplomacy_rows import DiplomacyHarvestRows, harvest_diplomacy_rows
from simulation.diplomacy_status import TreatyStatusRow, derive_treaty_statuses

__all__ = [
    "DiplomacyHarvest",
    "build_completed_run_diplomacy_harvest",
]


@dataclass(frozen=True, slots=True)
class DiplomacyHarvest:
    run_id: str
    generated_tick: int
    rows: DiplomacyHarvestRows
    candidates: tuple[DiplomaticRelationCandidate, ...]
    analysis: tuple[DiplomacyAnalysis, ...]
    summary: DiplomacyAnalysisSummary
    layers: DiplomacyLayerView
    alignment: tuple[DiplomacyEnvoyAlignmentRow, ...]
    objective_rows: tuple[DiplomacyObjectiveAnchorRow, ...]
    lane_rows: tuple[InterSocietyRelationRow, ...]
    treaties: tuple[object, ...] = ()
    treaty_versions: tuple[object, ...] = ()
    treaty_declarations: tuple[object, ...] = ()
    treaty_recollections: tuple[object, ...] = ()
    treaty_misrepresentations: tuple[object, ...] = ()
    treaty_lineage: tuple[TreatyVersionLineageEdge, ...] = ()
    treaty_alignment: tuple[TreatyRecollectionAlignmentRow, ...] = ()
    treaty_statuses: tuple[TreatyStatusRow, ...] = ()


def _run_id(runner_result: object) -> str:
    value = getattr(getattr(runner_result, "run_id", None), "value", None)
    return value if type(value) is str and value else "run-unknown"


def build_completed_run_diplomacy_harvest(
    runner_result: object,
    *,
    committed_events: Sequence[object] = (),
    entity_to_agent: Mapping[Any, Any] | None = None,
    lane_rows: Sequence[InterSocietyRelationRow] = (),
) -> DiplomacyHarvest:
    """Harvest exported diplomacy ledgers and objective lane anchors."""

    mapping = dict(entity_to_agent or {})
    ledgers = tuple(getattr(runner_result, "diplomacy_ledgers", ()))
    rows = harvest_diplomacy_rows(ledgers, entity_to_agent=mapping)
    anchors = diplomacy_objective_anchor_rows_from_events(committed_events, mapping)
    lane_tuple = tuple(lane_rows)
    candidates = detect_diplomacy_candidates(rows, lane_tuple)
    treaty_lineage = derive_treaty_version_lineage(rows.treaty_versions)
    analysis = assign_diplomacy_identities(
        candidates,
        treaty_rows=rows.treaties,
        treaty_versions=rows.treaty_versions,
        treaty_declarations=rows.treaty_declarations,
        treaty_lineage=treaty_lineage,
    )
    alignment = classify_diplomacy_envoy_alignment(rows)
    treaty_alignment = classify_treaty_recollection_alignment(rows)
    layers = project_diplomacy_layers(
        rows,
        candidates,
        analysis,
        objective_rows=anchors,
        coverage=rows.coverage.value,
    )
    summary = summarize_diplomacy(rows, candidates, layers, alignment, treaty_alignment)
    tick = getattr(runner_result, "ticks_committed", 0)
    generated_tick = tick if type(tick) is int and tick >= 0 else 0
    statuses = derive_treaty_statuses(
        ledgers,
        getattr(runner_result, "representation_ledgers", ()),
        tick=generated_tick,
    )
    return DiplomacyHarvest(
        run_id=_run_id(runner_result),
        generated_tick=generated_tick,
        rows=rows,
        candidates=candidates,
        analysis=analysis,
        summary=summary,
        layers=layers,
        alignment=alignment,
        objective_rows=anchors,
        lane_rows=lane_tuple,
        treaties=rows.treaties,
        treaty_versions=rows.treaty_versions,
        treaty_declarations=rows.treaty_declarations,
        treaty_recollections=rows.treaty_recollections,
        treaty_misrepresentations=rows.treaty_misrepresentations,
        treaty_lineage=treaty_lineage,
        treaty_alignment=treaty_alignment,
        treaty_statuses=tuple(statuses),
    )
