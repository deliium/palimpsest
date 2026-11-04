"""Detached completed-run evidence harvest and receipt.

The harvest reads only an exported runner result and committed events. It never
reads live cognition, world state, or persistence, and it never changes the
scientific result.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from analysis.evidence_testimony_alignment import (
    EvidenceAnalysis,
    EvidenceAnalysisSummary,
    derive_evidence_lineage,
)
from analysis.evidence_testimony_contract import EvidenceCoverage
from analysis.evidence_testimony_layers import (
    EvidenceLayerView,
    project_evidence_layers,
)
from analysis.evidence_testimony_objective import (
    EvidenceObjectiveAnchorRow,
    EvidenceWindowEvidence,
    build_evidence_windows,
    evidence_objective_anchor_rows_from_events,
)
from analysis.evidence_testimony_rows import EvidenceHarvestRows, harvest_evidence_rows

__all__ = [
    "EvidenceTestimonyHarvest",
    "build_completed_run_evidence_harvest",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.evidence_testimony_harvest"
)


@dataclass(frozen=True, slots=True)
class EvidenceTestimonyHarvest:
    """Detached harvest output plus its publication receipt state."""

    rows: EvidenceHarvestRows
    windows: tuple[EvidenceWindowEvidence, ...]
    analysis: EvidenceAnalysis
    summary: EvidenceAnalysisSummary
    layers: EvidenceLayerView
    coverage: str
    receipt_status: str
    receipt_reason: str
    truncated: bool
    run_id: str = ""
    generated_tick: int = 0
    objective_rows: tuple[EvidenceObjectiveAnchorRow, ...] = field(default=())


def _entity_map(
    runner_result: object, explicit: Mapping[str, str] | None
) -> dict[str, str]:
    if explicit is not None:
        return dict(explicit)
    runner_config = getattr(runner_result, "runner_config", None)
    agents = getattr(runner_config, "agents", ()) or ()
    resolved: dict[str, str] = {}
    for agent in agents:
        entity = getattr(getattr(agent, "entity_id", None), "value", None)
        agent_id = getattr(getattr(agent, "agent_id", None), "value", None)
        if entity and agent_id:
            resolved[entity] = agent_id
    return resolved


def build_completed_run_evidence_harvest(
    runner_result: object,
    *,
    committed_events: Sequence[object] = (),
    entity_to_agent: Mapping[str, str] | None = None,
    window_ticks: int = 100,
) -> EvidenceTestimonyHarvest:
    """Harvest one completed run into detached evidence analysis."""

    ledgers = getattr(runner_result, "evidence_ledgers", None)
    if ledgers is None:
        ledgers = ()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        raise TypeError("evidence_ledgers must be an ordered sequence")

    rows = harvest_evidence_rows(ledgers, window_ticks=window_ticks)
    anchors = (
        evidence_objective_anchor_rows_from_events(
            committed_events, _entity_map(runner_result, entity_to_agent)
        )
        if committed_events
        else ()
    )
    windows = build_evidence_windows(
        rows, window_ticks=window_ticks, objective_rows=anchors
    )
    analysis = derive_evidence_lineage(
        rows, objective_rows=anchors, window_ticks=window_ticks
    )
    layers = project_evidence_layers(
        rows,
        analysis,
        analysis.summary,
        windows=windows,
        objective_rows=anchors,
    )
    partial = (
        rows.coverage is EvidenceCoverage.PARTIAL
        or not anchors
        or analysis.summary.coverage is EvidenceCoverage.PARTIAL
    )
    truncated = rows.coverage is EvidenceCoverage.PARTIAL
    if partial:
        _LOG.warning("evidence_testimony_harvest_partial reason=no_objective_events")
    has_rows = bool(rows.sources or rows.testimony or rows.items or rows.contradictions)
    run_id_value = getattr(runner_result, "run_id", "")
    run_id = getattr(run_id_value, "value", run_id_value)
    ticks = getattr(runner_result, "ticks_committed", 0)
    return EvidenceTestimonyHarvest(
        rows=rows,
        windows=windows,
        analysis=analysis,
        summary=analysis.summary,
        layers=layers,
        coverage=(
            EvidenceCoverage.PARTIAL.value
            if partial
            else EvidenceCoverage.COMPLETE.value
        ),
        receipt_status="ok" if has_rows else "empty",
        receipt_reason=(
            "evidence_testimony_truncated"
            if truncated
            else "evidence_testimony_empty"
            if not has_rows
            else "evidence_testimony_harvested"
        ),
        truncated=truncated,
        run_id=str(run_id) if run_id else "",
        generated_tick=ticks if type(ticks) is int and ticks >= 0 else 0,
        objective_rows=anchors,
    )
